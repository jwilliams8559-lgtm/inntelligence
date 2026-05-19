"""
engine/crm/campaigns.py — Phase 6
Email campaign creation, sending, and demand-triggered automation.

Functions:
    create_draft_campaign(tenant_id, property_id, *, name, target_segment,
                          subject, body_html, scheduled_at=None,
                          trigger_source=None, trigger_metadata=None) -> campaign_id

    send_campaign(campaign_id) -> {campaign_id, recipient_count, delivered,
                                   opened, clicked, status, sent_at}
        Resolves target_segment to a guest list (intersecting marketing_consent),
        renders the subject+body per-guest, dispatches via SendGrid (or mock
        when SENDGRID_API_KEY is absent), writes campaign_recipients rows,
        and updates campaigns aggregate counts.

    check_and_create_campaigns(property_id, *, lookahead_days=90,
                               window_days=7, occupancy_floor=0.55,
                               min_lead_days=21) -> list[campaign_id]
        Walks the next *lookahead_days* of demand forecasts in rolling
        *window_days* windows; for any window with avg occupancy_forecast
        below *occupancy_floor* and lead time within [min_lead_days,
        lookahead_days], drafts a campaign aimed at Lapsed+VIP guests.

SendGrid:
    Real send path is implemented but only activates when SENDGRID_API_KEY
    is set in .env. Without that key the connector enters mock mode —
    every recipient is marked 'delivered' with deterministic open/click
    rates so the dashboard demo has realistic numbers.
"""
from __future__ import annotations

import logging
import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import requests

from engine.crm.guest_manager import (
    _sb_get, _sb_hdrs, _sb_patch, _sb_post, _sb_url, unsubscribe_token_for,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Campaign creation
# ─────────────────────────────────────────────────────────────────────────────

def create_draft_campaign(
    tenant_id:        str,
    property_id:      str,
    *,
    name:             str,
    target_segment:   str,
    subject:          str,
    body_html:        str,
    scheduled_at:     Optional[datetime] = None,
    trigger_source:   Optional[str]      = None,
    trigger_metadata: Optional[dict]     = None,
) -> Optional[str]:
    """Insert a draft (or scheduled) campaign row. Returns campaign_id."""
    body = {
        "tenant_id":        tenant_id,
        "property_id":      property_id,
        "name":             name,
        "target_segment":   target_segment,
        "subject":          subject,
        "body_html":        body_html,
        "status":           "scheduled" if scheduled_at else "draft",
        "scheduled_at":     scheduled_at.isoformat() if scheduled_at else None,
        "trigger_source":   trigger_source,
        "trigger_metadata": trigger_metadata,
    }
    out = _sb_post("campaigns", body)
    return out[0]["id"] if out else None


# ─────────────────────────────────────────────────────────────────────────────
#  Audience resolution
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_audience(property_id: str, segment: str) -> list[dict]:
    """
    Return guests for the property whose tags match *segment* (single tag
    or comma-separated 'vip,lapsed' meaning ANY-of).
    """
    if not segment:
        return []
    segments = [s.strip() for s in segment.split(",") if s.strip()]
    if not segments:
        return []

    # tags is a text[] in Postgres — use cs (contains) per-tag and OR with PostgREST's `or` filter.
    or_clauses = ",".join(f'tags.cs.{{"{s}"}}' for s in segments)
    params = {
        "property_id":       f"eq.{property_id}",
        "marketing_consent": "eq.true",
        "select":            "id,first_name,last_name,email_hash,tags,"
                             "preferred_room_type,home_city,home_state,"
                             "total_stays,total_revenue,unsubscribe_token",
        "or":                f"({or_clauses})",
    }
    return _sb_get("guests", params)


# ─────────────────────────────────────────────────────────────────────────────
#  SendGrid dispatch (with mock fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _sendgrid_key() -> str: return os.getenv("SENDGRID_API_KEY", "")


def _personalise(body_html: str, guest: dict, unsub_url: str) -> str:
    first = guest.get("first_name") or "Friend"
    last  = guest.get("last_name")  or ""
    fname_caps = first.title()
    return (body_html
            .replace("{{first_name}}", fname_caps)
            .replace("{{last_name}}",  last.title())
            .replace("{{full_name}}",  f"{fname_caps} {last.title()}".strip())
            .replace("{{unsubscribe_url}}", unsub_url))


def _send_via_sendgrid(
    api_key:   str,
    sender:    str,
    to_email:  str,
    subject:   str,
    html:      str,
) -> tuple[bool, Optional[str]]:
    """Returns (success, error). Email is encrypted in DB, so the caller must
    decrypt or, in our placeholder scheme, compute the recipient address
    out-of-band. The dashboard demo path uses the mock branch below."""
    try:
        r = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type":  "application/json"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from":    {"email": sender, "name": "The Gracious Collection"},
                "subject": subject,
                "content": [{"type": "text/html", "value": html}],
            },
            timeout=20,
        )
        if r.status_code in (200, 202):
            return (True, None)
        return (False, f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        return (False, str(exc))


def _mock_engagement(guest: dict, *, seed: int) -> tuple[str, datetime, datetime]:
    """
    Deterministic 'delivered → opened → clicked' simulation per guest.
    Open rate ≈ 38% overall, lifted for VIP/local guests.
    Click rate ≈ 18% of opens (so ~7% of total).
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    tags = set(guest.get("tags") or [])
    open_p  = 0.38 + (0.18 if "vip"   in tags else 0) + (0.08 if "local" in tags else 0)
    click_p = 0.18
    sent_at   = now
    opened_at = sent_at + timedelta(minutes=rng.randint(7, 240)) if rng.random() < open_p else None
    clicked_at = None
    if opened_at and rng.random() < click_p:
        clicked_at = opened_at + timedelta(seconds=rng.randint(30, 600))
    if clicked_at: return ("clicked",   sent_at, clicked_at)
    if opened_at:  return ("opened",    sent_at, opened_at)
    return ("delivered", sent_at, sent_at)


# ─────────────────────────────────────────────────────────────────────────────
#  send_campaign
# ─────────────────────────────────────────────────────────────────────────────

def send_campaign(campaign_id: str, *, db_conn: Any = None,
                  base_url: Optional[str] = None) -> dict:
    """
    Resolve audience, render emails, dispatch via SendGrid (or mock),
    write campaign_recipients, and update the campaigns aggregate counts.

    *base_url* — used to build unsubscribe links; defaults to
    APP_BASE_URL env var or 'http://localhost:5001'.
    """
    rows = _sb_get("campaigns", {
        "id":     f"eq.{campaign_id}",
        "select": "id,tenant_id,property_id,name,target_segment,subject,"
                  "body_html,status,scheduled_at",
        "limit":  "1",
    })
    if not rows:
        return {"error": f"campaign {campaign_id} not found"}
    camp = rows[0]
    if camp["status"] in ("sent", "sending"):
        return {"error": f"campaign already in status {camp['status']!r}"}

    audience = _resolve_audience(camp["property_id"], camp.get("target_segment") or "")
    if not audience:
        _sb_patch("campaigns", {"id": f"eq.{campaign_id}"}, {
            "status": "sent", "sent_at": datetime.now(timezone.utc).isoformat(),
            "recipient_count": 0,
        })
        return {"campaign_id": campaign_id, "recipient_count": 0,
                "delivered": 0, "opened": 0, "clicked": 0, "status": "sent"}

    _sb_patch("campaigns", {"id": f"eq.{campaign_id}"}, {"status": "sending"})

    api_key = _sendgrid_key()
    is_mock = not bool(api_key)
    base    = base_url or os.getenv("APP_BASE_URL", "http://localhost:5001")
    sender  = os.getenv("CAMPAIGN_SENDER", "hello@gracious.collection")

    delivered = opened = clicked = bounced = 0
    recipient_rows: list[dict] = []
    sent_at = datetime.now(timezone.utc)

    for idx, guest in enumerate(audience):
        unsub_url = f"{base}/unsubscribe?token={unsubscribe_token_for(guest['id'])}"
        rendered  = _personalise(camp.get("body_html") or "", guest, unsub_url)
        subj      = _personalise(camp.get("subject")   or "", guest, unsub_url)

        if is_mock:
            status, _t_sent, _t_event = _mock_engagement(guest, seed=idx + hash(campaign_id) % 100000)
            ok = True; err = None
        else:
            # Real send — for the placeholder PII scheme we can't recover the
            # raw email server-side, so live mode currently requires the
            # caller to have populated guest["email_plain"] via a KMS decrypt
            # step. In a production deployment that hook lives upstream of
            # this function.
            to_email = guest.get("email_plain")
            if not to_email:
                ok, err = (False, "no_decrypted_email")
                status  = "bounced"
            else:
                ok, err = _send_via_sendgrid(api_key, sender, to_email, subj, rendered)
                status  = "delivered" if ok else "bounced"

        if status == "clicked":   delivered += 1; opened += 1; clicked += 1
        elif status == "opened":  delivered += 1; opened += 1
        elif status == "delivered": delivered += 1
        else:                     bounced += 1

        recipient_rows.append({
            "campaign_id": campaign_id,
            "guest_id":    guest["id"],
            "status":      status,
            "sent_at":     sent_at.isoformat(),
            "opened_at":   (sent_at + timedelta(minutes=10)).isoformat() if status in ("opened","clicked") else None,
            "clicked_at":  (sent_at + timedelta(minutes=12)).isoformat() if status == "clicked" else None,
        })

    # Bulk insert recipients
    if recipient_rows:
        _sb_post("campaign_recipients", recipient_rows, prefer="return=minimal")

    _sb_patch("campaigns", {"id": f"eq.{campaign_id}"}, {
        "status":          "sent",
        "sent_at":         sent_at.isoformat(),
        "recipient_count": len(audience),
        "delivered_count": delivered,
        "opened_count":    opened,
        "clicked_count":   clicked,
    })

    summary = {
        "campaign_id":     campaign_id,
        "recipient_count": len(audience),
        "delivered":       delivered,
        "opened":          opened,
        "clicked":         clicked,
        "bounced":         bounced,
        "status":          "sent",
        "sent_at":         sent_at.isoformat(),
        "mock":            is_mock,
    }
    logger.info("send_campaign %s → %s", campaign_id, summary)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
#  Demand-triggered campaign automation
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_TEMPLATE_HTML = """
<div style="font-family:Georgia,serif;max-width:540px;margin:0 auto;padding:24px;background:#FAF6EE;color:#2C3E50;">
  <h1 style="color:#1F3A5F;font-size:24px;margin-bottom:4px;">Hi {{first_name}},</h1>
  <p style="font-size:14px;color:#7C8B9B;margin-top:0;">We saved a date for you at the Anchorage.</p>
  <p style="font-size:15px;line-height:1.6;margin-top:18px;">
    We have <strong>{{window_label}}</strong> coming up with quieter days and softer rates —
    starting at <strong>${{from_rate}}/night</strong> for our Garden View &amp; Waterview rooms.
    A perfect window to slip away to Beaufort.
  </p>
  <a href="https://anchorage1770inn.com/book?utm=tgc-demand&dates={{window_dates}}"
     style="display:inline-block;padding:12px 24px;background:#1F3A5F;color:white;
            text-decoration:none;border-radius:6px;font-weight:bold;margin-top:18px;">
    See Available Rooms
  </a>
  <p style="font-size:11px;color:#94A3B8;margin-top:28px;border-top:1px solid #E2E8F0;padding-top:12px;">
    The Gracious Collection · Boutique Hospitality Intelligence<br/>
    <a href="{{unsubscribe_url}}" style="color:#94A3B8;">Unsubscribe</a>
  </p>
</div>
""".strip()


def check_and_create_campaigns(
    property_id:      str,
    *,
    lookahead_days:   int     = 90,
    window_days:      int     = 7,
    occupancy_floor:  float   = 0.55,
    min_lead_days:    int     = 21,
) -> list[str]:
    """
    Scan demand forecasts for a property; for any *window_days*-long window
    with avg forecasted occupancy below *occupancy_floor* and lead time in
    [*min_lead_days*, *lookahead_days*], draft a demand-triggered campaign.

    Returns the list of campaign_ids that were created. Existing drafts for
    the same window are not duplicated.
    """
    today = date.today()
    start = today + timedelta(days=min_lead_days)
    end   = today + timedelta(days=lookahead_days)

    rows = _sb_get("rate_recommendations", {
        "property_id": f"eq.{property_id}",
        "target_date": f"gte.{start.isoformat()}",
        "and":         f"(target_date.lte.{end.isoformat()})",
        "select":      "target_date,demand_score,recommended_rate,room_type_id",
        "order":       "target_date.asc",
    })
    if not rows:
        return []

    # Tenant for the property
    p = _sb_get("properties", {"id": f"eq.{property_id}", "select": "tenant_id,name"})
    if not p:
        return []
    tenant_id = p[0]["tenant_id"]

    # Group by date — avg demand across room types as occupancy proxy.
    # demand_score in 0..100 is roughly inversely correlated with availability;
    # we map score → occupancy_proxy via /100, then look for soft windows
    # where avg occupancy_proxy < occupancy_floor.
    by_date: dict[date, list[dict]] = {}
    for r in rows:
        d = date.fromisoformat(r["target_date"])
        by_date.setdefault(d, []).append(r)

    sorted_dates = sorted(by_date.keys())
    if len(sorted_dates) < window_days:
        return []

    soft_windows: list[tuple[date, date, float, float]] = []
    last_window_end = today
    for i in range(len(sorted_dates) - window_days + 1):
        wstart = sorted_dates[i]
        wend   = sorted_dates[i + window_days - 1]
        if wstart < last_window_end:
            continue  # don't overlap soft windows
        scores: list[float] = []
        rates:  list[float] = []
        for d in sorted_dates[i:i + window_days]:
            for rec in by_date[d]:
                if rec.get("demand_score") is not None:
                    scores.append(float(rec["demand_score"]))
                if rec.get("recommended_rate"):
                    rates.append(float(rec["recommended_rate"]))
        if not scores:
            continue
        occ_proxy = (sum(scores) / len(scores)) / 100.0
        if occ_proxy < occupancy_floor:
            soft_windows.append((wstart, wend, occ_proxy, min(rates) if rates else 0))
            last_window_end = wend + timedelta(days=1)

    if not soft_windows:
        return []

    # Don't duplicate drafts that already cover the same windows
    existing = _sb_get("campaigns", {
        "property_id": f"eq.{property_id}",
        "status":      "in.(draft,scheduled)",
        "select":      "trigger_metadata",
        "trigger_source": "eq.demand",
    })
    existing_keys = {
        (d.get("window_start"), d.get("window_end"))
        for d in (c.get("trigger_metadata") or {} for c in existing)
    }

    out: list[str] = []
    for wstart, wend, occ, from_rate in soft_windows:
        key = (wstart.isoformat(), wend.isoformat())
        if key in existing_keys:
            continue
        label = f"{wstart.strftime('%b %-d')}–{wend.strftime('%b %-d')}"
        subject = (f"A quiet week in Beaufort — {label} from ${from_rate:.0f}/night")
        body = (_DEFAULT_TEMPLATE_HTML
                .replace("{{window_label}}", label)
                .replace("{{window_dates}}", f"{wstart.isoformat()}_{wend.isoformat()}")
                .replace("{{from_rate}}",    f"{from_rate:.0f}"))
        cid = create_draft_campaign(
            tenant_id, property_id,
            name=f"Demand fill · {label}",
            target_segment="vip,lapsed",
            subject=subject,
            body_html=body,
            trigger_source="demand",
            trigger_metadata={
                "window_start": wstart.isoformat(),
                "window_end":   wend.isoformat(),
                "avg_occupancy_proxy": round(occ, 3),
                "from_rate":     from_rate,
                "lead_days":     (wstart - today).days,
            },
        )
        if cid:
            out.append(cid)
            logger.info("Demand campaign drafted: %s · %s · occ=%.2f · from $%.0f",
                        cid, label, occ, from_rate)
    return out


__all__ = [
    "create_draft_campaign", "send_campaign",
    "check_and_create_campaigns", "_DEFAULT_TEMPLATE_HTML",
]


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def _cli_main() -> None:
    import argparse, json as _json
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--slug", default="anchorage-1770-demo")
    p.add_argument("--check-demand", action="store_true",
                   help="Run check_and_create_campaigns to draft demand-triggered campaigns")
    p.add_argument("--send", default=None, help="Send a campaign by id")
    args = p.parse_args()

    sb = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=none"}
    t = requests.get(f"{sb}/rest/v1/tenants", headers=h,
                      params={"slug": f"eq.{args.slug}", "select": "id"},
                      timeout=10).json()[0]
    pr = requests.get(f"{sb}/rest/v1/properties", headers=h,
                       params={"tenant_id": f"eq.{t['id']}",
                               "select": "id,name", "limit": "1"},
                       timeout=10).json()[0]
    pid = pr["id"]
    print(f"  Property: {pr['name']}  ({pid})")

    if args.check_demand:
        print("\n── check_and_create_campaigns ──")
        created = check_and_create_campaigns(pid)
        print(f"  Drafts created: {len(created)}")
        for cid in created[:5]:
            print(f"    · {cid}")

    if args.send:
        print(f"\n── send_campaign({args.send}) ──")
        print(_json.dumps(send_campaign(args.send), indent=2))


if __name__ == "__main__":
    _cli_main()

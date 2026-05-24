#!/usr/bin/env python3
"""Rate data integrity validator.

Runs as the pre-commit hook. Reads from the Anchorage 1770 demo tenant
in Supabase and asserts that every API path that exposes a rate to the
customer agrees with the DB. Exits 1 on any failure so broken numbers
cannot be committed.

Two layers of checks:

  1. Business rules across all 90 days of rate_recommendations
     (hierarchy, bands, bounds, event surge).

  2. Cross-screen consistency — every endpoint that returns a rate must
     match the canonical value in rate_recommendations.

If credentials or the network are missing the validator still has to
make a decision. It hard-fails ("cannot prove the data is correct") so
commits stay blocked. Run from PricingEngine/ root.
"""
from __future__ import annotations

import datetime
import os
import sys
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ENV  = ROOT / ".env"
sys.path.insert(0, str(ROOT))

# Re-exec under the project venv if available — Flask + project deps live
# there, and the pre-commit hook needs them to test cross-screen consistency.
_VENV_PY = ROOT / "venv" / "bin" / "python3"
if _VENV_PY.exists() and os.path.realpath(sys.executable) != os.path.realpath(str(_VENV_PY)):
    os.execv(str(_VENV_PY), [str(_VENV_PY), __file__, *sys.argv[1:]])

TENANT_SLUG          = "anchorage-1770-demo"
WATER_FESTIVAL_START = datetime.date(2026, 7, 17)
WATER_FESTIVAL_END   = datetime.date(2026, 7, 26)
ADJ_BEFORE           = (datetime.date(2026, 7, 14), datetime.date(2026, 7, 16))
ADJ_AFTER            = (datetime.date(2026, 7, 27), datetime.date(2026, 7, 30))

# DB room-type names vary in spacing — accept any of these for each tier.
ROOM_ALIASES = {
    "waterfront": ("Waterfront Suite", "Waterfront"),
    "waterview":  ("Waterview Suite", "Water View Suite", "Waterview", "Water View"),
    "cottage":    ("Cottage Room", "Private Cottage", "Cottage"),
    "garden":     ("Garden View Room", "Garden View", "Garden"),
}

ABSOLUTE_FLOOR   = 150.0
ABSOLUTE_CEILING = 1200.0
EXCLUDED_CATEGORIES = ("airbnb_str", "budget_hotel")

# ANSI for terminal readability
G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; B = "\033[1m"; D = "\033[2m"; X = "\033[0m"

_failures: list[str] = []
_passed   = 0


def _print_pass(name: str, detail: str = "") -> None:
    global _passed
    _passed += 1
    print(f"  {G}PASS{X}  {name}" + (f"  {D}{detail}{X}" if detail else ""))


def _print_fail(name: str, detail: str) -> None:
    _failures.append(f"{name}: {detail}")
    print(f"  {R}FAIL{X}  {name}  {R}{detail}{X}")


def _load_env() -> dict[str, str]:
    """Load .env into os.environ so importing app (Flask + canonical helpers)
    sees the same Supabase credentials. Returns the merged dict for local use."""
    env: dict[str, str] = dict(os.environ)
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                env.setdefault(k, v)
                os.environ.setdefault(k, v)
    return env


def _sb_get(env: dict[str, str], path: str, params: dict | None = None) -> list[dict]:
    h = {
        "apikey":        env["SUPABASE_SERVICE_KEY"],
        "Authorization": f"Bearer {env['SUPABASE_SERVICE_KEY']}",
    }
    r = requests.get(f"{env['SUPABASE_URL']}/rest/v1/{path}",
                     headers=h, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _resolve_tenant(env: dict[str, str]) -> tuple[str, str, str, dict[str, str]]:
    """Returns (tenant_id, property_id, property_name, room_type_id_by_tier)."""
    tenants = _sb_get(env, "tenants", {"slug": f"eq.{TENANT_SLUG}", "select": "id"})
    if not tenants:
        raise RuntimeError(f"tenant {TENANT_SLUG!r} not found")
    tenant_id = tenants[0]["id"]

    props = _sb_get(env, "properties",
                    {"tenant_id": f"eq.{tenant_id}", "select": "id,name"})
    if not props:
        raise RuntimeError("no properties for tenant")
    property_id, property_name = props[0]["id"], props[0]["name"]

    rooms = _sb_get(env, "room_types",
                    {"property_id": f"eq.{property_id}",
                     "select": "id,name,base_rate"})
    name_to_id = {r["name"]: r["id"] for r in rooms}

    rt_ids: dict[str, str] = {}
    for tier, aliases in ROOM_ALIASES.items():
        for n in aliases:
            if n in name_to_id:
                rt_ids[tier] = name_to_id[n]
                break
    missing = [t for t in ROOM_ALIASES if t not in rt_ids]
    if missing:
        raise RuntimeError(f"room types missing for tiers: {missing}; have {list(name_to_id)}")
    return tenant_id, property_id, property_name, rt_ids


def _load_recs(env: dict[str, str], property_id: str,
               today: datetime.date, horizon: datetime.date
               ) -> list[dict]:
    recs = _sb_get(env, "rate_recommendations", {
        "property_id": f"eq.{property_id}",
        "target_date": f"gte.{today.isoformat()}",
        "select":      "room_type_id,target_date,recommended_rate,status",
        "order":       "target_date",
    })
    return [r for r in recs
            if r["target_date"] <= horizon.isoformat()
            and r["recommended_rate"] is not None]


def _load_cuthbert_rates(env: dict[str, str], property_id: str,
                         today: datetime.date, horizon: datetime.date
                         ) -> dict[str, float]:
    comps = _sb_get(env, "competitor_properties",
                    {"property_id":      f"eq.{property_id}",
                     "competitor_name":  "eq.Cuthbert House Inn",
                     "select":           "id"})
    if not comps:
        return {}
    cid = comps[0]["id"]
    rates = _sb_get(env, "competitor_rates", {
        "competitor_id": f"eq.{cid}",
        "rate_date":     f"gte.{today.isoformat()}",
        "select":        "rate_date,rate_amount,is_stale",
    })
    return {r["rate_date"]: float(r["rate_amount"])
            for r in rates
            if not r.get("is_stale") and r["rate_date"] <= horizon.isoformat()
            and r["rate_amount"] is not None}


# ── Business rule checks ────────────────────────────────────────────────

def check_hierarchy(by_date: dict, rt_ids: dict, dates_all: list[str]) -> None:
    wf, wv, co, gv = (rt_ids[k] for k in ("waterfront", "waterview", "cottage", "garden"))

    fails = [d for d in dates_all if by_date[d][wf] <= by_date[d][wv]]
    if fails:
        d0 = fails[0]
        _print_fail("R1  Waterfront > Waterview",
                    f"{len(fails)} date(s); e.g. {d0} "
                    f"WF=${by_date[d0][wf]:.0f} WV=${by_date[d0][wv]:.0f}")
    else:
        _print_pass("R1  Waterfront > Waterview", f"all {len(dates_all)} dates")

    fails = [d for d in dates_all if by_date[d][wv] <= by_date[d][co]]
    if fails:
        d0 = fails[0]
        _print_fail("R2  Waterview  > Cottage",
                    f"{len(fails)} date(s); e.g. {d0} "
                    f"WV=${by_date[d0][wv]:.0f} CO=${by_date[d0][co]:.0f}")
    else:
        _print_pass("R2  Waterview  > Cottage", f"all {len(dates_all)} dates")

    fails = [d for d in dates_all if by_date[d][co] < by_date[d][gv]]
    if fails:
        d0 = fails[0]
        _print_fail("R3  Cottage    >= Garden",
                    f"{len(fails)} date(s); e.g. {d0} "
                    f"CO=${by_date[d0][co]:.0f} GV=${by_date[d0][gv]:.0f}")
    else:
        _print_pass("R3  Cottage    >= Garden", f"all {len(dates_all)} dates")


def check_cuthbert_band(by_date: dict, rt_ids: dict,
                        cuthbert: dict[str, float]) -> None:
    if not cuthbert:
        _print_fail("R4  Waterfront within 98-108% of Cuthbert",
                    "no Cuthbert competitor rates in DB; cannot validate")
        return
    wf = rt_ids["waterfront"]
    fails: list[tuple[str, float, float, float]] = []
    checked = 0
    for d, c_rate in cuthbert.items():
        if d not in by_date or wf not in by_date[d]:
            continue
        ours = by_date[d][wf]
        pct = ours / c_rate
        checked += 1
        if not (0.98 <= pct <= 1.08):
            fails.append((d, ours, c_rate, pct))
    if fails:
        d, ours, c_rate, pct = fails[0]
        _print_fail("R4  Waterfront within 98-108% of Cuthbert",
                    f"{len(fails)}/{checked} dates outside band; "
                    f"e.g. {d} WF=${ours:.0f} Cuthbert=${c_rate:.0f} ({pct*100:.1f}%)")
    else:
        _print_pass("R4  Waterfront within 98-108% of Cuthbert",
                    f"all {checked} overlapping dates")


def _check_band(label: str, by_date: dict, rt_ids: dict, dates: list[str],
                upper_tier: str, lower_tier: str, lo: float, hi: float) -> None:
    up, lo_id = rt_ids[upper_tier], rt_ids[lower_tier]
    fails: list[tuple[str, float, float, float]] = []
    for d in dates:
        if up not in by_date[d] or lo_id not in by_date[d]:
            continue
        pct = by_date[d][lo_id] / by_date[d][up]
        if not (lo <= pct <= hi):
            fails.append((d, by_date[d][lo_id], by_date[d][up], pct))
    if fails:
        d, lo_r, up_r, pct = fails[0]
        _print_fail(label,
                    f"{len(fails)} date(s) outside band; e.g. {d} "
                    f"{lower_tier}=${lo_r:.0f} {upper_tier}=${up_r:.0f} ({pct*100:.1f}%)")
    else:
        _print_pass(label, f"all {len(dates)} dates")


def check_bounds(recs: list[dict]) -> None:
    low  = [r for r in recs if float(r["recommended_rate"]) < ABSOLUTE_FLOOR]
    high = [r for r in recs if float(r["recommended_rate"]) > ABSOLUTE_CEILING]
    if low:
        r = low[0]
        _print_fail("R8  Floor >= $150",
                    f"{len(low)} rec(s) below; e.g. room={r['room_type_id'][:8]} "
                    f"{r['target_date']} ${r['recommended_rate']}")
    else:
        _print_pass("R8  Floor >= $150", f"all {len(recs)} recs")
    if high:
        r = high[0]
        _print_fail("R9  Ceiling <= $1,200",
                    f"{len(high)} rec(s) above; e.g. room={r['room_type_id'][:8]} "
                    f"{r['target_date']} ${r['recommended_rate']}")
    else:
        _print_pass("R9  Ceiling <= $1,200", f"all {len(recs)} recs")


def check_water_festival_surge(by_date: dict, rt_ids: dict) -> None:
    wf = rt_ids["waterfront"]

    def _avg(start: datetime.date, end: datetime.date) -> float | None:
        rates = []
        d = start
        while d <= end:
            iso = d.isoformat()
            if iso in by_date and wf in by_date[iso]:
                rates.append(by_date[iso][wf])
            d += datetime.timedelta(days=1)
        return sum(rates) / len(rates) if rates else None

    fest = _avg(WATER_FESTIVAL_START, WATER_FESTIVAL_END)
    before = _avg(*ADJ_BEFORE)
    after  = _avg(*ADJ_AFTER)
    adj_rates = [x for x in (before, after) if x is not None]
    if fest is None or not adj_rates:
        _print_fail("R10 Water Festival >= +25% vs adjacent",
                    f"insufficient data; festival_avg={fest} adjacent={adj_rates}")
        return
    adj_avg = sum(adj_rates) / len(adj_rates)
    surge_pct = (fest - adj_avg) / adj_avg
    if surge_pct < 0.25:
        _print_fail("R10 Water Festival >= +25% vs adjacent",
                    f"festival_avg=${fest:.0f} adjacent_avg=${adj_avg:.0f} "
                    f"surge={surge_pct*100:+.1f}%")
    else:
        _print_pass("R10 Water Festival >= +25% vs adjacent",
                    f"festival_avg=${fest:.0f} vs ${adj_avg:.0f} = +{surge_pct*100:.1f}%")


# ── Cross-screen consistency checks ────────────────────────────────────

def check_calendar_vs_competitive(by_date: dict, rt_ids: dict,
                                  property_id: str) -> None:
    """X11: /api/calendar/per-room Waterfront on date X must equal the DB rate;
       /api/competitors/by-room-type our_rates[0] must also equal the DB rate.
       Both API paths are the customer-facing rate display surface."""
    try:
        import app as flask_app  # noqa: WPS433
        client = flask_app.app.test_client()
    except Exception as exc:  # noqa: BLE001
        _print_fail("X11 /api/calendar/per-room == DB == /api/competitors",
                    f"could not import Flask app: {type(exc).__name__}: {exc}")
        return

    # Pick a representative date — first date in DB recs that has Waterfront
    wf = rt_ids["waterfront"]
    sample = next((d for d in sorted(by_date.keys()) if wf in by_date[d]), None)
    if sample is None:
        _print_fail("X11 /api/calendar/per-room == DB == /api/competitors",
                    "no Waterfront recs in DB to sample")
        return
    db_rate = by_date[sample][wf]

    # /api/calendar/per-room
    r = client.get(f"/api/calendar/per-room?date={sample}&days=1")
    if r.status_code != 200:
        _print_fail("X11 /api/calendar/per-room == DB",
                    f"endpoint returned HTTP {r.status_code}")
        return
    payload = r.get_json() or {}
    rates_map = payload.get("rates", {})
    api_cal_rate = None
    for alias in ROOM_ALIASES["waterfront"]:
        if alias in rates_map and sample in rates_map[alias]:
            api_cal_rate = rates_map[alias][sample].get("recommended_rate")
            break

    if api_cal_rate is None:
        _print_fail("X11a /api/calendar/per-room has Waterfront",
                    f"no Waterfront entry for {sample} in /api/calendar/per-room response")
    elif abs(api_cal_rate - db_rate) > 1.0:
        _print_fail("X11a /api/calendar/per-room == DB",
                    f"{sample} WF: api=${api_cal_rate:.0f}  db=${db_rate:.0f}  Δ=${abs(api_cal_rate-db_rate):.0f}")
    else:
        _print_pass("X11a /api/calendar/per-room == DB",
                    f"{sample} WF: api=${api_cal_rate:.0f} db=${db_rate:.0f}")

    # /api/competitors/by-room-type
    r = client.get(f"/api/competitors/by-room-type?room_category=waterfront&date={sample}&days=1")
    if r.status_code != 200:
        _print_fail("X11b /api/competitors/by-room-type == DB",
                    f"endpoint returned HTTP {r.status_code}")
        return
    payload = r.get_json() or {}
    our_rates = payload.get("our_rates", [])
    api_cmp_rate = our_rates[0] if our_rates else None
    if api_cmp_rate is None:
        _print_fail("X11b /api/competitors/by-room-type has our_rates",
                    "missing our_rates[0]")
    elif abs(api_cmp_rate - db_rate) > 1.0:
        _print_fail("X11b /api/competitors/by-room-type == DB",
                    f"{sample} WF: api=${api_cmp_rate:.0f}  db=${db_rate:.0f}  Δ=${abs(api_cmp_rate-db_rate):.0f}")
    else:
        _print_pass("X11b /api/competitors/by-room-type == DB",
                    f"{sample} WF: api=${api_cmp_rate:.0f} db=${db_rate:.0f}")


def check_roi_report_vs_db(by_date: dict, rt_ids: dict,
                           name_to_id: dict[str, str]) -> None:
    """X12: every (date, room, rate) win cited in the ROI report must match the
       DB recommendation for that date/room (or be marked as not in window)."""
    try:
        from modules.hospitality import performance_engine
    except Exception as exc:  # noqa: BLE001
        _print_fail("X12 ROI report rates == DB",
                    f"could not import performance_engine: {exc}")
        return

    # Use V2_PROPERTY as the report does today
    try:
        from app import V2_PROPERTY
    except Exception:
        V2_PROPERTY = None
    rep = performance_engine.get_report(V2_PROPERTY, "professional")
    wins = rep.get("top_wins", [])
    if not wins:
        _print_pass("X12 ROI report rates == DB",
                    "report exposes no per-date wins; nothing to validate")
        return

    today = datetime.date.today()
    year = today.year
    fails: list[str] = []
    skipped = 0
    for w in wins:
        room = w.get("room", "")
        date_str = w.get("date", "")
        reported = w.get("rate_recommended")
        # parse "Jul 20" → date(year, 7, 20)
        try:
            dt = datetime.datetime.strptime(f"{date_str} {year}", "%b %d %Y").date()
        except ValueError:
            try:
                dt = datetime.datetime.strptime(date_str.split("-")[0].strip() + f" {year}", "%b %d %Y").date()
            except Exception:
                skipped += 1
                continue
        if dt < today:
            skipped += 1
            continue
        rt_id = name_to_id.get(room)
        if rt_id is None:
            # "Multiple rooms" or another freeform label — skip
            skipped += 1
            continue
        iso = dt.isoformat()
        if iso not in by_date or rt_id not in by_date[iso]:
            fails.append(f"{date_str} {room}: report=${reported} but DB has no rec")
            continue
        db_rate = by_date[iso][rt_id]
        if abs(float(reported) - db_rate) > 1.0:
            fails.append(f"{date_str} {room}: report=${reported} db=${db_rate:.0f}")

    if fails:
        _print_fail("X12 ROI report rates == DB",
                    f"{len(fails)} mismatch(es); first: {fails[0]}")
    else:
        _print_pass("X12 ROI report rates == DB",
                    f"validated {len(wins)-skipped} of {len(wins)} wins ({skipped} skipped)")


def check_comp_avg_excludes_str(env: dict[str, str], property_id: str) -> None:
    """X13: /api/competitors/by-room-type comp_avg must exclude airbnb_str +
       budget_hotel competitors. Verify by recomputing the expected average
       from the DB + comparing to what the endpoint returns."""
    try:
        import app as flask_app  # noqa: WPS433
        client = flask_app.app.test_client()
    except Exception as exc:  # noqa: BLE001
        _print_fail("X13 comp_avg excludes airbnb_str/budget_hotel",
                    f"could not import Flask app: {exc}")
        return

    today = datetime.date.today()
    r = client.get(f"/api/competitors/by-room-type?room_category=waterfront&date={today.isoformat()}&days=1")
    if r.status_code != 200:
        _print_fail("X13 comp_avg excludes airbnb_str/budget_hotel",
                    f"endpoint HTTP {r.status_code}")
        return
    payload = r.get_json() or {}
    competitors = payload.get("competitors", [])
    excluded_in_response = [c["name"] for c in competitors
                            if c.get("property_type") in EXCLUDED_CATEGORIES
                            and c.get("rates") and c["rates"][0] is not None]
    pbd = (payload.get("position_by_date") or [{}])[0]
    api_avg = pbd.get("comp_avg")

    # Recompute: include only non-excluded competitors with a rate
    eligible = [c["rates"][0] for c in competitors
                if c.get("property_type") not in EXCLUDED_CATEGORIES
                and c.get("rates") and c["rates"][0] is not None]
    expected_avg = int(sum(eligible) / len(eligible)) if eligible else None

    if api_avg is None and expected_avg is None:
        _print_pass("X13 comp_avg excludes airbnb_str/budget_hotel",
                    "no eligible competitors (vacuously true)")
        return
    if api_avg != expected_avg:
        _print_fail("X13 comp_avg excludes airbnb_str/budget_hotel",
                    f"api comp_avg=${api_avg} expected=${expected_avg} "
                    f"(excluded categories present in payload: {excluded_in_response})")
    else:
        _print_pass("X13 comp_avg excludes airbnb_str/budget_hotel",
                    f"comp_avg=${api_avg} from {len(eligible)} eligible peers; "
                    f"{len(excluded_in_response)} excluded category items present in payload")


# ── main ───────────────────────────────────────────────────────────────

def main() -> int:
    env = _load_env()
    if "SUPABASE_URL" not in env or "SUPABASE_SERVICE_KEY" not in env:
        print(f"{R}ERROR{X} .env missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        return 1

    try:
        tenant_id, property_id, property_name, rt_ids = _resolve_tenant(env)
    except Exception as exc:  # noqa: BLE001
        print(f"{R}ERROR{X} could not resolve tenant: {exc}")
        return 1

    today   = datetime.date.today()
    horizon = today + datetime.timedelta(days=90)
    recs    = _load_recs(env, property_id, today, horizon)
    cuth    = _load_cuthbert_rates(env, property_id, today, horizon)
    rooms   = _sb_get(env, "room_types",
                      {"property_id": f"eq.{property_id}", "select": "id,name"})
    name_to_id = {r["name"]: r["id"] for r in rooms}

    by_date: dict[str, dict[str, float]] = defaultdict(dict)
    for r in recs:
        by_date[r["target_date"]][r["room_type_id"]] = float(r["recommended_rate"])
    dates_all = sorted(d for d, rooms in by_date.items()
                       if all(rt_ids[k] in rooms for k in ROOM_ALIASES))

    print(f"\n{B}Rate Integrity Validation — {TENANT_SLUG}{X}")
    print(f"  property:           {property_name}  ({property_id})")
    print(f"  window:             {today} → {horizon}  ({(horizon-today).days} days)")
    print(f"  recs in window:     {len(recs)}")
    print(f"  dates with all 4 room types: {len(dates_all)}")
    print(f"  cuthbert dates:     {len(cuth)}")
    print()
    print(f"{B}Business Rules — Hierarchy{X}")
    check_hierarchy(by_date, rt_ids, dates_all)
    print()
    print(f"{B}Business Rules — Bands{X}")
    check_cuthbert_band(by_date, rt_ids, cuth)
    _check_band("R5  Waterview is 72-88% of Waterfront",
                by_date, rt_ids, dates_all, "waterfront", "waterview", 0.72, 0.88)
    _check_band("R6  Cottage   is 78-92% of Waterview",
                by_date, rt_ids, dates_all, "waterview", "cottage", 0.78, 0.92)
    _check_band("R7  Garden    is 85-97% of Cottage",
                by_date, rt_ids, dates_all, "cottage", "garden", 0.85, 0.97)
    print()
    print(f"{B}Business Rules — Bounds{X}")
    check_bounds(recs)
    print()
    print(f"{B}Business Rules — Event Surge{X}")
    check_water_festival_surge(by_date, rt_ids)
    print()
    print(f"{B}Cross-Screen Consistency{X}")
    check_calendar_vs_competitive(by_date, rt_ids, property_id)
    check_roi_report_vs_db(by_date, rt_ids, name_to_id)
    check_comp_avg_excludes_str(env, property_id)
    print()

    total = _passed + len(_failures)
    if _failures:
        print(f"{R}{B}╔══════════════════════════════════════════════════════════╗{X}")
        print(f"{R}{B}║  FAIL  {len(_failures)} of {total} checks failed{X}")
        print(f"{R}{B}╚══════════════════════════════════════════════════════════╝{X}")
        for f in _failures:
            print(f"  {R}•{X} {f}")
        return 1
    print(f"{G}{B}╔══════════════════════════════════════════════════════════╗{X}")
    print(f"{G}{B}║  PASS  all {total} checks passed{X}")
    print(f"{G}{B}╚══════════════════════════════════════════════════════════╝{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

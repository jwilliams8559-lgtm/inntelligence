#!/usr/bin/env python3
"""Generate ElevenLabs MP3 narration for each step of the /demo tour.

Walks the 12 NARRATIONS below (the canonical source of truth), calls
the ElevenLabs Text-to-Speech API with Adam (pNInz6obpgDQGcFmaJgB) at
the voice settings dialled in for the boutique-hospitality brand voice,
and writes step-01.mp3 through step-12.mp3 into
dashboard/public/demo-audio/. Skips files that already exist so reruns
only generate new or changed steps.

PHONETIC SPELLINGS — the narrations below intentionally spell three
words differently from the React captions (demoScript.ts) so Adam
pronounces them the way an innkeeper would say them out loud:

    written here          says aloud      English source
    Byoo-fort             "byoo-fort"     Beaufort
    Ree-BO                "ree-bo"        Ribaut (silent t)
    Inn-telligence        "inn telligence" INNtelligence (two syllables)

Do not "fix" these back to standard spellings — the audio quality
depends on the phonetic guides. The captions in demoScript.ts keep
the proper English spellings since those are shown to viewers.

Usage:
    python3 scripts/generate_demo_audio.py            # uses .env
    ELEVENLABS_API_KEY=sk_... python3 scripts/generate_demo_audio.py

To regenerate all 12: delete dashboard/public/demo-audio/ then re-run.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")


ROOT       = Path(__file__).resolve().parent.parent
OUT_DIR    = ROOT / "dashboard" / "public" / "demo-audio"
ENV_FILE   = ROOT / ".env"

VOICE_ID   = "pNInz6obpgDQGcFmaJgB"        # Adam
MODEL_ID   = "eleven_turbo_v2_5"
VOICE_SETTINGS = {
    "stability":         0.25,
    "similarity_boost":  0.82,
    "style":             0.55,
    "use_speaker_boost": True,
}


# ────────────────────────────────────────────────────────────────────
# Canonical narration text — 12 enhanced scripts for the /demo tour
# ────────────────────────────────────────────────────────────────────
NARRATIONS: list[str] = [
    # Step 1
    "Welcome to Inn-telligence. What you're about to see is a 19-room historic boutique inn on Bay Street in Byoo-fort, South Carolina — managing its pricing, its restaurant, its rooftop bar, its guest relationships, and its revenue... all from one platform. The moment you open Inn-telligence, before you look at a single rate — you see this. A gold alert banner across the top of the screen. 'Byoo-fort Water Festival. July 17th through July 26th. Approaching. No premium applied yet.' That's Inn-telligence telling you something important. The biggest tourism event in the Lowcountry is 57 days away. Your rooms aren't priced for it yet. And your competitors? They're already moving. This is the difference between a tool that REACTS... and a tool that ANTICIPATES. Inn-telligence monitors your local events calendar continuously — major festivals, USMC graduations at Parris Island, art walks, food festivals, everything that brings visitors to your town. And I want to be clear about something. Inn-telligence combines machine intelligence with human pricing expertise. The AI monitors your market 24 hours a day, 7 days a week — detecting demand shifts, analyzing competitors, generating recommendations. But every recommendation is reviewed through the lens of real hospitality pricing experience. You're not relying on an algorithm alone. You're getting the judgment of a seasoned pricing professional — delivered at the speed of software. Let's see what it's recommending for the Water Festival.",

    # Step 2 (action — cursor clicks July 20)
    "This is the Rate Calendar — the command center of Inn-telligence. A 90-day forward view of all 19 rooms at Bay Street Inn. Waterfront Suites across the top — premier front-of-house rooms with direct river views and porch access. Water View Rooms below. Garden Rooms. Classic Rooms. Every room type... every day... for the next three months. The gold cells stretching across July 17th through the 26th — those are Water Festival dates. Inn-telligence colors them automatically. You never miss your peak revenue period. Each cell shows three things. The recommended rate — large and clear. The base rate below it in gray — so you always know how far the engine has moved from your starting point. And a status dot — yellow means pending your approval... green means approved and live on all SEVEN of your OTA channels simultaneously. Right now — 363 pending recommendations. Three hundred and sixty-three individual rate decisions. Already made. Waiting for your review. Let me click July 20th — the Saturday at the absolute peak of Water Festival — and show you exactly how Inn-telligence arrived at its recommendation for the Waterfront Suite.",

    # Step 3 (action — cursor clicks Approve)
    "This — right here — is what makes Inn-telligence different from every other pricing tool on the market. For EVERY recommendation — every single one — Inn-telligence shows you exactly why it's recommending that number. Plain English. No algorithm jargon. No black box. Just a clear explanation you could read to a skeptical business partner and have them immediately understand. For the Waterfront Suite on July 20th — demand score: 92 out of 100. PEAK. The highest category. Here's what's driving it. Booking pace is running 23 percent ahead of last year — guests are booking Water Festival earlier than ever. The festival historically drives 94 percent occupancy across Byoo-fort's boutique properties. And your two closest competitors — Cuthbert House Inn and Rhett House Inn — are already SOLD OUT for that weekend. Completely full. At $560 and $510 respectively. And then there's this. Because Bay Street Inn provides chef-prepared breakfast every morning... The Parlor restaurant steps away... The Rooftop at Bay Street with panoramic river views... and the personal touch of innkeeper service — Inn-telligence calculates that you're offering approximately $136 more in real value per night than a comparable Airbnb on Bay Street. That's not a guess. It's a calculation based on what those individual amenities actually cost when purchased separately. The recommendation: $500 per night. Waterfront Suite. Three-night minimum stay. Let me approve it — and watch what happens.",

    # Step 4
    "I just clicked Approve. One click. Less than a second. And here's what happened in the background while you watched me click. That $500 rate for the Waterfront Suite on July 20th is now live — SIMULTANEOUSLY — on Booking dot com, Expedia, Airbnb, VRBO, Hotels dot com, Trip dot com, and Agoda. SEVEN channels. Updated at exactly the same time. In 2.3 seconds. Think about what that used to look like. Logging into each platform separately. Finding the right dates. Entering the rate. Saving it. Moving to the next platform. Doing it again. Seven times. For one room. On one date. With 19 rooms and 90 days to manage... that math becomes impossible very quickly. Innkeepers spend an average of 12 to 18 hours per week on manual rate management before Inn-telligence. Every one of those hours is time you could have spent with a guest... developing a new package... building relationships in your community... or simply having a day off. After Inn-telligence — most of our customers spend less than 30 minutes a week reviewing and approving recommendations. Everything else runs automatically.",

    # Step 5
    "See this button — top right corner. 'Approve All. 363.' One click. All 363 pending recommendations. Across all 19 rooms. Across 90 days forward. Published to all seven OTAs. Simultaneously. Now you might be wondering — is that SAFE? What if I disagree with one? What if the engine gets something wrong? That's exactly why Inn-telligence gives you complete control at every level. Approve everything at once for speed. Filter by room type and approve just the Waterfront Suites. Review each recommendation individually — read the reasoning — approve or override on a case by case basis. Type in whatever number you want. The engine accepts it. No argument. No friction. You are ALWAYS in control. Inn-telligence never publishes anything you haven't approved. And for innkeepers who want even less friction — there's Autopilot. Set your guardrails once. Maximum rate change per day. Minimum confidence threshold. Operating hours. Inn-telligence runs within those guardrails automatically... every morning... before you wake up. Most of our customers run Autopilot on standard rooms and manual review on their premier suites. Best of both worlds. Let me show you the competitive intelligence behind all of this.",

    # Step 6
    "This is the Competitive Intelligence center. Inn-telligence monitors 39 properties in the Byoo-fort market. But it doesn't treat them all the same — because they're NOT all the same. The green columns — Cuthbert House Inn, Rhett House Inn, Anchorage 1770 Inn — these are your direct boutique competitors. Properties offering a genuinely comparable guest experience. When Inn-telligence sets your rates, it pays close attention to these. The orange columns — labeled 'STR, not a peer' — those are short-term rental properties. Airbnb listings. VRBO units. Inn-telligence shows them for context... but here's the critical difference — it does NOT use those rates to set yours. An Airbnb on Bay Street at $199 a night is not your competition. Your guest at Bay Street Inn gets chef-prepared breakfast every morning... The Parlor steps away for dinner... The Rooftop for cocktails with river views... a genuine innkeeper who knows Byoo-fort and can tell them exactly where to go and what to see. The Airbnb guest gets a key code and a welcome message. These are NOT the same products. They should not be priced by the same logic. And one more thing worth knowing — when you subscribe to Inn-telligence, your market is protected. No competitor within a five-mile radius can access the same pricing intelligence. Your edge stays yours.",

    # Step 7
    "Every other revenue management platform for boutique inns prices rooms. ONLY rooms. The restaurant is invisible to them. The bar doesn't exist. The packages, the gift shop, the private events — none of it. Inn-telligence is the ONLY platform that manages all six revenue streams a boutique inn operates. This screen — the F&B Yield dashboard — is where we do it for The Parlor at Bay Street Inn and The Rooftop. Look at this table. Day of week. Average covers. Average check. Average revenue. Occupancy percentage. And RevPASH — Revenue Per Available Seat Hour. The food and beverage industry's equivalent of RevPAR. Tuesday and Wednesday — flagged in amber. Forty-four percent covers on Tuesday. Forty-six on Wednesday. Yield gaps. You have 100 seats available and you're filling fewer than half of them on your slowest nights. Inn-telligence recommends: a $38 prix fixe lunch to attract local Byoo-fort residents mid-week. A four to six pm happy hour on The Rooftop. And a Dinner and Stay package — combined room and dinner — that fills the room AND fills The Parlor simultaneously. On warm Byoo-fort evenings, The Parlor extends to the front porches overlooking Bay Street — 25 additional seats under the stars. Inn-telligence factors this seasonal capacity into its recommendations. Saturday — 92 percent occupancy — $3,476 in revenue. On Water Festival nights, Inn-telligence recommends a prix fixe dinner at $85 per person and a $25 minimum spend on The Rooftop. The annual revenue opportunity from optimizing just the slow nights alone — not even touching peak nights — is over $24,000. That's sitting on the table right now.",

    # Step 8
    "This is your Guest CRM — the relationship intelligence layer of Inn-telligence. Every guest who has stayed at Bay Street Inn is here. Complete history. Number of stays. Total lifetime revenue. Last visit date. How they booked. Which rooms they prefer. And segment tags Inn-telligence has automatically assigned based on their behavior. Margaret Whitfield from Charleston. Six stays. $7,250 in lifetime revenue. Last visit April 2026. VIP and Local — a high-value repeat guest who lives close enough to visit frequently. Catherine DuBose from Washington DC. Five stays. $6,420. Tagged Anniversary and VIP — Inn-telligence detected that she and her partner stay around the same dates each year. She's celebrating something meaningful. Every time. At the top of the screen — 16 outreach campaigns. Already drafted. Automatically generated for dates where occupancy is projected below target. The right guests... the right timing... the right offer. Queued for your review. One click sends them. For Margaret — a personal reach-out six weeks before Water Festival. Because historical data shows past VIP guests who receive a personal invitation at that lead time convert at about 34 percent. Not a mass email blast. A targeted, timed message to someone who has already demonstrated... she loves your property.",

    # Step 9
    "Every month, Inn-telligence produces this report. The ROI Performance Report. And I want to be specific about why — because it matters. Most software you buy just... does a thing. You pay for it. You use it. At renewal time you kind of remember it seemed helpful but can't quite put a number on it. Inn-telligence doesn't work that way. Every month — documentation. Exact numbers. Specific dates, room types, and rate decisions that generated additional revenue. Direct booking savings from guests captured through your website instead of an OTA. Total value delivered — in dollars — compared directly to your subscription cost. This month's report for Bay Street Inn: Engine revenue contribution — $4,840. The documented additional revenue from rate recommendations. The difference between what you would have charged... and what Inn-telligence recommended and you approved. Direct booking savings — $1,240. Commissions you didn't pay because guests booked directly instead of through Booking dot com or Expedia. Total value delivered — $6,080. Subscription cost — $699. Return on subscription — 8.7 TIMES. For every dollar you spent on Inn-telligence this month — you got $8.70 back. And every specific win listed right below. July 20th. Water Festival. Waterfront Suite. $378 became $535. $157 per night. Three nights. One room. One event. This is not a testimonial. This is YOUR data. From YOUR property. Documented and dated. Show it to your accountant. Show it to your bank. Show it to anyone who questions whether it's worth it.",

    # Step 10
    "Packages are one of the most underutilized revenue opportunities at boutique inns. Not because innkeepers don't know packages work — they DO. But because building them, pricing them correctly, and knowing WHEN to promote which ones takes time most owner-operators simply don't have. Inn-telligence handles this through the Package Intelligence module. The Anniversary Package — room, fresh flowers from a local Byoo-fort florist, a bottle of champagne on arrival. Inn-telligence recommends a $65 add-on above base room rate. How did it arrive at $65? It analyzed what comparable boutique inns nationally charge for this package — 71 percent of Select Registry properties offer some version of it — and what the actual components cost. The flowers. The champagne. The innkeeper's time to arrange it. The margin is healthy. And $65 feels like nothing to a couple celebrating an anniversary. At 22 percent conversion — roughly one in five guests who see the offer books it — that's $4,095 per month in additional revenue. From ONE package. And Inn-telligence knows exactly WHEN to promote it. Six weeks before Water Festival when anniversary travel spikes. Around Valentine's weekend. During the window when couples plan milestone celebrations. The Adventure Package, the Spa Enhancement, the Sunset Cruise, the Porch Breakfast for Two — each with its own pricing recommendation, its own conversion data, its own optimal promotion timing. You don't have to guess at any of it.",

    # Step 11
    "Everything you've just seen — the Rate Calendar... the Competitive Intelligence... F&B yield analysis... Guest CRM... ROI report — all of it is on your phone. Right now. Without downloading anything. Inn-telligence is a progressive web app. Open the link in Safari on your iPhone. Tap 'Add to Home Screen.' From that moment — it sits on your home screen and opens like a native app. No App Store. No download. No update waiting. This matters because innkeeping doesn't follow a desk schedule. You're checking in a guest and your phone buzzes — Cuthbert House just sold out for the weekend you have open dates. Inn-telligence caught it. You pull out your phone. See the alert. Tap to approve the rate increase. Put your phone back in your pocket. Thirty seconds. You never left the conversation. You're at dinner and a notification arrives — booking pace just spiked 40 percent for the next two weekends. A USMC graduation at Parris Island you hadn't fully accounted for. You review it. Approve it. Your rates are updated on all seven OTAs before you finish your appetizer. Or you're simply away — on vacation yourself — and you know Bay Street Inn is being managed intelligently while you're gone. Not by someone you're paying to sit at a desk... but by a system that monitors your market continuously and makes reasoned decisions within the guardrails you've set. That's what Inn-telligence is designed for.",

    # Step 12
    "Let me tell you who built Inn-telligence and why — because I think it matters. I'm Jim Williams. I bring over 20 years of professional pricing experience to this platform — including several years focused specifically on hospitality and independent inn markets. I hold the Certified Pricing Professional designation — the highest credential in the pricing field. I built Inn-telligence on real Byoo-fort, South Carolina market data — specifically calibrated for the boutique inn market on the historic district's Bay Street waterfront. I didn't build this in a vacuum. I spent years studying this market. Analyzing what Cuthbert House Inn and Rhett House Inn charge. Understanding how the Water Festival drives demand. Learning what a boutique inn with a restaurant, a rooftop bar, and a gift shop actually NEEDS from a pricing tool. The result is a platform that understands the boutique inn market from the inside. And I want to be clear about something. Inn-telligence is not just software running unsupervised. It's a combination of AI and human pricing expertise — continuously monitored, continuously refined. The machine works at speed and scale. The human judgment ensures it stays on target. For properties wanting even more — The Gracious Collection offers boutique hospitality consulting engagements. Hands-on revenue strategy, market positioning, and pricing architecture. Contact us to learn more. Inn-telligence was initially built and validated in the Lowcountry — one of the most competitive boutique inn markets in the American South. Since then we've tested and verified its methodology across diverse markets throughout the United States and Europe — from the Hudson Valley to the Cotswolds, from the Texas Hill Country to the Scottish Highlands. The analysis you're seeing today is calibrated for Byoo-fort, South Carolina. But the same engine — the same intelligence — works for YOUR market. Wherever you are. But the platform itself — Inn-telligence — starts at three hundred and ninety-nine dollars a month. And it pays for itself many times over. The Water Festival starts in 57 days. Every day you wait is a day your competitors are filling up at rates you could be charging. 14-day free trial. No credit card. And when you subscribe — your market is protected. No competitor within five miles can access the same intelligence. Your edge. Yours alone. Let's talk.",
]


def _load_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ELEVENLABS_API_KEY not found in environment or .env")


def _check_subscription(api_key: str) -> None:
    """Print remaining ElevenLabs character allowance before generating."""
    try:
        r = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"⚠ could not reach ElevenLabs subscription endpoint: {exc}")
        return

    if r.status_code != 200:
        print(f"⚠ subscription check returned HTTP {r.status_code}: {r.text[:200]}")
        return

    info     = r.json()
    used     = info.get("character_count", 0)
    limit    = info.get("character_limit", 0)
    tier     = info.get("tier", "?")
    remaining = max(limit - used, 0)
    pct      = (used / limit * 100) if limit else 0
    print(f"ElevenLabs subscription:")
    print(f"  tier:       {tier}")
    print(f"  used:       {used:,} / {limit:,} characters ({pct:.1f}% consumed)")
    print(f"  remaining:  {remaining:,} characters")
    print()


def _tts(api_key: str, text: str, out_path: Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text":           text,
        "model_id":       MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    out_path.write_bytes(r.content)


def main() -> int:
    api_key = _load_api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    _check_subscription(api_key)

    if len(NARRATIONS) != 12:
        sys.exit(f"Expected 12 narrations, found {len(NARRATIONS)}")

    total_chars = sum(len(n) for n in NARRATIONS)
    print(f"Generating {len(NARRATIONS)} files, ~{total_chars:,} characters total")
    print(f"Voice: Adam ({VOICE_ID}) · Model: {MODEL_ID}")
    print(f"Settings: stability {VOICE_SETTINGS['stability']} · "
          f"similarity {VOICE_SETTINGS['similarity_boost']} · "
          f"style {VOICE_SETTINGS['style']} · "
          f"speaker_boost {VOICE_SETTINGS['use_speaker_boost']}")
    print()

    generated = 0
    skipped   = 0
    for i, text in enumerate(NARRATIONS, start=1):
        out_path = OUT_DIR / f"step-{i:02d}.mp3"
        label    = f"step-{i:02d}"
        snippet  = text[:60].replace("\n", " ") + ("…" if len(text) > 60 else "")

        if out_path.exists():
            print(f"  ⏭  {label}  ({out_path.stat().st_size:>7,} bytes)  skipped — already exists")
            skipped += 1
            continue

        print(f"  ▶  {label}  generating…  ({len(text):>5} chars)  \"{snippet}\"")
        try:
            _tts(api_key, text, out_path)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗  {label}  FAILED: {exc}")
            continue
        size = out_path.stat().st_size
        print(f"  ✓  {label}  saved  ({size:>7,} bytes)")
        generated += 1

    print()
    print(f"Done. {generated} generated · {skipped} skipped (already on disk)")
    print(f"Output directory: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

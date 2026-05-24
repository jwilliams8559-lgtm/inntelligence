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
    "Let me show you what Inn-telligence does for Anchorage 1770 Inn... a 14-room historic boutique property on Bay Street in Byoo-fort, South Carolina. The moment you open Inn-telligence — before you even look at the rate calendar, before you check your competitors — you see THIS. An alert. A gold banner across the top of the screen. Byoo-fort Water Festival. July 17th through July 26th. Approaching. No premium applied yet. That's Inn-telligence telling you something important. The single biggest tourism event in the Lowcountry... is 57 days away. Your rooms haven't been priced for it yet. And your competitors? They're already moving. This is the difference between a tool that REACTS — and a tool that ANTICIPATES. Inn-telligence monitors your local events calendar... continuously. Not just the major festivals. But USMC graduations at Parris Island. The Wine and Food Festival. First Friday Art Walks. Everything that brings visitors to your town. It detected the Water Festival automatically. Calculated its historical impact on room demand. And flagged it for your attention. You didn't have to set a reminder. You didn't have to check a calendar. It just... told you. And of course Inn-telligence does this for every market — whether you're in Savannah, Charleston, the Hudson Valley, or the Finger Lakes. It learns your local events. Your specific competitors. Your demand patterns. What you're seeing today is calibrated for Byoo-fort, South Carolina. Let me take you to the rate calendar.",

    # Step 2 (action — cursor clicks July 20)
    "This is the Rate Calendar — the command center of Inn-telligence. What you're looking at is a 90-day forward view of every room at Anchorage 1770... with a rate recommendation for every single date. The Waterfront Suites across the top. Water View Suites below. Garden View Rooms. The Private Cottage. Every room type. Every day. For the next three months. The gold cells — stretching across July 17th through the 26th — those are Water Festival dates. Inn-telligence colors them automatically... so you never miss your peak revenue period. Each cell shows you three things. The recommended rate in large text. The base rate below it in gray — so you always know how far the engine has moved from your starting point. And a dot indicating status. Yellow means pending — waiting for your approval. Green means approved... and live on all SEVEN of your OTA channels simultaneously. Right now? There are 363 pending recommendations sitting in this calendar. Three hundred and sixty-three individual rate decisions. All made by Inn-telligence. Waiting for a human to review and approve. Let me click on July 20th — the Saturday at the peak of Water Festival — and show you EXACTLY how Inn-telligence arrived at its recommendation for the Waterfront Suite.",

    # Step 3 (action — cursor clicks Approve)
    "This... is the feature that makes Inn-telligence genuinely different from every other pricing tool on the market. Pay close attention. Because it's the thing our customers talk about most. For every single rate recommendation — every one — Inn-telligence shows you exactly WHY it's recommending that number. In plain English. No algorithm jargon. No unexplained outputs from a black box. Just a clear, readable explanation... that you could read out loud to a skeptical spouse or business partner. And have them immediately understand. For the Waterfront Suite on July 20th, the demand score is 92 out of 100. That's PEAK. The highest category. Here's what's driving that score. Booking pace this week? Running 23 percent ahead of the same period last year. Guests are booking the Water Festival earlier than they did in 2025. The Water Festival historically drives 94 percent occupancy across Byoo-fort's boutique properties. And your two closest direct competitors — Cuthbert House Inn and Rhett House Inn — are both already SOLD OUT for that weekend. Completely full. At $560 and $510 respectively. And then there's this. Because Anchorage 1770 provides chef-prepared breakfast every morning... the Ree-BO Social Club restaurant on the premises... a rooftop bar... and the personal touch of innkeeper service — Inn-telligence recognizes that you're offering approximately $136 more in real value per night... than a comparable Airbnb on Bay Street. That's not a guess. It's a CALCULATION. Based on what those individual amenities actually cost when purchased separately. The recommendation? $585 per night for the Waterfront Suite. About 4 percent above Cuthbert. Three-night minimum stay. Watch what happens when I click Approve.",

    # Step 4
    "I just clicked Approve. That's it. One click. On a button that took less than a second to press. And here's what just happened in the background... while you watched me click. That $500 rate for the Waterfront Suite on July 20th... is now LIVE. Simultaneously. Right now. On Booking dot com. Expedia. Airbnb. VRBO. Hotels dot com. Trip dot com. And Agoda. SEVEN channels. Updated at exactly the same time. In 2.3 seconds. Think about what that used to look like. Logging into each platform separately. Finding the right dates. Entering the rate. Saving it. Moving to the next platform. Doing it again. Seven times. For ONE room. On ONE date. And if you have 14 rooms and 90 days to manage? That math becomes overwhelming... very quickly. Innkeepers spend an average of 12 to 18 hours per week on manual rate management — before they use Inn-telligence. Every one of those hours is time you could have spent with a guest. Developing a new package. Working on the restaurant. Or simply having a day off. After Inn-telligence? Most of our customers spend LESS than 30 minutes per week reviewing and approving recommendations. Everything else runs automatically. Now... let me click Approve All — and publish everything at once.",

    # Step 5
    "You just saw 363 pending rate recommendations turn green simultaneously. One click. Every room. Every day. Every channel. All updated. Now — you might be wondering. Is that safe? What if I disagree with one of them? What if the engine makes a recommendation I don't like? That's exactly why Inn-telligence gives you complete control... at every level. You can approve all at once for speed. You can filter by room type and approve just the Waterfront Suites. You can review each recommendation individually. Read the reasoning. Approve or override on a case-by-case basis. You can override ANY rate — type in whatever number you want — and the engine accepts it. Without complaint. You're always in control. Inn-telligence NEVER publishes anything you haven't approved. And for innkeepers who want even less friction... there's Autopilot mode. In Autopilot, you set the guardrails. Maximum rate change per day. Minimum confidence threshold. Operating hours. And Inn-telligence runs within those guardrails... automatically. It publishes rates every morning. Responds to real-time changes in competitor availability. Adjusts for last-minute demand surges. Most of our customers run Autopilot on their standard room types — and manual review on their premium suites. Best of both worlds. Let me take you to the Competitive Intelligence center.",

    # Step 6
    "This is the Competitive Intelligence center. And the first thing I want you to notice... is what's on this screen — and what's deliberately set apart. Inn-telligence monitors 39 properties in the Byoo-fort market. But it doesn't treat them all the same way. Because they're not all the same. The green columns — Cuthbert House Inn, Rhett House Inn, Byoo-fort Inn — these are your DIRECT boutique competitors. Properties that offer a genuinely comparable guest experience. When Inn-telligence sets your rates? It pays close attention to these. The orange columns — you'll notice the labels say STR, not a peer — those are short-term rental properties. Airbnb listings. VRBO units. Inn-telligence shows you their rates for CONTEXT. Because knowing what Airbnb is charging is useful information. But here's the critical difference. It does NOT use those rates to set yours. An Airbnb on Bay Street charging $199 a night... is not your competition. Your guest at Anchorage 1770 gets a chef-prepared breakfast every morning. A genuine innkeeper who knows Byoo-fort — and can tell them exactly where to eat and what to see. Premium linens and toiletries. Access to the Ree-BO Social Club. And the rooftop bar. The Airbnb guest? Gets a key code. And a welcome message. These are not the same products. And they should not be priced by the same logic. In your market, Inn-telligence builds the same comp set — identifying your direct boutique peers, your hotel references, and your STR context. Wherever you are. Let me click the Waterfront tab — and show you exactly where you stand relative to Cuthbert House... right now.",

    # Step 7
    "Every other revenue management platform for boutique inns prices rooms. ONLY rooms. The restaurant is invisible to them. The bar doesn't exist. The packages, the gift shop, the private events — none of it. Inn-telligence is the ONLY platform that manages all six revenue streams a boutique inn operates. And this screen — the F&B Yield dashboard — is where we do it for the Ree-BO Social Club and the rooftop bar. Look at this table. Day of week. Average covers. Average check. Average revenue. Occupancy percentage. And this last column — RevPASH. Revenue Per Available Seat Hour. That's the food and beverage industry's equivalent of RevPAR. It tells you how efficiently you're using your dining capacity. Right now? Inn-telligence is flagging Tuesday and Wednesday in amber. Forty-four percent covers on Tuesday. Forty-six on Wednesday. Those are yield gaps. You have 48 seats available — and you're filling fewer than half of them on your slowest nights. Here's what Inn-telligence recommends for those nights. A $35 prix fixe lunch... to pull in local Byoo-fort residents who can come mid-week. A four to six pm happy hour on house wines and signature cocktails. And a Dinner and Stay package — that fills the room AND fills the restaurant at the same time. On the other end of the spectrum? Look at Saturday. 92 percent occupancy. $3,476 in revenue. Inn-telligence is recommending that on Water Festival nights... you run a prix fixe dinner at $85 per person... and apply a $25 minimum spend on the rooftop bar. The annual revenue opportunity from optimizing just the slow nights alone — not even touching the peak nights — is over $24,000. That's sitting on the table. Right now.",

    # Step 8
    "This is your Guest CRM — the relationship intelligence layer of Inn-telligence. Every guest who has stayed at Anchorage 1770 is here. With their complete history. Number of stays. Total lifetime revenue. Last visit date. How they booked. Which rooms they prefer. And the segment tags Inn-telligence has automatically assigned based on their behavior. Margaret Whitfield from Charleston. Six stays. $7,250 in lifetime revenue. Last visit April 2026. She has VIP and Local tags — because she's a high-value repeat guest who lives close enough to visit frequently. Catherine DuBose from Washington DC. Five stays. $6,420. Tagged Anniversary and VIP. Inn-telligence detected that she and her partner consistently stay around the same dates each year... which means she's likely celebrating something meaningful to them. At the top of the screen, Inn-telligence has already drafted 16 outreach campaigns. Demand fill campaigns — automatically generated for dates where occupancy is projected to be below target. It identifies which guest segments are most likely to book those specific gaps. Personalizes the timing and the offer. And queues them up for your review. For Margaret? Inn-telligence is recommending a personal reach-out... about six weeks before Water Festival. Because historical data shows past VIP guests who receive a personal invitation at that lead time... convert at about 34 percent. That's not a mass email blast. That's a targeted, timed message — to someone who has already demonstrated she loves your property. Let me click on Margaret and show you her full profile.",

    # Step 9
    "Every month, Inn-telligence produces this report. The ROI Performance Report. And I want to be specific about WHY this exists. Because it matters. Most software you buy just... does a thing. You pay for it. You use it. And at some point you're asked whether you want to renew. You kind of remember that it seemed helpful — but you can't quite put a number on it. Inn-telligence doesn't work that way. Every month, it produces documentation. EXACT numbers. The specific dates, room types, and rate decisions that generated additional revenue. The direct booking savings from guests who were captured through your website instead of an OTA. The total value delivered to your property — in dollars — compared directly to the subscription cost. This month's report for Anchorage 1770. Engine revenue contribution: $4,840. That's the documented additional revenue from rate recommendations. The difference between what you would have charged at your old rates... and what Inn-telligence recommended and you approved. Direct booking savings: $1,240. Commissions you didn't pay — because guests booked directly through your website instead of through Booking dot com or Expedia. Total value delivered: $6,080. Subscription cost: $699. Return on subscription: 8.7 times. For every dollar you spent on Inn-telligence this month... you got $8.70 back. And listed right below — every specific win. July 20th. Water Festival. Waterfront Suite. $378... became $535. $157 per night. Times 3 nights. For one room. During one event. This is not a testimonial. This is YOUR own data. From YOUR own property. Documented. And dated. Show it to your accountant. Show it to your bank. Show it to anyone who asks whether the subscription is worth it.",

    # Step 10
    "Packages are one of the most underutilized revenue opportunities at boutique inns. Not because innkeepers don't know packages work — they do. But because building them, pricing them correctly, and knowing which ones to promote and when... takes time and research that most owner-operators simply don't have. Inn-telligence handles this through the Package Intelligence module. Here's the Anniversary Package. Room. Fresh flowers from a local Byoo-fort florist. A bottle of champagne on arrival. Inn-telligence is recommending a $65 add-on above the base room rate. How did it arrive at $65? It analyzed what comparable boutique inns nationally charge for this package — 71 percent of Select Registry properties offer some version of it — and what the actual cost of the components is. The flowers. The champagne. The innkeeper's time to arrange it. The margin is healthy. And the $65 premium doesn't feel significant to a couple celebrating an anniversary. At a 22 percent conversion rate — meaning roughly 1 in 5 guests who see the Anniversary Package offer actually books it — that generates $4,095 per month in additional revenue. From ONE package. And Inn-telligence knows WHEN to promote it. Six weeks before Water Festival, when anniversary travel spikes. Around Valentine's weekend. During the period when couples tend to plan milestone celebrations. The Adventure Package. The Breakfast Upgrade. The Spa Enhancement. The Sunset Cruise. Each one has its own pricing recommendation. Its own conversion data. And its own optimal promotion timing. You don't have to guess... at any of it.",

    # Step 11
    "I want to show you something that sounds small — but matters enormously in the day-to-day reality of running an inn. Everything you've seen — the Rate Calendar, the Competitive Intelligence, the F&B yield analysis, the Guest CRM, the ROI report — ALL of it is accessible from your phone. Right now. Without downloading anything. Inn-telligence is a progressive web app. You open the link in Safari on your iPhone. You tap Add to Home Screen. And from that moment on... it sits on your home screen and opens like a native app. No App Store approval process. No waiting for an update to download. Just the full Inn-telligence dashboard. On your phone. Always current. This matters because innkeeping doesn't follow a desk schedule. You're checking in a guest — and your phone buzzes. Cuthbert House just sold out for the weekend you have open dates. Inn-telligence caught it. You pull out your phone. See the alert. Tap to approve the rate increase. And put your phone back in your pocket. Thirty seconds. You never left the conversation with your arriving guest. Or — you're at dinner. And you get a notification. Booking pace just spiked 40 percent for the next two weekends. There's a USMC graduation at Parris Island you hadn't fully accounted for. You review it. Approve it. And your rates are updated on all seven OTAs... before you've finished your appetizer. Or you're simply away — visiting family, on vacation yourself — and you KNOW your property is being managed intelligently while you're gone. Not by a person you're paying to sit at a desk. But by a system that monitors your market continuously... and makes reasoned decisions within the guardrails you've set. That's what Inn-telligence is designed for.",

    # Step 12
    "I built Inn-telligence on real Byoo-fort, South Carolina market data. Specifically calibrated for the boutique inn market on the Historic District's Bay Street waterfront. I didn't build this in a vacuum. I spent months studying this market. Analyzing what Cuthbert House Inn and Rhett House Inn were charging. Understanding how the Water Festival drives demand. Learning what a boutique inn with a restaurant and rooftop bar actually NEEDS from a pricing tool. The result? A platform that understands the boutique inn market from the inside. My background is eleven years in revenue management as a Certified Pricing Professional. I've built pricing systems for major corporations. Inn-telligence brings that same enterprise-grade thinking to properties with 5 to 50 rooms... at a price that makes sense for an independent operator. The Water Festival starts in 57 days. Every day you wait... is a day your competitors are filling up at rates YOU could be charging. Inn-telligence starts with a 14-day free trial. No credit card. Let's talk.",
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

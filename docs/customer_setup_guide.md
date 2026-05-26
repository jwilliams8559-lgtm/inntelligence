# INNtelligence Setup Guide — Getting Started

*Boutique Hospitality Intelligence · by The Gracious Collection*

Welcome to INNtelligence. This guide walks you through everything from your first
login to approving your first rate recommendations. Most inns are fully live within
a single 90-minute onboarding call.

---

## 1. Before Your Onboarding Call

Have these three things ready so your call moves quickly:

1. **PMS login credentials**
   - **ResNexus:** your API key (Settings → Integrations → API in ResNexus).
   - **Cloudbeds:** your Cloudbeds login (you'll authorize via a one-click OAuth button — no key to copy).
   - Not sure / no PMS yet? That's fine — we'll run on realistic demo data until you connect.

2. **A list of your main competitors** — the 4–8 properties guests compare you to.
   Don't overthink it; INNtelligence will also auto-discover nearby properties.

3. **Your base rates for each room type** — your typical rack rate, plus the lowest
   rate you'd ever accept (floor) and the highest you'd charge at peak (ceiling).

> Tip: jot these on paper before the call. It turns a 90-minute call into a 60-minute one.

---

## 2. Step-by-Step: Connecting Your PMS

Connecting your PMS lets INNtelligence import your rooms, read live availability, and
publish approved rates automatically.

### ResNexus
1. In your dashboard, go to **Onboarding → Step 2 (Connect PMS)** and choose **ResNexus**.
2. In ResNexus, open **Settings → Integrations → API** and copy your API key.
3. Paste the key into the **ResNexus API Key** field.
4. Click **Test Connection**. You'll see *"Connected — syncing 2 years of history."*
   - *Screenshot description:* a green confirmation bar appears showing your property
     name and the number of room types detected.
5. History sync runs in the background (usually 5–15 minutes).

### Cloudbeds
1. Choose **Cloudbeds** in Step 2.
2. Click **Connect with Cloudbeds (OAuth)**.
   - *OAuth flow description:* a Cloudbeds window opens asking you to log in and authorize
     INNtelligence. Approve the requested read/write scopes, and you'll be returned to the
     wizard automatically — no key copying required.
3. On return you'll see the same *"Connected — syncing 2 years of history"* confirmation.

### Connect later
Choose **"I'll connect later."** INNtelligence runs on realistic demo data so you can
explore every screen. Connect any time from **Settings → Integrations**.

---

## 3. Step-by-Step: Confirming Your Competitors

INNtelligence searches for lodging within **25 miles** of your address and groups results
into tiers:

- **Tier 1 — Direct Boutique Competitors:** the properties that most affect your pricing.
- **Upscale Hotels / Market Reference:** context, lower weight.
- **Luxury Reference:** the top of your market (e.g., a nearby resort) — shown but excluded
  from your comp-set average.

**How discovery works:** we query mapping data for nearby lodging, then rank by similarity
(room count, style, rating). Pre-checked properties are our best Tier-1 guesses.

**To add a property we missed:** type its name in the **"Add a property we missed"** box and
press **Add**. **To remove one:** uncheck it. When the set looks right, click
**Confirm my competitor set**.

> Always sanity-check the list — mapping data occasionally returns a private residence or a
> closed business. Confirm each is an active lodging property.

---

## 4. Step-by-Step: Configuring Your Rooms

If your PMS is connected, your room types are imported automatically. Otherwise you'll start
from sensible defaults. For each room type, confirm:

- **Name** — how guests see the room (e.g., "Waterfront King"), not an internal room number.
- **Bathroom type** — INNtelligence auto-detects this (en-suite, soaking tub, walk-in shower…)
  because it affects your premium. Correct it if needed.
- **Base rate** — your typical rack rate.
- **Min rate (floor)** — the absolute lowest the engine may ever recommend. INNtelligence will
  *never* go below this.
- **Max rate (ceiling)** — your peak ceiling. The engine never exceeds this regardless of
  how many demand signals stack (rule of thumb: rack_high × 1.40).

Click **"These look right"** to continue.

---

## 5. Step-by-Step: Setting Up Autopilot

Autopilot publishes approved rates to your channels automatically, within your guardrails.

For each room type choose:
- **Manual Only** — INNtelligence recommends; you approve every rate yourself.
- **Autopilot Enabled** — approved-style rates publish automatically, with a confidence setting:
  - **Conservative** — only high-confidence moves, smaller adjustments.
  - **Balanced** *(recommended to start)* — the standard model behavior.
  - **Aggressive** — larger moves, captures more upside on peak dates.

**Recommended starting settings:** put your standard rooms on **Balanced autopilot** and keep
your top suites on **Manual** for the first few weeks until you trust the recommendations.

Click **Start INNtelligence** to finish.

---

## 6. Your First Rate Recommendations

Open the **Rate Calendar**. Each cell is one room, one night:

- **Rate (gold)** — the recommended nightly rate.
- **Status color** — green = premium (above rack mid), gray = at rack, rose = strategic discount.
- **Weekend tint / 🎉 event dot** — Fri/Sat shading and an icon when a demand event is active.
- **Confidence** — High / Medium / Low, shown in the detail panel.

Click any cell to open the **detail panel**: the recommended rate, the reasoning
(seasonal index, event multiplier, lead time, competitor average), comparable competitor
rates, confidence, and **Accept** / **Override** buttons.

---

## 7. Approving and Publishing Rates

- **Single approval:** click a cell → **Accept** to lock that night's rate.
- **Override:** type your own number and click **Override**.
- **Approve all** (where available): accept a whole category/date range at once.

**What happens next:** approved rates publish to your connected channels (via your PMS /
channel manager). On Autopilot, eligible rates publish automatically within your guardrails;
you'll get a weekly summary of what changed.

---

## 8. Troubleshooting Common Issues

**PMS sync failed**
- Re-check your API key (ResNexus) or re-authorize (Cloudbeds) in **Settings → Integrations**.
- Confirm your PMS user has API/integration permissions.
- Still stuck? Email **hello@inntelligence.app** — we can see sync logs on our side.

**Rates not publishing**
- Confirm the room is set to **Autopilot Enabled** (Manual rooms wait for your approval).
- Check that your PMS/channel manager connection is still authorized.
- Verify the recommended rate isn't being clamped by your min/max guardrails.

**Login issues**
- Use **Forgot password** on the sign-in screen to get a reset link.
- Accounts are created individually by our team — there is no public signup. If you don't
  have an account yet, click **Request access** or email **hello@inntelligence.app**.

---

*Questions any time: **hello@inntelligence.app** — INNtelligence by The Gracious Collection.*

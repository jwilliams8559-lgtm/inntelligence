export type DemoScreen =
  | 'calendar' | 'demand' | 'events' | 'competitive' | 'reputation'
  | 'fnb' | 'crm' | 'behavior' | 'packages' | 'performance' | 'historical'

export interface ActionStep {
  /** CSS selector for the element the cursor should animate to and click. */
  targetSelector: string
  /** Milliseconds after narration starts to begin the cursor animation. */
  delayMs: number
}

export interface DemoStep {
  id: number
  title: string
  screen: DemoScreen
  /** CSS selector for the element to spotlight on that screen. Falls
   * back to a screen-wide darkening when the selector matches nothing. */
  spotlightSelector?: string
  narration: string
  /** All steps auto-advance when narration audio ends. The animated
   * cursor (if `action` is defined) drives a click partway through. */
  autoAdvance: boolean
  /** When set, the AnimatedCursor moves from screen center to the
   * target element and programmatically clicks it. Narration continues
   * uninterrupted; the demo is fully self-driven. */
  action?: ActionStep
}

/**
 * Narration text below mirrors scripts/generate_demo_audio.py NARRATIONS
 * exactly. Audio files at /demo-audio/step-NN.mp3 are generated from that
 * Python list; the React captions and Web-Speech fallback both read from
 * here. Keep the two in sync — when you edit narration text, rerun:
 *
 *     rm dashboard/public/demo-audio/step-*.mp3
 *     python3 scripts/generate_demo_audio.py
 */
export const DEMO_STEPS: DemoStep[] = [
  {
    id: 1, title: 'Water Festival Alert', screen: 'calendar',
    spotlightSelector: '[data-tour="festival-alert"], [data-demo="festival-alert"]',
    narration:
      "Welcome to INNtelligence. What you're about to see is a 19-room historic boutique inn on Bay Street in Beaufort, South Carolina — managing its pricing, its restaurant, its rooftop bar, its guest relationships, and its revenue... all from one platform. The moment you open INNtelligence, before you look at a single rate — you see this. A gold alert banner across the top of the screen. 'Beaufort Water Festival. July 17th through July 26th. Approaching. No premium applied yet.' That's INNtelligence telling you something important. The biggest tourism event in the Lowcountry is 57 days away. Your rooms aren't priced for it yet. And your competitors? They're already moving. This is the difference between a tool that REACTS... and a tool that ANTICIPATES. INNtelligence monitors your local events calendar continuously — major festivals, USMC graduations at Parris Island, art walks, food festivals, everything that brings visitors to your town. And I want to be clear about something. INNtelligence combines machine intelligence with human pricing expertise. The AI monitors your market 24 hours a day, 7 days a week — detecting demand shifts, analyzing competitors, generating recommendations. But every recommendation is reviewed through the lens of real hospitality pricing experience. You're not relying on an algorithm alone. You're getting the judgment of a seasoned pricing professional — delivered at the speed of software. Let's see what it's recommending for the Water Festival.",
    autoAdvance: true,
  },
  {
    id: 2, title: 'The 90-Day Rate Calendar', screen: 'calendar',
    spotlightSelector: '[data-tour="rate-cell-festival"], [data-demo="rate-grid"], table',
    narration:
      "This is the Rate Calendar — the command center of INNtelligence. A 90-day forward view of all 19 rooms at Bay Street Inn. Waterfront Suites across the top — premier front-of-house rooms with direct river views and porch access. Water View Rooms below. Garden Rooms. Classic Rooms. Every room type... every day... for the next three months. The gold cells stretching across July 17th through the 26th — those are Water Festival dates. INNtelligence colors them automatically. You never miss your peak revenue period. Each cell shows three things. The recommended rate — large and clear. The base rate below it in gray — so you always know how far the engine has moved from your starting point. And a status dot — yellow means pending your approval... green means approved and live on all SEVEN of your OTA channels simultaneously. Right now — 363 pending recommendations. Three hundred and sixty-three individual rate decisions. Already made. Waiting for your review. Let me click July 20th — the Saturday at the absolute peak of Water Festival — and show you exactly how INNtelligence arrived at its recommendation for the Waterfront Suite.",
    autoAdvance: true,
    action: {
      // Real DOM: festival rate cells are <td class="… bg-gold/8 cursor-pointer …">.
      // Tailwind's slash escape means we match by attribute. Falls back to the
      // first cursor-pointer td under any header tagged data-tour='rate-cell-festival'.
      targetSelector: "td[class*='bg-gold'].cursor-pointer, [data-festival='true'], .festival-cell, td.gold-cell",
      delayMs: 4000,
    },
  },
  {
    id: 3, title: 'Plain-English Reasoning', screen: 'calendar',
    spotlightSelector: '[data-demo="rate-grid"], table',
    narration:
      "This — right here — is what makes INNtelligence different from every other pricing tool on the market. For EVERY recommendation — every single one — INNtelligence shows you exactly why it's recommending that number. Plain English. No algorithm jargon. No black box. Just a clear explanation you could read to a skeptical business partner and have them immediately understand. For the Waterfront Suite on July 20th — demand score: 92 out of 100. PEAK. The highest category. Here's what's driving it. Booking pace is running 23 percent ahead of last year — guests are booking Water Festival earlier than ever. The festival historically drives 94 percent occupancy across Beaufort's boutique properties. And your two closest competitors — Cuthbert House Inn and Rhett House Inn — are already SOLD OUT for that weekend. Completely full. At $560 and $510 respectively. And then there's this. Because Bay Street Inn provides chef-prepared breakfast every morning... The Parlor restaurant steps away... The Rooftop at Bay Street with panoramic river views... and the personal touch of innkeeper service — INNtelligence calculates that you're offering approximately $136 more in real value per night than a comparable Airbnb on Bay Street. That's not a guess. It's a calculation based on what those individual amenities actually cost when purchased separately. The recommendation: $500 per night. Waterfront Suite. Three-night minimum stay. Let me approve it — and watch what happens.",
    autoAdvance: true,
    action: {
      // Drawer Approve button — single rate approval. Text-based selectors aren't
      // standard CSS, so we rely on button position inside the drawer pane.
      targetSelector: "[data-demo='approve'], .approve-btn, button.approve, aside button[class*='bg-gold']:not([class*='Approve All'])",
      delayMs: 6000,
    },
  },
  {
    id: 4, title: 'One-Click Approval to 7 OTAs', screen: 'calendar',
    spotlightSelector: '[data-demo="approve-all"], button[class*="approve"]',
    narration:
      "I just clicked Approve. One click. Less than a second. And here's what happened in the background while you watched me click. That $500 rate for the Waterfront Suite on July 20th is now live — SIMULTANEOUSLY — on Booking dot com, Expedia, Airbnb, VRBO, Hotels dot com, Trip dot com, and Agoda. SEVEN channels. Updated at exactly the same time. In 2.3 seconds. Think about what that used to look like. Logging into each platform separately. Finding the right dates. Entering the rate. Saving it. Moving to the next platform. Doing it again. Seven times. For one room. On one date. With 19 rooms and 90 days to manage... that math becomes impossible very quickly. Innkeepers spend an average of 12 to 18 hours per week on manual rate management before INNtelligence. Every one of those hours is time you could have spent with a guest... developing a new package... building relationships in your community... or simply having a day off. After INNtelligence — most of our customers spend less than 30 minutes a week reviewing and approving recommendations. Everything else runs automatically.",
    autoAdvance: true,
    action: {
      // Real DOM: "Approve All ({pendingCount})" button — white bg, gold text, no data attr.
      // Match by aria/text via attribute selectors that fall through to existing markers.
      targetSelector: "[data-demo='approve-all'], .approve-all-btn, button[class*='bg-white'][class*='text-gold']",
      delayMs: 3000,
    },
  },
  {
    id: 5, title: 'Approve All + Autopilot', screen: 'calendar',
    spotlightSelector: '[data-demo="approve-all"], button[class*="approve"]',
    narration:
      "See this button — top right corner. 'Approve All. 363.' One click. All 363 pending recommendations. Across all 19 rooms. Across 90 days forward. Published to all seven OTAs. Simultaneously. Now you might be wondering — is that SAFE? What if I disagree with one? What if the engine gets something wrong? That's exactly why INNtelligence gives you complete control at every level. Approve everything at once for speed. Filter by room type and approve just the Waterfront Suites. Review each recommendation individually — read the reasoning — approve or override on a case by case basis. Type in whatever number you want. The engine accepts it. No argument. No friction. You are ALWAYS in control. INNtelligence never publishes anything you haven't approved. And for innkeepers who want even less friction — there's Autopilot. Set your guardrails once. Maximum rate change per day. Minimum confidence threshold. Operating hours. INNtelligence runs within those guardrails automatically... every morning... before you wake up. Most of our customers run Autopilot on standard rooms and manual review on their premier suites. Best of both worlds. Let me show you the competitive intelligence behind all of this.",
    autoAdvance: true,
  },
  {
    id: 6, title: 'Competitive Intelligence', screen: 'competitive',
    spotlightSelector: '[data-demo="comp-table"], table',
    narration:
      "This is the Competitive Intelligence center. INNtelligence monitors 39 properties in the Beaufort market. But it doesn't treat them all the same — because they're NOT all the same. The green columns — Cuthbert House Inn, Rhett House Inn, Anchorage 1770 Inn — these are your direct boutique competitors. Properties offering a genuinely comparable guest experience. When INNtelligence sets your rates, it pays close attention to these. The orange columns — labeled 'STR, not a peer' — those are short-term rental properties. Airbnb listings. VRBO units. INNtelligence shows them for context... but here's the critical difference — it does NOT use those rates to set yours. An Airbnb on Bay Street at $199 a night is not your competition. Your guest at Bay Street Inn gets chef-prepared breakfast every morning... The Parlor steps away for dinner... The Rooftop for cocktails with river views... a genuine innkeeper who knows Beaufort and can tell them exactly where to go and what to see. The Airbnb guest gets a key code and a welcome message. These are NOT the same products. They should not be priced by the same logic. And one more thing worth knowing — when you subscribe to INNtelligence, your market is protected. No competitor within a five-mile radius can access the same pricing intelligence. Your edge stays yours.",
    autoAdvance: true,
    action: {
      // Waterfront room-type filter pill on Competitive Intel.
      // Buttons are rendered via .map() with no data attr; we target by sibling
      // selectors in fallback. The capture script tags this via JS for the demo
      // by adding data-tab="waterfront" before clicking.
      targetSelector: "button[data-tab='waterfront'], .waterfront-tab, button[data-room='Waterfront']",
      delayMs: 3000,
    },
  },
  {
    id: 7, title: 'F&B Yield Management', screen: 'fnb',
    spotlightSelector: '[data-demo="dow-table"], table',
    narration:
      "Every other revenue management platform for boutique inns prices rooms. ONLY rooms. The restaurant is invisible to them. The bar doesn't exist. The packages, the gift shop, the private events — none of it. INNtelligence is the ONLY platform that manages all six revenue streams a boutique inn operates. This screen — the F&B Yield dashboard — is where we do it for The Parlor at Bay Street Inn and The Rooftop. Look at this table. Day of week. Average covers. Average check. Average revenue. Occupancy percentage. And RevPASH — Revenue Per Available Seat Hour. The food and beverage industry's equivalent of RevPAR. Tuesday and Wednesday — flagged in amber. Forty-four percent covers on Tuesday. Forty-six on Wednesday. Yield gaps. You have 100 seats available and you're filling fewer than half of them on your slowest nights. INNtelligence recommends: a $38 prix fixe lunch to attract local Beaufort residents mid-week. A four to six pm happy hour on The Rooftop. And a Dinner and Stay package — combined room and dinner — that fills the room AND fills The Parlor simultaneously. On warm Beaufort evenings, The Parlor extends to the front porches overlooking Bay Street — 25 additional seats under the stars. INNtelligence factors this seasonal capacity into its recommendations. Saturday — 92 percent occupancy — $3,476 in revenue. On Water Festival nights, INNtelligence recommends a prix fixe dinner at $85 per person and a $25 minimum spend on The Rooftop. The annual revenue opportunity from optimizing just the slow nights alone — not even touching peak nights — is over $24,000. That's sitting on the table right now.",
    autoAdvance: true,
  },
  {
    id: 8, title: 'Guest CRM', screen: 'crm',
    spotlightSelector: '[data-demo="guest-list"], table, .guest-card',
    narration:
      "This is your Guest CRM — the relationship intelligence layer of INNtelligence. Every guest who has stayed at Bay Street Inn is here. Complete history. Number of stays. Total lifetime revenue. Last visit date. How they booked. Which rooms they prefer. And segment tags INNtelligence has automatically assigned based on their behavior. Margaret Whitfield from Charleston. Six stays. $7,250 in lifetime revenue. Last visit April 2026. VIP and Local — a high-value repeat guest who lives close enough to visit frequently. Catherine DuBose from Washington DC. Five stays. $6,420. Tagged Anniversary and VIP — INNtelligence detected that she and her partner stay around the same dates each year. She's celebrating something meaningful. Every time. At the top of the screen — 16 outreach campaigns. Already drafted. Automatically generated for dates where occupancy is projected below target. The right guests... the right timing... the right offer. Queued for your review. One click sends them. For Margaret — a personal reach-out six weeks before Water Festival. Because historical data shows past VIP guests who receive a personal invitation at that lead time convert at about 34 percent. Not a mass email blast. A targeted, timed message to someone who has already demonstrated... she loves your property.",
    autoAdvance: true,
    action: {
      // First guest row in CRM table — uses tbody tr:first-child as primary,
      // since rows are rendered via .map() with no data attr.
      targetSelector: ".guest-row:first-child, .guest-card:first-child, tbody tr:first-child",
      delayMs: 4000,
    },
  },
  {
    id: 9, title: 'Documented ROI', screen: 'performance',
    spotlightSelector: '[data-tour="roi-hero"], [data-demo="roi"]',
    narration:
      "Every month, INNtelligence produces this report. The ROI Performance Report. And I want to be specific about why — because it matters. Most software you buy just... does a thing. You pay for it. You use it. At renewal time you kind of remember it seemed helpful but can't quite put a number on it. INNtelligence doesn't work that way. Every month — documentation. Exact numbers. Specific dates, room types, and rate decisions that generated additional revenue. Direct booking savings from guests captured through your website instead of an OTA. Total value delivered — in dollars — compared directly to your subscription cost. This month's report for Bay Street Inn: Engine revenue contribution — $4,840. The documented additional revenue from rate recommendations. The difference between what you would have charged... and what INNtelligence recommended and you approved. Direct booking savings — $1,240. Commissions you didn't pay because guests booked directly instead of through Booking dot com or Expedia. Total value delivered — $6,080. Subscription cost — $699. Return on subscription — 8.7 TIMES. For every dollar you spent on INNtelligence this month — you got $8.70 back. And every specific win listed right below. July 20th. Water Festival. Waterfront Suite. $378 became $535. $157 per night. Three nights. One room. One event. This is not a testimonial. This is YOUR data. From YOUR property. Documented and dated. Show it to your accountant. Show it to your bank. Show it to anyone who questions whether it's worth it.",
    autoAdvance: true,
  },
  {
    id: 10, title: 'Package Intelligence', screen: 'packages',
    spotlightSelector: '[data-demo="package-card"], .package-card',
    narration:
      "Packages are one of the most underutilized revenue opportunities at boutique inns. Not because innkeepers don't know packages work — they DO. But because building them, pricing them correctly, and knowing WHEN to promote which ones takes time most owner-operators simply don't have. INNtelligence handles this through the Package Intelligence module. The Anniversary Package — room, fresh flowers from a local Beaufort florist, a bottle of champagne on arrival. INNtelligence recommends a $65 add-on above base room rate. How did it arrive at $65? It analyzed what comparable boutique inns nationally charge for this package — 71 percent of Select Registry properties offer some version of it — and what the actual components cost. The flowers. The champagne. The innkeeper's time to arrange it. The margin is healthy. And $65 feels like nothing to a couple celebrating an anniversary. At 22 percent conversion — roughly one in five guests who see the offer books it — that's $4,095 per month in additional revenue. From ONE package. And INNtelligence knows exactly WHEN to promote it. Six weeks before Water Festival when anniversary travel spikes. Around Valentine's weekend. During the window when couples plan milestone celebrations. The Adventure Package, the Spa Enhancement, the Sunset Cruise, the Porch Breakfast for Two — each with its own pricing recommendation, its own conversion data, its own optimal promotion timing. You don't have to guess at any of it.",
    autoAdvance: true,
  },
  {
    id: 11, title: 'Works on Your Phone', screen: 'historical',
    spotlightSelector: '[data-demo="trend-chart"], svg.recharts-surface',
    narration:
      "Everything you've just seen — the Rate Calendar... the Competitive Intelligence... F&B yield analysis... Guest CRM... ROI report — all of it is on your phone. Right now. Without downloading anything. INNtelligence is a progressive web app. Open the link in Safari on your iPhone. Tap 'Add to Home Screen.' From that moment — it sits on your home screen and opens like a native app. No App Store. No download. No update waiting. This matters because innkeeping doesn't follow a desk schedule. You're checking in a guest and your phone buzzes — Cuthbert House just sold out for the weekend you have open dates. INNtelligence caught it. You pull out your phone. See the alert. Tap to approve the rate increase. Put your phone back in your pocket. Thirty seconds. You never left the conversation. You're at dinner and a notification arrives — booking pace just spiked 40 percent for the next two weekends. A USMC graduation at Parris Island you hadn't fully accounted for. You review it. Approve it. Your rates are updated on all seven OTAs before you finish your appetizer. Or you're simply away — on vacation yourself — and you know Bay Street Inn is being managed intelligently while you're gone. Not by someone you're paying to sit at a desk... but by a system that monitors your market continuously and makes reasoned decisions within the guardrails you've set. That's what INNtelligence is designed for.",
    autoAdvance: true,
  },
  {
    id: 12, title: 'Why I Built INNtelligence', screen: 'calendar',
    spotlightSelector: '[data-tour="festival-alert"], [data-demo="festival-alert"]',
    narration:
      "Let me tell you who built INNtelligence and why — because I think it matters. I'm Jim Williams. I bring over 20 years of professional pricing experience to this platform — including several years focused specifically on hospitality and independent inn markets. I hold the Certified Pricing Professional designation — the highest credential in the pricing field. I built INNtelligence on real Beaufort, South Carolina market data — specifically calibrated for the boutique inn market on the historic district's Bay Street waterfront. I didn't build this in a vacuum. I spent years studying this market. Analyzing what Cuthbert House Inn and Rhett House Inn charge. Understanding how the Water Festival drives demand. Learning what a boutique inn with a restaurant, a rooftop bar, and a gift shop actually NEEDS from a pricing tool. The result is a platform that understands the boutique inn market from the inside. And I want to be clear about something. INNtelligence is not just software running unsupervised. It's a combination of AI and human pricing expertise — continuously monitored, continuously refined. The machine works at speed and scale. The human judgment ensures it stays on target. For properties wanting even more — The Gracious Collection offers boutique hospitality consulting engagements. Hands-on revenue strategy, market positioning, and pricing architecture. Contact us to learn more. INNtelligence was initially built and validated in the Lowcountry — one of the most competitive boutique inn markets in the American South. Since then we've tested and verified its methodology across diverse markets throughout the United States and Europe — from the Hudson Valley to the Cotswolds, from the Texas Hill Country to the Scottish Highlands. The analysis you're seeing today is calibrated for Beaufort, South Carolina. But the same engine — the same intelligence — works for YOUR market. Wherever you are. But the platform itself — INNtelligence — starts at $399 a month. And it pays for itself many times over. The Water Festival starts in 57 days. Every day you wait is a day your competitors are filling up at rates you could be charging. 14-day free trial. No credit card. And when you subscribe — your market is protected. No competitor within five miles can access the same intelligence. Your edge. Yours alone. Let's talk.",
    autoAdvance: true,
  },
]

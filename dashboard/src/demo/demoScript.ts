export type DemoScreen =
  | 'calendar' | 'demand' | 'events' | 'competitive' | 'reputation'
  | 'fnb' | 'crm' | 'behavior' | 'packages' | 'performance' | 'historical'

export interface InteractiveStep {
  /** Pulsing label rendered near the spotlight to direct the user. */
  instruction:    string
  /** CSS selector for the element the user must click to advance. */
  targetSelector: string
}

export interface DemoStep {
  id: number
  title: string
  screen: DemoScreen
  /** CSS selector for the element to spotlight on that screen. Falls
   * back to a screen-wide darkening when the selector matches nothing. */
  spotlightSelector?: string
  narration: string
  /** When true, advance fires automatically when narration audio ends.
   * Set to false on interactive steps — DemoMode waits for a click on
   * `interactive.targetSelector` (or the manual Next button). */
  autoAdvance: boolean
  interactive?: InteractiveStep
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
      "Let me show you what INNtelligence does for Anchorage 1770 Inn — a 14-room historic boutique property on Bay Street in Beaufort, South Carolina. The moment you open INNtelligence, before you even look at the rate calendar, before you check your competitors — you see this. An alert. A gold banner across the top of the screen. Beaufort Water Festival. July 17th through July 26th. Approaching. No premium applied yet. That's INNtelligence telling you something important. The single biggest tourism event in the Lowcountry is 57 days away. Your rooms haven't been priced for it yet. And your competitors? They're already moving. This is the difference between a tool that reacts and a tool that anticipates. INNtelligence monitors the Beaufort events calendar continuously — not just major festivals, but USMC graduations at Parris Island, the Wine and Food Festival, First Friday Art Walks, everything that brings visitors to town. It detected the Water Festival automatically, calculated its historical impact on room demand, and flagged it for your attention. You didn't have to set a reminder. You didn't have to check a calendar. It just told you. Let's click Review and see what it's recommending.",
    autoAdvance: true,
  },
  {
    id: 2, title: 'The 90-Day Rate Calendar', screen: 'calendar',
    spotlightSelector: '[data-tour="rate-cell-festival"], [data-demo="rate-grid"], table',
    narration:
      "This is the Rate Calendar — the command center of INNtelligence. What you're looking at is a 90-day forward view of every room at Anchorage 1770, with a rate recommendation for every single date. The Waterfront Suites across the top. Water View Suites below. Garden View Rooms. The Private Cottage. Every room type, every day, for the next three months. The gold cells — you can see them stretching across July 17th through the 26th — those are Water Festival dates. INNtelligence colors them automatically so you never miss your peak revenue period. Each cell shows you three things. The recommended rate in large text. The base rate below it in gray — so you always know how far the engine has moved from your starting point. And a dot indicating the status: yellow means pending, waiting for your approval; green means approved and live on all seven of your OTA channels simultaneously. Right now there are 363 pending recommendations sitting in this calendar. Three hundred and sixty-three individual rate decisions that INNtelligence has already made, waiting for a human to review and approve them. I want you to click on July 20th — the Saturday at the peak of Water Festival — and see exactly how INNtelligence arrived at its recommendation for the Waterfront Suite.",
    autoAdvance: false,
    interactive: {
      instruction:    "Click July 20th — the Water Festival peak night",
      targetSelector: '[data-tour="rate-cell-festival"], [data-festival="true"], .festival-cell, td.gold-cell',
    },
  },
  {
    id: 3, title: 'Plain-English Reasoning', screen: 'calendar',
    spotlightSelector: '[data-demo="rate-grid"], table',
    narration:
      "This is the feature that makes INNtelligence genuinely different from every other pricing tool on the market. And I want you to pay close attention to it, because it's the thing our customers talk about most. For every single rate recommendation — every one — INNtelligence shows you exactly why it's recommending that number. In plain English. No algorithm jargon. No unexplained outputs from a black box. Just a clear, readable explanation you could read out loud to a skeptical spouse or business partner and have them immediately understand. For the Waterfront Suite on July 20th, the demand score is 92 out of 100. That's Peak. The highest category. Here's what's driving that score. Booking pace this week is running 23 percent ahead of the same period last year — guests are booking the Water Festival earlier than they did in 2025. The Water Festival historically drives 94 percent occupancy across Beaufort's boutique properties. And your two closest direct competitors — Cuthbert House Inn and Rhett House Inn — are both already sold out for that weekend. Completely full. At $560 and $510 respectively. And then there's this: because Anchorage 1770 provides chef-prepared breakfast every morning, the Ribaut Social Club restaurant on the premises, a rooftop bar, and the personal touch of innkeeper service — INNtelligence recognizes that you're offering approximately $136 more in real value per night than a comparable Airbnb on Bay Street. That's not a guess. It's a calculation based on what those individual amenities cost when purchased separately. The recommendation: $500 per night for the Waterfront Suite. Three-night minimum stay. Go ahead and click Approve — let's see what happens.",
    autoAdvance: false,
    interactive: {
      instruction:    "Click Approve to publish this rate live",
      targetSelector: '.approve-btn, [data-demo="approve"], button.approve, button[class*="approve"]:not([class*="approve-all"])',
    },
  },
  {
    id: 4, title: 'One-Click Approval to 7 OTAs', screen: 'calendar',
    spotlightSelector: '[data-demo="approve-all"], button[class*="approve"]',
    narration:
      "I just clicked Approve. That's it. One click on a button that took less than a second to press. And here's what just happened in the background while you watched me click. That $500 rate for the Waterfront Suite on July 20th is now live — simultaneously, right now — on Booking dot com, Expedia, Airbnb, VRBO, Hotels dot com, Trip dot com, and Agoda. Seven channels. Updated at exactly the same time. In 2.3 seconds. Think about what that used to look like. Logging into each platform separately. Finding the right dates. Entering the rate. Saving it. Moving to the next platform. Doing it again. Seven times. For one room. On one date. And if you have 14 rooms and 90 days to manage, that math becomes overwhelming very quickly. Innkeepers spend an average of 12 to 18 hours per week on manual rate management before they use INNtelligence. Every one of those hours is time you could have spent with a guest, developing a new package, working on the restaurant, or simply having a day off. After INNtelligence, most of our customers spend less than 30 minutes per week reviewing and approving recommendations. Everything else runs automatically. Now try clicking Approve All — let's publish everything at once.",
    autoAdvance: false,
    interactive: {
      instruction:    "Click 'Approve All' to publish all 363 rates",
      targetSelector: '.approve-all-btn, [data-demo="approve-all"], button[class*="approve-all"]',
    },
  },
  {
    id: 5, title: 'Approve All + Autopilot', screen: 'calendar',
    spotlightSelector: '[data-demo="approve-all"], button[class*="approve"]',
    narration:
      "You see this button in the top right corner — Approve All, 363. One click on that button publishes all 363 pending rate recommendations across all 14 room types, for the next 90 days, to all seven OTAs. Simultaneously. Now, you might be wondering: is that safe? What if I disagree with one of them? What if the engine makes a recommendation I don't like? That's exactly why INNtelligence gives you complete control at every level. You can approve all at once for speed. You can filter by room type and approve just the Waterfront Suites. You can review each recommendation individually, read the reasoning, and approve or override on a case-by-case basis. You can override any rate — type in whatever number you want — and the engine accepts it without complaint. You're always in control. INNtelligence never publishes anything you haven't approved. And for innkeepers who want even less friction, there's Autopilot mode. In Autopilot, you set the guardrails — maximum rate change per day, minimum confidence threshold, operating hours — and INNtelligence runs within those guardrails automatically. It publishes rates every morning, responds to real-time changes in competitor availability, adjusts for last-minute demand surges. Most of our customers run Autopilot on their standard room types and manual review on their premium suites. Best of both worlds. Let me take you to the Competitive Intelligence center.",
    autoAdvance: true,
  },
  {
    id: 6, title: 'Competitive Intelligence', screen: 'competitive',
    spotlightSelector: '[data-demo="comp-table"], table',
    narration:
      "This is the Competitive Intelligence center. And the first thing I want you to notice is what's on this screen — and what's deliberately set apart. INNtelligence monitors 39 properties in the Beaufort market. But it doesn't treat them all the same way, because they're not all the same. The green columns — Cuthbert House Inn, Rhett House Inn, Beaufort Inn — these are your direct boutique competitors. Properties that offer a genuinely comparable guest experience. When INNtelligence sets your rates, it pays close attention to these. The orange columns — you'll notice the labels say STR, not a peer — those are short-term rental properties. Airbnb listings, VRBO units. INNtelligence shows you their rates for context, because knowing what Airbnb is charging is useful information. But here's the critical difference: it does not use those rates to set yours. An Airbnb on Bay Street charging $199 a night is not your competition. Your guest at Anchorage 1770 gets a chef-prepared breakfast every morning, a genuine innkeeper who knows Beaufort and can tell them exactly where to eat and what to see, premium linens and toiletries, access to the Ribaut Social Club, and the rooftop bar. The Airbnb guest gets a key code and a welcome message. These are not the same products, and they should not be priced by the same logic. Click the Waterfront tab and see exactly where you stand relative to Cuthbert House right now.",
    autoAdvance: false,
    interactive: {
      instruction:    "Click the Waterfront tab to see your comp position",
      targetSelector: 'button[data-room="Waterfront"], .room-tab.waterfront, button[class*="waterfront"], [data-room-category="waterfront"]',
    },
  },
  {
    id: 7, title: 'F&B Yield Management', screen: 'fnb',
    spotlightSelector: '[data-demo="dow-table"], table',
    narration:
      "Every other revenue management platform for boutique inns prices rooms. Only rooms. The restaurant is invisible to them. The bar doesn't exist. The packages, the gift shop, the private events — none of it. INNtelligence is the only platform that manages all six revenue streams a boutique inn operates. And this screen — the F&B Yield dashboard — is where we do it for the Ribaut Social Club and the rooftop bar. Look at this table. Day of week. Average covers. Average check. Average revenue. Occupancy percentage. And this last column — RevPASH. Revenue Per Available Seat Hour. That's the food and beverage industry's equivalent of RevPAR. It tells you how efficiently you're using your dining capacity. Right now, INNtelligence is flagging Tuesday and Wednesday in amber. Forty-four percent covers on Tuesday. Forty-six on Wednesday. Those are yield gaps. You have 48 seats available and you're filling fewer than half of them on your slowest nights. Here's what INNtelligence recommends for those nights: a $35 prix fixe lunch to pull in local Beaufort residents who can come mid-week. A four to six pm happy hour on house wines and signature cocktails. And a Dinner and Stay package that fills the room and fills the restaurant at the same time. On the other end of the spectrum, look at Saturday. 92 percent occupancy. $3,476 in revenue. INNtelligence is recommending that on Water Festival nights, you run a prix fixe dinner at $85 per person and apply a $25 minimum spend on the rooftop bar. The annual revenue opportunity from optimizing just the slow nights alone — not even touching the peak nights — is over $24,000. That's sitting on the table right now.",
    autoAdvance: true,
  },
  {
    id: 8, title: 'Guest CRM', screen: 'crm',
    spotlightSelector: '[data-demo="guest-list"], table, .guest-card',
    narration:
      "This is your Guest CRM — the relationship intelligence layer of INNtelligence. Every guest who has stayed at Anchorage 1770 is here, with their complete history: number of stays, total lifetime revenue, last visit date, how they booked, which rooms they prefer, and the segment tags INNtelligence has automatically assigned based on their behavior. Margaret Whitfield from Charleston. Six stays. $7,250 in lifetime revenue. Last visit April 2026. She has VIP and Local tags, because she's a high-value repeat guest who lives close enough to visit frequently. Catherine DuBose from Washington DC. Five stays. $6,420. Tagged Anniversary and VIP — INNtelligence detected that she and her partner consistently stay around the same dates each year, which means she's likely celebrating something meaningful to them. At the top of the screen, INNtelligence has already drafted 16 outreach campaigns — demand fill campaigns automatically generated for dates where occupancy is projected to be below target. It identifies which guest segments are most likely to book those specific gaps, personalizes the timing and the offer, and queues them up for your review. For Margaret, INNtelligence is recommending a personal reach-out about six weeks before Water Festival, because historical data shows past VIP guests who receive a personal invitation at that lead time convert at about 34 percent. That's not a mass email blast. It's a targeted, timed message to someone who has already demonstrated she loves your property. Click on Margaret and see her full profile.",
    autoAdvance: false,
    interactive: {
      instruction:    "Click Margaret Whitfield to see her full profile",
      targetSelector: '.guest-row:first-child, .guest-card:first-child, tr.guest:first-child, tbody tr:first-child',
    },
  },
  {
    id: 9, title: 'Documented ROI', screen: 'performance',
    spotlightSelector: '[data-tour="roi-hero"], [data-demo="roi"]',
    narration:
      "Every month, INNtelligence produces this report. The ROI Performance Report. And I want to be specific about why this exists, because it matters. Most software you buy just does a thing. You pay for it, you use it, and at some point you're asked whether you want to renew. You kind of remember that it seemed helpful, but you can't quite put a number on it. INNtelligence doesn't work that way. Every month, it produces documentation. Exact numbers. The specific dates, room types, and rate decisions that generated additional revenue. The direct booking savings from guests who were captured through your website instead of an OTA. The total value delivered to your property — in dollars — compared directly to the subscription cost. This month's report for Anchorage 1770: Engine revenue contribution: $4,840. That's the documented additional revenue from rate recommendations — the difference between what you would have charged at your old rates and what INNtelligence recommended and you approved. Direct booking savings: $1,240. Commissions you didn't pay because guests booked directly through your website instead of through Booking dot com or Expedia. Total value delivered: $6,080. Subscription cost: $699. Return on subscription: 8.7 times. For every dollar you spent on INNtelligence this month, you got $8.70 back. And listed right below — every specific win. July 20th, Water Festival, Waterfront Suite: $378 became $535. $157 per night, times 3 nights, for one room, during one event. This is not a testimonial. This is your own data, from your own property, documented and dated. Show it to your accountant. Show it to your bank. Show it to anyone who asks whether the subscription is worth it.",
    autoAdvance: true,
  },
  {
    id: 10, title: 'Package Intelligence', screen: 'packages',
    spotlightSelector: '[data-demo="package-card"], .package-card',
    narration:
      "Packages are one of the most underutilized revenue opportunities at boutique inns. Not because innkeepers don't know packages work — they do — but because building them, pricing them correctly, and knowing which ones to promote and when takes time and research that most owner-operators simply don't have. INNtelligence handles this through the Package Intelligence module. Here's the Anniversary Package — room, fresh flowers from a local Beaufort florist, a bottle of champagne on arrival. INNtelligence is recommending a $65 add-on above the base room rate. How did it arrive at $65? It analyzed what comparable boutique inns nationally charge for this package — 71 percent of Select Registry properties offer some version of it — and what the actual cost of the components is. The flowers, the champagne, the innkeeper's time to arrange it. The margin is healthy, and the $65 premium doesn't feel significant to a couple celebrating an anniversary. At a 22 percent conversion rate — meaning roughly 1 in 5 guests who see the Anniversary Package offer actually books it — that generates $4,095 per month in additional revenue. From one package. And INNtelligence knows when to promote it. Six weeks before Water Festival, when anniversary travel spikes. Around Valentine's weekend. During the period when couples tend to plan milestone celebrations. The Adventure Package, the Breakfast Upgrade, the Spa Enhancement, the Sunset Cruise — each one has its own pricing recommendation, its own conversion data, and its own optimal promotion timing. You don't have to guess at any of it.",
    autoAdvance: true,
  },
  {
    id: 11, title: 'Works on Your Phone', screen: 'historical',
    spotlightSelector: '[data-demo="trend-chart"], svg.recharts-surface',
    narration:
      "I want to show you something that sounds small but matters enormously in the day-to-day reality of running an inn. Everything you've seen — the Rate Calendar, the Competitive Intelligence, the F&B yield analysis, the Guest CRM, the ROI report — all of it is accessible from your phone. Right now. Without downloading anything. INNtelligence is a progressive web app. You open the link in Safari on your iPhone, you tap Add to Home Screen, and from that moment on it sits on your home screen and opens like a native app. No App Store approval process. No waiting for an update to download. Just the full INNtelligence dashboard, on your phone, always current. This matters because innkeeping doesn't follow a desk schedule. You're checking in a guest and your phone buzzes — Cuthbert House just sold out for the weekend you have open dates. INNtelligence caught it. You pull out your phone, see the alert, tap to approve the rate increase, and put your phone back in your pocket. Thirty seconds. You never left the conversation with your arriving guest. You're at dinner and you get a notification — booking pace just spiked 40 percent for the next two weekends. There's a USMC graduation at Parris Island you hadn't fully accounted for. You review it, approve it, and your rates are updated on all seven OTAs before you've finished your appetizer. Or you're simply away — visiting family, on vacation yourself — and you know your property is being managed intelligently while you're gone. Not by a person you're paying to sit at a desk, but by a system that monitors your market continuously and makes reasoned decisions within the guardrails you've set. That's what INNtelligence is designed for.",
    autoAdvance: true,
  },
  {
    id: 12, title: 'Why I Built INNtelligence', screen: 'calendar',
    spotlightSelector: '[data-tour="festival-alert"], [data-demo="festival-alert"]',
    narration:
      "Let me tell you who built INNtelligence and why, because I think it matters. My name is Jim Williams. I'm a Certified Pricing Professional with eleven years of experience in revenue management. I built pricing systems for major telecommunications companies. I understand demand modeling, competitive positioning, and yield optimization at an enterprise level. And I'm also an innkeeper. I fell in love with a historic property on Bay Street in Beaufort, South Carolina — Anchorage 1770 Inn, the exact property you've been watching throughout this demo — and I started the process of acquiring it. And in preparing to run it, I looked at every revenue management tool available for boutique inns. What I found was disappointing. Enterprise systems priced at $1,500 to $10,000 a month, built for chain hotels, adapted poorly for small independent properties. Simpler tools that priced rooms only — ignoring the restaurant, the bar, the entire guest relationship. And a few promising platforms that closed without warning when their venture funding ran out. So I built INNtelligence from scratch. Built it the way I would want it as an innkeeper. Transparent reasoning. Full control. All six revenue streams. Real Beaufort market data, real competitor monitoring, real event intelligence. And priced at $399 to $699 a month — a subscription that pays for itself many times over. The Water Festival starts in 57 days. Your Waterfront Suite rates are not yet at their Water Festival premium. Cuthbert House is already seeing sold-out dates. Every day between now and July 17th is an opportunity to capture revenue that your competitors are already capturing. INNtelligence starts with a 14-day free trial. No credit card. Personal onboarding from me directly. Let's talk.",
    autoAdvance: false,
  },
]

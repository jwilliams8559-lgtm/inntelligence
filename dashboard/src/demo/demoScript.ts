export type DemoScreen =
  | 'calendar' | 'demand' | 'events' | 'competitive' | 'reputation'
  | 'fnb' | 'crm' | 'behavior' | 'packages' | 'performance' | 'historical'

export interface DemoStep {
  id: number
  title: string
  screen: DemoScreen
  /** CSS selector for the element to spotlight on that screen. Falls
   * back to a screen-wide darkening when the selector matches nothing. */
  spotlightSelector?: string
  narration: string
  autoAdvance: boolean
}

export const DEMO_STEPS: DemoStep[] = [
  {
    id: 1, title: 'Water Festival Alert', screen: 'calendar',
    spotlightSelector: '[data-tour="festival-alert"], [data-demo="festival-alert"]',
    narration:
      "Welcome to INNtelligence. This is the rate intelligence center for Anchorage 1770 Inn in Beaufort, South Carolina, a 14-room historic boutique inn on Bay Street. The first thing you see is an alert. The Beaufort Water Festival is approaching — the biggest tourism event of the year in the Lowcountry. INNtelligence detected it automatically. Your competitors are already raising rates.",
    autoAdvance: true,
  },
  {
    id: 2, title: 'The 90-Day Rate Calendar', screen: 'calendar',
    spotlightSelector: '[data-tour="rate-cell-festival"], [data-demo="rate-grid"], table',
    narration:
      "This is the 90-Day Rate Calendar. Each row is a room type. Each column is a day. Gold cells mark Water Festival dates — colored automatically so you see your biggest revenue opportunities instantly. For the Waterfront Suite during Water Festival, INNtelligence recommends 565 dollars per night with a 3-night minimum. Your base rate was 419 dollars. That's a 146-dollar lift per night, on every room, for ten consecutive nights.",
    autoAdvance: true,
  },
  {
    id: 3, title: 'Plain-English Reasoning', screen: 'calendar',
    spotlightSelector: '[data-demo="rate-grid"], table',
    narration:
      "Every rate recommendation comes with plain English reasoning. Demand score 92 of 100, Peak. Four factors: booking pace is 23 percent ahead of last year. Water Festival historically drives 94 percent occupancy. Cuthbert House and Rhett House Inn are already sold out at 560 and 510. And as a boutique inn with the Ribaut Social Club restaurant and breakfast included, you offer 136 dollars more value per night than a comparable Airbnb. Recommended rate: 565 dollars.",
    autoAdvance: true,
  },
  {
    id: 4, title: 'One-Click Approval to 7 OTAs', screen: 'calendar',
    spotlightSelector: '[data-demo="approve-all"], button[class*="approve"]',
    narration:
      "Approving rates takes one click. Approved rates publish to seven OTAs simultaneously: Booking.com, Expedia, Airbnb, VRBO, Hotels.com, Trip.com, and Agoda. In under three seconds. Approve All publishes every pending recommendation across 14 rooms and 90 days at once. This is what INNtelligence autopilot does every morning before your first cup of coffee.",
    autoAdvance: true,
  },
  {
    id: 5, title: 'Competitive Intelligence', screen: 'competitive',
    spotlightSelector: '[data-demo="comp-table"], table',
    narration:
      "This is your Competitive Intelligence center. INNtelligence monitors 39 properties in the Beaufort market in real time. Boutique inn direct competitors are your true peers. Airbnb and VRBO are shown for context but never used for your pricing. On Water Festival weekends Cuthbert House sells out at 560, Rhett House at 510, Anchorage 1770 at 570 — the premium boutique alternative when the competition is full.",
    autoAdvance: true,
  },
  {
    id: 6, title: 'F&B Yield Management', screen: 'fnb',
    spotlightSelector: '[data-demo="dow-table"], table',
    narration:
      "Something no other platform does: INNtelligence manages your Food and Beverage revenue too. The Ribaut Social Club shows a clear pattern. Friday and Saturday run at 88 to 92 percent capacity, around 3,400 dollars per night. Tuesday and Wednesday sit at 44 percent — barely 1,200 dollars. INNtelligence flags those slow nights in amber and recommends a 35 dollar prix fixe lunch, a happy hour, or a Dinner and Stay package. Annual opportunity: over 24,000 dollars.",
    autoAdvance: true,
  },
  {
    id: 7, title: 'Guest CRM', screen: 'crm',
    spotlightSelector: '[data-demo="guest-list"], table, .guest-card',
    narration:
      "Your guests are your most valuable asset. INNtelligence segments returning guests by lifetime value, recency, and stay pattern. When a VIP guest has not visited in twelve months, INNtelligence automatically drafts a personal re-engagement email — timed to arrive six weeks before Water Festival when conversion rates peak. One click sends it.",
    autoAdvance: true,
  },
  {
    id: 8, title: 'Behavior Tracking', screen: 'behavior',
    spotlightSelector: '[data-demo="booking-sources"], svg.recharts-surface',
    narration:
      "Behavior tracking shows you exactly where every booking comes from. Direct bookings at 26 percent — above the industry average. OTA commissions paid this month: over 3 thousand dollars. INNtelligence flags every opportunity to shift bookings direct. Cancellation analysis spots patterns. Price sensitivity tracking shows which rate increases your guests absorb and which ones slow your booking pace.",
    autoAdvance: true,
  },
  {
    id: 9, title: 'Documented ROI', screen: 'performance',
    spotlightSelector: '[data-tour="roi-hero"], [data-demo="roi"]',
    narration:
      "Every month INNtelligence produces a documented return on investment report. This month: 4,840 dollars in engine-driven revenue increases. 1,240 dollars in direct booking savings. Total value delivered: 6,080 dollars against a 699 dollar subscription. That is 8.7 times return — documented, not estimated. Every top win listed by date, room, and exact dollar amount.",
    autoAdvance: true,
  },
  {
    id: 10, title: 'Package Intelligence', screen: 'packages',
    spotlightSelector: '[data-demo="package-card"], .package-card',
    narration:
      "INNtelligence also manages your guest packages. The Anniversary Package — room, flowers, champagne — is offered by 71 percent of comparable boutique inns nationally. INNtelligence recommends pricing it 65 dollars above base rate. At 22 percent conversion that generates over 4,000 dollars per month from guests who wanted to celebrate and just needed the prompt.",
    autoAdvance: true,
  },
  {
    id: 11, title: 'Historical Trends', screen: 'historical',
    spotlightSelector: '[data-demo="trend-chart"], svg.recharts-surface',
    narration:
      "Historical Performance shows the proof. RevPAR up 17.5 percent year over year. ADR up 8.2 percent. Occupancy up 4.8 points. Direct booking share grew from 22 to 26 percent. Every metric trending the right direction. Solid gold line is this year, dashed navy is prior. Export the report as a PDF for your accountant, your bank, or potential investors.",
    autoAdvance: true,
  },
  {
    id: 12, title: 'Ready to Start?', screen: 'calendar',
    spotlightSelector: '[data-tour="festival-alert"], [data-demo="festival-alert"]',
    narration:
      "This is INNtelligence — revenue intelligence built for innkeepers, by an innkeeper. 14 room types. 7 OTA channels. 39 competitors monitored. Restaurant yield. Guest CRM. Package intelligence. Plain-English reasoning on every recommendation. Every day you wait is a day your competitors are filling up at higher rates. Start your free 14-day trial today.",
    autoAdvance: false,
  },
]

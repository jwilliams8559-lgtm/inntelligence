export interface DemoStep {
  id: number
  screen: 'calendar' | 'demand' | 'events' | 'competitive' | 'reputation' | 'fnb' | 'crm' | 'behavior' | 'packages' | 'performance' | 'historical' | 'settings'
  spotlightSelector?: string
  narration: string
  autoAdvanceSec?: number  // auto-advance after this many seconds (in addition to narration end)
  click?: string           // optional element to programmatically click after narration
}

export const DEMO_STEPS: DemoStep[] = [
  {
    id: 1, screen: 'calendar', spotlightSelector: '[data-tour="festival-alert"]',
    narration: "Welcome to INNtelligence. This is the rate intelligence center for Anchorage 1770 Inn in Beaufort, South Carolina — a 14-room historic boutique inn on Bay Street. The first thing you see is an alert. The Beaufort Water Festival is the biggest tourism event of the year in the Lowcountry. INNtelligence detected it automatically. Your competitors have already started raising rates. Let me show you.",
  },
  {
    id: 2, screen: 'calendar', spotlightSelector: '[data-tour="rate-cell-festival"]',
    narration: "This is the 90-Day Rate Calendar. Each row is a room type. Gold cells are Water Festival — colored automatically so you see your biggest opportunities instantly. For the Waterfront Suite during Water Festival, INNtelligence recommends $565 per night with a 3-night minimum. Your base rate was $378. That is $187 more per night — over 1800 dollars in additional revenue from one room during one event.",
  },
  {
    id: 3, screen: 'calendar',
    narration: "What separates INNtelligence from every other pricing tool is plain English reasoning for every recommendation. Demand score 92 out of 100. Peak. Four factors: booking pace is 23 percent ahead of last year. Water Festival drives 94 percent historical occupancy. Cuthbert House and Rhett House Inn are already sold out. And as a boutique inn with the Ribaut Social Club restaurant and breakfast included, you provide $136 more value per night than a comparable Airbnb.",
  },
  {
    id: 4, screen: 'calendar',
    narration: "Approving rates takes one click. Approved rates publish to seven OTAs simultaneously: Booking.com, Expedia, Airbnb, VRBO, Hotels.com, Trip.com, and Agoda. In under three seconds. Or use autopilot to publish 363 rate recommendations every morning before your first cup of coffee.",
  },
  {
    id: 5, screen: 'competitive',
    narration: "This is your Competitive Intelligence center. INNtelligence monitors 39 properties in the Beaufort market in real time. Boutique inn direct competitors are your true peers. Airbnb and VRBO are shown for context but never used for your pricing. On Water Festival weekends: Cuthbert House sold out at $560. Rhett House sold out at $510. Anchorage 1770 at $570. The premium boutique alternative. This is exactly where you want to be.",
  },
  {
    id: 6, screen: 'fnb',
    narration: "Something no other platform does: INNtelligence manages your Food and Beverage revenue too. The Ribaut Social Club shows a clear pattern. Friday and Saturday: 88 to 92 percent capacity, around $3,400 in revenue per night. Tuesday and Wednesday: 44 percent capacity, barely $1,200. INNtelligence flags those slow nights in amber and recommends a $35 prix fixe lunch, a happy hour, or a Dinner and Stay package. Annual opportunity from optimizing slow nights: over 24 thousand dollars.",
  },
  {
    id: 7, screen: 'crm',
    narration: "Your guests are your most valuable asset. INNtelligence segments returning guests by lifetime value, recency, and stay pattern. When a VIP guest hasn't visited in twelve months, INNtelligence automatically drafts a personal re-engagement email timed to arrive six weeks before Water Festival when conversion rates peak. One click sends it.",
  },
  {
    id: 8, screen: 'performance',
    narration: "Every month INNtelligence produces a documented return on investment report. This month: $4,840 in engine-driven revenue increases. $1,240 in direct booking savings. Total value delivered: $6,080. Subscription cost $699. That is 8.7 times your subscription cost — documented, not estimated. Every top win listed by date, room type, and exact dollar amount.",
  },
  {
    id: 9, screen: 'packages',
    narration: "INNtelligence also manages your guest packages. The Anniversary Package is offered by 71 percent of comparable boutique inns nationally. INNtelligence recommends pricing it at $65 above base. At 22 percent conversion rate that generates over $4,000 per month in additional revenue from guests who wanted to celebrate but needed the prompt.",
  },
  {
    id: 10, screen: 'historical',
    narration: "Historical Performance shows the proof. RevPAR up 17.5 percent year over year. ADR up 8.2 percent. Occupancy up 4.8 points. Direct booking share grew from 22 percent to 26 percent. Every metric trending the right direction. The dashed navy line is last year, the solid gold line is this year. Export the report as a PDF for your accountant, bank, or potential investors.",
  },
  {
    id: 11, screen: 'reputation',
    narration: "Reviews drive pricing power. Your 4.8 TripAdvisor rating supports a 15 percent rate premium above the comp set. INNtelligence accounts for this in every recommendation. New 5-star reviews trigger pricing power score updates automatically. Negative review keywords surface so you can fix the underlying issue before it spreads.",
  },
  {
    id: 12, screen: 'calendar', spotlightSelector: '[data-tour="festival-alert"]',
    narration: "This is INNtelligence — revenue intelligence built for innkeepers, by an innkeeper. 14 room types. 7 OTA channels. 39 competitors monitored. Restaurant yield. Guest CRM. Package intelligence. Plain-English reasoning on every recommendation. Every day you wait is a day your competitors are filling up at higher rates. Start your free trial today — 14 days, no credit card required.",
  },
]

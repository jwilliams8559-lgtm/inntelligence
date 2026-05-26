// Guided /demo tour — 7 steps over the REAL Bay Street Inn dashboard.
//
// Each step deep-links to a real screen (with query params that set its initial
// view), then spotlights a real element by its data-tour id. Tooltip copy is
// number-light on purpose: the spotlighted element shows the real, live values
// so the words can never contradict the screen. Narration audio is served from
// /api/tour/audio/<narrationId> (ElevenLabs "Will"), generated server-side.
//
// Step 7 has no target — the overlay renders a closing call-to-action card.

export const DEMO_STEPS = [
  {
    id: 'demo_01',
    title: '90-Day Rate Calendar',
    route: '/rate-calendar?days=90',
    target: 'wf-banner',
    text: "This is the real INNtelligence dashboard for The Bay Street Inn. Every cell is an AI-generated rate recommendation — one room, one night. Note the Water Festival alert: peak demand, detected automatically.",
  },
  {
    id: 'demo_02',
    title: 'Why this rate?',
    route: '/rate-calendar?days=90&focus=peak',
    target: 'rate-drawer',
    text: "Click any date and INNtelligence shows the full reasoning — demand, competitor rates, seasonal index and lead time, in plain English. Accept it or override it in one click.",
  },
  {
    id: 'demo_03',
    title: 'Competitive Intelligence',
    route: '/competitive-intel?tier=waterfront&days=90',
    target: 'comp-cuthbert',
    text: "INNtelligence monitors your Beaufort competitors around the clock and compares you like-for-like, by room type. Cuthbert House Inn is one of your closest waterfront competitors.",
  },
  {
    id: 'demo_04',
    title: 'Demand Forecast',
    route: '/events?view=quarter',
    target: 'events-peak',
    text: "Your demand forecast reads the local Beaufort events calendar and turns it into revenue. Every event is scored by pricing impact, and the biggest demand drivers are surfaced automatically — months ahead.",
  },
  {
    id: 'demo_05',
    title: 'Guest CRM',
    route: '/guest-crm',
    target: 'crm-stats',
    text: "INNtelligence segments every guest automatically — VIPs, regulars, and lapsed guests worth winning back. When occupancy dips, it can trigger a personalized win-back campaign.",
  },
  {
    id: 'demo_06',
    title: 'Approve All',
    route: '/rate-calendar?days=90&spotlight=approve',
    target: 'approve-all',
    text: "Here's the moment that changes your morning: approve every recommendation in one click, and INNtelligence publishes to Booking.com, Expedia, Airbnb, VRBO, Hotels.com, Trip.com and Agoda at once.",
  },
  {
    id: 'demo_closing',
    title: 'INNtelligence',
    route: '/rate-calendar?days=90',
    target: null,           // closing CTA card, no spotlight
    text: "That's INNtelligence — real pricing intelligence for boutique inns. Starting at $399 a month, with Founding Member access free for six months. Request access today.",
  },
]

export const DEMO_CONTACT_EMAIL = 'jwilliams8559@gmail.com'

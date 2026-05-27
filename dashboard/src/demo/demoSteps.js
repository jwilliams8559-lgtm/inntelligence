// Guided /demo tour — 11 steps over the REAL Bay Street Inn dashboard, framed
// by a full-screen opening (founder intro) and a full-screen closing (CTA).
//
// Each "screen" step deep-links to a real screen and spotlights a real element
// by its data-tour id when one exists, falling back to robust CSS selectors,
// then to a no-spotlight centered tooltip. On-screen captions are short; the
// full narration lives server-side (app.py DEMO_NARRATION) for ElevenLabs audio
// and the browser-speech fallback. Auto-advance is driven by audio end, with the
// per-step `timer` (seconds) as the fallback when no audio is available.

export const DEMO_CONTACT = {
  name: 'Jim Williams',
  phone: '470-789-2433',
  email: 'jwilliams8559@gmail.com',
}

export const DEMO_MAILTO =
  'mailto:jwilliams8559@gmail.com' +
  '?subject=' + encodeURIComponent('INNtelligence Founding Member Request') +
  '&body=' + encodeURIComponent(
    'Hi Jim, I watched the INNtelligence demo and I am interested in the Founding Member program. My property is:')

export const DEMO_STEPS = [
  {
    id: 'step_00', kind: 'opening', route: '/', target: null, timer: 20,
    title: 'INNtelligence',
  },
  {
    id: 'step_01', kind: 'screen', route: '/', target: null,
    selectors: ['main .grid', 'main h1'], timer: 18, title: 'Tuesday Morning',
    caption: "Tuesday at The Bay Street Inn. INNtelligence is mobile-first — every feature works identically on iPhone, Android, iPad, or any tablet. It ran all night: 39 properties watched, booking pace checked. Water Festival in 52 days: peak demand. Nothing changes until Sarah approves.",
    badge: 'Works on iPhone · Android · iPad · Any tablet',
  },
  {
    id: 'step_02', kind: 'screen', route: '/rate-calendar?days=90', target: 'wf-banner',
    timer: 22, title: 'Rate Calendar — 90 Days',
    caption: "90 days of AI rate recommendations — every room, every night. The gold Water Festival columns (Jul 17–26) score 90/100 — Peak. These are recommendations only. Nothing is live until Sarah approves.",
  },
  {
    id: 'step_03', kind: 'screen', route: '/rate-calendar?days=90&focus=wf', target: 'rate-drawer',
    timer: 25, title: 'Why This Rate?', dynamicRate: true,
    caption: "On a Water Festival night, see the full reasoning — demand 90/100, competitor compression, booking pace +47%. The direct rate nets more than the OTA, with a 3-night minimum on peak dates.",
  },
  {
    id: 'step_04', kind: 'screen', route: '/competitive-intel?tier=waterfront&days=90&room=waterfront', target: 'comp-cuthbert',
    timer: 22, title: 'Competitive Intelligence',
    caption: "39 competitors found within 25 miles; the 9 most relevant scored. Filter to Waterfront Suite and non-waterfront competitors gray out. Cuthbert (92.7) sold out, Anchorage (88.5) limited — Bay Street becomes THE waterfront option.",
  },
  {
    id: 'step_05', kind: 'screen', route: '/events?view=6mo', target: 'events-peak',
    timer: 18, title: 'Demand Calendar',
    caption: "Every Beaufort demand driver, by horizon. Parris Island graduations every Friday, the Gullah Festival, Water Festival, the Film Festival — months of revenue intelligence with time to prepare. No surprises.",
  },
  {
    id: 'step_06', kind: 'screen', route: '/weddings', target: 'wedding-calc',
    selectors: ['main .rounded-2xl', 'main .rounded-xl', 'main .grid'], timer: 20, title: 'Weddings & Private Events',
    caption: "A wedding inquiry: 40 guests, full buyout, 2 nights → $37,300, a clear accept. Move it onto Water Festival dates and the conflict alert fires — festival pricing beats the buyout. The AI flags it; Sarah decides.",
  },
  {
    id: 'step_07', kind: 'screen', route: '/private-events', target: null,
    selectors: ['main .grid', 'main .rounded-2xl', 'main .rounded-xl'], timer: 26, title: 'Private Events, Packages & Gift Shop',
    caption: "Private Events manages buyouts, corporate retreats, and group bookings with the same revenue intelligence as weddings.",
    sequence: [
      { route: '/private-events', at: 0, caption: "Private Events manages buyouts, corporate retreats, and group bookings with the same revenue intelligence as weddings — conflict detection, exclusivity premium, and comparison to displaced individual room revenue." },
      { route: '/packages', at: 8000, caption: "INNtelligence includes 25 pre-built packages used by top boutique inns nationwide — romance, anniversary, culinary, birding, and more. Turn any on or off instantly. Each is pre-priced and integrated with your rate calendar for total RevPAR optimization." },
      { route: '/gift-shop', at: 18000, caption: "Gift shop and retail revenue — tracked alongside room revenue for a complete picture of every dollar your property generates." },
    ],
  },
  {
    id: 'step_08', kind: 'screen', route: '/guest-crm', target: 'crm-stats',
    timer: 22, title: 'Guest CRM',
    caption: "Guests auto-segmented nightly — 7 VIP, 8 local, 3 lapsed, 4 new. With November occupancy forecast under 55%, INNtelligence drafted a win-back campaign. Sarah personalizes it in her own voice and approves.",
  },
  {
    id: 'step_09', kind: 'screen', route: '/reputation', target: null,
    selectors: ['main .grid', 'main .rounded-2xl', 'main .rounded-xl'], timer: 16, title: 'Reputation',
    caption: "Google, TripAdvisor and Booking reviews in one feed. 4.8 overall, up from 4.6. One review flagged with a suggested reply — Sarah answers in her own voice. Reputation is revenue.",
  },
  {
    id: 'step_10', kind: 'screen', route: '/roi-performance', target: null,
    selectors: ['main .grid', 'main .rounded-2xl', 'main .rounded-xl'], timer: 20, title: 'ROI Performance',
    caption: "This month vs last year: occupancy +9%, ADR +16%, RevPAR +26%. $699/mo subscription, $1,244 avg lift, $545 net benefit — 1.8× monthly, 7.1× annual ROI. Conservative. Auditable. Real.",
  },
  {
    id: 'step_11', kind: 'screen', route: '/rate-calendar?days=90', target: 'approve-all',
    timer: 22, title: 'Approve All & Publish',
    caption: "55 minutes reviewed. Sarah taps Approve All — and in 2.26 seconds rates publish to all 7 OTAs at once. The AI works all night so the innkeeper works smarter in the morning.",
  },
  {
    id: 'closing', kind: 'closing', route: null, target: null, timer: 30,
    title: 'INNtelligence',
  },
]

// Steps that carry a "Step X of 11" counter (the 11 numbered screen steps).
export const SCREEN_STEP_COUNT = DEMO_STEPS.filter((s) => s.kind === 'screen').length
export const FIRST_SCREEN_INDEX = DEMO_STEPS.findIndex((s) => s.kind === 'screen')
export const LAST_INDEX = DEMO_STEPS.length - 1

export const PMS_LIST = ['ResNexus', 'Cloudbeds', 'ThinkReservations', 'Guesty', 'WebRezPro', 'Little Hotelier']
export const OTA_LIST = ['Booking.com', 'Expedia', 'Airbnb', 'VRBO', 'Hotels.com', 'Trip.com', 'Agoda']
export const GEO_LIST = ['United States', 'Canada', 'United Kingdom', 'Europe', 'Caribbean']

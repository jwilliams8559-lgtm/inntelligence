// Single source for the 12 screens — drives both the sidebar nav and the routes.
export const SCREENS = [
  { path: '/rate-calendar',       name: 'Rate Calendar',       icon: '📅' },
  { path: '/competitive-intel',   name: 'Competitive Intel',   icon: '📊' },
  { path: '/fnb-yield',           name: 'F&B Yield',           icon: '🍽️' },
  { path: '/guest-crm',           name: 'Guest CRM',           icon: '👥' },
  { path: '/roi-performance',     name: 'ROI Performance',     icon: '💰' },
  { path: '/packages',            name: 'Packages',            icon: '🎁' },
  { path: '/gift-shop',           name: 'Gift Shop',           icon: '🛍️' },
  { path: '/historical',          name: 'Historical',          icon: '📈' },
  { path: '/reputation',          name: 'Reputation',          icon: '⭐' },
  { path: '/weather',             name: 'Weather',             icon: '☀️' },
  { path: '/gap-night',           name: 'Revenue Intelligence', icon: '🧠' },
  { path: '/events',              name: 'Events',              icon: '🎉' },
  { path: '/private-events',      name: 'Private Events',      icon: '💒' },
  { path: '/weddings',            name: 'Weddings',            icon: '💍' },
  { path: '/management-console',  name: 'Management Console',  icon: '🛠️' },
  { path: '/admin/analytics',     name: 'Analytics',           icon: '📊' },
]

// Route → feature-catalog key (engine/features.py). Drives sidebar locks and
// the in-feature trial banner. Admin-only paths are gated by role, not tier.
export const PATH_FEATURE = {
  '/rate-calendar':     'rate_calendar',
  '/competitive-intel': 'competitive_intel',
  '/events':            'events',
  '/reputation':        'reputation',
  '/weather':           'weather',
  '/historical':        'historical',
  '/roi-performance':   'roi_performance',
  '/guest-crm':         'guest_crm_basic',
  '/weddings':          'weddings',
  '/private-events':    'private_events',
  '/packages':          'packages',
  '/gift-shop':         'gift_shop',
  '/fnb-yield':         'fb_yield',
  '/gap-night':         'revenue_intel',
}

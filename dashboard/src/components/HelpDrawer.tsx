import { useState } from 'react'

interface Props { open: boolean; onClose: () => void }

interface Guide { id: string; title: string; emoji: string; body: string[] }

const GUIDES: Guide[] = [
  {
    id: 'pms', title: 'Connecting your PMS', emoji: '🔌',
    body: [
      '**Step 1.** Settings → Property → choose your PMS (ResNexus or Cloudbeds).',
      '**Step 2.** Paste the API key from your PMS account. For Cloudbeds, you\'ll be redirected to authorize OAuth.',
      '**Step 3.** Click "Test Connection". You should see "✓ Connection verified".',
      '**Step 4.** The first sync pulls 12 months of history and forward inventory — usually 30–90 seconds.',
      'After the first sync, daily syncs run at 3 AM property time.',
    ],
  },
  {
    id: 'recommendations', title: 'Understanding your rate recommendations', emoji: '📅',
    body: [
      'Every cell in the Rate Calendar is a recommendation for one room type on one date.',
      '**Demand score (0–100)** combines 4 signals: booking pace (35%), seasonal pattern (25%), local events (20%), competitive set (20%).',
      '**Recommended rate** applies an S-curve to your base rate, weighted by demand score, with quality and bathroom premiums layered on top.',
      'Score color: green ≥ 76, gold 61–75, amber 41–60, red < 40.',
      'Click any cell to see the drivers, comp set rates, OTA breakdown, and LOS pricing.',
    ],
  },
  {
    id: 'autopilot', title: 'Setting up autopilot', emoji: '🤖',
    body: [
      'Autopilot publishes approved rates to your channel manager automatically — within limits you control.',
      '**Per-room toggle** in Settings → Autopilot. Start with one room (e.g., your premium suite) for the first 30 days.',
      '**Max rate change**: how far the new rate can move vs current rate. Safe default 10%; aggressive: 20%.',
      '**Min confidence**: refuse to publish below this score. Default 75; tighten to 85 for higher-risk dates.',
      '**Active hours**: rates only publish 6 AM–10 PM by default — you\'ll never wake to a surprise overnight push.',
      '**Daily cap**: maximum 3 changes per room per day, even if more recommendations are eligible.',
    ],
  },
  {
    id: 'demand', title: 'Reading the demand dashboard', emoji: '📊',
    body: [
      'The Demand Dashboard answers: "What will my next 90 days look like?"',
      '**Booking pace** vs same period last year — green if ahead, red if behind.',
      '**Forward occupancy curve** shows projected fill rate per night.',
      '**Driver attribution** breaks each day into the 4 signals (pace, season, events, comp set).',
      'Use this to spot soft windows early — campaigns drafted from the Guest CRM target these dates automatically.',
    ],
  },
  {
    id: 'crm', title: 'Using the guest CRM', emoji: '👥',
    body: [
      'Guests are auto-segmented nightly: VIP (3+ stays or $1,500+ revenue), Local (SC/GA/NC), Lapsed (12+ mo since last stay), New, Anniversary, Honeymoon.',
      'WiFi capture form at /wifi/<slug> brings walk-ins into your CRM with marketing consent.',
      '**Demand-triggered campaigns** auto-draft when a 7-day window forecasts low occupancy 21+ days out. Review and send with one click.',
      'Unsubscribe links use HMAC tokens — no account creation needed for guests to opt out.',
    ],
  },
  {
    id: 'competitors', title: 'Managing competitors', emoji: '🎯',
    body: [
      'Settings → Discover Competitors finds nearby boutique hotels and ranks them on price band (30%), amenity (25%), distance (20%), reviews (15%), and size (10%).',
      'Rank #1 becomes your dynamic pricing anchor — the rate engine pegs against it on peak dates.',
      '**Competitor drop alerts** fire when any competitor drops >20% overnight for dates within 60 days.',
      'Edit the radius (10/25/50mi) from the same modal. The system seeds 730 days of synthetic rates immediately so the comp set works on day one.',
    ],
  },
]

export default function HelpDrawer({ open, onClose }: Props) {
  const [active, setActive] = useState<string>(GUIDES[0].id)
  if (!open) return null
  const guide = GUIDES.find(g => g.id === active) ?? GUIDES[0]

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-navy/30" />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="bg-navy text-white px-5 py-3 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[3px] text-gold font-bold">Help</div>
            <h2 className="font-bold text-base">Quick guides</h2>
          </div>
          <button onClick={onClose} className="text-white/60 hover:text-white text-2xl leading-none">×</button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <nav className="w-52 bg-cream border-r border-slate-200 overflow-y-auto scrollbar-thin py-2">
            {GUIDES.map(g => (
              <button key={g.id} onClick={() => setActive(g.id)}
                className={`w-full text-left flex items-center gap-2 px-3 py-2.5 text-sm font-medium transition-colors border-l-2 ${
                  active === g.id
                    ? 'bg-white border-navy text-navy'
                    : 'border-transparent text-slate-500 hover:bg-white hover:text-navy'
                }`}>
                <span>{g.emoji}</span>
                <span className="flex-1">{g.title}</span>
              </button>
            ))}
          </nav>

          {/* Body */}
          <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-5">
            <h3 className="font-bold text-navy text-xl mb-1">
              <span className="mr-2">{guide.emoji}</span>{guide.title}
            </h3>
            <div className="border-b border-slate-200 mb-4" />
            <div className="space-y-3 text-sm text-slate-700 leading-relaxed">
              {guide.body.map((p, i) => (
                <p key={i} dangerouslySetInnerHTML={{
                  __html: p
                    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-navy">$1</strong>')
                    .replace(/`(.+?)`/g, '<code class="text-xs bg-slate-100 px-1 rounded">$1</code>')
                }} />
              ))}
            </div>
          </div>
        </div>

        <div className="px-5 py-2 bg-cream border-t border-slate-200 text-[10px] text-slate-400 text-center">
          The Gracious Collection · Need more help? Email Jim Williams directly.
        </div>
      </div>
    </div>
  )
}

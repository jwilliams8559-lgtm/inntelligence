import { useEffect, useState } from 'react'

interface Props { open: boolean; onClose: () => void }

interface Step {
  screen: 'calendar' | 'demand' | 'events' | 'competitive' | 'reputation' | 'crm' | 'packages' | 'performance' | 'management' | 'settings'
  title: string
  body: string
  cta: string
  next_screen?: Step['screen']
  spotlight?: string  // CSS selector — element to highlight
}

const STEPS: Step[] = [
  {
    screen: 'calendar',
    title: 'Beaufort Water Festival',
    body: 'July 17–26 — your busiest 10 days of the year. The engine detected Peak demand (score 92/100) and is recommending $535/night for Waterfront Suites — a $157 increase over last year\'s rate.',
    cta: 'See the recommendation →',
    next_screen: 'calendar',
    spotlight: '[data-tour="festival-alert"]',
  },
  {
    screen: 'calendar',
    title: 'Every rate comes with a plain-English reason',
    body: 'Click any cell to see the demand score gauge, the drivers behind it, competitor rates, OTA commission waterfall, and the reasoning. No black box. You always know why.',
    cta: 'See your competitive position →',
    next_screen: 'competitive',
    spotlight: '[data-tour="rate-cell-festival"]',
  },
  {
    screen: 'competitive',
    title: 'Where you sit in the market',
    body: 'Cuthbert House: SOLD OUT at $560. Rhett House: SOLD OUT at $510. Your recommended rate of $480 positions you as the premium boutique alternative when competitors are full.',
    cta: 'See your revenue forecast →',
    next_screen: 'demand',
  },
  {
    screen: 'demand',
    title: 'Revenue forecast vs last year',
    body: 'The engine forecasts 92.1% occupancy this month — up from 87.3% last year. RevPAR is $409, up $61 year-over-year. The gold band on the chart is your Water Festival lift.',
    cta: 'See what this earned you →',
    next_screen: 'performance',
  },
  {
    screen: 'performance',
    title: 'Subscription ROI',
    body: 'Last month the engine contributed an estimated $1,244 in additional revenue against a $699 subscription. That\'s 1.8× return. The conservative 15% lift case — it climbs past 2× at 20%.',
    cta: 'See your guest packages →',
    next_screen: 'packages',
    spotlight: '[data-tour="roi-hero"]',
  },
  {
    screen: 'packages',
    title: 'Differentiate, don\'t compete on price',
    body: '78% of boutique inns nationally offer a Romance Package. None of your direct competitors offer a Stargazing Package — that\'s a differentiator opportunity with zero price competition.',
    cta: 'See your gift shop →',
    next_screen: 'settings',
  },
  {
    screen: 'reputation',
    title: 'Reviews drive your pricing power',
    body: 'Your 4.8 TripAdvisor rating supports a 15% rate premium above your comp set. The engine accounts for this in every recommendation.',
    cta: 'Finish the tour →',
    next_screen: 'reputation',
    spotlight: '[data-tour="pricing-power"]',
  },
  {
    screen: 'reputation',
    title: 'That\'s INNtelligence',
    body: 'Pricing intelligence built for boutique inns, not hotel chains. Built around how your guests actually decide — and how your competitors actually price.',
    cta: '',
  },
]

export default function DemoWalkthrough({ open, onClose }: Props) {
  const [step, setStep] = useState(0)
  const [spotlight, setSpotlight] = useState<DOMRect | null>(null)
  const s = STEPS[step]
  const isLast = step === STEPS.length - 1

  // Navigate to the step's screen on advance
  useEffect(() => {
    if (!open) return
    window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: s.screen }))
  }, [open, step, s.screen])

  // Recompute spotlight rect after navigation settles
  useEffect(() => {
    if (!open) { setSpotlight(null); return }
    if (!s.spotlight) { setSpotlight(null); return }
    const t = setTimeout(() => {
      const el = document.querySelector(s.spotlight!)
      if (el) {
        const r = (el as HTMLElement).getBoundingClientRect()
        setSpotlight(r)
        // Scroll into view if needed
        ;(el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else {
        setSpotlight(null)
      }
    }, 250)
    return () => clearTimeout(t)
  }, [open, step, s.spotlight])

  if (!open) return null

  function advance() {
    if (s.next_screen) {
      window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: s.next_screen }))
    }
    setStep(step + 1)
  }

  // Position tooltip: bottom-right by default; if spotlight present, near it
  const tooltipStyle: React.CSSProperties = spotlight
    ? {
        position: 'fixed',
        top:  Math.min(window.innerHeight - 280, spotlight.bottom + 14),
        left: Math.max(20, Math.min(window.innerWidth - 460, spotlight.left)),
        width: 440,
      }
    : { position: 'fixed', bottom: 30, right: 30, width: 460 }

  return (
    <>
      {/* Backdrop with cutout */}
      <div className="fixed inset-0 z-40 pointer-events-none" aria-hidden>
        {spotlight ? (
          <svg className="w-full h-full">
            <defs>
              <mask id="tour-mask">
                <rect width="100%" height="100%" fill="white" />
                <rect
                  x={spotlight.left - 8}  y={spotlight.top - 8}
                  width={spotlight.width + 16} height={spotlight.height + 16}
                  rx={10} fill="black"
                />
              </mask>
            </defs>
            <rect width="100%" height="100%" fill="rgba(26, 58, 92, 0.65)" mask="url(#tour-mask)" />
            <rect
              x={spotlight.left - 8} y={spotlight.top - 8}
              width={spotlight.width + 16} height={spotlight.height + 16}
              rx={10} fill="none"
              stroke="#A07830" strokeWidth={3}
              style={{ filter: 'drop-shadow(0 0 12px rgba(160, 120, 48, 0.8))' }}
            />
          </svg>
        ) : (
          <div className="absolute inset-0 bg-navy/60" />
        )}
      </div>

      {/* Tooltip card */}
      <div className="z-50 bg-white rounded-xl shadow-2xl border-2 border-gold pointer-events-auto" style={tooltipStyle}>
        <div className="bg-gold text-white px-4 py-2 flex items-center justify-between rounded-t-xl">
          <div className="text-[10px] uppercase tracking-[3px] font-bold">
            Walk-through · {step + 1} of {STEPS.length}
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="px-5 py-4">
          <h2 className="font-bold text-navy text-lg">{s.title}</h2>
          <p className="text-slate-700 text-sm mt-1.5 leading-relaxed">{s.body}</p>
        </div>
        <div className="px-4 py-3 bg-cream border-t border-slate-200 flex items-center justify-between rounded-b-xl">
          <div className="flex items-center gap-1">
            {STEPS.map((_, i) => (
              <span key={i} className={`w-1.5 h-1.5 rounded-full ${
                i === step ? 'bg-gold' : i < step ? 'bg-sage' : 'bg-slate-300'
              }`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button onClick={() => setStep(s => s - 1)}
                className="px-2 py-1 text-xs font-semibold text-slate-500 hover:text-navy">← Back</button>
            )}
            <button onClick={onClose} className="px-2 py-1 text-xs text-slate-400 hover:text-navy">Exit tour</button>
            {!isLast ? (
              <button onClick={advance}
                className="px-3 py-1.5 bg-navy text-white text-xs font-bold rounded hover:bg-navy-light">
                {s.cta || 'Next →'}
              </button>
            ) : (
              <FinishActions onClose={onClose} />
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function FinishActions({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex gap-2">
      <a href="mailto:jwilliams8559@gmail.com?subject=Schedule a demo call"
         onClick={onClose}
         className="px-3 py-1.5 bg-white border border-navy text-navy text-xs font-bold rounded hover:bg-navy/5">
        Schedule a Demo Call
      </a>
      <button onClick={onClose}
        className="px-3 py-1.5 bg-gold text-white text-xs font-bold rounded hover:bg-gold-dark">
        Start Free Trial — No Credit Card
      </button>
    </div>
  )
}

import { useState } from 'react'

interface Props { open: boolean; onClose: () => void }

interface Step {
  title: string
  body: string
  hint?: string
}

const STEPS: Step[] = [
  {
    title: 'Welcome to the Rate Intelligence Center',
    body: 'This is the demo environment for The Gracious Collection — built around the Anchorage 1770 Inn, Beaufort SC, our founding member property.',
    hint: 'A full year of real occupancy data, a real competitor set, and live pricing across 4 room types over the next 90 days.',
  },
  {
    title: '90-Day Rate Calendar',
    body: 'Every cell is one room × one date with its recommended rate, demand score, and status. Green band = high demand. Orange dot = pending approval.',
    hint: 'The first thing you see at the top: the gold Water Festival banner showing peak rates and a 3-night minimum.',
  },
  {
    title: 'Click any cell for the recommendation detail',
    body: 'The right drawer shows demand score with attribution, comp set rates, OTA commission math, length-of-stay pricing ladder, and the "Approve & Publish" action.',
    hint: 'The Water Festival cells (Jul 17–26) show Waterfront Suite jumping from $378 → $535 with a 3-night minimum — driven by sold-out competitors.',
  },
  {
    title: 'Approve and publish to 7 OTAs in one click',
    body: 'When an innkeeper clicks "Approve & Publish", the rate flows through SiteMinder XML in under 200ms to Booking.com, Expedia, Airbnb, VRBO, Hotels.com, Trip.com, and Agoda.',
    hint: '"Approve All" handles 360 recommendations in 2.3 seconds — grouped by room type for bulk efficiency.',
  },
  {
    title: 'Autopilot',
    body: 'For experienced operators, autopilot publishes within limits they set: max ±15% change, min 75 confidence, active hours, daily cap. Every auto-publish writes an audit row + dashboard alert.',
    hint: 'Today\'s autopilot for the Waterfront Suite: 3 rates published, top win +$157 (Jul 20 went from $378 → $535).',
  },
  {
    title: 'Demand alerts on the sidebar bell',
    body: 'Surge, competitor drop, low occupancy, festival, gap night, autopilot publish. Each alert is severity-coded and de-duplicated so you never get spam.',
    hint: 'The bell currently shows 16 unread alerts — all real, derived from competitor_rates and rate_recommendations.',
  },
  {
    title: 'Guest CRM and demand-triggered campaigns',
    body: '15 guest profiles auto-segmented into VIP/Local/Lapsed/New/Anniversary. When the system spots a soft window 21+ days out, it drafts a campaign targeting Lapsed + VIP automatically.',
    hint: '10 campaigns drafted from this week\'s forecast, including the Aug 6–12 quiet window with a starting-from $250 hook.',
  },
  {
    title: 'Management Console',
    body: 'The strategic command center: portfolio metrics vs LY, MRR/ARR (currently $0 — honest framing for pre-revenue), market intelligence, acquisition opportunity scoring across new markets like Savannah.',
    hint: 'This is the view Jim uses to manage the whole Gracious Collection as it grows.',
  },
]

export default function DemoWalkthrough({ open, onClose }: Props) {
  const [step, setStep] = useState(0)
  if (!open) return null

  const s = STEPS[step]
  const isLast = step === STEPS.length - 1

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-navy/60" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-2xl max-w-lg mx-4 overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="bg-gold text-white px-5 py-2 flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-[3px] font-bold">
            Demo Walk-Through · {step + 1} of {STEPS.length}
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white">×</button>
        </div>

        <div className="px-6 py-5">
          <h2 className="font-bold text-navy text-xl mb-2">{s.title}</h2>
          <p className="text-slate-700 text-sm leading-relaxed">{s.body}</p>
          {s.hint && (
            <div className="mt-3 bg-cream rounded-lg p-3 border border-gold/30 text-xs text-slate-600">
              <span className="text-gold font-bold uppercase tracking-wider text-[10px]">★ Insight</span>
              <div className="mt-1">{s.hint}</div>
            </div>
          )}
        </div>

        <div className="px-5 py-3 bg-cream border-t border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-1">
            {STEPS.map((_, i) => (
              <span key={i} className={`w-1.5 h-1.5 rounded-full ${
                i === step ? 'bg-navy' : i < step ? 'bg-sage' : 'bg-slate-300'
              }`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button onClick={() => setStep(s => s - 1)}
                className="px-3 py-1.5 text-sm font-semibold text-slate-500 hover:text-navy">
                ← Back
              </button>
            )}
            {!isLast ? (
              <button onClick={() => setStep(s => s + 1)}
                className="px-4 py-1.5 bg-navy text-white text-sm font-semibold rounded-lg hover:bg-navy-dark">
                Next →
              </button>
            ) : (
              <button onClick={onClose}
                className="px-4 py-1.5 bg-sage text-white text-sm font-semibold rounded-lg hover:bg-sage-dark">
                ✓ Got it
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

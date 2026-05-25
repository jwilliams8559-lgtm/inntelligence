import { useState, useEffect } from 'react'
import { getGapNight } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const URGENCY = {
  immediate: { tone: 'rose', label: 'Immediate' },
  soon:      { tone: 'gold', label: 'Soon' },
  planning:  { tone: 'gray', label: 'Planning' },
}

export default function GapNight() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getGapNight().then(setD).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!d) return <LoadingSpinner label="Detecting gap nights…" />

  const gaps = d.gap_nights || []
  const immediate = gaps.filter((g) => g.urgency === 'immediate')
  const order = { immediate: 0, soon: 1, planning: 2 }
  const sorted = [...gaps].sort((a, b) => (order[a.urgency] - order[b.urgency]) || a.date.localeCompare(b.date))
  const shown = sorted.slice(0, 30)

  return (
    <div>
      <ScreenHeader title="Gap Night Optimizer" subtitle="Orphan 1–2 night gaps between bookings · fill them before they go empty" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Recoverable Revenue" value={usd(d.potential_recovery)} sub="across all gaps" accent />
        <StatCard label="Gap Nights" value={d.gap_count} sub="next 60 days" />
        <StatCard label="Immediate" value={immediate.length} sub="within 14 days" />
        <StatCard label="Min-Stay Rules" value={d.min_stay_count} sub="recommended" />
      </div>

      <Card title={`Gap Fill Opportunities (showing ${shown.length} of ${gaps.length})`}>
        <div className="space-y-2">
          {shown.map((g, i) => {
            const u = URGENCY[g.urgency] || URGENCY.planning
            return (
              <div key={i} className="flex items-center gap-4 rounded-lg border border-gray-200 p-3 hover:bg-gray-50">
                <div className="text-center shrink-0 w-20">
                  <div className="text-navy font-bold text-sm">{g.date.slice(5)}</div>
                  <div className="text-[10px] text-gray-400">{g.gap_length_nights}-night gap</div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-navy text-sm">{g.room_name}</div>
                  <div className="text-[11px] text-gray-500 truncate">{g.recommended_action}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-gold font-extrabold">{usd(g.recommended_price)}</div>
                  <Pill tone={u.tone}>{u.label}</Pill>
                </div>
              </div>
            )
          })}
          {gaps.length === 0 && <p className="text-sm text-gray-400">No gap nights detected — calendar is well-packed.</p>}
        </div>
      </Card>
    </div>
  )
}

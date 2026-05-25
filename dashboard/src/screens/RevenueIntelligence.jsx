import { useState, useEffect } from 'react'
import { usePrices } from '../context/PriceContext'
import { getRevenueIntelligence } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, ExportButton, LastUpdated, exportToCsv, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const fmtDay = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
const PRIO = { high: 'rose', medium: 'gold', low: 'gray' }

export default function RevenueIntelligence() {
  const { lastUpdated } = usePrices()
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getRevenueIntelligence().then(setD).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!d) return <LoadingSpinner label="Analyzing revenue opportunities…" />

  const onExport = () => exportToCsv('gap-nights', d.gap_nights, [
    { key: 'date', label: 'Date' }, { key: 'room_name', label: 'Room' },
    { key: 'gap_length_nights', label: 'Gap Nights' }, { key: 'recommended_price', label: 'Recommended Price' },
    { key: 'urgency', label: 'Urgency' }, { key: 'recommended_action', label: 'Action' },
  ])

  return (
    <div>
      <ScreenHeader
        title="Revenue Intelligence"
        subtitle="Gap fills, weekend optimization, and AI-driven actions to capture more revenue right now"
        right={<div className="flex items-center gap-2"><ExportButton onClick={onExport} label="Export Gaps" /><LastUpdated at={lastUpdated} /></div>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Recoverable Revenue" value={usd(d.potential_recovery)} sub="across all gaps" accent />
        <StatCard label="Gap Nights" value={d.gap_count} sub="next 60 days" />
        <StatCard label="Weekend Fixes" value={d.fri_sat.length} sub="Fri/Sat opportunities" />
        <StatCard label="AI Actions" value={d.ai_recommendations.length} sub="ready now" />
      </div>

      {/* AI Revenue Recommendations */}
      <Card title="🧠 AI Revenue Recommendations — Top Actions Right Now" className="mb-6">
        <div className="space-y-2">
          {d.ai_recommendations.map((r, i) => (
            <div key={i} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 hover:bg-gray-50">
              <Pill tone={PRIO[r.priority] || 'gray'}>{r.priority}</Pill>
              <div className="flex-1 min-w-0">
                <span className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold mr-2">{r.category}</span>
                <span className="text-sm text-navy">{r.action}</span>
              </div>
              {r.impact > 0 && <span className="text-emerald-700 font-bold text-sm shrink-0">+{usd(r.impact)}</span>}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Fri/Sat solver */}
        <Card title="📅 Friday / Saturday Problem Solver">
          {d.fri_sat.length === 0 ? <p className="text-sm text-gray-400">No weekend gaps detected.</p> : (
            <div className="space-y-3">
              {d.fri_sat.map((f, i) => (
                <div key={i} className="rounded-lg border border-gray-200 p-3">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-navy text-sm">{fmtDay(f.saturday)} · {f.room}</div>
                    <Pill tone="gold">{f.context}</Pill>
                  </div>
                  <div className="text-[11px] text-gray-500 mt-0.5">Fill Friday {fmtDay(f.friday)} to capture the full weekend</div>
                  <ul className="mt-2 space-y-1">
                    {f.recommendations.map((rec, j) => (
                      <li key={j} className="text-[12px] text-gray-700 flex gap-2"><span className="text-gold">◆</span>{rec}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Min-stay optimizer */}
        <Card title="🛏️ Minimum-Stay Optimizer">
          {d.min_stay.length === 0 ? <p className="text-sm text-gray-400">No minimum-stay rules recommended.</p> : (
            <div className="space-y-2">
              {d.min_stay.map((m, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3">
                  <div className="text-center shrink-0 w-12">
                    <div className="text-2xl font-extrabold text-gold">{m.recommended_min_stay}</div>
                    <div className="text-[9px] text-gray-400">nights</div>
                  </div>
                  <div className="min-w-0">
                    <div className="font-semibold text-navy text-sm">{fmtDay(m.date)}</div>
                    <div className="text-[11px] text-gray-500">{m.reason}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Customer Experience */}
      <Card title="💡 Customer Experience Recommendations" className="mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {d.cx_recommendations.map((c, i) => (
            <div key={i} className="flex gap-2 rounded-lg bg-gold/5 border border-gold/20 p-3">
              <span className="text-lg">{c.icon}</span>
              <span className="text-[12px] text-gray-700">{c.text}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Gap night detail */}
      <Card title={`🔍 Gap Night Detector — ${d.gap_count} orphan nights`}>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {d.gap_nights.slice(0, 25).map((g, i) => {
            const tone = g.urgency === 'immediate' ? 'rose' : g.urgency === 'soon' ? 'gold' : 'gray'
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
                  <Pill tone={tone}>{g.urgency}</Pill>
                </div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

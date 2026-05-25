import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import { getEventsDetail } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, Segmented, YoYToggle, LastUpdated, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const VIEWS = [
  { value: 'week', label: 'This Week' },
  { value: 'month', label: 'This Month' },
  { value: 'quarter', label: 'This Quarter' },
  { value: '6mo', label: 'Next 6 Months' },
]
const VIEW_DAYS = { week: 7, month: 30, quarter: 90, '6mo': 180 }

export default function Events() {
  const { lastUpdated } = usePrices()
  const [view, setView] = useState('month')
  const [yoy, setYoy] = useState(false)
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const days = VIEW_DAYS[view]

  useEffect(() => {
    let live = true; setData(null); setErr(null)
    getEventsDetail(days).then((d) => live && setData(d)).catch((e) => live && setErr(e.message))
    return () => { live = false }
  }, [days])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading events…" />

  const events = data.events
  const monthGroups = Object.entries(events.reduce((acc, e) => {
    (acc[e.month] ||= []).push(e); return acc
  }, {}))
  const peak = events.reduce((m, e) => (e.impact_pct > (m?.impact_pct ?? -1) ? e : m), null)
  const chart = [...events].sort((a, b) => b.est_revenue_lift - a.est_revenue_lift).slice(0, 8)
    .map((e) => ({ name: e.event.length > 16 ? e.event.slice(0, 15) + '…' : e.event, lift: e.est_revenue_lift }))

  return (
    <div>
      <ScreenHeader
        title="Events Intelligence"
        subtitle="Beaufort demand calendar · pricing impact and revenue lift, automatically detected"
        right={<div className="flex items-center gap-2 flex-wrap"><YoYToggle on={yoy} onChange={setYoy} /><LastUpdated at={lastUpdated} /></div>}
      />

      <div className="mb-4"><Segmented options={VIEWS} value={view} onChange={setView} /></div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Events in Window" value={data.event_count} sub={`${days} days`} accent />
        <StatCard label="Total Revenue Lift" value={usd(data.total_lift)} sub="from event pricing" />
        <StatCard label="Biggest Impact" value={peak ? `+${peak.impact_pct}%` : '—'} sub={peak?.event || ''} />
        <StatCard label="Next Event" value={events[0]?.display || '—'} sub={events[0] ? `${events[0].days_away}d away` : ''} />
      </div>

      <Card title="Revenue Lift by Event" className="mb-6">
        {chart.length === 0 ? <p className="text-sm text-gray-400">No events in window.</p> : (
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={chart} layout="vertical" margin={{ top: 4, right: 16, left: 40, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
              <XAxis type="number" tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} stroke="#94a3b8" width={110} />
              <Tooltip formatter={(v) => [usd(v), 'Est. revenue lift']} />
              <Bar dataKey="lift" fill="#c9a84c" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>

      {events.length === 0 ? (
        <p className="text-sm text-gray-400">No upcoming events in this window.</p>
      ) : view === '6mo' ? (
        <div className="space-y-5">
          {monthGroups.map(([month, evts]) => (
            <div key={month}>
              <div className="flex items-center gap-3 mb-2">
                <h3 className="text-sm font-bold text-navy">{month}</h3>
                <div className="flex-1 h-px bg-gray-200" />
                <span className="text-[11px] text-gray-400">{evts.length} event{evts.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="space-y-3">{evts.map((e, i) => <EventCard key={i} e={e} yoy={yoy} />)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">{events.map((e, i) => <EventCard key={i} e={e} yoy={yoy} />)}</div>
      )}
    </div>
  )
}

function EventCard({ e, yoy }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-navy">{e.event}</span>
            <Pill tone="gold">+{e.impact_pct}%</Pill>
          </div>
          <div className="text-[11px] text-gray-500 mt-0.5">
            {e.display} · {e.days_away}d away · {e.impacted_days} impacted night{e.impacted_days !== 1 ? 's' : ''}
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-extrabold text-emerald-700">+{usd(e.est_revenue_lift)}</div>
          <div className="text-[10px] text-gray-400">est. revenue lift</div>
        </div>
      </div>
      <p className="text-[12px] text-gray-700 mt-2 leading-snug"><span className="font-semibold text-navy">Action:</span> {e.recommended_action}</p>
      {yoy && (
        <div className="text-[11px] text-gray-500 mt-2 rounded bg-gray-50 px-3 py-1.5">
          <span className="font-semibold">Last year:</span> +{usd(e.last_year.revenue_lift)} lift · {e.last_year.note}
        </div>
      )}
    </div>
  )
}

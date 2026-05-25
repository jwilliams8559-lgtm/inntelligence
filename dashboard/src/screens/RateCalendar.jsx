import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import { getRateCalendar, getRoomRate } from '../api/client'
import {
  ScreenHeader, Card, StatCard, StatusPill, Pill, ConfidencePill,
  Segmented, YoYToggle, ExportButton, LastUpdated, exportToCsv, usd,
} from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const RANGES = [
  { value: 7, label: 'Next Week' },
  { value: 14, label: 'Next 2 Weeks' },
  { value: 30, label: 'Next Month' },
  { value: 90, label: 'Next 90 Days' },
]
const TIER_LABELS = {
  waterfront: 'Waterfront', water_view: 'Water View', garden: 'Garden',
  carriage_house: 'Carriage House', signature_suite: 'Signature', grand_parlor: 'Grand Parlor',
}
const TIER_ORDER = ['waterfront', 'water_view', 'garden', 'carriage_house', 'signature_suite', 'grand_parlor']

const fmtDay = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
const fmtFull = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

export default function RateCalendar() {
  const { lastUpdated } = usePrices()
  const [days, setDays] = useState(14)
  const [cat, setCat] = useState('all')
  const [yoy, setYoy] = useState(false)
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [sel, setSel] = useState(null)          // {roomId, roomName, date}
  const [detail, setDetail] = useState(null)
  const [detailErr, setDetailErr] = useState(null)
  const [decisions, setDecisions] = useState({}) // key -> {action:'accepted'|'override', rate}

  useEffect(() => {
    let live = true
    setData(null); setErr(null)
    getRateCalendar(days).then((d) => live && setData(d)).catch((e) => live && setErr(e.message))
    return () => { live = false }
  }, [days])

  useEffect(() => {
    if (!sel) return
    let live = true
    setDetail(null); setDetailErr(null)
    getRoomRate(sel.roomId, sel.date).then((d) => live && setDetail(d)).catch((e) => live && setDetailErr(e.message))
    return () => { live = false }
  }, [sel])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading rate calendar…" />

  const tiersPresent = TIER_ORDER.filter((t) => data.rooms.some((r) => r.tier === t))
  const catOptions = [{ value: 'all', label: 'All' }, ...tiersPresent.map((t) => ({ value: t, label: TIER_LABELS[t] }))]
  const rooms = cat === 'all' ? data.rooms : data.rooms.filter((r) => r.tier === cat)

  const dates = rooms[0]?.days.map((d) => d.date) || []
  const allRates = rooms.flatMap((r) => r.days.map((d) => d.rate))
  const avgRate = allRates.length ? allRates.reduce((a, b) => a + b, 0) / allRates.length : 0
  const premiumCells = rooms.flatMap((r) => r.days).filter((d) => d.status === 'premium').length
  const eventCells = rooms.flatMap((r) => r.days).filter((d) => d.active_events.length).length

  const trend = dates.map((dt, i) => {
    const col = rooms.map((r) => r.days[i]?.rate).filter(Boolean)
    return { date: dt, label: fmtDay(dt), rate: Math.round(col.reduce((a, b) => a + b, 0) / (col.length || 1)) }
  })

  const onExport = () => {
    const rows = rooms.flatMap((r) => r.days.map((d) => ({
      room: r.room_name, tier: TIER_LABELS[r.tier] || r.tier, date: d.date,
      day: d.day_of_week, recommended_rate: d.rate, last_year_rate: d.last_year_rate,
      status: d.status, confidence: d.confidence, events: d.active_events.join('; '),
    })))
    exportToCsv(`rate-calendar-${days}d`, rows, [
      { key: 'room', label: 'Room' }, { key: 'tier', label: 'Tier' }, { key: 'date', label: 'Date' },
      { key: 'day', label: 'Day' }, { key: 'recommended_rate', label: 'Recommended Rate' },
      { key: 'last_year_rate', label: 'Last Year Rate' }, { key: 'status', label: 'Status' },
      { key: 'confidence', label: 'Confidence' }, { key: 'events', label: 'Events' },
    ])
  }

  const cellTone = (s) => s === 'premium' ? 'bg-emerald-50 text-emerald-800'
    : s === 'discount' ? 'bg-rose-50 text-rose-700' : 'text-navy'

  return (
    <div>
      <ScreenHeader
        title="Rate Calendar"
        subtitle={`${data.property_name} · AI-recommended nightly rates, every room, every day`}
        right={<div className="flex items-center gap-2 flex-wrap"><YoYToggle on={yoy} onChange={setYoy} /><ExportButton onClick={onExport} /><LastUpdated at={lastUpdated} /></div>}
      />

      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <Segmented options={catOptions} value={cat} onChange={setCat} />
        <Segmented options={RANGES} value={days} onChange={setDays} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Avg Recommended" value={usd(avgRate)} sub={`${rooms.length} rooms · ${days}d`} accent />
        <StatCard label="Premium Cells" value={premiumCells} sub="above rack mid" />
        <StatCard label="Event Nights" value={eventCells} sub="demand driver active" />
        <StatCard label="Date Range" value={`${days}d`} sub={dates.length ? `${fmtDay(dates[0])}–${fmtDay(dates[dates.length - 1])}` : ''} />
      </div>

      <Card title="Average Rate Outlook" className="mb-6">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={trend} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
            <defs>
              <linearGradient id="rateFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#c9a84c" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#c9a84c" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={Math.max(0, Math.floor(trend.length / 12))} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${v}`} domain={['dataMin - 20', 'dataMax + 20']} />
            <Tooltip formatter={(v) => [usd(v), 'Avg rate']} labelStyle={{ color: '#0a2342' }} />
            <Area type="monotone" dataKey="rate" stroke="#0a2342" strokeWidth={2} fill="url(#rateFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Rate Grid — click any cell for pricing detail">
        <div className="overflow-x-auto">
          <table className="text-xs border-separate" style={{ borderSpacing: 0 }}>
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-white text-left px-2 py-2 font-semibold text-navy border-b border-gray-200">Room</th>
                {dates.map((dt) => {
                  const wknd = rooms[0]?.days.find((d) => d.date === dt)?.is_weekend
                  return (
                    <th key={dt} className={`px-2 py-2 text-center font-semibold border-b border-gray-200 whitespace-nowrap ${wknd ? 'text-gold-dark' : 'text-gray-500'}`}>
                      {fmtDay(dt)}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.room_id} className="hover:bg-gray-50/50">
                  <td className="sticky left-0 z-10 bg-white px-2 py-1.5 font-medium text-navy whitespace-nowrap border-b border-gray-100">
                    <span className="mr-1">{r.tier_icon}</span>{r.room_name}
                  </td>
                  {r.days.map((d) => {
                    const key = `${r.room_id}|${d.date}`
                    const dec = decisions[key]
                    return (
                      <td key={d.date} className={`px-1 py-1 text-center border-b border-gray-100 ${d.is_weekend ? 'bg-gold/5' : ''}`}>
                        <button
                          onClick={() => setSel({ roomId: r.room_id, roomName: r.room_name, date: d.date })}
                          className={`relative w-full rounded px-1.5 py-1 font-semibold hover:ring-2 hover:ring-gold transition ${cellTone(d.status)} ${dec ? 'ring-1 ring-emerald-400' : ''}`}
                          title={`${r.room_name} · ${fmtFull(d.date)}`}
                        >
                          {usd(dec?.rate ?? d.rate)}
                          {yoy && <span className="block text-[9px] text-gray-400 font-normal">ly {usd(d.last_year_rate)}</span>}
                          {d.active_events.length > 0 && <span className="absolute top-0 right-0.5 text-[8px]">🎉</span>}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-4 mt-3 text-[11px] text-gray-500">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-50 border border-emerald-200" /> premium</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-white border border-gray-200" /> at rack</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-rose-50 border border-rose-200" /> discount</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-gold/10 border border-gold/30" /> weekend</span>
          <span>🎉 event night</span>
        </div>
      </Card>

      {sel && (
        <DetailPanel
          sel={sel} detail={detail} detailErr={detailErr} yoy={yoy}
          decision={decisions[`${sel.roomId}|${sel.date}`]}
          onClose={() => setSel(null)}
          onAccept={(rate) => setDecisions((m) => ({ ...m, [`${sel.roomId}|${sel.date}`]: { action: 'accepted', rate } }))}
          onOverride={(rate) => setDecisions((m) => ({ ...m, [`${sel.roomId}|${sel.date}`]: { action: 'override', rate } }))}
        />
      )}
    </div>
  )
}

function DetailPanel({ sel, detail, detailErr, yoy, decision, onClose, onAccept, onOverride }) {
  const [override, setOverride] = useState('')
  const delta = detail ? detail.rate - detail.last_year_rate : 0

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="bg-navy text-white px-5 py-4 flex items-start justify-between sticky top-0">
          <div>
            <div className="font-bold text-lg">{sel.roomName}</div>
            <div className="text-gold-light text-sm">{fmtFull(sel.date)}</div>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white text-xl leading-none">✕</button>
        </div>

        {detailErr && <div className="p-5"><ErrorBanner message={detailErr} /></div>}
        {!detail && !detailErr && <div className="p-5"><LoadingSpinner label="Loading detail…" /></div>}

        {detail && (
          <div className="p-5 space-y-5">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold">Recommended Rate</div>
                <div className="text-4xl font-extrabold text-gold">{usd(decision?.rate ?? detail.rate)}</div>
                {decision && <div className="text-[11px] text-emerald-600 font-semibold mt-0.5">✓ {decision.action === 'accepted' ? 'Accepted' : 'Overridden'}</div>}
              </div>
              <ConfidencePill level={detail.confidence} />
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <Box label="Rack Range" value={`${usd(detail.rack_low)}–${usd(detail.rack_high)}`} />
              <Box label="Rate Ceiling" value={usd(detail.rack_ceiling)} sub="rack_high ×1.40" />
              <Box label="Last Year" value={usd(detail.last_year_rate)} sub={`${delta >= 0 ? '▲' : '▼'} ${usd(Math.abs(delta))} YoY`} />
              <Box label="vs Comp Set" value={`${detail.rate_vs_comp_pct >= 0 ? '+' : ''}${detail.rate_vs_comp_pct}%`} sub={`comp avg ${usd(detail.competitor_avg)}`} />
            </div>

            <div>
              <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Why this rate</div>
              <p className="text-sm text-gray-700 leading-snug">{detail.reasoning}</p>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <Mini label="Event ×" value={detail.event_multiplier} />
              <Mini label="Demand ×" value={detail.effective_demand} />
              <Mini label="Season" value={detail.seasonal_index} />
            </div>

            {detail.active_events.length > 0 && (
              <div className="rounded-lg bg-gold/10 border border-gold/30 p-3 text-sm">
                <span className="font-semibold text-navy">🎉 Events:</span> {detail.active_events.join(', ')}
              </div>
            )}

            <div>
              <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Confidence</div>
              <p className="text-sm text-gray-700">{detail.confidence_reason}</p>
            </div>

            <div>
              <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-2">Comparable Competitor Rates</div>
              <div className="space-y-1">
                {detail.competitor_rates.map((c) => (
                  <div key={c.name} className="flex justify-between text-sm border-b border-gray-100 py-1">
                    <span className="text-gray-600">{c.name}</span>
                    <span className="font-semibold text-navy">{usd(c.rate)}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="border-t border-gray-200 pt-4 space-y-3">
              <button
                onClick={() => onAccept(detail.rate)}
                className="w-full bg-navy text-white font-semibold py-2.5 rounded-lg hover:bg-navy-light transition-colors"
              >
                ✓ Accept {usd(detail.rate)}
              </button>
              <div className="flex gap-2">
                <input
                  type="number" value={override} onChange={(e) => setOverride(e.target.value)}
                  placeholder="Override rate"
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                />
                <button
                  onClick={() => { if (override) { onOverride(Number(override)); setOverride('') } }}
                  className="px-4 bg-gold text-navy font-semibold rounded-lg hover:bg-gold-light transition-colors"
                >
                  Override
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const Box = ({ label, value, sub }) => (
  <div className="rounded-lg border border-gray-200 p-3">
    <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">{label}</div>
    <div className="font-bold text-navy">{value}</div>
    {sub && <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>}
  </div>
)
const Mini = ({ label, value }) => (
  <div className="rounded-lg bg-gray-50 py-2">
    <div className="text-sm font-bold text-navy">{value}</div>
    <div className="text-[10px] text-gray-400">{label}</div>
  </div>
)

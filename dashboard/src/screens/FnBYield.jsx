import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import { getFnB } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, YoYToggle, LastUpdated, usd, usd2 } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function FnBYield() {
  const { lastUpdated } = usePrices()
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [yoy, setYoy] = useState(false)
  useEffect(() => { getFnB().then(setD).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!d) return <LoadingSpinner label="Loading F&B yield…" />

  const s = d.summary || {}
  const lbl = d.labels || { restaurant: 'Restaurant', rooftop_bar: 'Rooftop Bar' }
  const rdow = (d.restaurant_dow || []).map((r) => ({ ...r, day3: r.day.slice(0, 3) }))
  const bdow = (d.rooftop_dow || []).map((r) => ({ ...r, day3: r.day.slice(0, 3) }))

  return (
    <div>
      <ScreenHeader
        title="F&B Yield Management"
        subtitle={`${lbl.restaurant} · ${lbl.rooftop_bar} · the only platform that prices your restaurant`}
        right={<div className="flex items-center gap-2"><YoYToggle on={yoy} onChange={setYoy} /><LastUpdated at={lastUpdated} /></div>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3 mb-6">
        <StatCard label="Monthly F&B" value={usd(s.monthly_revenue)} sub="total" accent />
        <StatCard label={lbl.restaurant} value={usd(s.restaurant_monthly)} sub="/ month" />
        <StatCard label={lbl.rooftop_bar} value={usd(s.bar_monthly)} sub="/ month" />
        <StatCard label="RevPASH" value={usd2(s.revpash)} sub="/ seat-hr" />
        <StatCard label="Avg Check" value={usd2(s.avg_check)} sub="/ cover" />
        <StatCard label="Monthly Covers" value={(s.total_monthly_covers || 0).toLocaleString()} sub="covers" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card title={`${lbl.restaurant} — All 7 Days`}>
          <DowChart data={rdow} fill="#c9a84c" yoy={yoy} />
          <DowTable rows={rdow} yoy={yoy} />
        </Card>
        <Card title={`${lbl.rooftop_bar} — All 7 Days`}>
          <DowChart data={bdow} fill="#0a2342" yoy={yoy} />
          <DowTable rows={bdow} yoy={yoy} />
        </Card>
      </div>

      <Card title="Recommendations to Grow F&B Revenue">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {(d.recommendations || []).map((rec, i) => {
            const hi = (rec.priority || '').toUpperCase() === 'HIGH'
            return (
              <div key={i} className={`rounded-lg border-l-4 p-4 ${hi ? 'border-rose-400 bg-rose-50' : 'border-gold bg-gold/5'}`}>
                <div className="flex items-center justify-between">
                  <Pill tone={hi ? 'navy' : 'gold'}>{rec.priority}</Pill>
                  <span className="text-xs font-bold text-emerald-700">{rec.lift_label}</span>
                </div>
                <div className="font-semibold text-navy text-sm mt-2">{rec.title}</div>
                <div className="text-[11px] text-gray-500 mt-0.5">{rec.date}</div>
                <p className="text-[12px] text-gray-700 mt-1.5 leading-snug">{rec.action}</p>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

function DowChart({ data, fill, yoy }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 6, right: 8, left: -14, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
        <XAxis dataKey="day3" tick={{ fontSize: 10 }} stroke="#94a3b8" />
        <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
        <Tooltip formatter={(v, n) => [usd(v), n]} />
        {yoy && <Legend wrapperStyle={{ fontSize: 10 }} />}
        {yoy && <Bar dataKey="ly_revenue" name="Last year" fill="#c7d2dd" radius={[4, 4, 0, 0]} />}
        <Bar dataKey="revenue" name="This year" fill={fill} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function DowTable({ rows, yoy }) {
  return (
    <table className="w-full text-xs mt-3">
      <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
        <tr>
          <th className="text-left py-1">Day</th>
          <th className="text-right">Covers</th>
          <th className="text-right">Avg Check</th>
          <th className="text-right">Revenue</th>
          {yoy && <th className="text-right">YoY</th>}
          <th className="text-right">Occ</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          if (r.closed) {
            return (
              <tr key={r.day} className="border-t border-gray-100 text-gray-300">
                <td className="py-1.5 font-medium text-gray-400">{r.day}</td>
                <td className="text-right" colSpan={yoy ? 5 : 4}>— closed —</td>
              </tr>
            )
          }
          const gap = r.occ_pct < 55
          const yoyDelta = r.ly_revenue ? Math.round((r.revenue - r.ly_revenue) / r.ly_revenue * 100) : 0
          return (
            <tr key={r.day} className={`border-t border-gray-100 ${gap ? 'bg-amber-50' : ''}`}>
              <td className="py-1.5 font-medium text-navy">{r.day}</td>
              <td className="text-right text-gray-600">{r.covers}</td>
              <td className="text-right text-gray-600">{usd(r.avg_check)}</td>
              <td className="text-right text-gray-700 font-medium">{usd(r.revenue)}</td>
              {yoy && <td className={`text-right font-semibold ${yoyDelta >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>{yoyDelta >= 0 ? '+' : ''}{yoyDelta}%</td>}
              <td className={`text-right font-semibold ${gap ? 'text-amber-700' : 'text-gray-500'}`}>{r.occ_pct}%</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

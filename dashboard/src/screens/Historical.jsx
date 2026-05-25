import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, ComposedChart,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import { getHistorical } from '../api/client'
import {
  ScreenHeader, Card, StatCard, YoYToggle, ExportButton, LastUpdated, exportToCsv, usd,
} from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const Delta = ({ v, pts }) => {
  const up = Number(v) >= 0
  return <span className={up ? 'text-emerald-600' : 'text-rose-600'}>{up ? '▲' : '▼'} {Math.abs(Number(v))}{pts ? ' pts' : '%'}</span>
}

export default function Historical() {
  const { lastUpdated } = usePrices()
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  const [yoy, setYoy] = useState(true)
  useEffect(() => { getHistorical().then(setD).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!d) return <LoadingSpinner label="Loading historical trends…" />

  const k = d.kpi_trend, y = k.yoy_summary
  const monthly = k.monthly_data
  const rolling = d.rolling_12mo

  const onExport = () => exportToCsv('historical-24mo', monthly, [
    { key: 'month', label: 'Month' }, { key: 'adr', label: 'ADR' },
    { key: 'occupancy', label: 'Occupancy %' }, { key: 'revpar', label: 'RevPAR' },
    { key: 'revenue', label: 'Revenue' }, { key: 'direct_pct', label: 'Direct %' },
  ])

  return (
    <div>
      <ScreenHeader
        title="Historical Performance"
        subtitle="24-month KPI trend · year-over-year, sourced from booking history"
        right={<div className="flex items-center gap-2 flex-wrap"><YoYToggle on={yoy} onChange={setYoy} /><ExportButton onClick={onExport} /><LastUpdated at={lastUpdated} /></div>}
      />

      <div className="rounded-2xl bg-navy text-white p-5 mb-6">
        <div className="text-gold-light text-xs uppercase tracking-wide font-semibold">Year over year</div>
        <div className="text-lg font-semibold mt-1">{y.headline}</div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="RevPAR Growth" value={<Delta v={y.revpar_growth_pct} />} sub="YoY" accent />
        <StatCard label="ADR Growth" value={<Delta v={y.adr_growth_pct} />} sub="YoY" />
        <StatCard label="Occupancy" value={<Delta v={y.occ_growth_pts} pts />} sub="YoY" />
        <StatCard label="Direct Bookings" value={`${k.direct_pct_now}%`} sub={`vs ${k.direct_pct_prior}% prior year`} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="text-xs uppercase tracking-wide text-emerald-700 font-semibold">Best Month Ever</div>
          <div className="text-2xl font-extrabold text-navy mt-1">{d.best_month.month}</div>
          <div className="text-sm text-gray-600">RevPAR {usd(d.best_month.revpar)} · {d.best_month.occupancy}% occ · ADR {usd(d.best_month.adr)}</div>
        </div>
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="text-xs uppercase tracking-wide text-rose-700 font-semibold">Worst Month Ever</div>
          <div className="text-2xl font-extrabold text-navy mt-1">{d.worst_month.month}</div>
          <div className="text-sm text-gray-600">RevPAR {usd(d.worst_month.revpar)} · {d.worst_month.occupancy}% occ · ADR {usd(d.worst_month.adr)}</div>
        </div>
      </div>

      <Card title="ADR & RevPAR — Current vs Prior Year" className="mb-6">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={k.paired} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
            <XAxis dataKey="month_label" tick={{ fontSize: 10 }} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${v}`} />
            <Tooltip formatter={(v, n) => [usd(v), n]} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {yoy && <Bar dataKey="prior_revpar" name="Prior RevPAR" fill="#c7d2dd" radius={[3, 3, 0, 0]} />}
            <Bar dataKey="current_revpar" name="Current RevPAR" fill="#c9a84c" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Rolling 12-Month RevPAR Trend" className="mb-6">
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={rolling} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
            <XAxis dataKey="month" tick={{ fontSize: 9 }} stroke="#94a3b8" interval={2} />
            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${v}`} domain={['dataMin - 10', 'dataMax + 10']} />
            <Tooltip formatter={(v) => [usd(v), 'Rolling RevPAR']} />
            <Line type="monotone" dataKey="rolling_revpar" stroke="#0a2342" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Seasonal Pattern & Recommendation" className="mb-6">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={d.seasonal} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} stroke="#94a3b8" />
            <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${v}`} />
            <Tooltip formatter={(v) => [usd(v), 'Avg RevPAR']} />
            <Bar dataKey="avg_revpar" fill="#c9a84c" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <p className="text-sm text-gray-700 mt-3 rounded-lg bg-gold/10 border border-gold/30 p-3">{d.seasonal_recommendation}</p>
      </Card>

      <Card title="Monthly Detail — 24 Months">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
              <tr>
                <th className="text-left py-2">Month</th>
                <th className="text-right">ADR</th>
                <th className="text-right">Occ %</th>
                <th className="text-right">RevPAR</th>
                <th className="text-right">Revenue</th>
                <th className="text-right">Direct %</th>
              </tr>
            </thead>
            <tbody>
              {[...monthly].reverse().map((r) => (
                <tr key={r.month_iso} className={`border-t border-gray-100 ${r.is_current_year ? 'bg-gold/5' : ''}`}>
                  <td className="py-1.5 font-medium text-navy">{r.month}</td>
                  <td className="text-right text-gray-600">{usd(r.adr)}</td>
                  <td className="text-right text-gray-600">{r.occupancy}%</td>
                  <td className="text-right font-semibold text-navy">{usd(r.revpar)}</td>
                  <td className="text-right text-gray-600">{usd(r.revenue)}</td>
                  <td className="text-right text-gray-500">{r.direct_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { format, parseISO } from 'date-fns'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'
import DateRangePicker, { type RangeKey } from '../components/DateRangePicker'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface PairedRow {
  month_label: string
  current_adr: number;     prior_adr: number | null
  current_revpar: number;  prior_revpar: number | null
  current_occ: number;     prior_occ: number | null
  current_revenue: number; prior_revenue: number | null
}
interface YoySummary { revpar_growth_pct: number; adr_growth_pct: number; occ_growth_pts: number; headline: string }
interface TrendData {
  months_requested: number
  current_year: any[]; prior_year: any[]
  paired: PairedRow[]
  direct_pct_now: number; direct_pct_prior: number
  yoy_summary: YoySummary
}
interface CompHistory {
  history: { date: string; your_rate: number; comp_avg: number; above_market: boolean }[]
  avg_premium_pct: number; days_above_market: number; days_below_market: number
  insight: string
}

const RANGE_TO_MONTHS: Record<RangeKey, number> = {
  '7d': 1, '30d': 1, '90d': 3, '6m': 6, '12m': 12, '24m': 24, 'custom': 24,
}

export default function HistoricalScreen(_: Props) {
  return (
    <LockedFeature featureName="Historical Performance" featureKey="historical_trends"
      description="24-month KPI trends with current vs prior year overlays. Competitive positioning history. Year-over-year summary at a glance.">
      <Body />
    </LockedFeature>
  )
}

function Body() {
  const [range, setRange] = useState<RangeKey>('24m')
  const [trends, setTrends] = useState<TrendData | null>(null)
  const [comp, setComp]     = useState<CompHistory | null>(null)
  const [showMonthly, setShowMonthly] = useState(false)

  useEffect(() => {
    const months = RANGE_TO_MONTHS[range]
    fetch(`/api/historical/trends?months=${months}`).then(r => r.json()).then(setTrends)
    fetch('/api/historical/competitive-positioning?days=90').then(r => r.json()).then(setComp)
  }, [range])

  if (!trends || !comp) return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading historical data…</div>

  const y = trends.yoy_summary
  const directDelta = +(trends.direct_pct_now - trends.direct_pct_prior).toFixed(1)
  const allPositive = y.revpar_growth_pct >= 0 && y.adr_growth_pct >= 0 && y.occ_growth_pts >= 0 && directDelta >= 0
  const anyNegative = y.revpar_growth_pct < 0 || y.adr_growth_pct < 0 || y.occ_growth_pts < 0 || directDelta < 0

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 pb-20 space-y-5">
      <header className="flex items-baseline justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-navy font-bold text-xl">Historical Performance</h1>
          <p className="text-slate-500 text-sm">{trends.months_requested}-month KPI trend · current year vs prior year</p>
        </div>
        <DateRangePicker value={range} onChange={setRange} />
      </header>

      {/* Unified trend banner (Gap 4) */}
      <div className={`rounded-xl p-4 border-2 ${
        anyNegative ? 'bg-coral/5 border-coral'
        : allPositive ? 'bg-navy text-white border-navy'
                      : 'bg-amber-50 border-amber-300 text-amber-900'}`}>
        <div className={`text-[10px] uppercase tracking-[3px] font-bold ${anyNegative ? 'text-coral' : allPositive ? 'text-gold' : 'text-amber-700'}`}>
          {anyNegative ? '↓ Attention needed' : allPositive ? '↑ All trends positive' : '⚠ Mixed performance'}
        </div>
        <div className="text-base font-bold mt-1">
          ADR {y.adr_growth_pct >= 0 ? '+' : ''}{y.adr_growth_pct}% ·
          RevPAR {y.revpar_growth_pct >= 0 ? '+' : ''}{y.revpar_growth_pct}% ·
          Occupancy {y.occ_growth_pts >= 0 ? '+' : ''}{y.occ_growth_pts} pts ·
          Direct Booking {directDelta >= 0 ? '+' : ''}{directDelta} pts
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="RevPAR Growth"    value={`${y.revpar_growth_pct >= 0 ? '+' : ''}${y.revpar_growth_pct}%`} sub="vs prior year" positive={y.revpar_growth_pct >= 0} />
        <KpiCard label="ADR Growth"        value={`${y.adr_growth_pct >= 0 ? '+' : ''}${y.adr_growth_pct}%`}    sub="vs prior year" positive={y.adr_growth_pct >= 0} />
        <KpiCard label="Occupancy Growth"  value={`${y.occ_growth_pts >= 0 ? '+' : ''}${y.occ_growth_pts} pts`} sub="vs prior year" positive={y.occ_growth_pts >= 0} />
        <KpiCard label="Direct Booking %" value={`${trends.direct_pct_now}%`} sub={`was ${trends.direct_pct_prior}%`} positive={directDelta >= 0} />
      </div>

      <TrendChart title="ADR — 24 Month Trend"        data={trends.paired} currentKey="current_adr"     priorKey="prior_adr"     yFormat={(v: number) => `$${v}`} />
      <TrendChart title="RevPAR — 24 Month Trend"     data={trends.paired} currentKey="current_revpar"  priorKey="prior_revpar"  yFormat={(v: number) => `$${v}`} />
      <TrendChart title="Occupancy — 24 Month Trend"  data={trends.paired} currentKey="current_occ"     priorKey="prior_occ"     yFormat={(v: number) => `${v}%`} yDomain={[0, 100]} />

      {/* Competitive positioning */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <h2 className="font-bold text-navy">Your Rate vs Comp Set Average — Last 90 Days</h2>
        <p className="text-xs text-slate-500 mb-3">Above the comp line = premium captured. Below = rate gap.</p>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={comp.history} margin={{ top: 5, right: 15, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => format(parseISO(d), 'M/d')} interval={9} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${v}`} />
            <Tooltip formatter={(v: any, name: string) => [`$${Number(v).toFixed(0)}`, name === 'your_rate' ? 'You' : 'Comp Avg']} labelFormatter={l => format(parseISO(l as string), 'EEE MMM d')} />
            <Legend iconType="line" iconSize={10} wrapperStyle={{ fontSize: 11 }} />
            <Area type="monotone" dataKey="comp_avg"  stroke="#94A3B8" fill="#94A3B8" fillOpacity={0.15} name="Comp Avg" />
            <Area type="monotone" dataKey="your_rate" stroke="#A07830" fill="#A07830" fillOpacity={0.18} name="You" />
          </AreaChart>
        </ResponsiveContainer>
        <div className="bg-navy/5 border border-navy/20 rounded-lg p-3 mt-3 text-xs text-slate-700">
          <strong className="text-navy">{comp.days_above_market} of {comp.days_above_market + comp.days_below_market} days above market</strong>
          {' · '}avg premium <strong className="text-gold-dark">{comp.avg_premium_pct}%</strong>. {comp.insight}
        </div>
      </div>

      {/* Monthly detail (collapsible) */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <button onClick={() => setShowMonthly(!showMonthly)} className="text-sm font-bold text-navy hover:underline">
          {showMonthly ? '▼' : '▶'} Monthly KPI detail · {trends.paired.length} months
        </button>
        {showMonthly && (
          <table className="w-full text-xs mt-3">
            <thead className="text-[10px] uppercase tracking-wider text-slate-400">
              <tr>
                <th className="text-left py-1">Month</th>
                <th className="text-right">ADR</th><th className="text-right">vs LY</th>
                <th className="text-right">RevPAR</th><th className="text-right">vs LY</th>
                <th className="text-right">Occ%</th><th className="text-right">vs LY</th>
                <th className="text-right">Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {trends.paired.map((m, i) => {
                const adrDelta = m.prior_adr ? +(((m.current_adr - m.prior_adr) / m.prior_adr) * 100).toFixed(1) : null
                const revparDelta = m.prior_revpar ? +(((m.current_revpar - m.prior_revpar) / m.prior_revpar) * 100).toFixed(1) : null
                const occDelta = m.prior_occ ? +(m.current_occ - m.prior_occ).toFixed(1) : null
                return (
                  <tr key={i}>
                    <td className="py-1.5 font-semibold text-navy">{m.month_label}</td>
                    <td className="text-right text-slate-700">${m.current_adr}</td>
                    <td className={`text-right ${(adrDelta ?? 0) >= 0 ? 'text-sage-dark' : 'text-coral'}`}>{adrDelta != null ? `${adrDelta > 0 ? '+' : ''}${adrDelta}%` : '—'}</td>
                    <td className="text-right text-slate-700">${m.current_revpar}</td>
                    <td className={`text-right ${(revparDelta ?? 0) >= 0 ? 'text-sage-dark' : 'text-coral'}`}>{revparDelta != null ? `${revparDelta > 0 ? '+' : ''}${revparDelta}%` : '—'}</td>
                    <td className="text-right text-slate-700">{m.current_occ}%</td>
                    <td className={`text-right ${(occDelta ?? 0) >= 0 ? 'text-sage-dark' : 'text-coral'}`}>{occDelta != null ? `${occDelta > 0 ? '+' : ''}${occDelta}` : '—'}</td>
                    <td className="text-right text-slate-700">${m.current_revenue.toLocaleString()}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function KpiCard({ label, value, sub, positive }: { label: string; value: string; sub: string; positive: boolean }) {
  return (
    <div className={`bg-white rounded-xl border p-4 ${positive ? 'border-sage/30' : 'border-coral/30'}`}>
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">{label}</div>
      <div className={`text-2xl font-bold mt-0.5 ${positive ? 'text-sage-dark' : 'text-coral'}`}>{value}</div>
      <div className="text-[11px] text-slate-500">{sub}</div>
    </div>
  )
}

function TrendChart({ title, data, currentKey, priorKey, yFormat, yDomain }: {
  title: string; data: PairedRow[]; currentKey: keyof PairedRow; priorKey: keyof PairedRow
  yFormat: (v: number) => string; yDomain?: [number, number]
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5">
      <h2 className="font-bold text-navy mb-2">{title}</h2>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 5, right: 15, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
          <XAxis dataKey="month_label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={yFormat} domain={yDomain} />
          <Tooltip formatter={(v: any) => yFormat(Number(v))} />
          <Legend iconType="line" iconSize={10} wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey={priorKey as string}   stroke="#1A3A5C" strokeDasharray="4 3" strokeWidth={1.5} dot={false} name="Prior year" />
          <Line type="monotone" dataKey={currentKey as string} stroke="#A07830" strokeWidth={2.5} dot={{ r: 3 }} name="Current year" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

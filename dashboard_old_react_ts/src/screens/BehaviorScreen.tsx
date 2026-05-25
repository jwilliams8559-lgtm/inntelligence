import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface SourceRow {
  bookings: number; revenue: number; commission_pct: number
  pct_bookings: number; pct_revenue: number
  commission_cost: number; net_revenue: number
}
interface SourceData {
  period_days: number; total_bookings: number; total_revenue: number
  total_commission_paid: number; direct_booking_pct: number
  sources: Record<string, SourceRow>
  insight: { headline: string; opportunity: string; direct_vs_industry: string }
}
interface Cancellation {
  date: string; room: string; booked_rate: number; nights: number
  lead_time_days: number; days_before_checkin: number; source: string
  demand_score_at_cancel: number; reason: string
}
interface CancelData {
  period_days: number; total_cancellations: number; total_lost_revenue: number
  avg_days_before_checkin: number; cancellation_rate_pct: number
  by_source: Record<string, number>
  by_window: Record<string, number>
  cancellations: Cancellation[]
  insight: { headline: string; recommendation: string; high_demand_cancellations: number }
}
interface SensitivityEvent {
  date: string; room: string; rate_change: string
  rate_before: number; rate_after: number
  bookings_7d_before: number; bookings_7d_after: number
  pace_change_pct: number
  interpretation: string; recommendation: string
}
interface SensitivityData {
  total_events_tracked: number; elastic_responses: number; inelastic_responses: number
  sensitivity_summary: string; events: SensitivityEvent[]
  insight: { headline: string; waterfront_elasticity: string; garden_elasticity: string; festival_elasticity: string }
}

const SOURCE_COLORS: Record<string, string> = {
  'Direct':       '#A07830',  // gold
  'Phone/Email':  '#C19E50',
  'Booking.com':  '#003580',
  'Expedia':      '#FBCC30',
  'Airbnb':       '#FF5A5F',
  'VRBO':         '#1A5276',
  'Hotels.com':   '#D32D2F',
  'Agoda':        '#FF5722',
}

export default function BehaviorScreen(_: Props) {
  return (
    <LockedFeature featureName="Guest Behavior Tracking" featureKey="behavior_tracking"
      description="Booking source breakdown, cancellation pattern analysis, and price sensitivity by room type. Tied to your demand engine so you see which rate moves grew vs slowed bookings.">
      <Body />
    </LockedFeature>
  )
}

function Body() {
  const [sources,     setSources]     = useState<SourceData | null>(null)
  const [cancels,     setCancels]     = useState<CancelData | null>(null)
  const [sensitivity, setSensitivity] = useState<SensitivityData | null>(null)
  const [days, setDays] = useState(30)

  useEffect(() => {
    fetch(`/api/behavior/sources?days=${days}`).then(r => r.json()).then(setSources)
    fetch(`/api/behavior/cancellations?days=${days * 3}`).then(r => r.json()).then(setCancels)
    fetch('/api/behavior/price-sensitivity').then(r => r.json()).then(setSensitivity)
  }, [days])

  if (!sources || !cancels || !sensitivity) {
    return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading behavior data…</div>
  }

  const sourceArray = Object.entries(sources.sources).map(([name, d]) => ({ name, ...d }))

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 pb-20 space-y-5">
      <header className="flex items-baseline justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-navy font-bold text-xl">Guest Behavior Tracking</h1>
          <p className="text-slate-500 text-sm">Booking sources · cancellations · price sensitivity</p>
        </div>
        <RangeTabs value={days} onChange={setDays} />
      </header>

      {/* Panel 1 — Booking sources */}
      <section className="bg-white rounded-xl border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-1">Booking Source Breakdown</h2>
        <p className="text-xs text-slate-500 mb-4">{sources.period_days}-day window · {sources.total_bookings} bookings · ${sources.total_revenue.toLocaleString()} revenue</p>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={sourceArray} dataKey="bookings" nameKey="name" innerRadius={50} outerRadius={95} paddingAngle={2}>
                  {sourceArray.map((s, i) => <Cell key={i} fill={SOURCE_COLORS[s.name] || '#94A3B8'} />)}
                </Pie>
                <Tooltip formatter={(v: any, _name: string, props: any) => [`${v} bookings (${props.payload.pct_bookings}%)`, props.payload.name]} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="lg:col-span-3">
            <table className="w-full text-xs">
              <thead className="text-[10px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="text-left py-1">Source</th>
                  <th className="text-right">Bookings</th>
                  <th className="text-right">Revenue</th>
                  <th className="text-right">Commission</th>
                  <th className="text-right">Net</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sourceArray.map(s => (
                  <tr key={s.name} className={s.name === 'Direct' ? 'bg-gold/5 font-semibold' : ''}>
                    <td className="py-1.5 text-navy">
                      <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: SOURCE_COLORS[s.name] || '#94A3B8' }} />
                      {s.name} <span className="text-[10px] text-slate-400">({s.pct_bookings}%)</span>
                    </td>
                    <td className="text-right text-slate-700">{s.bookings}</td>
                    <td className="text-right text-slate-700">${s.revenue.toLocaleString()}</td>
                    <td className="text-right text-coral">{s.commission_cost > 0 ? `$${s.commission_cost.toLocaleString()}` : '—'}</td>
                    <td className="text-right text-sage-dark">${s.net_revenue.toLocaleString()}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-slate-200 font-bold text-navy">
                  <td className="py-1.5">Total</td>
                  <td className="text-right">{sources.total_bookings}</td>
                  <td className="text-right">${sources.total_revenue.toLocaleString()}</td>
                  <td className="text-right text-coral">${sources.total_commission_paid.toLocaleString()}</td>
                  <td className="text-right text-sage-dark">${(sources.total_revenue - sources.total_commission_paid).toLocaleString()}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-navy text-white rounded-lg p-3 mt-4">
          <div className="text-[10px] uppercase tracking-[2px] text-gold font-bold">Direct booking opportunity</div>
          <div className="font-bold mt-1 text-sm">{sources.insight.headline}</div>
          <div className="text-xs text-white/80 mt-1">{sources.insight.opportunity}</div>
          <div className="text-[11px] text-gold mt-2">{sources.insight.direct_vs_industry}</div>
        </div>
      </section>

      {/* Panel 2 — Cancellations */}
      <section className="bg-white rounded-xl border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-1">Cancellation Analysis</h2>
        <p className="text-xs text-slate-500 mb-4">{cancels.period_days}-day window · {cancels.cancellation_rate_pct}% cancellation rate</p>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-2">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={Object.entries(cancels.by_window).map(([k, v]) => ({ name: k, count: v }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#A07830" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
              <KpiBox label="Cancellations"          value={String(cancels.total_cancellations)} />
              <KpiBox label="Lost revenue"           value={`$${cancels.total_lost_revenue.toLocaleString()}`} coral />
              <KpiBox label="Avg days before check-in" value={String(cancels.avg_days_before_checkin)} />
              <KpiBox label="High-demand cancels"    value={String(cancels.insight.high_demand_cancellations)} />
            </div>
          </div>
          <div className="lg:col-span-3">
            <table className="w-full text-xs">
              <thead className="text-[10px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="text-left py-1">Date</th>
                  <th className="text-left">Room</th>
                  <th className="text-right">Rate</th>
                  <th className="text-right">Days Before</th>
                  <th className="text-left">Source</th>
                  <th className="text-right">Demand</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cancels.cancellations.map((c, i) => {
                  const demandColor = c.demand_score_at_cancel < 50 ? 'text-coral'
                    : c.demand_score_at_cancel < 70 ? 'text-amber-600' : 'text-sage-dark'
                  return (
                    <tr key={i}>
                      <td className="py-1.5 text-slate-700">{c.date}</td>
                      <td className="text-slate-700">{c.room}</td>
                      <td className="text-right text-slate-700">${c.booked_rate}</td>
                      <td className="text-right text-slate-700">{c.days_before_checkin}</td>
                      <td className="text-slate-600 text-[10px]">{c.source}</td>
                      <td className={`text-right font-bold ${demandColor}`}>{c.demand_score_at_cancel}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-4 text-xs">
          <div className="font-bold text-amber-900">{cancels.insight.headline}</div>
          <div className="text-amber-800 mt-1">{cancels.insight.recommendation}</div>
        </div>
      </section>

      {/* Panel 3 — Price sensitivity */}
      <section className="bg-white rounded-xl border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-1">Price Sensitivity</h2>
        <p className="text-xs text-slate-500 mb-4">
          {sensitivity.total_events_tracked} rate changes tracked · {sensitivity.inelastic_responses} inelastic · {sensitivity.elastic_responses} elastic
        </p>
        <div className="space-y-3">
          {sensitivity.events.map((e, i) => {
            const inelastic = e.pace_change_pct >= 0
            return (
              <div key={i} className={`grid grid-cols-1 lg:grid-cols-3 gap-3 border-l-4 rounded-r-lg p-3 ${inelastic ? 'border-sage bg-sage/5' : 'border-coral bg-coral/5'}`}>
                <div>
                  <div className="text-[10px] uppercase text-slate-400 font-bold">{e.date} · {e.room}</div>
                  <div className="font-bold text-navy mt-0.5">{e.rate_change}</div>
                  <div className="text-xs text-slate-600 mt-1">
                    <span className="line-through text-slate-400">${e.rate_before}</span>
                    {' → '}
                    <strong className="text-navy">${e.rate_after}</strong>
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-[10px] uppercase text-slate-400 font-bold">Booking pace 7d</div>
                  <div className="font-bold text-navy mt-0.5">{e.bookings_7d_before} → {e.bookings_7d_after}</div>
                  <div className={`text-sm font-bold mt-1 ${e.pace_change_pct >= 0 ? 'text-sage-dark' : 'text-coral'}`}>
                    {e.pace_change_pct > 0 ? '+' : ''}{e.pace_change_pct}%
                  </div>
                </div>
                <div>
                  <span className={`text-[9px] uppercase font-bold tracking-wide px-1.5 py-0.5 rounded ${inelastic ? 'bg-sage text-white' : 'bg-coral text-white'}`}>
                    {inelastic ? 'Inelastic' : 'Elastic'}
                  </span>
                  <div className="text-[11px] text-slate-700 mt-1.5 leading-snug">{e.interpretation}</div>
                  <div className="text-[10px] text-gold-dark font-semibold mt-1">→ {e.recommendation}</div>
                </div>
              </div>
            )
          })}
        </div>
        <div className="bg-navy/5 border border-navy/20 rounded-lg p-3 mt-4 text-xs">
          <div className="font-bold text-navy">{sensitivity.insight.headline}</div>
          <div className="text-slate-700 mt-1">{sensitivity.sensitivity_summary}</div>
        </div>
      </section>
    </div>
  )
}

function KpiBox({ label, value, coral }: { label: string; value: string; coral?: boolean }) {
  return (
    <div className={`border rounded-lg p-2 ${coral ? 'border-coral/30 bg-coral/5' : 'border-slate-200'}`}>
      <div className="text-[10px] uppercase text-slate-400 font-bold">{label}</div>
      <div className={`text-base font-bold mt-0.5 ${coral ? 'text-coral' : 'text-navy'}`}>{value}</div>
    </div>
  )
}

function RangeTabs({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const opts = [
    { label: '30 Days',  value: 30 },
    { label: '90 Days',  value: 90 },
    { label: '6 Months', value: 180 },
    { label: '12 Months', value: 365 },
  ]
  return (
    <div className="flex gap-1 text-xs">
      {opts.map(o => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`px-2.5 py-1 rounded font-semibold ${value === o.value ? 'bg-navy text-white' : 'bg-white border border-slate-200 text-slate-600'}`}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

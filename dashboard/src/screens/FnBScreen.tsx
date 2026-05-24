import { useEffect, useState } from 'react'
import { format, parseISO } from 'date-fns'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceArea, Legend,
} from 'recharts'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface FnbConfig {
  enabled: boolean
  outlets?: { id: string; name: string; type: string; icon: string; seats?: number; capacity?: number }[]
  pos_system?: string | null
  reservation_system?: string | null
}
interface DowRow {
  day: string; avg_covers: number; avg_check: number; avg_revenue: number
  avg_occ_pct: number; is_yield_gap: boolean
}
interface CorrelationRow { bucket: string; avg_fnb_revenue: number; nights: number }
interface Summary {
  enabled: boolean; period_days: number
  total_fnb_revenue: number
  restaurant: {
    total_revenue: number; total_covers: number; avg_check: number
    avg_occupancy_pct: number; avg_revpash: number
    dow_table: DowRow[]
    top_days: any[]; low_days: any[]
  }
  bar: { total_revenue: number; total_guests: number; avg_occupancy_pct: number; operating_nights: number }
  combined_per_room_per_day: number
  room_fnb_correlation: CorrelationRow[]
  industry_benchmark_revpash: { low: number; high: number }
}
interface DailyRestaurant {
  date: string; covers: number; revenue: number; revpash: number
  service_type: string; notes: string; avg_check: number
  covers_capacity_pct: number
}
interface DailyBar {
  date: string; day_of_week: string; guests: number; revenue: number
  avg_spend: number; capacity_pct: number; min_spend_applied: boolean
  weather_flag: boolean
}
interface Recommendation {
  outlet: string; outlet_name: string; date: string; date_label: string
  days_away: number; demand_score: number; demand_label: string
  type: string; priority: 'high'|'medium'; title: string; action: string
  est_revenue_lift: number; bar_action?: string
}

type TabKey = 'combined' | 'restaurant' | 'bar'

export default function FnBScreen(_: Props) {
  return (
    <LockedFeature featureName="F&B Yield Management" featureKey="fb_yield_module"
      description="Track restaurant covers, bar guests, and RevPASH. Demand-gated recommendations: prix fixe on peak nights, happy hour on slow Tue/Wed. Private event pricing calculator. Room-to-F&B correlation insights.">
      <Body />
    </LockedFeature>
  )
}

function Body() {
  const [config,     setConfig]     = useState<FnbConfig | null>(null)
  const [summary,    setSummary]    = useState<Summary | null>(null)
  const [rsc,        setRsc]        = useState<DailyRestaurant[]>([])
  const [bar,        setBar]        = useState<DailyBar[]>([])
  const [recs,       setRecs]       = useState<Recommendation[]>([])
  const [tab,        setTab]        = useState<TabKey>('combined')

  useEffect(() => {
    fetch('/api/fnb/config').then(r => r.json()).then(setConfig)
    fetch('/api/fnb/summary').then(r => r.json()).then(setSummary)
    fetch('/api/fnb/daily').then(r => r.json()).then(d => {
      setRsc(d?.outlets?.rsc_restaurant || [])
      setBar(d?.outlets?.rooftop_bar || [])
    })
    fetch('/api/fnb/recommendations').then(r => r.json()).then(setRecs)
  }, [])

  if (!config) return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading F&amp;B…</div>
  if (!config.enabled) return (
    <div className="flex-1 bg-cream p-8 flex items-center justify-center">
      <div className="max-w-md bg-white rounded-xl border border-slate-200 p-6 text-center">
        <div className="text-4xl">🍽️</div>
        <h2 className="text-navy font-bold mt-3">F&amp;B module not configured</h2>
        <p className="text-sm text-slate-600 mt-2">
          The F&amp;B yield module is available for properties with restaurant or bar
          operations. Configure outlets in Settings to enable it.
        </p>
      </div>
    </div>
  )
  if (!summary) return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading F&amp;B summary…</div>

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 pb-20 space-y-5">
      <header>
        <h1 className="text-navy font-bold text-xl">F&amp;B Yield Management</h1>
        <p className="text-slate-500 text-sm">Last {summary.period_days} days · {config.outlets?.map(o => o.name).join(' · ')}</p>
      </header>

      <Tabs tab={tab} setTab={setTab} />

      {/* Integration banner */}
      {(!config.pos_system || !config.reservation_system) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm flex items-baseline justify-between gap-4 flex-wrap">
          <div className="text-amber-800">
            📋 <strong>Connect your POS</strong> (Square, Toast, Clover) and <strong>reservation system</strong> (OpenTable, Resy) to pull real data instead of estimates.
            The module works without integration — current numbers are forecasts.
          </div>
          <div className="flex gap-2 text-xs whitespace-nowrap">
            <button className="bg-amber-700 text-white font-bold px-3 py-1.5 rounded">Connect POS</button>
            <button className="bg-white border border-amber-300 text-amber-800 font-bold px-3 py-1.5 rounded">Skip — Manual</button>
          </div>
        </div>
      )}

      {tab === 'combined' && <CombinedView summary={summary} recs={recs} />}
      {tab === 'restaurant' && <RestaurantView summary={summary} daily={rsc} recs={recs.filter(r => r.outlet === 'rsc_restaurant')} />}
      {tab === 'bar' && <BarView summary={summary} daily={bar} recs={recs.filter(r => r.outlet === 'rooftop_bar')} />}
    </div>
  )
}

function Tabs({ tab, setTab }: { tab: TabKey; setTab: (t: TabKey) => void }) {
  const items: { id: TabKey; icon: string; label: string }[] = [
    { id: 'combined',   icon: '📊', label: 'Combined' },
    { id: 'restaurant', icon: '🍽️', label: 'The Parlor' },
    { id: 'bar',        icon: '🍸', label: 'Rooftop Bar' },
  ]
  return (
    <div className="flex gap-2 border-b border-slate-200">
      {items.map(t => (
        <button key={t.id} onClick={() => setTab(t.id)}
          className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
            tab === t.id ? 'border-gold text-navy' : 'border-transparent text-slate-500 hover:text-navy'
          }`}>
          {t.icon} {t.label}
        </button>
      ))}
    </div>
  )
}

// ── Combined view ─────────────────────────────────────────────────
function CombinedView({ summary, recs }: { summary: Summary; recs: Recommendation[] }) {
  return (
    <>
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total F&B Revenue" value={`$${summary.total_fnb_revenue.toLocaleString()}`} sub={`/ ${summary.period_days} days`} />
        <KpiCard label="Avg Check (RSC)"   value={`$${summary.restaurant.avg_check.toFixed(2)}`}      sub="/ cover" />
        <KpiCard label="RevPASH (Restaurant)" value={`$${summary.restaurant.avg_revpash.toFixed(2)}`} sub="/ seat-hour" highlight />
        <KpiCard label="Bar Occupancy"     value={`${summary.bar.avg_occupancy_pct}%`}              sub={`avg / ${summary.bar.operating_nights} open nights`} />
      </div>
      <p className="text-[11px] text-slate-500 -mt-3">
        RevPASH (Revenue Per Available Seat Hour) is the F&amp;B equivalent of RevPAR. Industry benchmark for upscale independents:
        <strong> ${summary.industry_benchmark_revpash.low}–${summary.industry_benchmark_revpash.high}</strong>/seat-hour.
      </p>

      {/* Correlation card */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <h2 className="font-bold text-navy">Room Occupancy → F&amp;B Revenue Correlation</h2>
        <p className="text-xs text-slate-500 mt-0.5 mb-4">Higher room occupancy drives higher F&amp;B yield. The pricing engine accounts for this when recommending rates.</p>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={summary.room_fnb_correlation} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${v}`} />
            <Tooltip formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Avg F&B Revenue']} />
            <Bar dataKey="avg_fnb_revenue" fill="#A07830" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="text-xs text-slate-700 mt-2">
          When room occupancy exceeds 85%, RSC revenue averages
          <strong> ${summary.room_fnb_correlation.find(c => c.bucket === '85+')?.avg_fnb_revenue.toLocaleString() || '—'}/night</strong>.
          Room pricing decisions directly drive F&amp;B yield.
        </div>
      </div>

      {/* Recommendations preview */}
      <Recommendations recs={recs.slice(0, 5)} />
    </>
  )
}

// ── Restaurant view ───────────────────────────────────────────────
function RestaurantView({ summary, daily, recs }: { summary: Summary; daily: DailyRestaurant[]; recs: Recommendation[] }) {
  const wfStart = daily.find(d => d.date >= '2026-07-17' && d.date <= '2026-07-26')?.date
  const wfEnd   = [...daily].reverse().find(d => d.date >= '2026-07-17' && d.date <= '2026-07-26')?.date
  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      <div className="lg:col-span-3 space-y-4">
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h2 className="font-bold text-navy">The Parlor — Daily Performance</h2>
          <p className="text-xs text-slate-500 mb-3">Covers and revenue over the next {summary.period_days} days. Gold band = Water Festival.</p>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={daily} margin={{ top: 5, right: 35, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => format(parseISO(d), 'M/d')} interval={4} />
              <YAxis yAxisId="rev" orientation="left"  tick={{ fontSize: 10 }} tickFormatter={v => `$${(v/1000).toFixed(1)}k`} />
              <YAxis yAxisId="cov" orientation="right" tick={{ fontSize: 10 }} />
              {wfStart && wfEnd && <ReferenceArea yAxisId="rev" x1={wfStart} x2={wfEnd} fill="#A07830" fillOpacity={0.12} />}
              <Tooltip
                formatter={(v: any, name: string) => name === 'Revenue' ? [`$${Number(v).toFixed(0)}`, name] : [v, name]}
                labelFormatter={l => format(parseISO(l), 'EEE MMM d')} />
              <Legend iconType="line" iconSize={10} wrapperStyle={{ fontSize: 11 }} />
              <Line yAxisId="rev" type="monotone" dataKey="revenue" stroke="#A07830" strokeWidth={2.5} dot={false} name="Revenue" />
              <Line yAxisId="cov" type="monotone" dataKey="covers"  stroke="#1A3A5C" strokeWidth={1.5} dot={false} name="Covers" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h2 className="font-bold text-navy">Day-of-Week Average</h2>
          <p className="text-xs text-slate-500 mb-3">Amber rows are yield gaps (occupancy below 55%).</p>
          <table className="w-full text-xs">
            <thead className="text-[10px] uppercase tracking-wider text-slate-400">
              <tr><th className="text-left py-1">Day</th><th className="text-right">Covers</th><th className="text-right">Avg Check</th><th className="text-right">Revenue</th><th className="text-right">Occ %</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.restaurant.dow_table.map(r => (
                <tr key={r.day} className={r.is_yield_gap ? 'bg-amber-50' : ''}>
                  <td className="py-1.5 font-semibold text-navy">{r.day}</td>
                  <td className="text-right text-slate-600">{r.avg_covers}</td>
                  <td className="text-right text-slate-600">${r.avg_check.toFixed(2)}</td>
                  <td className="text-right text-slate-600">${r.avg_revenue.toLocaleString()}</td>
                  <td className={`text-right font-semibold ${r.is_yield_gap ? 'text-amber-700' : 'text-slate-700'}`}>{r.avg_occ_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="lg:col-span-2 space-y-4">
        <Recommendations recs={recs} title="Restaurant Recommendations" />
        <PrivateEventCalculator />
      </div>
    </div>
  )
}

// ── Bar view ──────────────────────────────────────────────────────
function BarView({ summary, daily, recs }: { summary: Summary; daily: DailyBar[]; recs: Recommendation[] }) {
  // Aggregate by day-of-week
  const dowMap: Record<string, { count: number; revenue: number; guests: number }> = {}
  daily.forEach(d => {
    const key = d.day_of_week
    if (!dowMap[key]) dowMap[key] = { count: 0, revenue: 0, guests: 0 }
    dowMap[key].count += 1
    dowMap[key].revenue += d.revenue
    dowMap[key].guests  += d.guests
  })
  const dowData = ['Thursday','Friday','Saturday','Sunday'].map(day => {
    const row = dowMap[day] || { count: 1, revenue: 0, guests: 0 }
    return {
      day,
      avg_revenue: Math.round(row.revenue / row.count),
      avg_guests:  Math.round(row.guests / row.count),
    }
  })
  const minSpendNights = daily.filter(d => d.min_spend_applied).length

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      <div className="lg:col-span-3 space-y-4">
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h2 className="font-bold text-navy">Rooftop Bar — Revenue by Day of Week</h2>
          <p className="text-xs text-slate-500 mb-3">Thursday–Sunday operations only.</p>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={dowData} margin={{ top: 5, right: 15, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${v}`} />
              <Tooltip formatter={(v: any) => `$${Number(v).toLocaleString()}`} />
              <Bar dataKey="avg_revenue" fill="#A07830" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <KpiCard label="Avg Guests / Night" value={String(Math.round(summary.bar.total_guests / Math.max(summary.bar.operating_nights, 1)))} sub="/ 60 capacity" />
          <KpiCard label="Min-Spend Nights" value={`${minSpendNights} / ${daily.length}`} sub="$25 minimum applied" />
        </div>

        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h2 className="font-bold text-navy">Bar Configuration</h2>
          <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
            <div><div className="text-[10px] uppercase text-slate-400 font-bold">Peak min spend</div><div className="font-bold text-navy text-base">$25.00</div></div>
            <div><div className="text-[10px] uppercase text-slate-400 font-bold">Normal nights</div><div className="font-bold text-slate-500 text-base">No minimum</div></div>
            <div><div className="text-[10px] uppercase text-slate-400 font-bold">Private buyout</div><div className="font-bold text-navy text-base">$1,800/evening</div></div>
          </div>
        </div>
      </div>

      <div className="lg:col-span-2 space-y-4">
        <Recommendations recs={recs} title="Bar Recommendations" />
        <PrivateEventCalculator defaultOutlet="rooftop_bar" />
      </div>
    </div>
  )
}

// ── Shared components ─────────────────────────────────────────────
function KpiCard({ label, value, sub, highlight }: { label: string; value: string; sub: string; highlight?: boolean }) {
  return (
    <div className={`bg-white rounded-xl border p-4 ${highlight ? 'border-gold' : 'border-slate-100'}`}>
      <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">{label}</div>
      <div className="text-2xl font-bold text-navy mt-1">{value}</div>
      <div className="text-[11px] text-slate-500">{sub}</div>
    </div>
  )
}

function Recommendations({ recs, title = 'F&B Yield Recommendations' }: { recs: Recommendation[]; title?: string }) {
  if (recs.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-100 p-4 text-xs text-slate-400">
        No recommendations for the next 14 days. Your F&amp;B schedule is well-tuned to current demand.
      </div>
    )
  }
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5 space-y-3">
      <h2 className="font-bold text-navy">{title}</h2>
      {recs.map((r, i) => (
        <div key={i} className={`rounded-lg p-3 border-l-4 ${
          r.priority === 'high' ? 'border-coral bg-coral/5' : 'border-gold bg-gold/5'
        }`}>
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <span className={`text-[9px] uppercase font-bold tracking-wide px-1.5 py-0.5 rounded ${
                r.priority === 'high' ? 'bg-coral text-white' : 'bg-gold text-white'
              }`}>{r.priority}</span>
              <span className="ml-2 font-semibold text-navy text-sm">{r.title}</span>
            </div>
            <span className="text-[10px] text-slate-500">{r.date_label}</span>
          </div>
          <div className="text-[11px] text-slate-700 mt-1.5 leading-snug">{r.action}</div>
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-xs font-bold text-sage-dark">+${r.est_revenue_lift.toLocaleString()} est lift</span>
            <button onClick={() => window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: 'calendar' }))}
              className="text-[10px] text-navy hover:underline">Apply to Calendar →</button>
          </div>
          {r.bar_action && <div className="text-[10px] text-slate-500 mt-1 italic">+ Bar: {r.bar_action}</div>}
        </div>
      ))}
    </div>
  )
}

function PrivateEventCalculator({ defaultOutlet = 'rooftop_bar' }: { defaultOutlet?: string }) {
  const [outletId, setOutletId]       = useState(defaultOutlet)
  const [guestCount, setGuestCount]   = useState(40)
  const [eventDate, setEventDate]     = useState(new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10))
  const [hours, setHours]             = useState(4)
  const [result, setResult]           = useState<any>(null)
  const [busy, setBusy]               = useState(false)

  async function calculate() {
    setBusy(true)
    const r = await fetch('/api/fnb/private-event', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ outlet_id: outletId, guest_count: guestCount, hours, event_date: eventDate }),
    })
    setResult(await r.json())
    setBusy(false)
  }

  return (
    <details className="bg-white rounded-xl border border-slate-100 p-4 text-sm">
      <summary className="cursor-pointer font-bold text-navy">Private Event / Buyout Calculator</summary>
      <div className="mt-3 space-y-2 text-xs">
        <label className="block">
          <div className="text-slate-500 font-semibold mb-0.5">Outlet</div>
          <select className="w-full border border-slate-200 rounded px-2 py-1.5" value={outletId} onChange={e => setOutletId(e.target.value)}>
            <option value="rsc_restaurant">The Parlor</option>
            <option value="rooftop_bar">Rooftop Bar</option>
          </select>
        </label>
        <label className="block">
          <div className="text-slate-500 font-semibold mb-0.5">Guest count</div>
          <input type="number" className="w-full border border-slate-200 rounded px-2 py-1.5" value={guestCount} onChange={e => setGuestCount(Number(e.target.value))} />
        </label>
        <label className="block">
          <div className="text-slate-500 font-semibold mb-0.5">Event date</div>
          <input type="date" className="w-full border border-slate-200 rounded px-2 py-1.5" value={eventDate} onChange={e => setEventDate(e.target.value)} />
        </label>
        <label className="block">
          <div className="text-slate-500 font-semibold mb-0.5">Hours</div>
          <input type="number" step={0.5} className="w-full border border-slate-200 rounded px-2 py-1.5" value={hours} onChange={e => setHours(Number(e.target.value))} />
        </label>
        <button onClick={calculate} disabled={busy} className="w-full bg-navy text-white font-bold py-2 rounded mt-2 disabled:opacity-60">
          {busy ? 'Calculating…' : 'Get Pricing'}
        </button>
        {result?.pricing && (
          <div className="bg-cream border border-gold/30 rounded-lg p-3 mt-3 space-y-1">
            <div className="flex justify-between"><span className="text-slate-500">Recommended rate</span><strong className="text-navy text-base">${(result.pricing.recommended_rate || result.pricing.recommended_total).toLocaleString()}</strong></div>
            {result.pricing.buyout_rate && <div className="flex justify-between"><span className="text-slate-500">Buyout rate</span><span>${result.pricing.buyout_rate.toLocaleString()}</span></div>}
            {result.pricing.per_head_equivalent && <div className="flex justify-between"><span className="text-slate-500">Per-head equivalent</span><span>${result.pricing.per_head_equivalent.toFixed(2)}</span></div>}
            {result.pricing.per_head_minimum && <div className="flex justify-between"><span className="text-slate-500">Per-head minimum</span><span>${result.pricing.per_head_minimum.toFixed(2)}</span></div>}
            {result.pricing.minimum_spend && <div className="flex justify-between"><span className="text-slate-500">Minimum spend</span><span>${result.pricing.minimum_spend.toLocaleString()}</span></div>}
            {result.demand_score != null && <div className="text-[10px] text-slate-500 mt-1">Demand on {result.event_date}: <strong>{result.demand_score}</strong> ({result.demand_label}){result.pricing.premium_applied && <span className="ml-1 text-gold-dark font-bold">★ Premium applied</span>}</div>}
            {result.opportunity_cost?.note && <div className="text-[10px] text-slate-600 mt-1 italic">{result.opportunity_cost.note}</div>}
          </div>
        )}
      </div>
    </details>
  )
}

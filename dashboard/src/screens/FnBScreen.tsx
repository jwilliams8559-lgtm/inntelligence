import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
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
// Flat monthly summary (matches /api/fnb/summary contract).
interface Summary {
  monthly_revenue: number; restaurant_monthly: number; bar_monthly: number
  revpash: number; avg_check: number; total_monthly_covers: number
}
// Day-of-week rows (matches /api/fnb/daily?outlet= contract).
interface RestaurantDow { day: string; covers: number; avg_check: number; revenue: number; occ_pct: number }
interface RooftopDow    { day: string; guests: number; avg_spend: number; revenue: number; occ_pct: number }
interface Recommendation {
  priority: string; date: string; title: string; action: string
  revenue_lift: number; lift_label: string
}

type TabKey = 'combined' | 'restaurant' | 'bar'

export default function FnBScreen(_: Props) {
  return (
    <LockedFeature featureName="F&B Yield Management" featureKey="fb_yield_module"
      description="Track restaurant covers, bar guests, and RevPASH. Demand-gated recommendations: prix fixe on peak nights, happy hour on slow Tue/Wed. Private event pricing calculator.">
      <Body />
    </LockedFeature>
  )
}

function Body() {
  const [config,  setConfig]  = useState<FnbConfig | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [rsc,     setRsc]     = useState<RestaurantDow[]>([])
  const [bar,     setBar]     = useState<RooftopDow[]>([])
  const [recs,    setRecs]    = useState<Recommendation[]>([])
  const [tab,     setTab]     = useState<TabKey>('combined')

  useEffect(() => {
    fetch('/api/fnb/config').then(r => r.json()).then(setConfig)
    fetch('/api/fnb/summary').then(r => r.json()).then(setSummary)
    fetch('/api/fnb/daily?outlet=restaurant').then(r => r.json()).then(d => setRsc(Array.isArray(d) ? d : []))
    fetch('/api/fnb/daily?outlet=rooftop_bar').then(r => r.json()).then(d => setBar(Array.isArray(d) ? d : []))
    fetch('/api/fnb/recommendations').then(r => r.json()).then(d => setRecs(Array.isArray(d) ? d : []))
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
        <p className="text-slate-500 text-sm">Monthly · {config.outlets?.map(o => o.name).join(' · ')}</p>
      </header>

      <Tabs tab={tab} setTab={setTab} />

      {/* KPI row from the flat monthly summary */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <KpiCard label="Monthly F&B Revenue" value={`$${summary.monthly_revenue.toLocaleString()}`} sub="/ month" highlight />
        <KpiCard label="The Parlor"     value={`$${summary.restaurant_monthly.toLocaleString()}`} sub="/ month" />
        <KpiCard label="The Rooftop"    value={`$${summary.bar_monthly.toLocaleString()}`} sub="/ month" />
        <KpiCard label="RevPASH"        value={`$${summary.revpash.toFixed(2)}`} sub="/ seat-hour" />
        <KpiCard label="Avg Check"      value={`$${summary.avg_check.toFixed(2)}`} sub="/ cover" />
        <KpiCard label="Monthly Covers" value={summary.total_monthly_covers.toLocaleString()} sub="covers / month" />
      </div>

      {tab === 'combined' && (
        <>
          <ParlorDowCard rows={rsc} />
          <RooftopDowCard rows={bar} />
          <Recommendations recs={recs} />
          <PrivateEventCalculator />
        </>
      )}
      {tab === 'restaurant' && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3 space-y-4"><ParlorDowCard rows={rsc} chart /></div>
          <div className="lg:col-span-2 space-y-4">
            <Recommendations recs={recs} title="Parlor Recommendations" />
            <PrivateEventCalculator defaultOutlet="rsc_restaurant" />
          </div>
        </div>
      )}
      {tab === 'bar' && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-3 space-y-4"><RooftopDowCard rows={bar} chart /></div>
          <div className="lg:col-span-2 space-y-4">
            <Recommendations recs={recs} title="Rooftop Recommendations" />
            <PrivateEventCalculator defaultOutlet="rooftop_bar" />
          </div>
        </div>
      )}
    </div>
  )
}

function Tabs({ tab, setTab }: { tab: TabKey; setTab: (t: TabKey) => void }) {
  const items: { id: TabKey; icon: string; label: string }[] = [
    { id: 'combined',   icon: '📊', label: 'Combined' },
    { id: 'restaurant', icon: '🍽️', label: 'The Parlor' },
    { id: 'bar',        icon: '🍸', label: 'The Rooftop' },
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

function ParlorDowCard({ rows, chart }: { rows: RestaurantDow[]; chart?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5">
      <h2 className="font-bold text-navy">The Parlor at Bay Street Inn — Day of Week</h2>
      <p className="text-xs text-slate-500 mb-3">Amber rows are yield gaps (occupancy below 55%).</p>
      {chart && (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={rows} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="day" tick={{ fontSize: 10 }} tickFormatter={(d: string) => d.slice(0, 3)} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(1)}k`} />
            <Tooltip formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Revenue']} />
            <Bar dataKey="revenue" fill="#A07830" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
      <table className="w-full text-xs mt-2">
        <thead className="text-[10px] uppercase tracking-wider text-slate-400">
          <tr><th className="text-left py-1">Day</th><th className="text-right">Covers</th><th className="text-right">Avg Check</th><th className="text-right">Revenue</th><th className="text-right">Occ %</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(r => {
            const gap = r.occ_pct < 55
            return (
              <tr key={r.day} className={gap ? 'bg-amber-50' : ''}>
                <td className="py-1.5 font-semibold text-navy">{r.day}</td>
                <td className="text-right text-slate-600">{r.covers}</td>
                <td className="text-right text-slate-600">${r.avg_check}</td>
                <td className="text-right text-slate-600">${r.revenue.toLocaleString()}</td>
                <td className={`text-right font-semibold ${gap ? 'text-amber-700' : 'text-slate-700'}`}>{r.occ_pct}%</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RooftopDowCard({ rows, chart }: { rows: RooftopDow[]; chart?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5">
      <h2 className="font-bold text-navy">The Rooftop at Bay Street Inn — Day of Week</h2>
      <p className="text-xs text-slate-500 mb-3">Thursday–Sunday operations · 55-guest capacity.</p>
      {chart && (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={rows} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="day" tick={{ fontSize: 10 }} tickFormatter={(d: string) => d.slice(0, 3)} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(1)}k`} />
            <Tooltip formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Revenue']} />
            <Bar dataKey="revenue" fill="#1A3A5C" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
      <table className="w-full text-xs mt-2">
        <thead className="text-[10px] uppercase tracking-wider text-slate-400">
          <tr><th className="text-left py-1">Day</th><th className="text-right">Guests</th><th className="text-right">Avg Spend</th><th className="text-right">Revenue</th><th className="text-right">Occ %</th></tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(r => (
            <tr key={r.day}>
              <td className="py-1.5 font-semibold text-navy">{r.day}</td>
              <td className="text-right text-slate-600">{r.guests}</td>
              <td className="text-right text-slate-600">${r.avg_spend}</td>
              <td className="text-right text-slate-600">${r.revenue.toLocaleString()}</td>
              <td className="text-right font-semibold text-slate-700">{r.occ_pct}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

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
        No recommendations right now. Your F&amp;B schedule is well-tuned to current demand.
      </div>
    )
  }
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5 space-y-3">
      <h2 className="font-bold text-navy">{title}</h2>
      {recs.map((r, i) => {
        const high = (r.priority || '').toUpperCase() === 'HIGH'
        return (
          <div key={i} className={`rounded-lg p-3 border-l-4 ${high ? 'border-coral bg-coral/5' : 'border-gold bg-gold/5'}`}>
            <div className="flex items-baseline justify-between gap-2">
              <div>
                <span className={`text-[9px] uppercase font-bold tracking-wide px-1.5 py-0.5 rounded ${high ? 'bg-coral text-white' : 'bg-gold text-white'}`}>{r.priority}</span>
                <span className="ml-2 font-semibold text-navy text-sm">{r.title}</span>
              </div>
              <span className="text-[10px] text-slate-500">{r.date}</span>
            </div>
            <div className="text-[11px] text-slate-700 mt-1.5 leading-snug">{r.action}</div>
            <div className="flex items-baseline justify-between mt-2">
              <span className="text-xs font-bold text-sage-dark">{r.lift_label}</span>
              <button onClick={() => window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: 'calendar' }))}
                className="text-[10px] text-navy hover:underline">Apply to Calendar →</button>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function PrivateEventCalculator({ defaultOutlet = 'rooftop_bar' }: { defaultOutlet?: string }) {
  const [outletId, setOutletId]     = useState(defaultOutlet)
  const [guestCount, setGuestCount] = useState(50)
  const [eventDate, setEventDate]   = useState(new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10))
  const [hours, setHours]           = useState(4)
  const [result, setResult]         = useState<any>(null)
  const [busy, setBusy]             = useState(false)

  async function calculate(g = guestCount) {
    setBusy(true)
    const r = await fetch('/api/fnb/private-event', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ outlet_id: outletId, guest_count: g, hours, event_date: eventDate }),
    })
    setResult(await r.json())
    setBusy(false)
  }

  // Show a sample 50-guest calculation immediately on mount.
  useEffect(() => { calculate(50) }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <details open className="bg-white rounded-xl border border-slate-100 p-4 text-sm">
      <summary className="cursor-pointer font-bold text-navy">Private Event / Buyout Calculator</summary>
      <div className="mt-3 space-y-2 text-xs">
        <label className="block">
          <div className="text-slate-500 font-semibold mb-0.5">Outlet</div>
          <select className="w-full border border-slate-200 rounded px-2 py-1.5" value={outletId} onChange={e => setOutletId(e.target.value)}>
            <option value="rsc_restaurant">The Parlor</option>
            <option value="rooftop_bar">The Rooftop</option>
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
        <button onClick={() => calculate()} disabled={busy} className="w-full bg-navy text-white font-bold py-2 rounded mt-2 disabled:opacity-60">
          {busy ? 'Calculating…' : 'Get Pricing'}
        </button>
        {result?.pricing && (
          <div className="bg-cream border border-gold/30 rounded-lg p-3 mt-3 space-y-1">
            <div className="text-[10px] uppercase text-slate-400 font-bold">Sample · {result.guest_count} guests</div>
            <div className="flex justify-between"><span className="text-slate-500">Recommended rate</span><strong className="text-navy text-base">${(result.pricing.recommended_rate || result.pricing.recommended_total || 0).toLocaleString()}</strong></div>
            {result.pricing.buyout_rate && <div className="flex justify-between"><span className="text-slate-500">Buyout rate</span><span>${result.pricing.buyout_rate.toLocaleString()}</span></div>}
            {result.pricing.per_head_equivalent && <div className="flex justify-between"><span className="text-slate-500">Per-head equivalent</span><span>${result.pricing.per_head_equivalent.toFixed(2)}</span></div>}
            {result.pricing.minimum_spend && <div className="flex justify-between"><span className="text-slate-500">Minimum spend</span><span>${result.pricing.minimum_spend.toLocaleString()}</span></div>}
            {result.demand_score != null && <div className="text-[10px] text-slate-500 mt-1">Demand on {result.event_date}: <strong>{result.demand_score}</strong> ({result.demand_label}){result.pricing.premium_applied && <span className="ml-1 text-gold-dark font-bold">★ Premium applied</span>}</div>}
          </div>
        )}
      </div>
    </details>
  )
}

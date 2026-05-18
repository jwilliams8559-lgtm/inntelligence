import { useEffect, useState } from 'react'
import { format, subDays, addDays, startOfMonth, endOfMonth, addMonths } from 'date-fns'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, ReferenceArea, Legend,
} from 'recharts'
import { supabase } from '../lib/supabase'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

// ── D1: Optimization Recommendations panel ──
interface OptRecs {
  midweek_specials: { triggered: boolean; message: string; est_uplift?: number }
  rate_alerts: { type: string; icon: string; title: string; message: string; est_uplift: number }[]
  package_opportunities: { icon: string; name: string; components: string;
    upsell_price: number; take_rate_pct: number; best_date: string;
    est_uplift_monthly: number; action: string }[]
  total_est_uplift: number
}

function OptimizationRecsPanel() {
  const [recs, setRecs] = useState<OptRecs | null>(null)
  useEffect(() => {
    fetch('/api/optimization-recommendations').then(r => r.json()).then(setRecs).catch(() => setRecs(null))
  }, [])
  if (!recs) return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 text-sm text-slate-400">
      Loading optimization recommendations…
    </div>
  )
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-bold text-navy">Optimization Recommendations</h2>
        {recs.total_est_uplift > 0 && (
          <span className="bg-sage/15 text-sage text-xs font-bold px-2.5 py-1 rounded-full">
            +${recs.total_est_uplift.toLocaleString()}/mo est. uplift
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          {/* Card 1 — Midweek */}
          <div className={`rounded-lg p-3 border ${recs.midweek_specials.triggered ? 'border-gold/30 bg-gold/5' : 'border-sage/20 bg-sage/5'}`}>
            <div className="font-semibold text-navy text-sm">
              {recs.midweek_specials.triggered ? '⚠ Midweek Special Triggered' : '✓ Midweek Specials'}
            </div>
            <div className="text-xs text-slate-600 mt-1">{recs.midweek_specials.message}</div>
          </div>
          {/* Cards 2-4 — Rate alerts */}
          {recs.rate_alerts.map((a, i) => (
            <div key={i} className="rounded-lg p-3 border border-navy/10 bg-cream">
              <div className="font-semibold text-navy text-sm">{a.icon} {a.title}</div>
              <div className="text-xs text-slate-600 mt-1">{a.message}</div>
              {a.est_uplift > 0 && (
                <div className="text-[11px] text-sage font-semibold mt-1">→ +${a.est_uplift}/mo uplift</div>
              )}
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
            Package Opportunities · top 3
          </div>
          {recs.package_opportunities.map((p, i) => (
            <div key={i} className="rounded-lg p-3 border border-slate-200 bg-white">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-semibold text-navy text-sm">{p.icon} {p.name}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{p.components}</div>
                </div>
                <span className="text-[11px] bg-sage/15 text-sage font-bold px-2 py-0.5 rounded">
                  +${p.est_uplift_monthly.toLocaleString()}/mo
                </span>
              </div>
              <div className="text-[11px] text-gold font-medium italic mt-1.5">→ {p.action}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── D4: Revenue Streams summary ──
function RevenueStreamsPanel({ propertyTotalRooms }: { propertyTotalRooms: number }) {
  const [packages, setPackages] = useState<any[]>([])
  const [giftShop, setGiftShop] = useState<any[]>([])
  const [fb,       setFb]       = useState<any>(null)
  const [avgRate,  setAvgRate]  = useState<number>(0)
  useEffect(() => {
    fetch('/api/packages').then(r => r.json()).then(setPackages).catch(() => setPackages([]))
    fetch('/api/gift-shop').then(r => r.json()).then(setGiftShop).catch(() => setGiftShop([]))
    fetch('/api/fb-summary').then(r => r.json()).then(setFb).catch(() => setFb(null))
    fetch('/api/rates').then(r => r.json()).then((rooms: any[]) => {
      if (rooms.length) setAvgRate(Math.round(rooms.reduce((s, r) => s + r.price, 0) / rooms.length))
    }).catch(() => {})
  }, [])
  const roomRev = Math.round(avgRate * propertyTotalRooms * 0.75 * 30)
  const pkgRev  = packages.filter(p => p.active).reduce((s, p) => s + (p.est_monthly_rev || 0), 0)
  const shopRev = giftShop.reduce((s, c) => s + (c.est_monthly_rev || 0), 0)
  const fbRev   = fb?.total ?? 0
  const total   = roomRev + pkgRev + shopRev + fbRev

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <h2 className="font-bold text-navy mb-3">Revenue Streams · Monthly Projection</h2>
      <div className="space-y-1.5 text-sm">
        <Row label="Room Revenue (proj.)"   value={roomRev}  locked={false} description={`${propertyTotalRooms} rooms · 75% occupancy · avg $${avgRate}`} />
        <LockedFeature featureName="F&B Revenue Module" featureKey="fb_module"
          description="Track restaurant, bar, and private event revenue alongside room revenue. Includes Ribaut Social Club covers, bar sales, and event nights.">
          <Row label="F&B Revenue (proj.)"   value={fbRev}   locked={false} description={fb ? `Restaurant + bar + ${fb.config?.event_nights_per_month ?? 0} event nights` : ''} />
        </LockedFeature>
        <LockedFeature featureName="Package Revenue Module" featureKey="packages_module"
          description="Optimize add-on package pricing: Romance, Anniversary, Spa, Adventure, Breakfast, Pet, Sunset Cruise.">
          <Row label="Package Revenue"      value={pkgRev}   locked={false} description={`${packages.filter(p => p.active).length} active packages`} />
        </LockedFeature>
        <LockedFeature featureName="Gift Shop Module" featureKey="gift_shop_module"
          description="Sync inventory and sales from Square POS or Shopify — track Lowcountry food, branded merch, artisan goods, wines & spirits.">
          <Row label="Gift Shop Revenue"    value={shopRev}  locked={false} description={`${giftShop.length} categories tracked`} />
        </LockedFeature>
        <div className="border-t border-slate-200 pt-2 mt-1 flex justify-between items-center">
          <span className="text-sm font-bold text-navy uppercase tracking-wider">Total Projected</span>
          <span className="text-2xl font-bold text-gold">${total.toLocaleString()}/mo</span>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value, locked, description }:
  { label: string; value: number; locked: boolean; description?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <span className="text-slate-700">{label}</span>
        {description && <span className="text-[11px] text-slate-400 ml-2">· {description}</span>}
      </div>
      <span className={`font-bold ${locked ? 'text-slate-300' : 'text-sage'}`}>
        {locked ? '—' : `$${value.toLocaleString()}`}
      </span>
    </div>
  )
}

export default function DemandDashboard({ tenant, property, pendingCount }: Props) {
  const [occData,      setOccData]      = useState<any[]>([])
  const [monthlyRev,   setMonthlyRev]   = useState<any[]>([])
  const [paceData,     setPaceData]     = useState<any[]>([])
  const [kpis,         setKpis]         = useState({ occ: 0, occLy: 0, revpar: 0, revparLy: 0, rev: 0, revLy: 0 })
  const [loading,      setLoading]      = useState(true)

  const today = new Date()

  useEffect(() => {
    async function load() {
      setLoading(true)
      const start90 = format(subDays(today, 90), 'yyyy-MM-dd')
      const end90   = format(addDays(today, 90), 'yyyy-MM-dd')
      const startLy = format(subDays(today, 90 + 365), 'yyyy-MM-dd')
      const endLy   = format(subDays(today, 365), 'yyyy-MM-dd')

      const [{ data: occNow }, { data: occLy }, { data: bookings }] = await Promise.all([
        supabase.from('occupancy_snapshots')
          .select('snapshot_date,occupancy_rate,adr,revpar')
          .eq('property_id', property.id)
          .gte('snapshot_date', start90)
          .lte('snapshot_date', end90)
          .order('snapshot_date'),

        supabase.from('occupancy_snapshots')
          .select('snapshot_date,occupancy_rate,adr,revpar')
          .eq('property_id', property.id)
          .gte('snapshot_date', startLy)
          .lte('snapshot_date', endLy)
          .order('snapshot_date'),

        supabase.from('bookings')
          .select('check_in,rate_paid,booked_at')
          .eq('property_id', property.id)
          .order('check_in'),
      ])

      // Aggregate occupancy by week for line chart
      const byDate = new Map<string, number[]>()
      occNow?.forEach(r => {
        const week = format(new Date(r.snapshot_date), 'MMM d')
        if (!byDate.has(week)) byDate.set(week, [])
        byDate.get(week)!.push(r.occupancy_rate)
      })
      const byDateLy = new Map<string, number[]>()
      occLy?.forEach(r => {
        const week = format(addDays(new Date(r.snapshot_date), 365), 'MMM d')
        if (!byDateLy.has(week)) byDateLy.set(week, [])
        byDateLy.get(week)!.push(r.occupancy_rate)
      })

      // Build 60-day occupancy chart
      const occ60: any[] = []
      for (let i = -30; i <= 90; i += 3) {
        const d    = addDays(today, i)
        const dStr = format(d, 'MMM d')
        const vals    = byDate.get(dStr)
        const valsLy  = byDateLy.get(dStr)
        occ60.push({
          date:  dStr,
          occ:   vals  ? Math.round(vals.reduce((a, b) => a + b, 0)  / vals.length  * 100) : null,
          occLy: valsLy? Math.round(valsLy.reduce((a, b) => a + b, 0) / valsLy.length * 100) : null,
          isFuture: i > 0,
        })
      }
      setOccData(occ60)

      // KPIs from this month's snapshots
      const monthStart = format(startOfMonth(today), 'yyyy-MM-dd')
      const monthEnd   = format(endOfMonth(today), 'yyyy-MM-dd')
      const monthNow   = occNow?.filter(r => r.snapshot_date >= monthStart && r.snapshot_date <= monthEnd) ?? []
      const monthLyD   = occLy?.filter(r => {
        const d = format(addDays(new Date(r.snapshot_date), 365), 'yyyy-MM-dd')
        return d >= monthStart && d <= monthEnd
      }) ?? []

      const avg = (arr: any[], key: string) =>
        arr.length ? arr.reduce((s, r) => s + r[key], 0) / arr.length : 0

      setKpis({
        occ:      Math.round(avg(monthNow, 'occupancy_rate') * 100),
        occLy:    Math.round(avg(monthLyD, 'occupancy_rate') * 100),
        revpar:   Math.round(avg(monthNow, 'revpar')),
        revparLy: Math.round(avg(monthLyD, 'revpar')),
        rev:      Math.round(bookings?.filter(b => b.check_in >= monthStart && b.check_in <= monthEnd)
                    .reduce((s, b) => s + b.rate_paid, 0) ?? 0),
        revLy:    Math.round(bookings?.filter(b => {
                    const d = format(addDays(new Date(b.check_in), 365), 'yyyy-MM-dd')
                    return d >= monthStart && d <= monthEnd
                  }).reduce((s, b) => s + b.rate_paid, 0) ?? 0),
      })

      // Monthly revenue bar chart (next 6 months)
      const rev6: any[] = []
      for (let m = 0; m < 6; m++) {
        const mStart = format(startOfMonth(addMonths(today, m)), 'yyyy-MM-dd')
        const mEnd   = format(endOfMonth(addMonths(today, m)), 'yyyy-MM-dd')
        const month  = format(addMonths(today, m), 'MMM yy')
        const snapshots = occNow?.filter(r => r.snapshot_date >= mStart && r.snapshot_date <= mEnd) ?? []
        const avgRevpar = snapshots.length ? snapshots.reduce((s, r) => s + r.revpar, 0) / snapshots.length : 0
        // Estimate monthly revenue: avg RevPAR * 15 rooms * days in month
        const daysInMonth = endOfMonth(addMonths(today, m)).getDate()
        rev6.push({ month, revenue: Math.round(avgRevpar * 15 * daysInMonth) })
      }
      setMonthlyRev(rev6)

      // Booking pace: bookings made in last 14 days for upcoming 30 days
      const pace: any[] = []
      for (let i = 1; i <= 30; i++) {
        const d    = addDays(today, i)
        const dStr = format(d, 'MMM d')
        const wStr = format(d, 'yyyy-MM-dd')
        const curr = bookings?.filter(b => b.check_in === wStr).length ?? 0
        const ly   = bookings?.filter(b =>
          format(addDays(new Date(b.check_in), 365), 'yyyy-MM-dd') === wStr
        ).length ?? 0
        pace.push({ date: dStr, current: curr, lastYear: ly })
      }
      setPaceData(pace)

      setLoading(false)
    }
    load()
  }, [property.id])

  const delta = (now: number, ly: number) => {
    if (!ly) return null
    const pct = ((now - ly) / ly * 100).toFixed(0)
    return { pct: Number(pct), label: `${Number(pct) >= 0 ? '+' : ''}${pct}% vs LY` }
  }

  function KpiCard({ label, value, ly, prefix = '', suffix = '' }: any) {
    const d = delta(value, ly)
    return (
      <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{label}</div>
        <div className="text-3xl font-bold text-navy">{prefix}{value?.toLocaleString()}{suffix}</div>
        {d && (
          <div className={`text-xs mt-1 font-semibold ${d.pct >= 0 ? 'text-sage' : 'text-coral'}`}>
            {d.label}
          </div>
        )}
        <div className="text-xs text-slate-300 mt-0.5">LY: {prefix}{ly?.toLocaleString()}{suffix}</div>
      </div>
    )
  }

  // Water Festival band boundaries for charts
  const wfStart = format(new Date(today.getFullYear(), 6, 17), 'MMM d')
  const wfEnd   = format(new Date(today.getFullYear(), 6, 26), 'MMM d')

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-navy border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 space-y-5">
      {/* Alert banner */}
      <div className="bg-gold/10 border border-gold/30 rounded-xl px-5 py-3 flex items-center gap-3">
        <span className="text-gold text-xl">★</span>
        <div className="flex-1">
          <span className="font-bold text-navy">Peak Demand — Water Festival July 17–26</span>
          <span className="text-slate-600 text-sm ml-2">
            Waterfront Suite peak recommendation $535/night (Mon Jul 20, 3-night min).
          </span>
          {pendingCount > 0 && (
            <span className="ml-2 bg-amber-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {pendingCount} pending
            </span>
          )}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="This Month Occupancy" value={kpis.occ} ly={kpis.occLy} suffix="%" />
        <KpiCard label="RevPAR" value={kpis.revpar} ly={kpis.revparLy} prefix="$" />
        <KpiCard label="Month Revenue" value={kpis.rev} ly={kpis.revLy} prefix="$" />
        <div className="bg-white rounded-xl p-5 shadow-sm border border-slate-100">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Pending Approvals</div>
          <div className="text-3xl font-bold text-amber-500">{pendingCount}</div>
          <div className="text-xs text-slate-400 mt-1">rate recommendations</div>
        </div>
      </div>

      {/* 90-day occupancy chart */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-navy">90-Day Occupancy Forecast vs Last Year</h2>
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-navy inline-block" /> This Year</span>
            <span className="flex items-center gap-1"><span className="w-4 h-0.5 border-t-2 border-dashed border-slate-300 inline-block" /> Last Year</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-gold/30 inline-block rounded-sm" /> Water Festival</span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={occData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false}
                   interval={Math.floor(occData.length / 8)} />
            <YAxis tick={{ fontSize: 10 }} domain={[0, 100]}
                   tickFormatter={v => `${v}%`} />
            <Tooltip formatter={(v: any) => `${v}%`} />
            <ReferenceArea x1={wfStart} x2={wfEnd} fill="#A07830" fillOpacity={0.15}
                           label={{ value: 'Water Festival', position: 'top', fontSize: 10, fill: '#A07830' }} />
            <ReferenceLine x={format(today, 'MMM d')} stroke="#CBD5E1" strokeDasharray="4 2" label={{ value: 'Today', position: 'top', fontSize: 9, fill: '#94A3B8' }} />
            <Line type="monotone" dataKey="occ"   stroke="#1A3A5C" strokeWidth={2} dot={false} name="This Year" />
            <Line type="monotone" dataKey="occLy" stroke="#94A3B8" strokeWidth={1.5} strokeDasharray="4 2" dot={false} name="Last Year" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Monthly revenue */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
          <h2 className="font-bold text-navy mb-4">Monthly Revenue Forecast</h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={monthlyRev} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} tickLine={false} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: any) => `$${v.toLocaleString()}`} />
              <Bar dataKey="revenue" fill="#1A3A5C" radius={[4, 4, 0, 0]} name="Revenue" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Booking pace */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
          <h2 className="font-bold text-navy mb-4">Booking Pace vs Last Year</h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={paceData} margin={{ top: 0, right: 0, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} interval={6} />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip />
              <Legend iconType="square" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="current"  fill="#1A3A5C" radius={[2, 2, 0, 0]} name="This Year" />
              <Bar dataKey="lastYear" fill="#CBD5E1" radius={[2, 2, 0, 0]} name="Last Year" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* D1 — Optimization Recommendations */}
      <LockedFeature
        featureName="Optimization Recommendations"
        featureKey="optimization_engine"
        description="AI-generated weekly action plan: midweek specials, rate floor alerts, competitor pricing gaps, and package opportunities. Estimated to add $1,500–$3,000/mo for a typical 14-room inn."
      >
        <OptimizationRecsPanel />
      </LockedFeature>

      {/* D4 — Revenue Streams summary */}
      <RevenueStreamsPanel propertyTotalRooms={14} />
    </div>
  )
}

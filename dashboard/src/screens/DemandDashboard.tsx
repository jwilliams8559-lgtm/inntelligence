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

// ── D2: Gap-Night Optimizer ──
interface GapNight {
  date: string; room_id: string; room_name: string
  gap_length_nights: number
  booking_before_end: string; booking_after_start: string
  recommended_action: string; recommended_price: number
  urgency: 'immediate' | 'soon' | 'planning'
}
interface MinStayRec {
  room_id: string; start_date: string; end_date: string
  recommended_min_stay: number; reason: string; demand_score: number
}

function UrgencyBadge({ urgency }: { urgency: GapNight['urgency'] }) {
  const cfg = {
    immediate: { cls: 'bg-coral text-white',         label: 'IMMEDIATE' },
    soon:      { cls: 'bg-amber-400 text-white',     label: 'SOON' },
    planning:  { cls: 'bg-slate-300 text-slate-700', label: 'PLANNING' },
  }[urgency]
  return <span className={`text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${cfg.cls}`}>{cfg.label}</span>
}

function GapNightPanel() {
  const [gaps, setGaps] = useState<GapNight[] | null>(null)
  const [minStay, setMinStay] = useState<MinStayRec[] | null>(null)
  const [showPlanning, setShowPlanning] = useState(false)
  useEffect(() => {
    fetch('/api/los/gaps').then(r => r.json()).then(setGaps).catch(() => setGaps([]))
    fetch('/api/los/min-stay').then(r => r.json()).then(setMinStay).catch(() => setMinStay([]))
  }, [])
  if (!gaps || !minStay) return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 text-sm text-slate-400">
      Loading gap-night analysis…
    </div>
  )

  const byUrgency = {
    immediate: gaps.filter(g => g.urgency === 'immediate'),
    soon:      gaps.filter(g => g.urgency === 'soon'),
    planning:  gaps.filter(g => g.urgency === 'planning'),
  }

  // Dedupe min-stay recs by date+min-stay (engine returns one per room — collapse)
  const minByDate = new Map<string, MinStayRec & { room_count: number }>()
  for (const m of minStay) {
    const key = `${m.start_date}::${m.recommended_min_stay}`
    const cur = minByDate.get(key)
    if (cur) cur.room_count += 1
    else minByDate.set(key, { ...m, room_count: 1 })
  }
  const minRows = [...minByDate.values()].sort((a, b) => a.start_date.localeCompare(b.start_date)).slice(0, 8)

  function GapRow({ g }: { g: GapNight }) {
    return (
      <div className="px-3 py-2 text-xs">
        <div className="flex items-baseline justify-between gap-2">
          <div className="font-semibold text-navy">{g.date} · {g.room_name}</div>
          <div className="flex items-center gap-2">
            <span className="text-slate-500 text-[10px]">{g.gap_length_nights}-night gap</span>
            <UrgencyBadge urgency={g.urgency} />
          </div>
        </div>
        <div className="text-slate-600 mt-0.5">{g.recommended_action}</div>
        <div className="flex items-center justify-between mt-1">
          <strong className="text-sage-dark">Apply ${g.recommended_price}</strong>
          <span className="text-[10px] text-slate-500">After {g.booking_before_end} checkout · next stay {g.booking_after_start}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className="flex items-baseline justify-between mb-3 flex-wrap gap-2">
        <h2 className="font-bold text-navy">Gap-Night Optimizer</h2>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-coral font-bold">{byUrgency.immediate.length} immediate</span>
          <span className="text-amber-600 font-bold">{byUrgency.soon.length} soon</span>
          <span className="text-slate-500">{byUrgency.planning.length} planning</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs font-semibold text-slate-600 mb-2">Gap nights · next 60 days</div>
          <div className="max-h-96 overflow-auto divide-y divide-slate-100 border border-slate-100 rounded-lg">
            {byUrgency.immediate.length === 0 && byUrgency.soon.length === 0 && (
              <div className="px-3 py-3 text-xs text-slate-400">No immediate or upcoming gaps. ✓</div>
            )}
            {byUrgency.immediate.map((g, i) => <GapRow key={`i${i}`} g={g} />)}
            {byUrgency.soon.map((g, i)      => <GapRow key={`s${i}`} g={g} />)}
            {byUrgency.planning.length > 0 && (
              <div className="px-3 py-2 text-xs">
                <button onClick={() => setShowPlanning(!showPlanning)}
                  className="text-slate-500 font-semibold hover:text-navy">
                  {showPlanning ? '▼' : '▶'} {byUrgency.planning.length} planning-horizon gaps
                </button>
              </div>
            )}
            {showPlanning && byUrgency.planning.map((g, i) => <GapRow key={`p${i}`} g={g} />)}
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-600 mb-2">Minimum-stay recommendations</div>
          {minRows.length === 0 ? (
            <div className="text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg p-3">
              No high-demand dates require min-stay overrides.
            </div>
          ) : (
            <div className="space-y-2">
              {minRows.map((r, i) => (
                <div key={i} className="border border-gold/30 bg-gold/5 rounded-lg p-3 text-xs">
                  <div className="flex items-baseline justify-between">
                    <div className="font-semibold text-navy">{r.start_date}</div>
                    <div className="text-[10px] text-gold-dark font-bold">Demand {r.demand_score}</div>
                  </div>
                  <div className="text-slate-600 mt-0.5">{r.reason}</div>
                  <div className="text-gold-dark font-semibold mt-1">→ Set {r.recommended_min_stay}-night minimum ({r.room_count} room types)</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── D3: Weather Intelligence ──
interface WeatherDay {
  date: string; name: string; temp: number; temp_unit: string
  wind: string; short: string; detailed: string
  icon: string; good_weather: boolean; demand_blend: number
}
interface WeatherSummary {
  forecast: WeatherDay[]
  good_day_count?: number
  good_day_pct?: number
  data_source: string; fetched_at: number
  error?: string
}

function WeatherPanel() {
  const [w, setW] = useState<WeatherSummary | null>(null)
  useEffect(() => {
    fetch('/api/weather').then(r => r.json()).then(setW).catch(() => setW(null))
  }, [])
  if (!w) return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 text-sm text-slate-400">
      Loading weather…
    </div>
  )
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className="flex items-baseline justify-between mb-3 flex-wrap gap-2">
        <h2 className="font-bold text-navy">Weather Intelligence — Next 7 Days</h2>
        <div className="text-xs text-slate-500">
          {w.good_day_count != null && `${w.good_day_count}/${w.forecast.length} good days (${w.good_day_pct}%)`}
          {' · source: '}<span className="text-slate-400">{w.data_source}</span>
        </div>
      </div>
      {w.error ? (
        <div className="text-xs text-coral">⚠ {w.error}</div>
      ) : (
        <div className="grid grid-cols-7 gap-2">
          {w.forecast.map(d => (
            <div key={d.date} className={`rounded-lg p-2 border text-center ${
              d.demand_blend > 0  ? 'border-sage/30 bg-sage/5'
              : d.demand_blend < 0 ? 'border-coral/30 bg-coral/5'
                                     : 'border-slate-100 bg-cream'
            }`} title={d.detailed}>
              <div className="text-[10px] text-slate-500">{d.name.length > 8 ? d.name.slice(0,3) : d.name}</div>
              <div className="text-2xl">{d.icon}</div>
              <div className="text-sm font-bold text-navy">{d.temp}°</div>
              <div className="text-[9px] text-slate-500 leading-tight mt-0.5 h-6 line-clamp-2">{d.short}</div>
              {d.demand_blend !== 0 && (
                <div className={`text-[10px] font-bold mt-1 ${d.demand_blend > 0 ? 'text-sage-dark' : 'text-coral'}`}>
                  {d.demand_blend > 0 ? '↑' : '↓'} {(Math.abs(d.demand_blend) * 100).toFixed(0)}% demand
                </div>
              )}
            </div>
          ))}
        </div>
      )}
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

// ── CPP Section 6: Price Bands ──
interface PriceBandRow {
  room_name: string; base_rate: number
  min_rate: number; max_rate: number
  median_rate: number; p25_rate: number; p75_rate: number
  avg_rate: number
  rate_distribution: { below_base: number; at_base: number; above_base: number }
  premium_nights: number; band_width: number
  comp_avg: number; pct_vs_comp_avg: number
}
function PriceBandsPanel() {
  const [data, setData] = useState<Record<string, PriceBandRow> | null>(null)
  useEffect(() => {
    fetch('/api/price-bands').then(r => r.json()).then(setData).catch(() => setData(null))
  }, [])
  if (!data) return null
  const rows = Object.entries(data)
  const globalMin = Math.min(...rows.map(([, r]) => r.min_rate))
  const globalMax = Math.max(...rows.map(([, r]) => r.max_rate))
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <h2 className="font-bold text-navy mb-1">Rate Distribution — Next 90 Days</h2>
      <p className="text-xs text-slate-500 mb-3">
        Where each room's rates land across the forward 90-day window. Narrow bands = pricing discipline;
        wide bands = volatility driven by demand spikes and weekend swings.
      </p>
      <div className="space-y-3">
        {rows.map(([id, r]) => {
          const range = globalMax - globalMin || 1
          const pctFrom = (v: number) => ((v - globalMin) / range) * 100
          return (
            <div key={id}>
              <div className="flex items-baseline justify-between mb-1">
                <strong className="text-navy text-sm">{r.room_name}</strong>
                <span className="text-[11px] text-slate-500">
                  ${r.min_rate} – ${r.max_rate} · median ${r.median_rate}
                  <span className={`ml-2 ${r.pct_vs_comp_avg >= 0 ? 'text-sage' : 'text-coral'} font-semibold`}>
                    {r.pct_vs_comp_avg >= 0 ? '+' : ''}{r.pct_vs_comp_avg.toFixed(0)}% vs comp avg ${r.comp_avg}
                  </span>
                </span>
              </div>
              {/* Box plot style band */}
              <div className="relative h-6 bg-slate-100 rounded">
                {/* IQR p25-p75 (gold band) */}
                <div className="absolute top-0 bottom-0 bg-gold/30 rounded"
                  style={{ left: `${pctFrom(r.p25_rate)}%`, width: `${pctFrom(r.p75_rate) - pctFrom(r.p25_rate)}%` }} />
                {/* whiskers min-max line */}
                <div className="absolute top-1/2 -translate-y-1/2 h-px bg-slate-400"
                  style={{ left: `${pctFrom(r.min_rate)}%`, width: `${pctFrom(r.max_rate) - pctFrom(r.min_rate)}%` }} />
                {/* base rate marker */}
                <div className="absolute top-0 bottom-0 w-0.5 bg-navy"
                  style={{ left: `${pctFrom(r.base_rate)}%` }} title={`Base rate $${r.base_rate}`} />
                {/* median */}
                <div className="absolute top-0 bottom-0 w-0.5 bg-coral"
                  style={{ left: `${pctFrom(r.median_rate)}%` }} title={`Median $${r.median_rate}`} />
                {/* comp avg */}
                <div className="absolute top-0 bottom-0 w-0.5 bg-sage border-dashed"
                  style={{ left: `${pctFrom(r.comp_avg)}%` }} title={`Comp avg $${r.comp_avg}`} />
                {/* min/max labels */}
                <span className="absolute -bottom-4 text-[9px] text-slate-400"
                  style={{ left: `${pctFrom(r.min_rate)}%`, transform: 'translateX(-50%)' }}>
                  ${r.min_rate}
                </span>
                <span className="absolute -bottom-4 text-[9px] text-slate-400"
                  style={{ left: `${pctFrom(r.max_rate)}%`, transform: 'translateX(-50%)' }}>
                  ${r.max_rate}
                </span>
              </div>
              <div className="text-[10px] text-slate-500 mt-5">
                {r.premium_nights} nights above 20% premium · {r.rate_distribution.at_base} at base · {r.rate_distribution.below_base} below base
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex items-center gap-3 mt-3 text-[10px] text-slate-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-gold/60" /> P25–P75 (typical range)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-3 bg-navy" /> Base rate</span>
        <span className="flex items-center gap-1"><span className="w-2 h-3 bg-coral" /> Median</span>
        <span className="flex items-center gap-1"><span className="w-2 h-3 bg-sage" /> Comp avg</span>
      </div>
    </div>
  )
}

// ── Section E: Dual revenue forecast ──
interface DualForecast {
  labels: string[]
  confirmed_revenue: number[]
  projected_additional: number[]
  total_projected: number[]
  confirmed_occupancy_pct: number[]
  projected_occupancy_pct: number[]
  avg_confirmed_daily: number
  avg_total_daily: number
  summary: { confirmed_90day_total: number; projected_90day_total: number; combined_90day_total: number }
  monthly: { month_key: string; month_label: string; confirmed: number; projected: number;
    combined: number; projected_occ: number; is_water_fest: boolean; days: number }[]
}

function DualRevenueForecast() {
  const [data, setData] = useState<DualForecast | null>(null)
  useEffect(() => {
    fetch('/api/forecast/dual').then(r => r.json()).then(setData).catch(() => setData(null))
  }, [])
  if (!data) return null

  // Build chart-friendly arrays
  const chartData = data.labels.map((label, i) => ({
    label,
    confirmed:  data.confirmed_revenue[i],
    projected:  data.projected_additional[i],
    total:      data.total_projected[i],
    conf_occ:   data.confirmed_occupancy_pct[i],
    proj_occ:   data.projected_occupancy_pct[i],
  }))

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h2 className="font-bold text-navy">90-Day Revenue Forecast — Confirmed vs Projected</h2>
        <div className="text-xs text-slate-600 space-x-4">
          <span><span className="text-slate-500">Confirmed:</span> <span className="font-bold text-navy">${data.summary.confirmed_90day_total.toLocaleString()}</span></span>
          <span><span className="text-slate-500">Projected:</span> <span className="font-bold text-gold">${data.summary.projected_90day_total.toLocaleString()}</span></span>
          <span><span className="text-slate-500">Combined:</span> <span className="font-bold text-sage">${data.summary.combined_90day_total.toLocaleString()}</span></span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={9} tickLine={false} />
          <YAxis tick={{ fontSize: 9 }} tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
          <Tooltip formatter={(v: any) => `$${v.toLocaleString()}`} />
          <Legend iconType="square" iconSize={9} wrapperStyle={{ fontSize: 10 }} />
          <Bar dataKey="confirmed" stackId="rev" fill="#1A3A5C" name="Confirmed Bookings" />
          <Bar dataKey="projected" stackId="rev" fill="#A07830" name="Projected Additional" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      {/* Occupancy chart */}
      <div className="mt-4">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1">
          Occupancy: Confirmed vs Projected · target zone 70-85%
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={9} tickLine={false} />
            <YAxis tick={{ fontSize: 9 }} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip formatter={(v: any) => `${v}%`} />
            <ReferenceArea y1={70} y2={85} fill="#A07830" fillOpacity={0.08} />
            <ReferenceLine y={70} stroke="#A07830" strokeDasharray="4 3" />
            <ReferenceLine y={85} stroke="#A07830" strokeDasharray="4 3" />
            <Legend iconType="square" iconSize={9} wrapperStyle={{ fontSize: 10 }} />
            <Line type="monotone" dataKey="conf_occ" stroke="#1A3A5C" strokeWidth={2} dot={false} name="Confirmed %" />
            <Line type="monotone" dataKey="proj_occ" stroke="#A07830" strokeWidth={2} dot={false} name="Projected %" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 12-month summary table */}
      <div className="mt-4 border-t border-slate-100 pt-3">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
          Monthly Summary (next 90 days)
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50">
              <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500">
                <th className="px-3 py-1.5">Month</th>
                <th className="px-2 py-1.5 text-right">Confirmed Rev</th>
                <th className="px-2 py-1.5 text-right">Projected Rev</th>
                <th className="px-2 py-1.5 text-right">Combined</th>
                <th className="px-2 py-1.5 text-right">Proj Occ %</th>
                <th className="px-2 py-1.5 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.monthly.map(m => {
                const confPct = m.combined > 0 ? Math.round((m.confirmed / m.combined) * 100) : 0
                const lowConf = confPct < 40
                return (
                  <tr key={m.month_key} className="border-t border-slate-100">
                    <td className="px-3 py-1.5 font-bold text-navy">
                      {m.month_label}
                      {m.is_water_fest && <span className="ml-1 text-gold" title="Water Festival">★</span>}
                    </td>
                    <td className="px-2 py-1.5 text-right text-navy">${m.confirmed.toLocaleString()}</td>
                    <td className="px-2 py-1.5 text-right text-gold">${m.projected.toLocaleString()}</td>
                    <td className="px-2 py-1.5 text-right font-bold text-sage">${m.combined.toLocaleString()}</td>
                    <td className="px-2 py-1.5 text-right">{m.projected_occ.toFixed(0)}%</td>
                    <td className={`px-2 py-1.5 text-[11px] ${lowConf ? 'text-amber-700 bg-amber-50/60' : 'text-slate-400'}`}>
                      {lowConf
                        ? `⚡ Low confirmed (${confPct}%) — last-minute fill pricing`
                        : `${confPct}% confirmed`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
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

      {/* E — Dual revenue forecast (confirmed vs projected) */}
      <DualRevenueForecast />

      {/* CPP Section 6 — Price Bands */}
      <PriceBandsPanel />

      {/* D1 — Optimization Recommendations */}
      <LockedFeature
        featureName="Optimization Recommendations"
        featureKey="optimization_engine"
        description="AI-generated weekly action plan: midweek specials, rate floor alerts, competitor pricing gaps, and package opportunities. Estimated to add $1,500–$3,000/mo for a typical 14-room inn."
      >
        <OptimizationRecsPanel />
      </LockedFeature>

      {/* D2 — Gap-Night Optimizer */}
      <LockedFeature
        featureName="Gap-Night Optimizer"
        featureKey="gap_night_analysis"
        description="Detects 1–2 night orphan gaps between bookings and recommends gap-fill discounts or minimum-stay enforcement to capture lost revenue."
      >
        <GapNightPanel />
      </LockedFeature>

      {/* D3 — Weather Intelligence */}
      <LockedFeature
        featureName="Weather Intelligence"
        featureKey="weather_intel"
        description="Seven-day NWS forecast layered onto your demand model. Sunny weekends nudge demand up; rain weekends pull it down. Free, no API key."
      >
        <WeatherPanel />
      </LockedFeature>

      {/* D4 — Revenue Streams summary */}
      <RevenueStreamsPanel propertyTotalRooms={14} />
    </div>
  )
}

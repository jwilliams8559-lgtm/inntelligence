import { useEffect, useState } from 'react'
import { format, addDays } from 'date-fns'
import { supabase } from '../lib/supabase'
import type { Tenant, Property, CompRate, CompetitorProp, RateRec, RoomType } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

function TierBadge({ tier }: { tier?: number | null }) {
  const config: Record<number, { label: string; cls: string }> = {
    1: { label: 'Direct Comp',     cls: 'bg-navy/10 text-navy' },
    2: { label: 'Upscale Hotel',   cls: 'bg-gold/15 text-gold-dark' },
    3: { label: 'Luxury Ref',      cls: 'bg-purple-100 text-purple-700' },
    4: { label: 'Budget Anchor',   cls: 'bg-slate-100 text-slate-500' },
  }
  const t = tier ?? 1
  const { label, cls } = config[t] ?? config[1]
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${cls}`}>
      {label}
    </span>
  )
}

type PropertyType = 'boutique_inn' | 'upscale_hotel' | 'luxury_resort' | 'airbnb_str' | 'budget_hotel'

// Mirrors PROPERTY_TYPES in config/settings.py — sources kept in sync manually.
const PROPERTY_TYPE_BY_NAME: Record<string, PropertyType> = {
  '607 Bay Inn':            'airbnb_str',
  '607 Bay':                'airbnb_str',
  'Airbnb Near Bay (avg)':  'airbnb_str',
  'Airbnb Near Bay':        'airbnb_str',
  'Bay Street Inn':         'airbnb_str',   // private residence — visually de-emphasized if still in data
  'Cuthbert House Inn':     'boutique_inn',
  'Cuthbert House':         'boutique_inn',
  'Rhett House Inn':        'boutique_inn',
  'Rhett House':            'boutique_inn',
  'Beaufort Inn':           'upscale_hotel',
  'The Beaufort Inn':       'upscale_hotel',
  'City Loft Hotel':        'upscale_hotel',
  'City Loft':              'upscale_hotel',
  'Montage Palmetto Bluff': 'luxury_resort',
  'Montage':                'luxury_resort',
  'Hampton Inn Beaufort':   'budget_hotel',
  'Hampton Inn':            'budget_hotel',
}

const PROPERTY_TYPE_BADGE: Record<PropertyType, { label: string; cls: string; tooltip?: string }> = {
  boutique_inn:  { label: 'Boutique Inn', cls: 'bg-sage/15 text-sage-dark' },
  upscale_hotel: { label: 'Hotel',        cls: 'bg-navy/10 text-navy' },
  luxury_resort: { label: 'Luxury Resort',cls: 'bg-gold/15 text-gold-dark' },
  budget_hotel:  { label: 'Budget Anchor',cls: 'bg-slate-100 text-slate-500' },
  airbnb_str:    { label: 'STR / Airbnb', cls: 'bg-amber-100 text-amber-800',
                   tooltip: 'Short-term rental — not a direct competitor. Boutique inns command a 40–60% premium over STRs once breakfast, service, and amenities are included.' },
}

const STR_TRUE_GUEST_COST_MULTIPLIER = 1.35

function PropertyTypeBadge({ ptype }: { ptype: PropertyType }) {
  const cfg = PROPERTY_TYPE_BADGE[ptype]
  return (
    <span title={cfg.tooltip} className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${cfg.cls} ${cfg.tooltip ? 'cursor-help' : ''}`}>
      {cfg.label}
    </span>
  )
}

function PriceLadder({
  yourRate, yourName, compRates, competitors, dateStr, dateLabel,
}: {
  yourRate: number | null
  yourName: string
  compRates: CompRate[]
  competitors: CompetitorProp[]
  dateStr:   string
  dateLabel: string
}) {
  const compMap = new Map(competitors.map(c => [c.id, c]))
  const dayRates = compRates.filter(r => r.rate_date === dateStr)

  // Dedupe by name — keep highest rate, preserve sold-out flag
  const dedup = new Map<string, { name: string; rate: number; tier: number; soldOut: boolean; ptype: PropertyType }>()
  dayRates.forEach(cr => {
    const comp = compMap.get(cr.competitor_id)
    if (!comp || cr.rate_amount == null) return
    const name = comp.competitor_name ?? comp.name ?? 'Competitor'
    const tier = comp.property_tier ?? 1
    const ptype = PROPERTY_TYPE_BY_NAME[name] ?? (tier === 4 ? 'budget_hotel' : tier === 3 ? 'luxury_resort' : tier === 2 ? 'upscale_hotel' : 'boutique_inn')
    const key  = name
    const cur  = dedup.get(key)
    if (!cur || cr.rate_amount > cur.rate) {
      dedup.set(key, { name, rate: cr.rate_amount, tier, ptype, soldOut: cr.is_sold_out || cur?.soldOut || false })
    } else if (cr.is_sold_out && cur) {
      cur.soldOut = true
    }
  })

  const entries: { name: string; rate: number; tier: number; ptype: PropertyType; soldOut: boolean; isYou: boolean }[] =
    [...dedup.values()].map(e => ({ ...e, isYou: false }))
  if (yourRate) entries.push({ name: yourName, rate: yourRate, tier: 0, ptype: 'boutique_inn', soldOut: false, isYou: true })
  entries.sort((a, b) => b.rate - a.rate)
  if (entries.length === 0) return null

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="font-bold text-navy text-sm">Price Ladder</h2>
        <span className="text-xs text-slate-400">{dateLabel}</span>
      </div>
      <div className="space-y-1">
        {entries.map((e, i) => {
          const isStr = e.ptype === 'airbnb_str'
          const rowBg = e.isYou ? 'bg-navy text-white'
                      : isStr   ? 'bg-amber-50 border-amber-200'
                      : e.ptype === 'luxury_resort' ? 'bg-gold/5 border-gold/15'
                      : e.ptype === 'boutique_inn'  ? 'bg-sage/5 border-sage/15'
                      : e.ptype === 'budget_hotel'  ? 'bg-slate-50 border-slate-100'
                                                      : 'bg-cream border-slate-100'
          const trueCost = isStr ? Math.round(e.rate * STR_TRUE_GUEST_COST_MULTIPLIER) : null
          return (
            <div key={i} className={`px-2.5 py-1.5 rounded-lg border ${rowBg}`}>
              <div className="flex items-center gap-2">
                <span className={`text-sm font-bold w-14 text-right
                  ${e.isYou ? 'text-gold'
                    : isStr ? 'text-amber-700 line-through'
                    : e.soldOut ? 'text-coral line-through'
                    : 'text-navy'}`}>
                  ${e.rate.toFixed(0)}
                </span>
                <span className={`flex-1 text-xs font-medium truncate
                  ${e.isYou ? 'text-white' : 'text-slate-700'}`}>
                  {e.isYou ? `★ ${e.name}` : e.name}
                </span>
                {e.soldOut && (
                  <span className="text-[9px] font-bold bg-coral text-white px-1.5 py-0.5 rounded">
                    SOLD OUT
                  </span>
                )}
                {!e.isYou && <PropertyTypeBadge ptype={e.ptype} />}
              </div>
              {isStr && trueCost && (
                <div className="text-[10px] text-amber-700 mt-0.5 ml-16">
                  True guest cost with fees: <strong>${trueCost}</strong> <span className="text-amber-500">(cleaning + service fees)</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function CompetitiveIntel({ tenant, property }: Props) {
  const [competitors, setCompetitors] = useState<CompetitorProp[]>([])
  const [compRates,   setCompRates]   = useState<CompRate[]>([])
  const [yourRates,   setYourRates]   = useState<Pick<RateRec,'id'|'target_date'|'recommended_rate'|'demand_score'|'status'|'minimum_stay_rec'>[]>([])
  const [roomType,    setRoomType]    = useState<RoomType | null>(null)
  const [loading,     setLoading]     = useState(true)

  // ── Section C — Room-type comparison mode ──
  type RoomCategory = 'all' | 'waterfront' | 'waterview' | 'garden' | 'classic'
  const [roomCategory, setRoomCategory] = useState<RoomCategory>('all')
  interface RoomTypeApi {
    room_category: string; our_room_label: string; our_description: string
    our_base_rate: number; icon: string
    dates: string[]; date_labels: string[]; our_rates: number[]
    competitors: { name: string; property_type?: PropertyType; tier: string; distance: number | null
      tripadvisor: number | null; avail_color: string
      has_equivalent: boolean; comp_room_name: string | null
      comp_room_notes: string | null; no_equivalent_msg: string | null
      rates: (number | null)[] }[]
    position_by_date: { date: string; our_rate: number; comp_avg: number | null
      comp_min?: number; comp_max?: number; str_avg?: number | null
      pct_vs_avg?: number; position: string }[]
  }
  const [roomData, setRoomData] = useState<RoomTypeApi | null>(null)
  useEffect(() => {
    if (roomCategory === 'all') { setRoomData(null); return }
    fetch(`/api/competitors/by-room-type?room_category=${roomCategory}&days=14`)
      .then(r => r.json()).then(setRoomData).catch(() => setRoomData(null))
  }, [roomCategory])

  // ── Filters (Section B) — radius / tier / top-N ──
  const [radiusMi, setRadiusMi] = useState<number | 'all'>(() => {
    const v = localStorage.getItem('tgc.compIntel.radius')
    return v === 'all' ? 'all' : (v ? Number(v) : 25)
  })
  const [tierFilter, setTierFilter] = useState<number | 'all'>(() => {
    const v = localStorage.getItem('tgc.compIntel.tier')
    return v === 'all' || !v ? 'all' : Number(v)
  })
  const [topN, setTopN] = useState<number | 'all'>(() => {
    const v = localStorage.getItem('tgc.compIntel.topN')
    return v === 'all' || !v ? 'all' : Number(v)
  })
  useEffect(() => { localStorage.setItem('tgc.compIntel.radius', String(radiusMi)) }, [radiusMi])
  useEffect(() => { localStorage.setItem('tgc.compIntel.tier',   String(tierFilter)) }, [tierFilter])
  useEffect(() => { localStorage.setItem('tgc.compIntel.topN',   String(topN)) }, [topN])

  const today = new Date()
  const dates = Array.from({ length: 14 }, (_, i) => addDays(today, i + 1))

  useEffect(() => {
    async function load() {
      setLoading(true)
      const startDate = format(addDays(today, 1), 'yyyy-MM-dd')
      const endDate   = format(addDays(today, 14), 'yyyy-MM-dd')

      const [{ data: comps }, { data: cr }, { data: rts }] = await Promise.all([
        supabase.from('competitor_properties')
          .select('id,competitor_name,name,booking_com_id,active,property_tier,property_category,room_count,trip_advisor_rating,distance_miles')
          .eq('property_id', property.id)
          .eq('active', true)
          .order('property_tier', { ascending: true }),

        // 14-day window only — July 20 fetched separately below
        supabase.from('competitor_rates')
          .select('id,competitor_id,rate_date,rate_amount,is_sold_out,is_stale')
          .eq('property_id', property.id)
          .eq('is_stale', false)
          .gte('rate_date', startDate)
          .lte('rate_date', endDate)
          .order('rate_date'),

        supabase.from('room_types')
          .select('id,name,base_rate,min_rate,max_rate,bathroom_type,bathroom_premium,total_count')
          .eq('property_id', property.id)
          .order('base_rate', { ascending: false })
          .limit(1),
      ])

      setCompetitors(comps ?? [])
      setCompRates(cr ?? [])
      const primaryRt = rts?.[0] ?? null
      setRoomType(primaryRt)

      if (primaryRt) {
        // Fetch 14-day window + the July 20 peak day in parallel, then merge
        const [{ data: rr }, { data: wf }, { data: wfRates }] = await Promise.all([
          supabase.from('rate_recommendations')
            .select('id,target_date,recommended_rate,demand_score,status,minimum_stay_rec')
            .eq('property_id', property.id)
            .eq('room_type_id', primaryRt.id)
            .gte('target_date', startDate)
            .lte('target_date', endDate),
          supabase.from('rate_recommendations')
            .select('id,target_date,recommended_rate,demand_score,status,minimum_stay_rec')
            .eq('property_id', property.id)
            .eq('room_type_id', primaryRt.id)
            .eq('target_date', '2026-07-20')
            .limit(1),
          supabase.from('competitor_rates')
            .select('id,competitor_id,rate_date,rate_amount,is_sold_out,is_stale')
            .eq('property_id', property.id)
            .eq('is_stale', false)
            .eq('rate_date', '2026-07-20'),
        ])
        setYourRates([...(rr ?? []), ...(wf ?? [])])
        setCompRates(prev => [...prev, ...(wfRates ?? [])])
      }

      setLoading(false)
    }
    load()
  }, [property.id])

  // Apply filters: radius → tier → top N (preserving original tier-asc order)
  const filteredCompetitors = (() => {
    let list = competitors
    if (radiusMi !== 'all') {
      list = list.filter(c => c.distance_miles == null || c.distance_miles <= radiusMi)
    }
    if (tierFilter !== 'all') {
      list = list.filter(c => (c.property_tier ?? 1) === tierFilter)
    }
    if (topN !== 'all') list = list.slice(0, topN)
    return list
  })()
  const tierCounts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0 }
  competitors.forEach(c => {
    const t = c.property_tier ?? 1
    if (t in tierCounts) tierCounts[t]++
  })

  const compMap  = new Map(filteredCompetitors.map(c => [c.id, c.competitor_name || c.name || 'Unknown']))
  const yourMap  = new Map(yourRates.map(r => [r.target_date as string, r]))

  // Build rate matrix: date → {comp_id: rate}
  const rateMatrix = new Map<string, Map<string, { amount: number | null; soldOut: boolean }>>()
  compRates.forEach(cr => {
    if (!rateMatrix.has(cr.rate_date)) rateMatrix.set(cr.rate_date, new Map())
    rateMatrix.get(cr.rate_date)!.set(cr.competitor_id, {
      amount: cr.rate_amount,
      soldOut: cr.is_sold_out,
    })
  })

  function positionLabel(yourRate: number, compAvg: number): { label: string; cls: string } {
    const pct = (yourRate - compAvg) / compAvg
    if (pct > 0.15)  return { label: 'Premium',        cls: 'bg-sage/15 text-sage' }
    if (pct > -0.10) return { label: 'At Market',      cls: 'bg-navy/10 text-navy' }
    if (pct > -0.25) return { label: 'Below Market',   cls: 'bg-amber-100 text-amber-700' }
    return { label: 'Significantly Below', cls: 'bg-coral/15 text-coral' }
  }

  // Summary stats — boutique peer comp avg only (STRs and budget anchors
  // are visible in the table for context but not used as a pricing baseline).
  const summaryDates = dates.map(d => {
    const dStr = format(d, 'yyyy-MM-dd')
    const your = yourMap.get(dStr)?.recommended_rate ?? null
    const rows = rateMatrix.get(dStr)
    if (!rows) return null
    const peerRates: number[] = []
    filteredCompetitors.forEach(c => {
      const r = rows.get(c.id)
      if (!r || r.soldOut || r.amount == null) return
      const cname = c.competitor_name || c.name || ''
      const ptype = PROPERTY_TYPE_BY_NAME[cname] ?? ((c.property_tier ?? 1) === 4 ? 'budget_hotel' : 'boutique_inn')
      if (ptype === 'airbnb_str' || ptype === 'budget_hotel') return
      peerRates.push(r.amount)
    })
    if (!peerRates.length || !your) return null
    return { your, avg: peerRates.reduce((a, b) => a + b, 0) / peerRates.length }
  }).filter(Boolean) as { your: number; avg: number }[]

  const overallPct = summaryDates.length
    ? Math.round(summaryDates.reduce((s, d) => s + (d.your - d.avg) / d.avg, 0) / summaryDates.length * 100)
    : 0

  // Stale-rate drop detection (is_stale=true rows vs current)
  const [drops, setDrops] = useState<{name: string; old: number; new: number; pct: number}[]>([])
  useEffect(() => {
    async function checkDrops() {
      const startDate = format(addDays(today, 1), 'yyyy-MM-dd')
      const { data: stale } = await supabase
        .from('competitor_rates')
        .select('competitor_id,rate_date,rate_amount')
        .eq('property_id', property.id)
        .eq('is_stale', true)
        .gte('rate_date', startDate)

      const { data: current } = await supabase
        .from('competitor_rates')
        .select('competitor_id,rate_date,rate_amount')
        .eq('property_id', property.id)
        .eq('is_stale', false)
        .gte('rate_date', startDate)

      if (!stale || !current) return

      const staleIdx = new Map(stale.map(r => [`${r.competitor_id}:${r.rate_date}`, r.rate_amount]))
      const dropMap  = new Map<string, { old: number; new: number; count: number }>()

      current.forEach(r => {
        const key  = `${r.competitor_id}:${r.rate_date}`
        const old  = staleIdx.get(key)
        if (!old || !r.rate_amount) return
        const drop = (old - r.rate_amount) / old
        if (drop >= 0.10) {
          const name = compMap.get(r.competitor_id) ?? 'Unknown'
          if (!dropMap.has(name)) dropMap.set(name, { old, new: r.rate_amount, count: 0 })
          const d = dropMap.get(name)!
          d.count++
          if (drop > (d.old - d.new) / d.old) { d.old = old; d.new = r.rate_amount }
        }
      })

      setDrops([...dropMap.entries()].map(([name, d]) => ({
        name, old: d.old, new: d.new, pct: Math.round((d.old - d.new) / d.old * 100),
      })))
    }
    if (competitors.length) checkDrops()
  }, [competitors])

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-navy border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-navy font-bold text-xl">Competitive Intelligence</h1>
          <p className="text-slate-400 text-sm">14-day forward rates — {roomType?.name} vs Beaufort comp set</p>
        </div>
        <div className={`rounded-xl px-4 py-2 text-center ${overallPct >= 0 ? 'bg-sage/10' : 'bg-coral/10'}`}>
          <div className={`text-2xl font-bold ${overallPct >= 0 ? 'text-sage' : 'text-coral'}`}>
            {overallPct >= 0 ? '+' : ''}{overallPct}%
          </div>
          <div className="text-xs text-slate-400">vs boutique peer avg (14d)</div>
        </div>
      </div>

      {/* Section G — Competitive Response Recommendations */}
      <LockedFeature featureName="Competitive Response Recommendations" featureKey="competitive_response"
        description="When a competitor drops their rate, surface three strategic responses — match, hold, or counter — with rationale, conditions, and risk.">
        <CompetitiveResponsePanel />
      </LockedFeature>

      {/* Section C — Room-type selector */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-bold text-navy uppercase tracking-wider text-[10px]">Compare by Room Type</span>
        {([
          { val: 'all'        as const, lbl: 'All (Avg)',     icon: '◐' },
          { val: 'waterfront' as const, lbl: 'Waterfront',    icon: '🌊' },
          { val: 'waterview'  as const, lbl: 'Water View',    icon: '💧' },
          { val: 'garden'     as const, lbl: 'Garden',        icon: '🌿' },
          { val: 'classic'    as const, lbl: 'Classic',       icon: '🛏️' },
        ]).map(opt => (
          <button key={opt.val} onClick={() => setRoomCategory(opt.val)}
            className={`px-3 py-1 rounded-full font-semibold transition-colors ${
              roomCategory === opt.val
                ? 'bg-navy text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
            <span className="mr-1">{opt.icon}</span>{opt.lbl}
          </button>
        ))}
        {roomData && (
          <span className="ml-auto text-slate-500">
            {roomData.competitors.filter(c => c.has_equivalent).length} of {roomData.competitors.length} competitors offer {roomData.our_room_label}
          </span>
        )}
      </div>

      {/* Section C — Room-type table (renders only when not 'all') */}
      {roomCategory !== 'all' && roomData && (() => {
        const visible = roomData.competitors  // show ALL — N/A cells communicate gaps
        const validPositions = roomData.position_by_date.filter(p => p.comp_avg != null)
        const avgPct = validPositions.length
          ? Math.round(validPositions.reduce((s, p) => s + (p.pct_vs_avg ?? 0), 0) / validPositions.length)
          : 0
        const avgCompAvg = validPositions.length
          ? Math.round(validPositions.reduce((s, p) => s + (p.comp_avg ?? 0), 0) / validPositions.length)
          : 0
        const avgOurs = Math.round(roomData.our_rates.reduce((s, r) => s + r, 0) / roomData.our_rates.length)
        return (
          <>
            <div className={`rounded-xl p-3 border ${avgPct >= 0 ? 'bg-sage/5 border-sage/30' : 'bg-coral/5 border-coral/30'}`}>
              <div className="text-sm font-semibold">
                <span className="text-lg mr-2">{roomData.icon}</span>
                <span className="text-navy">{roomData.our_room_label}:</span>{' '}
                <span className={avgPct >= 0 ? 'text-sage' : 'text-coral'}>
                  You are priced {avgPct >= 0 ? '+' : ''}{avgPct}% {avgPct >= 0 ? 'above' : 'below'} boutique peer average
                </span>
                <span className="text-slate-500"> (${avgOurs} vs ${avgCompAvg} comp avg) over the next 14 days</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">{roomData.our_description}</div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
              <div className="overflow-x-auto scrollbar-thin">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-navy text-white">
                      <th className="sticky left-0 bg-navy px-4 py-3 text-left font-semibold text-xs w-24">Date</th>
                      <th className="px-4 py-3 text-right font-semibold text-xs text-gold">Your {roomData.our_room_label}</th>
                      {visible.map(c => {
                        const ptype = (c.property_type ?? PROPERTY_TYPE_BY_NAME[c.name]) as PropertyType | undefined
                        const isStr = ptype === 'airbnb_str'
                        return (
                          <th key={c.name}
                              title={isStr ? PROPERTY_TYPE_BADGE.airbnb_str.tooltip : `${c.name}\n${c.tier}\n${c.distance ? `📍 ${c.distance} mi` : ''}\n${c.tripadvisor ? `⭐ ${c.tripadvisor}` : ''}\nEquivalent: ${c.comp_room_name ?? 'N/A'}`}
                              className={`px-3 py-3 text-right font-semibold text-xs whitespace-nowrap ${isStr ? 'bg-amber-700/40' : ''}`}>
                            <div>
                              {c.name.split(' ').slice(0, 2).join(' ')}
                              {isStr && <sup className="ml-1 text-[8px] text-amber-200 font-bold">STR</sup>}
                            </div>
                            <div className="font-normal italic text-[10px] text-white/60 mt-0.5">
                              {isStr ? 'STR — not a peer' : c.has_equivalent ? c.comp_room_name : '— no equivalent —'}
                            </div>
                          </th>
                        )
                      })}
                      <th className="px-4 py-3 text-right font-semibold text-xs">Comp Avg</th>
                      <th className="px-4 py-3 text-center font-semibold text-xs">Position</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roomData.dates.map((dStr, di) => {
                      const pos = roomData.position_by_date[di]
                      const dotCls = pos.position === 'Premium' ? 'bg-sage'
                                    : pos.position === 'At Market' ? 'bg-gold'
                                    : pos.position === 'Below Market' ? 'bg-coral'
                                    : 'bg-slate-200'
                      const wf = roomData.date_labels[di]?.includes('Jul') && [17,18,19,20,21,22,23,24,25,26].some(d => roomData.date_labels[di].endsWith(` ${d}`))
                      return (
                        <tr key={dStr} className={`border-t border-slate-100 ${di % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'} ${wf ? 'bg-gold/5' : ''}`}>
                          <td className="sticky left-0 bg-inherit px-4 py-2.5 font-medium text-navy w-24">
                            {roomData.date_labels[di]}
                            {wf && <span className="ml-1 text-gold text-[10px] font-bold">★WF</span>}
                          </td>
                          <td className="px-4 py-2.5 text-right font-bold text-navy">
                            ${roomData.our_rates[di]}
                          </td>
                          {visible.map(c => {
                            const r = c.rates[di]
                            const ptype = (c.property_type ?? PROPERTY_TYPE_BY_NAME[c.name]) as PropertyType | undefined
                            const isStr = ptype === 'airbnb_str'
                            const trueCost = isStr && r != null ? Math.round(r * STR_TRUE_GUEST_COST_MULTIPLIER) : null
                            return (
                              <td key={c.name}
                                  className={`px-3 py-2.5 text-right ${isStr ? 'bg-amber-50/60' : ''}`}
                                  title={c.comp_room_notes ?? ''}>
                                {r == null ? (
                                  <span className="text-slate-300 italic">N/A</span>
                                ) : isStr ? (
                                  <div>
                                    <div className="text-amber-700 line-through text-xs">${r}</div>
                                    {trueCost && <div className="text-amber-800 text-[10px] font-semibold">+fees ${trueCost}</div>}
                                  </div>
                                ) : (
                                  <span className="text-slate-700">${r}</span>
                                )}
                              </td>
                            )
                          })}
                          <td className="px-4 py-2.5 text-right text-slate-500 font-medium">
                            {pos.comp_avg != null ? `$${pos.comp_avg}` : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <span className={`inline-block w-2 h-2 rounded-full ${dotCls}`} title={pos.position} />
                            <span className="ml-2 text-[11px] text-slate-600">{pos.position}</span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div className="px-3 py-2 text-[10px] text-slate-400 border-t border-slate-100">
                Hover any competitor column header for property details. N/A = competitor has no equivalent room in this category.
              </div>
            </div>
          </>
        )
      })()}

      {/* Section B filter bar — radius / tier / top N */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3 flex flex-wrap items-center gap-3 text-xs">
        <span className="font-bold text-navy uppercase tracking-wider text-[10px]">Filters</span>

        <div className="flex items-center gap-1">
          <span className="text-slate-500">Radius:</span>
          {([5, 10, 15, 25, 'all'] as const).map(r => (
            <button key={r} onClick={() => setRadiusMi(r as any)}
              className={`px-2 py-0.5 rounded ${radiusMi === r
                ? 'bg-navy text-white font-semibold'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
              {r === 'all' ? 'All' : `${r} mi`}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <span className="text-slate-500">Tier:</span>
          {([
            { val: 'all' as const, lbl: 'All' },
            { val: 1   as const, lbl: `Direct (${tierCounts[1] || 0})`,        cls: 'data-active:bg-navy' },
            { val: 2   as const, lbl: `Upscale (${tierCounts[2] || 0})` },
            { val: 4   as const, lbl: `Budget (${tierCounts[4] || 0})` },
            { val: 3   as const, lbl: `Luxury (${tierCounts[3] || 0})` },
          ]).map(t => (
            <button key={String(t.val)} onClick={() => setTierFilter(t.val as any)}
              className={`px-2 py-0.5 rounded ${tierFilter === t.val
                ? 'bg-navy text-white font-semibold'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
              {t.lbl}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <span className="text-slate-500">Show top:</span>
          <select value={String(topN)} onChange={e => setTopN(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            className="border border-slate-200 rounded px-2 py-0.5 text-xs focus:outline-none focus:border-navy">
            <option value="5">5</option>
            <option value="10">10</option>
            <option value="15">15</option>
            <option value="20">20</option>
            <option value="all">All</option>
          </select>
        </div>

        <span className="ml-auto text-slate-400">
          Showing {filteredCompetitors.length} of {competitors.length}
        </span>
      </div>

      {/* Rate drop alerts */}
      {drops.length > 0 && (
        <div className="bg-coral/5 border border-coral/20 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-coral font-bold text-sm">⚠ Rate Drop Alerts — Last 48 Hours</span>
          </div>
          {drops.map(d => (
            <div key={d.name} className="flex items-center gap-3 text-sm">
              <span className="font-semibold text-slate-700 w-40">{d.name}</span>
              <span className="text-coral font-bold">↓ {d.pct}%</span>
              <span className="text-slate-400">${d.old} → ${d.new}</span>
              <span className="text-slate-400 text-xs ml-auto">
                Consider holding if demand ≥ High — they may reverse
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 14-day competitive table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-navy text-white">
                <th className="sticky left-0 bg-navy px-4 py-3 text-left font-semibold text-xs w-24">Date</th>
                <th className="px-4 py-3 text-right font-semibold text-xs text-gold">Your Rate</th>
                {filteredCompetitors.map(c => {
                  const cname = c.competitor_name || c.name || ''
                  const ptype = PROPERTY_TYPE_BY_NAME[cname] ?? ((c.property_tier ?? 1) === 4 ? 'budget_hotel' : 'boutique_inn')
                  const isStr = ptype === 'airbnb_str'
                  return (
                    <th key={c.id}
                        title={isStr ? PROPERTY_TYPE_BADGE.airbnb_str.tooltip : undefined}
                        className={`px-3 py-3 text-right font-semibold text-xs whitespace-nowrap ${isStr ? 'bg-amber-700/40' : ''}`}>
                      {cname.split(' ').slice(0, 2).join(' ')}
                      {isStr && <sup className="ml-1 text-[8px] text-amber-200 font-bold">STR</sup>}
                    </th>
                  )
                })}
                <th className="px-4 py-3 text-right font-semibold text-xs">Comp Avg</th>
                <th className="px-4 py-3 text-center font-semibold text-xs">Position</th>
              </tr>
            </thead>
            <tbody>
              {dates.map((d, di) => {
                const dStr   = format(d, 'yyyy-MM-dd')
                const label  = format(d, 'MMM d')
                const dow    = format(d, 'EEE')
                const your   = yourMap.get(dStr)
                const matrix = rateMatrix.get(dStr) ?? new Map()
                // Boutique-only comp avg: exclude STR and budget_hotel from the
                // peer comparison since pricing a boutique inn against an Airbnb
                // would price the inn below market. Filter via PROPERTY_TYPE_BY_NAME.
                const boutiquePeerRates: number[] = []
                filteredCompetitors.forEach(c => {
                  const row = matrix.get(c.id)
                  if (!row || row.soldOut || row.amount == null) return
                  const cname = c.competitor_name || c.name || ''
                  const ptype = PROPERTY_TYPE_BY_NAME[cname] ?? ((c.property_tier ?? 1) === 4 ? 'budget_hotel' : 'boutique_inn')
                  if (ptype === 'airbnb_str' || ptype === 'budget_hotel') return
                  boutiquePeerRates.push(row.amount)
                })
                const avg = boutiquePeerRates.length
                  ? Math.round(boutiquePeerRates.reduce((a, b) => a + b, 0) / boutiquePeerRates.length)
                  : null
                const pos    = your?.recommended_rate && avg ? positionLabel(your.recommended_rate, avg) : null
                const wf     = d.getMonth() === 6 && d.getDate() >= 17 && d.getDate() <= 26

                return (
                  <tr key={dStr} className={`border-t border-slate-100 ${di % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'} ${wf ? 'bg-gold/5' : ''}`}>
                    <td className="sticky left-0 bg-inherit px-4 py-2.5 font-medium text-navy w-24">
                      <span>{label}</span>
                      <span className="text-slate-400 text-xs ml-1">{dow}</span>
                      {wf && <span className="ml-1 text-gold text-[10px] font-bold">★WF</span>}
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-navy">
                      {your?.recommended_rate ? `$${your.recommended_rate.toFixed(0)}` : '—'}
                    </td>
                    {filteredCompetitors.map(c => {
                      const row = matrix.get(c.id)
                      const cname = c.competitor_name || c.name || ''
                      const ptype = PROPERTY_TYPE_BY_NAME[cname] ?? ((c.property_tier ?? 1) === 4 ? 'budget_hotel' : 'boutique_inn')
                      const isStr = ptype === 'airbnb_str'
                      const trueCost = isStr && row?.amount != null ? Math.round(row.amount * STR_TRUE_GUEST_COST_MULTIPLIER) : null
                      return (
                        <td key={c.id} className={`px-3 py-2.5 text-right ${isStr ? 'bg-amber-50/60' : ''}`}>
                          {row?.soldOut ? (
                            <span className="inline-block bg-coral/15 text-coral text-[10px] font-bold px-1.5 py-0.5 rounded">SOLD OUT</span>
                          ) : row?.amount != null ? (
                            isStr ? (
                              <div>
                                <div className="text-amber-700 line-through text-xs">${row.amount.toFixed(0)}</div>
                                {trueCost && <div className="text-amber-800 text-[10px] font-semibold">+fees ${trueCost}</div>}
                              </div>
                            ) : (
                              <span className="text-slate-700">${row.amount.toFixed(0)}</span>
                            )
                          ) : (
                            <span className="text-slate-300">—</span>
                          )}
                        </td>
                      )
                    })}
                    <td className="px-4 py-2.5 text-right text-slate-500 font-medium">
                      {avg ? `$${avg}` : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      {pos && (
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${pos.cls}`}>
                          {pos.label}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Price Ladders + Competitor cards */}
      <div className="grid grid-cols-3 gap-4">
        <PriceLadder
          yourRate={yourMap.get(format(addDays(today, 1), 'yyyy-MM-dd'))?.recommended_rate ?? null}
          yourName="Bay Street Inn (Waterfront)"
          compRates={compRates}
          competitors={competitors}
          dateStr={format(addDays(today, 1), 'yyyy-MM-dd')}
          dateLabel={format(addDays(today, 1), 'EEE MMM d')}
        />
        <PriceLadder
          yourRate={yourMap.get('2026-07-20')?.recommended_rate ?? null}
          yourName="Bay Street Inn (Waterfront)"
          compRates={compRates}
          competitors={competitors}
          dateStr="2026-07-20"
          dateLabel="★ Mon Jul 20 — Water Festival"
        />
        <div className="col-span-1 grid grid-cols-1 gap-3 content-start">
          {competitors.map(c => {
            const rates     = compRates.filter(r => r.competitor_id === c.id && !r.is_sold_out && r.rate_amount)
            const avgRate   = rates.length ? Math.round(rates.reduce((s, r) => s + r.rate_amount!, 0) / rates.length) : null
            const soldDates = compRates.filter(r => r.competitor_id === c.id && r.is_sold_out).length
            return (
              <div key={c.id} className="bg-white rounded-xl p-4 shadow-sm border border-slate-100">
                <div className="flex items-center gap-2 mb-1">
                  <div className="font-semibold text-navy text-sm flex-1 truncate">
                    {c.competitor_name || c.name}
                  </div>
                  <TierBadge tier={c.property_tier} />
                </div>
                <div className="text-2xl font-bold text-slate-700">{avgRate ? `$${avgRate}` : '—'}</div>
                <div className="text-xs text-slate-400 mt-0.5">14-day avg</div>
                {c.distance_miles != null && (
                  <div className="text-[10px] text-slate-400 mt-0.5">{c.distance_miles.toFixed(1)} mi away</div>
                )}
                {c.trip_advisor_rating && (
                  <div className="text-[10px] text-slate-400">TA: {c.trip_advisor_rating}★</div>
                )}
                {soldDates > 0 && (
                  <div className="mt-1.5 text-[10px] bg-coral/10 text-coral font-semibold px-2 py-0.5 rounded">
                    {soldDates} dates sold out
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── Section G: Competitive Response Recommendations ──
interface ResponseOption {
  id: string; label: string; rate: number; description: string
}
interface ResponseAlert {
  competitor: string; their_old_rate: number; their_new_rate: number
  drop_pct: number; your_rate: number; your_premium_pct: number
  demand_score: number; demand_label: string
  recommended_action: 'hold' | 'partial_match' | 'match'
  rationale: string
  options: ResponseOption[]
  target_date: string
}

function CompetitiveResponsePanel() {
  const [data, setData] = useState<{ responses: ResponseAlert[] } | null>(null)
  const [selected, setSelected] = useState<Record<string, string>>({})
  useEffect(() => {
    fetch('/api/competitive-response').then(r => r.json()).then(setData)
  }, [])
  if (!data) return null
  if (data.responses.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-sage/20 p-4">
        <div className="text-sm font-semibold text-sage-dark">✓ No competitive rate drops detected</div>
        <div className="text-xs text-slate-500 mt-0.5">Your comp set is stable. We will surface a recommendation here when someone moves more than 15%.</div>
      </div>
    )
  }
  // Map recommended_action to corresponding option id so the recommended card highlights
  const recToOptId: Record<ResponseAlert['recommended_action'], string> = {
    hold: 'hold', partial_match: 'partial', match: 'match',
  }
  return (
    <div className="space-y-3">
      {data.responses.map(alert => {
        const chosen = selected[alert.competitor] ?? recToOptId[alert.recommended_action]
        return (
          <div key={alert.competitor} className="bg-white rounded-xl shadow-sm border-2 border-coral/30 p-5">
            <div className="flex items-baseline justify-between flex-wrap gap-2 mb-1">
              <h3 className="font-bold text-navy text-base">⚠ {alert.competitor} dropped {alert.drop_pct}%</h3>
              <div className="text-xs text-slate-500">
                ${alert.their_old_rate} → <strong className="text-coral">${alert.their_new_rate}</strong> ·
                You at <strong className="text-navy">${alert.your_rate}</strong> (+{alert.your_premium_pct}%)
              </div>
            </div>

            {/* Demand-gated recommendation rationale */}
            <div className="mt-2 mb-3 bg-navy/5 border border-navy/20 rounded-lg p-3">
              <div className="flex items-baseline gap-2 text-[11px] uppercase tracking-wide text-navy font-bold">
                <span>Demand score: {alert.demand_score} ({alert.demand_label})</span>
                <span className="text-slate-400">·</span>
                <span className="text-gold-dark">Recommended: {alert.recommended_action.replace('_', ' ')}</span>
              </div>
              <div className="text-sm text-slate-700 mt-1 leading-snug">{alert.rationale}</div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {alert.options.map(opt => {
                const isRecommended = opt.id === recToOptId[alert.recommended_action]
                const isSelected = chosen === opt.id
                return (
                  <button key={opt.id}
                    onClick={() => setSelected({ ...selected, [alert.competitor]: opt.id })}
                    className={`text-left rounded-lg p-3 border-2 transition-all relative ${
                      isSelected
                        ? 'border-gold bg-gold/5 shadow-md'
                        : isRecommended
                          ? 'border-sage/60 bg-sage/5'
                          : 'border-slate-100 hover:border-navy/30'
                    }`}>
                    {isRecommended && (
                      <span className="absolute top-1 right-2 text-[9px] uppercase font-bold bg-sage text-white px-1.5 py-0.5 rounded">★ Recommended</span>
                    )}
                    <div className="font-bold text-navy text-sm">{opt.label}</div>
                    <div className="text-2xl font-bold text-navy mt-1">${opt.rate}</div>
                    <div className="text-[11px] text-slate-600 mt-1 leading-snug">{opt.description}</div>
                    {isSelected && <div className="text-[10px] text-gold font-bold mt-2">✓ Selected — apply via Rate Calendar</div>}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

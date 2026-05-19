import { useEffect, useState } from 'react'
import { format, addDays } from 'date-fns'
import { supabase } from '../lib/supabase'
import type { Tenant, Property, CompRate, CompetitorProp, RateRec, RoomType } from '../lib/types'

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

  // Dedupe by (name, tier) — keep highest rate, preserve sold-out flag
  const dedup = new Map<string, { name: string; rate: number; tier: number; soldOut: boolean }>()
  dayRates.forEach(cr => {
    const comp = compMap.get(cr.competitor_id)
    if (!comp || cr.rate_amount == null) return
    const name = comp.competitor_name ?? comp.name ?? 'Competitor'
    const tier = comp.property_tier ?? 1
    const key  = `${name}::${tier}`
    const cur  = dedup.get(key)
    if (!cur || cr.rate_amount > cur.rate) {
      dedup.set(key, { name, rate: cr.rate_amount, tier, soldOut: cr.is_sold_out || cur?.soldOut || false })
    } else if (cr.is_sold_out && cur) {
      cur.soldOut = true
    }
  })

  const entries: { name: string; rate: number; tier: number; soldOut: boolean; isYou: boolean }[] =
    [...dedup.values()].map(e => ({ ...e, isYou: false }))
  if (yourRate) entries.push({ name: yourName, rate: yourRate, tier: 0, soldOut: false, isYou: true })
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
          const tierColor = e.tier === 0 ? 'bg-navy text-white'
                          : e.tier === 3 ? 'bg-purple-50 border-purple-200'
                          : e.tier === 1 ? 'bg-cream border-slate-100'
                          : e.tier === 2 ? 'bg-gold/5 border-gold/15'
                          :                'bg-slate-50 border-slate-100'
          return (
            <div key={i}
                 className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border ${tierColor}`}>
              <span className={`text-sm font-bold w-14 text-right
                ${e.isYou ? 'text-gold' : e.soldOut ? 'text-coral line-through' : 'text-navy'}`}>
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
              {!e.isYou && <TierBadge tier={e.tier} />}
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
  type RoomCategory = 'all' | 'waterfront' | 'waterview' | 'garden' | 'cottage'
  const [roomCategory, setRoomCategory] = useState<RoomCategory>('all')
  interface RoomTypeApi {
    room_category: string; our_room_label: string; our_description: string
    our_base_rate: number; icon: string
    dates: string[]; date_labels: string[]; our_rates: number[]
    competitors: { name: string; tier: string; distance: number | null
      tripadvisor: number | null; avail_color: string
      has_equivalent: boolean; comp_room_name: string | null
      comp_room_notes: string | null; no_equivalent_msg: string | null
      rates: (number | null)[] }[]
    position_by_date: { date: string; our_rate: number; comp_avg: number | null
      comp_min?: number; comp_max?: number; pct_vs_avg?: number; position: string }[]
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

  // Summary stats
  const summaryDates = dates.map(d => {
    const dStr = format(d, 'yyyy-MM-dd')
    const your  = yourMap.get(dStr)?.recommended_rate ?? null
    const rows  = rateMatrix.get(dStr)
    if (!rows) return null
    const live  = [...rows.values()].filter(r => !r.soldOut && r.amount != null).map(r => r.amount!)
    if (!live.length || !your) return null
    return { your, avg: live.reduce((a, b) => a + b, 0) / live.length }
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
          <div className="text-xs text-slate-400">vs comp avg (14d)</div>
        </div>
      </div>

      {/* Section C — Room-type selector */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="font-bold text-navy uppercase tracking-wider text-[10px]">Compare by Room Type</span>
        {([
          { val: 'all'        as const, lbl: 'All (Avg)',     icon: '◐' },
          { val: 'waterfront' as const, lbl: 'Waterfront',    icon: '🌊' },
          { val: 'waterview'  as const, lbl: 'Water View',    icon: '💧' },
          { val: 'garden'     as const, lbl: 'Garden',        icon: '🌿' },
          { val: 'cottage'    as const, lbl: 'Cottage',       icon: '🏡' },
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
                  You are priced {avgPct >= 0 ? '+' : ''}{avgPct}% {avgPct >= 0 ? 'above' : 'below'} comp set average
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
                      {visible.map(c => (
                        <th key={c.name} className="px-3 py-3 text-right font-semibold text-xs whitespace-nowrap"
                            title={`${c.name}\n${c.tier}\n${c.distance ? `📍 ${c.distance} mi` : ''}\n${c.tripadvisor ? `⭐ ${c.tripadvisor}` : ''}\nEquivalent: ${c.comp_room_name ?? 'N/A'}`}>
                          <div>{c.name.split(' ').slice(0, 2).join(' ')}</div>
                          <div className="font-normal italic text-[10px] text-white/60 mt-0.5">
                            {c.has_equivalent ? c.comp_room_name : '— no equivalent —'}
                          </div>
                        </th>
                      ))}
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
                            return (
                              <td key={c.name} className="px-3 py-2.5 text-right" title={c.comp_room_notes ?? ''}>
                                {r != null
                                  ? <span className="text-slate-700">${r}</span>
                                  : <span className="text-slate-300 italic">N/A</span>}
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
                {filteredCompetitors.map(c => (
                  <th key={c.id} className="px-3 py-3 text-right font-semibold text-xs whitespace-nowrap">
                    {(c.competitor_name || c.name || '').split(' ').slice(0, 2).join(' ')}
                  </th>
                ))}
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
                const live   = [...matrix.values()].filter(r => !r.soldOut && r.amount != null).map(r => r.amount!)
                const avg    = live.length ? Math.round(live.reduce((a, b) => a + b, 0) / live.length) : null
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
                      return (
                        <td key={c.id} className="px-3 py-2.5 text-right">
                          {row?.soldOut
                            ? <span className="inline-block bg-coral/15 text-coral text-[10px] font-bold px-1.5 py-0.5 rounded">SOLD OUT</span>
                            : row?.amount != null
                            ? <span className="text-slate-700">${row.amount.toFixed(0)}</span>
                            : <span className="text-slate-300">—</span>
                          }
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
          yourName="Anchorage 1770 (Waterfront)"
          compRates={compRates}
          competitors={competitors}
          dateStr={format(addDays(today, 1), 'yyyy-MM-dd')}
          dateLabel={format(addDays(today, 1), 'EEE MMM d')}
        />
        <PriceLadder
          yourRate={yourMap.get('2026-07-20')?.recommended_rate ?? null}
          yourName="Anchorage 1770 (Waterfront)"
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

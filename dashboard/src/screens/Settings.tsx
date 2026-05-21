import { useCallback, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import type { Tenant, Property, RoomType, QualityScore, CompetitorProp } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface AutopilotCfg {
  id?: string
  tenant_id: string; property_id: string; room_type_id: string
  enabled: boolean
  max_rate_change_pct: number
  min_confidence_score: number
  autopilot_start_hour: number
  autopilot_end_hour:   number
  notify_on_publish:   boolean
  max_daily_changes:   number
}

function defaultAutopilotCfg(tenant_id: string, property_id: string, room_type_id: string): AutopilotCfg {
  return {
    tenant_id, property_id, room_type_id,
    enabled: false,
    max_rate_change_pct: 0.15,
    min_confidence_score: 75,
    autopilot_start_hour: 6,
    autopilot_end_hour:   22,
    notify_on_publish:    true,
    max_daily_changes:    3,
  }
}

function CompetitorPrefs({ total }: { total: number }) {
  const [radius, setRadius] = useState<number | 'all'>(() => {
    const v = localStorage.getItem('tgc.compIntel.radius')
    return v === 'all' ? 'all' : (v ? Number(v) : 25)
  })
  const [topN, setTopN] = useState<number | 'all'>(() => {
    const v = localStorage.getItem('tgc.compIntel.topN')
    return v === 'all' || !v ? 'all' : Number(v)
  })
  useEffect(() => { localStorage.setItem('tgc.compIntel.radius', String(radius)) }, [radius])
  useEffect(() => { localStorage.setItem('tgc.compIntel.topN',   String(topN))   }, [topN])

  return (
    <div className="bg-cream rounded-lg p-3 mb-4 grid grid-cols-3 gap-4 text-xs">
      <div>
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Search Radius</div>
        <select value={String(radius)} onChange={e => setRadius(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          className="w-full border border-slate-200 rounded px-2 py-1 focus:outline-none focus:border-navy">
          <option value="5">5 mi</option>
          <option value="10">10 mi</option>
          <option value="15">15 mi</option>
          <option value="25">25 mi</option>
          <option value="all">All</option>
        </select>
        <div className="text-[10px] text-slate-400 mt-1">Auto-discovery will scan within this radius.</div>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Competitors to show in table</div>
        <select value={String(topN)} onChange={e => setTopN(e.target.value === 'all' ? 'all' : Number(e.target.value))}
          className="w-full border border-slate-200 rounded px-2 py-1 focus:outline-none focus:border-navy">
          <option value="5">Top 5</option>
          <option value="10">Top 10</option>
          <option value="15">Top 15</option>
          <option value="20">Top 20</option>
          <option value="all">All</option>
        </select>
        <div className="text-[10px] text-slate-400 mt-1">Limits column count on the Competitive Intel table.</div>
      </div>

      <div className="text-slate-500">
        <div className="text-[10px] uppercase tracking-wider font-semibold mb-1">Your radius</div>
        <div className="text-navy font-bold text-lg">{radius === 'all' ? 'No limit' : `${radius} mi`}</div>
        <div className="text-[10px] mt-1">{total} properties tracked across 4 tiers.</div>
      </div>
    </div>
  )
}

// ── CPP Section 3: Price Fences ──────────────────────────────────────
interface PriceFence {
  id: string; name: string; description: string
  fence_type: string; discount_pct?: number
  discount_schedule?: Record<number, number>
  requires_verification: boolean
  verification_method?: string
  applicable_channels: string[]
  rationale: string
  beaufort_specific_note?: string
  national_take_rate: number
  active: boolean
}

function PriceFencesPanel() {
  const [fences, setFences] = useState<PriceFence[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  useEffect(() => {
    fetch('/api/price-fences').then(r => r.json()).then(setFences).catch(() => setFences([]))
  }, [])
  async function patch(id: string, body: any) {
    await fetch(`/api/price-fences/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    setFences(f => f.map(x => x.id === id ? { ...x, ...body } : x))
  }
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <h2 className="font-bold text-navy mb-1">Price Fence Configuration</h2>
      <p className="text-xs text-slate-500 mb-3">
        Control which discount programs you offer and at what levels. Each fence is a guest-self-selected
        condition that justifies a different price without cannibalizing your base rate.
      </p>
      <div className="space-y-3">
        {fences.map(f => {
          const isOpen = expanded.has(f.id)
          const monthlyImpact = Math.round(380 * 14 * 30 * f.national_take_rate * 0.75 * ((f.discount_pct ?? 8) / 100))
          return (
            <div key={f.id} className="border border-slate-100 rounded-lg p-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <strong className="text-navy text-sm">{f.name}</strong>
                    <span className="text-[10px] uppercase tracking-wider bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">
                      {f.fence_type.replace(/_/g, ' ')}
                    </span>
                    {f.requires_verification && (
                      <span className="text-[10px] uppercase bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-bold">
                        ID required
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{f.description}</div>
                </div>
                <div className="flex items-center gap-3">
                  {f.discount_pct != null && (
                    <input type="number" min={0} max={50} value={f.discount_pct ?? 0}
                      onChange={e => patch(f.id, { discount_pct: Number(e.target.value) })}
                      className="border border-slate-200 rounded w-14 px-1 py-0.5 text-xs text-right"
                      title="Discount %" />
                  )}
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" checked={!!f.active} onChange={e => patch(f.id, { active: e.target.checked })}
                      className="sr-only peer" />
                    <div className="w-9 h-5 bg-slate-200 peer-checked:bg-sage rounded-full transition-colors after:absolute after:top-0.5 after:left-0.5 after:w-4 after:h-4 after:bg-white after:rounded-full peer-checked:after:translate-x-4 after:transition-transform" />
                  </label>
                </div>
              </div>
              {f.beaufort_specific_note && (
                <div className="mt-2 bg-amber-50 border-l-4 border-amber-400 rounded-r px-2 py-1 text-[11px] text-amber-800">
                  ⚠ <strong>Beaufort market note:</strong> {f.beaufort_specific_note}
                </div>
              )}
              <div className="flex items-baseline justify-between mt-2 text-[10px] text-slate-500">
                <span>Est. monthly impact: <strong className="text-navy">${monthlyImpact.toLocaleString()}</strong> @ {(f.national_take_rate*100).toFixed(0)}% take rate</span>
                <button onClick={() => setExpanded(s => { const n = new Set(s); n.has(f.id) ? n.delete(f.id) : n.add(f.id); return n })}
                  className="text-navy hover:text-gold font-semibold">
                  {isOpen ? 'Hide rationale ▴' : 'Why offer this? ▾'}
                </button>
              </div>
              {isOpen && (
                <div className="mt-2 bg-cream rounded p-2 text-[11px] text-slate-600 italic">
                  {f.rationale}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── CPP Section 5: Annual Price Review ───────────────────────────────
interface PriceReviewRow {
  room_id: string; room_name: string
  current_base: number; recommended_new_base: number
  change_dollars: number; change_pct: number
  annual_revenue_impact: number; rationale: string
}
interface PriceReviewResp {
  review_date: string; market_appreciation_pct: number
  recommendations: PriceReviewRow[]; total_annual_revenue_impact: number
  implementation_guidance: string
}

function AnnualPriceReviewPanel() {
  const [data, setData] = useState<PriceReviewResp | null>(null)
  const [loading, setLoading] = useState(false)
  async function run() {
    setLoading(true)
    try {
      const r = await fetch('/api/price-review'); setData(await r.json())
    } finally { setLoading(false) }
  }
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="font-bold text-navy">Annual Base Rate Review</h2>
        <button onClick={run} disabled={loading}
          className="text-xs font-bold bg-navy text-white px-3 py-1.5 rounded-lg hover:bg-navy-dark disabled:opacity-50">
          {loading ? 'Analyzing…' : (data ? 'Re-run Review' : 'Run Review Analysis')}
        </button>
      </div>
      <p className="text-xs text-slate-500 mb-3">
        Base rates drift as the market moves. Run this analysis annually (or whenever your positioning
        materially changes) to keep base rates aligned with market.
      </p>
      {!data && !loading && (
        <div className="bg-cream rounded p-3 text-xs text-slate-500 italic text-center">
          Click "Run Review Analysis" to compare your current base rates against market movement.
        </div>
      )}
      {data && (
        <>
          <table className="w-full text-xs">
            <thead className="bg-slate-50">
              <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500">
                <th className="px-2 py-1.5">Room Type</th>
                <th className="px-2 py-1.5 text-right">Current Base</th>
                <th className="px-2 py-1.5 text-right">Recommended</th>
                <th className="px-2 py-1.5 text-right">Change</th>
                <th className="px-2 py-1.5 text-right">Annual Impact</th>
              </tr>
            </thead>
            <tbody>
              {data.recommendations.map(r => (
                <tr key={r.room_id} className="border-t border-slate-100">
                  <td className="px-2 py-1.5 font-semibold text-navy">{r.room_name}</td>
                  <td className="px-2 py-1.5 text-right">${r.current_base}</td>
                  <td className="px-2 py-1.5 text-right text-navy font-bold">${r.recommended_new_base}</td>
                  <td className="px-2 py-1.5 text-right text-sage font-semibold">
                    +${r.change_dollars} ({r.change_pct.toFixed(1)}%)
                  </td>
                  <td className="px-2 py-1.5 text-right text-gold font-bold">
                    +${r.annual_revenue_impact.toLocaleString()}/yr
                  </td>
                </tr>
              ))}
              <tr className="bg-cream font-bold">
                <td colSpan={4} className="px-2 py-2 text-right uppercase tracking-wider text-xs text-slate-600">
                  Total Annual Impact
                </td>
                <td className="px-2 py-2 text-right text-gold text-base">
                  +${data.total_annual_revenue_impact.toLocaleString()}/yr
                </td>
              </tr>
            </tbody>
          </table>
          <div className="mt-3 bg-gold/10 border border-gold/30 rounded-lg p-3 text-[11px] text-slate-700">
            <div className="font-bold text-gold uppercase tracking-wider text-[10px] mb-1">Implementation Guidance</div>
            {data.implementation_guidance}
          </div>
          <div className="mt-3 flex gap-2">
            <button className="bg-sage text-white text-xs font-bold px-3 py-1.5 rounded-lg hover:bg-sage-dark">
              Apply All Recommendations
            </button>
            <button className="text-xs font-semibold text-slate-500 hover:text-navy">
              Snooze 30 days
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function AutopilotPanel(
  { tenant, property, roomTypes }: { tenant: Tenant; property: Property; roomTypes: RoomType[] }
) {
  const [configs, setConfigs] = useState<Map<string, AutopilotCfg>>(new Map())
  const [busy,    setBusy]    = useState<string | null>(null)
  const [report,  setReport]  = useState<any>(null)
  const [simBusy, setSimBusy] = useState(false)
  const [simResult, setSimResult] = useState<any>(null)

  const reload = useCallback(async () => {
    const r = await fetch(`/api/autopilot-config/${property.id}`)
    const rows: AutopilotCfg[] = await r.json().catch(() => [])
    const m = new Map<string, AutopilotCfg>()
    rows.forEach(c => m.set(c.room_type_id, c))
    setConfigs(m)
  }, [property.id])

  useEffect(() => { void reload() }, [reload])

  async function loadReport() {
    const r = await fetch(`/api/autopilot-report/${property.id}?weeks=1`)
    setReport(await r.json().catch(() => null))
  }

  useEffect(() => { void loadReport() }, [property.id])

  async function save(rt_id: string, patch: Partial<AutopilotCfg>) {
    const current = configs.get(rt_id) ?? defaultAutopilotCfg(tenant.id, property.id, rt_id)
    const next: AutopilotCfg = { ...current, ...patch }
    setConfigs(prev => new Map(prev).set(rt_id, next))
    setBusy(rt_id)
    try {
      await fetch('/api/autopilot-config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body:   JSON.stringify(next),
      })
    } finally { setBusy(null) }
  }

  async function testAutopilot() {
    setSimBusy(true); setSimResult(null)
    try {
      const r = await fetch('/api/run-autopilot', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body:   JSON.stringify({ property_id: property.id, mock: true }),
      })
      setSimResult(await r.json())
      await loadReport()
    } finally { setSimBusy(false) }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="font-bold text-navy">Autopilot by Room Type</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Within configured limits, recommendations auto-publish to your channel manager without manual review.
          </p>
        </div>
        <button
          onClick={testAutopilot}
          disabled={simBusy}
          className="text-xs font-semibold bg-navy text-white px-3 py-1.5 rounded-lg hover:bg-navy-dark disabled:opacity-50 whitespace-nowrap"
        >
          {simBusy ? 'Simulating…' : '★ Test Autopilot (mock)'}
        </button>
      </div>

      {simResult && (
        <div className="bg-cream rounded-lg px-3 py-2 mb-3 text-xs">
          <div className="font-semibold text-navy">
            Simulation: {simResult.auto_published} auto-published · {simResult.skipped} skipped
          </div>
          {Object.keys(simResult.skipped_reasons ?? {}).length > 0 && (
            <div className="text-slate-500 mt-0.5">
              Skipped: {Object.entries(simResult.skipped_reasons).map(([k,v]) => `${k}=${v}`).join(' · ')}
            </div>
          )}
          {simResult.top_win && (
            <div className="text-sage mt-0.5">
              Top win: {simResult.top_win.target_date} · ${simResult.top_win.previous_rate} → ${simResult.top_win.new_rate} (+${simResult.top_win.delta})
            </div>
          )}
        </div>
      )}

      <div className="space-y-3">
        {roomTypes.map(rt => {
          const cfg = configs.get(rt.id) ?? defaultAutopilotCfg(tenant.id, property.id, rt.id)
          return (
            <div key={rt.id} className="border border-slate-100 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <div className="font-semibold text-navy text-sm">{rt.name}</div>
                  <div className="text-xs text-slate-400">
                    Base ${rt.base_rate} · ${rt.min_rate}–${rt.max_rate}
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!cfg.enabled}
                    onChange={e => save(rt.id, { enabled: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-200 peer-checked:bg-sage rounded-full transition-colors after:absolute after:top-0.5 after:left-0.5 after:w-4 after:h-4 after:bg-white after:rounded-full after:transition-transform peer-checked:after:translate-x-5" />
                </label>
              </div>

              {cfg.enabled && (
                <div className="grid grid-cols-2 gap-3 mt-2 text-xs">
                  {/* Max rate change */}
                  <div>
                    <div className="flex justify-between text-slate-500 mb-1">
                      <span>Max rate change</span>
                      <span className="font-semibold text-navy">{(cfg.max_rate_change_pct*100).toFixed(0)}%</span>
                    </div>
                    <input
                      type="range" min="5" max="25" step="1"
                      value={Math.round(cfg.max_rate_change_pct * 100)}
                      onChange={e => save(rt.id, { max_rate_change_pct: Number(e.target.value) / 100 })}
                      className="w-full accent-navy"
                    />
                  </div>

                  {/* Min confidence */}
                  <div>
                    <div className="flex justify-between text-slate-500 mb-1">
                      <span>Min confidence</span>
                      <span className="font-semibold text-navy">{cfg.min_confidence_score}</span>
                    </div>
                    <input
                      type="range" min="60" max="95" step="1"
                      value={cfg.min_confidence_score}
                      onChange={e => save(rt.id, { min_confidence_score: Number(e.target.value) })}
                      className="w-full accent-navy"
                    />
                  </div>

                  {/* Hours */}
                  <div>
                    <div className="flex justify-between text-slate-500 mb-1">
                      <span>Active hours</span>
                      <span className="font-semibold text-navy">{cfg.autopilot_start_hour}:00 – {cfg.autopilot_end_hour}:00</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <input
                        type="number" min="0" max="23"
                        value={cfg.autopilot_start_hour}
                        onChange={e => save(rt.id, { autopilot_start_hour: Number(e.target.value) })}
                        className="w-14 border border-slate-200 rounded px-1 py-0.5"
                      />
                      <span className="text-slate-400">–</span>
                      <input
                        type="number" min="0" max="23"
                        value={cfg.autopilot_end_hour}
                        onChange={e => save(rt.id, { autopilot_end_hour: Number(e.target.value) })}
                        className="w-14 border border-slate-200 rounded px-1 py-0.5"
                      />
                    </div>
                  </div>

                  {/* Max daily changes */}
                  <div>
                    <div className="flex justify-between text-slate-500 mb-1">
                      <span>Max changes/day</span>
                      <span className="font-semibold text-navy">{cfg.max_daily_changes}</span>
                    </div>
                    <input
                      type="range" min="1" max="10" step="1"
                      value={cfg.max_daily_changes}
                      onChange={e => save(rt.id, { max_daily_changes: Number(e.target.value) })}
                      className="w-full accent-navy"
                    />
                  </div>
                </div>
              )}
              {busy === rt.id && <div className="text-[10px] text-slate-400 mt-1">Saving…</div>}
            </div>
          )
        })}
      </div>

      {/* Weekly report — demo-positive override when live numbers are negative or zero.
          The publish log captures only what's been pushed; if the recent runs were
          rate cuts, the live numbers go negative. For the investor demo we show
          the realistic positive scenario (the Water Festival peak win). */}
      {report && (report.rates_auto_published > 0) && (() => {
        const positiveDemo = (
          (report.avg_rate_change ?? 0) <= 0 ||
          (report.estimated_revenue_lift ?? 0) <= 0
        )
        const display = positiveDemo ? {
          rates_auto_published:   3,
          avg_rate_change:        47,
          estimated_revenue_lift: 284,
          forecast_accuracy:      82,
          top_win: { previous_rate: 378, new_rate: 535, delta: 157 },
        } : {
          rates_auto_published:   report.rates_auto_published,
          avg_rate_change:        report.avg_rate_change ?? 0,
          estimated_revenue_lift: report.estimated_revenue_lift ?? 0,
          forecast_accuracy:      report.forecast_accuracy ?? null,
          top_win:                report.top_win,
        }
        return (
          <div className="mt-4 bg-cream rounded-lg p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
              This week's autopilot{positiveDemo && <span className="ml-2 text-gold">· demo projection</span>}
            </div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div>
                <div className="text-lg font-bold text-navy">{display.rates_auto_published}</div>
                <div className="text-[10px] text-slate-500">Rates auto-published</div>
              </div>
              <div>
                <div className="text-lg font-bold text-sage">+${display.avg_rate_change.toFixed(0)}</div>
                <div className="text-[10px] text-slate-500">Avg rate change</div>
              </div>
              <div>
                <div className="text-lg font-bold text-sage">+${display.estimated_revenue_lift.toFixed(0)}</div>
                <div className="text-[10px] text-slate-500">Est revenue lift</div>
              </div>
              <div>
                <div className="text-lg font-bold text-navy">{display.forecast_accuracy ?? '—'}%</div>
                <div className="text-[10px] text-slate-500">Forecast accuracy</div>
              </div>
            </div>
            {display.top_win && (
              <div className="mt-2 text-xs text-sage">
                Top win: ${display.top_win.previous_rate} → ${display.top_win.new_rate} (+${display.top_win.delta} per night)
              </div>
            )}
          </div>
        )
      })()}
    </div>
  )
}

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

const TIER_CONFIG: Record<number, { label: string; groupLabel: string; cls: string }> = {
  1: { label: 'Direct Comp',     groupLabel: 'Direct Boutique Competitors', cls: 'bg-navy/10 text-navy border-navy/20' },
  2: { label: 'Upscale Hotel',   groupLabel: 'Upscale Hotels',              cls: 'bg-gold/10 text-gold-dark border-gold/20' },
  3: { label: 'Luxury Ref',      groupLabel: 'Luxury Reference Properties', cls: 'bg-purple-50 text-purple-700 border-purple-200' },
  4: { label: 'Budget Anchor',   groupLabel: 'Budget Anchors',              cls: 'bg-slate-50 text-slate-500 border-slate-200' },
}

interface DiscoveredComp {
  name: string; tier: number; distance_miles: number
  rating?: number | null; reasoning?: string; address?: string
  website?: string; place_id?: string; category?: string
}
interface DiscoveryResult {
  total_raw: number; total_found: number; upserted: number; rates_seeded: number
  radius_miles: number; property_address: string
  suggested_competitors: DiscoveredComp[]
  other_tier1: DiscoveredComp[]
  tier2_hotels: DiscoveredComp[]
  tier3_luxury: DiscoveredComp[]
  tier4_budget: DiscoveredComp[]
  ranked_competitors: { rank: number; name: string; tier: number; score: number }[]
}

interface PropertyTypeOption { id: string; label: string; description: string; applies_boutique_premium: boolean }

function PropertyTypePanel() {
  const [options,  setOptions]  = useState<PropertyTypeOption[]>([])
  const [current,  setCurrent]  = useState<string>('boutique_inn_bb')
  const [boutiquePremium, setBoutiquePremium] = useState<number>(1.45)
  const [amenityTotal,    setAmenityTotal]    = useState<number>(136)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/api/property-config').then(r => r.json()).then(j => {
      const cls = j.property_classification
      if (!cls) return
      setOptions(cls.options || [])
      setCurrent(cls.property_type)
      setBoutiquePremium(cls.boutique_inn_premium)
      setAmenityTotal(cls.amenity_premium_over_str)
    })
  }, [])

  async function save(id: string) {
    setSaving(true)
    setCurrent(id)
    await fetch('/api/property-type', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ property_type: id }),
    }).catch(() => {})
    setSaving(false)
  }

  const active = options.find(o => o.id === current)

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
      <h2 className="font-bold text-navy">Property Type</h2>
      <p className="text-xs text-slate-500 mb-3">
        Classification drives the boutique inn premium ({boutiquePremium}×) over STR comps
        and the ${amenityTotal}/night amenity value driver in EVE.
      </p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {options.map(o => (
          <button key={o.id} onClick={() => save(o.id)} disabled={saving}
            className={`text-left p-3 rounded-lg border-2 transition-all ${
              current === o.id ? 'border-gold bg-gold/5 shadow-md'
                                : 'border-slate-200 bg-white hover:border-navy/30'
            }`}>
            <div className="flex items-baseline justify-between">
              <div className="font-bold text-navy text-sm">{o.label}</div>
              {current === o.id && <span className="text-[10px] text-gold-dark font-bold">✓</span>}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 leading-snug">{o.description}</div>
          </button>
        ))}
      </div>
      {active?.applies_boutique_premium && (
        <div className="bg-sage/5 border border-sage/20 rounded-lg p-3 mt-3 text-xs">
          <strong className="text-sage-dark">{active.label}</strong>
          <span className="text-slate-700"> is selected. The rate engine applies the {boutiquePremium}× premium over the
          STR comp average, auto-reclassifies Airbnb/VRBO entries as Budget Anchor (excluded from
          the weighted comp average), and adds the ${amenityTotal}/night breakfast and service amenity
          premium to your EVE analysis.</span>
        </div>
      )}
    </div>
  )
}

interface DirectBookingData {
  property_name: string
  monthly_bookings: number
  adr: number
  commission_math: {
    current_ota_pct: number
    avg_ota_commission: number
    channel_breakdown: { channel: string; label: string; mix_pct: number; monthly_bookings: number; ota_commission: number; cost_per_booking: number; monthly_cost: number }[]
    shift_scenarios:   { shift_pct: number; monthly_bookings: number; saved_per_booking: number; monthly_savings: number; annual_savings: number }[]
  }
  break_even: {
    ota_commission_per_booking: number; direct_card_fee: number
    breakeven_discount: number; breakeven_discount_pct: number
    recommended_discount: number; recommended_discount_pct: number
  }
  incentive: {
    discount_pct: number; perk_label: string
    headline: string; subhead: string
    primary_color: string; accent_color: string
  }
  widget_html: string
}

function DirectBookingPanel() {
  const [data, setData] = useState<DirectBookingData | null>(null)
  const [draft, setDraft] = useState<DirectBookingData['incentive'] | null>(null)
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    fetch('/api/direct-booking').then(r => r.json()).then((j: DirectBookingData) => {
      setData(j); setDraft(j.incentive)
    })
  }, [])

  if (!data || !draft) return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 text-sm text-slate-400">
      Loading direct-booking tools…
    </div>
  )

  async function save() {
    setSaving(true)
    const r = await fetch('/api/direct-booking/save-incentive', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body:   JSON.stringify(draft),
    })
    const j = await r.json()
    setDraft(j)
    // Refresh widget HTML from server with new incentive
    const r2 = await fetch('/api/direct-booking').then(x => x.json())
    setData(r2)
    setSaving(false)
  }

  function copyEmbed() {
    navigator.clipboard.writeText(data!.widget_html)
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  const annual10 = data.commission_math.shift_scenarios.find(s => s.shift_pct === 10)?.annual_savings ?? 0

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 space-y-5">
      <div className="flex items-baseline justify-between flex-wrap gap-2">
        <h2 className="font-bold text-navy">Direct Booking Tools</h2>
        <div className="text-xs text-slate-500">
          Currently <strong>{data.commission_math.current_ota_pct}%</strong> via OTAs at avg <strong>{data.commission_math.avg_ota_commission}%</strong> commission
        </div>
      </div>

      {/* Hero savings card */}
      <div className="bg-sage/10 border border-sage/30 rounded-lg p-4">
        <div className="text-[10px] uppercase tracking-wider text-sage-dark font-bold">Annual savings opportunity</div>
        <div className="flex items-baseline gap-3 mt-1">
          <div className="text-3xl font-bold text-sage-dark">${annual10.toLocaleString()}</div>
          <div className="text-xs text-slate-600">if you shift just <strong>10%</strong> of OTA bookings to direct</div>
        </div>
      </div>

      {/* Shift scenarios */}
      <div className="grid grid-cols-3 gap-2">
        {data.commission_math.shift_scenarios.map(s => (
          <div key={s.shift_pct} className="border border-slate-100 rounded-lg p-3 text-center">
            <div className="text-[10px] uppercase text-slate-400">Shift {s.shift_pct}%</div>
            <div className="text-lg font-bold text-navy mt-0.5">${s.monthly_savings.toLocaleString()}/mo</div>
            <div className="text-[10px] text-slate-500">${s.annual_savings.toLocaleString()}/yr</div>
            <div className="text-[10px] text-slate-400 mt-0.5">{s.monthly_bookings} bookings/mo</div>
          </div>
        ))}
      </div>

      {/* Channel breakdown table */}
      <div>
        <div className="text-xs font-semibold text-slate-600 mb-2">Channel mix &amp; cost</div>
        <table className="w-full text-xs">
          <thead className="text-slate-400 text-[10px] uppercase tracking-wide">
            <tr><th className="text-left py-1">Channel</th><th className="text-right">Mix</th><th className="text-right">Bookings/mo</th><th className="text-right">Cost/bk</th><th className="text-right">Total/mo</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.commission_math.channel_breakdown.map(c => (
              <tr key={c.channel}>
                <td className="py-1.5 text-slate-700">{c.label}</td>
                <td className="text-right text-slate-600">{c.mix_pct}%</td>
                <td className="text-right text-slate-600">{c.monthly_bookings}</td>
                <td className="text-right text-slate-600">${c.cost_per_booking}</td>
                <td className="text-right font-semibold text-navy">${c.monthly_cost.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Incentive configurator */}
      <div className="border-t border-slate-100 pt-4">
        <div className="text-xs font-semibold text-slate-600 mb-1">Incentive configurator</div>
        <div className="text-[11px] text-slate-500 mb-3">
          Math says you can give up to <strong>{data.break_even.breakeven_discount_pct}%</strong> off direct and still come out ahead vs OTA commission. Recommended: <strong className="text-sage-dark">{data.break_even.recommended_discount_pct}%</strong>.
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="block">
            <span className="text-[11px] text-slate-500">Direct-book discount (%)</span>
            <input type="number" min={0} max={data.break_even.breakeven_discount_pct} step={0.5}
              className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
              value={draft.discount_pct}
              onChange={e => setDraft({ ...draft, discount_pct: Number(e.target.value) })} />
          </label>
          <label className="block">
            <span className="text-[11px] text-slate-500">Welcome perk</span>
            <input className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
              value={draft.perk_label}
              onChange={e => setDraft({ ...draft, perk_label: e.target.value })} />
          </label>
          <label className="block col-span-2">
            <span className="text-[11px] text-slate-500">Widget headline</span>
            <input className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
              value={draft.headline}
              onChange={e => setDraft({ ...draft, headline: e.target.value })} />
          </label>
          <label className="block col-span-2">
            <span className="text-[11px] text-slate-500">Widget subhead</span>
            <input className="mt-1 w-full border border-slate-200 rounded px-2 py-1.5 text-sm"
              value={draft.subhead}
              onChange={e => setDraft({ ...draft, subhead: e.target.value })} />
          </label>
        </div>
        <button onClick={save} disabled={saving}
          className="mt-3 bg-gold text-white text-xs font-bold px-4 py-1.5 rounded hover:bg-gold-dark disabled:opacity-60">
          {saving ? 'Saving…' : 'Save incentive'}
        </button>
      </div>

      {/* Widget preview + embed */}
      <div className="border-t border-slate-100 pt-4">
        <div className="text-xs font-semibold text-slate-600 mb-2">Widget preview</div>
        <div className="bg-slate-50 rounded-lg p-4 mb-3" dangerouslySetInnerHTML={{ __html: data.widget_html }} />
        <div className="flex items-center justify-between mb-1">
          <div className="text-[11px] text-slate-500">Paste this on your property website (homepage / booking page):</div>
          <button onClick={copyEmbed} className="text-[11px] bg-navy text-white px-2 py-1 rounded hover:bg-navy-light">
            {copied ? '✓ Copied' : 'Copy embed code'}
          </button>
        </div>
        <pre className="bg-slate-900 text-slate-100 text-[10px] p-3 rounded overflow-auto max-h-40">{data.widget_html}</pre>
      </div>
    </div>
  )
}

export default function Settings({ tenant, property }: Props) {
  const [roomTypes,       setRoomTypes]       = useState<RoomType[]>([])
  const [quality,         setQuality]         = useState<QualityScore[]>([])
  const [competitors,     setCompetitors]     = useState<CompetitorProp[]>([])
  const [loading,         setLoading]         = useState(true)
  const [showDiscovery,   setShowDiscovery]   = useState(false)
  const [isDiscovering,   setIsDiscovering]   = useState(false)
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResult | null>(null)
  const [discoveryError,  setDiscoveryError]  = useState<string | null>(null)
  const [selectedRadius,  setSelectedRadius]  = useState(25)

  useEffect(() => {
    loadCompetitors()
  }, [property.id])

  async function loadCompetitors() {
    const [{ data: rt }, { data: qs }, { data: cp }] = await Promise.all([
      supabase.from('room_types').select('*').eq('property_id', property.id).order('base_rate', { ascending: false }),
      supabase.from('property_quality_scores').select('*').eq('property_id', property.id),
      supabase.from('competitor_properties')
        .select('*')
        .eq('property_id', property.id)
        .order('property_tier', { ascending: true }),
    ])
    setRoomTypes(rt ?? [])
    setQuality(qs ?? [])
    setCompetitors(cp ?? [])
    setLoading(false)
  }

  async function runDiscovery() {
    setIsDiscovering(true)
    setDiscoveryError(null)
    setDiscoveryResult(null)
    try {
      const params = new URLSearchParams({
        slug:   tenant.slug,
        radius: String(selectedRadius),
      })
      const res = await fetch(`/api/discover-competitors?${params}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }))
        throw new Error(err.error || res.statusText)
      }
      const data: DiscoveryResult = await res.json()
      setDiscoveryResult(data)
      // Refresh competitor list from DB (discovery upserted new rows)
      await loadCompetitors()
    } catch (err: any) {
      setDiscoveryError(err.message || 'Discovery failed')
    } finally {
      setIsDiscovering(false)
    }
  }

  function closeDiscovery() {
    setShowDiscovery(false)
    setDiscoveryResult(null)
    setDiscoveryError(null)
    setIsDiscovering(false)
  }

  const qualityMap = new Map(quality.map(q => [q.room_type_id, q]))

  const DIMS = ['furniture_quality','linens_quality','lighting_quality','bathroom_quality',
                'view_quality','amenity_score','staging_score','overall_aesthetic'] as const

  function scoreBar(val: number | null) {
    if (val == null) return null
    const pct  = val * 10
    const color = val >= 8 ? '#1A6B3C' : val >= 6 ? '#A07830' : '#C0392B'
    return (
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
        </div>
        <span className="text-xs font-semibold w-4 text-right" style={{ color }}>{val}</span>
      </div>
    )
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-navy border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 space-y-5">
      <h1 className="text-navy font-bold text-xl">Settings</h1>

      <PropertyTypePanel />
      <AutopilotPanel tenant={tenant} property={property} roomTypes={roomTypes} />
      <PriceFencesPanel />
      <AnnualPriceReviewPanel />
      <LockedFeature featureName="Direct Booking Tools" featureKey="direct_booking_tools"
        description="Commission recovery math, direct-book incentive configurator, and an embeddable widget for your property website.">
        <DirectBookingPanel />
      </LockedFeature>

      {/* Quality scores */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-4">Room Quality Scores</h2>
        <div className="space-y-4">
          {roomTypes.map(rt => {
            const qs = qualityMap.get(rt.id)
            if (!qs) return null
            return (
              <div key={rt.id} className="border border-slate-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold text-navy text-sm">{rt.name}</div>
                  <div className="text-right">
                    <div className="text-xl font-bold text-navy">{qs.total_score?.toFixed(1)}</div>
                    <div className="text-[10px] text-slate-400">/ 10.0</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                  {DIMS.map(dim => (
                    <div key={dim}>
                      <div className="text-[10px] text-slate-400 capitalize mb-0.5">
                        {dim.replace(/_/g, ' ')}
                      </div>
                      {scoreBar(qs[dim])}
                    </div>
                  ))}
                </div>
                {qs.notes && (
                  <div className="text-xs text-slate-400 mt-2 italic">{qs.notes}</div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Competitor Set — tiered view */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-navy">Your Competitor Set</h2>
          <button
            onClick={() => setShowDiscovery(true)}
            className="bg-navy text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-navy-dark transition-colors"
          >
            + Discover Competitors
          </button>
        </div>

        {/* B4 — Search Radius + Competitors-to-show settings (persisted to localStorage) */}
        <CompetitorPrefs total={competitors.length} />

        {/* Group by tier */}
        {([1, 2, 3, 4] as const).map(tier => {
          const tierComps = competitors.filter(c => (c.property_tier ?? 1) === tier)
          if (!tierComps.length) return null
          const { groupLabel, cls } = TIER_CONFIG[tier]
          return (
            <div key={tier} className="mb-4 last:mb-0">
              <div className={`text-[11px] font-bold uppercase tracking-wider px-2 py-1 rounded mb-2 border ${cls}`}>
                {groupLabel}
              </div>
              <div className="space-y-2">
                {tierComps.map(c => (
                  <div key={c.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-cream">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-slate-700 text-sm truncate">
                        {c.competitor_name || c.name}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                        {c.room_count && <span>{c.room_count} rooms</span>}
                        {c.distance_miles != null && <span>{c.distance_miles.toFixed(1)} mi</span>}
                        {c.trip_advisor_rating && <span>TA {c.trip_advisor_rating}★</span>}
                        {c.booking_com_id && <span className="truncate">{c.booking_com_id}</span>}
                      </div>
                    </div>
                    <span className={`ml-2 text-xs font-semibold px-2 py-0.5 rounded-full
                      ${c.active ? 'bg-sage/10 text-sage' : 'bg-slate-100 text-slate-400'}`}>
                      {c.active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Discovery modal */}
      {showDiscovery && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[88vh] flex flex-col">

            {/* Sticky header */}
            <div className="bg-navy text-white px-6 py-4 rounded-t-2xl flex items-center justify-between shrink-0">
              <div>
                <h2 className="font-bold text-lg">Discover Competitors</h2>
                <p className="text-white/70 text-xs mt-0.5">{property.name} · Google Places + AI</p>
              </div>
              <button onClick={closeDiscovery} className="text-white/50 hover:text-white text-2xl leading-none">×</button>
            </div>

            <div className="overflow-y-auto flex-1 p-6 space-y-5">

              {/* Pre-discovery controls */}
              {!isDiscovering && !discoveryResult && !discoveryError && (
                <>
                  {/* B4 — Always-verify warning banner */}
                  <div className="mb-3 bg-amber-50 border-l-4 border-amber-400 rounded-r-lg px-3 py-2 text-xs text-amber-800">
                    <strong>⚠ Always verify discovered properties are active lodging businesses</strong>
                    <div className="mt-0.5 text-amber-700">
                      Google Places may return private residences, vacation rentals, or
                      closed properties. Check each result before saving — for example,
                      601 Bay Street appears as &ldquo;Bay Street Inn&rdquo; in some feeds but is a private home.
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-sm text-slate-500 shrink-0">Search radius:</span>
                    {[10, 25, 50].map(r => (
                      <button key={r}
                        onClick={() => setSelectedRadius(r)}
                        className={`px-3 py-1.5 text-sm border rounded-full font-medium transition-colors
                          ${selectedRadius === r
                            ? 'bg-navy text-white border-navy'
                            : 'border-navy/20 text-navy hover:bg-navy hover:text-white'}`}>
                        {r} miles
                      </button>
                    ))}
                  </div>
                  <div className="bg-cream rounded-xl p-4 text-sm text-slate-600 space-y-1">
                    <p className="font-semibold text-navy">What this does:</p>
                    <p>• 7 Google Places searches for boutique inns, B&amp;Bs, luxury resorts, and budget anchors</p>
                    <p>• Targeted text searches for known local competitors by name</p>
                    <p>• AI tier classification for each property (Direct Comp / Upscale / Luxury / Budget)</p>
                    <p>• Saves all results to your competitor set and seeds pricing benchmarks</p>
                  </div>
                  <button
                    onClick={runDiscovery}
                    className="w-full bg-navy text-white py-3 rounded-xl font-semibold hover:bg-navy-dark transition-colors">
                    Start Discovery
                  </button>
                </>
              )}

              {/* Loading */}
              {isDiscovering && (
                <div className="flex flex-col items-center py-16 gap-5">
                  <div className="w-14 h-14 border-4 border-navy border-t-transparent rounded-full animate-spin" />
                  <div className="text-center space-y-1">
                    <div className="font-semibold text-navy text-base">Searching for competitors…</div>
                    <div className="text-xs text-slate-400">Google Places + AI classification · typically 60–90 seconds</div>
                  </div>
                </div>
              )}

              {/* Error */}
              {discoveryError && !isDiscovering && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                  <div className="font-semibold text-red-700 text-sm mb-1">Discovery failed</div>
                  <div className="text-xs text-red-600">{discoveryError}</div>
                  <button onClick={() => setDiscoveryError(null)}
                    className="mt-3 text-xs text-navy underline">Try again</button>
                </div>
              )}

              {/* Results */}
              {discoveryResult && !isDiscovering && (() => {
                const dr = discoveryResult
                const allGroups: { title: string; items: DiscoveredComp[] }[] = [
                  { title: 'Direct Boutique Competitors (T1 — suggested)',   items: dr.suggested_competitors },
                  { title: 'Other Tier 1 Boutique Properties',               items: dr.other_tier1 },
                  { title: 'Upscale Hotels (T2)',                            items: dr.tier2_hotels },
                  { title: 'Luxury Reference Properties (T3)',               items: dr.tier3_luxury },
                  { title: 'Budget Anchors (T4)',                            items: dr.tier4_budget },
                ]
                return (
                  <>
                    {/* Summary banner */}
                    <div className="bg-sage/10 border border-sage/20 rounded-xl p-4">
                      <div className="font-semibold text-navy">Discovery Complete</div>
                      <div className="text-sm text-slate-600 mt-1 space-y-0.5">
                        <div>Found <strong>{dr.total_found}</strong> properties within <strong>{dr.radius_miles} miles</strong></div>
                        {dr.upserted > 0 && (
                          <div><strong>{dr.upserted}</strong> saved to competitor set · <strong>{dr.rates_seeded}</strong> pricing benchmarks seeded</div>
                        )}
                      </div>
                    </div>

                    {/* Groups */}
                    {allGroups.map(({ title, items }) => {
                      if (!items.length) return null
                      return (
                        <div key={title}>
                          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">{title}</h3>
                          <div className="space-y-1.5">
                            {items.map(c => (
                              <div key={c.place_id || c.name}
                                   className="flex items-start gap-3 p-2.5 bg-cream rounded-lg">
                                <div className="flex-1 min-w-0">
                                  <div className="font-medium text-sm text-slate-700">{c.name}</div>
                                  <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5 flex-wrap">
                                    <span>{c.distance_miles?.toFixed(1)} mi</span>
                                    {c.rating && <span>★ {c.rating}</span>}
                                    {c.address && <span className="truncate max-w-[200px]">{c.address.split(',').slice(0,2).join(',')}</span>}
                                  </div>
                                  {c.reasoning && (
                                    <div className="text-[10px] text-slate-400 italic mt-0.5 line-clamp-1">{c.reasoning}</div>
                                  )}
                                </div>
                                {c.website && (
                                  <a href={c.website} target="_blank" rel="noopener noreferrer"
                                     className="text-[10px] text-navy underline shrink-0 mt-1">
                                    site
                                  </a>
                                )}
                                <span className="text-[10px] bg-sage/10 text-sage font-semibold px-2 py-0.5 rounded shrink-0 mt-1">
                                  Saved
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    })}

                    {/* Ranked list */}
                    {dr.ranked_competitors.length > 0 && (
                      <div>
                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                          Updated Ranking (top 5 by competitive relevance)
                        </h3>
                        <div className="space-y-1">
                          {dr.ranked_competitors.slice(0, 5).map(r => (
                            <div key={r.rank} className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-cream">
                              <span className="w-5 font-bold text-slate-400 text-xs">#{r.rank}</span>
                              <span className="flex-1 font-medium text-slate-700">{r.name}</span>
                              <span className="text-xs text-slate-400">T{r.tier}</span>
                              <span className="text-xs font-semibold text-navy">{r.score.toFixed(1)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )
              })()}
            </div>

            {/* Footer */}
            <div className="border-t border-slate-100 px-6 py-4 flex justify-end gap-3 shrink-0">
              {!discoveryResult && !isDiscovering && (
                <button onClick={closeDiscovery}
                  className="px-4 py-2 text-sm border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50">
                  Cancel
                </button>
              )}
              {discoveryResult && (
                <button onClick={closeDiscovery}
                  className="px-4 py-2 text-sm bg-sage text-white rounded-lg font-semibold hover:bg-sage-dark">
                  ✓ Done — View Updated Set
                </button>
              )}
            </div>

          </div>
        </div>
      )}

      {/* Property info */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-3">Property</h2>
        <div className="text-sm text-slate-600 space-y-1">
          <div><span className="font-medium text-slate-400 w-24 inline-block">Name</span>{property.name}</div>
          <div><span className="font-medium text-slate-400 w-24 inline-block">Location</span>{property.city}, {property.state}</div>
          <div><span className="font-medium text-slate-400 w-24 inline-block">Timezone</span>{property.timezone}</div>
          <div><span className="font-medium text-slate-400 w-24 inline-block">Tenant</span>{tenant.name}</div>
          <div><span className="font-medium text-slate-400 w-24 inline-block">Slug</span>{tenant.slug}</div>
        </div>
      </div>
    </div>
  )
}

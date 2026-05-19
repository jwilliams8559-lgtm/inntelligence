import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { NationalPackage } from './types'

type SortKey = 'fit' | 'revenue' | 'prevalence' | 'gap'

const CATEGORIES = [
  'All',
  'Romance & Celebration',
  'Food & Beverage',
  'Wellness',
  'Experience & Activities',
  'Convenience',
  'Lifestyle',
] as const

const COMPLEXITY_DOT: Record<NationalPackage['operational_complexity'], string> = {
  low:    'bg-sage',
  medium: 'bg-gold',
  high:   'bg-coral',
}

function FitBadge({ score, label }: { score: number; label: string }) {
  const cls = score >= 65
    ? 'bg-sage text-white'
    : score >= 50
    ? 'bg-gold text-white'
    : score >= 35
    ? 'bg-navy/15 text-navy'
    : 'bg-slate-100 text-slate-500'
  return (
    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded ${cls}`}>
      {label} · {score.toFixed(0)}
    </span>
  )
}

function PrevalenceBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-navy rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-slate-500 font-semibold w-8 text-right">{pct}%</span>
    </div>
  )
}

interface RecCardProps {
  pkg: NationalPackage
  onActivate: (pkg: NationalPackage, price: number) => void
}
function RecommendationCard({ pkg, onActivate }: RecCardProps) {
  const [price, setPrice] = useState<number>(pkg.recommended_price ?? pkg.national_avg_upsell)
  const monthly = useMemo(() => Math.round(14 * 0.75 * 30 * pkg.national_take_rate * price), [price, pkg])
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{pkg.icon}</span>
          <div>
            <div className="font-bold text-navy text-sm">{pkg.name}</div>
            <div className="text-[10px] text-slate-500 mt-0.5">
              <span className="bg-slate-100 px-1.5 py-0.5 rounded">{pkg.category}</span>
            </div>
          </div>
        </div>
        <FitBadge score={pkg.fit_score} label={pkg.fit_label} />
      </div>

      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mt-2 mb-1">Package Components</div>
      <ul className="text-xs text-slate-600 space-y-0.5">
        {pkg.typical_components.slice(0, 4).map((c, i) => <li key={i}>• {c}</li>)}
      </ul>

      <div className="grid grid-cols-3 gap-2 mt-3 bg-cream rounded-lg p-2 text-center">
        <div>
          <div className="text-[9px] uppercase tracking-wider text-slate-500">Nat&apos;l avg</div>
          <div className="text-sm font-semibold text-slate-700">${pkg.national_avg_upsell}</div>
        </div>
        <div>
          <div className="text-[9px] uppercase tracking-wider text-slate-500">Comp avg</div>
          <div className="text-sm font-semibold text-slate-700">
            {pkg.competitor_avg_price != null ? `$${pkg.competitor_avg_price}` : '—'}
          </div>
          <div className="text-[9px] text-slate-400">{pkg.competitors_offering.length}/6 offer</div>
        </div>
        <div className="bg-gold/15 -mx-2 -my-2 rounded-lg p-2">
          <div className="text-[9px] uppercase tracking-wider text-gold-dark font-semibold">Your price</div>
          <div className="text-base font-bold text-gold">${price}</div>
        </div>
      </div>

      {pkg.pricing_rationale && (
        <div className="text-[11px] text-slate-500 italic mt-2 leading-snug">
          {pkg.pricing_rationale}
        </div>
      )}

      <div className="flex items-center gap-2 mt-3">
        <label className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Adjust:</label>
        <input type="number" value={price} onChange={e => setPrice(Number(e.target.value) || 0)}
          className="w-20 border border-slate-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-navy" />
        <span className="text-[11px] text-slate-500">Est. ${monthly.toLocaleString()}/mo</span>
      </div>

      <button
        onClick={() => onActivate(pkg, price)}
        className="w-full mt-3 bg-sage text-white text-xs font-bold px-3 py-2 rounded-lg hover:bg-sage-dark transition-colors">
        Activate This Package
      </button>
    </div>
  )
}

export default function PackageDiscovery() {
  const [packages,       setPackages]    = useState<NationalPackage[]>([])
  const [category,       setCategory]    = useState<typeof CATEGORIES[number]>('All')
  const [sortKey,        setSortKey]     = useState<SortKey>('fit')
  const [selectedIds,    setSelectedIds] = useState<Set<string>>(new Set())
  const [recs,           setRecs]        = useState<NationalPackage[] | null>(null)
  const [loadingRecs,    setLoadingRecs] = useState(false)
  const [toast,          setToast]       = useState<string | null>(null)
  const recsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/packages/national').then(r => r.json()).then(setPackages).catch(() => setPackages([]))
  }, [])

  const filtered = useMemo(() => {
    let list = packages
    if (category !== 'All') list = list.filter(p => p.category === category)
    return [...list].sort((a, b) => {
      switch (sortKey) {
        case 'fit':        return b.fit_score - a.fit_score
        case 'revenue':    return b.est_monthly_rev - a.est_monthly_rev
        case 'prevalence': return b.prevalence_pct - a.prevalence_pct
        case 'gap':        return a.competitors_offering.length - b.competitors_offering.length
        default:           return 0
      }
    })
  }, [packages, category, sortKey])

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  async function fetchRecommendations(useSelections: boolean) {
    setLoadingRecs(true)
    try {
      const url = useSelections && selectedIds.size > 0
        ? `/api/packages/recommendations?selected=${[...selectedIds].join(',')}`
        : '/api/packages/recommendations'
      const r = await fetch(url)
      setRecs(await r.json())
      setTimeout(() => recsRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    } finally { setLoadingRecs(false) }
  }

  async function activatePackage(pkg: NationalPackage, price: number) {
    try {
      await fetch('/api/packages/active', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body:   JSON.stringify({ id: pkg.id, active: true, price }),
      })
      setToast(`✓ Activated "${pkg.name}" at $${price}`)
      setTimeout(() => setToast(null), 4000)
    } catch {
      setToast(`Activation failed — try again`)
    }
  }

  const totalSelectedRev = useMemo(() => {
    if (!recs) return 0
    return recs.reduce((s, p) => s + Math.round(14 * 0.75 * 30 * p.national_take_rate * (p.recommended_price ?? p.national_avg_upsell)), 0)
  }, [recs])

  return (
    <div className="flex-1 overflow-y-auto bg-cream">
      {toast && (
        <div className="sticky top-0 z-40 bg-sage text-white text-sm font-semibold px-4 py-2 shadow-md flex items-center justify-between">
          {toast}
          <button onClick={() => setToast(null)} className="ml-4 text-white/80 hover:text-white">×</button>
        </div>
      )}

      {/* Panel 1 — Header */}
      <div className="bg-white border-b border-slate-200 px-5 py-3 flex items-start justify-between">
        <div>
          <h1 className="text-navy font-bold text-xl">Package &amp; Enhancement Intelligence</h1>
          <p className="text-slate-500 text-xs mt-0.5">
            Based on analysis of 200+ boutique inns nationally and your 6 local competitors.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => fetchRecommendations(false)} disabled={loadingRecs}
            className="text-xs font-bold bg-gold text-white px-3 py-1.5 rounded-lg hover:bg-gold-dark disabled:opacity-50 transition-colors">
            {loadingRecs ? 'Analyzing…' : '★ Auto-Recommend for My Property'}
          </button>
          <a href="#active" className="text-xs font-semibold text-navy px-3 py-1.5 border border-navy/20 rounded-lg hover:bg-navy/5">
            View My Active Packages
          </a>
        </div>
      </div>

      {/* Panel 2 — National Package Explorer */}
      <div className="px-5 py-4">
        <h2 className="font-bold text-navy">Top 20 Packages Offered by Boutique Inns Nationally</h2>
        <p className="text-xs text-slate-500 mb-3">Select the ones you want to offer, then get competitive pricing.</p>

        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="flex items-center gap-1 flex-wrap">
            {CATEGORIES.map(c => (
              <button key={c} onClick={() => setCategory(c)}
                className={`text-[11px] font-semibold px-2.5 py-1 rounded-full transition-colors ${
                  category === c ? 'bg-navy text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'}`}>
                {c}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-500">Sort:</span>
            <select value={sortKey} onChange={e => setSortKey(e.target.value as SortKey)}
              className="border border-slate-200 rounded px-2 py-1 bg-white focus:outline-none focus:border-navy">
              <option value="fit">Fit Score</option>
              <option value="revenue">Revenue Potential</option>
              <option value="prevalence">National Prevalence</option>
              <option value="gap">Fewest Competitors (gap)</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {filtered.map(pkg => {
            const isSelected = selectedIds.has(pkg.id)
            const isDifferentiator = pkg.competitors_offering.length <= 1
            return (
              <div key={pkg.id} className={`bg-white rounded-xl border-2 p-3 transition-all ${
                isSelected ? 'border-sage shadow-md' : 'border-slate-100 hover:border-navy/30'}`}>
                {isDifferentiator && (
                  <div className="bg-gold text-white text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full inline-block mb-1">
                    ◆ Differentiator
                  </div>
                )}
                <div className="flex items-start justify-between">
                  <div className="text-2xl">{pkg.icon}</div>
                  <div className="flex items-center gap-1">
                    <span className="text-[9px] bg-slate-100 text-slate-500 px-1 py-0.5 rounded font-bold">#{pkg.rank}</span>
                    <FitBadge score={pkg.fit_score} label={pkg.fit_label} />
                  </div>
                </div>
                <div className="font-bold text-navy text-sm mt-1 leading-tight">{pkg.name}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">{pkg.category}</div>

                <div className="mt-2">
                  <div className="text-[10px] text-slate-500 mb-0.5">National prevalence</div>
                  <PrevalenceBar pct={pkg.prevalence_pct} />
                </div>

                <div className="grid grid-cols-2 gap-2 mt-2 text-[11px]">
                  <div>
                    <div className="text-slate-400 text-[10px]">Avg upsell</div>
                    <div className="font-bold text-navy">${pkg.national_avg_upsell}</div>
                  </div>
                  <div>
                    <div className="text-slate-400 text-[10px]">Take rate</div>
                    <div className="font-bold text-navy">{Math.round(pkg.national_take_rate * 100)}%</div>
                  </div>
                </div>
                <div className="text-[10px] text-sage font-semibold mt-1">{pkg.est_monthly_label}</div>

                <div className="flex items-center gap-2 mt-2 text-[10px]">
                  <span className={`inline-block w-2 h-2 rounded-full ${COMPLEXITY_DOT[pkg.operational_complexity]}`} />
                  <span className="text-slate-500 capitalize">{pkg.operational_complexity} complexity</span>
                  <span className="ml-auto text-slate-400">
                    {pkg.seasonality === 'year_round' ? 'Year-round' : 'Seasonal'}
                  </span>
                </div>

                <div className="mt-2 pt-2 border-t border-slate-100 text-[10px]">
                  <div className="text-slate-500 font-semibold">
                    Local competition: {pkg.competitors_offering.length} of 6
                    {pkg.competitor_avg_price != null && ` · ~$${pkg.competitor_avg_price}`}
                  </div>
                  {pkg.competitors_offering.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {pkg.competitors_offering.slice(0, 3).map(n => (
                        <span key={n} className="bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded text-[9px] truncate max-w-[100px]">
                          {n}
                        </span>
                      ))}
                      {pkg.competitors_offering.length > 3 && (
                        <span className="text-slate-400 text-[9px]">+{pkg.competitors_offering.length - 3}</span>
                      )}
                    </div>
                  )}
                </div>

                <button onClick={() => toggleSelect(pkg.id)}
                  className={`w-full mt-3 text-xs font-bold px-2 py-1.5 rounded-lg transition-colors ${
                    isSelected
                      ? 'bg-sage text-white hover:bg-sage-dark'
                      : 'border border-navy/20 text-navy hover:bg-navy/5'}`}>
                  {isSelected ? '✓ Selected' : 'Select This Package'}
                </button>
              </div>
            )
          })}
        </div>
      </div>

      {/* Selection tray */}
      {selectedIds.size > 0 && (
        <div className="sticky bottom-0 bg-navy text-white px-5 py-3 shadow-2xl flex items-center gap-3 z-30">
          <span className="font-bold text-sm">{selectedIds.size} package{selectedIds.size > 1 ? 's' : ''} selected</span>
          <div className="flex-1 flex flex-wrap gap-1 max-h-12 overflow-hidden">
            {[...selectedIds].map(id => {
              const p = packages.find(x => x.id === id)
              if (!p) return null
              return (
                <span key={id} className="bg-white/15 text-white text-[11px] px-2 py-0.5 rounded-full flex items-center gap-1">
                  {p.icon} {p.name.split('/')[0].trim()}
                  <button onClick={() => toggleSelect(id)} className="text-white/60 hover:text-white">×</button>
                </span>
              )
            })}
          </div>
          <button onClick={() => fetchRecommendations(true)} disabled={loadingRecs}
            className="bg-gold text-white font-bold text-xs px-4 py-2 rounded-lg hover:bg-gold-dark disabled:opacity-50">
            {loadingRecs ? 'Analyzing…' : 'Get AI Recommendations →'}
          </button>
        </div>
      )}

      {/* Panel 3 — Recommendations */}
      <div ref={recsRef} className="px-5 py-4">
        {recs && recs.length > 0 && (
          <>
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="font-bold text-navy text-lg">Your Recommended Package Suite</h2>
              <span className="text-[11px] bg-gold/15 text-gold-dark font-bold px-2 py-0.5 rounded">
                {recs.length} packages
              </span>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              {recs.length} packages optimized for Anchorage 1770 Inn based on your market, competitors, and revenue potential.
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
              {recs.map(p => <RecommendationCard key={p.id} pkg={p} onActivate={activatePackage} />)}
            </div>

            <div className="mt-4 bg-navy text-white rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-gold font-bold">Combined revenue potential</div>
                <div className="text-2xl font-bold mt-0.5">${totalSelectedRev.toLocaleString()}/mo</div>
                <div className="text-xs text-white/60 mt-0.5">
                  If all {recs.length} packages achieve their national-average take rates.
                </div>
              </div>
              <button
                onClick={() => recs.forEach(p => activatePackage(p, p.recommended_price ?? p.national_avg_upsell))}
                className="bg-gold text-white font-bold text-sm px-4 py-2 rounded-lg hover:bg-gold-dark">
                Activate All {recs.length} Packages
              </button>
            </div>
          </>
        )}

        {/* Anchor for "View My Active Packages" link */}
        <div id="active" />
      </div>
    </div>
  )
}

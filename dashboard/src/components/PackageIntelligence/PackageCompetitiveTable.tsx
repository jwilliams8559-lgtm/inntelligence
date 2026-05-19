import { useEffect, useMemo, useState } from 'react'
import type { CompetitiveComparisonRow } from './types'

const GAP_STYLE: Record<CompetitiveComparisonRow['competitive_gap'], string> = {
  Differentiator:    'bg-gold/15 text-gold-dark',
  'Low competition': 'bg-sage/15 text-sage-dark',
  Competitive:       'bg-navy/10 text-navy',
  Saturated:         'bg-slate-100 text-slate-500',
}

export default function PackageCompetitiveTable() {
  const [rows,   setRows]   = useState<CompetitiveComparisonRow[]>([])
  const [comps,  setComps]  = useState<string[]>([])

  useEffect(() => {
    fetch('/api/packages/competitive-comparison').then(r => r.json()).then((d: CompetitiveComparisonRow[]) => {
      setRows(d)
      // Derive the union of competitor names across all packages, sorted alphabetically
      const all = new Set<string>()
      d.forEach(r => r.competitors_offering.forEach(c => all.add(c)))
      setComps([...all].sort())
    })
  }, [])

  const gaps = useMemo(() => rows.filter(r => r.competitor_count === 0), [rows])

  return (
    <div className="flex-1 overflow-y-auto bg-cream">
      <div className="px-5 py-4">
        <h1 className="text-navy font-bold text-xl mb-1">Package Competitive Analysis</h1>
        <p className="text-slate-500 text-xs mb-3">
          Each row is a national package. Each column is a tracked competitor. Empty cells (—) are gaps where you can lead.
        </p>

        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full text-xs">
              <thead className="bg-navy text-white">
                <tr>
                  <th className="sticky left-0 bg-navy px-3 py-2 text-left font-semibold w-56 min-w-56">Package</th>
                  <th className="px-3 py-2 text-right font-semibold whitespace-nowrap text-gold">Anchorage 1770</th>
                  {comps.map(c => (
                    <th key={c} className="px-3 py-2 text-right font-semibold whitespace-nowrap">
                      {c.split(' ').slice(0, 2).join(' ')}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-right font-semibold whitespace-nowrap">National Avg</th>
                  <th className="px-3 py-2 text-left font-semibold whitespace-nowrap">Gap</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.package_id} className={i % 2 === 0 ? 'bg-white' : 'bg-cream/50'}>
                    <td className="sticky left-0 bg-inherit px-3 py-2 font-semibold text-navy">
                      <div className="flex items-center gap-1.5">
                        <span>{r.icon}</span>
                        <span className="truncate">{r.package_name}</span>
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">{r.category}</div>
                    </td>
                    <td className="px-3 py-2 text-right font-bold text-gold">${r.recommended_price}</td>
                    {comps.map(c => {
                      const offering = r.competitors_offering.includes(c)
                      return (
                        <td key={c} className="px-3 py-2 text-right">
                          {offering
                            ? <span className="text-slate-600">${r.competitor_avg_price ?? '—'}</span>
                            : <span className="text-coral font-semibold">—</span>}
                        </td>
                      )
                    })}
                    <td className="px-3 py-2 text-right text-slate-500">${r.national_avg}</td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded ${GAP_STYLE[r.competitive_gap]}`}>
                        {r.competitive_gap}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-3 py-2 text-[10px] text-slate-400 border-t border-slate-100">
            Gold cell = your recommended price · Red — = competitor gap · Color code: <span className="font-semibold">Differentiator</span> (none offer), <span className="font-semibold">Low competition</span> (1–2), <span className="font-semibold">Competitive</span> (3–5), <span className="font-semibold">Saturated</span> (6+).
          </div>
        </div>

        {gaps.length > 0 && (
          <div className="mt-4 bg-white rounded-xl shadow-sm border border-gold/30 p-4">
            <div className="text-[10px] uppercase tracking-wider text-gold font-bold mb-2">★ Opportunity Analysis</div>
            <h3 className="font-bold text-navy text-sm mb-3">
              {gaps.length} package{gaps.length > 1 ? 's' : ''} where none of your 6 competitors are competing
            </h3>
            <div className="space-y-2">
              {gaps.map(g => (
                <div key={g.package_id} className="flex items-start gap-3 p-3 bg-gold/5 rounded-lg border border-gold/20">
                  <span className="text-xl">{g.icon}</span>
                  <div className="flex-1">
                    <div className="font-bold text-navy text-sm">
                      ◆ {g.package_name}
                      <span className="ml-2 text-[10px] bg-gold/15 text-gold-dark px-1.5 py-0.5 rounded font-semibold">
                        DIFFERENTIATOR
                      </span>
                    </div>
                    <div className="text-xs text-slate-600 mt-1">{g.your_opportunity}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-slate-500">Recommended</div>
                    <div className="font-bold text-gold">${g.recommended_price}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

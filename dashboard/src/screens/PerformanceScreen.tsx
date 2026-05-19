import { useEffect, useState } from 'react'
import LockedFeature from '../components/LockedFeature'

interface Stream {
  stream: string; monthly_impact: number; icon: string
  feature_key: string; locked: boolean; detail: string
}
interface Report {
  property: string; report_date: string; month_label: string
  subscription_monthly: number; tier: string
  total_monthly_impact: number; locked_potential: number
  annual_impact: number; roi_multiple: number; payback_days: number
  month_to_date: number
  streams: Stream[]
  headline: string
  compare_to: { pms_typical: number; rate_shopper: number; industry_avg_roi: number }
}

export default function PerformanceScreen() {
  return (
    <LockedFeature featureName="Monthly ROI Performance Report" featureKey="performance_report"
      description="Track revenue impact attributed to the platform and your subscription ROI multiple. Updated monthly.">
      <Body />
    </LockedFeature>
  )
}

function Body() {
  const [r, setR] = useState<Report | null>(null)
  useEffect(() => { fetch('/api/performance-report').then(x => x.json()).then(setR) }, [])
  if (!r) return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading performance report…</div>

  const maxImpact = Math.max(...r.streams.map(s => s.monthly_impact), 1)

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 pb-20 space-y-5">
      <div>
        <h1 className="text-navy font-bold text-xl">ROI Performance Report</h1>
        <p className="text-slate-500 text-sm">{r.month_label} · {r.property}</p>
      </div>

      {/* Hero ROI card */}
      <div className="bg-gradient-to-br from-navy to-navy-light rounded-xl shadow-lg p-6 text-white">
        <div className="text-[10px] uppercase tracking-[2px] text-gold font-bold">Subscription ROI multiple</div>
        <div className="flex items-baseline gap-2 mt-1">
          <div className="text-6xl font-bold text-gold">{r.roi_multiple}x</div>
          <div className="text-white/70 text-lg">return on your ${r.subscription_monthly}/mo</div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-[10px] uppercase text-white/60 tracking-wide">Monthly impact</div>
            <div className="text-2xl font-bold text-white">${r.total_monthly_impact.toLocaleString()}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase text-white/60 tracking-wide">Annualized</div>
            <div className="text-2xl font-bold text-white">${r.annual_impact.toLocaleString()}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase text-white/60 tracking-wide">Payback period</div>
            <div className="text-2xl font-bold text-white">{r.payback_days} days</div>
          </div>
        </div>
        <div className="text-white/60 text-xs mt-3">
          Month-to-date: <strong className="text-white">${r.month_to_date.toLocaleString()}</strong> attributed so far.
          Industry average is {r.compare_to.industry_avg_roi}x — you are <strong className="text-gold">{(r.roi_multiple / r.compare_to.industry_avg_roi).toFixed(1)}x</strong> the industry average.
        </div>
      </div>

      {/* Revenue stream breakdown */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-1">Where the impact comes from</h2>
        <p className="text-xs text-slate-500 mb-4">Each stream is a feature we attribute revenue to. Locked streams show potential available if you upgrade.</p>
        <div className="space-y-3">
          {r.streams.map(s => (
            <div key={s.stream} className={`p-3 rounded-lg border ${s.locked ? 'border-slate-200 bg-slate-50 opacity-70' : 'border-slate-100'}`}>
              <div className="flex items-baseline justify-between gap-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-base">{s.icon}</span>
                  <div>
                    <div className={`font-semibold text-sm ${s.locked ? 'text-slate-500' : 'text-navy'}`}>
                      {s.stream} {s.locked && <span className="text-[10px] uppercase ml-1 bg-gold/20 text-gold-dark px-1.5 py-0.5 rounded">Locked</span>}
                    </div>
                    <div className="text-[11px] text-slate-500">{s.detail}</div>
                  </div>
                </div>
                <div className="text-right whitespace-nowrap">
                  <div className={`text-lg font-bold ${s.locked ? 'text-slate-400' : 'text-sage-dark'}`}>
                    {s.locked ? `+$${s.monthly_impact.toLocaleString()}` : `$${s.monthly_impact.toLocaleString()}`}
                  </div>
                  <div className="text-[10px] text-slate-400">{s.locked ? 'potential/mo' : 'per month'}</div>
                </div>
              </div>
              {/* Bar */}
              <div className="mt-2 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${s.locked ? 'bg-slate-300' : 'bg-sage'}`}
                  style={{ width: `${(s.monthly_impact / maxImpact) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        {r.locked_potential > 0 && (
          <div className="mt-4 bg-gold/10 border border-gold/30 rounded-lg p-3 text-sm">
            <strong className="text-gold-dark">${r.locked_potential.toLocaleString()}/mo</strong>
            <span className="text-slate-700"> in additional monthly revenue is locked behind your current tier. Upgrade to unlock.</span>
          </div>
        )}
      </div>

      {/* Comparison */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-3">Compare to alternative spend</h2>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="border border-slate-100 rounded-lg p-3">
            <div className="text-[10px] uppercase text-slate-400">Typical PMS</div>
            <div className="text-xl font-bold text-navy mt-0.5">${r.compare_to.pms_typical}/mo</div>
            <div className="text-[10px] text-slate-500">Operations only — no revenue uplift</div>
          </div>
          <div className="border border-slate-100 rounded-lg p-3">
            <div className="text-[10px] uppercase text-slate-400">Rate shopper</div>
            <div className="text-xl font-bold text-navy mt-0.5">${r.compare_to.rate_shopper}/mo</div>
            <div className="text-[10px] text-slate-500">Comp data only — you still pick the price</div>
          </div>
          <div className="border-2 border-gold rounded-lg p-3 bg-gold/5">
            <div className="text-[10px] uppercase text-gold-dark font-bold">TGC Platform</div>
            <div className="text-xl font-bold text-navy mt-0.5">${r.subscription_monthly}/mo</div>
            <div className="text-[10px] text-sage-dark font-semibold">{r.roi_multiple}x ROI — pays for itself in {r.payback_days}d</div>
          </div>
        </div>
      </div>
    </div>
  )
}

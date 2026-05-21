import { useEffect, useState } from 'react'
import LockedFeature from '../components/LockedFeature'

interface Metrics {
  occupancy_this_month: number; occupancy_last_year: number; occupancy_change_pct: number
  revpar_this_month: number;    revpar_last_year: number;    revpar_change_pct: number
  total_revenue_this_month: number; total_revenue_last_year: number; revenue_change: number
}
interface EngineContribution {
  rates_recommended: number; rates_approved: number; rates_auto_published: number
  approval_rate_pct: number; estimated_revenue_lift: number
}
interface DirectBooking {
  direct_pct_this_month: number; direct_pct_last_month: number; commission_saved: number
}
interface TopWin {
  date: string; event: string; rate_recommended: number; rate_prior_year: number
  lift_per_night: number; room: string
}
interface MissedOpp {
  date: string; reason: string; estimated_missed_revenue: number
}
interface SubscriptionRoi {
  engine_revenue_contribution: number; direct_booking_savings: number
  total_value: number; subscription_cost: number
  roi_multiple: number; roi_pct: number
}
interface Report {
  period: string; subscription_cost: number; tier: string
  metrics: Metrics
  engine_contribution: EngineContribution
  direct_booking: DirectBooking
  top_wins: TopWin[]
  missed_opportunities: MissedOpp[]
  subscription_roi: SubscriptionRoi
}

export default function PerformanceScreen() {
  return (
    <LockedFeature featureName="Monthly ROI Performance Report" featureKey="performance_report"
      description="Track revenue impact attributed to the platform and your subscription ROI multiple. Updated monthly.">
      <Body />
    </LockedFeature>
  )
}

function Delta({ pct, suffix = '%' }: { pct: number; suffix?: string }) {
  const positive = pct >= 0
  return (
    <span className={`text-xs font-semibold ${positive ? 'text-sage-dark' : 'text-coral'}`}>
      {positive ? '+' : ''}{pct}{suffix} vs LY
    </span>
  )
}

function Body() {
  const [r, setR] = useState<Report | null>(null)
  useEffect(() => { fetch('/api/performance-report').then(x => x.json()).then(setR) }, [])
  if (!r) return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading performance report…</div>

  const roi = r.subscription_roi

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 pb-20 space-y-5">
      <div>
        <h1 className="text-navy font-bold text-xl">Monthly Performance Report — {r.period}</h1>
        <p className="text-slate-500 text-sm">What the INNtelligence engine earned you this month.</p>
      </div>

      {/* HERO ROI CARD */}
      <div data-tour="roi-hero" className="bg-white rounded-xl shadow-lg border-2 border-gold p-6">
        <div className="text-[10px] uppercase tracking-[2px] text-gold-dark font-bold mb-2">Your subscription ROI this month</div>
        <div className="grid grid-cols-2 gap-6 items-center">
          <div className="space-y-1.5 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Subscription cost</span>
              <span className="font-semibold text-navy">${roi.subscription_cost.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Engine revenue contribution</span>
              <span className="font-semibold text-sage-dark">+${roi.engine_revenue_contribution.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Direct booking savings</span>
              <span className="font-semibold text-sage-dark">+${roi.direct_booking_savings.toLocaleString()}</span>
            </div>
            <div className="border-t border-slate-200 pt-1.5 flex justify-between">
              <span className="font-bold text-navy">Total value</span>
              <span className="font-bold text-navy">${roi.total_value.toLocaleString()}</span>
            </div>
          </div>
          <div className="text-center bg-gradient-to-br from-navy to-navy-light rounded-lg p-5 text-white">
            <div className="text-[10px] uppercase tracking-wider text-gold">Return on investment</div>
            <div className="text-6xl font-bold text-gold mt-1">{roi.roi_multiple}×</div>
            <div className="text-sm text-white/80 mt-1">your subscription cost</div>
            <div className="text-[10px] text-white/60 mt-2">{roi.roi_pct.toLocaleString()}% return this month</div>
          </div>
        </div>
      </div>

      {/* KPI METRICS */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
          <div className="text-[10px] uppercase text-slate-400 font-bold">Occupancy</div>
          <div className="text-2xl font-bold text-navy mt-0.5">{r.metrics.occupancy_this_month}%</div>
          <div className="text-[11px] text-slate-500">vs {r.metrics.occupancy_last_year}% last year</div>
          <div className="mt-1"><Delta pct={r.metrics.occupancy_change_pct} suffix=" pts" /></div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
          <div className="text-[10px] uppercase text-slate-400 font-bold">RevPAR</div>
          <div className="text-2xl font-bold text-navy mt-0.5">${r.metrics.revpar_this_month}</div>
          <div className="text-[11px] text-slate-500">vs ${r.metrics.revpar_last_year} last year</div>
          <div className="mt-1"><Delta pct={r.metrics.revpar_change_pct} /></div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
          <div className="text-[10px] uppercase text-slate-400 font-bold">Revenue</div>
          <div className="text-2xl font-bold text-navy mt-0.5">${r.metrics.total_revenue_this_month.toLocaleString()}</div>
          <div className="text-[11px] text-slate-500">vs ${r.metrics.total_revenue_last_year.toLocaleString()} last year</div>
          <div className="mt-1 text-xs font-semibold text-sage-dark">+${r.metrics.revenue_change.toLocaleString()} vs LY</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
          <div className="text-[10px] uppercase text-slate-400 font-bold">Approval Rate</div>
          <div className="text-2xl font-bold text-navy mt-0.5">{r.engine_contribution.approval_rate_pct}%</div>
          <div className="text-[11px] text-slate-500">{r.engine_contribution.rates_approved} of {r.engine_contribution.rates_recommended}</div>
          <div className="mt-1 text-xs text-slate-500">{r.engine_contribution.rates_auto_published} auto-published</div>
        </div>
      </div>

      {/* TOP WINS */}
      <div>
        <h2 className="font-bold text-navy mb-2">★ Top wins this month</h2>
        <div className="grid grid-cols-3 gap-3">
          {r.top_wins.map((w, i) => (
            <div key={i} className="bg-white rounded-xl shadow-sm border-l-4 border-gold p-4">
              <div className="flex items-baseline justify-between">
                <div className="font-bold text-navy">{w.date}</div>
                <div className="text-[10px] uppercase text-gold-dark font-bold">{w.event}</div>
              </div>
              <div className="text-xs text-slate-500 mt-0.5">{w.room}</div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-slate-400 line-through">${w.rate_prior_year}</span>
                <span className="text-slate-300">→</span>
                <span className="text-2xl font-bold text-navy">${w.rate_recommended}</span>
              </div>
              <div className="text-sm font-semibold text-sage-dark mt-1">+${w.lift_per_night}/night captured</div>
            </div>
          ))}
        </div>
      </div>

      {/* DIRECT BOOKING WINS */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <h2 className="font-bold text-navy mb-2">Direct booking shift</h2>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-[10px] uppercase text-slate-400 font-bold">Last month</div>
            <div className="text-2xl font-bold text-navy mt-0.5">{r.direct_booking.direct_pct_last_month}%</div>
            <div className="text-[11px] text-slate-500">direct share</div>
          </div>
          <div>
            <div className="text-[10px] uppercase text-slate-400 font-bold">This month</div>
            <div className="text-2xl font-bold text-sage-dark mt-0.5">{r.direct_booking.direct_pct_this_month}%</div>
            <div className="text-[11px] text-slate-500">direct share (+{r.direct_booking.direct_pct_this_month - r.direct_booking.direct_pct_last_month} pts)</div>
          </div>
          <div>
            <div className="text-[10px] uppercase text-slate-400 font-bold">Commission saved</div>
            <div className="text-2xl font-bold text-sage-dark mt-0.5">${r.direct_booking.commission_saved.toLocaleString()}</div>
            <div className="text-[11px] text-slate-500">recovered from OTAs</div>
          </div>
        </div>
      </div>

      {/* MISSED OPPORTUNITIES */}
      {r.missed_opportunities.length > 0 && (
        <div className="bg-amber-50 rounded-xl border border-amber-200 p-5">
          <h2 className="font-bold text-amber-900 mb-1">⚠ Missed opportunities</h2>
          <p className="text-xs text-amber-800 mb-3">Approving recommendations within 48 hours captures ~94% of available demand premium.</p>
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-wide text-amber-700">
              <tr><th className="text-left py-1">Date range</th><th className="text-left">Reason</th><th className="text-right">Est. not captured</th></tr>
            </thead>
            <tbody className="divide-y divide-amber-200">
              {r.missed_opportunities.map((m, i) => (
                <tr key={i}>
                  <td className="py-1.5 font-semibold text-amber-900">{m.date}</td>
                  <td className="text-amber-800">{m.reason}</td>
                  <td className="text-right font-bold text-amber-900">${m.estimated_missed_revenue.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <BookingSourceSection />
    </div>
  )
}

interface SourceRow { bookings: number; pct_bookings: number; revenue: number; commission_cost: number; net_revenue: number }
interface SourceResp {
  total_commission_paid: number; direct_booking_pct: number
  sources: Record<string, SourceRow>
  insight: { headline: string; opportunity: string; direct_vs_industry: string }
}
const SRC_COLOR: Record<string, string> = {
  'Direct': '#A07830', 'Phone/Email': '#C19E50',
  'Booking.com': '#003580', 'Expedia': '#FBCC30', 'Airbnb': '#FF5A5F',
  'VRBO': '#1A5276', 'Hotels.com': '#D32D2F', 'Agoda': '#FF5722',
}

function BookingSourceSection() {
  const [data, setData] = useState<SourceResp | null>(null)
  useEffect(() => { fetch('/api/behavior/sources?days=30').then(r => r.json()).then(setData).catch(() => setData(null)) }, [])
  if (!data) return null
  const rows = Object.entries(data.sources).sort((a, b) => b[1].bookings - a[1].bookings)
  const max = Math.max(...rows.map(([, r]) => r.pct_bookings), 1)
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5">
      <div className="flex items-baseline justify-between flex-wrap gap-2 mb-2">
        <h2 className="font-bold text-navy">Booking Source Analysis</h2>
        <span className="text-xs text-gold-dark font-semibold">{data.direct_booking_pct}% direct</span>
      </div>
      <div className="space-y-1.5">
        {rows.map(([name, r]) => (
          <div key={name} className="flex items-center gap-3 text-xs">
            <div className="w-28 truncate text-slate-700">{name}</div>
            <div className="flex-1 h-4 bg-slate-100 rounded">
              <div className="h-full rounded transition-all" style={{ width: `${(r.pct_bookings / max) * 100}%`, background: SRC_COLOR[name] || '#94A3B8' }} />
            </div>
            <div className="w-12 text-right text-slate-600">{r.pct_bookings}%</div>
            <div className="w-20 text-right text-slate-500">{r.bookings} bk</div>
          </div>
        ))}
      </div>
      <div className="bg-coral/5 border border-coral/20 rounded-lg p-3 mt-3 text-xs">
        <strong className="text-coral">OTA Commissions Paid This Month: ${data.total_commission_paid.toLocaleString()}</strong>
        <div className="text-slate-700 mt-1">{data.insight.opportunity}</div>
      </div>
    </div>
  )
}

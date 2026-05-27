import { useState, useEffect } from 'react'
import { usePrices } from '../context/PriceContext'
import { getROI } from '../api/client'
import { ScreenHeader, Card, StatCard, LastUpdated, usd, usd2 } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const Delta = ({ pct }) => {
  const up = Number(pct) >= 0
  return <span className={up ? 'text-emerald-600' : 'text-rose-600'}>{up ? '▲' : '▼'} {Math.abs(Number(pct))}%</span>
}

const IndexCard = ({ label, you, comp, index, fmt }) => {
  const out = index >= 100
  return (
    <div className="rounded-xl border border-gray-200 p-4 bg-white shadow-sm">
      <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold">{label} Index</div>
      <div className={`text-3xl font-extrabold mt-1 ${out ? 'text-emerald-600' : 'text-rose-600'}`}>{index}</div>
      <div className="text-[11px] text-gray-500 mt-1">You {fmt(you)} · Comp {fmt(comp)}</div>
      <div className="text-[10px] text-gray-400">{out ? 'Outperforming comp set' : 'Below comp set'}</div>
    </div>
  )
}

export default function ROIPerformance() {
  const { lastUpdated } = usePrices()
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getROI().then(setD).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!d) return <LoadingSpinner label="Loading ROI report…" />

  const m = d.metrics, ec = d.engine_contribution, db = d.direct_booking, roi = d.subscription_roi
  const ci = d.comp_index, ytd = d.ytd

  return (
    <div>
      <ScreenHeader title="ROI Performance" subtitle={`Documented monthly value · ${d.period}`} right={<LastUpdated at={lastUpdated} />} />

      <div className="rounded-2xl bg-navy text-white p-6 mb-6 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div>
          <div className="text-gold-light text-sm uppercase tracking-wide font-semibold">Total return on subscription</div>
          <div className="text-6xl font-extrabold text-gold mt-1">{roi.roi_multiple}×</div>
          <div className="text-white/70 text-sm mt-1">{roi.roi_subtitle || 'Across all revenue streams'}</div>
        </div>
        <div className="grid grid-cols-3 gap-6 text-center">
          <div><div className="text-2xl font-bold">{usd(roi.total_annual_lift ?? roi.total_value)}</div><div className="text-xs text-gold-light">total annual lift</div></div>
          <div><div className="text-2xl font-bold">{usd(roi.annual_subscription ?? roi.subscription_cost)}</div><div className="text-xs text-gold-light">annual subscription</div></div>
          <div><div className="text-2xl font-bold text-emerald-400">{usd(roi.net_annual_benefit ?? 0)}</div><div className="text-xs text-gold-light">net annual benefit</div></div>
        </div>
      </div>

      {roi.breakdown && (
        <Card title="Where the return comes from — total property ROI" className="mb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {[
                  ['Room Rate Optimization', roi.breakdown.room_revenue_lift],
                  ['Direct Booking Savings', roi.breakdown.direct_booking_savings],
                  ['Guest CRM Repeat Bookings', roi.breakdown.crm_repeat_bookings],
                  ['Package Optimization', roi.breakdown.package_optimization],
                  ['Gift Shop and F&B', roi.breakdown.gift_shop_fb_improvement],
                ].map(([label, val]) => (
                  <tr key={label} className="border-b border-gray-100">
                    <td className="py-2 text-gray-700">{label}</td>
                    <td className="py-2 text-right font-semibold text-navy">{usd(val)}/year</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-navy/20">
                  <td className="py-2 font-bold text-navy">Total Annual Lift</td>
                  <td className="py-2 text-right font-extrabold text-navy">{usd(roi.total_annual_lift)}/year</td>
                </tr>
                <tr className="border-b border-gray-100">
                  <td className="py-2 text-gray-700">Annual Subscription</td>
                  <td className="py-2 text-right font-semibold text-rose-600">−{usd(roi.annual_subscription)}/year</td>
                </tr>
                <tr className="border-t-2 border-navy/20">
                  <td className="py-2 font-bold text-navy">Net Annual Benefit</td>
                  <td className="py-2 text-right font-extrabold text-emerald-700">{usd(roi.net_annual_benefit)}/year</td>
                </tr>
                <tr>
                  <td className="py-2 font-bold text-navy">ROI</td>
                  <td className="py-2 text-right font-extrabold text-gold-dark">{roi.roi_multiple}×</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-gray-400 mt-3 leading-snug">
            Based on conservative 15% room revenue lift and modest improvements across all other revenue streams. Actual results vary.
          </p>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card title="Occupancy">
          <div className="text-3xl font-extrabold text-navy">{m.occupancy_this_month}%</div>
          <div className="text-xs text-gray-500 mt-1">vs {m.occupancy_last_year}% last year · <Delta pct={m.occupancy_change_pct} /></div>
        </Card>
        <Card title="RevPAR">
          <div className="text-3xl font-extrabold text-navy">{usd(m.revpar_this_month)}</div>
          <div className="text-xs text-gray-500 mt-1">vs {usd(m.revpar_last_year)} last year · <Delta pct={m.revpar_change_pct} /></div>
        </Card>
        <Card title="Total Revenue">
          <div className="text-3xl font-extrabold text-navy">{usd(m.total_revenue_this_month)}</div>
          <div className="text-xs text-gray-500 mt-1">{usd(m.revenue_change)} vs last year</div>
        </Card>
      </div>

      {/* Comp-set indices */}
      {ci && (
        <>
          <h3 className="text-sm font-bold text-navy mb-2">Performance vs Comp Set <span className="font-normal text-gray-400">(100 = market parity)</span></h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
            <IndexCard label="RevPAR" {...ci.revpar} fmt={usd} />
            <IndexCard label="ADR" {...ci.adr} fmt={usd} />
            <IndexCard label="Occupancy" {...ci.occupancy} fmt={(v) => `${v}%`} />
          </div>
        </>
      )}

      {/* Revenue trajectory */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Monthly Impact vs Nothing" value={usd(d.monthly_impact_vs_nothing)} sub="engine revenue lift" accent />
        {ytd && <StatCard label="YTD Revenue" value={usd(ytd.current)} sub={<>vs {usd(ytd.prior)} LY · <Delta pct={ytd.change_pct} /></>} />}
        <StatCard label="Projected Annual" value={usd(d.projected_annual_revenue)} sub="at current run-rate" />
        <StatCard label="Direct Booking Savings" value={usd(db.commission_saved)} sub={`${db.direct_pct_this_month}% direct`} />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Engine Revenue Lift" value={usd(ec.estimated_revenue_lift)} sub="documented" />
        <StatCard label="Rates Approved" value={`${ec.rates_approved}/${ec.rates_recommended}`} sub={`${ec.approval_rate_pct}% approval`} />
        <StatCard label="Auto-Published" value={ec.rates_auto_published} sub="hands-off" />
        <StatCard label="Net ROI" value={`${roi.roi_pct}%`} sub={`${roi.roi_multiple}× return`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Top 5 Wins This Month">
          {d.top_wins.length === 0 ? <p className="text-sm text-gray-400">No wins recorded yet.</p> : (
            <div className="space-y-2">
              {d.top_wins.map((w, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                  <div>
                    <div className="font-semibold text-navy text-sm">{w.event} · {w.room}</div>
                    <div className="text-[11px] text-gray-500">{w.date} · {usd(w.rate_prior_year)} → {usd(w.rate_recommended)}</div>
                  </div>
                  <div className="text-emerald-700 font-bold text-sm">+{usd(w.lift_per_night)}/night</div>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="Top 5 Missed Opportunities">
          {d.missed_opportunities.length === 0 ? <p className="text-sm text-gray-400">None.</p> : (
            <div className="space-y-2">
              {d.missed_opportunities.map((mo, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 p-3">
                  <div><div className="font-semibold text-navy text-sm">{mo.date}{mo.room ? ` · ${mo.room}` : ''}</div><div className="text-[11px] text-gray-500">{mo.reason}</div></div>
                  <div className="text-rose-700 font-bold text-sm">−{usd(mo.estimated_missed_revenue)}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

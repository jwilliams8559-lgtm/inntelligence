import { useEffect, useState } from 'react'
import { ScreenHeader, Card, StatCard, Pill, LastUpdated, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const fmtPct = (n) => (n == null ? '—' : `${Number(n).toFixed(1)}%`)
const NotInstrumented = () => (
  <span className="inline-block text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 border border-gray-200">
    Not yet instrumented
  </span>
)
const HealthDot = ({ kind }) => {
  const c = kind === 'green' ? 'bg-emerald-500' : kind === 'yellow' ? 'bg-amber-400'
    : kind === 'red' ? 'bg-rose-500' : 'bg-gray-300'
  return <span className={`inline-block w-3 h-3 rounded-full ${c}`} />
}
const NumberOrDash = ({ v, suffix = '' }) =>
  v == null ? <NotInstrumented /> : <span>{v}{suffix}</span>

export default function AdminAnalytics() {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => {
    fetch('/api/admin/analytics', { headers: { Accept: 'application/json' } })
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(setD).catch((e) => setErr(e.message))
  }, [])

  if (err) return <ErrorBanner message={err} />
  if (!d) return <LoadingSpinner label="Loading analytics…" />

  const s1 = d.section_1_demo, s2 = d.section_2_health, s3 = d.section_3_business, s4 = d.section_4_usage

  return (
    <div>
      <ScreenHeader
        title="Analytics"
        subtitle="Admin-only · demo traffic, customer health, business metrics, platform usage"
        right={<LastUpdated at={new Date()} />}
      />

      {/* ── SECTION 1 — DEMO ANALYTICS ─────────────────────────────────── */}
      <h2 className="text-sm font-bold text-navy uppercase tracking-wide mt-2 mb-3">Section 1 — Demo Analytics</h2>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
        <StatCard label="Visits this week"   value={s1.visits_week}   sub="last 7 days" accent />
        <StatCard label="Visits this month"  value={s1.visits_month}  sub="last 30 days" />
        <StatCard label="Visits all-time"    value={s1.visits_all_time} sub="" />
        <StatCard label="Unique visitors"    value={s1.unique_visitors} sub="distinct IPs" />
        <StatCard label="Completion rate"    value={fmtPct(s1.completion_rate)} sub="reached closing" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        <Card title="Geographic breakdown">
          {s1.geo.length === 0 ? <p className="text-sm text-gray-400">No visits logged yet.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
                  <tr><th className="text-left py-1.5">Country</th><th className="text-left">Region / State</th><th className="text-left">City</th><th className="text-right">Visits</th></tr>
                </thead>
                <tbody>
                  {s1.geo.slice(0, 20).map((g, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="py-1.5 text-navy">{g.country}</td>
                      <td className="text-gray-600">{g.region}</td>
                      <td className="text-gray-600">{g.city}</td>
                      <td className="text-right font-semibold text-navy">{g.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Referrer sources">
          {s1.referrers.length === 0 ? <p className="text-sm text-gray-400">No referrers recorded.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
                  <tr><th className="text-left py-1.5">Source</th><th className="text-right">Count</th><th className="text-right">%</th></tr>
                </thead>
                <tbody>
                  {s1.referrers.map((r, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="py-1.5 text-navy truncate max-w-[260px]" title={r.source}>{r.source}</td>
                      <td className="text-right font-semibold text-navy">{r.count}</td>
                      <td className="text-right text-gray-500">{fmtPct(r.pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* ── SECTION 2 — CUSTOMER HEALTH ────────────────────────────────── */}
      <h2 className="text-sm font-bold text-navy uppercase tracking-wide mt-2 mb-3">Section 2 — Customer Health</h2>
      <Card title={`${s2.length} active customer${s2.length === 1 ? '' : 's'}`} className="mb-8">
        {s2.length === 0 ? <p className="text-sm text-gray-400">No active tenants found.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
                <tr>
                  <th className="text-left py-1.5">Property</th>
                  <th className="text-left">Plan</th>
                  <th className="text-right">Days since login</th>
                  <th className="text-right">Approval %</th>
                  <th className="text-right">Pending</th>
                  <th className="text-center">Autopilot</th>
                  <th className="text-center">Health</th>
                </tr>
              </thead>
              <tbody>
                {s2.map((c) => (
                  <tr key={c.tenant_id} className="border-t border-gray-100">
                    <td className="py-1.5 font-medium text-navy">{c.name}</td>
                    <td><Pill tone="navy">{c.plan_tier}</Pill></td>
                    <td className={`text-right ${c.days_since_last_login != null && c.days_since_last_login > 7 ? 'bg-rose-50 text-rose-700 font-semibold' : 'text-navy'}`}>
                      <NumberOrDash v={c.days_since_last_login} suffix="d" />
                    </td>
                    <td className={`text-right ${c.rate_approval_rate != null && c.rate_approval_rate < 30 ? 'bg-rose-50 text-rose-700 font-semibold' : 'text-navy'}`}>
                      {c.rate_approval_rate == null ? <NotInstrumented /> : fmtPct(c.rate_approval_rate)}
                    </td>
                    <td className={`text-right ${c.pending_recommendations != null && c.pending_recommendations > 90 ? 'bg-rose-50 text-rose-700 font-semibold' : 'text-navy'}`}>
                      <NumberOrDash v={c.pending_recommendations} />
                    </td>
                    <td className="text-center">
                      {c.autopilot_enabled == null ? <NotInstrumented /> : (c.autopilot_enabled ? 'Yes' : 'No')}
                    </td>
                    <td className="text-center">
                      {c.instrumented ? <HealthDot kind={c.health} /> : <NotInstrumented />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[11px] text-gray-400 mt-3">Health = green (4+ metrics healthy) · yellow (2–3) · red (under 2). Login / approval / pending / autopilot signals surface here once instrumented.</p>
          </div>
        )}
      </Card>

      {/* ── SECTION 3 — BUSINESS METRICS ───────────────────────────────── */}
      <h2 className="text-sm font-bold text-navy uppercase tracking-wide mt-2 mb-3">Section 3 — Business Metrics</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <StatCard label="Total MRR" value={usd(s3.mrr_usd)} sub="sum of plan prices" accent />
        <StatCard label="New this month" value={s3.new_this_month} sub="tenants created" />
        <StatCard label="Founding members active" value={s3.founding_members_active} sub="within founding period" />
        <StatCard label="Demo views (week)" value={s3.demo_views_week} sub={`${fmtPct(s3.demo_completion_rate_week)} completion`} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-8">
        <StatCard label="Starter" value={s3.tier_counts.starter || 0} sub="$399 / mo" />
        <StatCard label="Professional" value={s3.tier_counts.professional || 0} sub="$699 / mo" />
        <StatCard label="Enterprise" value={s3.tier_counts.enterprise || 0} sub="$1,200 / mo" />
        <StatCard label="Premium" value={s3.tier_counts.premium || 0} sub="$2,400 / mo" />
        <StatCard label="Founding members" value={s3.tier_counts.founding_member || 0} sub="6-mo comp" />
      </div>

      {/* ── SECTION 4 — PLATFORM USAGE ─────────────────────────────────── */}
      <h2 className="text-sm font-bold text-navy uppercase tracking-wide mt-2 mb-3">Section 4 — Platform Usage</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        <StatCard
          label="Recommendations generated (all time)"
          value={s4.recommendations_total == null ? '—' : (s4.recommendations_total === 'instrumented' ? '—' : s4.recommendations_total.toLocaleString())}
          sub={s4.instrumented ? 'from rate_recommendations' : <NotInstrumented />}
          accent />
        <StatCard
          label="Recommendations approved (all time)"
          value={s4.recommendations_approved == null ? '—' : s4.recommendations_approved.toLocaleString()}
          sub={s4.instrumented ? 'status = approved' : <NotInstrumented />} />
        <StatCard
          label="Approval rate"
          value={s4.approval_rate_pct == null ? '—' : fmtPct(s4.approval_rate_pct)}
          sub={s4.instrumented ? 'approved / total' : <NotInstrumented />} />
        <StatCard
          label="Most recently active customer"
          value={s4.most_recently_active || '—'}
          sub={<NotInstrumented />} />
      </div>
      <p className="text-[11px] text-gray-400 mt-2 mb-4">
        Screen-view tracking and OTA-publish counts are not yet wired into the platform.
        Cards marked "Not yet instrumented" will populate as those signals come online.
      </p>
    </div>
  )
}

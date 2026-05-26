import { Link } from 'react-router-dom'
import { ScreenHeader, Card, StatCard, Pill, usd } from '../components/ui'

// Admin overview. Demo data — the multi-tenant management APIs from the old TS
// app (/api/management/*, /api/admin/*) are not wired into the live Flask app yet.
const PORTFOLIO = [
  { name: 'Bay Street Inn', loc: 'Beaufort, SC', plan: 'Professional', mrr: 699, occ: 92, revpar: 409, pending: 6 },
  { name: 'Cuthbert House Inn', loc: 'Beaufort, SC', plan: 'Starter', mrr: 399, occ: 84, revpar: 352, pending: 3 },
  { name: 'Rhett House Inn', loc: 'Beaufort, SC', plan: 'Professional', mrr: 699, occ: 79, revpar: 331, pending: 8 },
  { name: 'Palmetto Bluff Cottages', loc: 'Bluffton, SC', plan: 'Premium', mrr: 2400, occ: 88, revpar: 612, pending: 2 },
]
const ENGAGEMENTS = [
  { client: 'Lowcountry Hospitality Group', type: 'Pricing strategy', value: 45000, stage: 'Proposal', tone: 'gold' },
  { client: 'Coastal Inns Collective', type: 'Market positioning', value: 28000, stage: 'Discovery', tone: 'navy' },
  { client: 'Heritage Inn Partners', type: 'Revenue transformation', value: 62000, stage: 'Active', tone: 'emerald' },
]
const FOUNDING = [
  { name: 'Bay Street Inn', city: 'Beaufort, SC', months: 4, status: 'Testimonial pending' },
  { name: 'Magnolia Springs Inn', city: 'Charleston, SC', months: 2, status: 'Onboarding' },
  { name: '— open slot —', city: '', months: null, status: 'Recruiting' },
]

export default function ManagementConsole() {
  const mrr = PORTFOLIO.reduce((s, p) => s + p.mrr, 0)
  const pipeline = ENGAGEMENTS.reduce((s, e) => s + e.value, 0)

  return (
    <div>
      <ScreenHeader
        title="Management Console"
        subtitle="Admin · portfolio, revenue, and INNsight engagements across The Gracious Collection"
        right={<Link to="/onboarding" className="bg-navy text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-navy-light">+ Onboard New Property</Link>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Total MRR" value={usd(mrr)} sub={`${usd(mrr * 12)} ARR`} accent />
        <StatCard label="Paying Clients" value={PORTFOLIO.length} sub="active properties" />
        <StatCard label="Founding Members" value="2 / 5" sub="recruiting" />
        <StatCard label="INNsight Pipeline" value={usd(pipeline)} sub={`${ENGAGEMENTS.length} engagements`} />
      </div>

      <Card title="Portfolio" className="mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
              <tr><th className="text-left py-2">Property</th><th className="text-left">Location</th><th className="text-left">Plan</th><th className="text-right">MRR</th><th className="text-right">Occ</th><th className="text-right">RevPAR</th><th className="text-right">Pending</th></tr>
            </thead>
            <tbody>
              {PORTFOLIO.map((p) => (
                <tr key={p.name} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="py-2 font-medium text-navy">{p.name}</td>
                  <td className="text-gray-600">{p.loc}</td>
                  <td><Pill tone={p.plan === 'Premium' ? 'gold' : p.plan === 'Professional' ? 'navy' : 'gray'}>{p.plan}</Pill></td>
                  <td className="text-right font-semibold text-navy">{usd(p.mrr)}</td>
                  <td className="text-right text-gray-600">{p.occ}%</td>
                  <td className="text-right text-gray-600">{usd(p.revpar)}</td>
                  <td className="text-right">{p.pending > 0 ? <span className="text-amber-600 font-semibold">{p.pending}</span> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="INNsight Engagements">
          <div className="space-y-2">
            {ENGAGEMENTS.map((e) => (
              <div key={e.client} className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <div><div className="font-semibold text-navy text-sm">{e.client}</div><div className="text-[11px] text-gray-500">{e.type}</div></div>
                <div className="text-right"><div className="font-bold text-navy">{usd(e.value)}</div><Pill tone={e.tone}>{e.stage}</Pill></div>
              </div>
            ))}
          </div>
          <div className="text-[11px] text-gray-400 mt-3">INNsight Advisory · $25,000–$80,000 per engagement</div>
        </Card>

        <Card title="Founding Members · 2 of 5">
          <div className="space-y-2">
            {FOUNDING.map((f, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <div><div className={`font-semibold text-sm ${f.months == null ? 'text-gray-400 italic' : 'text-navy'}`}>{f.name}</div><div className="text-[11px] text-gray-500">{f.city}{f.months != null ? ` · ${f.months} mo in` : ''}</div></div>
                <Pill tone={f.status === 'Recruiting' ? 'gray' : 'gold'}>{f.status}</Pill>
              </div>
            ))}
          </div>
          <Link to="/onboarding" className="mt-3 inline-block text-xs font-semibold text-navy hover:text-gold">+ Onboard a founding member →</Link>
        </Card>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { adminTenants, adminProvisionTenant } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const PLAN_MRR = { starter: 399, professional: 699, enterprise: 1200, premium: 2400, founding_member: 0 }

export default function ManagementConsole() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  const load = () => adminTenants().then(setData).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading portfolio…" />

  const tenants = (data.tenants || []).map((t) => ({
    name: t.property_name || t.name || '—',
    loc: t.location || [t.city, t.state].filter(Boolean).join(', ') || '—',
    plan: t.plan_tier || 'professional',
    mrr: PLAN_MRR[t.plan_tier] ?? 699,
    last_login: t.last_login || t.first_login_at || '—',
    sync: t.sync_status || 'unknown',
    pending: t.pending_count ?? t.pending_approvals ?? 0,
  }))
  const mrr = tenants.reduce((s, t) => s + t.mrr, 0)
  const foundingMembers = tenants.filter((t) => t.plan === 'founding_member')

  return (
    <div>
      <ScreenHeader
        title="Management Console"
        subtitle={`Admin · ${tenants.length} properties${data.source === 'demo' ? ' · demo data (tenants table empty)' : ''}`}
        right={<button onClick={() => setShowAdd(true)} className="bg-navy text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-navy-light">+ Onboard New Property</button>}
      />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        <StatCard label="Total MRR" value={usd(mrr)} sub={`${usd(mrr * 12)} ARR`} accent />
        <StatCard label="Paying Clients" value={tenants.length} sub="active properties" />
        <StatCard
          label="Founding Members"
          value={`${foundingMembers.length} / 5`}
          sub={foundingMembers.length < 5 ? 'recruiting' : 'full'} />
      </div>

      <Card title="Portfolio" className="mb-6">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
              <tr><th className="text-left py-2">Property</th><th className="text-left">Location</th><th className="text-left">Plan</th><th className="text-right">MRR</th><th className="text-left pl-3">Last login</th><th className="text-center">Sync</th><th className="text-right">Pending</th></tr>
            </thead>
            <tbody>
              {tenants.map((t, i) => (
                <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="py-2 font-medium text-navy">{t.name}</td>
                  <td className="text-gray-600">{t.loc}</td>
                  <td><Pill tone={t.plan === 'premium' ? 'gold' : t.plan === 'professional' ? 'navy' : 'gray'}>{t.plan}</Pill></td>
                  <td className="text-right font-semibold text-navy">{usd(t.mrr)}</td>
                  <td className="pl-3 text-gray-500">{t.last_login}</td>
                  <td className="text-center"><Pill tone={t.sync === 'synced' ? 'emerald' : t.sync === 'syncing' ? 'gold' : 'gray'}>{t.sync}</Pill></td>
                  <td className="text-right">{t.pending > 0 ? <span className="text-amber-600 font-semibold">{t.pending}</span> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title={`Founding Members · ${foundingMembers.length} of 5`}>
        {foundingMembers.length === 0 ? (
          <p className="text-sm text-gray-400">No founding members onboarded yet.</p>
        ) : (
          <div className="space-y-2 text-sm">
            {foundingMembers.map((t, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
                <div>
                  <div className="font-semibold text-navy">{t.name}</div>
                  {t.loc && t.loc !== '—' && <div className="text-[11px] text-gray-500">{t.loc}</div>}
                </div>
                <Pill tone="gold">Founding Member</Pill>
              </div>
            ))}
          </div>
        )}
        <Link to="/onboarding" className="mt-3 inline-block text-xs font-semibold text-navy hover:text-gold">+ Onboard a founding member →</Link>
      </Card>

      {showAdd && <AddClientModal onClose={() => setShowAdd(false)} onDone={load} />}
    </div>
  )
}

function AddClientModal({ onClose, onDone }) {
  const [f, setF] = useState({ property_name: '', owner_name: '', owner_email: '', plan_tier: 'professional', city: '', state: '' })
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [err, setErr] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const cls = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'

  const submit = async () => {
    setBusy(true); setErr(null)
    try { const r = await adminProvisionTenant(f); setResult(r); onDone() }
    catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="font-bold text-navy text-lg mb-3">Add New Client</div>
        {result ? (
          <div className="space-y-3">
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-800">
              ✓ Account created{result.welcome_email_sent ? ' · welcome email sent' : ' · email skipped (no SendGrid key)'}.
            </div>
            <div className="rounded-lg border border-gold/40 bg-gold/5 p-3 text-sm font-mono">
              <div><span className="text-gray-500">Email:</span> {f.owner_email}</div>
              <div><span className="text-gray-500">Temp password:</span> <strong>{result.temp_password}</strong></div>
              {result.tenant_id && <div><span className="text-gray-500">Tenant:</span> {result.tenant_id}</div>}
            </div>
            <button onClick={onClose} className="w-full bg-navy text-white font-semibold py-2 rounded-lg">Done</button>
          </div>
        ) : (
          <div className="space-y-3">
            <Field l="Property name"><input className={cls} value={f.property_name} onChange={set('property_name')} /></Field>
            <Field l="Owner name"><input className={cls} value={f.owner_name} onChange={set('owner_name')} /></Field>
            <Field l="Owner email"><input type="email" className={cls} value={f.owner_email} onChange={set('owner_email')} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field l="City"><input className={cls} value={f.city} onChange={set('city')} /></Field>
              <Field l="State"><input className={cls} value={f.state} onChange={set('state')} /></Field>
            </div>
            <Field l="Plan tier">
              <select className={cls} value={f.plan_tier} onChange={set('plan_tier')}>
                {['starter', 'professional', 'enterprise', 'premium', 'founding_member'].map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            {err && <div className="text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded p-2">{err}</div>}
            <div className="flex gap-2">
              <button onClick={onClose} className="flex-1 border border-gray-300 text-gray-600 py-2 rounded-lg text-sm font-semibold">Cancel</button>
              <button onClick={submit} disabled={busy || !f.owner_email} className="flex-1 bg-gold text-navy py-2 rounded-lg text-sm font-bold disabled:opacity-50">{busy ? 'Creating…' : 'Create + send welcome'}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

const Field = ({ l, children }) => (
  <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">{l}</div>{children}</label>
)

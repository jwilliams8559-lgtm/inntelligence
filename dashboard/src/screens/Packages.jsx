import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import { getPackages, togglePackage } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, Segmented, LastUpdated, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function Packages() {
  const { lastUpdated } = usePrices()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  // In the /demo, open on the Available tab so prospects see the full catalog of
  // 25+ pre-built packages (abundance) rather than just the active set. Evaluated
  // per-render (not at module load) so it sees the demo flag set by startDemo().
  const [tab, setTab] = useState(() => {
    try { return sessionStorage.getItem('inn_demo') === '1' ? 'available' : 'active' } catch { return 'active' }
  })
  const [busyId, setBusyId] = useState(null)

  const load = () => getPackages().then(setData).catch((e) => setErr(e.message))
  useEffect(() => { load() }, [])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading packages…" />

  const { active, available } = data
  const activeRev = active.filter((p) => !p.is_discount).reduce((s, p) => s + p.monthly_revenue, 0)
  const list = tab === 'active' ? active : available

  const onToggle = async (id) => {
    setBusyId(id)
    try { await togglePackage(id); await load() }
    catch (e) { setErr(e.message) }
    finally { setBusyId(null) }
  }

  const chart = active.filter((p) => !p.is_discount)
    .sort((a, b) => b.monthly_revenue - a.monthly_revenue).slice(0, 8)
    .map((p) => ({ name: p.name.length > 14 ? p.name.slice(0, 13) + '…' : p.name, rev: p.monthly_revenue }))

  return (
    <div>
      <ScreenHeader
        title="Packages & Enhancements"
        subtitle="AI-priced add-ons · activate industry packages to grow ancillary revenue"
        right={<LastUpdated at={lastUpdated} />}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Active Monthly Revenue" value={usd(activeRev)} sub={`${active.length} active packages`} accent />
        <StatCard label="Active Packages" value={active.length} sub="live now" />
        <StatCard label="Available to Activate" value={available.length} sub="industry catalog" />
        <StatCard label="Catalog Size" value={active.length + available.length} sub="total packages" />
      </div>

      {chart.length > 0 && (
        <Card title="Estimated Monthly Revenue — Active Packages" className="mb-6">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chart} margin={{ top: 6, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="#94a3b8" interval={0} angle={-15} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v) => [usd(v), 'Est. monthly']} />
              <Bar dataKey="rev" fill="#c9a84c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="mb-4">
        <Segmented
          options={[{ value: 'active', label: `Active Packages (${active.length})` }, { value: 'available', label: `Available Packages (${available.length})` }]}
          value={tab} onChange={setTab} size="md"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {list.map((p) => (
          <div key={p.id} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md transition-shadow flex flex-col">
            <div className="flex items-start justify-between">
              <div className="text-2xl">{p.emoji}</div>
              {p.is_discount
                ? <Pill tone="navy">Discount offer</Pill>
                : <Pill tone="gold">+{usd(p.premium)}</Pill>}
            </div>
            <div className="font-semibold text-navy mt-2">{p.name}</div>
            <div className="text-[11px] text-gray-500 leading-snug flex-1">{p.description}</div>

            {tab === 'available' && (
              <div className="flex items-center gap-3 mt-3 text-[11px]">
                <span className="text-gray-500">{p.pct_inns}% of inns offer</span>
                <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-gold" style={{ width: `${p.pct_inns}%` }} />
                </div>
              </div>
            )}

            <div className="flex items-baseline justify-between mt-3">
              <span className="text-xs text-emerald-700 font-semibold">
                {tab === 'active' ? `${usd(p.monthly_revenue)}/mo` : `${usd(p.monthly_revenue_potential)}/mo potential`}
              </span>
              <span className="text-[10px] text-gray-400">{tab === 'active' ? `${Math.round(p.take_rate * 100)}% take` : '@ 20% take'}</span>
            </div>

            <button
              onClick={() => onToggle(p.id)}
              disabled={busyId === p.id}
              className={`mt-3 w-full py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 ${
                tab === 'active'
                  ? 'border border-rose-200 text-rose-600 hover:bg-rose-50'
                  : 'bg-navy text-white hover:bg-navy-light'
              }`}
            >
              {busyId === p.id ? '…' : tab === 'active' ? 'Deactivate' : '+ Activate'}
            </button>
          </div>
        ))}
        {list.length === 0 && <p className="text-sm text-gray-400">No packages in this tab.</p>}
      </div>
    </div>
  )
}

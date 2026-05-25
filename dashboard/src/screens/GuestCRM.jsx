import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import {
  getGuests, getGuestProfile, getCrmMeta, getCrmAnalytics, sendCampaign,
} from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, Segmented, ExportButton, LastUpdated, exportToCsv, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const SLICE = ['#0a2342', '#c9a84c', '#1a3a5c', '#e8d5a3', '#8a6d1f', '#c7d2dd']
const STATUS_TONE = { VIP: 'gold', Regular: 'navy', New: 'emerald', Lapsed: 'rose' }
const TABS = [{ value: 'list', label: 'Guest List' }, { value: 'campaigns', label: 'Campaigns' }, { value: 'analytics', label: 'Analytics' }]
const fmt = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

export default function GuestCRM() {
  const { lastUpdated } = usePrices()
  const [tab, setTab] = useState('list')
  const [guests, setGuests] = useState(null)
  const [meta, setMeta] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [err, setErr] = useState(null)
  const [selId, setSelId] = useState(null)

  useEffect(() => {
    getGuests().then((d) => setGuests(d.guests)).catch((e) => setErr(e.message))
    getCrmMeta().then(setMeta).catch((e) => setErr(e.message))
    getCrmAnalytics().then(setAnalytics).catch((e) => setErr(e.message))
  }, [])

  if (err) return <ErrorBanner message={err} />
  if (!guests || !meta || !analytics) return <LoadingSpinner label="Loading guest CRM…" />

  const vip = guests.filter((g) => g.status === 'VIP').length
  const lapsed = guests.filter((g) => g.status === 'Lapsed').length
  const totalSpend = guests.reduce((s, g) => s + g.lifetime_spend, 0)

  return (
    <div>
      <ScreenHeader
        title="Guest CRM"
        subtitle="Guest intelligence, segmentation, and campaigns for The Bay Street Inn"
        right={<LastUpdated at={lastUpdated} />}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Total Guests" value={guests.length} sub="in database" accent />
        <StatCard label="VIP Guests" value={vip} sub="top-tier" />
        <StatCard label="Lapsed (6+ mo)" value={lapsed} sub="win-back targets" />
        <StatCard label="Lifetime Value" value={usd(totalSpend)} sub="all guests" />
      </div>

      <div className="mb-4"><Segmented options={TABS} value={tab} onChange={setTab} size="md" /></div>

      {tab === 'list' && <GuestList guests={guests} onSelect={setSelId} />}
      {tab === 'campaigns' && <Campaigns meta={meta} />}
      {tab === 'analytics' && <Analytics a={analytics} />}

      {selId && <ProfileDrawer id={selId} onClose={() => setSelId(null)} />}
    </div>
  )
}

function GuestList({ guests, onSelect }) {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('all')
  const filtered = guests.filter((g) =>
    (status === 'all' || g.status === status) &&
    (q === '' || g.name.toLowerCase().includes(q.toLowerCase()) || g.city.toLowerCase().includes(q.toLowerCase()))
  )
  const onExport = () => exportToCsv('guests', filtered, [
    { key: 'name', label: 'Name' }, { key: 'last_stay', label: 'Last Stay' },
    { key: 'num_stays', label: '# Stays' }, { key: 'lifetime_spend', label: 'Lifetime Spend' },
    { key: 'city', label: 'City' }, { key: 'state', label: 'State' },
    { key: 'distance_miles', label: 'Distance (mi)' }, { key: 'favorite_room', label: 'Favorite Room' },
    { key: 'status', label: 'Status' },
  ])
  return (
    <Card title={`${filtered.length} Guests`} right={<ExportButton onClick={onExport} />}>
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <input
          value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or city…"
          className="flex-1 min-w-48 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-gold"
        />
        <Segmented options={['all', 'VIP', 'Regular', 'New', 'Lapsed'].map((s) => ({ value: s, label: s }))} value={status} onChange={setStatus} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
            <tr>
              <th className="text-left py-2">Name</th>
              <th className="text-left">Last Stay</th>
              <th className="text-right"># Stays</th>
              <th className="text-right">Lifetime</th>
              <th className="text-left pl-3">Home</th>
              <th className="text-right">Distance</th>
              <th className="text-left pl-3">Favorite</th>
              <th className="text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((g) => (
              <tr key={g.id} onClick={() => onSelect(g.id)} className="border-t border-gray-100 hover:bg-gold/5 cursor-pointer">
                <td className="py-2 font-medium text-navy">{g.name}</td>
                <td className="text-gray-600">{fmt(g.last_stay)}</td>
                <td className="text-right text-gray-600">{g.num_stays}</td>
                <td className="text-right font-semibold text-navy">{usd(g.lifetime_spend)}</td>
                <td className="pl-3 text-gray-600">{g.city}, {g.state}</td>
                <td className="text-right text-gray-500">{g.distance_miles} mi</td>
                <td className="pl-3 text-gray-600">{g.favorite_room}</td>
                <td className="text-center"><Pill tone={STATUS_TONE[g.status] || 'gray'}>{g.status}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function ProfileDrawer({ id, onClose }) {
  const [g, setG] = useState(null)
  const [err, setErr] = useState(null)
  const [notes, setNotes] = useState('')
  const [sent, setSent] = useState(false)
  useEffect(() => { getGuestProfile(id).then(setG).catch((e) => setErr(e.message)) }, [id])

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-full max-w-lg bg-white h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {err && <div className="p-5"><ErrorBanner message={err} /></div>}
        {!g && !err && <div className="p-5"><LoadingSpinner label="Loading profile…" /></div>}
        {g && (
          <>
            <div className="bg-navy text-white px-5 py-4 flex items-start justify-between sticky top-0 z-10">
              <div>
                <div className="font-bold text-lg">{g.name}</div>
                <div className="text-gold-light text-sm">{g.city}, {g.state} · {g.distance_miles} mi away</div>
              </div>
              <button onClick={onClose} className="text-white/70 hover:text-white text-xl leading-none">✕</button>
            </div>
            <div className="p-5 space-y-5">
              <div className="flex items-center gap-2 flex-wrap">
                <Pill tone={STATUS_TONE[g.status] || 'gray'}>{g.status}</Pill>
                <Pill tone="gray">{g.num_stays} stays</Pill>
                <Pill tone="gray">Prefers {g.favorite_room}</Pill>
              </div>

              <div className="grid grid-cols-3 gap-3 text-center">
                <Mini label="Lifetime" value={usd(g.lifetime_spend)} />
                <Mini label="Avg / Stay" value={usd(g.avg_spend)} />
                <Mini label="Last Stay" value={`${g.days_since_stay}d ago`} />
              </div>

              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Contact</div>
                <div className="text-sm text-gray-700">{g.email}</div>
                <div className="text-sm text-gray-700">{g.phone}</div>
              </div>

              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Preferences & Reasons</div>
                <div className="flex flex-wrap gap-1">
                  {g.preferences.map((p, i) => <Pill key={i} tone="gold">{p}</Pill>)}
                  <Pill tone="navy">{g.primary_reason}</Pill>
                </div>
              </div>

              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-2">Stay History</div>
                <div className="space-y-1">
                  {g.stays.map((s, i) => (
                    <div key={i} className="flex justify-between text-sm border-b border-gray-100 py-1.5">
                      <div><span className="text-navy font-medium">{fmt(s.date)}</span><span className="text-gray-400"> · {s.room} · {s.nights}n · {s.reason}</span></div>
                      <span className="font-semibold text-navy">{usd(s.total)}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-1">Staff Notes</div>
                <textarea
                  value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                  placeholder="Add a note…"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                />
              </div>

              <button
                onClick={() => setSent(true)}
                className="w-full bg-gold text-navy font-semibold py-2.5 rounded-lg hover:bg-gold-light transition-colors"
              >
                {sent ? '✓ Email queued' : `✉ Send email to ${g.first}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Campaigns({ meta }) {
  const [seg, setSeg] = useState(meta.segments[0]?.id || '')
  const [tpl, setTpl] = useState(meta.templates[0]?.id || '')
  const [name, setName] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const segObj = meta.segments.find((s) => s.id === seg)
  const tplObj = meta.templates.find((t) => t.id === tpl)

  const onSend = async () => {
    setBusy(true)
    try { setResult(await sendCampaign({ name: name || 'New Campaign', segment: seg, template: tpl })) }
    finally { setBusy(false) }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="Create Campaign">
        <label className="block text-xs font-semibold text-gray-500 mb-1">Campaign name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. June Win-back"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-gold" />

        <label className="block text-xs font-semibold text-gray-500 mb-1">Guest segment</label>
        <select value={seg} onChange={(e) => setSeg(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3">
          {meta.segments.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.count})</option>)}
        </select>

        <label className="block text-xs font-semibold text-gray-500 mb-1">Email template</label>
        <select value={tpl} onChange={(e) => setTpl(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3">
          {meta.templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>

        <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 mb-3">
          <div className="text-[11px] uppercase tracking-wide text-gray-400 font-semibold">Preview</div>
          <div className="font-semibold text-navy text-sm mt-1">{tplObj?.subject}</div>
          <div className="text-[12px] text-gray-600">{tplObj?.preview}</div>
          <div className="text-[11px] text-gold-dark mt-2">→ {segObj?.count} recipients</div>
        </div>

        <button onClick={onSend} disabled={busy} className="w-full bg-navy text-white font-semibold py-2.5 rounded-lg hover:bg-navy-light transition-colors disabled:opacity-50">
          {busy ? 'Sending…' : 'Send Campaign'}
        </button>
        {result && (
          <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm text-emerald-800">
            ✓ "{result.campaign.name}" queued to {result.campaign.recipients} {result.campaign.segment} guests.
          </div>
        )}
      </Card>

      <Card title="Campaign History">
        <div className="space-y-2">
          {meta.campaign_history.map((c) => (
            <div key={c.id} className="rounded-lg border border-gray-200 p-3">
              <div className="flex items-center justify-between">
                <div className="font-semibold text-navy text-sm">{c.name}</div>
                <span className="text-[11px] text-gray-400">{fmt(c.sent_date)}</span>
              </div>
              <div className="text-[11px] text-gray-500">{c.segment} · {c.template}</div>
              <div className="flex gap-4 mt-2 text-xs">
                <span className="text-gray-600">{c.recipients} sent</span>
                <span className="text-navy font-semibold">{c.open_rate}% open</span>
                <span className="text-emerald-700 font-semibold">{c.bookings} bookings</span>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold mb-2">Segments</div>
          <div className="grid grid-cols-2 gap-2">
            {meta.segments.map((s) => (
              <div key={s.id} className="flex justify-between rounded-lg bg-gray-50 px-3 py-2 text-sm">
                <span className="text-gray-600">{s.name}</span>
                <span className="font-bold text-navy">{s.count}</span>
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  )
}

function Analytics({ a }) {
  const pie = a.sources.map((s) => ({ name: s.source, value: s.guests, revenue: s.revenue }))
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card title="Booking Sources">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={pie} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={(e) => e.name}>
              {pie.map((_, i) => <Cell key={i} fill={SLICE[i % SLICE.length]} />)}
            </Pie>
            <Tooltip formatter={(v, n, p) => [`${v} guests · ${usd(p.payload.revenue)}`, n]} />
          </PieChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Where Guests Come From">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={a.geography} layout="vertical" margin={{ top: 4, right: 16, left: 30, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
            <XAxis type="number" tick={{ fontSize: 10 }} stroke="#94a3b8" />
            <YAxis type="category" dataKey="location" tick={{ fontSize: 9 }} stroke="#94a3b8" width={90} />
            <Tooltip formatter={(v) => [`${v} guests`, 'Guests']} />
            <Bar dataKey="count" fill="#c9a84c" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card title="Avg Lead Time by Guest Type">
        <div className="space-y-2">
          {a.lead_times.map((l) => (
            <div key={l.status} className="flex items-center gap-3">
              <div className="w-20 text-xs text-gray-500">{l.status}</div>
              <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
                <div className="h-full bg-navy" style={{ width: `${Math.min(100, l.avg_lead_days / 75 * 100)}%` }} />
              </div>
              <div className="w-14 text-right text-xs font-semibold text-navy">{l.avg_lead_days}d</div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-sm text-gray-600">Overall cancellation rate: <span className="font-bold text-navy">{a.cancellation_rate_pct}%</span></div>
      </Card>

      <Card title="Price Sensitivity by Segment">
        <div className="space-y-2">
          {a.price_sensitivity.map((p) => {
            const tone = p.sensitivity === 'Low' ? 'emerald' : p.sensitivity === 'Medium' ? 'gold' : 'rose'
            return (
              <div key={p.segment} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3">
                <div className="w-20 font-semibold text-navy text-sm">{p.segment}</div>
                <Pill tone={tone}>{p.sensitivity}</Pill>
                <div className="text-[11px] text-gray-500 flex-1">{p.note}</div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}

const Mini = ({ label, value }) => (
  <div className="rounded-lg bg-gray-50 py-2">
    <div className="text-sm font-bold text-navy">{value}</div>
    <div className="text-[10px] text-gray-400">{label}</div>
  </div>
)

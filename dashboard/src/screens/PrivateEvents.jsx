import { useState, useEffect, Fragment } from 'react'
import { usePrices } from '../context/PriceContext'
import { getPrivateEvents, getRates, getEventsDetail } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill, Segmented, LastUpdated, usd } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const TABS = [
  { value: 'calculator', label: 'Inquiry Calculator' },
  { value: 'packages', label: 'Pricing Packages' },
  { value: 'inquiries', label: 'Active Inquiries' },
  { value: 'impact', label: 'Revenue Impact' },
]
const STATUS_TONE = { Confirmed: 'emerald', Negotiating: 'amber', Quoted: 'gold', New: 'navy' }
const fmtDate = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

export default function PrivateEvents() {
  const { lastUpdated } = usePrices()
  const [tab, setTab] = useState('calculator')
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => { getPrivateEvents().then(setData).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading private events…" />

  return (
    <div>
      <ScreenHeader
        title="Private Events"
        subtitle={`${data.property_name} · weddings, corporate retreats & buyouts`}
        right={<LastUpdated at={lastUpdated} />}
      />
      <div className="mb-5"><Segmented options={TABS} value={tab} onChange={setTab} size="md" /></div>

      {tab === 'calculator' && <Calculator />}
      {tab === 'packages' && <Packages />}
      {tab === 'inquiries' && <Inquiries seed={data.inquiries} />}
      {tab === 'impact' && <Impact data={data} />}
    </div>
  )
}

// ── TAB 1: Inquiry Calculator ────────────────────────────────────────────────
function Calculator() {
  const [form, setForm] = useState({
    type: 'Wedding', date: '2026-10-11', guests: 30, rooms: 19, nights: 2,
    fnb: true, ceremony: true, openBar: false,
  })
  const [events, setEvents] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  useEffect(() => { getEventsDetail(180).then((d) => setEvents(d.events || [])).catch(() => {}) }, [])

  const spaceFee = (g) => (g < 20 ? 500 : g <= 40 ? 1000 : 2000)

  const calculate = async () => {
    setBusy(true); setErr(null)
    try {
      const rates = await getRates(form.date)
      const avgRate = rates.length ? Math.round(rates.reduce((s, r) => s + r.rate, 0) / rates.length) : 0
      const roomBlock = form.rooms * form.nights * avgRate
      const space = form.ceremony ? spaceFee(form.guests) : 0
      const fnb = form.fnb ? form.guests * 125 : 0
      const bar = form.openBar ? form.guests * 45 : 0
      const setup = 800
      const subtotal = roomBlock + space + fnb + bar + setup
      const exclusivity = form.rooms === 19 ? Math.round(subtotal * 0.20) : 0
      const total = subtotal + exclusivity
      const individual = form.rooms * form.nights * avgRate
      const premium = total - individual
      const premiumPct = individual ? Math.round((premium / individual) * 100) : 0

      // Conflict: does the date fall inside an event window?
      const dsel = new Date(form.date + 'T12:00:00')
      const conflict = events.find((e) => {
        const start = new Date(e.first_date + 'T12:00:00')
        const end = new Date(start); end.setDate(end.getDate() + Math.max(1, e.impacted_days || 2))
        return dsel >= start && dsel <= end
      })
      let conflictInfo = null
      if (conflict) {
        const fullHouseEventRevenue = 19 * form.nights * avgRate
        const rec = total >= fullHouseEventRevenue * 1.2 ? 'ACCEPT'
          : total >= fullHouseEventRevenue * 0.9 ? 'NEGOTIATE' : 'DECLINE'
        conflictInfo = { event: conflict.event, fullHouseEventRevenue, rec }
      }

      setResult({
        avgRate, roomBlock, space, fnb, bar, setup, exclusivity, total,
        individual, premium, premiumPct, conflictInfo,
      })
    } catch (e) { setErr(e.message) }
    finally { setBusy(false) }
  }

  const compTone = !result ? 'gray'
    : result.total < result.individual ? 'rose'
      : result.premiumPct < 20 ? 'amber' : 'emerald'

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Card title="Event Inquiry">
        <div className="space-y-4">
          <Field label="Event Type">
            <select value={form.type} onChange={(e) => set('type', e.target.value)} className={INPUT}>
              {['Wedding', 'Corporate Retreat', 'Executive Meeting', 'Anniversary Buyout', 'Birthday Celebration', 'Rehearsal Dinner', 'Other'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Event Date">
              <input type="date" value={form.date} onChange={(e) => set('date', e.target.value)} className={INPUT} />
            </Field>
            <Field label="Guest Count">
              <input type="number" min="1" value={form.guests} onChange={(e) => set('guests', Number(e.target.value))} className={INPUT} />
            </Field>
          </div>
          <Field label={`Rooms Needed: ${form.rooms}${form.rooms === 19 ? ' (full buyout)' : ''}`}>
            <input type="range" min="1" max="19" value={form.rooms} onChange={(e) => set('rooms', Number(e.target.value))} className="w-full accent-gold" />
          </Field>
          <Field label="Number of Nights">
            <div className="flex gap-2">
              {[1, 2, 3].map((n) => (
                <button key={n} onClick={() => set('nights', n)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-semibold border ${form.nights === n ? 'bg-navy text-white border-navy' : 'border-gray-300 text-gray-600'}`}>{n}</button>
              ))}
            </div>
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Toggle label="F&B" on={form.fnb} onChange={(v) => set('fnb', v)} />
            <Toggle label="Ceremony Space" on={form.ceremony} onChange={(v) => set('ceremony', v)} />
            <Toggle label="Open Bar" on={form.openBar} onChange={(v) => set('openBar', v)} />
          </div>
          <button onClick={calculate} disabled={busy}
            className="w-full bg-gold text-navy font-bold py-2.5 rounded-lg hover:bg-gold-light transition-colors disabled:opacity-50">
            {busy ? 'Calculating…' : 'Calculate Package Value'}
          </button>
          {err && <ErrorBanner message={err} />}
        </div>
      </Card>

      <div className="space-y-4">
        {!result ? (
          <Card title="Revenue Breakdown"><p className="text-sm text-gray-400">Enter inquiry details and calculate to see the full package value.</p></Card>
        ) : (
          <>
            <Card title="Revenue Breakdown">
              <Line label={`Room block (${form.rooms} × ${form.nights}n × ${usd(result.avgRate)})`} value={result.roomBlock} />
              {result.space > 0 && <Line label="Ceremony / event space fee" value={result.space} />}
              {result.fnb > 0 && <Line label={`F&B minimum (${form.guests} × $125)`} value={result.fnb} />}
              {result.bar > 0 && <Line label={`Open bar premium (${form.guests} × $45)`} value={result.bar} />}
              <Line label="Setup & coordination" value={result.setup} />
              {result.exclusivity > 0 && <Line label="Exclusivity premium (20%, full buyout)" value={result.exclusivity} />}
              <div className="flex justify-between items-center mt-3 pt-3 border-t border-gray-200">
                <span className="text-sm font-semibold text-navy">TOTAL PACKAGE VALUE</span>
                <span className="text-3xl font-extrabold text-gold">{usd(result.total)}</span>
              </div>
            </Card>

            <Card title="vs Selling Rooms Individually">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs text-gray-500">Individual booking revenue</div>
                  <div className="text-xl font-bold text-navy">{usd(result.individual)}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500">Private event premium</div>
                  <div className={`text-xl font-extrabold ${compTone === 'rose' ? 'text-rose-600' : compTone === 'amber' ? 'text-amber-600' : 'text-emerald-600'}`}>
                    +{usd(result.premium)} <span className="text-sm">(+{result.premiumPct}%)</span>
                  </div>
                </div>
              </div>
              <div className="mt-2"><Pill tone={compTone}>
                {compTone === 'emerald' ? 'Strong premium — pursue the event'
                  : compTone === 'amber' ? 'Within 20% of individual — negotiate carefully'
                    : 'Below individual — reconsider'}
              </Pill></div>
            </Card>

            {result.conflictInfo && (
              <div className="rounded-xl border border-amber-300 bg-amber-50 p-4">
                <div className="font-bold text-amber-800">⚠️ REVENUE CONFLICT: {result.conflictInfo.event} weekend</div>
                <div className="text-sm text-gray-700 mt-1">
                  Individual booking revenue at event pricing (full house): <span className="font-bold">{usd(result.conflictInfo.fullHouseEventRevenue)}</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-sm text-gray-600">Recommendation:</span>
                  <Pill tone={result.conflictInfo.rec === 'ACCEPT' ? 'emerald' : result.conflictInfo.rec === 'NEGOTIATE' ? 'amber' : 'rose'}>
                    {result.conflictInfo.rec}
                  </Pill>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

const INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'
const Field = ({ label, children }) => (
  <div><label className="block text-xs font-semibold text-gray-500 mb-1">{label}</label>{children}</div>
)
const Toggle = ({ label, on, onChange }) => (
  <button onClick={() => onChange(!on)}
    className={`w-full rounded-lg border px-2 py-2 text-xs font-semibold transition-colors ${on ? 'bg-navy text-white border-navy' : 'bg-white text-gray-500 border-gray-300'}`}>
    {label}: {on ? 'Yes' : 'No'}
  </button>
)
const Line = ({ label, value }) => (
  <div className="flex justify-between text-sm py-1 border-b border-gray-100"><span className="text-gray-600">{label}</span><span className="text-navy font-medium">{usd(value)}</span></div>
)

// ── TAB 2: Pricing Packages ──────────────────────────────────────────────────
export const WEDDING_PACKAGES = [
  { name: 'Intimate Elopement', tier: 'Wedding', guests: 'Up to 10 guests · 1 night min', price: '$2,500 – $4,500',
    inclusions: ['Ceremony space', 'Bridal suite upgrade', 'Champagne toast', 'Breakfast for two', 'Late checkout'],
    addons: 'Add-ons: photographer referral, flowers, custom cake' },
  { name: 'Garden Ceremony', tier: 'Wedding', guests: 'Up to 30 guests · 2 night min · 10+ rooms', price: '$12,000 – $18,000',
    inclusions: ['Outdoor ceremony space', 'Rehearsal dinner at The Parlor', 'Wedding night suite', 'Breakfast for all guests'] },
  { name: 'Classic Wedding', tier: 'Wedding', guests: 'Up to 50 guests · 2 night min · full buyout', price: '$18,000 – $28,000',
    inclusions: ['Everything in Garden Ceremony', 'Full Parlor reception', 'Rooftop cocktail hour', 'Dedicated event coordinator'] },
  { name: 'Grand Celebration', tier: 'Wedding', guests: 'Up to 75 guests · 3 night min · full buyout', price: '$28,000 – $45,000',
    inclusions: ['Everything in Classic', 'Welcome dinner (night 1)', 'Farewell brunch', 'Suite upgrades for wedding party'] },
]
const CORPORATE_PACKAGES = [
  { name: 'Executive Half Day', tier: 'Corporate', guests: 'No rooms', price: '$800 – $1,500',
    inclusions: ['Meeting space', 'AV', 'Coffee service', 'Working lunch'] },
  { name: 'Full Day Corporate Retreat', tier: 'Corporate', guests: 'No rooms', price: '$1,500 – $2,500',
    inclusions: ['Meeting space all day', 'AV', 'Three meals', 'Afternoon team activity'] },
  { name: 'Overnight Executive Retreat', tier: 'Corporate', guests: 'Up to 12 rooms', price: '$3,500 – $8,000',
    inclusions: ['Rooms for up to 12', 'Meeting space', 'All meals', 'Dinner at The Parlor', 'Rooftop reception'] },
  { name: 'Executive Property Buyout', tier: 'Corporate', guests: 'Full 19-room buyout · 2 nights', price: '$15,000 – $25,000',
    inclusions: ['Full property buyout', 'All meals', 'Dedicated staff', 'Complete privacy'] },
]

function PackageCard({ p }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden flex flex-col">
      <div className="bg-navy text-white px-5 py-4">
        <div className="flex items-center justify-between">
          <div className="font-bold text-lg">{p.name}</div>
          <Pill tone={p.tier === 'Wedding' ? 'gold' : 'navy'}>{p.tier}</Pill>
        </div>
        <div className="text-gold-light text-xs mt-0.5">{p.guests}</div>
      </div>
      <div className="p-5 flex-1 flex flex-col">
        <ul className="space-y-1 text-sm text-gray-700 flex-1">
          {p.inclusions.map((i) => <li key={i} className="flex gap-2"><span className="text-gold">✓</span>{i}</li>)}
        </ul>
        {p.addons && <div className="text-[11px] text-gray-400 mt-2 italic">{p.addons}</div>}
        <div className="text-2xl font-extrabold text-gold mt-3">{p.price}</div>
        <div className="text-[11px] text-gray-500 mt-2 border-t border-gray-100 pt-2 space-y-0.5">
          <div><span className="font-semibold">Deposit:</span> 25% to hold · 50% at 90 days · 25% at 30 days</div>
          <div><span className="font-semibold">Cancellation:</span> 90+ days full refund · 60–89 days 50% · under 60 none</div>
        </div>
        <button className="mt-3 w-full bg-gold text-navy font-semibold py-2 rounded-lg hover:bg-gold-light transition-colors">Request This Package</button>
      </div>
    </div>
  )
}

function Packages() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-bold text-navy uppercase tracking-wide mb-3">Wedding Packages</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {WEDDING_PACKAGES.map((p) => <PackageCard key={p.name} p={p} />)}
        </div>
      </div>
      <div>
        <h3 className="text-sm font-bold text-navy uppercase tracking-wide mb-3">Corporate Packages</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          {CORPORATE_PACKAGES.map((p) => <PackageCard key={p.name} p={p} />)}
        </div>
      </div>
    </div>
  )
}

// ── TAB 3: Active Inquiries ──────────────────────────────────────────────────
const STATUSES = ['New', 'Quoted', 'Negotiating', 'Confirmed', 'Declined']

function Inquiries({ seed }) {
  const [rows, setRows] = useState(seed)
  const [openId, setOpenId] = useState(null)
  const [showModal, setShowModal] = useState(false)

  const updateStatus = (id, status) => setRows((rs) => rs.map((r) => r.id === id ? { ...r, status } : r))
  const updateNotes = (id, notes) => setRows((rs) => rs.map((r) => r.id === id ? { ...r, notes } : r))
  const addInquiry = (inq) => { setRows((rs) => [{ ...inq, id: `pe${Date.now()}` }, ...rs]); setShowModal(false) }

  return (
    <Card title={`${rows.length} Active Inquiries`} right={
      <button onClick={() => setShowModal(true)} className="text-xs font-semibold bg-navy text-white px-3 py-1.5 rounded-lg hover:bg-navy-light">+ Add New Inquiry</button>
    }>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
            <tr>
              <th className="text-left py-2">Event</th><th className="text-left">Type</th><th className="text-left">Date</th>
              <th className="text-right">Guests</th><th className="text-center">Status</th><th className="text-right">Quoted</th><th className="text-right">Days Out</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Fragment key={r.id}>
                <tr onClick={() => setOpenId(openId === r.id ? null : r.id)} className="border-t border-gray-100 hover:bg-gold/5 cursor-pointer">
                  <td className="py-2 font-medium text-navy">{r.name}{r.conflict && <span className="ml-1 text-amber-500" title={`Conflict: ${r.conflict}`}>⚠️</span>}</td>
                  <td className="text-gray-600">{r.type}</td>
                  <td className="text-gray-600">{fmtDate(r.date)}</td>
                  <td className="text-right text-gray-600">{r.guests}</td>
                  <td className="text-center"><Pill tone={STATUS_TONE[r.status] || 'gray'}>{r.status}</Pill></td>
                  <td className="text-right font-semibold text-navy">{r.quoted_value ? usd(r.quoted_value) : '—'}</td>
                  <td className="text-right text-gray-500">{r.days_out}d</td>
                </tr>
                {openId === r.id && (
                  <tr className="bg-gray-50">
                    <td colSpan={7} className="p-4">
                      {r.conflict && (
                        <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
                          ⚠️ This date falls during <span className="font-semibold">{r.conflict}</span> — individual bookings may exceed buyout value.
                        </div>
                      )}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[11px] font-semibold text-gray-500 mb-1">Notes</label>
                          <textarea value={r.notes} onChange={(e) => updateNotes(r.id, e.target.value)} rows={3} className={INPUT} />
                        </div>
                        <div>
                          <label className="block text-[11px] font-semibold text-gray-500 mb-1">Update Status</label>
                          <select value={r.status} onChange={(e) => updateStatus(r.id, e.target.value)} className={INPUT}>
                            {STATUSES.map((s) => <option key={s}>{s}</option>)}
                          </select>
                          <div className="text-[11px] text-gray-500 mt-3">
                            {r.guests} guests · {fmtDate(r.date)} · {r.days_out} days out · {r.quoted_value ? `quoted ${usd(r.quoted_value)}` : 'not yet quoted'}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {showModal && <NewInquiryModal onClose={() => setShowModal(false)} onAdd={addInquiry} />}
    </Card>
  )
}

function NewInquiryModal({ onClose, onAdd }) {
  const [f, setF] = useState({ name: '', type: 'Wedding', date: '', guests: 20, status: 'New', quoted_value: null, days_out: 0, conflict: null, notes: '' })
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }))
  const submit = () => {
    const days = f.date ? Math.max(0, Math.round((new Date(f.date) - new Date()) / 86400000)) : 0
    onAdd({ ...f, days_out: days, guests: Number(f.guests) })
  }
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl p-5" onClick={(e) => e.stopPropagation()}>
        <div className="font-bold text-navy text-lg mb-3">New Inquiry</div>
        <div className="space-y-3">
          <Field label="Event / Client Name"><input value={f.name} onChange={(e) => set('name', e.target.value)} className={INPUT} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type">
              <select value={f.type} onChange={(e) => set('type', e.target.value)} className={INPUT}>
                {['Wedding', 'Corporate Retreat', 'Executive Meeting', 'Anniversary Buyout', 'Birthday Celebration', 'Rehearsal Dinner', 'Other'].map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Date"><input type="date" value={f.date} onChange={(e) => set('date', e.target.value)} className={INPUT} /></Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Guests"><input type="number" value={f.guests} onChange={(e) => set('guests', e.target.value)} className={INPUT} /></Field>
            <Field label="Status">
              <select value={f.status} onChange={(e) => set('status', e.target.value)} className={INPUT}>
                {STATUSES.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 border border-gray-300 text-gray-600 py-2 rounded-lg text-sm font-semibold">Cancel</button>
          <button onClick={submit} disabled={!f.name} className="flex-1 bg-gold text-navy py-2 rounded-lg text-sm font-bold disabled:opacity-50">Add Inquiry</button>
        </div>
      </div>
    </div>
  )
}

// ── TAB 4: Revenue Impact ────────────────────────────────────────────────────
function Impact({ data }) {
  const m = data.metrics
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard label="This Year Revenue" value={usd(m.this_year_revenue)} sub={`vs ${usd(m.last_year_revenue)} last year`} accent />
        <StatCard label="YoY Growth" value={`+${m.yoy_growth_pct}%`} sub="private events" />
        <StatCard label="Avg Package Value" value={usd(m.avg_package_value)} sub="per event" />
        <StatCard label="Conversion Rate" value={`${m.conversion_rate_pct}%`} sub="inquiry → booking" />
        <StatCard label="Avg Lead Time" value={`${m.avg_lead_time_days}d`} sub="inquiry to event" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="Best Event Types">
          <div className="space-y-3">
            {data.event_type_breakdown.map((e) => (
              <div key={e.type} className="flex items-center gap-3 text-sm">
                <span className="w-36 text-gray-600">{e.type}</span>
                <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden"><div className="h-full bg-gold" style={{ width: `${e.pct}%` }} /></div>
                <span className="w-24 text-right font-semibold text-navy">{usd(e.revenue)} ({e.pct}%)</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Blackout Date Recommendations">
          <p className="text-xs text-gray-500 mb-2">These dates are too valuable for private events:</p>
          <div className="space-y-2">
            {data.blackout_dates.map((b) => (
              <div key={b.event} className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 p-3">
                <div><div className="font-semibold text-navy text-sm">{b.window} · {b.event}</div><div className="text-[11px] text-gray-500">Individual revenue: {usd(b.individual_revenue)}</div></div>
                <Pill tone="rose">Block</Pill>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="Revenue Projections">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {data.projections.map((p) => (
            <div key={p.label} className="rounded-xl bg-navy text-white p-4">
              <div className="text-sm text-gold-light">{p.label}</div>
              <div className="text-3xl font-extrabold text-gold mt-1">+{usd(p.annual)}</div>
              <div className="text-[11px] text-white/50">annual revenue potential</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

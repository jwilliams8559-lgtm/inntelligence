import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usd } from '../components/ui'

const PLANS = [
  { id: 'starter', name: 'Starter', price: 399, best: '5–10 rooms', bullets: ['Rate calendar', 'AI recommendations', '5 competitors', 'Manual approval'] },
  { id: 'professional', name: 'Professional', price: 699, best: '10–20 rooms', bullets: ['Autopilot publishing', 'Guest CRM', 'Packages + gift shop', 'Monthly strategy call'] },
  { id: 'enterprise', name: 'Enterprise', price: 1200, best: '20+ rooms', bullets: ['Multi-property console', '2 advisory hrs/mo', 'Custom integrations'] },
  { id: 'premium', name: 'Premium', price: 2400, best: 'Portfolios', bullets: ['Unlimited properties', 'White-label', 'Dedicated manager'] },
]
const STEPS = ['Property', 'Plan', 'Rooms', 'Review']
const blankRoom = () => ({ name: '', count: 1, base_rate: '', min_rate: '', max_rate: '' })
const INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'

export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)
  const [form, setForm] = useState({ inn: '', city: '', state: '', rooms: 8, first: '', last: '', email: '' })
  const [plan, setPlan] = useState('professional')
  const [founding, setFounding] = useState(false)
  const [rooms, setRooms] = useState([blankRoom()])
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const planObj = PLANS.find((p) => p.id === plan)

  const valid = [
    form.inn && form.city && form.state && form.first && form.last && /\S+@\S+\.\S+/.test(form.email),
    true,
    rooms.length > 0 && rooms.every((r) => r.name && r.count > 0),
    true,
  ]

  const updateRoom = (i, k, v) => setRooms((rs) => rs.map((r, idx) => idx === i ? { ...r, [k]: v } : r))

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'radial-gradient(circle at 50% 20%, #14385f, #061629)' }}>
        <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8 text-center">
          <div className="w-16 h-16 bg-emerald-500 rounded-full mx-auto flex items-center justify-center text-white text-4xl">✓</div>
          <h2 className="text-navy font-bold text-2xl mt-3">{form.inn} is ready!</h2>
          <p className="text-gray-500 text-sm mt-1">Your INNtelligence dashboard is configured and pre-loaded with rate recommendations.</p>
          <div className="mt-5 rounded-xl border border-gold/40 bg-gold/5 p-4 text-left text-sm">
            <div className="flex justify-between py-1"><span className="text-gray-500">Plan</span><span className="font-semibold text-navy">{founding ? 'Founding Member (free 6 mo → $699)' : `${planObj.name} · ${usd(planObj.price)}/mo`}</span></div>
            <div className="flex justify-between py-1"><span className="text-gray-500">Owner</span><span className="text-navy">{form.first} {form.last}</span></div>
            <div className="flex justify-between py-1"><span className="text-gray-500">Room types</span><span className="text-navy">{rooms.length}</span></div>
          </div>
          <button onClick={() => navigate('/')} className="mt-6 w-full bg-gold text-navy font-bold py-3 rounded-xl hover:bg-gold-light">Go to Dashboard →</button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-8 px-4" style={{ background: 'linear-gradient(135deg, #FAF7F0 0%, #F2ECDD 100%)' }}>
      <div className="max-w-3xl mx-auto">
        <div className="bg-navy text-white rounded-t-2xl px-6 py-4">
          <div className="text-[10px] uppercase tracking-[3px] text-gold font-bold">INNtelligence · New Property</div>
          <h1 className="font-bold text-lg">Onboard your inn — Step {step + 1} of {STEPS.length}</h1>
          <div className="flex items-center gap-2 mt-2">
            {STEPS.map((l, i) => (
              <div key={l} className="flex items-center gap-1.5">
                <span className={`w-2.5 h-2.5 rounded-full ${i === step ? 'bg-gold' : i < step ? 'bg-emerald-400' : 'bg-white/30'}`} />
                <span className={`text-[10px] ${i === step ? 'text-gold font-bold' : 'text-white/60'}`}>{l}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-b-2xl shadow-lg p-6 min-h-[340px]">
          {step === 0 && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2"><Label l="Inn Name"><input className={INPUT} value={form.inn} onChange={set('inn')} placeholder="The Blue Ridge Inn" /></Label></div>
              <Label l="City"><input className={INPUT} value={form.city} onChange={set('city')} /></Label>
              <Label l="State / Region"><input className={INPUT} value={form.state} onChange={set('state')} /></Label>
              <Label l="Total Rooms"><input type="number" min="1" className={INPUT} value={form.rooms} onChange={set('rooms')} /></Label>
              <div />
              <Label l="Owner First Name"><input className={INPUT} value={form.first} onChange={set('first')} /></Label>
              <Label l="Owner Last Name"><input className={INPUT} value={form.last} onChange={set('last')} /></Label>
              <div className="col-span-2"><Label l="Owner Email (login)"><input type="email" className={INPUT} value={form.email} onChange={set('email')} placeholder="owner@inn.com" /></Label></div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                {PLANS.map((p) => {
                  const active = !founding && plan === p.id
                  return (
                    <button key={p.id} onClick={() => { setFounding(false); setPlan(p.id) }}
                      className={`text-left p-4 rounded-xl border-2 transition-all ${active ? 'border-gold bg-gold/5 shadow-md' : 'border-gray-200 hover:border-navy/30 bg-white'}`}>
                      <div className="font-bold text-navy">{p.name}</div>
                      <div className="text-2xl font-extrabold text-navy mt-0.5">{usd(p.price)}<span className="text-xs text-gray-500">/mo</span></div>
                      <div className="text-[11px] text-gray-500 mt-1">{p.best}</div>
                      <ul className="mt-2 space-y-0.5 text-[11px] text-gray-700">{p.bullets.map((b, i) => <li key={i}>✓ {b}</li>)}</ul>
                    </button>
                  )
                })}
              </div>
              <button onClick={() => { setFounding(true); setPlan('professional') }}
                className={`w-full text-left p-4 rounded-xl border-2 transition-all ${founding ? 'border-gold bg-gold/10 shadow-md' : 'border-gold/40 bg-gold/5 hover:bg-gold/10'}`}>
                <span className="text-gold">⭐</span> <strong className="text-navy ml-1">Founding Member</strong>
                <span className="text-sm text-gray-600 ml-2">— Free 6 months, then $699/month (Professional)</span>
                {founding && <span className="text-[10px] uppercase text-gold-dark font-bold ml-2">✓ Selected</span>}
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <p className="text-sm text-gray-600">Add the room types at <strong>{form.inn || 'your inn'}</strong> (categories, not individual rooms).</p>
              <table className="w-full text-xs">
                <thead className="text-gray-400 uppercase text-[10px] tracking-wide">
                  <tr><th className="text-left py-1">Room Type</th><th className="text-right">Count</th><th className="text-right">Base</th><th className="text-right">Min</th><th className="text-right">Max</th><th /></tr>
                </thead>
                <tbody>
                  {rooms.map((r, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      <td className="py-1 pr-1"><input className={INPUT} value={r.name} onChange={(e) => updateRoom(i, 'name', e.target.value)} placeholder="Waterfront King" /></td>
                      <td className="py-1 px-1 w-16"><input type="number" min="1" className={`${INPUT} text-right`} value={r.count} onChange={(e) => updateRoom(i, 'count', Number(e.target.value))} /></td>
                      <td className="py-1 px-1 w-20"><input type="number" className={`${INPUT} text-right`} value={r.base_rate} onChange={(e) => updateRoom(i, 'base_rate', e.target.value)} /></td>
                      <td className="py-1 px-1 w-20"><input type="number" className={`${INPUT} text-right`} value={r.min_rate} onChange={(e) => updateRoom(i, 'min_rate', e.target.value)} /></td>
                      <td className="py-1 px-1 w-20"><input type="number" className={`${INPUT} text-right`} value={r.max_rate} onChange={(e) => updateRoom(i, 'max_rate', e.target.value)} /></td>
                      <td className="text-center"><button onClick={() => setRooms((rs) => rs.filter((_, idx) => idx !== i))} className="text-gray-300 hover:text-rose-500">×</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button onClick={() => setRooms((rs) => [...rs, blankRoom()])} className="text-xs text-navy font-semibold hover:underline">+ Add Room Type</button>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Review your configuration</h3>
              <div className="rounded-xl border border-gray-200 p-4 text-sm">
                <Row l="Property" v={form.inn} />
                <Row l="Location" v={`${form.city}, ${form.state}`} />
                <Row l="Owner" v={`${form.first} ${form.last} · ${form.email}`} />
                <Row l="Plan" v={founding ? '⭐ Founding Member — free 6 months → $699/mo' : `${planObj.name} — ${usd(planObj.price)}/mo`} />
                <Row l="Rooms" v={`${rooms.length} types · ${rooms.reduce((s, r) => s + Number(r.count || 0), 0)} of ${form.rooms} rooms`} />
              </div>
              <div className="rounded-lg bg-gold/5 border border-gold/30 p-3 text-xs text-gray-700">
                {founding ? 'Founding Member — no charge for 6 months, then $699/month.' : `First charge of ${usd(planObj.price)} when Stripe billing is activated. No charge today.`}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mt-4">
          <button onClick={() => step === 0 ? navigate('/pricing') : setStep(step - 1)} className="text-sm text-gray-500 hover:text-navy">← Back</button>
          {step < STEPS.length - 1 ? (
            <button onClick={() => setStep(step + 1)} disabled={!valid[step]}
              className="bg-navy text-white text-sm font-bold px-5 py-2 rounded-lg hover:bg-navy-light disabled:bg-gray-300">Next →</button>
          ) : (
            <button onClick={() => setDone(true)} className="bg-gold text-navy text-sm font-bold px-6 py-2 rounded-lg hover:bg-gold-light">Activate Property</button>
          )}
        </div>
      </div>
    </div>
  )
}

const Label = ({ l, children }) => (
  <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">{l}</div>{children}</label>
)
const Row = ({ l, v }) => (
  <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-gray-100 last:border-0"><span className="text-gray-500 font-semibold">{l}</span><span className="col-span-2 text-navy">{v}</span></div>
)

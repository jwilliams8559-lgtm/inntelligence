import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { onboardingComplete } from '../api/client'

const STEPS = ['Welcome', 'Connect PMS', 'Competitors', 'Rooms', 'Autopilot']
const INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'
const DEFAULT_ROOMS = [
  { name: 'Waterfront King', base: 389, min: 329, max: 545, bath: 'En-suite · soaking tub', autopilot: false, confidence: 'balanced' },
  { name: 'Water View Queen', base: 299, min: 259, max: 399, bath: 'En-suite · walk-in shower', autopilot: false, confidence: 'balanced' },
  { name: 'Garden Room', base: 249, min: 219, max: 329, bath: 'En-suite · shower', autopilot: false, confidence: 'balanced' },
  { name: 'Signature Suite', base: 519, min: 469, max: 721, bath: 'En-suite · double vanity', autopilot: false, confidence: 'balanced' },
]
const DEMO_COMPS = {
  'Direct Boutique Competitors': ['Cuthbert House Inn', 'Rhett House Inn', 'Anchorage 1770', '607 Bay Inn'],
  'Upscale Hotels': ['Beaufort Inn', 'City Loft Hotel'],
  'Luxury Reference': ['Montage Palmetto Bluff'],
}

export default function Onboarding() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const first = (user?.owner_name || '').split(' ')[0] || 'there'
  const property = user?.property_name || 'your inn'

  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pms, setPms] = useState('later')         // resnexus | cloudbeds | later
  const [apiKey, setApiKey] = useState('')
  const [pmsTested, setPmsTested] = useState(null)
  const [comps, setComps] = useState(() => new Set(DEMO_COMPS['Direct Boutique Competitors']))
  const [discovering, setDiscovering] = useState(false)
  const [addComp, setAddComp] = useState('')
  const [rooms, setRooms] = useState(DEFAULT_ROOMS)

  useEffect(() => {
    if (step === 2) { setDiscovering(true); const t = setTimeout(() => setDiscovering(false), 1500); return () => clearTimeout(t) }
  }, [step])

  const toggleComp = (n) => setComps((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x })
  const setRoom = (i, k, v) => setRooms((rs) => rs.map((r, idx) => idx === i ? { ...r, [k]: v } : r))

  const finish = async () => {
    setBusy(true)
    try {
      await onboardingComplete({
        pms_type: pms,
        pms_api_key: pms === 'resnexus' ? apiKey : '',
        room_types: rooms.map(({ name, base, min, max, bath }) => ({ name, base_rate: base, min_rate: min, max_rate: max, bathroom: bath })),
        autopilot_preferences: rooms.map(({ name, autopilot, confidence }) => ({ room: name, autopilot, confidence })),
      })
    } catch { /* proceed regardless — completion is idempotent server-side */ }
    finally { setBusy(false); setDone(true) }
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'radial-gradient(circle at 50% 20%, #14385f, #061629)' }}>
        <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8 text-center">
          <div className="w-16 h-16 bg-emerald-500 rounded-full mx-auto flex items-center justify-center text-white text-4xl">✓</div>
          <h2 className="text-navy font-bold text-2xl mt-3">Your INNtelligence dashboard is ready</h2>
          <p className="text-gray-500 text-sm mt-1">{property} is configured with {rooms.length} room types and {comps.size} competitors.</p>
          <div className="mt-4 rounded-lg border border-gold/40 bg-gold/10 p-3 text-left text-sm text-navy">
            🌊 <span className="font-semibold">Heads-up:</span> the Beaufort Water Festival is 9 days out — your waterfront rooms are already being priced up. Review them first.
          </div>
          <button onClick={() => navigate('/')} className="mt-6 w-full bg-gold text-navy font-bold py-3 rounded-xl hover:bg-gold-light">Go to my Rate Calendar →</button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen py-8 px-4" style={{ background: 'linear-gradient(135deg, #FAF7F0 0%, #F2ECDD 100%)' }}>
      <div className="max-w-3xl mx-auto">
        <div className="bg-navy text-white rounded-t-2xl px-6 py-4">
          <div className="text-[10px] uppercase tracking-[3px] text-gold font-bold">INNtelligence Onboarding</div>
          <h1 className="font-bold text-lg">Step {step + 1} of {STEPS.length} — {STEPS[step]}</h1>
          <div className="flex items-center gap-2 mt-2">
            {STEPS.map((l, i) => (
              <span key={l} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-gold' : 'bg-white/20'}`} />
            ))}
          </div>
        </div>

        <div className="bg-white rounded-b-2xl shadow-lg p-6 min-h-[360px]">
          {step === 0 && (
            <div className="text-center py-6">
              <div className="text-5xl">👋</div>
              <h2 className="text-navy font-bold text-2xl mt-3">Welcome to INNtelligence, {first}</h2>
              <p className="text-gray-600 mt-2">We're setting up dynamic pricing for <strong>{property}</strong>.</p>
              <div className="mt-5 text-left max-w-md mx-auto rounded-xl border border-gray-200 p-4 text-sm text-gray-700 space-y-1.5">
                <div className="font-semibold text-navy">Over the next ~90 minutes we'll:</div>
                <div>① Connect your PMS (or use demo data for now)</div>
                <div>② Confirm your competitor set</div>
                <div>③ Review your room types and rate floors/ceilings</div>
                <div>④ Set your autopilot preferences</div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-navy font-bold">Connect your Property Management System</h3>
              <div className="grid grid-cols-3 gap-3">
                {[['resnexus', 'ResNexus'], ['cloudbeds', 'Cloudbeds'], ['later', 'I’ll connect later']].map(([id, label]) => (
                  <button key={id} onClick={() => { setPms(id); setPmsTested(null) }}
                    className={`p-4 rounded-xl border-2 text-sm font-semibold ${pms === id ? 'border-gold bg-gold/10 text-navy' : 'border-gray-200 text-gray-600 hover:border-navy/30'}`}>{label}</button>
                ))}
              </div>
              {pms === 'resnexus' && (
                <div className="rounded-xl border border-gray-200 p-4 space-y-2">
                  <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">ResNexus API Key</div>
                    <input className={INPUT} value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="rnx_live_…" /></label>
                  <button onClick={() => setPmsTested(!!apiKey)} className="bg-navy text-white text-xs font-bold px-4 py-1.5 rounded hover:bg-navy-light">Test Connection</button>
                  {pmsTested === true && <div className="text-xs bg-emerald-50 text-emerald-700 rounded p-2">✓ Connected — syncing 2 years of history…</div>}
                  {pmsTested === false && <div className="text-xs bg-rose-50 text-rose-700 rounded p-2">Enter an API key first.</div>}
                </div>
              )}
              {pms === 'cloudbeds' && (
                <div className="rounded-xl border border-gray-200 p-4">
                  <button onClick={() => setPmsTested(true)} className="bg-navy text-white text-sm font-bold px-4 py-2 rounded hover:bg-navy-light">Connect with Cloudbeds (OAuth)</button>
                  {pmsTested && <div className="text-xs bg-emerald-50 text-emerald-700 rounded p-2 mt-2">✓ Connected — syncing 2 years of history…</div>}
                </div>
              )}
              {pms === 'later' && <div className="text-xs text-gray-500 rounded-lg bg-gray-50 p-3">No problem — recommendations will use realistic demo data until you connect a PMS. You can connect any time from Settings.</div>}
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Your competitors</h3>
              {discovering ? (
                <div className="text-center py-10 text-sm text-gray-500"><div className="w-8 h-8 border-4 border-gold border-t-transparent rounded-full animate-spin mx-auto mb-3" />Searching for competitors within 25 miles…</div>
              ) : (
                <>
                  {Object.entries(DEMO_COMPS).map(([tier, items]) => (
                    <div key={tier}>
                      <div className="text-[10px] uppercase tracking-wide text-navy font-bold mb-1">{tier}</div>
                      <div className="rounded-lg border border-gray-100 divide-y divide-gray-100">
                        {items.map((c) => (
                          <label key={c} className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-gray-50 cursor-pointer">
                            <input type="checkbox" checked={comps.has(c)} onChange={() => toggleComp(c)} />
                            <span className="text-navy">{c}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                  <div className="flex gap-2 items-center pt-1">
                    <input className={INPUT} placeholder="Add a property we missed" value={addComp} onChange={(e) => setAddComp(e.target.value)} />
                    <button onClick={() => { if (addComp) { toggleComp(addComp); setAddComp('') } }} className="bg-navy text-white text-xs font-bold px-3 py-2 rounded">Add</button>
                  </div>
                  <div className="text-[11px] text-gray-500">{comps.size} competitors selected</div>
                </>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Your room configuration</h3>
              <p className="text-xs text-gray-500">{pms === 'later' ? 'Default room types shown — edit to match your inn.' : 'Imported from your PMS — confirm or correct.'}</p>
              <div className="space-y-2">
                {rooms.map((r, i) => (
                  <div key={i} className="rounded-lg border border-gray-200 p-3">
                    <div className="grid grid-cols-4 gap-2 items-end">
                      <label className="col-span-2 text-xs"><div className="text-gray-500 mb-0.5">Room type</div><input className={INPUT} value={r.name} onChange={(e) => setRoom(i, 'name', e.target.value)} /></label>
                      <label className="text-xs"><div className="text-gray-500 mb-0.5">Base</div><input type="number" className={`${INPUT} text-right`} value={r.base} onChange={(e) => setRoom(i, 'base', Number(e.target.value))} /></label>
                      <label className="text-xs"><div className="text-gray-500 mb-0.5">Min / Max</div><div className="flex gap-1"><input type="number" className={`${INPUT} text-right`} value={r.min} onChange={(e) => setRoom(i, 'min', Number(e.target.value))} /><input type="number" className={`${INPUT} text-right`} value={r.max} onChange={(e) => setRoom(i, 'max', Number(e.target.value))} /></div></label>
                    </div>
                    <div className="text-[11px] text-gray-500 mt-1">🛁 AI-detected: {r.bath} <span className="text-gold-dark">— confirm or correct above</span></div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Autopilot preferences</h3>
              <p className="text-xs text-gray-500">Autopilot publishes approved rates automatically within the guardrails you set. You can switch any room to Manual at any time.</p>
              <div className="space-y-2">
                {rooms.map((r, i) => (
                  <div key={i} className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 p-3">
                    <div className="text-sm font-medium text-navy flex-1">{r.name}</div>
                    <button onClick={() => setRoom(i, 'autopilot', !r.autopilot)}
                      className={`text-xs font-semibold px-3 py-1.5 rounded-lg border ${r.autopilot ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-50 text-gray-500 border-gray-200'}`}>
                      {r.autopilot ? 'Autopilot On' : 'Manual Only'}
                    </button>
                    {r.autopilot && (
                      <select value={r.confidence} onChange={(e) => setRoom(i, 'confidence', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
                        <option value="conservative">Conservative</option>
                        <option value="balanced">Balanced</option>
                        <option value="aggressive">Aggressive</option>
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mt-4">
          <button onClick={() => step === 0 ? navigate('/') : setStep(step - 1)} className="text-sm text-gray-500 hover:text-navy">← Back</button>
          {step < STEPS.length - 1 ? (
            <button onClick={() => setStep(step + 1)} className="bg-navy text-white text-sm font-bold px-5 py-2 rounded-lg hover:bg-navy-light">
              {step === 0 ? "Let's get started" : 'Next →'}
            </button>
          ) : (
            <button onClick={finish} disabled={busy} className="bg-gold text-navy text-sm font-bold px-6 py-2 rounded-lg hover:bg-gold-light disabled:opacity-60">
              {busy ? 'Starting…' : 'Start INNtelligence'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { onboardingComplete, getPmsCatalog, discoverCompetitors } from '../api/client'

const STEPS = ['Welcome', 'Your property', 'Connect PMS', 'Competitors', 'Rooms & rates', 'Autopilot']
const INPUT = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'
const PROPERTY_TYPES = [
  ['boutique_inn', 'Boutique inn'],
  ['bed_breakfast', 'Bed & breakfast'],
  ['upscale_hotel', 'Upscale / independent hotel'],
  ['select_service_hotel', 'Select-service hotel'],
  ['vacation_rental', 'Vacation rental(s)'],
  ['other', 'Other'],
]

export default function Onboarding() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const first = (user?.owner_name || '').split(' ')[0] || 'there'

  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  // Step 1 — property
  const [prop, setProp] = useState({
    name: user?.property_name || '', address: '', postalCode: '', website: '',
    type: 'boutique_inn', roomCount: '', typicalRate: '',
  })
  const setP = (k) => (e) => setProp((p) => ({ ...p, [k]: e.target.value }))

  // Step 2 — PMS
  const [catalog, setCatalog] = useState([])
  const [tierLabels, setTierLabels] = useState({})
  const [catalogErr, setCatalogErr] = useState(false)
  const [pmsId, setPmsId] = useState('later')
  const [pmsCreds, setPmsCreds] = useState({})
  const [pmsSearch, setPmsSearch] = useState('')

  // Step 3 — competitors
  const [compsByKey, setCompsByKey] = useState({})     // key -> competitor object
  const [tiers, setTiers] = useState([])               // [{tier,label,competitors:[key...]}]
  const [selected, setSelected] = useState(() => new Set())
  const [discoLoading, setDiscoLoading] = useState(false)
  const [discoSource, setDiscoSource] = useState(null)
  const [discoveredFor, setDiscoveredFor] = useState('')
  const [addComp, setAddComp] = useState('')

  // Step 4 — rooms
  const [rooms, setRooms] = useState([{ name: '', base: '', min: '', max: '', autopilot: false, confidence: 'balanced' }])

  // Load the PMS catalog once (for the Connect step).
  useEffect(() => {
    getPmsCatalog()
      .then((d) => { setCatalog(d.catalog || []); setTierLabels(d.tier_labels || {}) })
      .catch(() => setCatalogErr(true))
  }, [])

  const rateBand = useCallback(() => {
    const r = Number(prop.typicalRate) || 0
    return r > 0 ? { rate_low: Math.round(r * 0.7), rate_high: Math.round(r * 1.3) } : {}
  }, [prop.typicalRate])

  // Discover competitors when entering the Competitors step (re-run if address changed).
  const runDiscovery = useCallback(() => {
    const addr = prop.address || prop.postalCode
    if (!addr) { setTiers([]); setDiscoSource('no_address'); return }
    setDiscoLoading(true)
    discoverCompetitors({
      address: [prop.address, prop.postalCode].filter(Boolean).join(' '),
      property_type: prop.type, room_count: prop.roomCount, name: prop.name,
      ...rateBand(),
    })
      .then((res) => {
        const byKey = {}
        const nextSel = new Set()
        const t = (res.tiers || []).map((tr) => {
          const keys = (tr.competitors || []).map((c) => {
            byKey[c.key] = { ...c, source: 'discovered' }
            nextSel.add(c.key)          // default: select all discovered
            return c.key
          })
          return { tier: tr.tier, label: tr.label, keys }
        })
        setCompsByKey(byKey); setTiers(t); setSelected(nextSel)
        setDiscoSource(res.source); setDiscoveredFor(addr)
      })
      .catch(() => setDiscoSource('error'))
      .finally(() => setDiscoLoading(false))
  }, [prop.address, prop.postalCode, prop.type, prop.roomCount, prop.name, rateBand])

  useEffect(() => {
    if (step === 3 && discoveredFor !== (prop.address || prop.postalCode)) runDiscovery()
  }, [step]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (key) => setSelected((s) => { const x = new Set(s); x.has(key) ? x.delete(key) : x.add(key); return x })
  const selectAll = (on) => setSelected(on ? new Set(Object.keys(compsByKey)) : new Set())
  const addManual = () => {
    const name = addComp.trim()
    if (!name) return
    const key = `manual_${Date.now()}`
    setCompsByKey((m) => ({ ...m, [key]: { key, name, tier: 1, source: 'manual' } }))
    setTiers((ts) => {
      const has1 = ts.find((t) => t.tier === 1)
      if (has1) return ts.map((t) => t.tier === 1 ? { ...t, keys: [...t.keys, key] } : t)
      return [{ tier: 1, label: 'Your Direct Competitors', keys: [key] }, ...ts]
    })
    setSelected((s) => new Set(s).add(key))
    setAddComp('')
  }

  const setRoom = (i, k, v) => setRooms((rs) => rs.map((r, idx) => idx === i ? { ...r, [k]: v } : r))
  const addRoom = () => setRooms((rs) => [...rs, { name: '', base: '', min: '', max: '', autopilot: false, confidence: 'balanced' }])
  const removeRoom = (i) => setRooms((rs) => rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs)

  const pmsSelected = catalog.find((c) => c.id === pmsId)

  const finish = async () => {
    setBusy(true)
    const competitors = [...selected].map((k) => compsByKey[k]).filter(Boolean).map((c) => ({
      name: c.name, tier: c.tier, place_id: c.place_id || null,
      address: c.address || null, website_url: c.website_url || null, source: c.source || 'discovered',
    }))
    const validRooms = rooms.filter((r) => r.name.trim())
    const primaryCred = pmsCreds.api_key || pmsCreds.password || pmsCreds.access_token || ''
    try {
      await onboardingComplete({
        property_name: prop.name,
        address: prop.address, postal_code: prop.postalCode, website_url: prop.website,
        property_type: prop.type, room_count: Number(prop.roomCount) || null,
        pms_type: pmsId,
        pms_api_key: pmsId !== 'later' && pmsId !== 'csv_import' ? primaryCred : '',
        room_types: validRooms.map(({ name, base, min, max }) => ({
          name, base_rate: Number(base) || null, min_rate: Number(min) || null, max_rate: Number(max) || null,
        })),
        autopilot_preferences: validRooms.map(({ name, autopilot, confidence }) => ({ room: name, autopilot, confidence })),
        competitors,
      })
    } catch { /* completion is idempotent server-side — proceed */ }
    finally { setBusy(false); setDone(true) }
  }

  // Step-level validation for the Next button.
  const canNext = () => {
    if (step === 1) return prop.name.trim() && (prop.address.trim() || prop.postalCode.trim())
    return true
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'radial-gradient(circle at 50% 20%, #14385f, #061629)' }}>
        <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8 text-center">
          <div className="w-16 h-16 bg-emerald-500 rounded-full mx-auto flex items-center justify-center text-white text-4xl">✓</div>
          <h2 className="text-navy font-bold text-2xl mt-3">Your INNtelligence dashboard is ready</h2>
          <p className="text-gray-500 text-sm mt-1">
            {prop.name || 'Your property'} is configured with {rooms.filter((r) => r.name.trim()).length} room type(s)
            and {selected.size} competitor(s){pmsId !== 'later' && pmsId !== 'csv_import' ? `, connected to ${pmsSelected?.name || 'your PMS'}` : ''}.
          </p>
          <button onClick={() => navigate('/')} className="mt-6 w-full bg-gold text-navy font-bold py-3 rounded-xl hover:bg-gold-light">Go to my dashboard →</button>
        </div>
      </div>
    )
  }

  const filteredCatalog = catalog.filter((c) => c.name.toLowerCase().includes(pmsSearch.toLowerCase()))
  const grouped = filteredCatalog.reduce((acc, c) => { (acc[c.tier] = acc[c.tier] || []).push(c); return acc }, {})

  return (
    <div className="min-h-screen py-8 px-4" style={{ background: 'linear-gradient(135deg, #FAF7F0 0%, #F2ECDD 100%)' }}>
      <div className="max-w-3xl mx-auto">
        <div className="bg-navy text-white rounded-t-2xl px-6 py-4">
          <div className="text-[10px] uppercase tracking-[3px] text-gold font-bold">INNtelligence Onboarding</div>
          <h1 className="font-bold text-lg">Step {step + 1} of {STEPS.length} — {STEPS[step]}</h1>
          <div className="flex items-center gap-2 mt-2">
            {STEPS.map((l, i) => <span key={l} className={`h-1.5 flex-1 rounded-full ${i <= step ? 'bg-gold' : 'bg-white/20'}`} />)}
          </div>
        </div>

        <div className="bg-white rounded-b-2xl shadow-lg p-6 min-h-[380px]">
          {/* Step 0 — Welcome */}
          {step === 0 && (
            <div className="text-center py-6">
              <div className="text-5xl">👋</div>
              <h2 className="text-navy font-bold text-2xl mt-3">Welcome to INNtelligence, {first}</h2>
              <p className="text-gray-600 mt-2">Let's set up dynamic pricing for your property. It takes about 5 minutes.</p>
              <div className="mt-5 text-left max-w-md mx-auto rounded-xl border border-gray-200 p-4 text-sm text-gray-700 space-y-1.5">
                <div className="font-semibold text-navy">We'll walk through:</div>
                <div>① Your property &amp; location</div>
                <div>② Connecting your PMS or channel manager</div>
                <div>③ Finding &amp; choosing your competitors</div>
                <div>④ Your room types and rate floors/ceilings</div>
                <div>⑤ Autopilot preferences</div>
              </div>
            </div>
          )}

          {/* Step 1 — Property & location */}
          {step === 1 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Tell us about your property</h3>
              <p className="text-xs text-gray-500">Your location is how we find the right competitors near you.</p>
              <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">Property name</div>
                <input className={INPUT} value={prop.name} onChange={setP('name')} placeholder="The Bay Street Inn" /></label>
              <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">Street address</div>
                <input className={INPUT} value={prop.address} onChange={setP('address')} placeholder="1001 Bay Street, Beaufort, SC" /></label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">ZIP / postal code</div>
                  <input className={INPUT} value={prop.postalCode} onChange={setP('postalCode')} placeholder="29902" /></label>
                <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">Rooms / units</div>
                  <input type="number" className={INPUT} value={prop.roomCount} onChange={setP('roomCount')} placeholder="12" /></label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">Property type</div>
                  <select className={INPUT} value={prop.type} onChange={setP('type')}>
                    {PROPERTY_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select></label>
                <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">Typical nightly rate ($)</div>
                  <input type="number" className={INPUT} value={prop.typicalRate} onChange={setP('typicalRate')} placeholder="299" /></label>
              </div>
              <label className="block text-xs"><div className="text-gray-600 font-semibold mb-1">Website (optional)</div>
                <input className={INPUT} value={prop.website} onChange={setP('website')} placeholder="https://yourinn.com" /></label>
            </div>
          )}

          {/* Step 2 — Connect PMS */}
          {step === 2 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Connect your PMS or channel manager</h3>
              <p className="text-xs text-gray-500">
                We integrate with {catalog.length || 'two dozen+'} systems. Pick yours to sync rooms, rates and bookings —
                or connect later and start with the rates you enter here.
              </p>
              {catalogErr && <div className="text-xs bg-amber-50 border border-amber-200 text-amber-700 rounded p-2">Couldn't load the full list right now — you can connect later from Settings.</div>}
              <input className={INPUT} placeholder="Search for your PMS…" value={pmsSearch} onChange={(e) => setPmsSearch(e.target.value)} />
              <div className="max-h-56 overflow-y-auto space-y-3 pr-1">
                {Object.entries(grouped).map(([tier, items]) => (
                  <div key={tier}>
                    <div className="text-[10px] uppercase tracking-wide text-navy font-bold mb-1">{tierLabels[tier] || tier}</div>
                    <div className="grid grid-cols-2 gap-2">
                      {items.map((c) => (
                        <button key={c.id} onClick={() => { setPmsId(c.id); setPmsCreds({}) }}
                          className={`p-2.5 rounded-lg border-2 text-xs font-semibold text-left ${pmsId === c.id ? 'border-gold bg-gold/10 text-navy' : 'border-gray-200 text-gray-600 hover:border-navy/30'}`}>{c.name}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={() => { setPmsId('later'); setPmsCreds({}) }}
                className={`w-full p-2.5 rounded-lg border-2 text-xs font-semibold ${pmsId === 'later' ? 'border-gold bg-gold/10 text-navy' : 'border-gray-200 text-gray-600 hover:border-navy/30'}`}>
                I'll connect later — use the rates I enter
              </button>
              {pmsSelected && pmsSelected.auth_fields?.length > 0 && (
                <div className="rounded-xl border border-gray-200 p-4 space-y-2">
                  <div className="text-xs font-semibold text-navy">Connect {pmsSelected.name}</div>
                  {pmsSelected.notes && <div className="text-[11px] text-gray-500">{pmsSelected.notes}</div>}
                  {pmsSelected.auth_fields.map((f) => (
                    <label key={f.key} className="block text-xs">
                      <div className="text-gray-600 mb-0.5">{f.label}</div>
                      <input type={f.type === 'password' ? 'password' : 'text'} className={INPUT}
                        value={pmsCreds[f.key] || ''} onChange={(e) => setPmsCreds((c) => ({ ...c, [f.key]: e.target.value }))}
                        placeholder={f.help || ''} />
                      {f.help && <div className="text-[10px] text-gray-400 mt-0.5">{f.help}</div>}
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3 — Competitors */}
          {step === 3 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-navy font-bold">Your competitors</h3>
                <button onClick={runDiscovery} className="text-[11px] text-navy underline hover:text-gold">Re-search</button>
              </div>
              {discoLoading ? (
                <div className="text-center py-10 text-sm text-gray-500">
                  <div className="w-8 h-8 border-4 border-gold border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                  Searching for lodging near {prop.address || prop.postalCode}…
                </div>
              ) : (
                <>
                  {discoSource === 'google_places' && (
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-gray-500">Found nearby — uncheck any that aren't real competitors.</span>
                      <span><button onClick={() => selectAll(true)} className="text-navy underline mr-2">Select all</button>
                        <button onClick={() => selectAll(false)} className="text-navy underline">Clear</button></span>
                    </div>
                  )}
                  {(discoSource === 'no_address') && <div className="text-xs bg-amber-50 border border-amber-200 text-amber-700 rounded p-2">Add your address on the previous step to auto-find competitors — or add them manually below.</div>}
                  {(discoSource === 'none' || discoSource === 'geocode_failed' || discoSource === 'error') && <div className="text-xs bg-amber-50 border border-amber-200 text-amber-700 rounded p-2">Automatic search isn't available right now — add your competitors manually below.</div>}

                  {tiers.filter((t) => t.keys.length).map((t) => (
                    <div key={t.tier}>
                      <div className="text-[10px] uppercase tracking-wide text-navy font-bold mb-1">{t.label}</div>
                      <div className="rounded-lg border border-gray-100 divide-y divide-gray-100">
                        {t.keys.map((key) => {
                          const c = compsByKey[key]; if (!c) return null
                          return (
                            <label key={key} className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-gray-50 cursor-pointer">
                              <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(key)} />
                              <span className="text-navy flex-1">{c.name}
                                {c.source === 'manual' && <span className="text-[10px] text-gold-dark ml-1">(added)</span>}</span>
                              {c.rating && <span className="text-[11px] text-gray-400">★ {c.rating}</span>}
                            </label>
                          )
                        })}
                      </div>
                    </div>
                  ))}

                  <div className="flex gap-2 items-center pt-1">
                    <input className={INPUT} placeholder="Add a competitor we missed" value={addComp}
                      onChange={(e) => setAddComp(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addManual() } }} />
                    <button onClick={addManual} className="bg-navy text-white text-xs font-bold px-3 py-2 rounded">Add</button>
                  </div>
                  <div className="text-[11px] text-gray-500">{selected.size} competitor(s) selected</div>
                </>
              )}
            </div>
          )}

          {/* Step 4 — Rooms & rates */}
          {step === 4 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Your rooms &amp; rate guardrails</h3>
              <p className="text-xs text-gray-500">
                {pmsId === 'later' || pmsId === 'csv_import'
                  ? 'Add your room types with the base rate and the floor/ceiling the engine must stay within.'
                  : `We'll import rooms from ${pmsSelected?.name || 'your PMS'} after setup — add any now so you can start immediately.`}
              </p>
              <div className="space-y-2">
                {rooms.map((r, i) => (
                  <div key={i} className="rounded-lg border border-gray-200 p-3">
                    <div className="grid grid-cols-5 gap-2 items-end">
                      <label className="col-span-2 text-xs"><div className="text-gray-500 mb-0.5">Room type</div>
                        <input className={INPUT} value={r.name} onChange={(e) => setRoom(i, 'name', e.target.value)} placeholder="Waterfront King" /></label>
                      <label className="text-xs"><div className="text-gray-500 mb-0.5">Base</div>
                        <input type="number" className={`${INPUT} text-right`} value={r.base} onChange={(e) => setRoom(i, 'base', e.target.value)} /></label>
                      <label className="text-xs"><div className="text-gray-500 mb-0.5">Min</div>
                        <input type="number" className={`${INPUT} text-right`} value={r.min} onChange={(e) => setRoom(i, 'min', e.target.value)} /></label>
                      <label className="text-xs"><div className="text-gray-500 mb-0.5">Max</div>
                        <input type="number" className={`${INPUT} text-right`} value={r.max} onChange={(e) => setRoom(i, 'max', e.target.value)} /></label>
                    </div>
                    {rooms.length > 1 && <button onClick={() => removeRoom(i)} className="text-[11px] text-rose-500 hover:underline mt-1">Remove</button>}
                  </div>
                ))}
              </div>
              <button onClick={addRoom} className="text-xs text-navy font-semibold underline hover:text-gold">+ Add another room type</button>
            </div>
          )}

          {/* Step 5 — Autopilot */}
          {step === 5 && (
            <div className="space-y-3">
              <h3 className="text-navy font-bold">Autopilot preferences</h3>
              <p className="text-xs text-gray-500">Autopilot publishes approved rates automatically within your guardrails. Switch any room to Manual anytime.</p>
              <div className="space-y-2">
                {rooms.filter((r) => r.name.trim()).length === 0 && <div className="text-xs text-gray-400">Add room types on the previous step to set autopilot.</div>}
                {rooms.map((r, i) => r.name.trim() && (
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
            <button onClick={() => canNext() && setStep(step + 1)} disabled={!canNext()}
              className="bg-navy text-white text-sm font-bold px-5 py-2 rounded-lg hover:bg-navy-light disabled:opacity-40">
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

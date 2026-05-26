import { useState } from 'react'
import type { Tenant, Property } from '../lib/types'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface PropertyDraft {
  name: string; address: string; city: string; state: string; zip: string
  total_rooms: number; website: string
}
interface RoomTypeDraft {
  id?: string
  name: string; description: string
  base_rate: number; min_rate: number; max_rate: number
  parsed?: { bathroom_type?: string; view?: string; confidence?: number }
}
interface PMSDraft {
  pms_type: 'resnexus'|'cloudbeds'|'none' | ''
  api_key: string
  test_status: 'idle'|'testing'|'ok'|'fail'
  test_message?: string
}

const STEPS = [
  'Property',
  'Room Types',
  'PMS Connection',
  'Competitors',
  'Autopilot',
] as const

type StepIndex = 0 | 1 | 2 | 3 | 4

const STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

function StepHeader({ step, title, subtitle }: { step: number; title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <div className="text-[11px] tracking-[3px] uppercase text-gold font-bold mb-1">Step {step + 1} of 5</div>
      <h2 className="text-navy font-bold text-2xl">{title}</h2>
      {subtitle && <p className="text-slate-500 text-sm mt-1">{subtitle}</p>}
    </div>
  )
}

function StepNav({ step, setStep, canNext, completed }: {
  step: StepIndex; setStep: (n: StepIndex) => void;
  canNext: boolean; completed: boolean;
}) {
  return (
    <div className="flex items-center justify-between mt-8 pt-4 border-t border-slate-200">
      {step > 0 ? (
        <button onClick={() => setStep(step - 1 as StepIndex)}
          className="px-4 py-2 text-sm font-semibold text-slate-600 hover:text-navy">← Back</button>
      ) : <span />}
      <div className="flex items-center gap-1">
        {[0,1,2,3,4].map(i => (
          <span key={i}
            className={`w-2 h-2 rounded-full ${i === step ? 'bg-navy' : i < step ? 'bg-sage' : 'bg-slate-200'}`} />
        ))}
      </div>
      {step < 4 ? (
        <button onClick={() => canNext && setStep(step + 1 as StepIndex)} disabled={!canNext}
          className="px-5 py-2 text-sm font-bold bg-navy text-white rounded-lg hover:bg-navy-dark disabled:opacity-40 transition-colors">
          Continue →
        </button>
      ) : (
        <button onClick={() => setStep(4 as StepIndex)} disabled={!completed}
          className="px-5 py-2 text-sm font-bold bg-sage text-white rounded-lg hover:bg-sage-dark disabled:opacity-40 transition-colors">
          {completed ? '✓ Finish Setup' : 'Complete all steps first'}
        </button>
      )}
    </div>
  )
}

export default function Onboarding({ tenant, property }: Props) {
  const [step, setStep] = useState<StepIndex>(0)
  const [done, setDone] = useState(false)

  // Step 1 state
  const [draft, setDraft] = useState<PropertyDraft>({
    name: property.name || '',
    address: '', city: property.city || '', state: property.state || 'SC', zip: '',
    total_rooms: 15, website: '',
  })

  // Step 2 state
  const [rooms, setRooms] = useState<RoomTypeDraft[]>([])
  const [newRoom, setNewRoom] = useState<RoomTypeDraft>({
    name: '', description: '', base_rate: 295, min_rate: 200, max_rate: 525,
  })
  const [parsingRoom, setParsingRoom] = useState(false)

  // Step 3 state
  const [pms, setPms] = useState<PMSDraft>({ pms_type: '', api_key: '', test_status: 'idle' })

  // Step 4 state — competitor discovery
  const [radius, setRadius] = useState<10|25|50>(25)
  const [discovering, setDiscovering] = useState(false)
  const [discovered, setDiscovered] = useState<any[]>([])

  // Step 5 state — autopilot toggles
  const [apToggles, setApToggles] = useState<Map<string, boolean>>(new Map())

  const canNext1 = !!(draft.name && draft.city && draft.state && draft.total_rooms > 0)
  const canNext2 = rooms.length >= 1
  const canNext3 = pms.pms_type === 'none' || pms.test_status === 'ok'
  const canNext4 = true
  const canFinish = !!(canNext1 && canNext2 && canNext3)

  async function addRoom() {
    if (!newRoom.name || !newRoom.description) return
    setParsingRoom(true)
    let parsed = undefined
    try {
      // Reuse the Phase autonomous-intelligence description parser via a backend call.
      // For the wizard, simulate parse with simple heuristics if no live endpoint.
      const d = newRoom.description.toLowerCase()
      parsed = {
        bathroom_type: d.includes('clawfoot')  ? 'clawfoot'
                     : d.includes('rain')      ? 'rain_shower'
                     : d.includes('soaking')   ? 'soaking_tub'
                     : 'shower_only',
        view:          d.includes('waterfront')? 'waterfront'
                     : d.includes('water')     ? 'water_view'
                     : d.includes('garden')    ? 'garden'
                                                  : 'interior',
        confidence: 0.85,
      }
    } finally { setParsingRoom(false) }
    setRooms(r => [...r, { ...newRoom, parsed }])
    setNewRoom({ name: '', description: '', base_rate: 295, min_rate: 200, max_rate: 525 })
  }

  async function testPMS() {
    setPms(p => ({ ...p, test_status: 'testing' }))
    // Demo: always pass for non-empty key (mock)
    setTimeout(() => {
      const ok = pms.pms_type === 'none' || (pms.api_key.length > 4)
      setPms(p => ({ ...p, test_status: ok ? 'ok' : 'fail',
                     test_message: ok ? 'Connection verified · 4 room types · 15 rooms found'
                                       : 'Connection failed — check your API key' }))
    }, 1200)
  }

  async function runDiscovery() {
    setDiscovering(true)
    try {
      const r = await fetch(`/api/discover-competitors?slug=${tenant.slug}&radius=${radius}`)
      const j = await r.json()
      // Compact for display
      const list = [
        ...(j.suggested_competitors ?? []),
        ...(j.other_tier1 ?? []).slice(0, 5),
        ...(j.tier2_hotels ?? []).slice(0, 5),
      ]
      setDiscovered(list)
    } catch { setDiscovered([]) }
    finally { setDiscovering(false) }
  }

  if (done) {
    return (
      <div className="flex-1 overflow-y-auto bg-cream p-8">
        <div className="max-w-2xl mx-auto mt-8 bg-white rounded-xl shadow-lg border border-slate-100 p-8 text-center">
          <div className="text-6xl mb-4">✓</div>
          <div className="text-[11px] tracking-[3px] uppercase text-gold font-bold mb-1">Setup Complete</div>
          <h1 className="text-navy font-bold text-3xl mb-2">Your INNtelligence dashboard is ready</h1>
          <p className="text-slate-500 mb-6">
            Welcome aboard, {draft.name}. We've configured pricing for {rooms.length} room type{rooms.length !== 1 ? 's' : ''} across the next 90 days.
          </p>
          <div className="bg-gold/10 rounded-lg p-4 border border-gold/30 text-left mb-6">
            <div className="text-[10px] uppercase tracking-wider text-gold font-bold mb-1">★ First Insight</div>
            <div className="font-bold text-navy">Beaufort Water Festival · July 17–26</div>
            <div className="text-sm text-slate-600 mt-1">
              Peak demand window with sold-out competitors. Waterfront Suite recommendation: <span className="font-bold">$378 → $535</span> with 3-night minimum.
            </div>
          </div>
          <a href="#" onClick={() => window.location.reload()}
            className="inline-block bg-navy text-white text-sm font-bold px-6 py-3 rounded-lg hover:bg-navy-dark transition-colors">
            Open Rate Calendar →
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-8">
      <div className="max-w-3xl mx-auto bg-white rounded-xl shadow-lg border border-slate-100 p-8">
        {step === 0 && (
          <>
            <StepHeader step={0} title="Property Setup" subtitle="Tell us about your inn." />
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Property Name</label>
                <input value={draft.name} onChange={e => setDraft({...draft, name: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
              </div>
              <div className="col-span-2">
                <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Address</label>
                <input value={draft.address} onChange={e => setDraft({...draft, address: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">City</label>
                <input value={draft.city} onChange={e => setDraft({...draft, city: e.target.value})}
                  className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">State</label>
                  <select value={draft.state} onChange={e => setDraft({...draft, state: e.target.value})}
                    className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy">
                    {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">ZIP</label>
                  <input value={draft.zip} onChange={e => setDraft({...draft, zip: e.target.value})}
                    className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
                </div>
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Total Rooms</label>
                <input type="number" min={1} max={500} value={draft.total_rooms}
                  onChange={e => setDraft({...draft, total_rooms: Number(e.target.value)})}
                  className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Website</label>
                <input value={draft.website} onChange={e => setDraft({...draft, website: e.target.value})}
                  placeholder="https://" className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
              </div>
            </div>
            <StepNav step={step} setStep={setStep} canNext={!!canNext1} completed={canFinish} />
          </>
        )}

        {step === 1 && (
          <>
            <StepHeader step={1} title="Room Types" subtitle="Add each room type. We'll parse descriptions to detect amenities." />
            {rooms.length > 0 && (
              <div className="space-y-2 mb-4">
                {rooms.map((r, i) => (
                  <div key={i} className="bg-cream rounded-lg p-3 flex items-start justify-between">
                    <div>
                      <div className="font-semibold text-navy">{r.name}</div>
                      <div className="text-xs text-slate-500">${r.min_rate}–${r.max_rate} · base ${r.base_rate}</div>
                      {r.parsed && (
                        <div className="text-[11px] text-sage mt-1">
                          ✓ Parsed: {r.parsed.bathroom_type?.replace('_',' ')} · {r.parsed.view?.replace('_',' ')} · {Math.round((r.parsed.confidence ?? 0)*100)}% confidence
                        </div>
                      )}
                    </div>
                    <button onClick={() => setRooms(rs => rs.filter((_, j) => j !== i))}
                      className="text-coral text-xs font-semibold">Remove</button>
                  </div>
                ))}
              </div>
            )}
            <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2">
                Add Room Type {rooms.length + 1}
              </div>
              <div className="grid grid-cols-2 gap-2 mb-2">
                <input placeholder="Name (e.g., Waterfront Suite)" value={newRoom.name}
                  onChange={e => setNewRoom({...newRoom, name: e.target.value})}
                  className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
                <div className="grid grid-cols-3 gap-1">
                  <input type="number" placeholder="Base" value={newRoom.base_rate}
                    onChange={e => setNewRoom({...newRoom, base_rate: Number(e.target.value)})}
                    className="px-2 py-2 border border-slate-200 rounded text-xs focus:outline-none focus:border-navy" />
                  <input type="number" placeholder="Min" value={newRoom.min_rate}
                    onChange={e => setNewRoom({...newRoom, min_rate: Number(e.target.value)})}
                    className="px-2 py-2 border border-slate-200 rounded text-xs focus:outline-none focus:border-navy" />
                  <input type="number" placeholder="Max" value={newRoom.max_rate}
                    onChange={e => setNewRoom({...newRoom, max_rate: Number(e.target.value)})}
                    className="px-2 py-2 border border-slate-200 rounded text-xs focus:outline-none focus:border-navy" />
                </div>
              </div>
              <textarea placeholder="Description — mention bathroom type, views, and key amenities."
                value={newRoom.description}
                onChange={e => setNewRoom({...newRoom, description: e.target.value})}
                rows={2} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
              <button onClick={addRoom} disabled={parsingRoom || !newRoom.name || !newRoom.description}
                className="mt-2 px-4 py-2 bg-navy text-white text-sm font-semibold rounded-lg hover:bg-navy-dark disabled:opacity-50">
                {parsingRoom ? 'Parsing…' : '+ Add Room Type'}
              </button>
            </div>
            <StepNav step={step} setStep={setStep} canNext={canNext2} completed={canFinish} />
          </>
        )}

        {step === 2 && (
          <>
            <StepHeader step={2} title="PMS Connection" subtitle="Connect your property management system to sync reservations and publish rates." />
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                {(['resnexus','cloudbeds','none'] as const).map(t => (
                  <button key={t} onClick={() => setPms({...pms, pms_type: t, test_status: 'idle'})}
                    className={`p-4 rounded-lg border-2 text-sm font-semibold ${
                      pms.pms_type === t
                        ? 'border-navy bg-navy/5 text-navy'
                        : 'border-slate-200 text-slate-500 hover:border-navy/30'
                    }`}>
                    {t === 'resnexus' ? 'ResNexus' : t === 'cloudbeds' ? 'Cloudbeds' : 'Skip for now'}
                  </button>
                ))}
              </div>
              {pms.pms_type && pms.pms_type !== 'none' && (
                <div>
                  <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">API Key</label>
                  <input value={pms.api_key} onChange={e => setPms({...pms, api_key: e.target.value, test_status: 'idle'})}
                    placeholder={pms.pms_type === 'resnexus' ? 'rn_xxx…' : 'cb_xxx…'}
                    className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-navy" />
                  <button onClick={testPMS} disabled={pms.test_status === 'testing' || !pms.api_key}
                    className="mt-2 px-4 py-2 bg-navy text-white text-sm font-semibold rounded-lg hover:bg-navy-dark disabled:opacity-50">
                    {pms.test_status === 'testing' ? 'Testing…' : 'Test Connection'}
                  </button>
                  {pms.test_status === 'ok' && (
                    <div className="mt-2 bg-sage/10 border border-sage/30 text-sage-dark text-sm rounded-lg p-3">
                      ✓ {pms.test_message}
                    </div>
                  )}
                  {pms.test_status === 'fail' && (
                    <div className="mt-2 bg-coral/10 border border-coral/30 text-coral text-sm rounded-lg p-3">
                      ✗ {pms.test_message}
                    </div>
                  )}
                </div>
              )}
              {pms.pms_type === 'none' && (
                <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-600">
                  You can connect your PMS later from Settings. Rate recommendations will be available, but autopilot and publishing will be disabled until a PMS is connected.
                </div>
              )}
            </div>
            <StepNav step={step} setStep={setStep} canNext={canNext3} completed={canFinish} />
          </>
        )}

        {step === 3 && (
          <>
            <StepHeader step={3} title="Competitor Set" subtitle="We'll find nearby boutique hotels in your market." />
            <div className="flex items-center gap-3 mb-4">
              <label className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Search radius</label>
              {[10,25,50].map(r => (
                <button key={r} onClick={() => setRadius(r as 10|25|50)}
                  className={`px-3 py-1.5 text-sm font-semibold rounded-full border ${
                    radius === r ? 'bg-navy text-white border-navy' : 'bg-white text-slate-500 border-slate-200'
                  }`}>{r}mi</button>
              ))}
              <button onClick={runDiscovery} disabled={discovering}
                className="ml-auto px-4 py-2 bg-navy text-white text-sm font-semibold rounded-lg hover:bg-navy-dark disabled:opacity-50">
                {discovering ? 'Searching…' : '★ Discover Competitors'}
              </button>
            </div>
            {discovered.length > 0 ? (
              <div className="space-y-1.5 max-h-80 overflow-auto scrollbar-thin">
                {discovered.map((c, i) => (
                  <div key={i} className="flex items-center justify-between bg-cream rounded p-2 text-sm">
                    <div className="flex-1">
                      <div className="font-semibold text-navy">{c.name}</div>
                      <div className="text-xs text-slate-400">{c.distance_miles?.toFixed(1)}mi · tier {c.tier}</div>
                    </div>
                    <span className="text-sage text-xs">✓</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center text-slate-400 text-sm py-8 bg-slate-50 rounded-lg">
                Click "Discover Competitors" to scan within {radius} miles.
              </div>
            )}
            <StepNav step={step} setStep={setStep} canNext={canNext4} completed={canFinish} />
          </>
        )}

        {step === 4 && (
          <>
            <StepHeader step={4} title="Autopilot Setup" subtitle="Choose which rooms can publish rates without your approval." />
            <div className="space-y-2">
              {rooms.map(r => (
                <div key={r.name} className="bg-cream rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <div className="font-semibold text-navy text-sm">{r.name}</div>
                    <div className="text-xs text-slate-500">${r.base_rate} base · ${r.min_rate}–${r.max_rate}</div>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox"
                      checked={!!apToggles.get(r.name)}
                      onChange={e => {
                        const m = new Map(apToggles); m.set(r.name, e.target.checked); setApToggles(m)
                      }}
                      className="sr-only peer" />
                    <div className="w-10 h-5 bg-slate-200 peer-checked:bg-sage rounded-full transition-colors after:absolute after:top-0.5 after:left-0.5 after:w-4 after:h-4 after:bg-white after:rounded-full after:transition-transform peer-checked:after:translate-x-5" />
                  </label>
                </div>
              ))}
              {rooms.length === 0 && (
                <div className="text-center text-slate-400 text-sm py-6">Add room types in Step 2 first.</div>
              )}
            </div>
            <div className="mt-4 bg-navy/5 border border-navy/20 rounded-lg p-3 text-xs text-slate-600">
              <div className="font-semibold text-navy mb-1">Safe defaults:</div>
              Max rate change ±15%, minimum confidence score 75, active hours 6 AM – 10 PM, max 3 changes per day. You can adjust these any time in Settings.
            </div>
            <div className="flex justify-end mt-6 pt-4 border-t border-slate-200">
              <button onClick={() => setDone(true)} disabled={!canFinish}
                className="px-6 py-3 bg-sage text-white text-sm font-bold rounded-lg hover:bg-sage-dark disabled:opacity-40 transition-colors">
                {canFinish ? '✓ Complete Setup' : 'Complete earlier steps first'}
              </button>
            </div>
          </>
        )}

        <div className="mt-6 text-[10px] text-slate-300 text-center">
          INNtelligence · onboarding wizard · {tenant.slug}
        </div>
      </div>
    </div>
  )
}

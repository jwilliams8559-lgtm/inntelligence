import { useEffect, useState, type ChangeEvent } from 'react'

interface Props { open: boolean; onClose: () => void; onProvisioned: () => void }

// ── Types ──────────────────────────────────────────────────────────
interface RoomTypeDraft {
  name: string; count: number; base_rate: number
  min_rate: number; max_rate: number; category: string
}
interface CompetitorCandidate {
  name: string; address: string; tier: string
  distance_miles: number; tripadvisor_rating: number; rooms: number
  pre_checked: boolean
}
interface PmsDef {
  id: string; name: string; tier: string
  notes?: string
  auth_fields: { key: string; label: string; type: string; help?: string }[]
}
interface Provisioned {
  tenant_id: string; inn_name: string; owner_email: string
  temp_password: string; plan_tier: string; founding_member: boolean
  status: string; login_url: string; created_at: string
}

const COUNTRIES: Record<string, { label: string; currency: string; symbol: string; timezone: string; gdpr: boolean }> = {
  US: { label: 'United States',  currency: 'USD', symbol: '$',   timezone: 'America/New_York',  gdpr: false },
  CA: { label: 'Canada',         currency: 'CAD', symbol: 'C$',  timezone: 'America/Toronto',   gdpr: false },
  GB: { label: 'United Kingdom', currency: 'GBP', symbol: '£',   timezone: 'Europe/London',     gdpr: true  },
  IE: { label: 'Ireland',        currency: 'EUR', symbol: '€',   timezone: 'Europe/Dublin',     gdpr: true  },
  FR: { label: 'France',         currency: 'EUR', symbol: '€',   timezone: 'Europe/Paris',      gdpr: true  },
  IT: { label: 'Italy',          currency: 'EUR', symbol: '€',   timezone: 'Europe/Rome',       gdpr: true  },
  ES: { label: 'Spain',          currency: 'EUR', symbol: '€',   timezone: 'Europe/Madrid',     gdpr: true  },
  PT: { label: 'Portugal',       currency: 'EUR', symbol: '€',   timezone: 'Europe/Lisbon',     gdpr: true  },
  AU: { label: 'Australia',      currency: 'AUD', symbol: 'A$',  timezone: 'Australia/Sydney',  gdpr: false },
  NZ: { label: 'New Zealand',    currency: 'NZD', symbol: 'NZ$', timezone: 'Pacific/Auckland',  gdpr: false },
}

const ROOM_CATEGORIES = ['waterfront', 'waterview', 'garden', 'cottage', 'suite', 'standard', 'premium', 'other']

interface Plan { id: 'essentials'|'professional'|'portfolio'|'enterprise'; name: string; price: number; best_for: string; bullets: string[] }
const PLANS: Plan[] = [
  { id: 'essentials',   name: 'Essentials',   price: 399, best_for: '5–15 rooms, first-time revenue management',
    bullets: ['30-day rate calendar', 'AI recommendations', '5 competitors', 'Manual approval only', '✗ No autopilot', '✗ No guest CRM', '✗ No packages/gift shop'] },
  { id: 'professional', name: 'Professional', price: 699, best_for: '10–25 rooms, serious revenue growth',
    bullets: ['90-day calendar', '10 competitors', 'Autopilot', 'Guest CRM', 'Packages + gift shop', 'Direct booking tools', 'Weather + gap nights', 'ROI performance report'] },
  { id: 'portfolio',    name: 'Portfolio',    price: 1199, best_for: 'Multi-property operators',
    bullets: ['Up to 5 properties', 'Management console', 'White label', 'Open API', 'EVE analysis'] },
  { id: 'enterprise',   name: 'Enterprise',   price: 2400, best_for: '5+ properties, advisory clients',
    bullets: ['Unlimited properties', 'Acquisition intelligence', '2 advisory hrs/mo', 'Custom integrations'] },
]

const TIER_LABEL: Record<string, string> = {
  direct_boutique: 'Direct Boutique Competitors',
  upscale:         'Upscale Hotels',
  budget_anchor:   'Budget Anchors',
  luxury_reference:'Luxury Reference',
}
const PMS_TIER_LABEL: Record<string, string> = {
  tier_1:           'Tier 1 — Full Integration',
  tier_2:           'Tier 2 — Connected',
  channel_manager:  'Other / Channel Manager',
  csv_import:       'CSV Import',
}

// ── Component ──────────────────────────────────────────────────────
export default function OnboardingWizard({ open, onClose, onProvisioned }: Props) {
  const [step, setStep] = useState(1)

  // Step 1
  const [innName, setInnName] = useState('')
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [stateField, setStateField] = useState('')
  const [postcode, setPostcode] = useState('')
  const [country, setCountry] = useState('US')
  const [totalRooms, setTotalRooms] = useState(8)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [ownerEmail, setOwnerEmail] = useState('')
  const [ownerPhone, setOwnerPhone] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')

  // Step 2
  const [planId, setPlanId] = useState<Plan['id']>('professional')
  const [founding, setFounding] = useState(false)

  // Step 3
  const [rooms, setRooms] = useState<RoomTypeDraft[]>([
    { name: '', count: 1, base_rate: 0, min_rate: 0, max_rate: 0, category: 'standard' },
  ])
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [suggestSource, setSuggestSource] = useState<string | null>(null)

  // Step 4
  const [pmsCatalog, setPmsCatalog] = useState<PmsDef[]>([])
  const [pmsId, setPmsId] = useState<string | null>(null)
  const [pmsCreds, setPmsCreds] = useState<Record<string, string>>({})
  const [pmsTest, setPmsTest] = useState<{ connected: boolean; pms_name?: string; error?: string; room_types_found?: number; pms_property_name?: string } | null>(null)
  const [pmsTesting, setPmsTesting] = useState(false)

  // Step 5
  const [radius, setRadius] = useState(25)
  const [discoveryLoading, setDiscoveryLoading] = useState(false)
  const [discovery, setDiscovery] = useState<{ groups: Record<string, { label: string; items: CompetitorCandidate[] }>; warning: string; total_count: number } | null>(null)
  const [selectedComps, setSelectedComps] = useState<Set<string>>(new Set())
  const [manualCompName, setManualCompName] = useState('')
  const [manualCompAddress, setManualCompAddress] = useState('')
  const [manualComps, setManualComps] = useState<{ name: string; address: string }[]>([])

  // Step 6 / success
  const [provisioning, setProvisioning] = useState(false)
  const [provisioned, setProvisioned] = useState<Provisioned | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copiedCreds, setCopiedCreds] = useState(false)

  useEffect(() => {
    if (open) fetch('/api/pms/catalog').then(r => r.json()).then(d => setPmsCatalog(d.pms || []))
  }, [open])

  // Step 5 auto-discovery on entry
  useEffect(() => {
    if (step === 5 && city && stateField && !discoveryLoading) {
      runDiscovery(radius)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

  function reset() {
    setStep(1); setInnName(''); setAddress(''); setCity(''); setStateField('')
    setPostcode(''); setCountry('US'); setTotalRooms(8); setFirstName('')
    setLastName(''); setOwnerEmail(''); setOwnerPhone(''); setWebsiteUrl('')
    setPlanId('professional'); setFounding(false)
    setRooms([{ name: '', count: 1, base_rate: 0, min_rate: 0, max_rate: 0, category: 'standard' }])
    setPmsId(null); setPmsCreds({}); setPmsTest(null)
    setDiscovery(null); setSelectedComps(new Set()); setManualComps([])
    setProvisioned(null); setError(null); setCopiedCreds(false)
  }

  const countryCfg = COUNTRIES[country]
  const validStep1 = innName && address && city && stateField && postcode && /\S+@\S+\.\S+/.test(ownerEmail) && firstName && lastName && totalRooms > 0
  const validStep2 = !!planId
  const validStep3 = rooms.length > 0 && rooms.every(r => r.name && r.count > 0 && r.base_rate > 0 && r.min_rate > 0 && r.max_rate > 0)
  const validStep4 = true // PMS is optional

  async function runSuggest() {
    setSuggestLoading(true); setSuggestSource(null)
    try {
      const r = await fetch('/api/onboarding/suggest-rooms', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inn_name: innName, city, state: stateField, total_rooms: totalRooms }),
      })
      const j = await r.json()
      if (j.suggested_rooms?.length) {
        setRooms(j.suggested_rooms.map((s: any) => ({
          name: s.name, count: s.count, base_rate: s.base_rate,
          min_rate: s.min_rate, max_rate: s.max_rate, category: s.category,
        })))
        setSuggestSource(j.source)
      }
    } finally { setSuggestLoading(false) }
  }

  async function testPms() {
    if (!pmsId) return
    setPmsTesting(true); setPmsTest(null)
    try {
      const r = await fetch('/api/pms/connect', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pms_id: pmsId, credentials: pmsCreds, expected_property_name: innName, expected_room_count: totalRooms }),
      })
      const j = await r.json()
      setPmsTest(j)
    } catch (e: any) {
      setPmsTest({ connected: false, error: e?.message || 'Connection failed' })
    } finally { setPmsTesting(false) }
  }

  async function runDiscovery(r: number) {
    setRadius(r); setDiscoveryLoading(true)
    try {
      const res = await fetch('/api/competitors/discover', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city, state: stateField, radius_miles: r }),
      })
      const j = await res.json()
      setDiscovery(j)
      const pre = new Set<string>()
      Object.values(j.groups || {}).forEach((g: any) => g.items.forEach((c: CompetitorCandidate) => { if (c.pre_checked) pre.add(c.name) }))
      // Also auto-select 1 luxury reference (highest rated)
      const lux = j.groups?.luxury_reference?.items || []
      if (lux.length) {
        const top = lux.reduce((a: CompetitorCandidate, b: CompetitorCandidate) => a.tripadvisor_rating > b.tripadvisor_rating ? a : b)
        pre.add(top.name)
      }
      setSelectedComps(pre)
    } finally { setDiscoveryLoading(false) }
  }

  function toggleComp(name: string) {
    const next = new Set(selectedComps)
    if (next.has(name)) next.delete(name); else next.add(name)
    setSelectedComps(next)
  }

  function addManualComp() {
    if (!manualCompName) return
    setManualComps([...manualComps, { name: manualCompName, address: manualCompAddress }])
    setSelectedComps(new Set([...selectedComps, manualCompName]))
    setManualCompName(''); setManualCompAddress('')
  }

  async function activate() {
    setProvisioning(true); setError(null)
    const allComps: { name: string; address?: string; tier?: string }[] = []
    if (discovery) {
      Object.values(discovery.groups).forEach(g => g.items.forEach(c => {
        if (selectedComps.has(c.name)) allComps.push({ name: c.name, address: c.address, tier: c.tier })
      }))
    }
    manualComps.forEach(c => allComps.push({ ...c, tier: 'manual' }))

    try {
      const r = await fetch('/api/admin/provision-tenant', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          inn_name: innName, address, city, state: stateField, postcode, country,
          currency: countryCfg.currency, currency_symbol: countryCfg.symbol,
          timezone: countryCfg.timezone, gdpr_in_scope: countryCfg.gdpr,
          total_rooms: totalRooms,
          owner_first_name: firstName, owner_last_name: lastName,
          owner_email: ownerEmail, owner_phone: ownerPhone, website_url: websiteUrl,
          plan_tier: founding ? 'professional' : planId,
          founding_member: founding,
          room_types: rooms,
          pms_id: pmsId,
          pms_connected: pmsTest?.connected ?? false,
          pms_property_name: pmsTest?.pms_property_name,
          competitors: allComps,
        }),
      })
      if (!r.ok) {
        const e = await r.json().catch(() => ({}))
        throw new Error(e.error || `HTTP ${r.status}`)
      }
      const j: Provisioned = await r.json()
      setProvisioned(j)
      onProvisioned()
    } catch (e: any) {
      setError(e?.message || 'Activation failed')
    } finally { setProvisioning(false) }
  }

  if (!open) return null

  // ── Success state ────────────────────────────────────────────────
  if (provisioned) {
    return <SuccessState
      data={provisioned} innName={innName} totalRooms={totalRooms} rooms={rooms}
      ownerFirstName={firstName} city={city} competitorCount={selectedComps.size + manualComps.length}
      copied={copiedCreds} setCopied={setCopiedCreds}
      onOnboardAnother={reset} onClose={onClose}
    />
  }

  // ── Step shell ───────────────────────────────────────────────────
  return (
    <div className="fixed inset-0 z-50 bg-navy/40 flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-cream rounded-2xl shadow-2xl w-full max-w-5xl my-8 overflow-hidden flex flex-col" style={{ maxHeight: '92vh' }}>
        <Header step={step} onClose={onClose} />

        <div className="flex-1 overflow-y-auto p-6">
          {step === 1 && <Step1 {...{ innName, setInnName, address, setAddress, city, setCity, stateField, setStateField, postcode, setPostcode, country, setCountry, totalRooms, setTotalRooms, firstName, setFirstName, lastName, setLastName, ownerEmail, setOwnerEmail, ownerPhone, setOwnerPhone, websiteUrl, setWebsiteUrl, countryCfg }} />}
          {step === 2 && <Step2 {...{ planId, setPlanId, founding, setFounding, totalRooms }} />}
          {step === 3 && <Step3 {...{ innName, rooms, setRooms, totalRooms, runSuggest, suggestLoading, suggestSource, countryCfg }} />}
          {step === 4 && <Step4 {...{ pmsCatalog, pmsId, setPmsId, pmsCreds, setPmsCreds, pmsTest, pmsTesting, testPms }} />}
          {step === 5 && <Step5 {...{ city, stateField, radius, runDiscovery, discoveryLoading, discovery, selectedComps, toggleComp, manualComps, manualCompName, setManualCompName, manualCompAddress, setManualCompAddress, addManualComp }} />}
          {step === 6 && <Step6 {...{ innName, address, city, stateField, postcode, country, currency: countryCfg.currency, currencySymbol: countryCfg.symbol, gdpr: countryCfg.gdpr, firstName, lastName, ownerEmail, planId, founding, rooms, totalRooms, pmsId, pmsCatalog, pmsTest, selectedComps, manualCompsCount: manualComps.length, error }} />}
        </div>

        <Footer step={step} setStep={setStep} validStep1={validStep1} validStep2={validStep2} validStep3={validStep3} validStep4={validStep4} activate={activate} provisioning={provisioning} />
      </div>
    </div>
  )
}

// ── Header / progress ──────────────────────────────────────────────
function Header({ step, onClose }: { step: number; onClose: () => void }) {
  const labels = ['Property', 'Plan', 'Rooms', 'PMS', 'Competitors', 'Review']
  return (
    <div className="bg-navy text-white px-6 py-4 flex items-center justify-between">
      <div>
        <div className="text-[10px] uppercase tracking-[3px] text-gold font-bold">Admin · New Property</div>
        <h2 className="font-bold text-lg">Onboard a new inn — Step {step} of 6</h2>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          {labels.map((l, i) => (
            <div key={l} className="flex items-center gap-1.5">
              <div className={`w-2.5 h-2.5 rounded-full ${i + 1 === step ? 'bg-gold' : i + 1 < step ? 'bg-sage' : 'bg-white/30'}`} />
              <span className={`text-[10px] ${i + 1 === step ? 'text-gold font-bold' : 'text-white/60'}`}>{l}</span>
              {i < labels.length - 1 && <span className="text-white/30">·</span>}
            </div>
          ))}
        </div>
        <button onClick={onClose} className="text-white/70 hover:text-white text-2xl leading-none ml-2">×</button>
      </div>
    </div>
  )
}

function Footer({ step, setStep, validStep1, validStep2, validStep3, validStep4, activate, provisioning }: any) {
  const validByStep = [true, validStep1, validStep2, validStep3, validStep4, true, true]
  const canNext = validByStep[step]
  return (
    <div className="border-t border-slate-200 bg-white px-6 py-3 flex items-center justify-between">
      <button onClick={() => setStep(Math.max(1, step - 1))} disabled={step === 1}
        className="text-sm text-slate-500 hover:text-navy disabled:opacity-30">← Back</button>
      {step < 6 ? (
        <button onClick={() => setStep(step + 1)} disabled={!canNext}
          className="bg-navy text-white text-sm font-bold px-5 py-2 rounded hover:bg-navy-light disabled:bg-slate-300">Next →</button>
      ) : (
        <button onClick={activate} disabled={provisioning}
          className="bg-gold text-white text-sm font-bold px-6 py-2 rounded hover:bg-gold-dark disabled:opacity-60">
          {provisioning ? 'Activating…' : 'Activate Property'}
        </button>
      )}
    </div>
  )
}

// ── Step 1 — property basics ──────────────────────────────────────
function Step1(p: any) {
  function Field({ label, children, optional }: any) {
    return (
      <label className="block text-xs">
        <div className="text-slate-600 font-semibold mb-1">{label} {optional && <span className="text-slate-400 font-normal">(optional)</span>}</div>
        {children}
      </label>
    )
  }
  const stateLabel = ['GB','IE'].includes(p.country) ? 'Region / County' : 'State / Province'
  const zipLabel   = ['GB','IE'].includes(p.country) ? 'Postcode' : 'ZIP / Postal Code'
  return (
    <div className="grid grid-cols-3 gap-5">
      <div className="col-span-2 grid grid-cols-2 gap-3">
        <div className="col-span-2"><Field label="Inn Name"><input className="w-full input" value={p.innName} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setInnName(e.target.value)} placeholder="The Blue Ridge Inn" /></Field></div>
        <div className="col-span-2"><Field label="Street Address"><input className="w-full input" value={p.address} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setAddress(e.target.value)} /></Field></div>
        <Field label="City / Town"><input className="w-full input" value={p.city} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setCity(e.target.value)} /></Field>
        <Field label={stateLabel}><input className="w-full input" value={p.stateField} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setStateField(e.target.value)} /></Field>
        <Field label={zipLabel}><input className="w-full input" value={p.postcode} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setPostcode(e.target.value)} /></Field>
        <Field label="Country">
          <select className="w-full input" value={p.country} onChange={e => p.setCountry(e.target.value)}>
            {Object.entries(COUNTRIES).map(([code, c]) => <option key={code} value={code}>{c.label}</option>)}
          </select>
        </Field>
        <Field label="Total Rooms"><input type="number" min={1} className="w-full input" value={p.totalRooms} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setTotalRooms(Number(e.target.value))} /></Field>
        <Field label="Owner First Name"><input className="w-full input" value={p.firstName} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setFirstName(e.target.value)} /></Field>
        <Field label="Owner Last Name"><input className="w-full input" value={p.lastName} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setLastName(e.target.value)} /></Field>
        <div className="col-span-2"><Field label="Owner Email (login)"><input type="email" className="w-full input" value={p.ownerEmail} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setOwnerEmail(e.target.value)} placeholder="owner@inn.com" /></Field></div>
        <Field label="Owner Phone" optional><input className="w-full input" value={p.ownerPhone} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setOwnerPhone(e.target.value)} /></Field>
        <Field label="Website URL" optional><input className="w-full input" value={p.websiteUrl} onChange={(e: ChangeEvent<HTMLInputElement>) => p.setWebsiteUrl(e.target.value)} placeholder="https://" /></Field>
      </div>
      <aside className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 self-start">
        <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold mb-2">Live preview</div>
        <div className="font-bold text-navy text-lg">{p.innName || '—'}</div>
        <div className="text-sm text-slate-600">{p.city || '—'}, {p.stateField || '—'}</div>
        <div className="text-xs text-slate-500 mt-2">Currency will be: <strong>{p.countryCfg.symbol} {p.countryCfg.currency}</strong></div>
        <div className="text-xs text-slate-500">Timezone: {p.countryCfg.timezone}</div>
        {p.countryCfg.gdpr && (
          <div className="mt-3 bg-amber-50 border border-amber-200 rounded p-2 text-[11px] text-amber-800">
            ⚠ GDPR compliance steps required before activating EU/UK properties. Ensure DPA is signed and EU representative is appointed.
          </div>
        )}
      </aside>
      <style>{`.input { border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 10px; font-size: 13px; }`}</style>
    </div>
  )
}

// ── Step 2 — plan tier ─────────────────────────────────────────────
function Step2(p: any) {
  const recommendedTier = p.totalRooms >= 10 && p.totalRooms <= 25 ? 'professional' : null
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {PLANS.map(plan => {
          const recommended = plan.id === recommendedTier
          const active = !p.founding && p.planId === plan.id
          return (
            <button key={plan.id}
              onClick={() => { p.setFounding(false); p.setPlanId(plan.id) }}
              className={`text-left p-4 rounded-xl border-2 transition-all relative ${
                active ? 'border-gold bg-gold/5 shadow-md'
                       : recommended ? 'border-sage/40 bg-sage/5'
                                       : 'border-slate-200 hover:border-navy/30 bg-white'
              }`}>
              {recommended && <span className="absolute -top-2 left-3 bg-sage text-white text-[9px] uppercase font-bold tracking-wide px-2 py-0.5 rounded-full">Recommended</span>}
              <div className="font-bold text-navy text-lg">{plan.name}</div>
              <div className="text-2xl font-bold text-navy mt-0.5">${plan.price.toLocaleString()}<span className="text-xs text-slate-500">/mo</span></div>
              <div className="text-[11px] text-slate-500 mt-1">{plan.best_for}</div>
              <ul className="mt-3 space-y-0.5 text-[11px] text-slate-700">
                {plan.bullets.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </button>
          )
        })}
      </div>
      <button onClick={() => { p.setFounding(true); p.setPlanId('professional') }}
        className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
          p.founding ? 'border-gold bg-gold/10 shadow-md' : 'border-gold/40 bg-gold/5 hover:bg-gold/10'
        }`}>
        <div className="flex items-baseline justify-between">
          <div>
            <span className="text-gold">⭐</span>
            <strong className="text-navy ml-1">Founding Member</strong>
            <span className="text-sm text-slate-600 ml-2">— Free 6 months, then $524/mo for life (25% off Professional)</span>
          </div>
          {p.founding && <span className="text-[10px] uppercase text-gold-dark font-bold">✓ Selected</span>}
        </div>
        <div className="text-[11px] text-slate-500 mt-1">In exchange: PMS connection, monthly calls, testimonial, case study.</div>
      </button>
    </div>
  )
}

// ── Step 3 — rooms ─────────────────────────────────────────────────
function Step3(p: any) {
  function update(idx: number, field: keyof RoomTypeDraft, value: any) {
    const next = [...p.rooms]
    next[idx] = { ...next[idx], [field]: value }
    p.setRooms(next)
  }
  function add() {
    p.setRooms([...p.rooms, { name: '', count: 1, base_rate: 0, min_rate: 0, max_rate: 0, category: 'standard' }])
  }
  function remove(idx: number) {
    p.setRooms(p.rooms.filter((_: any, i: number) => i !== idx))
  }
  const totalCount = p.rooms.reduce((s: number, r: RoomTypeDraft) => s + Number(r.count || 0), 0)
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Enter the room types at <strong>{p.innName || 'your inn'}</strong>. Use categories that match how guests see your rooms —
        not individual room numbers. You can edit these later.
      </p>
      <div className="flex items-center justify-between">
        <button onClick={p.runSuggest} disabled={p.suggestLoading}
          className="bg-navy text-white text-xs font-bold px-3 py-1.5 rounded hover:bg-navy-light disabled:opacity-60">
          {p.suggestLoading ? 'Asking Claude…' : '✨ Auto-suggest from Property Name + Location'}
        </button>
        {p.suggestSource && (
          <span className="text-[10px] text-slate-500">
            Source: {p.suggestSource === 'claude' ? '🤖 Claude AI' : '⚙ Deterministic fallback'}
          </span>
        )}
      </div>
      <div className="bg-white rounded-xl border border-slate-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 text-left">Room Type Name</th>
              <th className="px-2 py-2 text-right w-16">Count</th>
              <th className="px-2 py-2 text-right w-20">Base</th>
              <th className="px-2 py-2 text-right w-20">Min</th>
              <th className="px-2 py-2 text-right w-20">Max</th>
              <th className="px-2 py-2 text-left w-28">Category</th>
              <th className="w-8"></th>
            </tr>
          </thead>
          <tbody>
            {p.rooms.map((r: RoomTypeDraft, i: number) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="px-2 py-1"><input className="w-full input" value={r.name} onChange={e => update(i, 'name', e.target.value)} /></td>
                <td className="px-1 py-1"><input type="number" min={1} className="w-full input text-right" value={r.count} onChange={e => update(i, 'count', Number(e.target.value))} /></td>
                <td className="px-1 py-1"><input type="number" min={0} className="w-full input text-right" value={r.base_rate} onChange={e => update(i, 'base_rate', Number(e.target.value))} /></td>
                <td className="px-1 py-1"><input type="number" min={0} className="w-full input text-right" value={r.min_rate} onChange={e => update(i, 'min_rate', Number(e.target.value))} /></td>
                <td className="px-1 py-1"><input type="number" min={0} className="w-full input text-right" value={r.max_rate} onChange={e => update(i, 'max_rate', Number(e.target.value))} /></td>
                <td className="px-1 py-1">
                  <select className="w-full input" value={r.category} onChange={e => update(i, 'category', e.target.value)}>
                    {ROOM_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </td>
                <td className="px-1 text-center">
                  <button onClick={() => remove(i)} className="text-slate-300 hover:text-coral">×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between">
        <button onClick={add} className="text-xs text-navy font-semibold hover:underline">+ Add Room Type</button>
        <div className="text-xs text-slate-500">
          {totalCount} of {p.totalRooms} rooms allocated
          {totalCount !== p.totalRooms && <span className="text-amber-600 ml-1">⚠ counts do not sum to total</span>}
        </div>
      </div>
      <p className="text-[11px] text-slate-500">
        Tip: <strong>Base rate</strong> is your typical rack rate.{' '}
        <strong>Min rate</strong> is the absolute floor — the engine will never go below this.{' '}
        <strong>Max rate</strong> is your ceiling during peak demand.
      </p>
      <style>{`.input { border: 1px solid #E2E8F0; border-radius: 4px; padding: 4px 6px; font-size: 12px; }`}</style>
    </div>
  )
}

// ── Step 4 — PMS ───────────────────────────────────────────────────
function Step4(p: any) {
  const grouped: Record<string, PmsDef[]> = {}
  p.pmsCatalog.forEach((pms: PmsDef) => { (grouped[pms.tier] ||= []).push(pms) })
  const selected = p.pmsCatalog.find((x: PmsDef) => x.id === p.pmsId)
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-navy font-bold">Connect your Property Management System</h3>
        <p className="text-xs text-slate-500">Optional but recommended — enables live rate publishing and reservation sync.</p>
      </div>

      {(['tier_1', 'tier_2', 'channel_manager', 'csv_import'] as const).map(tier => grouped[tier] && (
        <div key={tier}>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">{PMS_TIER_LABEL[tier]}</div>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
            {grouped[tier].map(pms => (
              <button key={pms.id} onClick={() => { p.setPmsId(pms.id); p.setPmsCreds({}); }}
                className={`text-xs font-semibold px-3 py-2 rounded-lg border ${
                  p.pmsId === pms.id ? 'border-gold bg-gold/10 text-navy' : 'border-slate-200 bg-white text-slate-700 hover:border-navy/30'
                }`}>
                {pms.name}
              </button>
            ))}
          </div>
        </div>
      ))}
      <div className="text-center">
        <button onClick={() => { p.setPmsId(null); p.setPmsCreds({}); p.setPmsTest(null) }}
          className="text-xs text-slate-500 underline hover:text-navy">Skip PMS — connect later</button>
      </div>

      {selected && selected.auth_fields.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
          <div className="text-sm font-bold text-navy">{selected.name} credentials</div>
          {(selected as any).notes && (
            <div className="bg-amber-50 border border-amber-200 rounded p-2 text-[11px] text-amber-800">
              ⓘ {(selected as any).notes}
            </div>
          )}
          {selected.auth_fields.map((f: any) => (
            <label key={f.key} className="block text-xs">
              <div className="text-slate-600 font-semibold mb-1">{f.label} {f.help && <span title={f.help} className="text-slate-400 cursor-help">ⓘ</span>}</div>
              <input type={f.type} className="w-full input"
                value={p.pmsCreds[f.key] || ''}
                onChange={e => p.setPmsCreds({ ...p.pmsCreds, [f.key]: e.target.value })} />
            </label>
          ))}
          <button onClick={p.testPms} disabled={p.pmsTesting}
            className="bg-navy text-white text-xs font-bold px-4 py-1.5 rounded hover:bg-navy-light disabled:opacity-60">
            {p.pmsTesting ? 'Testing…' : 'Test Connection'}
          </button>
          {p.pmsTest && (
            <div className={`text-xs p-3 rounded ${p.pmsTest.connected ? 'bg-sage/10 text-sage-dark' : 'bg-coral/10 text-coral'}`}>
              {p.pmsTest.connected
                ? <>✓ Connected to <strong>{p.pmsTest.pms_property_name}</strong> · Found {p.pmsTest.room_types_found} room types</>
                : <>✗ {p.pmsTest.error || 'Connection failed'} — check credentials and try again</>}
            </div>
          )}
          <style>{`.input { border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 10px; font-size: 13px; }`}</style>
        </div>
      )}
    </div>
  )
}

// ── Step 5 — competitor discovery ──────────────────────────────────
function Step5(p: any) {
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-navy font-bold">Discover Local Competitors</h3>
          <p className="text-xs text-slate-500">Within <strong>{p.radius} miles</strong> of <strong>{p.city}, {p.stateField}</strong>.</p>
        </div>
        <div className="flex gap-1 text-xs">
          {[5, 10, 15, 25, 50].map(r => (
            <button key={r} onClick={() => p.runDiscovery(r)} disabled={p.discoveryLoading}
              className={`px-2 py-1 rounded ${p.radius === r ? 'bg-navy text-white font-bold' : 'bg-white border border-slate-200 text-slate-600 hover:border-navy/30'}`}>
              {r} mi
            </button>
          ))}
        </div>
      </div>

      <div className="bg-amber-50 border-2 border-amber-300 rounded-lg p-3 text-xs text-amber-900">
        ⚠ <strong>Verify each property before saving.</strong> Google Places occasionally returns private residences or closed
        businesses as lodging results. We previously found a private home listed as "Bay Street Inn" — always confirm each result
        is an active lodging business.
      </div>

      {p.discoveryLoading ? (
        <div className="text-center py-8 text-sm text-slate-400">Searching Google Places for properties near {p.city}, {p.stateField}…</div>
      ) : p.discovery ? (
        <div className="space-y-4">
          {Object.entries(p.discovery.groups).map(([tier, group]: [string, any]) => (
            <div key={tier}>
              <div className="text-[10px] uppercase tracking-wider text-navy font-bold mb-1">{group.label}</div>
              <div className="bg-white rounded-lg border border-slate-100 divide-y divide-slate-100">
                {group.items.map((c: CompetitorCandidate) => (
                  <label key={c.name} className="flex items-center gap-3 px-3 py-2 text-xs hover:bg-slate-50 cursor-pointer">
                    <input type="checkbox" checked={p.selectedComps.has(c.name)} onChange={() => p.toggleComp(c.name)} />
                    <div className="flex-1 font-semibold text-navy">{c.name}</div>
                    <div className="text-slate-500">{c.distance_miles} mi</div>
                    <div className="text-slate-500">TA {c.tripadvisor_rating}★</div>
                    <div className="text-slate-500">{c.rooms} rooms</div>
                    <div className="text-[10px] uppercase text-slate-400">{tier.replace('_', ' ')}</div>
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <div className="bg-white rounded-lg border border-slate-100 p-3">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">+ Add competitor manually</div>
        <div className="flex gap-2 text-xs items-center">
          <input className="input flex-1" placeholder="Property name" value={p.manualCompName} onChange={e => p.setManualCompName(e.target.value)} />
          <input className="input flex-1" placeholder="Address (optional)" value={p.manualCompAddress} onChange={e => p.setManualCompAddress(e.target.value)} />
          <button onClick={p.addManualComp} className="bg-navy text-white font-bold px-3 py-1.5 rounded">Add</button>
        </div>
        {p.manualComps.length > 0 && (
          <div className="mt-2 space-y-0.5 text-xs">
            {p.manualComps.map((c: any, i: number) => (
              <div key={i} className="text-slate-700">• {c.name} <span className="text-slate-400">{c.address}</span></div>
            ))}
          </div>
        )}
      </div>
      <style>{`.input { border: 1px solid #E2E8F0; border-radius: 6px; padding: 5px 8px; font-size: 12px; }`}</style>
    </div>
  )
}

// ── Step 6 — review & activate ─────────────────────────────────────
function Step6(p: any) {
  const planObj = PLANS.find(x => x.id === p.planId)!
  const pmsDef = p.pmsCatalog?.find((x: PmsDef) => x.id === p.pmsId)
  function Row({ label, value }: { label: string; value: React.ReactNode }) {
    return <div className="grid grid-cols-3 gap-2 text-sm py-1.5 border-b border-slate-100 last:border-b-0">
      <div className="text-slate-500 font-semibold">{label}</div>
      <div className="col-span-2 text-navy">{value}</div>
    </div>
  }
  const totalCount = p.rooms.reduce((s: number, r: RoomTypeDraft) => s + Number(r.count || 0), 0)
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <h3 className="text-navy font-bold mb-2">Review your configuration</h3>
        <Row label="Property" value={<strong>{p.innName}</strong>} />
        <Row label="Address"  value={`${p.address}, ${p.city}, ${p.stateField} ${p.postcode}, ${p.country}`} />
        <Row label="Owner"    value={<>{p.firstName} {p.lastName} — <span className="text-slate-600">{p.ownerEmail}</span></>} />
        <Row label="Plan"     value={p.founding
          ? <>⭐ Founding Member <span className="text-slate-500">— Free 6 months → $524/mo for life</span></>
          : <>{planObj.name} — ${planObj.price}/mo</>} />
        <Row label="Currency" value={`${p.currencySymbol} ${p.currency}`} />
        <Row label="Rooms"    value={`${p.rooms.length} types, ${totalCount} total rooms (target ${p.totalRooms})`} />
        <Row label="PMS"      value={pmsDef
          ? <>{pmsDef.name} {p.pmsTest?.connected ? <span className="text-sage-dark">— Connected ✓</span> : <span className="text-slate-500">— Not tested</span>}</>
          : <span className="text-slate-500">Not connected</span>} />
        <Row label="Competitors" value={`${p.selectedComps.size} discovered + ${p.manualCompsCount} manual`} />
        <Row label="GDPR"        value={p.gdpr
          ? <span className="text-amber-700">In scope — checklist pending</span>
          : <span className="text-slate-500">Not required</span>} />
      </div>
      <div className="bg-gold/5 border border-gold/30 rounded-lg p-3 text-xs text-slate-700">
        {p.founding
          ? <><strong>Founding Member</strong> — no charge for 6 months. Converts to $524/month after.</>
          : <>First charge of <strong>${planObj.price}</strong> will be billed when Stripe billing is activated. No charge today — admin-provisioned accounts are activated manually.</>}
      </div>
      {p.error && <div className="bg-coral/10 border border-coral/30 rounded p-2 text-xs text-coral">⚠ {p.error}</div>}
    </div>
  )
}

// ── Success state ──────────────────────────────────────────────────
function SuccessState({ data, innName, totalRooms, rooms, ownerFirstName, city, competitorCount, copied, setCopied, onOnboardAnother, onClose }: any) {
  const totalRoomTypes = rooms.length

  function copyCreds() {
    const text = `Dashboard: ${data.login_url}\nEmail: ${data.owner_email}\nTemporary password: ${data.temp_password}`
    navigator.clipboard.writeText(text)
    setCopied(true); setTimeout(() => setCopied(false), 2500)
  }

  function welcomeMailto() {
    const subject = encodeURIComponent('Welcome to INNtelligence — Your pricing engine is live')
    const body = encodeURIComponent(
`Dear ${ownerFirstName},

Your AI pricing engine for ${innName} is ready. Here are your login credentials:

Dashboard: ${data.login_url}
Email: ${data.owner_email}
Temporary password: ${data.temp_password}

Please change your password after your first login.

Your dashboard is pre-loaded with:
• ${totalRoomTypes} room types from your configuration (${totalRooms} total rooms)
• ${competitorCount} competitors in the ${city} market
• 90 days of AI-generated rate recommendations awaiting your review

Your first step: log in and review the Rate Calendar. You'll see your pending rate recommendations. Approving these takes less than 5 minutes and puts your pricing ahead of the market immediately.

I'll be in touch within 24 hours to schedule your onboarding call.

Jim Williams · INNtelligence by The Gracious Collection
404-909-5818
jwilliams8559@gmail.com`)
    window.location.href = `mailto:${data.owner_email}?subject=${subject}&body=${body}`
  }

  return (
    <div className="fixed inset-0 z-50 bg-navy/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl p-8">
        <div className="text-center">
          <div className="w-16 h-16 bg-sage rounded-full mx-auto flex items-center justify-center text-white text-4xl">✓</div>
          <h2 className="text-navy font-bold text-2xl mt-3">{innName} is live!</h2>
          <p className="text-slate-500 text-sm mt-1">Tenant ID: <code className="text-xs">{data.tenant_id}</code></p>
        </div>

        <div className="mt-6 border-2 border-gold rounded-xl p-5 bg-gold/5">
          <div className="text-[10px] uppercase tracking-[2px] text-gold-dark font-bold mb-2">Login credentials</div>
          <div className="space-y-1.5 text-sm font-mono">
            <div><span className="text-slate-500">Login URL:</span> <strong>{data.login_url}</strong></div>
            <div><span className="text-slate-500">Email:</span>     <strong>{data.owner_email}</strong></div>
            <div><span className="text-slate-500">Password:</span>  <strong className="bg-white px-2 py-0.5 rounded border border-gold/30">{data.temp_password}</strong></div>
          </div>
          <button onClick={copyCreds}
            className="mt-3 bg-navy text-white text-xs font-bold px-4 py-1.5 rounded hover:bg-navy-light">
            {copied ? '✓ Copied' : 'Copy Credentials'}
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2 text-xs">
          <button onClick={welcomeMailto}
            className="bg-gold text-white font-bold py-2 rounded hover:bg-gold-dark">📧 Send Welcome Email</button>
          <button onClick={onOnboardAnother}
            className="bg-white border border-slate-200 text-navy font-bold py-2 rounded hover:bg-slate-50">+ Onboard Another</button>
          <button onClick={onClose}
            className="col-span-2 bg-navy text-white font-bold py-2 rounded hover:bg-navy-light">Return to Management Console</button>
        </div>
      </div>
    </div>
  )
}

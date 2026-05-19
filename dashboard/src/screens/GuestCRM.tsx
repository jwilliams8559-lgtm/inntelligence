import { useCallback, useEffect, useMemo, useState } from 'react'
import { format, parseISO } from 'date-fns'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface Guest {
  id: string
  first_name: string | null; last_name: string | null
  home_city: string | null; home_state: string | null
  total_stays: number | null; total_nights: number | null
  total_revenue: number | null; avg_rate_paid: number | null
  preferred_room_type: string | null
  booking_sources: string[] | null
  last_stay_date: string | null; next_stay_date: string | null
  tags: string[] | null
  marketing_consent: boolean | null
  source: string | null
  created_at: string | null
}

interface Campaign {
  id: string
  name: string; target_segment: string | null; subject: string | null
  status: 'draft'|'scheduled'|'sending'|'sent'|'cancelled' | null
  scheduled_at: string | null; sent_at: string | null
  recipient_count: number | null; delivered_count: number | null
  opened_count: number | null; clicked_count: number | null
  bookings_attributed: number | null; revenue_attributed: number | null
  trigger_source: string | null
  trigger_metadata: any
  created_at: string | null
}

const SEGMENT_META: Record<string, { label: string; color: string; bg: string }> = {
  vip:         { label: 'VIP',         color: '#B8973E', bg: '#FAF6EE' },
  local:       { label: 'Local',       color: '#1F3A5F', bg: '#E0EAF5' },
  lapsed:      { label: 'Lapsed',      color: '#B91C1C', bg: '#FEF2F2' },
  new_guest:   { label: 'New',         color: '#047857', bg: '#ECFDF5' },
  anniversary: { label: 'Anniversary', color: '#7C3AED', bg: '#F3EAFF' },
  honeymoon:   { label: 'Honeymoon',   color: '#D946EF', bg: '#FDF4FF' },
  corporate:   { label: 'Corporate',   color: '#4B5563', bg: '#F3F4F6' },
  wifi_capture:{ label: 'WiFi',        color: '#0E7490', bg: '#ECFEFF' },
}

function SegmentChip({ tag }: { tag: string }) {
  const m = SEGMENT_META[tag] ?? { label: tag, color: '#475569', bg: '#F1F5F9' }
  return (
    <span style={{ color: m.color, background: m.bg }}
          className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wide">
      {m.label}
    </span>
  )
}

function campaignStatusBadge(status: Campaign['status']) {
  const map: Record<string, string> = {
    sent:      'bg-sage/15 text-sage-dark',
    scheduled: 'bg-navy/15 text-navy',
    sending:   'bg-gold/15 text-gold',
    draft:     'bg-slate-200 text-slate-600',
    cancelled: 'bg-coral/15 text-coral',
  }
  return (
    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${map[status || 'draft'] ?? 'bg-slate-100 text-slate-500'}`}>
      {status ?? 'draft'}
    </span>
  )
}

export default function GuestCRM({ tenant, property }: Props) {
  const [guests,    setGuests]    = useState<Guest[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [segment,   setSegment]   = useState<string>('')
  const [selected,  setSelected]  = useState<Guest | null>(null)
  const [busyCheck, setBusyCheck] = useState(false)
  const [busySend,  setBusySend]  = useState<string | null>(null)
  const [toast,     setToast]     = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (segment) params.set('segment', segment)
    if (search)  params.set('q', search)
    const [gRes, cRes] = await Promise.all([
      fetch(`/api/guests/${property.id}?${params.toString()}`),
      fetch(`/api/campaigns/${property.id}`),
    ])
    const g = await gRes.json().catch(() => [])
    const c = await cRes.json().catch(() => [])
    setGuests(Array.isArray(g) ? g : [])
    setCampaigns(Array.isArray(c) ? c : [])
    setLoading(false)
  }, [property.id, segment, search])

  useEffect(() => { void reload() }, [reload])

  const segmentCounts = useMemo(() => {
    const c: Record<string, number> = {}
    guests.forEach(g => (g.tags ?? []).forEach(t => { c[t] = (c[t] || 0) + 1 }))
    return c
  }, [guests])

  const draftCampaigns = useMemo(
    () => campaigns.filter(c => c.status === 'draft' && c.trigger_source === 'demand'),
    [campaigns]
  )

  async function runDemandCheck() {
    setBusyCheck(true); setToast(null)
    // D4 — minimum 2-second hold so the spinner reads "live" even when the API returns fast
    const minHold = new Promise<void>(res => setTimeout(res, 2000))
    try {
      const [r] = await Promise.all([
        fetch('/api/check-campaigns', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body:   JSON.stringify({ property_id: property.id }),
        }),
        minHold,
      ])
      const j = await r.json()
      setToast(j.count ? `${j.count} new demand campaign draft${j.count > 1 ? 's' : ''} created` : 'No soft windows detected — no drafts created')
      await reload()
    } finally { setBusyCheck(false) }
  }

  async function sendCampaign(c: Campaign) {
    setBusySend(c.id); setToast(null)
    try {
      const r = await fetch('/api/send-campaign', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body:   JSON.stringify({ campaign_id: c.id }),
      })
      const j = await r.json()
      if (j.error) setToast(`Send failed: ${j.error}`)
      else setToast(`Sent ${j.recipient_count} · opened ${j.opened} · clicked ${j.clicked}`)
      await reload()
    } finally { setBusySend(null) }
  }

  const segmentTabs = [
    { key: '', label: 'All' },
    { key: 'vip', label: 'VIP' },
    { key: 'local', label: 'Local' },
    { key: 'lapsed', label: 'Lapsed' },
    { key: 'new_guest', label: 'New' },
    { key: 'anniversary', label: 'Anniversary' },
  ]

  return (
    // D1 — root scrolls. Was h-full overflow-hidden which clipped the
    // Packages + Gift Shop panels below the body. min-h-full plus
    // overflow-y-auto lets the page scroll freely. The internal guest
    // list keeps its own scroll via max-h further down.
    <div className="flex flex-col min-h-full overflow-y-auto bg-cream pb-20">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-4 py-2 flex items-center gap-3 flex-wrap">
        <h1 className="text-navy font-bold text-base whitespace-nowrap">Guest CRM</h1>
        <span className="text-sm text-slate-500">{guests.length} profile{guests.length !== 1 ? 's' : ''}</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={runDemandCheck}
            disabled={busyCheck}
            className="text-xs font-semibold bg-navy text-white px-3 py-1.5 rounded-lg hover:bg-navy-dark disabled:opacity-50 transition-colors"
          >
            {busyCheck ? 'Scanning…' : '★ Run Demand Check'}
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className="px-4 py-2 bg-navy/5 border-b border-navy/20 text-sm text-navy flex items-center gap-2">
          <span>{toast}</span>
          <button onClick={() => setToast(null)} className="ml-auto text-slate-400 hover:text-slate-700">×</button>
        </div>
      )}

      {/* Demand-triggered drafts panel */}
      {draftCampaigns.length > 0 && (
        <div className="bg-gold/10 border-b border-gold/30 px-4 py-2">
          <div className="text-[11px] uppercase tracking-wider text-gold font-bold mb-1">
            ★ Demand Alert · {draftCampaigns.length} draft campaign{draftCampaigns.length > 1 ? 's' : ''} ready for review
          </div>
          <div className="flex flex-wrap gap-2">
            {draftCampaigns.map(c => (
              <div key={c.id} className="bg-white rounded-lg px-3 py-2 shadow-sm border border-gold/30 text-xs flex items-center gap-2">
                <span className="font-semibold text-navy">{c.name}</span>
                <span className="text-slate-500">→ {c.target_segment}</span>
                <button
                  onClick={() => sendCampaign(c)}
                  disabled={busySend === c.id}
                  className="bg-sage text-white text-[10px] font-bold px-2 py-1 rounded hover:bg-sage-dark disabled:opacity-50"
                >
                  {busySend === c.id ? 'Sending…' : 'Send Now'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Body — guest list + drawer; cap body height so panels below remain reachable */}
      <div className="flex" style={{ minHeight: '60vh', maxHeight: '85vh' }}>
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Filters */}
          <div className="bg-white border-b border-slate-200 px-4 py-2 flex items-center gap-2 flex-wrap">
            <input
              type="text" placeholder="Search name or city…" value={search}
              onChange={e => setSearch(e.target.value)}
              className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 w-56 focus:outline-none focus:border-navy"
            />
            <div className="flex items-center gap-1">
              {segmentTabs.map(t => (
                <button
                  key={t.key}
                  onClick={() => setSegment(t.key)}
                  className={`text-xs font-semibold px-2.5 py-1 rounded-full transition-colors ${
                    segment === t.key
                      ? 'bg-navy text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {t.label}{t.key && segmentCounts[t.key] ? ` (${segmentCounts[t.key]})` : ''}
                </button>
              ))}
            </div>
          </div>

          {/* Guest list */}
          <div className="flex-1 overflow-auto scrollbar-thin">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-6 h-6 border-4 border-navy border-t-transparent rounded-full animate-spin" />
              </div>
            ) : guests.length === 0 ? (
              <div className="text-center text-slate-400 text-sm py-12">
                No guests match. Try clearing the filter or adjusting search.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-white shadow-sm">
                  <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="px-4 py-2 font-bold">Guest</th>
                    <th className="px-2 py-2 font-bold">Segments</th>
                    <th className="px-2 py-2 font-bold text-right">Stays</th>
                    <th className="px-2 py-2 font-bold text-right">Revenue</th>
                    <th className="px-2 py-2 font-bold">Last Stay</th>
                    <th className="px-2 py-2 font-bold text-center">Email</th>
                  </tr>
                </thead>
                <tbody>
                  {guests.map((g, gi) => (
                    <tr
                      key={g.id}
                      onClick={() => setSelected(g)}
                      className={`cursor-pointer hover:bg-navy/5 transition-colors border-b border-slate-100 ${
                        gi % 2 === 0 ? 'bg-white' : 'bg-cream/50'
                      } ${selected?.id === g.id ? 'ring-2 ring-inset ring-navy' : ''}`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="font-semibold text-navy">
                          {g.first_name} {g.last_name}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {g.home_city ? `${g.home_city}, ${g.home_state || ''}` : '—'}
                        </div>
                      </td>
                      <td className="px-2 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {(g.tags ?? []).slice(0, 4).map(t => <SegmentChip key={t} tag={t} />)}
                          {(g.tags ?? []).length === 0 && <span className="text-[11px] text-slate-300">—</span>}
                        </div>
                      </td>
                      <td className="px-2 py-2.5 text-right font-semibold text-slate-700">{g.total_stays ?? 0}</td>
                      <td className="px-2 py-2.5 text-right font-bold text-navy">
                        ${(g.total_revenue ?? 0).toLocaleString()}
                      </td>
                      <td className="px-2 py-2.5 text-slate-500 text-xs">
                        {g.last_stay_date ? format(parseISO(g.last_stay_date), 'MMM d, yyyy') : '—'}
                      </td>
                      <td className="px-2 py-2.5 text-center">
                        {g.marketing_consent
                          ? <span className="inline-block w-2 h-2 bg-sage rounded-full" title="Subscribed" />
                          : <span className="inline-block w-2 h-2 bg-slate-300 rounded-full" title="Unsubscribed" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Campaigns section */}
          <div className="bg-white border-t border-slate-200 max-h-[40%] overflow-auto scrollbar-thin">
            <div className="sticky top-0 bg-white border-b border-slate-200 px-4 py-2 flex items-center gap-3 z-10">
              <h2 className="text-navy font-bold text-sm">Campaigns</h2>
              <span className="text-xs text-slate-400">{campaigns.length} total</span>
            </div>
            {campaigns.length === 0 ? (
              <div className="text-center text-slate-400 text-sm py-6">
                No campaigns yet. Run a demand check to draft one automatically.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-100">
                    <th className="px-4 py-1.5">Name</th>
                    <th className="px-2 py-1.5">Status</th>
                    <th className="px-2 py-1.5">Segment</th>
                    <th className="px-2 py-1.5 text-right">Recipients</th>
                    <th className="px-2 py-1.5 text-right">Open Rate</th>
                    <th className="px-2 py-1.5 text-right">Bookings</th>
                    <th className="px-2 py-1.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map(c => {
                    const openRate = c.recipient_count
                      ? Math.round(((c.opened_count ?? 0) / c.recipient_count) * 100)
                      : null
                    return (
                      <tr key={c.id} className="border-b border-slate-50 hover:bg-cream/50">
                        <td className="px-4 py-1.5 font-semibold text-navy text-xs">
                          {c.name}
                          {c.trigger_source === 'demand' && (
                            <span className="ml-2 text-[10px] bg-gold/15 text-gold px-1.5 py-0.5 rounded">
                              ★ AUTO
                            </span>
                          )}
                        </td>
                        <td className="px-2 py-1.5">{campaignStatusBadge(c.status)}</td>
                        <td className="px-2 py-1.5 text-xs text-slate-600">{c.target_segment ?? '—'}</td>
                        <td className="px-2 py-1.5 text-right text-xs">{c.recipient_count ?? '—'}</td>
                        <td className="px-2 py-1.5 text-right text-xs">{openRate !== null ? `${openRate}%` : '—'}</td>
                        <td className="px-2 py-1.5 text-right text-xs">{c.bookings_attributed ?? '—'}</td>
                        <td className="px-2 py-1.5 text-right">
                          {(c.status === 'draft' || c.status === 'scheduled') && (
                            <button
                              onClick={() => sendCampaign(c)}
                              disabled={busySend === c.id}
                              className="text-[10px] font-bold bg-sage text-white px-2 py-1 rounded hover:bg-sage-dark disabled:opacity-50"
                            >
                              {busySend === c.id ? '…' : 'Send'}
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right drawer */}
        {selected && (
          <div className="w-80 flex-shrink-0 bg-white border-l border-slate-200 flex flex-col shadow-xl overflow-y-auto scrollbar-thin">
            <div className="bg-navy px-4 py-3 flex items-start justify-between">
              <div>
                <div className="text-white font-bold text-base">
                  {selected.first_name} {selected.last_name}
                </div>
                <div className="text-white/70 text-xs mt-0.5">
                  {selected.home_city ? `${selected.home_city}, ${selected.home_state || ''}` : 'Location unknown'}
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="text-white/50 hover:text-white text-xl leading-none">×</button>
            </div>

            <div className="px-4 py-3 space-y-4">
              {/* Tags */}
              {selected.tags && selected.tags.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Segments</div>
                  <div className="flex flex-wrap gap-1">
                    {selected.tags.map(t => <SegmentChip key={t} tag={t} />)}
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-cream rounded-lg p-2.5 text-center">
                  <div className="text-2xl font-bold text-navy">{selected.total_stays ?? 0}</div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Total Stays</div>
                </div>
                <div className="bg-cream rounded-lg p-2.5 text-center">
                  <div className="text-2xl font-bold text-navy">${(selected.total_revenue ?? 0).toLocaleString()}</div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Lifetime Revenue</div>
                </div>
                <div className="bg-cream rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-slate-700">{selected.total_nights ?? 0}</div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Nights</div>
                </div>
                <div className="bg-cream rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-slate-700">${selected.avg_rate_paid?.toFixed(0) ?? '—'}</div>
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">Avg Rate</div>
                </div>
              </div>

              {/* Last/next stay */}
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Last stay</span>
                  <span className="font-medium">
                    {selected.last_stay_date ? format(parseISO(selected.last_stay_date), 'MMM d, yyyy') : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Next stay</span>
                  <span className="font-medium">
                    {selected.next_stay_date ? format(parseISO(selected.next_stay_date), 'MMM d, yyyy') : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Preferred room</span>
                  <span className="font-medium">{selected.preferred_room_type || '—'}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Source</span>
                  <span className="font-medium">{selected.source || '—'}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Booking sources</span>
                  <span className="font-medium">{(selected.booking_sources ?? []).join(', ') || '—'}</span>
                </div>
              </div>

              {/* Marketing consent */}
              <div className={`rounded-lg px-3 py-2 text-xs ${
                selected.marketing_consent
                  ? 'bg-sage/10 text-sage-dark border border-sage/30'
                  : 'bg-slate-100 text-slate-500 border border-slate-200'
              }`}>
                {selected.marketing_consent
                  ? '✓ Subscribed to marketing emails'
                  : '✗ Not subscribed — cannot send campaigns'}
              </div>

              {/* Campaign history (filter campaigns by recipient — simplified to "would receive") */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Eligible for campaigns</div>
                <div className="text-xs text-slate-500">
                  Targeted by segment{selected.tags?.length ? ': ' + selected.tags.join(', ') : ' — none assigned yet'}.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* D2 — Guest Packages panel */}
      <div className="px-4 py-3 border-t border-slate-200 bg-cream">
        <LockedFeature
          featureName="Guest Packages & Enhancements"
          featureKey="packages_module"
          description="Optimize add-on packages: Romance, Anniversary, Adventure, Spa, Breakfast, Sunset Cruise, Pet. Generates an estimated $13,000+/mo for a typical 14-room boutique inn."
        >
          <PackagesPanel />
        </LockedFeature>
      </div>

      {/* D3 — Gift Shop panel */}
      <div className="px-4 py-3 border-t border-slate-200 bg-cream">
        <LockedFeature
          featureName="Gift Shop & Online Store"
          featureKey="gift_shop_module"
          description="Track Lowcountry food, branded merch, artisan goods, and wines & spirits. Integration-ready for Square POS and Shopify."
        >
          <GiftShopPanel />
        </LockedFeature>
      </div>

      <div className="px-4 py-1 text-[10px] text-slate-400 bg-white border-t border-slate-100">
        Tenant: {tenant.slug} · property_id: {property.id.slice(0, 8)}…
      </div>
    </div>
  )
}

// ── D2: Guest Packages panel ──
interface Pkg {
  id: string; icon: string; name: string; components: string; description: string
  upsell_price: number; take_rate: number; seasonal: string | null
  active: boolean; coming_soon: boolean
  est_monthly_rev: number
  est_monthly_label: string
  eligible_rooms: number
  room_restriction_label: string
}

function PackagesPanel() {
  const [pkgs, setPkgs] = useState<Pkg[]>([])
  useEffect(() => {
    fetch('/api/packages/active').then(r => r.json()).then(setPkgs).catch(() => setPkgs([]))
  }, [])
  async function togglePkg(p: Pkg) {
    const newActive = !p.active
    setPkgs(list => list.map(x => x.id === p.id ? { ...x, active: newActive } : x))
    try {
      await fetch(`/api/packages/active`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: p.id, active: newActive }),
      })
    } catch { /* keep optimistic update */ }
  }
  const totalActiveRev = pkgs.filter(p => p.active).reduce((s, p) => s + (p.est_monthly_rev || 0), 0)
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-navy font-bold text-sm">Guest Packages &amp; Enhancements</h2>
          <div className="text-[11px] text-slate-500 mt-0.5">
            {pkgs.filter(p => p.active).length} active · Est. ${totalActiveRev.toLocaleString()}/mo combined
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">
            {pkgs.filter(p => p.coming_soon).length} coming soon
          </span>
          <a href="#packages" className="text-[11px] font-semibold text-navy hover:text-gold"
             onClick={() => window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: 'packages' }))}>
            Manage Packages →
          </a>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        {pkgs.map(p => (
          <div key={p.id} className="border border-slate-100 rounded-lg p-3 bg-white relative">
            {p.coming_soon && (
              <span className="absolute top-2 right-2 text-[9px] uppercase tracking-wide bg-gold/15 text-gold px-1.5 py-0.5 rounded">Coming soon</span>
            )}
            <div className="text-2xl mb-1">{p.icon}</div>
            <div className="font-bold text-navy text-sm">{p.name}</div>
            <div className="text-[11px] text-slate-500 mt-0.5">{p.components}</div>
            <div className="text-[11px] text-slate-600 mt-1.5">{p.description}</div>
            {p.seasonal && (
              <span className="inline-block mt-1 text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">
                {p.seasonal}
              </span>
            )}
            <div className="text-sage font-bold text-sm mt-2">+${p.upsell_price} per stay</div>
            <div className="text-[10px] text-slate-400">{p.est_monthly_label}</div>
            {p.room_restriction_label && (
              <div className="text-[10px] text-amber-600 mt-1">{p.room_restriction_label}</div>
            )}
            {!p.coming_soon && (
              <label className="absolute top-2 right-2 inline-flex items-center cursor-pointer">
                <input type="checkbox" checked={p.active} onChange={() => togglePkg(p)} className="sr-only peer" />
                <div className="w-9 h-5 bg-slate-200 peer-checked:bg-sage rounded-full transition-colors after:absolute after:top-0.5 after:left-0.5 after:w-4 after:h-4 after:bg-white after:rounded-full after:transition-transform peer-checked:after:translate-x-4" />
              </label>
            )}
          </div>
        ))}
      </div>
      <div className="text-[10px] text-slate-400 mt-3 italic">
        Monthly estimates based on 75% occupancy × take rate.
      </div>
    </div>
  )
}

// ── D3 (rebuilt 2026-05-19): Flexible Gift Shop with arrangement-aware UI ──

type Arrangement = 'owned' | 'consignment' | 'resell' | 'dropship' | 'gifted'
type Fulfillment = 'in_person' | 'ship_to_guest' | 'drop_ship' | 'digital'

interface ShopItem {
  id: string; name: string
  price: number; cost: number; monthly_units: number
  active: boolean; notes: string; vendor: string
  fulfillment?: Fulfillment | null
  is_consignment?: boolean
  est_monthly_rev?: number
  margin_pct?: number
  arrangement?: string
}

interface ConsignmentDetails {
  inn_commission_pct: number; artist_pct: number
  payment_terms?: string; display_agreement?: string
}

interface ResellDetails {
  brand?: string; program_name?: string
  account_rep?: string; website?: string
  factory?: string
  contact_marketing?: string; contact_sales?: string
  ordering?: string; lead_time?: string
  shipping_notes?: string; display?: string
  notes?: string
}

interface ShopCategory {
  id: string; icon: string; name: string; description?: string
  arrangement: Arrangement; fulfillment: Fulfillment
  margin: number; active: boolean; notes?: string
  item_count: number; total_item_count: number
  est_monthly_rev: number; est_monthly_label: string
  consignment_details?: ConsignmentDetails
  resell_details?: ResellDetails
}

interface CategoryTemplate {
  id: string; icon: string; name: string; description: string
  default_arrangement: Arrangement; default_fulfillment: Fulfillment
  default_margin: number; notes?: string
}

const ARRANGEMENT_BADGE: Record<Arrangement, { label: string; cls: string }> = {
  owned:       { label: 'Owned Inventory',     cls: 'bg-navy/15 text-navy' },
  consignment: { label: 'Consignment',         cls: 'bg-amber-100 text-amber-700' },
  resell:      { label: 'Authorized Reseller', cls: 'bg-sage/15 text-sage-dark' },
  dropship:    { label: 'Drop-Ship',           cls: 'bg-purple-100 text-purple-700' },
  gifted:      { label: 'Gifted/Donated',      cls: 'bg-slate-100 text-slate-600' },
}

const FULFILLMENT_BADGE: Record<Fulfillment, { label: string; icon: string }> = {
  in_person:     { label: 'In-Person',     icon: '🏪' },
  ship_to_guest: { label: 'Ships from Inn', icon: '📦' },
  drop_ship:     { label: 'Drop-Ships from Vendor', icon: '🚢' },
  digital:       { label: 'Digital',       icon: '💻' },
}

function GiftShopPanel() {
  const [cats, setCats]           = useState<ShopCategory[]>([])
  const [itemsByCat, setItemsByCat] = useState<Record<string, ShopItem[]>>({})
  const [expanded, setExpanded]   = useState<Set<string>>(new Set())
  const [addingTo, setAddingTo]   = useState<string | null>(null)
  const [draftItem, setDraftItem] = useState({ name: '', price: '', monthly_units: '', notes: '', vendor: '' })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<Partial<ShopItem>>({})
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [showAddCat, setShowAddCat] = useState(false)
  const [templates, setTemplates]   = useState<CategoryTemplate[]>([])

  const reloadCats = useCallback(() => {
    fetch('/api/gift-shop/categories').then(r => r.json()).then(setCats).catch(() => setCats([]))
  }, [])
  const reloadItems = useCallback((cat_id: string) => {
    fetch(`/api/gift-shop/categories/${cat_id}/items`)
      .then(r => r.json())
      .then(items => setItemsByCat(prev => ({ ...prev, [cat_id]: items })))
      .catch(() => {})
  }, [])

  useEffect(() => {
    reloadCats()
    fetch('/api/gift-shop/categories/templates').then(r => r.json()).then(setTemplates).catch(() => {})
  }, [reloadCats])

  function toggleExpand(id: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else { next.add(id); reloadItems(id) }
      return next
    })
  }

  async function addItem(cat_id: string) {
    if (!draftItem.name || !draftItem.price) return
    await fetch(`/api/gift-shop/categories/${cat_id}/items`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name:          draftItem.name,
        price:         Number(draftItem.price),
        monthly_units: Number(draftItem.monthly_units || 5),
        notes:         draftItem.notes,
        vendor:        draftItem.vendor,
      }),
    })
    setDraftItem({ name: '', price: '', monthly_units: '', notes: '', vendor: '' })
    setAddingTo(null)
    reloadItems(cat_id); reloadCats()
  }

  async function toggleActive(cat_id: string, item: ShopItem) {
    await fetch(`/api/gift-shop/categories/${cat_id}/items/${item.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !item.active }),
    })
    reloadItems(cat_id); reloadCats()
  }

  async function confirmDelete(cat_id: string, item: ShopItem) {
    await fetch(`/api/gift-shop/categories/${cat_id}/items/${item.id}`, { method: 'DELETE' })
    setDeleteConfirmId(null)
    reloadItems(cat_id); reloadCats()
  }

  function startEdit(item: ShopItem) {
    setEditingId(item.id)
    setEditDraft({ name: item.name, price: item.price, monthly_units: item.monthly_units, notes: item.notes, vendor: item.vendor })
  }
  async function saveEdit(cat_id: string) {
    if (!editingId) return
    await fetch(`/api/gift-shop/categories/${cat_id}/items/${editingId}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editDraft),
    })
    setEditingId(null); setEditDraft({})
    reloadItems(cat_id); reloadCats()
  }

  const grandTotal = cats.reduce((s, c) => s + c.est_monthly_rev, 0)

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div>
          <h2 className="text-navy font-bold text-sm">Gift Shop &amp; Online Store</h2>
          <div className="text-[11px] text-slate-500 mt-0.5">
            Manage everything you sell — physical products, art, resell agreements, drop-ship items, and more.
          </div>
        </div>
        <button onClick={() => setShowAddCat(true)}
          className="bg-navy text-white text-xs font-bold px-3 py-1.5 rounded-lg hover:bg-navy-dark">
          + Add Category
        </button>
      </div>

      <div className="bg-gold/10 border border-gold/30 rounded-lg px-3 py-2 mb-3 text-xs text-gold-dark">
        🔗 Square POS / Shopify — connect to import sales data and sync inventory counts automatically.
        <div className="text-[11px] text-slate-600 italic mt-1">
          These integrations import data. Add and manage what you sell in the categories below.
        </div>
      </div>

      <div className="bg-cream rounded-lg p-3 mb-3 flex items-center justify-between">
        <span className="text-xs text-slate-600">
          Total est. monthly gift shop revenue across {cats.reduce((s, c) => s + c.item_count, 0)} active items in {cats.length} categories
        </span>
        <span className="font-bold text-gold text-lg">${grandTotal.toLocaleString()}/mo</span>
      </div>

      <div className="space-y-2">
        {cats.map(cat => {
          const isOpen   = expanded.has(cat.id)
          const items    = itemsByCat[cat.id] ?? []
          const arrBadge = ARRANGEMENT_BADGE[cat.arrangement] ?? ARRANGEMENT_BADGE.owned
          const fulBadge = FULFILLMENT_BADGE[cat.fulfillment] ?? FULFILLMENT_BADGE.in_person
          return (
            <div key={cat.id} className="border border-slate-200 rounded-lg overflow-hidden">
              <button onClick={() => toggleExpand(cat.id)}
                className="w-full bg-cream hover:bg-cream/60 px-3 py-2 flex items-center gap-3 text-left transition-colors">
                <span className="text-xl">{cat.icon}</span>
                <div className="flex-1">
                  <div className="font-bold text-navy text-sm">{cat.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${arrBadge.cls}`}>
                      {arrBadge.label}
                    </span>
                    <span className="text-[10px] text-slate-500">{fulBadge.icon} {fulBadge.label}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {cat.item_count} active items · Est. ${cat.est_monthly_rev.toLocaleString()}/mo
                  </div>
                </div>
                <span className="text-slate-400 text-lg">{isOpen ? '▾' : '▸'}</span>
              </button>

              {isOpen && (
                <div className="bg-white">
                  {cat.description && (
                    <div className="px-3 py-2 text-xs text-slate-600 border-b border-slate-100">{cat.description}</div>
                  )}

                  {/* Arrangement-specific details panel */}
                  {cat.consignment_details && (
                    <div className="px-3 py-2 bg-amber-50/50 border-b border-amber-100 text-xs">
                      <div className="font-bold text-amber-800">📋 Consignment Terms</div>
                      <div className="text-slate-600 mt-1 space-y-0.5">
                        <div>Commission: <strong>Inn {cat.consignment_details.inn_commission_pct}% / Artist {cat.consignment_details.artist_pct}%</strong></div>
                        {cat.consignment_details.payment_terms &&
                          <div>Payment terms: {cat.consignment_details.payment_terms}</div>}
                        {cat.consignment_details.display_agreement &&
                          <div className="italic">{cat.consignment_details.display_agreement}</div>}
                      </div>
                      {items.length > 0 && (() => {
                        const totalSale = items.filter(i => i.active).reduce((s, i) => s + i.price * i.monthly_units, 0)
                        const innShare  = totalSale * (cat.consignment_details!.inn_commission_pct / 100)
                        const artShare  = totalSale - innShare
                        return (
                          <div className="mt-2 pt-2 border-t border-amber-200 text-[11px]">
                            Monthly settlement: <strong className="text-amber-700">Est. ${artShare.toFixed(0)} to artists</strong>,
                            <strong className="text-navy"> ${innShare.toFixed(0)} retained by inn</strong>
                          </div>
                        )
                      })()}
                    </div>
                  )}

                  {cat.resell_details && (
                    <div className="px-3 py-2 bg-sage/5 border-b border-sage/20 text-xs">
                      <div className="flex items-center justify-between">
                        <div className="font-bold text-sage-dark">
                          🤝 {cat.resell_details.program_name ?? `${cat.resell_details.brand} Resell Program`}
                        </div>
                        {cat.resell_details.contact_sales && (
                          <a href={`mailto:${cat.resell_details.contact_sales}`}
                             className="text-[10px] bg-navy text-white px-2 py-0.5 rounded hover:bg-navy-dark">
                            📧 Contact Vendor
                          </a>
                        )}
                      </div>
                      <div className="text-slate-600 mt-1 space-y-0.5">
                        {cat.resell_details.brand && <div>Brand: <strong>{cat.resell_details.brand}</strong></div>}
                        {cat.resell_details.factory && <div>Factory: {cat.resell_details.factory}</div>}
                        {cat.resell_details.website && <div>Website: {cat.resell_details.website}</div>}
                        {cat.resell_details.ordering && <div className="italic mt-1">{cat.resell_details.ordering}</div>}
                        {cat.resell_details.lead_time && <div>Lead time: <strong>{cat.resell_details.lead_time}</strong></div>}
                      </div>
                      <div className="mt-1.5 text-[11px] text-sage-dark italic">
                        Items ship direct from vendor to guest — no inventory needed.
                      </div>
                    </div>
                  )}

                  {cat.notes && !cat.consignment_details && !cat.resell_details && (
                    <div className="px-3 py-2 bg-slate-50 text-xs italic text-slate-600 border-b border-slate-100">
                      {cat.notes}
                    </div>
                  )}

                  <table className="w-full text-xs">
                    <thead className="bg-slate-50">
                      <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="px-3 py-1.5">Item / Vendor</th>
                        <th className="px-2 py-1.5 text-right">Price</th>
                        <th className="px-2 py-1.5 text-right">Mo Units</th>
                        <th className="px-2 py-1.5 text-right">Rev/Mo</th>
                        <th className="px-2 py-1.5 text-center">Fulfillment</th>
                        <th className="px-2 py-1.5 text-center">Active</th>
                        <th className="px-2 py-1.5"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map(item => {
                        const isEditing = editingId === item.id
                        const rev = item.price * item.monthly_units
                        const fulOverride = item.fulfillment && item.fulfillment !== cat.fulfillment
                        const fulIcon = FULFILLMENT_BADGE[(item.fulfillment ?? cat.fulfillment) as Fulfillment]?.icon ?? '🏪'
                        return (
                          <tr key={item.id} className="border-t border-slate-100">
                            <td className="px-3 py-1.5">
                              {isEditing ? (
                                <>
                                  <input value={editDraft.name as string ?? ''}
                                    onChange={e => setEditDraft(d => ({ ...d, name: e.target.value }))}
                                    className="border border-slate-200 rounded px-1.5 py-0.5 w-full mb-1" />
                                  <input placeholder="Vendor" value={editDraft.vendor as string ?? ''}
                                    onChange={e => setEditDraft(d => ({ ...d, vendor: e.target.value }))}
                                    className="border border-slate-200 rounded px-1.5 py-0.5 w-full text-[10px]" />
                                </>
                              ) : (
                                <>
                                  <div className="font-medium text-slate-700">{item.name}</div>
                                  {item.vendor && (
                                    <div className="text-[10px] text-slate-400">{item.vendor}</div>
                                  )}
                                  {item.notes && (
                                    <div className="text-[10px] text-slate-400 italic">{item.notes}</div>
                                  )}
                                  {item.is_consignment && (
                                    <span className="inline-block mt-1 text-[9px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-bold">
                                      📋 Consignment
                                    </span>
                                  )}
                                </>
                              )}
                            </td>
                            <td className="px-2 py-1.5 text-right">
                              {isEditing
                                ? <input type="number" step="0.01" value={editDraft.price as number ?? 0}
                                    onChange={e => setEditDraft(d => ({ ...d, price: Number(e.target.value) }))}
                                    className="border border-slate-200 rounded px-1 py-0.5 w-16 text-right" />
                                : `$${item.price.toFixed(2)}`}
                              {item.margin_pct != null && !isEditing && (
                                <div className="text-[10px] text-slate-400">{item.margin_pct.toFixed(0)}% margin</div>
                              )}
                            </td>
                            <td className="px-2 py-1.5 text-right">
                              {isEditing
                                ? <input type="number" value={editDraft.monthly_units as number ?? 0}
                                    onChange={e => setEditDraft(d => ({ ...d, monthly_units: Number(e.target.value) }))}
                                    className="border border-slate-200 rounded px-1 py-0.5 w-14 text-right" />
                                : item.monthly_units}
                            </td>
                            <td className="px-2 py-1.5 text-right text-sage font-semibold">${rev.toFixed(0)}</td>
                            <td className="px-2 py-1.5 text-center text-base"
                                title={FULFILLMENT_BADGE[(item.fulfillment ?? cat.fulfillment) as Fulfillment]?.label ?? ''}>
                              {fulIcon}
                              {fulOverride && <span className="block text-[9px] text-amber-600">override</span>}
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" checked={item.active}
                                       onChange={() => toggleActive(cat.id, item)} className="sr-only peer" />
                                <div className="w-7 h-3.5 bg-slate-200 peer-checked:bg-sage rounded-full after:absolute after:top-0.5 after:left-0.5 after:w-2.5 after:h-2.5 after:bg-white after:rounded-full peer-checked:after:translate-x-3.5 after:transition-transform" />
                              </label>
                            </td>
                            <td className="px-2 py-1.5 text-right space-x-1 whitespace-nowrap">
                              {deleteConfirmId === item.id ? (
                                <>
                                  <span className="text-[10px] text-slate-500">Remove?</span>
                                  <button onClick={() => confirmDelete(cat.id, item)} className="text-coral font-bold">Yes</button>
                                  <button onClick={() => setDeleteConfirmId(null)} className="text-slate-400">No</button>
                                </>
                              ) : isEditing ? (
                                <>
                                  <button onClick={() => saveEdit(cat.id)} className="text-sage font-semibold">Save</button>
                                  <button onClick={() => setEditingId(null)} className="text-slate-400">Cancel</button>
                                </>
                              ) : (
                                <>
                                  <button onClick={() => startEdit(item)} title="Edit" className="text-navy hover:underline">✏</button>
                                  <button onClick={() => setDeleteConfirmId(item.id)} title="Delete" className="text-coral hover:underline">🗑</button>
                                </>
                              )}
                            </td>
                          </tr>
                        )
                      })}

                      {/* Add row */}
                      {addingTo === cat.id ? (
                        <tr className="border-t-2 border-sage/30 bg-sage/5">
                          <td className="px-3 py-2">
                            <input placeholder="Item name" value={draftItem.name}
                              onChange={e => setDraftItem(d => ({ ...d, name: e.target.value }))}
                              className="border border-slate-200 rounded px-2 py-0.5 w-full" />
                            <input placeholder={cat.arrangement === 'consignment' ? 'Artist / vendor name' : 'Vendor (optional)'}
                              value={draftItem.vendor}
                              onChange={e => setDraftItem(d => ({ ...d, vendor: e.target.value }))}
                              className="border border-slate-200 rounded px-2 py-0.5 w-full mt-1 text-[10px]" />
                            <input placeholder="Notes (optional)" value={draftItem.notes}
                              onChange={e => setDraftItem(d => ({ ...d, notes: e.target.value }))}
                              className="border border-slate-200 rounded px-2 py-0.5 w-full mt-1 text-[10px]" />
                          </td>
                          <td className="px-2 py-2 text-right">
                            <input type="number" step="0.01" placeholder="Price" value={draftItem.price}
                              onChange={e => setDraftItem(d => ({ ...d, price: e.target.value }))}
                              className="border border-slate-200 rounded px-1 py-0.5 w-16 text-right" />
                          </td>
                          <td className="px-2 py-2 text-right">
                            <input type="number" placeholder="Mo" value={draftItem.monthly_units}
                              onChange={e => setDraftItem(d => ({ ...d, monthly_units: e.target.value }))}
                              className="border border-slate-200 rounded px-1 py-0.5 w-14 text-right" />
                          </td>
                          <td colSpan={4} className="px-2 py-2 text-right space-x-2 whitespace-nowrap">
                            <button onClick={() => addItem(cat.id)}
                              className="bg-sage text-white font-semibold text-[11px] px-2 py-0.5 rounded">Save</button>
                            <button onClick={() => setAddingTo(null)} className="text-slate-400 text-[11px]">Cancel</button>
                          </td>
                        </tr>
                      ) : (
                        <tr>
                          <td colSpan={7} className="px-3 py-1.5">
                            <button onClick={() => setAddingTo(cat.id)}
                              className="text-[11px] text-navy hover:text-gold font-semibold">
                              + Add Item to {cat.name}
                            </button>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="text-[10px] text-slate-400 italic mt-2">
        Based on current active items and estimated monthly unit sales.
      </div>

      {showAddCat && <AddCategoryModal templates={templates} onClose={() => setShowAddCat(false)} onCreated={reloadCats} />}
    </div>
  )
}

// ── Add Category — template picker + form ─────────────────────────────
function AddCategoryModal({ templates, onClose, onCreated }:
  { templates: CategoryTemplate[]; onClose: () => void; onCreated: () => void }) {
  const [step, setStep] = useState<'pick' | 'form'>('pick')
  const [chosen, setChosen] = useState<CategoryTemplate | null>(null)
  const [form, setForm] = useState({
    icon: '📦', name: '', description: '',
    arrangement: 'owned' as Arrangement,
    fulfillment: 'in_person' as Fulfillment,
    margin: 0.50, notes: '',
    inn_commission_pct: 30,
    brand: '', contact_sales: '', website: '', ordering: '', lead_time: '',
  })
  function useTemplate(t: CategoryTemplate) {
    setChosen(t)
    setForm(f => ({
      ...f,
      icon:        t.icon,
      name:        t.name,
      description: t.description,
      arrangement: t.default_arrangement,
      fulfillment: t.default_fulfillment,
      margin:      t.default_margin,
      notes:       t.notes ?? '',
    }))
    setStep('form')
  }
  function startCustom() {
    setChosen(null)
    setForm(f => ({ ...f, icon: '📦', name: '', description: '', arrangement: 'owned', fulfillment: 'in_person', margin: 0.5, notes: '' }))
    setStep('form')
  }
  async function submit() {
    if (!form.name) return
    const body: any = {
      icon:        form.icon,
      name:        form.name,
      description: form.description,
      arrangement: form.arrangement,
      fulfillment: form.fulfillment,
      margin:      form.margin,
      notes:       form.notes,
    }
    if (form.arrangement === 'consignment') {
      body.consignment_details = {
        inn_commission_pct: form.inn_commission_pct,
        artist_pct:         100 - form.inn_commission_pct,
      }
    }
    if (form.arrangement === 'resell' || form.arrangement === 'dropship') {
      body.resell_details = {
        brand:          form.brand,
        contact_sales:  form.contact_sales,
        website:        form.website,
        ordering:       form.ordering,
        lead_time:      form.lead_time,
        program_name:   form.brand ? `${form.brand} Resell Program` : '',
      }
    }
    await fetch('/api/gift-shop/categories', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    onCreated(); onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
           onClick={e => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white">
          <h2 className="font-bold text-navy">
            {step === 'pick' ? 'Add Category — choose a starting point' : 'Category details'}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl leading-none">×</button>
        </div>

        {step === 'pick' && (
          <div className="p-5">
            <p className="text-xs text-slate-500 mb-3">
              Start from a template (pre-fills arrangement, fulfillment, margin) or build from scratch.
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
              {templates.map(t => (
                <div key={t.id} className="border border-slate-200 rounded-lg p-3 bg-white hover:border-navy/40 transition-colors">
                  <div className="text-2xl mb-1">{t.icon}</div>
                  <div className="font-bold text-navy text-sm">{t.name}</div>
                  <div className="text-[11px] text-slate-500 mt-1">{t.description}</div>
                  <span className={`inline-block text-[9px] uppercase tracking-wide px-1.5 py-0.5 rounded mt-2 ${ARRANGEMENT_BADGE[t.default_arrangement].cls}`}>
                    {ARRANGEMENT_BADGE[t.default_arrangement].label}
                  </span>
                  <button onClick={() => useTemplate(t)}
                    className="w-full mt-3 bg-navy text-white text-[11px] font-bold py-1.5 rounded hover:bg-navy-dark">
                    Use This Template
                  </button>
                </div>
              ))}
            </div>
            <div className="mt-4 text-center">
              <button onClick={startCustom} className="text-sm font-semibold text-navy underline hover:text-gold">
                Create Custom Category →
              </button>
            </div>
          </div>
        )}

        {step === 'form' && (
          <div className="p-5 space-y-3 text-sm">
            {chosen && (
              <div className="bg-cream rounded p-2 text-[11px] text-slate-600">
                Starting from template: <strong>{chosen.name}</strong>
              </div>
            )}
            <div className="grid grid-cols-3 gap-2">
              <label className="block">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Icon</div>
                <input value={form.icon} onChange={e => setForm(f => ({ ...f, icon: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-2 py-1 text-xl text-center" />
              </label>
              <label className="block col-span-2">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Category Name</div>
                <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-2 py-1" />
              </label>
            </div>
            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Description</div>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                rows={2} className="w-full border border-slate-200 rounded px-2 py-1 text-xs" />
            </label>

            <fieldset>
              <legend className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Business Arrangement</legend>
              {(['owned','consignment','resell','dropship','digital'] as Arrangement[]).map(a => (
                <label key={a} className="flex items-center gap-2 py-1 cursor-pointer text-xs">
                  <input type="radio" name="arrangement" checked={form.arrangement === a}
                    onChange={() => setForm(f => ({ ...f, arrangement: a }))} />
                  <span className={`text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${ARRANGEMENT_BADGE[a].cls}`}>
                    {ARRANGEMENT_BADGE[a].label}
                  </span>
                </label>
              ))}
            </fieldset>

            {form.arrangement === 'consignment' && (
              <div className="bg-amber-50/50 border border-amber-200 rounded p-2 text-xs">
                <div className="font-bold text-amber-800 mb-1">Consignment terms</div>
                <label className="flex items-center gap-2">
                  Inn commission %:
                  <input type="number" min={0} max={100} value={form.inn_commission_pct}
                    onChange={e => setForm(f => ({ ...f, inn_commission_pct: Number(e.target.value) }))}
                    className="border border-slate-200 rounded px-1 py-0.5 w-14" />
                  <span className="text-slate-500">
                    Artist gets {100 - form.inn_commission_pct}%
                  </span>
                </label>
              </div>
            )}

            {(form.arrangement === 'resell' || form.arrangement === 'dropship') && (
              <div className="bg-sage/5 border border-sage/30 rounded p-2 text-xs space-y-1">
                <div className="font-bold text-sage-dark mb-1">Vendor / Brand details</div>
                <input placeholder="Brand / vendor name" value={form.brand}
                  onChange={e => setForm(f => ({ ...f, brand: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-2 py-0.5" />
                <input placeholder="Sales contact email" value={form.contact_sales}
                  onChange={e => setForm(f => ({ ...f, contact_sales: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-2 py-0.5" />
                <input placeholder="Website" value={form.website}
                  onChange={e => setForm(f => ({ ...f, website: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-2 py-0.5" />
                <input placeholder="Lead time (e.g. 3-5 weeks)" value={form.lead_time}
                  onChange={e => setForm(f => ({ ...f, lead_time: e.target.value }))}
                  className="w-full border border-slate-200 rounded px-2 py-0.5" />
                <textarea placeholder="Ordering process / notes" value={form.ordering}
                  onChange={e => setForm(f => ({ ...f, ordering: e.target.value }))}
                  rows={2} className="w-full border border-slate-200 rounded px-2 py-0.5" />
              </div>
            )}

            <fieldset>
              <legend className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Fulfillment</legend>
              {(['in_person','ship_to_guest','drop_ship','digital'] as Fulfillment[]).map(f => (
                <label key={f} className="flex items-center gap-2 py-1 cursor-pointer text-xs">
                  <input type="radio" name="fulfillment" checked={form.fulfillment === f}
                    onChange={() => setForm(state => ({ ...state, fulfillment: f }))} />
                  <span>{FULFILLMENT_BADGE[f].icon} {FULFILLMENT_BADGE[f].label}</span>
                </label>
              ))}
            </fieldset>

            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">
                Default Margin {form.arrangement === 'consignment' ? '(set by commission)' : ''}
              </div>
              <input type="number" min={0} max={1} step={0.05} value={form.margin}
                disabled={form.arrangement === 'consignment'}
                onChange={e => setForm(f => ({ ...f, margin: Number(e.target.value) }))}
                className="border border-slate-200 rounded px-2 py-1 w-24 disabled:bg-slate-100" />
              <span className="text-xs text-slate-500 ml-2">{(form.margin * 100).toFixed(0)}%</span>
            </label>

            <label className="block">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Notes</div>
              <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                rows={2} className="w-full border border-slate-200 rounded px-2 py-1 text-xs" />
            </label>

            <div className="flex items-center justify-between pt-3 border-t border-slate-200">
              <button onClick={() => setStep('pick')} className="text-xs font-semibold text-slate-500 hover:text-navy">
                ← Back to templates
              </button>
              <div className="flex gap-2">
                <button onClick={onClose} className="text-xs text-slate-500 px-3 py-1.5">Cancel</button>
                <button onClick={submit} disabled={!form.name}
                  className="bg-navy text-white text-xs font-bold px-4 py-1.5 rounded-lg hover:bg-navy-dark disabled:opacity-40">
                  Create Category
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

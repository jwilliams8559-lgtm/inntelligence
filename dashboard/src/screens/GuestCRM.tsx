import { useCallback, useEffect, useMemo, useState } from 'react'
import { format, parseISO } from 'date-fns'
import type { Tenant, Property } from '../lib/types'

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
    <div className="flex flex-col h-full overflow-hidden bg-cream">
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

      {/* Body — guest list + drawer */}
      <div className="flex flex-1 overflow-hidden">
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

      <div className="px-4 py-1 text-[10px] text-slate-400 bg-white border-t border-slate-100">
        Tenant: {tenant.slug} · property_id: {property.id.slice(0, 8)}…
      </div>
    </div>
  )
}

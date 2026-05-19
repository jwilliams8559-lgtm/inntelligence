import { useEffect, useMemo, useState } from 'react'
import type { Tenant, Property } from '../lib/types'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface EventRow {
  id: string; name: string; date: string; end_date: string
  days_away: number; duration_days: number; month: string; month_num: number
  pricing_nudge_pct: number; projected_occupancy_pct: number
  projected_nightly_rev: number; projected_event_total_rev: number
  source: string; category: string
  action_plan: string
  rate_status: 'premium_applied' | 'needs_attention' | 'not_yet_set'
  urgency: 'immediate' | 'upcoming' | 'planning' | 'horizon'
}

type UrgencyFilter = 'all' | 'immediate' | 'upcoming' | 'planning' | 'horizon'

const URGENCY_META = {
  all:       { label: 'All Events',                  icon: '📅' },
  immediate: { label: 'Immediate (next 21 days)',    icon: '⚡' },
  upcoming:  { label: 'Upcoming (22-60 days)',        icon: '📅' },
  planning:  { label: 'Planning (61-180 days)',       icon: '📆' },
  horizon:   { label: 'Horizon (180+ days)',          icon: '🔭' },
} as const

const CATEGORY_COLORS: Record<string, string> = {
  Festival:           'bg-gold/15 text-gold-dark',
  'Military/Academic':'bg-navy/15 text-navy',
  Community:          'bg-sage/15 text-sage-dark',
  Holiday:            'bg-coral/15 text-coral',
  Event:              'bg-slate-100 text-slate-600',
}

const RATE_STATUS = {
  premium_applied:  { label: '✓ Premium Applied',  cls: 'bg-sage text-white' },
  needs_attention:  { label: '⚡ Needs Attention', cls: 'bg-amber-100 text-amber-700' },
  not_yet_set:      { label: 'Not Yet Set',         cls: 'bg-slate-100 text-slate-500' },
} as const

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export default function EventsScreen({ }: Props) {
  const [events,        setEvents]     = useState<EventRow[]>([])
  const [loading,       setLoading]    = useState(true)
  const [urgency,       setUrgency]    = useState<UrgencyFilter>('all')
  const [scrollMonth,   setScrollMonth]= useState<number | null>(null)
  const [sourcesOpen,   setSourcesOpen]= useState(false)
  const [addOpen,       setAddOpen]    = useState(false)

  useEffect(() => {
    fetch('/api/events/intelligence').then(r => r.json()).then(d => {
      setEvents(Array.isArray(d) ? d : [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const filtered = useMemo(
    () => urgency === 'all' ? events : events.filter(e => e.urgency === urgency),
    [events, urgency],
  )

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: events.length, immediate: 0, upcoming: 0, planning: 0, horizon: 0 }
    events.forEach(e => { c[e.urgency] = (c[e.urgency] || 0) + 1 })
    return c
  }, [events])

  const summary = useMemo(() => {
    const next7  = events.filter(e => 0 <= e.days_away && e.days_away <= 7)
    const next30 = events.filter(e => 0 <= e.days_away && e.days_away <= 30)
    const byMonth: Record<string, number> = {}
    events.forEach(e => {
      const key = `${e.month}`
      byMonth[key] = (byMonth[key] || 0) + e.projected_event_total_rev
    })
    let peakMonth = '—'; let peakRev = 0
    Object.entries(byMonth).forEach(([m, r]) => { if (r > peakRev) { peakMonth = m; peakRev = r } })
    return {
      next7Count:  next7.length,
      next7Rev:    next7.reduce((s, e) => s + e.projected_event_total_rev, 0),
      next30Count: next30.length,
      next30Rev:   next30.reduce((s, e) => s + e.projected_event_total_rev, 0),
      peakMonth, peakRev,
    }
  }, [events])

  // Group filtered events by month for the body
  const byMonthGroups = useMemo(() => {
    const g: Record<number, EventRow[]> = {}
    filtered.forEach(e => {
      if (!g[e.month_num]) g[e.month_num] = []
      g[e.month_num].push(e)
    })
    return g
  }, [filtered])

  return (
    <div className="flex-1 overflow-y-auto bg-cream pb-20">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between mb-3 flex-wrap gap-2">
          <div>
            <h1 className="text-navy font-bold text-xl">Events &amp; Local Intelligence</h1>
            <p className="text-slate-500 text-xs mt-0.5">
              Festivals, fairs, graduations, and high-demand periods affecting your market
            </p>
            <div className="text-[11px] text-slate-400 mt-1 flex flex-wrap items-center gap-2">
              <span>Sources:</span>
              <span>🏛 City Visitors Bureau</span>
              <span>📡 Tourist Board RSS</span>
              <span>🎟 Eventbrite</span>
              <button onClick={() => setSourcesOpen(true)} className="text-navy underline ml-1">Configure</button>
            </div>
          </div>
          <button onClick={() => setAddOpen(true)}
            className="text-xs font-semibold bg-navy text-white px-3 py-1.5 rounded-lg hover:bg-navy-dark transition-colors">
            + Add Event Manually
          </button>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <SummaryCard label="Next 7 Days" count={summary.next7Count} rev={summary.next7Rev} accent="coral" />
          <SummaryCard label="Next 30 Days" count={summary.next30Count} rev={summary.next30Rev} accent="gold" />
          <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Peak Month</div>
            <div className="text-lg font-bold text-navy">{summary.peakMonth}</div>
            <div className="text-sage font-semibold text-sm">${summary.peakRev.toLocaleString()} projected event lift</div>
          </div>
        </div>

        {/* Urgency tabs */}
        <div className="flex items-center gap-1 mb-3 flex-wrap">
          {(['all', 'immediate', 'upcoming', 'planning', 'horizon'] as const).map(u => (
            <button key={u} onClick={() => setUrgency(u)}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-full transition-colors ${
                urgency === u ? 'bg-navy text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'}`}>
              <span className="mr-1">{URGENCY_META[u].icon}</span>{URGENCY_META[u].label}
              <span className="ml-1 opacity-60">{counts[u] ?? 0}</span>
            </button>
          ))}
        </div>

        {/* Month scroll bar */}
        <div className="flex items-center gap-1 mb-4 overflow-x-auto pb-1 text-xs">
          {MONTHS.map((m, i) => {
            const monthNum = i + 1
            const has = (byMonthGroups[monthNum] ?? []).length > 0
            const isCurrent = monthNum === new Date().getMonth() + 1
            return (
              <button key={m} onClick={() => setScrollMonth(monthNum)} disabled={!has}
                className={`px-2.5 py-1 rounded font-semibold whitespace-nowrap transition-colors ${
                  scrollMonth === monthNum ? 'bg-gold text-white'
                  : isCurrent ? 'bg-navy text-white'
                  : has ? 'bg-white border border-slate-200 hover:bg-slate-100 text-slate-600'
                  : 'bg-slate-100 text-slate-300'}`}>
                {m}
                {has && <span className="ml-1 opacity-60">{byMonthGroups[monthNum].length}</span>}
              </button>
            )
          })}
        </div>

        {/* Event cards grouped by month */}
        {loading ? (
          <div className="text-center text-slate-400 py-12">Loading events…</div>
        ) : filtered.length === 0 ? (
          <div className="text-center text-slate-400 py-12">No events match this filter.</div>
        ) : (
          <div className="space-y-4">
            {Object.entries(byMonthGroups)
              .sort(([a], [b]) => Number(a) - Number(b))
              .map(([monthNum, evs]) => (
                <div key={monthNum} id={`month-${monthNum}`}
                     className={scrollMonth === Number(monthNum) ? 'ring-2 ring-gold/30 rounded-xl p-1 -m-1 transition-all' : ''}>
                  <div className="text-[11px] uppercase tracking-wider font-bold text-slate-500 mb-2">
                    {MONTHS[Number(monthNum) - 1]} · {evs.length} event{evs.length > 1 ? 's' : ''}
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    {evs.map(e => <EventCard key={e.id} ev={e} />)}
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>

      {sourcesOpen && <SourcesModal onClose={() => setSourcesOpen(false)} />}
      {addOpen     && <AddEventModal onClose={() => setAddOpen(false)} />}
    </div>
  )
}

function SummaryCard({ label, count, rev, accent }:
  { label: string; count: number; rev: number; accent: 'coral' | 'gold' | 'sage' }) {
  const accentCls = accent === 'coral' ? 'text-coral' : accent === 'gold' ? 'text-gold' : 'text-sage'
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3">
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-2xl font-bold ${accentCls}`}>{count}</div>
      <div className="text-xs text-slate-500">events · ${rev.toLocaleString()} projected</div>
    </div>
  )
}

function EventCard({ ev }: { ev: EventRow }) {
  const cat = CATEGORY_COLORS[ev.category] ?? CATEGORY_COLORS.Event
  const status = RATE_STATUS[ev.rate_status]
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded ${cat}`}>
          {ev.category}
        </span>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${status.cls}`}>
          {status.label}
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-xs text-slate-500">📅</span>
        <span className="text-sm font-bold text-navy">{new Date(ev.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
        <span className="ml-auto text-[11px] font-semibold text-gold bg-gold/10 px-2 py-0.5 rounded-full">
          {ev.days_away <= 0 ? 'NOW' : `${ev.days_away}d away`}
        </span>
      </div>
      <h3 className="font-bold text-navy text-base mt-1">{ev.name}</h3>
      <div className="text-[11px] text-slate-500 mt-0.5">
        Duration: {ev.duration_days} {ev.duration_days === 1 ? 'day' : 'days'} · Source: {ev.source}
      </div>

      <div className="bg-cream rounded-lg p-2.5 mt-3">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Revenue Impact</div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-slate-500 text-[10px]">Pricing premium</div>
            <div className="font-bold text-sage">+{ev.pricing_nudge_pct}%</div>
          </div>
          <div>
            <div className="text-slate-500 text-[10px]">Projected occ</div>
            <div className="font-bold text-navy">{ev.projected_occupancy_pct.toFixed(0)}%</div>
          </div>
          <div>
            <div className="text-slate-500 text-[10px]">Nightly revenue</div>
            <div className="font-bold text-navy">${ev.projected_nightly_rev.toLocaleString()}</div>
          </div>
          <div>
            <div className="text-slate-500 text-[10px]">Event total</div>
            <div className="font-bold text-gold">${ev.projected_event_total_rev.toLocaleString()}</div>
          </div>
        </div>
      </div>

      <div className="mt-3 bg-navy/5 rounded-lg p-2.5 border-l-2 border-navy/30">
        <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-0.5">
          🎯 Action Plan
        </div>
        <div className="text-xs text-slate-700">{ev.action_plan}</div>
      </div>

      <div className="flex gap-1.5 mt-3">
        <button onClick={() => window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: 'calendar' }))}
          className="flex-1 text-[11px] font-semibold text-navy border border-navy/20 px-2 py-1.5 rounded-lg hover:bg-navy/5">
          View Rate Calendar
        </button>
        <button className="flex-1 text-[11px] font-bold bg-gold text-white px-2 py-1.5 rounded-lg hover:bg-gold-dark">
          Apply +{ev.pricing_nudge_pct}% Premium
        </button>
      </div>
    </div>
  )
}

function SourcesModal({ onClose }: { onClose: () => void }) {
  const sources = [
    { name: 'City Visitors Bureau', detail: 'Beaufort SC', enabled: true,  lastSync: 'today' },
    { name: 'Tourist Board RSS',    detail: 'South Carolina', enabled: true,  lastSync: 'today' },
    { name: 'Eventbrite API',       detail: 'Beaufort SC area', enabled: true,  lastSync: 'today' },
    { name: 'Google Events API',    detail: 'requires API key', enabled: false, lastSync: '—' },
    { name: 'Facebook Events',      detail: 'requires access token', enabled: false, lastSync: '—' },
    { name: 'Chamber of Commerce',  detail: 'Beaufort SC', enabled: false, lastSync: '—' },
    { name: 'Sports/Venue Calendar', detail: 'Parris Island, USCB', enabled: false, lastSync: '—' },
  ]
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-navy">Configure Event Sources</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">×</button>
        </div>
        <p className="text-xs text-slate-500 mb-3">
          Sources are city-agnostic — when a new property signs up in Asheville NC or Savannah GA,
          the system pulls events for THEIR city, not hardcoded Beaufort data.
        </p>
        <div className="space-y-2">
          {sources.map(s => (
            <div key={s.name} className="flex items-center gap-3 px-3 py-2 border border-slate-200 rounded-lg">
              <span className={s.enabled ? 'text-sage' : 'text-slate-300'}>{s.enabled ? '✓' : '○'}</span>
              <div className="flex-1">
                <div className="text-sm font-semibold text-navy">{s.name}</div>
                <div className="text-[10px] text-slate-500">{s.detail}</div>
              </div>
              <div className="text-[10px] text-slate-400">last sync: {s.lastSync}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function AddEventModal({ onClose }: { onClose: () => void }) {
  const [draft, setDraft] = useState({ name: '', date: '', nudge: 15, duration: 1 })
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-navy">Add Event Manually</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">×</button>
        </div>
        <div className="space-y-2 text-sm">
          <label className="block">
            <div className="text-xs text-slate-500 mb-1">Event name</div>
            <input value={draft.name} onChange={e => setDraft(d => ({ ...d, name: e.target.value }))}
              className="w-full border border-slate-200 rounded px-2 py-1" />
          </label>
          <label className="block">
            <div className="text-xs text-slate-500 mb-1">Date</div>
            <input type="date" value={draft.date} onChange={e => setDraft(d => ({ ...d, date: e.target.value }))}
              className="w-full border border-slate-200 rounded px-2 py-1" />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <div className="text-xs text-slate-500 mb-1">Duration (days)</div>
              <input type="number" min={1} max={14} value={draft.duration}
                onChange={e => setDraft(d => ({ ...d, duration: Number(e.target.value) }))}
                className="w-full border border-slate-200 rounded px-2 py-1" />
            </label>
            <label className="block">
              <div className="text-xs text-slate-500 mb-1">Pricing nudge (%)</div>
              <input type="number" min={0} max={50} value={draft.nudge}
                onChange={e => setDraft(d => ({ ...d, nudge: Number(e.target.value) }))}
                className="w-full border border-slate-200 rounded px-2 py-1" />
            </label>
          </div>
          <div className="text-[11px] text-slate-400 italic">
            Custom events are saved to this property and used in rate recommendations.
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 text-xs font-semibold text-slate-500 hover:text-navy">
            Cancel
          </button>
          <button onClick={onClose} className="px-3 py-1.5 text-xs font-bold bg-navy text-white rounded-lg">
            Add Event
          </button>
        </div>
      </div>
    </div>
  )
}

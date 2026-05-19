import { useEffect, useState, useCallback } from 'react'
import { format, addDays, parseISO, isWithinInterval } from 'date-fns'
import { supabase } from '../lib/supabase'
import type { RateRec, RoomType, CompRate, Tenant, Property } from '../lib/types'
import NetRevenuePanel from '../components/NetRevenuePanel'

interface Props {
  tenant: Tenant; property: Property
  pendingCount: number; setPendingCount: (n: number) => void
}

interface ToastMsg { id: number; kind: 'success' | 'error' | 'info'; text: string; onRetry?: () => void }

interface PublishLogRow {
  id: string
  channel_manager: string | null
  status: 'success' | 'partial' | 'failed' | null
  otas_updated: string[] | null
  response_body: any
  published_at: string | null
  error_message: string | null
}

const PUBLISH_MOCK = true  // Phase 5 demo flag — set false once OTA creds are live

const WF_START = new Date(new Date().getFullYear(), 6, 17)  // Jul 17
const WF_END   = new Date(new Date().getFullYear(), 6, 26)  // Jul 26

function isWaterFestival(d: Date) {
  return isWithinInterval(d, { start: WF_START, end: WF_END })
}

function demandColor(score: number | null): string {
  if (!score) return '#94A3B8'
  if (score >= 90) return '#1A6B3C'
  if (score >= 76) return '#2A8B4E'
  if (score >= 61) return '#A07830'
  if (score >= 41) return '#D97706'
  return '#C0392B'
}

function rateColor(rec: number | null, base: number | null) {
  if (!rec || !base) return 'text-slate-500'
  if (rec > base * 1.02) return 'text-navy'
  if (rec < base * 0.98) return 'text-coral'
  return 'text-slate-600'
}

function DemandGauge({ score }: { score: number }) {
  const R = 52, SW = 10
  const circ = Math.PI * R
  const pct  = Math.min(1, score / 100)
  const color = demandColor(score)
  const cx = 60, cy = 62

  return (
    <svg width="120" height="70" viewBox="0 0 120 70">
      <path d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`}
            fill="none" stroke="#E2E8F0" strokeWidth={SW} strokeLinecap="round" />
      <path d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`}
            fill="none" stroke={color} strokeWidth={SW} strokeLinecap="round"
            strokeDasharray={`${pct * circ} ${circ}`} />
      <text x={cx} y={cy - 6} textAnchor="middle" fontSize="22" fontWeight="700" fill={color}>{score}</text>
      <text x={cx} y={cy + 8} textAnchor="middle" fontSize="10" fill="#64748B">/ 100</text>
    </svg>
  )
}

function statusDot(status: string) {
  const map: Record<string, string> = {
    pending:       'bg-amber-400',
    approved:      'bg-sage',
    rejected:      'bg-coral',
    auto_published:'bg-blue-500',
    published:     'bg-blue-700',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${map[status] ?? 'bg-slate-300'}`} />
}

function computeOta(rate: number) {
  return {
    direct: Math.round(rate * 0.94 / 5) * 5,
    bookingCom: Math.round(rate * 0.85 / 5) * 5,
    expedia: Math.round(rate * 0.82 / 5) * 5,
    netOta: Math.round(rate * 0.85),
  }
}

const LOS_TABLE: Record<number, number> = { 1: 0, 2: 0.03, 3: 0.07, 4: 0.10, 5: 0.10 }

export default function RateCalendar({ tenant, property, pendingCount, setPendingCount }: Props) {
  const [recs,      setRecs]      = useState<RateRec[]>([])
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([])
  const [compRates, setCompRates] = useState<CompRate[]>([])
  const [selected,  setSelected]  = useState<RateRec | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [approving, setApproving] = useState(false)
  const [bulkProgress, setBulkProgress] = useState<{ total: number; running: boolean } | null>(null)
  const [toasts,    setToasts]    = useState<ToastMsg[]>([])
  const [drawerTab, setDrawerTab] = useState<'rate' | 'net' | 'history'>('rate')
  const [publishLog,  setPublishLog]  = useState<PublishLogRow[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const pushToast = useCallback((msg: Omit<ToastMsg, 'id'>) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, ...msg }])
    if (msg.kind !== 'error') {
      setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5000)
    }
  }, [])
  const dismissToast = (id: number) => setToasts(t => t.filter(x => x.id !== id))

  // Phase 8 — load alerts for top-of-calendar banner
  type AlertBanner = { id: string; alert_type: string; severity: string|null; message: string }
  const [alerts, setAlerts] = useState<AlertBanner[]>([])
  useEffect(() => {
    fetch(`/api/alerts/${property.id}?unread=true&limit=10`)
      .then(r => r.json()).then(j => setAlerts(Array.isArray(j) ? j : []))
      .catch(() => setAlerts([]))
  }, [property.id])
  const surgeAlerts   = alerts.filter(a => a.alert_type === 'surge')
  const lowOccAlerts  = alerts.filter(a => a.alert_type === 'low_occupancy')
  const festAlerts    = alerts.filter(a => a.alert_type === 'festival')

  const today    = new Date()
  // D1 — range selector. Default 90 days (matches "90-Day Outlook" title).
  type RangeKey = 7 | 14 | 30 | 90 | 'custom'
  const [rangeKey, setRangeKey] = useState<RangeKey>(90)
  const [customStart, setCustomStart] = useState<string>(format(addDays(today, 1), 'yyyy-MM-dd'))
  const [customEnd,   setCustomEnd]   = useState<string>(format(addDays(today, 30), 'yyyy-MM-dd'))
  const dates = (() => {
    if (rangeKey === 'custom') {
      const s = parseISO(customStart); const e = parseISO(customEnd)
      const n = Math.max(1, Math.min(180, Math.floor((e.getTime() - s.getTime()) / 86400000) + 1))
      return Array.from({ length: n }, (_, i) => addDays(s, i))
    }
    return Array.from({ length: rangeKey }, (_, i) => addDays(today, i + 1))
  })()

  useEffect(() => {
    async function load() {
      setLoading(true)
      const endDate = format(addDays(today, 91), 'yyyy-MM-dd')

      const [{ data: rt }, { data: rr }, { data: cr }] = await Promise.all([
        supabase.from('room_types')
          .select('id,name,base_rate,min_rate,max_rate,bathroom_type,bathroom_premium,total_count')
          .eq('property_id', property.id)
          .order('base_rate', { ascending: false }),

        supabase.from('rate_recommendations')
          .select('*')
          .eq('property_id', property.id)
          .eq('status', 'pending')
          .gte('target_date', format(today, 'yyyy-MM-dd'))
          .lte('target_date', endDate)
          .order('target_date'),

        supabase.from('competitor_rates')
          .select('id,competitor_id,rate_date,rate_amount,is_sold_out,competitor_properties(competitor_name,name)')
          .eq('property_id', property.id)
          .eq('is_stale', false)
          .gte('rate_date', format(today, 'yyyy-MM-dd'))
          .lte('rate_date', endDate),
      ])

      setRoomTypes(rt ?? [])
      setRecs(rr ?? [])
      setCompRates((cr ?? []) as any)
      setLoading(false)
    }
    load()
  }, [property.id])

  const cellMap = new Map<string, RateRec>()
  recs.forEach(r => cellMap.set(`${r.room_type_id}:${r.target_date}`, r))

  async function publishSingle(rec: RateRec) {
    setApproving(true)
    try {
      const r = await fetch('/api/approve-rate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ recommendation_id: rec.id, tenant_id: tenant.id, mock: PUBLISH_MOCK }),
      })
      const json = await r.json()
      if (r.ok && json.success) {
        const otas = (json.otas_updated as string[] | undefined) ?? []
        setRecs(prev => prev.map(x => x.id === rec.id
          ? { ...x, status: 'published', published_at: json.published_at }
          : x))
        setPendingCount(Math.max(0, pendingCount - 1))
        pushToast({
          kind: 'success',
          text: otas.length
            ? `Rate published to ${otas.join(', ')} ✓`
            : 'Rate published ✓',
        })
        // Refresh the publish history tab if it's open on this cell
        if (drawerTab === 'history') void loadPublishLog(rec.id)
      } else {
        const err = (json.errors as string[] | undefined)?.[0] ?? json.error ?? 'Publish failed'
        setRecs(prev => prev.map(x => x.id === rec.id ? { ...x, status: 'publish_failed' } : x))
        pushToast({
          kind: 'error', text: `Publish failed: ${err}`,
          onRetry: () => publishSingle(rec),
        })
      }
    } catch (exc: any) {
      pushToast({
        kind: 'error', text: `Network error: ${exc?.message ?? exc}`,
        onRetry: () => publishSingle(rec),
      })
    } finally {
      setApproving(false)
    }
  }

  async function reject(id: string) {
    setApproving(true)
    await supabase.from('rate_recommendations').update({ status: 'rejected' }).eq('id', id)
    setRecs(prev => prev.map(r => r.id === id ? { ...r, status: 'rejected' } : r))
    setPendingCount(Math.max(0, pendingCount - 1))
    setSelected(null)
    setApproving(false)
  }

  const approveAll = useCallback(async () => {
    setBulkProgress({ total: pendingCount, running: true })
    try {
      const r = await fetch('/api/approve-all-rates', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          property_id: property.id, tenant_id: tenant.id, mock: PUBLISH_MOCK,
        }),
      })
      const json = await r.json()
      const published = json.published ?? 0
      const failed    = json.failed    ?? 0
      const total     = json.total     ?? 0
      // Refresh recs from DB to pick up new statuses
      const { data: rr } = await supabase.from('rate_recommendations')
        .select('*')
        .eq('property_id', property.id)
        .order('target_date')
      setRecs(rr ?? [])
      setPendingCount((rr ?? []).filter(x => x.status === 'pending').length)
      if (failed === 0) {
        pushToast({ kind: 'success', text: `${published} rates published ✓` })
      } else {
        pushToast({
          kind: 'error',
          text: `${published} published ✓ | ${failed} failed — review log`,
        })
      }
      console.info('approve-all summary', json)
      void total
    } catch (exc: any) {
      pushToast({ kind: 'error', text: `Bulk publish error: ${exc?.message ?? exc}` })
    } finally {
      setBulkProgress(null)
    }
  }, [property.id, tenant.id, pendingCount, pushToast])

  const loadPublishLog = useCallback(async (recId: string) => {
    setHistoryLoading(true)
    try {
      const r = await fetch(`/api/publish-log/${property.id}?recommendation_id=${recId}&limit=5`)
      const json = await r.json()
      setPublishLog(Array.isArray(json) ? json : [])
    } catch {
      setPublishLog([])
    } finally {
      setHistoryLoading(false)
    }
  }, [property.id])

  useEffect(() => {
    setDrawerTab('rate')
    setPublishLog([])
  }, [selected?.id])

  useEffect(() => {
    if (drawerTab === 'history' && selected) void loadPublishLog(selected.id)
  }, [drawerTab, selected, loadPublishLog])

  const selectedRoom = roomTypes.find(rt => rt.id === selected?.room_type_id)
  const selectedDate = selected?.target_date
  const compForDate  = selectedDate
    ? compRates.filter(c => c.rate_date === selectedDate)
    : []

  const drivers = selected?.reasoning
    ? selected.reasoning.split('. ').filter(Boolean).slice(0, 3)
    : []

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-navy border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Phase 8 alert banners — surge / low_occupancy / festival */}
      {surgeAlerts.map(a => (
        <div key={a.id} className="bg-gold/15 border-b border-gold/30 px-4 py-1.5 text-xs text-gold-dark font-semibold flex items-center gap-2 flex-shrink-0">
          <span>📈</span><span>{a.message}</span>
        </div>
      ))}
      {lowOccAlerts.map(a => (
        <div key={a.id} className="bg-coral/10 border-b border-coral/30 px-4 py-1.5 text-xs text-coral font-semibold flex items-center gap-2 flex-shrink-0">
          <span>📉</span><span>{a.message}</span>
        </div>
      ))}
      {festAlerts.map(a => (
        <div key={a.id} className="bg-gold/10 border-b border-gold/30 px-4 py-1.5 text-xs text-gold font-semibold flex items-center gap-2 flex-shrink-0">
          <span>★</span><span>{a.message}</span>
        </div>
      ))}

      {/* Water Festival Demo Banner — pulls peak rate from rate_recommendations */}
      {(() => {
        const wfRecs = recs.filter(r => {
          if (!r.target_date) return false
          const d = parseISO(r.target_date)
          return isWaterFestival(d) && r.recommended_rate != null
        })
        const peakRec = wfRecs.length
          ? wfRecs.reduce((max, r) => r.recommended_rate! > max.recommended_rate! ? r : max)
          : null
        const peakRoom = peakRec ? roomTypes.find(rt => rt.id === peakRec.room_type_id) : null
        return (
          <div
            onClick={() => peakRec && setSelected(peakRec)}
            className="bg-gold text-white px-4 py-2 flex items-center gap-3 shadow-md cursor-pointer hover:bg-gold-dark transition-colors flex-shrink-0"
          >
            <span className="text-lg">★</span>
            <div className="flex-1 min-w-0">
              <span className="font-bold">Water Festival Alert</span>
              <span className="mx-2 opacity-70">·</span>
              <span className="text-sm">Jul 17–26 · Peak Demand</span>
              {peakRec && peakRoom ? (
                <>
                  <span className="mx-2 opacity-70">|</span>
                  <span className="text-sm">{peakRoom.name}: ${peakRoom.base_rate.toFixed(0)} →</span>
                  <span className="font-bold ml-1">${peakRec.recommended_rate!.toFixed(0)}</span>
                  {(peakRec.minimum_stay_rec ?? 1) > 1 && (
                    <span className="ml-2 text-xs opacity-90">({peakRec.minimum_stay_rec}-night min)</span>
                  )}
                </>
              ) : null}
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); approveAll() }}
              disabled={approving || pendingCount === 0}
              className="bg-white text-gold font-bold text-xs px-3 py-1.5 rounded-lg hover:bg-gold-light hover:text-white transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              Approve All ({pendingCount})
            </button>
          </div>
        )
      })()}

      {/* Top bar — compact for iPad 1024px width */}
      <div className="bg-white border-b border-slate-200 px-4 py-2 flex items-center gap-3 flex-wrap">
        <h1 className="text-navy font-bold text-base whitespace-nowrap">Rate Calendar — 90-Day Outlook</h1>
        <span className="text-sm text-slate-500 whitespace-nowrap">
          {pendingCount > 0
            ? <><span className="text-amber-500 font-semibold">{pendingCount}</span> pending</>
            : <span className="text-sage font-medium">✓ All approved</span>
          }
        </span>

        {/* D1 — range selector */}
        <div className="flex items-center gap-1 ml-2">
          {([
            { val: 7  as const, lbl: '7 Days' },
            { val: 14 as const, lbl: '2 Weeks' },
            { val: 30 as const, lbl: '1 Month' },
            { val: 90 as const, lbl: '3 Months' },
            { val: 'custom' as const, lbl: 'Custom' },
          ]).map(r => (
            <button key={String(r.val)} onClick={() => setRangeKey(r.val)}
              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full transition-colors ${
                rangeKey === r.val
                  ? 'bg-navy text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
              {r.lbl}
            </button>
          ))}
          {rangeKey === 'custom' && (
            <>
              <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)}
                className="text-xs border border-slate-200 rounded px-1.5 py-0.5 ml-1" />
              <span className="text-slate-400 text-xs">→</span>
              <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)}
                className="text-xs border border-slate-200 rounded px-1.5 py-0.5" />
            </>
          )}
        </div>

        <div className="ml-auto flex items-center gap-3 text-xs text-slate-400 whitespace-nowrap">
          <span><span className="inline-block w-2 h-2 bg-amber-400 rounded-full mr-1" />Pending</span>
          <span><span className="inline-block w-2 h-2 bg-sage rounded-full mr-1" />Approved</span>
          <span className="text-gold font-semibold">★ Gold = Festival</span>
        </div>
      </div>

      {/* Grid area + optional drawer */}
      <div className="flex flex-1 overflow-hidden">
        {/* Calendar grid */}
        <div className="flex-1 overflow-auto scrollbar-thin">
          <table className="border-collapse" style={{ minWidth: `${dates.length * 88 + 160}px` }}>
            <thead className="sticky top-0 z-20 bg-white shadow-sm">
              <tr>
                <th className="sticky left-0 z-30 bg-navy text-white text-xs font-semibold px-3 py-2 w-36 min-w-36 text-left border-r border-navy-dark">
                  Room Type
                </th>
                {dates.map(d => {
                  const wf = isWaterFestival(d)
                  const dateStr = format(d, 'yyyy-MM-dd')
                  const isWeekend = [0, 6].includes(d.getDay())
                  return (
                    <th key={dateStr}
                        className={`text-xs font-medium px-1 py-1.5 w-20 min-w-20 border-r text-center ${
                          wf
                            ? 'bg-gold text-white border-gold-dark'
                            : isWeekend
                            ? 'bg-slate-50 text-navy border-slate-200'
                            : 'bg-white text-slate-600 border-slate-100'
                        }`}>
                      <div className="font-semibold">{format(d, 'MMM d')}</div>
                      <div className="opacity-70 text-[10px]">{format(d, 'EEE')}</div>
                      {wf && <div className="text-[9px] font-bold mt-0.5">FESTIVAL</div>}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {roomTypes.map((rt, ri) => (
                <tr key={rt.id} className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
                  <td className="sticky left-0 z-10 bg-inherit border-r border-b border-slate-200 px-3 py-2 w-36 min-w-36">
                    <div className="text-navy font-semibold text-xs leading-tight">{rt.name}</div>
                    <div className="text-slate-400 text-[10px]">Base ${rt.base_rate}</div>
                    {rt.bathroom_type && rt.bathroom_type !== 'shower_only' && (
                      <div className="text-gold text-[9px] font-medium mt-0.5 capitalize">
                        {rt.bathroom_type.replace(/_/g, ' ')}
                      </div>
                    )}
                  </td>
                  {dates.map(d => {
                    const dateStr = format(d, 'yyyy-MM-dd')
                    const rec = cellMap.get(`${rt.id}:${dateStr}`)
                    const wf  = isWaterFestival(d)

                    if (!rec || rec.recommended_rate == null) {
                      return (
                        <td key={dateStr}
                            className={`border-r border-b border-slate-100 w-20 min-w-20 ${wf ? 'bg-gold/10' : ''}`} />
                      )
                    }

                    const pct  = rec.demand_score ?? 0
                    const barW = `${pct}%`
                    const barC = demandColor(rec.demand_score)
                    const rateC = rateColor(rec.recommended_rate, rt.base_rate)

                    return (
                      <td key={dateStr}
                          onClick={() => setSelected(rec)}
                          className={`border-r border-b border-slate-100 w-20 min-w-20 cursor-pointer
                            transition-colors hover:bg-navy/5 relative
                            ${wf ? 'bg-gold/8' : ''} ${selected?.id === rec.id ? 'ring-2 ring-inset ring-navy' : ''}`}>
                        {/* Demand bar */}
                        <div className="absolute top-0 left-0 h-1 w-full bg-slate-100">
                          <div className="h-full transition-all" style={{ width: barW, background: barC }} />
                        </div>
                        <div className="pt-2 pb-1.5 px-1.5 text-center">
                          <div className={`font-bold text-sm leading-none ${rateC}`}>
                            ${rec.recommended_rate.toFixed(0)}
                          </div>
                          <div className="text-[10px] text-slate-400 mt-0.5">${rt.base_rate}</div>
                          <div className="flex items-center justify-center gap-1 mt-0.5">
                            {statusDot(rec.status)}
                            {(rec.minimum_stay_rec ?? 1) > 1 && (
                              <span className="text-[9px] bg-navy/10 text-navy px-1 rounded font-medium">
                                {rec.minimum_stay_rec}n
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right Drawer */}
        {selected && selectedRoom && (
          <div className="w-80 flex-shrink-0 bg-white border-l border-slate-200 flex flex-col shadow-xl overflow-y-auto scrollbar-thin">
            {/* Drawer header */}
            <div className="bg-navy px-4 py-3 flex items-start justify-between">
              <div>
                <div className="text-white font-bold text-sm">{selectedRoom.name}</div>
                <div className="text-white/70 text-xs mt-0.5">
                  {selected.target_date && format(parseISO(selected.target_date), 'EEEE, MMMM d, yyyy')}
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="text-white/50 hover:text-white text-xl leading-none">×</button>
            </div>

            {/* Drawer tabs */}
            <div className="flex border-b border-slate-200 bg-slate-50">
              {(['rate', 'net', 'history'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setDrawerTab(tab)}
                  className={`flex-1 py-2 text-[11px] font-semibold transition-colors ${
                    drawerTab === tab
                      ? 'bg-white text-navy border-b-2 border-navy'
                      : 'text-slate-500 hover:text-navy hover:bg-white/60'
                  }`}
                >
                  {tab === 'rate' ? 'Rate Detail' : tab === 'net' ? 'Net Revenue' : 'Publish History'}
                </button>
              ))}
            </div>

            {drawerTab === 'net' && selectedRoom && selected.recommended_rate != null && (
              <div className="flex-1 overflow-y-auto px-3 py-3">
                <NetRevenuePanel
                  rate={selected.recommended_rate}
                  roomName={selectedRoom.name}
                  roomCategory={
                    selectedRoom.name.toLowerCase().includes('waterfront') ? 'waterfront'
                    : selectedRoom.name.toLowerCase().includes('water')    ? 'waterview'
                    : selectedRoom.name.toLowerCase().includes('cottage')  ? 'cottage'
                    : 'garden'
                  }
                />
              </div>
            )}

            {drawerTab === 'history' && (
              <div className="flex-1 px-4 py-3">
                {historyLoading ? (
                  <div className="text-center text-slate-400 text-sm py-6">Loading…</div>
                ) : publishLog.length === 0 ? (
                  <div className="text-center text-slate-400 text-sm py-6">
                    No publish attempts yet for this date.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {publishLog.map(row => {
                      const ok   = row.status === 'success'
                      const part = row.status === 'partial'
                      const otas = row.otas_updated ?? []
                      return (
                        <div key={row.id} className="border border-slate-200 rounded-lg px-3 py-2">
                          <div className="flex items-center justify-between text-xs">
                            <span className={`font-semibold ${ok ? 'text-sage' : part ? 'text-gold' : 'text-coral'}`}>
                              {ok ? '✓ Success' : part ? '⚠ Partial' : '✗ Failed'}
                            </span>
                            <span className="text-slate-400">
                              {row.published_at ? format(parseISO(row.published_at), 'MMM d, h:mm a') : '—'}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 mt-1">
                            via {row.channel_manager ?? 'unknown'}
                          </div>
                          {otas.length > 0 && (
                            <div className="text-[11px] text-slate-700 mt-1">
                              OTAs: {otas.join(', ')}
                            </div>
                          )}
                          {row.error_message && (
                            <div className="text-[11px] text-coral mt-1 bg-coral/10 rounded px-2 py-1">
                              {row.error_message}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            <div className={`flex-1 px-4 py-3 space-y-4 ${drawerTab !== 'rate' ? 'hidden' : ''}`}>
              {/* Demand score */}
              <div className="text-center">
                <DemandGauge score={selected.demand_score ?? 0} />
                <div className="mt-1">
                  <span className="inline-block px-3 py-1 rounded-full text-xs font-bold text-white"
                        style={{ background: demandColor(selected.demand_score) }}>
                    {selected.demand_score ?? 0} — {
                      (selected.demand_score ?? 0) >= 90 ? 'Peak' :
                      (selected.demand_score ?? 0) >= 76 ? 'Very High' :
                      (selected.demand_score ?? 0) >= 61 ? 'High' :
                      (selected.demand_score ?? 0) >= 41 ? 'Normal' : 'Low'
                    }
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Confidence: {selected.confidence_score ?? 0}%
                </div>
              </div>

              {/* Rate summary */}
              <div className="bg-cream rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-navy">
                  ${selected.recommended_rate?.toFixed(0)}
                  <span className="text-sm font-normal text-slate-400 ml-1">/night</span>
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  Base ${selectedRoom.base_rate} →{' '}
                  <span className={selected.recommended_rate! > selectedRoom.base_rate ? 'text-sage font-semibold' : 'text-coral font-semibold'}>
                    {selected.recommended_rate! > selectedRoom.base_rate ? '+' : ''}
                    {(((selected.recommended_rate ?? 0) - selectedRoom.base_rate) / selectedRoom.base_rate * 100).toFixed(0)}%
                  </span>
                </div>
                {(selected.minimum_stay_rec ?? 1) > 1 && (
                  <div className="mt-1.5 inline-block bg-navy/10 text-navy text-xs font-semibold px-2 py-0.5 rounded">
                    {selected.minimum_stay_rec}-night minimum
                  </div>
                )}
              </div>

              {/* Bathroom */}
              {selectedRoom.bathroom_type && selectedRoom.bathroom_type !== 'shower_only' && (
                <div className="flex items-center gap-2 bg-gold/10 rounded-lg px-3 py-2">
                  <span className="text-base">🛁</span>
                  <div>
                    <div className="text-gold font-semibold text-xs capitalize">
                      {selectedRoom.bathroom_type.replace(/_/g, ' ')}
                    </div>
                    <div className="text-slate-500 text-[10px]">
                      +{((selectedRoom.bathroom_premium ?? 0) * 100).toFixed(0)}% bathroom premium applied
                    </div>
                  </div>
                </div>
              )}

              {/* Top drivers */}
              {drivers.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">Top Drivers</div>
                  <div className="space-y-1.5">
                    {drivers.map((d, i) => (
                      <div key={i} className="bg-navy/5 rounded px-2.5 py-1.5 text-xs text-slate-700 leading-snug">
                        {d.trim()}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Competitor rates */}
              {compForDate.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">Comp Set</div>
                  <div className="space-y-1">
                    {compForDate.map(c => {
                      const name = (c.competitor_properties as any)?.competitor_name
                        || (c.competitor_properties as any)?.name || 'Competitor'
                      return (
                        <div key={c.id} className="flex items-center justify-between text-xs">
                          <span className="text-slate-600 truncate max-w-[140px]">{name}</span>
                          <div className="flex items-center gap-1.5">
                            {c.is_sold_out
                              ? <span className="bg-coral/15 text-coral font-bold text-[10px] px-1.5 py-0.5 rounded">SOLD OUT</span>
                              : <span className="font-semibold text-slate-700">${c.rate_amount?.toFixed(0)}</span>
                            }
                          </div>
                        </div>
                      )
                    })}
                    {selected.recommended_rate && compForDate.filter(c => !c.is_sold_out).length > 0 && (() => {
                      const liveRates = compForDate.filter(c => !c.is_sold_out && c.rate_amount).map(c => c.rate_amount!)
                      const avg = liveRates.reduce((a, b) => a + b, 0) / liveRates.length
                      const pct = ((selected.recommended_rate - avg) / avg * 100).toFixed(0)
                      return (
                        <div className="border-t border-slate-100 pt-1 mt-1 flex justify-between text-xs font-semibold">
                          <span className="text-slate-500">vs Comp Avg</span>
                          <span className={Number(pct) >= 0 ? 'text-navy' : 'text-coral'}>
                            {Number(pct) >= 0 ? '+' : ''}{pct}% (${avg.toFixed(0)})
                          </span>
                        </div>
                      )
                    })()}
                  </div>
                </div>
              )}

              {/* OTA analysis */}
              {selected.recommended_rate && (
                <div>
                  <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">OTA Commission</div>
                  {(() => {
                    const ota = computeOta(selected.recommended_rate)
                    return (
                      <div className="bg-cream rounded-lg p-2.5 space-y-1 text-xs">
                        <div className="flex justify-between"><span className="text-slate-500">Listed (OTA/CM)</span><span className="font-semibold">${selected.recommended_rate.toFixed(0)}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">Booking.com equiv</span><span>${ota.bookingCom}</span></div>
                        <div className="flex justify-between"><span className="text-slate-500">Expedia equiv</span><span>${ota.expedia}</span></div>
                        <div className="flex justify-between border-t border-slate-200 pt-1 mt-1">
                          <span className="text-sage font-semibold">Recommend direct</span>
                          <span className="text-sage font-bold">${ota.direct}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-400">Net via OTA</span>
                          <span className="text-slate-600">${ota.netOta}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sage font-semibold">Direct uplift</span>
                          <span className="text-sage font-bold">+${ota.direct - ota.netOta}</span>
                        </div>
                      </div>
                    )
                  })()}
                </div>
              )}

              {/* LOS table */}
              {selected.recommended_rate && (
                <div>
                  <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">Length of Stay</div>
                  <div className="rounded-lg overflow-hidden border border-slate-200">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="px-2 py-1.5 text-left text-slate-500">Nights</th>
                          <th className="px-2 py-1.5 text-right text-slate-500">Rate</th>
                          <th className="px-2 py-1.5 text-right text-slate-500">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(LOS_TABLE).map(([n, disc]) => {
                          const nights  = Number(n)
                          const nightly = Math.max(
                            selectedRoom.min_rate,
                            Math.round(selected.recommended_rate! * (1 - disc) / 5) * 5
                          )
                          return (
                            <tr key={n} className="border-t border-slate-100">
                              <td className="px-2 py-1.5 text-slate-700 font-medium">
                                {nights}n {disc > 0 && <span className="text-sage text-[10px]">-{disc * 100}%</span>}
                              </td>
                              <td className="px-2 py-1.5 text-right font-semibold text-navy">${nightly}</td>
                              <td className="px-2 py-1.5 text-right text-slate-500">${nightly * nights}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Approve / Reject — disabled once published */}
            <div className="sticky bottom-0 bg-white border-t border-slate-200 px-4 py-3 flex gap-2">
              {selected.status === 'published' ? (
                <div className="flex-1 text-center text-xs text-sage font-semibold py-2">
                  ✓ Published{selected.published_at ? ` ${format(parseISO(selected.published_at), 'MMM d, h:mm a')}` : ''}
                </div>
              ) : (
                <>
                  <button
                    onClick={() => reject(selected.id)}
                    disabled={approving || selected.status !== 'pending'}
                    className="flex-1 py-2 rounded-lg border border-coral text-coral text-sm font-semibold hover:bg-coral/5 disabled:opacity-40 transition-colors"
                  >Reject</button>
                  <button
                    onClick={() => publishSingle(selected)}
                    disabled={approving}
                    className="flex-1 py-2 rounded-lg bg-sage text-white text-sm font-semibold hover:bg-sage-dark disabled:opacity-40 transition-colors"
                  >{approving ? 'Publishing…' : '✓ Approve & Publish'}</button>
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Toast notifications (Phase 5 publish flow) */}
      {toasts.length > 0 && (
        <div className="fixed top-4 right-4 z-50 space-y-2 max-w-md">
          {toasts.map(t => (
            <div key={t.id}
                 className={`shadow-lg rounded-lg px-4 py-3 flex items-start gap-3 text-sm border-l-4 ${
                   t.kind === 'success' ? 'bg-sage/10 border-sage text-sage-dark' :
                   t.kind === 'error'   ? 'bg-coral/10 border-coral text-coral' :
                                          'bg-navy/10 border-navy text-navy'
                 }`}>
              <div className="flex-1">{t.text}</div>
              {t.kind === 'error' && t.onRetry && (
                <button onClick={() => { t.onRetry?.(); dismissToast(t.id) }}
                        className="text-xs font-semibold underline hover:no-underline">
                  Retry
                </button>
              )}
              <button onClick={() => dismissToast(t.id)} className="text-slate-400 hover:text-slate-700">×</button>
            </div>
          ))}
        </div>
      )}

      {/* Bulk publish progress (Approve All) */}
      {bulkProgress?.running && (
        <div className="fixed inset-0 z-40 bg-navy/40 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-2xl px-6 py-5 w-80 text-center">
            <div className="text-navy font-bold mb-2">
              Publishing {bulkProgress.total} rates…
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-sage animate-pulse" style={{ width: '80%' }} />
            </div>
            <div className="text-xs text-slate-500 mt-2">
              Pushing to channel manager — this may take a few seconds.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

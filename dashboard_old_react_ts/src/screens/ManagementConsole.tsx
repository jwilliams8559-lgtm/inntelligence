import { useEffect, useState } from 'react'
import { format, parseISO } from 'date-fns'
import type { Tenant, Property } from '../lib/types'
import OnboardingWizard from './OnboardingWizard'

interface Props {
  tenant: Tenant; property: Property
  pendingCount: number; setPendingCount: (n: number) => void
}

interface PortfolioRow {
  property_id: string; tenant_id: string
  name: string; location: string
  ytd_occupancy: number | null; ytd_adr: number | null
  month_occupancy: number | null; month_occupancy_ly: number | null
  delta_occ_pct: number | null
  month_revpar: number | null; month_revpar_ly: number | null
  delta_revpar_pct: number | null
  pending_count: number
  autopilot_enabled_rooms: number
  pms_type: string | null; pms_last_sync_at: string | null
  channel_manager_type: string | null
  plan_tier: string; mrr: number
}

interface RevenueData {
  mrr_total: number; arr_total: number
  mom_growth_pct: number; paying_clients: number
  founding_members: number; founding_member_target: string
  advisory_pipeline_value: number
  trend: { label: string; starter: number; professional: number; enterprise: number }[]
  by_plan_current: Record<string, { mrr: number; clients: number; price: number }>
}

interface MarketIntel {
  market: string; cells_used: number
  monthly: {
    month: number
    avg_occupancy: number | null; avg_adr: number | null
    event_lift: number | null
    bw_0_7: number | null; bw_8_30: number | null
    bw_31_60: number | null; bw_61_plus: number | null
  }[]
}

interface AcquisitionRow {
  market: string; market_name: string
  avg_occupancy: number | null; avg_adr: number | null
  tgc_properties: number; tgc_clients: number
  opportunity_score: number; status: string
}

interface FoundingMember {
  name: string; city: string | null; state: string | null
  start_date: string | null; months_elapsed: number | null
  data_quality_score: number | null; engagement_score: number | null
  testimonial_status: string | null; converted_to_paid: boolean | null
  is_slot?: boolean
}

interface AdvisoryData {
  engagements: any[]; prompt: string
}

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function pct(value: number | null, decimals = 1): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(decimals)}%`
}

function deltaArrow(value: number | null): { label: string; cls: string } {
  if (value == null) return { label: '—', cls: 'text-slate-400' }
  if (value > 0)  return { label: `▲ ${value.toFixed(1)}%`, cls: 'text-sage font-semibold' }
  if (value < 0)  return { label: `▼ ${Math.abs(value).toFixed(1)}%`, cls: 'text-coral font-semibold' }
  return { label: 'flat', cls: 'text-slate-500' }
}


interface AdminTenant {
  tenant_id: string; inn_name: string; city: string; state: string
  plan_tier: string; total_rooms: number
  pms_id: string | null; pms_connected: boolean
  competitors: any[]
  status: string; founding_member: boolean
  created_at: string; first_login_at: string | null
  room_types?: any[]
  owner_first_name: string; owner_last_name: string; owner_email: string
}

export default function ManagementConsole({ }: Props) {
  const [wizardOpen, setWizardOpen] = useState(false)
  const [adminTenants, setAdminTenants] = useState<AdminTenant[]>([])
  const [credModal, setCredModal] = useState<{ tenant: AdminTenant; password: string } | null>(null)
  const [portfolio, setPortfolio] = useState<{ properties: PortfolioRow[]; total_mrr: number } | null>(null)
  const [revenue,   setRevenue]   = useState<RevenueData | null>(null)
  const [intel,     setIntel]     = useState<MarketIntel | null>(null)
  const [acq,       setAcq]       = useState<{ markets: AcquisitionRow[] } | null>(null)
  const [founding,  setFounding]  = useState<{ members: FoundingMember[]; target: string } | null>(null)
  const [advisory,  setAdvisory]  = useState<AdvisoryData | null>(null)
  const [loading,   setLoading]   = useState(true)

  async function reloadAdminTenants() {
    try {
      const j = await fetch('/api/admin/tenants').then(r => r.json())
      setAdminTenants(j.tenants || [])
    } catch { setAdminTenants([]) }
  }

  useEffect(() => {
    async function loadAll() {
      const [p, r, i, a, f, ad] = await Promise.all([
        fetch('/api/management/portfolio').then(r => r.json()).catch(() => null),
        fetch('/api/management/revenue').then(r => r.json()).catch(() => null),
        fetch('/api/management/market-intel?market=beaufort-sc-lowcountry').then(r => r.json()).catch(() => null),
        fetch('/api/management/acquisition-signals').then(r => r.json()).catch(() => null),
        fetch('/api/management/founding-members').then(r => r.json()).catch(() => null),
        fetch('/api/management/advisory').then(r => r.json()).catch(() => null),
      ])
      setPortfolio(p); setRevenue(r); setIntel(i); setAcq(a); setFounding(f); setAdvisory(ad)
      await reloadAdminTenants()
      setLoading(false)
    }
    void loadAll()
  }, [])

  async function sendCredentials(t: AdminTenant) {
    const r = await fetch(`/api/admin/tenant/${t.tenant_id}/regenerate-password`, { method: 'POST' })
    const j = await r.json()
    if (j.temp_password) setCredModal({ tenant: t, password: j.temp_password })
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center bg-cream">
      <div className="w-8 h-8 border-4 border-navy border-t-transparent rounded-full animate-spin" />
    </div>
  )

  // Trend bar chart max
  const trendMax = revenue
    ? Math.max(1, ...revenue.trend.map(t => t.starter + t.professional + t.enterprise))
    : 1
  // Market intel max for chart scaling
  const occMax = intel ? Math.max(0.01, ...intel.monthly.map(m => m.avg_occupancy ?? 0)) : 1
  const adrMax = intel ? Math.max(1,    ...intel.monthly.map(m => m.avg_adr       ?? 0)) : 1

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[3px] text-gold font-bold">Management Console</div>
          <h1 className="text-navy font-bold text-2xl">INNtelligence — Management Console</h1>
          <div className="text-sm text-slate-500">Strategic command center · {new Date().toLocaleDateString()}</div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={() => setWizardOpen(true)}
            className="bg-gold text-white text-sm font-bold px-4 py-2 rounded hover:bg-gold-dark shadow-md">
            + Onboard New Property
          </button>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">Active Properties</div>
          <div className="text-3xl font-bold text-navy">{portfolio?.properties.length ?? 0}</div>
        </div>
        </div>
      </div>

      {/* SECTION 1 — Portfolio Overview */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
          <h2 className="font-bold text-navy">Portfolio Overview</h2>
          <span className="text-xs text-slate-400">· {portfolio?.properties.length ?? 0} properties</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left">Property</th>
                <th className="px-2 py-2 text-left">Location</th>
                <th className="px-2 py-2 text-right">This Mo Occ vs LY</th>
                <th className="px-2 py-2 text-right">RevPAR vs LY</th>
                <th className="px-2 py-2 text-right">Pending</th>
                <th className="px-2 py-2 text-center">Autopilot</th>
                <th className="px-2 py-2 text-left">Last Sync</th>
                <th className="px-2 py-2 text-left">Plan</th>
                <th className="px-2 py-2 text-right">MRR</th>
              </tr>
            </thead>
            <tbody>
              {portfolio?.properties.map(p => {
                const outperform = (p.delta_occ_pct ?? 0) > 0 || (p.delta_revpar_pct ?? 0) > 0
                const underperform = (p.delta_occ_pct ?? 0) < 0 && (p.delta_revpar_pct ?? 0) < 0
                const rowCls = outperform
                  ? 'bg-sage/5 hover:bg-sage/10'
                  : underperform ? 'bg-coral/5 hover:bg-coral/10'
                                  : 'bg-white hover:bg-slate-50'
                const dOcc = deltaArrow(p.delta_occ_pct)
                const dRev = deltaArrow(p.delta_revpar_pct)
                return (
                  <tr key={p.property_id} className={`${rowCls} border-b border-slate-100 cursor-pointer`}>
                    <td className="px-4 py-2.5">
                      <div className="font-semibold text-navy">{p.name}</div>
                      <div className="text-[10px] text-slate-400">
                        YTD occ {pct(p.ytd_occupancy)} · ADR ${p.ytd_adr?.toFixed(0) ?? '—'}
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-xs text-slate-600">{p.location}</td>
                    <td className="px-2 py-2.5 text-right text-xs">
                      <div>{pct(p.month_occupancy)}</div>
                      <div className={`text-[10px] ${dOcc.cls}`}>{dOcc.label}</div>
                    </td>
                    <td className="px-2 py-2.5 text-right text-xs">
                      <div>${p.month_revpar?.toFixed(0) ?? '—'}</div>
                      <div className={`text-[10px] ${dRev.cls}`}>{dRev.label}</div>
                    </td>
                    <td className="px-2 py-2.5 text-right">
                      {p.pending_count > 0
                        ? <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-0.5 rounded">{p.pending_count}</span>
                        : <span className="text-slate-300 text-xs">0</span>}
                    </td>
                    <td className="px-2 py-2.5 text-center">
                      {p.autopilot_enabled_rooms > 0
                        ? <span className="text-sage font-bold text-xs">★ {p.autopilot_enabled_rooms}</span>
                        : <span className="text-slate-300 text-xs">—</span>}
                    </td>
                    <td className="px-2 py-2.5 text-xs text-slate-500">
                      {p.pms_last_sync_at ? format(parseISO(p.pms_last_sync_at), 'MMM d, h:mma') : '—'}
                    </td>
                    <td className="px-2 py-2.5">
                      <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded bg-gold/15 text-gold">
                        {p.plan_tier}
                      </span>
                    </td>
                    <td className="px-2 py-2.5 text-right font-semibold text-navy">
                      ${p.mrr}
                    </td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="bg-slate-50 font-bold">
                <td colSpan={8} className="px-4 py-2 text-right text-xs uppercase tracking-wider text-slate-500">Total MRR</td>
                <td className="px-2 py-2 text-right text-navy">${portfolio?.total_mrr ?? 0}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      {/* SECTION 2 — Revenue Dashboard */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-navy">INNtelligence Revenue</h2>
          <span className="text-xs text-slate-400">Honest framing — pre-revenue</span>
        </div>
        {/* E1 — pre-revenue MRR target callout */}
        <div className="bg-gold/5 border border-gold/30 rounded-lg px-3 py-2 mb-3 text-xs text-slate-700">
          <span className="font-semibold text-gold uppercase tracking-wider text-[10px] mr-2">Honest framing</span>
          Pre-revenue · Target: 3–5 founding members by Q3 2026 → <span className="font-bold text-navy">$7,200–$12,000 MRR</span>
        </div>
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div className="bg-cream rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-navy">${revenue?.mrr_total ?? 0}</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">MRR</div>
          </div>
          <div className="bg-cream rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-navy">${revenue?.arr_total ?? 0}</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">ARR</div>
          </div>
          <div className="bg-cream rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-navy">{revenue?.paying_clients ?? 0}</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Paying Clients</div>
          </div>
          <div className="bg-gold/10 rounded-lg p-3 text-center border border-gold/30">
            <div className="text-xl font-bold text-gold">{revenue?.founding_members ?? 0}</div>
            <div className="text-[10px] uppercase tracking-wider text-gold-dark font-semibold">Founding Members</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Target: {revenue?.founding_member_target}</div>
          </div>
        </div>

        {/* 6-month trend stacked bar */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">MRR Trend · last 6 months</div>
          <div className="flex items-end gap-1 h-32 bg-cream rounded-lg p-3">
            {revenue?.trend.map(t => {
              const total = t.starter + t.professional + t.enterprise
              const h = total / trendMax
              return (
                <div key={t.label} className="flex-1 flex flex-col items-center gap-1">
                  <div className="flex-1 w-full flex flex-col justify-end">
                    {total > 0 ? (
                      <>
                        {t.enterprise > 0 && <div style={{ height: `${(t.enterprise/trendMax)*100}%` }} className="bg-navy w-full rounded-t" />}
                        {t.professional > 0 && <div style={{ height: `${(t.professional/trendMax)*100}%` }} className="bg-gold w-full" />}
                        {t.starter > 0 && <div style={{ height: `${(t.starter/trendMax)*100}%` }} className="bg-sage w-full rounded-b" />}
                      </>
                    ) : (
                      <div className="bg-slate-100 w-full" style={{ height: '4px' }} />
                    )}
                  </div>
                  <div className="text-[9px] text-slate-400">{t.label}</div>
                </div>
              )
            })}
          </div>
          <div className="flex items-center gap-3 text-[10px] mt-2">
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-sage rounded"/>Starter ${revenue?.by_plan_current.starter.price}/mo</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-gold rounded"/>Professional ${revenue?.by_plan_current.professional.price}/mo</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-navy rounded"/>Enterprise ${revenue?.by_plan_current.enterprise.price}/mo</span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="bg-cream rounded-lg p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">MoM Growth</div>
            <div className="text-lg font-bold text-navy">{revenue?.mom_growth_pct ?? 0}%</div>
          </div>
          <div className="bg-cream rounded-lg p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Advisory Pipeline</div>
            <div className="text-lg font-bold text-navy">${revenue?.advisory_pipeline_value ?? 0}</div>
          </div>
        </div>
      </section>

      {/* SECTION 3 — Market Intelligence */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-navy">Market Intelligence · Beaufort SC Lowcountry</h2>
          <span className="text-xs text-slate-400">{intel?.cells_used ?? 0} federated signal cells</span>
        </div>

        {/* Occupancy trend */}
        <div className="mb-4">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Avg Occupancy by Month</div>
          <div className="flex items-end gap-1 h-20 bg-cream rounded-lg p-2">
            {intel?.monthly.map(m => (
              <div key={`o-${m.month}`} className="flex-1 flex flex-col items-center gap-1">
                <div className="flex-1 w-full flex flex-col justify-end">
                  <div
                    className="bg-navy w-full rounded-t"
                    style={{ height: `${((m.avg_occupancy ?? 0) / occMax) * 100}%`,
                              minHeight: m.avg_occupancy ? '4px' : '0' }}
                    title={`${MONTH_LABELS[m.month-1]}: ${pct(m.avg_occupancy)}`}
                  />
                </div>
                <div className="text-[9px] text-slate-400">{MONTH_LABELS[m.month-1]}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ADR trend */}
        <div className="mb-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Avg ADR by Month</div>
          <div className="flex items-end gap-1 h-20 bg-cream rounded-lg p-2">
            {intel?.monthly.map(m => (
              <div key={`a-${m.month}`} className="flex-1 flex flex-col items-center gap-1">
                <div className="flex-1 w-full flex flex-col justify-end">
                  <div
                    className="bg-gold w-full rounded-t"
                    style={{ height: `${((m.avg_adr ?? 0) / adrMax) * 100}%`,
                              minHeight: m.avg_adr ? '4px' : '0' }}
                    title={`${MONTH_LABELS[m.month-1]}: $${m.avg_adr?.toFixed(0) ?? '—'}`}
                  />
                </div>
                <div className="text-[9px] text-slate-400">{MONTH_LABELS[m.month-1]}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Booking window mix — peak season only */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Booking Window Mix · July (peak)</div>
          {(() => {
            const jul = intel?.monthly.find(m => m.month === 7)
            if (!jul || (jul.bw_0_7 ?? jul.bw_8_30 ?? jul.bw_31_60 ?? jul.bw_61_plus) == null) {
              return <div className="text-xs text-slate-400 italic">no July signals yet</div>
            }
            const segs = [
              { lbl: '0–7d',    val: jul.bw_0_7    ?? 0, color: '#1F3A5F' },
              { lbl: '8–30d',   val: jul.bw_8_30   ?? 0, color: '#B8973E' },
              { lbl: '31–60d',  val: jul.bw_31_60  ?? 0, color: '#7BA098' },
              { lbl: '61d+',    val: jul.bw_61_plus?? 0, color: '#94A3B8' },
            ]
            return (
              <div>
                <div className="flex h-4 rounded overflow-hidden">
                  {segs.map(s => (
                    <div key={s.lbl} style={{ width: `${s.val*100}%`, background: s.color }}
                          title={`${s.lbl}: ${pct(s.val)}`} />
                  ))}
                </div>
                <div className="flex items-center gap-3 mt-1.5 text-[10px]">
                  {segs.map(s => (
                    <span key={s.lbl} className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded" style={{ background: s.color }} />
                      {s.lbl} · {pct(s.val)}
                    </span>
                  ))}
                </div>
              </div>
            )
          })()}
        </div>
      </section>

      {/* SECTION 4 — Acquisition Intelligence */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2">
          <h2 className="font-bold text-navy">Acquisition Intelligence</h2>
          <span className="text-xs text-slate-400">· {acq?.markets.length ?? 0} markets watched</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left">Market</th>
              <th className="px-2 py-2 text-right">Avg Occupancy</th>
              <th className="px-2 py-2 text-right">Avg ADR</th>
              <th className="px-2 py-2 text-right">INN Properties</th>
              <th className="px-2 py-2 text-right">INN Clients</th>
              <th className="px-2 py-2 text-right">Opportunity</th>
              <th className="px-4 py-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {acq?.markets.map(m => {
              const statusCls = m.status.startsWith('Active') ? 'bg-sage/15 text-sage-dark'
                              : m.status.startsWith('High') ? 'bg-gold/15 text-gold-dark'
                                                              : 'bg-slate-100 text-slate-500'
              return (
                <tr key={m.market} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-semibold text-navy">{m.market_name}</td>
                  <td className="px-2 py-2.5 text-right text-xs">{pct(m.avg_occupancy)}</td>
                  <td className="px-2 py-2.5 text-right text-xs">${m.avg_adr?.toFixed(0) ?? '—'}</td>
                  <td className="px-2 py-2.5 text-right text-xs">{m.tgc_properties}</td>
                  <td className="px-2 py-2.5 text-right text-xs">{m.tgc_clients}</td>
                  <td className="px-2 py-2.5 text-right">
                    <span className="font-bold text-navy">{m.opportunity_score}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded ${statusCls}`}>
                      {m.status}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      {/* SECTION 5 — Founding Member Tracker */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-navy">Founding Member Tracker</h2>
          <span className="text-xs text-gold font-semibold">{founding?.target}</span>
        </div>
        <table className="w-full text-sm">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
            <tr>
              <th className="px-2 py-1.5 text-left">Name</th>
              <th className="px-2 py-1.5 text-left">City</th>
              <th className="px-2 py-1.5 text-left">Start Date</th>
              <th className="px-2 py-1.5 text-right">Months In</th>
              <th className="px-2 py-1.5 text-right">Data Quality</th>
              <th className="px-2 py-1.5 text-right">Engagement</th>
              <th className="px-2 py-1.5 text-left">Testimonial</th>
              <th className="px-2 py-1.5 text-center">Converted</th>
            </tr>
          </thead>
          <tbody>
            {founding?.members.map((m, i) => (
              <tr key={i} className={`border-b border-slate-100 ${m.is_slot ? 'bg-slate-50/50 italic text-slate-400' : ''}`}>
                <td className="px-2 py-2 font-semibold">{m.name}</td>
                <td className="px-2 py-2">{m.city ? `${m.city}, ${m.state}` : '—'}</td>
                <td className="px-2 py-2 text-xs">{m.start_date ? format(parseISO(m.start_date), 'MMM d, yyyy') : '—'}</td>
                <td className="px-2 py-2 text-right">{m.months_elapsed ?? '—'}</td>
                <td className="px-2 py-2 text-right">{m.data_quality_score ?? '—'}</td>
                <td className="px-2 py-2 text-right">{m.engagement_score ?? '—'}</td>
                <td className="px-2 py-2 text-xs">{m.testimonial_status ?? '—'}</td>
                <td className="px-2 py-2 text-center">
                  {m.converted_to_paid == null ? '—'
                    : m.converted_to_paid ? <span className="text-sage">✓</span>
                                            : <span className="text-slate-400">no</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* SECTION 6 — Advisory Tracker */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-bold text-navy">Advisory Engagements</h2>
          <button className="text-xs font-semibold bg-navy text-white px-3 py-1.5 rounded-lg hover:bg-navy-dark transition-colors">
            + New Advisory
          </button>
        </div>
        {(!advisory || advisory.engagements.length === 0) ? (
          <div className="text-center py-8 bg-cream rounded-lg">
            <div className="text-slate-400 text-sm mb-2">No active engagements yet</div>
            <div className="text-navy font-semibold text-sm">{advisory?.prompt ?? 'Start your first advisory conversation'}</div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-2 py-1.5 text-left">Client</th>
                <th className="px-2 py-1.5 text-left">Property</th>
                <th className="px-2 py-1.5 text-left">Start</th>
                <th className="px-2 py-1.5 text-right">Contract</th>
                <th className="px-2 py-1.5 text-left">Next Deliverable</th>
                <th className="px-2 py-1.5 text-left">Renewal</th>
              </tr>
            </thead>
            <tbody>
              {advisory.engagements.map((e: any, i: number) => (
                <tr key={i}><td>{JSON.stringify(e)}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* SECTION 7 — Provisioned Tenants (admin) */}
      <section className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-navy">Provisioned Tenants</h2>
            <div className="text-xs text-slate-400 mt-0.5">{adminTenants.length} accounts on the platform</div>
          </div>
          <button onClick={() => setWizardOpen(true)}
            className="text-xs font-bold text-navy hover:underline">+ Onboard New Property</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left">Property</th>
                <th className="px-2 py-2 text-left">Location</th>
                <th className="px-2 py-2 text-left">Plan</th>
                <th className="px-2 py-2 text-right">Rooms</th>
                <th className="px-2 py-2 text-left">PMS</th>
                <th className="px-2 py-2 text-right">Comps</th>
                <th className="px-2 py-2 text-left">Created</th>
                <th className="px-2 py-2 text-left">Status</th>
                <th className="px-2 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {adminTenants.length === 0 && (
                <tr><td colSpan={9} className="px-4 py-6 text-center text-slate-400 text-xs">
                  No tenants provisioned yet. Click <strong>+ Onboard New Property</strong> to add one.
                </td></tr>
              )}
              {adminTenants.map(t => (
                <tr key={t.tenant_id}>
                  <td className="px-4 py-2 font-semibold text-navy">{t.inn_name}</td>
                  <td className="px-2 py-2 text-slate-600">{t.city}{t.state ? `, ${t.state}` : ''}</td>
                  <td className="px-2 py-2 text-slate-600 capitalize">{t.plan_tier}</td>
                  <td className="px-2 py-2 text-right text-slate-600">{t.total_rooms}</td>
                  <td className="px-2 py-2 text-slate-600">{t.pms_id ? (t.pms_connected ? `✓ ${t.pms_id}` : t.pms_id) : <span className="text-slate-400">—</span>}</td>
                  <td className="px-2 py-2 text-right text-slate-600">{(t.competitors || []).length}</td>
                  <td className="px-2 py-2 text-slate-500">{format(parseISO(t.created_at), 'MMM d')}</td>
                  <td className="px-2 py-2">
                    {t.founding_member
                      ? <span className="text-[10px] uppercase font-bold bg-gold/20 text-gold-dark px-2 py-0.5 rounded-full">Founding Member</span>
                      : t.status === 'active'
                      ? <span className="text-[10px] uppercase font-bold bg-sage/20 text-sage-dark px-2 py-0.5 rounded-full">Active</span>
                      : <span className="text-[10px] uppercase font-bold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">Pending</span>}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex gap-2 text-[11px]">
                      <button className="text-navy hover:underline">View</button>
                      <button onClick={() => sendCredentials(t)} className="text-gold-dark hover:underline">Send Credentials</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-5 py-2 bg-slate-50 border-t border-slate-100 text-xs text-slate-500 flex items-center justify-between">
          <div className="flex gap-4">
            <span>{adminTenants.filter(t => t.status === 'active').length} active properties</span>
            <span>·</span>
            <span>${adminTenants.filter(t => !t.founding_member).reduce((s, t) => s + ({essentials:399,professional:699,portfolio:1199,enterprise:2400}[t.plan_tier as 'essentials']||0), 0).toLocaleString()} MRR</span>
            <span>·</span>
            <span>{adminTenants.filter(t => t.founding_member).length} founding members</span>
          </div>
          <button onClick={async () => {
            if (!confirm('Reset all demo data to factory defaults?')) return
            const r = await fetch('/api/demo/reset', { method: 'POST' })
            if (r.ok) window.location.reload()
            else alert('Reset failed — admin token required.')
          }} className="text-[11px] text-slate-400 hover:text-coral underline">
            Reset Demo Data
          </button>
        </div>
      </section>

      <div className="text-[10px] text-slate-400 text-center pb-3">
        INNtelligence by The Gracious Collection · Management Console
      </div>

      {/* Onboarding wizard modal */}
      <OnboardingWizard open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onProvisioned={() => { void reloadAdminTenants() }} />

      {/* Send-Credentials confirmation modal */}
      {credModal && (
        <div className="fixed inset-0 z-50 bg-navy/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
            <h3 className="font-bold text-navy text-lg">Credentials regenerated</h3>
            <p className="text-xs text-slate-500 mt-1">New temporary password for {credModal.tenant.inn_name}. Send these to {credModal.tenant.owner_email}.</p>
            <div className="bg-gold/5 border-2 border-gold rounded-lg p-3 mt-3 font-mono text-sm">
              <div><span className="text-slate-500">Email:</span> {credModal.tenant.owner_email}</div>
              <div><span className="text-slate-500">Password:</span> <strong>{credModal.password}</strong></div>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={() => {
                navigator.clipboard.writeText(`Email: ${credModal.tenant.owner_email}\nPassword: ${credModal.password}`)
              }} className="flex-1 bg-navy text-white text-xs font-bold py-2 rounded">Copy</button>
              <button onClick={() => setCredModal(null)} className="flex-1 bg-slate-100 text-navy text-xs font-bold py-2 rounded">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

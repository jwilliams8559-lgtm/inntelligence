import { useEffect, useState } from 'react'
import { formatDistanceToNow, parseISO } from 'date-fns'
import type { AppRole, Screen } from '../lib/types'
import { usePlanFeatures } from '../hooks/usePlanFeatures'
import HelpDrawer from './HelpDrawer'
import DemoWalkthrough from './DemoWalkthrough'

const NAV: { id: Screen; label: string; icon: string; adminOnly?: boolean }[] = [
  { id: 'calendar',    label: 'Rate Calendar',     icon: '📅' },
  { id: 'demand',      label: 'Demand Dashboard',  icon: '📊' },
  { id: 'events',      label: 'Events',            icon: '📅' },
  { id: 'competitive', label: 'Competitive Intel', icon: '🎯' },
  { id: 'crm',         label: 'Guest CRM',         icon: '👥' },
  { id: 'packages',    label: 'Packages',          icon: '🎁' },
  { id: 'management',  label: 'Management Console',icon: '🏛️', adminOnly: true },
  { id: 'settings',    label: 'Settings',          icon: '⚙️' },
]

interface Alert {
  id: string
  alert_type: string
  severity: 'info'|'warning'|'critical'|null
  message: string
  metadata: any
  created_at: string
}

const ALERT_ICON: Record<string, string> = {
  surge:               '📈',
  competitor_drop:     '⚠️',
  low_occupancy:       '📉',
  festival:            '★',
  gap_night:           '🌙',
  autopilot_published: '🤖',
}

interface Props {
  screen: Screen
  setScreen: (s: Screen) => void
  pendingCount: number
  propertyName: string
  propertyId: string
  appRole: AppRole
  children: React.ReactNode
}

export default function Layout({ screen, setScreen, pendingCount, propertyName, propertyId, appRole, children }: Props) {
  const [alerts,  setAlerts]  = useState<Alert[]>([])
  const [bellOpen, setBellOpen] = useState(false)

  const reloadAlerts = async () => {
    try {
      const r = await fetch(`/api/alerts/${propertyId}?unread=true&limit=20`)
      const j = await r.json()
      setAlerts(Array.isArray(j) ? j : [])
    } catch { /* ignore — endpoint may not be live yet */ }
  }

  useEffect(() => {
    reloadAlerts()
    const id = setInterval(reloadAlerts, 60_000)
    return () => clearInterval(id)
  }, [propertyId])

  async function dismiss(alertId: string) {
    await fetch('/api/dismiss-alert', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body:   JSON.stringify({ alert_id: alertId }),
    })
    setAlerts(prev => prev.filter(a => a.id !== alertId))
  }

  const criticalCount = alerts.filter(a => a.severity === 'critical').length
  const warningCount  = alerts.filter(a => a.severity === 'warning').length

  const [helpOpen,   setHelpOpen]   = useState(false)
  const [demoOpen,   setDemoOpen]   = useState(false)
  const isDemo = (import.meta.env.VITE_TENANT_SLUG ?? 'anchorage-1770-demo') === 'anchorage-1770-demo'
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-cream">
      {/* Demo Mode Banner — only when running the demo tenant */}
      {isDemo && (
        <div className="bg-gold text-white text-xs font-semibold tracking-wide py-1.5 px-4 shadow-sm flex-shrink-0 flex items-center justify-center gap-3">
          <span className="opacity-90">★ Demo Environment</span>
          <span className="opacity-50">·</span>
          <span>The Gracious Collection Rate Intelligence Center</span>
          <span className="opacity-50">·</span>
          <span>Anchorage 1770 Inn, Beaufort SC</span>
          <button
            onClick={() => setDemoOpen(true)}
            className="ml-3 bg-white/20 hover:bg-white/30 text-white px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide transition-colors"
          >
            Start Demo Walk-Through
          </button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-52 lg:w-56 flex-shrink-0 bg-navy flex flex-col shadow-xl">
        {/* Logo */}
        <div className="px-4 pt-6 pb-4 border-b border-navy-light">
          <div className="text-white font-bold text-sm leading-tight">The Gracious Collection</div>
          <div className="text-gold text-[10px] font-medium mt-0.5 leading-tight tracking-wide">Boutique Hospitality Intelligence</div>
          <div className="text-white/60 text-[10px] mt-1 leading-tight">
            Rate Intelligence Center
          </div>
        </div>

        {/* Property selector */}
        <div className="px-3 py-3 border-b border-navy-light">
          <div className="bg-navy-light rounded-lg px-3 py-2">
            <div className="text-gold text-xs font-medium uppercase tracking-wider mb-0.5">Property</div>
            <div className="text-white text-xs font-semibold truncate">{propertyName}</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV
            .filter(item => !item.adminOnly || appRole === 'shg_admin')
            .map(item => (
            <button
              key={item.id}
              onClick={() => setScreen(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-sm font-medium transition-all ${
                screen === item.id
                  ? 'bg-gold text-white shadow-md'
                  : item.adminOnly
                    ? 'text-gold/80 hover:bg-navy-light hover:text-gold'
                    : 'text-white/70 hover:bg-navy-light hover:text-white'
              }`}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
              {item.id === 'calendar' && pendingCount > 0 && (
                <span className="ml-auto bg-coral text-white text-xs font-bold rounded-full min-w-[20px] h-5 flex items-center justify-center px-1">
                  {pendingCount}
                </span>
              )}
              {item.adminOnly && (
                <span className="ml-auto text-[9px] uppercase tracking-wide bg-gold/20 text-gold px-1.5 py-0.5 rounded">TGC</span>
              )}
            </button>
          ))}
        </nav>

        {/* Section G — Monthly all-stream summary */}
        <SidebarMonthlySummary />

        {/* Help button */}
        <div className="px-3 pb-2">
          <button onClick={() => setHelpOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-white/70 hover:bg-navy-light hover:text-white transition-colors">
            <span>?</span>
            <span>Help &amp; Guides</span>
          </button>
        </div>

        {/* Bell / alerts */}
        <div className="px-3 pb-4 relative">
          <button
            onClick={() => setBellOpen(o => !o)}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors text-xs ${
              alerts.length > 0
                ? 'bg-gold/20 text-white hover:bg-gold/30'
                : 'bg-navy-light text-white/60 hover:bg-navy-light hover:text-white'
            }`}
          >
            <span className="relative">
              🔔
              {alerts.length > 0 && (
                <span className={`absolute -top-1 -right-1 text-[9px] font-bold rounded-full min-w-[14px] h-3.5 px-0.5 flex items-center justify-center ${
                  criticalCount > 0 ? 'bg-coral text-white' : 'bg-gold text-white'
                }`}>
                  {alerts.length}
                </span>
              )}
            </span>
            <span className="flex-1 text-left">
              {alerts.length > 0
                ? `${alerts.length} alert${alerts.length > 1 ? 's' : ''}${warningCount + criticalCount > 0 ? ` · ${warningCount + criticalCount} need review` : ''}`
                : `${pendingCount} pending`}
            </span>
          </button>

          {bellOpen && (
            <div className="absolute bottom-14 left-3 right-3 z-50 bg-white text-slate-700 rounded-lg shadow-2xl border border-slate-200 max-h-96 overflow-auto">
              <div className="sticky top-0 bg-white px-3 py-2 border-b border-slate-100 flex items-center justify-between">
                <span className="text-xs font-bold text-navy">Alerts</span>
                <button onClick={() => setBellOpen(false)} className="text-slate-400 hover:text-slate-700 text-sm leading-none">×</button>
              </div>
              {alerts.length === 0 ? (
                <div className="px-3 py-6 text-center text-xs text-slate-400">
                  No active alerts. ✓
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {alerts.map(a => {
                    const sev = a.severity ?? 'info'
                    const cls = sev === 'critical' ? 'border-l-coral bg-coral/5'
                              : sev === 'warning'  ? 'border-l-gold bg-gold/5'
                                                    : 'border-l-navy bg-navy/5'
                    return (
                      <div key={a.id} className={`px-3 py-2 border-l-4 ${cls} flex items-start gap-2`}>
                        <span className="text-base">{ALERT_ICON[a.alert_type] ?? '•'}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-slate-700 leading-snug">{a.message}</div>
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            {a.alert_type} · {formatDistanceToNow(parseISO(a.created_at), { addSuffix: true })}
                          </div>
                        </div>
                        <button onClick={() => dismiss(a.id)}
                          className="text-slate-300 hover:text-slate-700 text-xs leading-none">×</button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col min-w-0">
        {children}
      </main>
      </div>

      <HelpDrawer open={helpOpen} onClose={() => setHelpOpen(false)} />
      <DemoWalkthrough open={demoOpen} onClose={() => setDemoOpen(false)} />
    </div>
  )
}

// ── Section G: Sidebar Monthly Summary panel ──
// Renders all four revenue streams. Locked lines show "—" with a lock
// icon. The total is always shown — locked streams contribute $0 so the
// total reflects what's actually unlocked, while the visible row labels
// create a constant upgrade incentive.
function SidebarMonthlySummary() {
  const [data, setData] = useState({ rooms: 0, fb: 0, packages: 0, giftShop: 0, loading: true })

  useEffect(() => {
    Promise.all([
      fetch('/api/rates').then(r => r.json()).catch(() => []),
      fetch('/api/fb-summary').then(r => r.json()).catch(() => null),
      fetch('/api/packages').then(r => r.json()).catch(() => []),
      fetch('/api/gift-shop').then(r => r.json()).catch(() => []),
    ]).then(([rooms, fb, pkgs, shop]: any[]) => {
      const avgRate = rooms.length ? Math.round(rooms.reduce((s: number, r: any) => s + r.price, 0) / rooms.length) : 0
      // Anchorage 1770 has 14 rooms per ACTIVE_PROPERTY
      const totalRooms = 14
      const roomRev = Math.round(avgRate * totalRooms * 0.75 * 30)
      const fbRev   = fb?.total ?? 0
      const pkgRev  = Array.isArray(pkgs) ? pkgs.filter((p: any) => p.active).reduce((s: number, p: any) => s + (p.est_monthly_rev || 0), 0) : 0
      const shopRev = Array.isArray(shop) ? shop.reduce((s: number, c: any) => s + (c.est_monthly_rev || 0), 0) : 0
      setData({ rooms: roomRev, fb: fbRev, packages: pkgRev, giftShop: shopRev, loading: false })
    })
  }, [])

  const { features } = usePlanFeaturesSafe()
  const f = features
  const locks = {
    fb:       !f.fb_module,
    packages: !f.packages_module,
    giftShop: !f.gift_shop_module,
  }
  const visibleTotal = data.rooms
    + (locks.fb       ? 0 : data.fb)
    + (locks.packages ? 0 : data.packages)
    + (locks.giftShop ? 0 : data.giftShop)

  function Line({ label, value, locked }: { label: string; value: number; locked: boolean }) {
    return (
      <div className="flex justify-between items-baseline">
        <span className="text-white/60">{label}</span>
        <span className={locked ? 'text-white/30' : 'text-gold font-semibold'}>
          {locked ? '🔒 —' : `$${value.toLocaleString()}`}
        </span>
      </div>
    )
  }

  return (
    <div className="mx-3 mb-3 p-3 rounded-lg bg-navy-light/40 border border-navy-light">
      <div className="text-[9px] uppercase tracking-[2px] text-gold font-bold mb-2">Monthly (proj.)</div>
      {data.loading ? (
        <div className="text-[11px] text-white/40">Loading…</div>
      ) : (
        <div className="space-y-1 text-[11px]">
          <Line label="Rooms"      value={data.rooms}    locked={false} />
          <Line label="F&B"         value={data.fb}       locked={locks.fb} />
          <Line label="Packages"   value={data.packages} locked={locks.packages} />
          <Line label="Gift Shop"  value={data.giftShop} locked={locks.giftShop} />
          <div className="border-t border-white/10 pt-1 mt-1 flex justify-between items-baseline">
            <span className="text-white/80 font-semibold">TOTAL</span>
            <span className="text-gold font-bold text-sm">${visibleTotal.toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  )
}

// Safe wrapper — usePlanFeatures may not be ready before the provider mounts
// (Layout is rendered inside the provider, so this should always succeed,
// but keep a fallback for defensive cases).
function usePlanFeaturesSafe() {
  try {
    return usePlanFeatures()
  } catch {
    return {
      features: { fb_module: true, packages_module: true, gift_shop_module: true } as any,
    } as any
  }
}

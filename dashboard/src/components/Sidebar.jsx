import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { SCREENS } from '../routes'
import { useAuth } from '../context/AuthContext'
import { usePlanFeatures } from '../hooks/usePlanFeatures'
import UpgradeModal from './UpgradeModal'

const linkBase = 'flex items-center gap-3 px-4 py-2.5 text-sm rounded-lg transition-colors'
const ADMIN_ONLY = new Set(['/management-console', '/admin/analytics'])

// Map sidebar route → feature flag. Admin-only paths are gated separately.
const PATH_FEATURE = {
  '/rate-calendar':     'rateCalendar',
  '/competitive-intel': 'competitiveIntel',
  '/events':            'events',
  '/reputation':        'reputation',
  '/weather':           'weather',
  '/historical':        'historical',
  '/roi-performance':   'roiPerformance',
  '/guest-crm':         'guestCrm',
  '/weddings':          'weddings',
  '/private-events':    'privateEvents',
  '/packages':          'packages',
  '/gift-shop':         'giftShop',
  '/fnb-yield':         'fbYield',
  '/gap-night':         'revenueIntelligence',
}

function itemClass({ isActive }) {
  return isActive
    ? `${linkBase} bg-gold text-navy font-semibold`
    : `${linkBase} text-white/80 hover:bg-navy-light`
}

const PLAN_LABEL = {
  starter: 'Starter', professional: 'Professional', enterprise: 'Enterprise',
  premium: 'Premium', founding_member: 'Founding Member',
}

export default function Sidebar() {
  const navigate = useNavigate()
  const { user, role, openMode, logout } = useAuth()
  const features = usePlanFeatures()
  const isAdmin = openMode || role === 'tgc_admin'
  const screens = SCREENS.filter((s) => isAdmin || !ADMIN_ONLY.has(s.path))
  const [upgrade, setUpgrade] = useState({ open: false, feature: null })

  const onLogout = async () => { await logout(); navigate('/login') }

  // Lock evaluation per nav item — admin overrides any feature lock.
  const isLocked = (path) => {
    if (isAdmin) return false
    const f = PATH_FEATURE[path]
    return f ? !features.has(f) : false
  }
  const onLockedClick = (path) => (e) => {
    e.preventDefault()
    setUpgrade({ open: true, feature: PATH_FEATURE[path] })
  }

  return (
    <aside className="w-60 shrink-0 bg-navy text-white flex flex-col">
      <div className="px-5 py-4 border-b border-white/10">
        <div className="font-extrabold text-white tracking-tight text-xl">INNtelligence</div>
        <div className="text-[11px] text-gold font-semibold mt-0.5">Boutique Hospitality Intelligence</div>
        <div className="text-[10px] text-white/40 mt-0.5">by The Gracious Collection</div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        <NavLink to="/" end className={itemClass}>
          <span aria-hidden>🏠</span> Home
        </NavLink>
        {screens.map((s) => {
          const locked = isLocked(s.path)
          if (locked) {
            return (
              <button key={s.path} onClick={onLockedClick(s.path)}
                className={`${linkBase} w-full text-left text-white/80 hover:bg-navy-light opacity-40 cursor-pointer`}
                aria-label={`${s.name} (locked)`}>
                <span aria-hidden>{s.icon}</span>
                <span className="flex-1">{s.name}</span>
                <span className="text-gold text-[13px]" aria-hidden>🔒</span>
              </button>
            )
          }
          if (s.highlight) return (
            <NavLink key={s.path} to={s.path}
              className={({ isActive }) => `${linkBase} mt-2 font-semibold border ${isActive ? 'bg-gold text-navy border-gold' : 'bg-gold/15 text-gold border-gold/50 hover:bg-gold/25'}`}>
              <span aria-hidden>{s.icon}</span> {s.name}
            </NavLink>
          )
          return (
            <NavLink key={s.path} to={s.path} className={itemClass}>
              <span aria-hidden>{s.icon}</span> {s.name}
            </NavLink>
          )
        })}
      </nav>
      <UpgradeModal open={upgrade.open} feature={upgrade.feature}
        onClose={() => setUpgrade({ open: false, feature: null })} />

      {/* User / session footer */}
      <div className="border-t border-white/10 p-3">
        {user ? (
          <div className="px-2 pb-2">
            <div className="text-sm font-semibold text-white truncate">{user.owner_name || user.email}</div>
            <div className="text-[11px] text-gold-light truncate">{user.property_name || '—'}</div>
            <div className="text-[10px] text-white/40">{PLAN_LABEL[user.plan_tier] || user.plan_tier} · {user.role === 'tgc_admin' ? 'Admin' : 'Innkeeper'}</div>
          </div>
        ) : openMode ? (
          <div className="px-2 pb-2 text-[10px] text-white/30">Demo mode · auth not configured</div>
        ) : null}
        <button onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs text-white/70 hover:bg-navy-light hover:text-white transition-colors">
          ⎋ Log out
        </button>
      </div>
    </aside>
  )
}

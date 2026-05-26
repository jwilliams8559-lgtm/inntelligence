import { NavLink, useNavigate } from 'react-router-dom'
import { SCREENS } from '../routes'
import { useAuth } from '../context/AuthContext'

const linkBase = 'flex items-center gap-3 px-4 py-2.5 text-sm rounded-lg transition-colors'
const ADMIN_ONLY = new Set(['/management-console'])

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
  const isAdmin = openMode || role === 'tgc_admin'
  const screens = SCREENS.filter((s) => isAdmin || !ADMIN_ONLY.has(s.path))

  const onLogout = async () => { await logout(); navigate('/login') }

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
        {screens.map((s) => (
          s.highlight ? (
            <NavLink key={s.path} to={s.path}
              className={({ isActive }) => `${linkBase} mt-2 font-semibold border ${isActive ? 'bg-gold text-navy border-gold' : 'bg-gold/15 text-gold border-gold/50 hover:bg-gold/25'}`}>
              <span aria-hidden>{s.icon}</span> {s.name}
            </NavLink>
          ) : (
            <NavLink key={s.path} to={s.path} className={itemClass}>
              <span aria-hidden>{s.icon}</span> {s.name}
            </NavLink>
          )
        ))}
      </nav>

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

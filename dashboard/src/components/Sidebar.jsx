import { NavLink } from 'react-router-dom'
import { SCREENS } from '../routes'

const linkBase =
  'flex items-center gap-3 px-4 py-2.5 text-sm rounded-lg transition-colors'

function itemClass({ isActive }) {
  return isActive
    ? `${linkBase} bg-gold text-navy font-semibold`
    : `${linkBase} text-white/80 hover:bg-navy-light`
}

export default function Sidebar() {
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
        {SCREENS.map((s) => (
          s.highlight ? (
            <NavLink
              key={s.path}
              to={s.path}
              className={({ isActive }) =>
                `${linkBase} mt-2 font-semibold border ${
                  isActive
                    ? 'bg-gold text-navy border-gold'
                    : 'bg-gold/15 text-gold border-gold/50 hover:bg-gold/25'
                }`
              }
            >
              <span aria-hidden>{s.icon}</span> {s.name}
            </NavLink>
          ) : (
            <NavLink key={s.path} to={s.path} className={itemClass}>
              <span aria-hidden>{s.icon}</span> {s.name}
            </NavLink>
          )
        ))}
      </nav>
    </aside>
  )
}

import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// Persistent banner shown throughout the public read-only demo.
export default function DemoBanner() {
  const { demoReadOnly } = useAuth() || {}
  if (!demoReadOnly) return null
  return (
    <div className="w-full px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium bg-navy text-white border-b border-gold/40">
      <div className="min-w-0 flex items-center gap-2">
        <span className="text-gold" aria-hidden>👁️</span>
        <span className="truncate">
          You're exploring a <span className="font-bold text-gold">live, read-only demo</span>
          <span className="hidden sm:inline"> — start a free trial to make it yours.</span>
        </span>
      </div>
      <div className="shrink-0 flex items-center gap-2">
        <a href="/demo?tour=1"
          className="px-3 py-1.5 rounded-md border border-gold/60 text-gold text-xs font-bold hover:bg-gold hover:text-navy">
          ▶ Play guided tour
        </a>
        <Link to="/onboarding"
          className="px-3 py-1.5 rounded-md bg-gold text-navy text-xs font-bold hover:bg-gold-light">
          Start free trial →
        </Link>
      </div>
    </div>
  )
}

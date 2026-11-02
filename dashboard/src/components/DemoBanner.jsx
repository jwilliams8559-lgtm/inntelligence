import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// Persistent conversion CTA shown throughout the public read-only demo: a top
// banner plus an always-visible floating button. Both route to /signup — the
// real start of the trial (account → verify email → card → onboarding). Never
// to /onboarding, which is behind the auth wall and would bounce a demo viewer.
export default function DemoBanner() {
  const { demoReadOnly } = useAuth() || {}
  if (!demoReadOnly) return null
  return (
    <>
      <div className="w-full px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium bg-navy text-white border-b border-gold/40">
        <div className="min-w-0 flex items-center gap-2">
          <span className="text-gold" aria-hidden>👁️</span>
          <span className="truncate">
            You&rsquo;re exploring a <span className="font-bold text-gold">live, read-only demo</span>
            <span className="hidden sm:inline"> — start your free trial to set this up for your own inn.</span>
          </span>
        </div>
        <Link to="/signup"
          className="shrink-0 px-3 py-1.5 rounded-md bg-gold text-navy text-xs font-bold hover:bg-gold-light">
          Start free trial →
        </Link>
      </div>

      {/* Always-visible floating CTA — unmissable on long scrolls and on mobile,
          where the banner text truncates. */}
      <Link to="/signup"
        className="fixed bottom-5 right-5 z-50 px-5 py-3 rounded-full bg-gold text-navy font-bold hover:bg-gold-light hover:scale-105 transition-transform flex items-center gap-2"
        style={{ boxShadow: '0 10px 30px rgba(201,168,76,0.45)' }}>
        <span className="hidden xs:inline sm:inline">Start your 14-day free trial</span>
        <span className="sm:hidden">Start free trial</span>
        <span aria-hidden>→</span>
      </Link>
    </>
  )
}

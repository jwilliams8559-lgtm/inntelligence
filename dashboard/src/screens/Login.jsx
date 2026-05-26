import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

// Demo accounts (tier names match engine/billing.py + modules/auth/auth.py).
const DEMO_ACCOUNTS = [
  { email: 'demo@graciouscollection.com', password: 'demo2026', label: 'Bay Street Inn', sub: 'Professional tier · Innkeeper view', icon: '★', to: '/' },
  { email: 'starter@graciouscollection.com', password: 'demo2026', label: 'Starter Demo Inn', sub: 'Starter tier · Manual approval', icon: '●', to: '/' },
  { email: 'premium@graciouscollection.com', password: 'demo2026', label: 'Premium Demo Properties', sub: 'Premium tier · Multi-property', icon: '◆', to: '/' },
  { email: 'admin@graciouscollection.com', password: 'admin2026', label: 'INNtelligence Admin', sub: 'Management Console · Onboarding', icon: '⚙', to: '/management-console' },
]

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  // NOTE: the JSX app has no auth backend wired yet — this routes into the
  // dashboard for the demo. Real auth (Supabase / tokens) is follow-up work.
  const signIn = (to = '/') => { setBusy(true); setTimeout(() => navigate(to), 300) }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8"
         style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #0F2238 60%, #07172B 100%)' }}>
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="text-gold font-bold text-4xl tracking-wide" style={{ fontFamily: 'Georgia, serif' }}>INNtelligence</div>
          <div className="text-gold-light text-[11px] font-semibold mt-1 italic">Boutique Hospitality Intelligence</div>
          <div className="text-white/40 text-[10px] mt-0.5">by The Gracious Collection</div>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); signIn('/') }} className="bg-white rounded-2xl shadow-2xl p-6">
          <h1 className="text-navy font-bold text-lg mb-4">Sign in</h1>
          <label className="block mb-3">
            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Email</div>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@inn.com"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
          </label>
          <label className="block mb-4">
            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Password</div>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
          </label>
          <button type="submit" disabled={busy}
            className="w-full bg-navy text-white font-bold py-2.5 rounded-lg hover:bg-navy-light disabled:opacity-50 transition-colors">
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="mt-5 bg-white/10 backdrop-blur border border-white/15 rounded-2xl p-4">
          <div className="text-gold text-[10px] uppercase tracking-[3px] font-bold mb-2 text-center">Demo accounts — one-click</div>
          <div className="space-y-1.5">
            {DEMO_ACCOUNTS.map((a) => (
              <button key={a.email} onClick={() => { setEmail(a.email); setPassword(a.password); signIn(a.to) }} disabled={busy}
                className="w-full text-left bg-white/5 hover:bg-white/20 border border-white/10 rounded-lg px-3 py-2 transition-all disabled:opacity-50 group">
                <div className="flex items-center gap-3">
                  <span className="text-gold text-base">{a.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-white text-sm font-semibold truncate">{a.label}</div>
                    <div className="text-white/60 text-[11px]">{a.sub}</div>
                  </div>
                  <span className="text-[10px] text-white/40 group-hover:text-gold whitespace-nowrap">Sign in →</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="text-center text-[10px] text-white/40 mt-6">
          INNtelligence by The Gracious Collection © 2026 · <a href="/pricing" className="underline hover:text-gold">View pricing</a>
        </div>
      </div>
    </div>
  )
}

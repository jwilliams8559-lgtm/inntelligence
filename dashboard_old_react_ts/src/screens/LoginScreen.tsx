import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

interface Account { email: string; password: string; label: string; sub: string; icon: string; accent: string }

const DEMO_ACCOUNTS: Account[] = [
  { email: 'demo@graciouscollection.com',       password: 'demo2026',  label: 'Bay Street Inn',         sub: 'Professional tier · Innkeeper view',  icon: '★', accent: 'gold' },
  { email: 'essentials@graciouscollection.com', password: 'demo2026',  label: 'Essentials Demo Inn',        sub: 'Essentials tier · Locked features',   icon: '●', accent: 'slate' },
  { email: 'portfolio@graciouscollection.com',  password: 'demo2026',  label: 'Portfolio Demo Properties',  sub: 'Portfolio tier · Multi-property',     icon: '◆', accent: 'navy' },
  { email: 'admin@graciouscollection.com',      password: 'admin2026', label: 'INNtelligence Admin',        sub: 'Management Console · Onboarding',     icon: '⚙', accent: 'gold' },
]

export default function LoginScreen() {
  const { login } = useAuth()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const [busy, setBusy]         = useState(false)

  async function submit(e?: React.FormEvent) {
    if (e) e.preventDefault()
    setBusy(true); setError(null)
    const r = await login(email, password)
    if (!r.ok) setError(r.error || 'Login failed')
    setBusy(false)
  }

  async function quickFill(a: Account) {
    setEmail(a.email); setPassword(a.password); setError(null)
    setBusy(true)
    const r = await login(a.email, a.password)
    if (!r.ok) setError(r.error || 'Login failed')
    setBusy(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8"
         style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #0F2238 60%, #07172B 100%)' }}>
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="text-gold font-serif font-bold text-4xl tracking-wide" style={{ fontFamily: 'Georgia, serif' }}>
            INNtelligence
          </div>
          <div className="text-white/70 text-xs mt-1 tracking-wide">
            by The Gracious Collection
          </div>
          <div className="text-white/40 text-[10px] uppercase tracking-[3px] mt-1">
            Boutique Hospitality Intelligence
          </div>
        </div>

        {/* Sign-in card */}
        <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl p-6">
          <h1 className="text-navy font-bold text-lg mb-4">Sign in</h1>

          <label className="block mb-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Email</div>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              autoComplete="email" required placeholder="you@inn.com"
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-navy" />
          </label>
          <label className="block mb-4">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Password</div>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              autoComplete="current-password" required
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-navy" />
          </label>
          {error && (
            <div className="mb-3 bg-coral/10 border border-coral/30 text-coral text-xs rounded p-2">{error}</div>
          )}
          <button type="submit" disabled={busy}
            className="w-full bg-navy text-white font-bold py-2.5 rounded-lg hover:bg-navy-light disabled:opacity-50 transition-colors">
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* One-click demo fill */}
        <div className="mt-5 bg-white/10 backdrop-blur border border-white/15 rounded-2xl p-4">
          <div className="text-gold text-[10px] uppercase tracking-[3px] font-bold mb-2 text-center">
            Demo accounts — one-click fill
          </div>
          <div className="space-y-1.5">
            {DEMO_ACCOUNTS.map(a => (
              <button key={a.email} onClick={() => quickFill(a)} disabled={busy}
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
          <div className="text-center text-[10px] text-white/40 mt-3">
            Or type credentials above to sign in manually.
          </div>
        </div>

        <div className="text-center text-[10px] text-white/40 mt-6">
          INNtelligence by The Gracious Collection © 2026 · graciouscollection.com
        </div>
      </div>
    </div>
  )
}

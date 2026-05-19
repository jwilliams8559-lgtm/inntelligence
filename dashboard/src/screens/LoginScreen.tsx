import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

const DEMO_ACCOUNTS = [
  { email: 'demo@graciouscollection.com',       password: 'demo2026', tier: 'Professional' },
  { email: 'essentials@graciouscollection.com', password: 'demo2026', tier: 'Essentials' },
  { email: 'portfolio@graciouscollection.com',  password: 'demo2026', tier: 'Portfolio' },
]

export default function LoginScreen() {
  const { login } = useAuth()
  const [email, setEmail]       = useState('demo@graciouscollection.com')
  const [password, setPassword] = useState('demo2026')
  const [error, setError]       = useState<string | null>(null)
  const [busy, setBusy]         = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    const r = await login(email, password)
    if (!r.ok) setError(r.error || 'Login failed')
    setBusy(false)
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        {/* Header / logo */}
        <div className="text-center mb-6">
          <div className="text-gold text-[10px] uppercase tracking-[4px] font-bold mb-1">
            The Gracious Collection
          </div>
          <h1 className="text-navy font-bold text-2xl">Rate Intelligence Center</h1>
          <p className="text-slate-500 text-xs mt-1">Boutique Hospitality Intelligence</p>
        </div>

        <form onSubmit={submit} className="bg-white rounded-xl shadow-lg border border-slate-100 p-6">
          <label className="block mb-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Email</div>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              autoComplete="email" required
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-navy" />
          </label>
          <label className="block mb-4">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-1">Password</div>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              autoComplete="current-password" required
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-navy" />
          </label>
          {error && (
            <div className="mb-3 bg-coral/10 border border-coral/30 text-coral text-xs rounded p-2">
              {error}
            </div>
          )}
          <button type="submit" disabled={busy}
            className="w-full bg-navy text-white font-bold py-2.5 rounded-lg hover:bg-navy-dark disabled:opacity-50 transition-colors">
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* Demo accounts */}
        <div className="mt-4 bg-cream/60 border border-slate-200 rounded-xl p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">
            Demo accounts (password: demo2026)
          </div>
          <div className="space-y-1.5">
            {DEMO_ACCOUNTS.map(a => (
              <button key={a.email}
                onClick={() => { setEmail(a.email); setPassword(a.password) }}
                className="w-full flex items-center justify-between text-xs text-slate-600 hover:text-navy hover:bg-white rounded px-2 py-1 transition-colors">
                <span className="font-mono">{a.email}</span>
                <span className="text-[10px] bg-gold/15 text-gold-dark font-bold px-1.5 py-0.5 rounded">
                  {a.tier}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="text-center text-[10px] text-slate-400 mt-4">
          Investor demo · Anchorage 1770 Inn, Beaufort SC
        </div>
      </div>
    </div>
  )
}

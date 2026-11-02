import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const DEMO_ACCOUNTS = [
  { email: 'demo@graciouscollection.com', label: 'Bay Street Inn', sub: 'Professional · Innkeeper', icon: '★' },
  { email: 'admin@graciouscollection.com', label: 'INNtelligence Admin', sub: 'Management Console', icon: '⚙' },
]

export default function Login() {
  const navigate = useNavigate()
  const { login, resetPassword, user, role, openMode } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  // Already signed in (or open mode) → go to the right landing screen.
  useEffect(() => {
    if (openMode) { navigate('/'); return }
    if (user) navigate(role === 'tgc_admin' ? '/management-console' : '/')
  }, [user, role, openMode, navigate])

  const submit = async (e) => {
    if (e) e.preventDefault()
    setBusy(true); setError(null); setNotice(null)
    try {
      const r = await login(email, password)
      navigate(r.role === 'tgc_admin' ? '/management-console' : '/')
    } catch (ex) {
      setError(ex.message || 'Sign in failed. Check your email and password.')
    } finally { setBusy(false) }
  }

  const forgot = async () => {
    if (!email) { setError('Enter your email first, then click “Forgot password”.'); return }
    setError(null)
    await resetPassword(email)
    setNotice('If an account exists for that email, a password reset link is on its way.')
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8"
         style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #0F2238 60%, #07172B 100%)' }}>
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="text-gold font-bold text-4xl tracking-wide" style={{ fontFamily: 'Georgia, serif' }}>INNtelligence</div>
          <div className="text-gold-light text-[11px] font-semibold mt-1 italic">Boutique Hospitality Intelligence</div>
          <div className="text-white/40 text-[10px] mt-0.5">by The Gracious Collection</div>
        </div>

        {/* New visitors: start a trial. This is the primary public call to action. */}
        <div className="bg-white rounded-2xl shadow-2xl p-6 mb-4 text-center">
          <h1 className="text-navy font-bold text-lg">Start your 14-day free trial</h1>
          <p className="text-gray-500 text-[13px] mt-1 mb-4">
            AI-powered pricing and competitor tracking for your inn. Set up in minutes.
          </p>
          <Link to="/signup"
            className="block w-full bg-gold text-navy font-bold py-3 rounded-lg hover:bg-gold-light transition-colors">
            Start free trial →
          </Link>
          <div className="text-[11px] text-gray-400 mt-2">
            No charge for 14 days · cancel anytime before you’re billed
          </div>
          <div className="mt-3 pt-3 border-t border-gray-100">
            <Link to="/demo" className="text-[12px] text-navy underline hover:text-gold">
              Or take the live demo first →
            </Link>
          </div>
        </div>

        {/* Returning customers: sign in. */}
        <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl p-6">
          <h2 className="text-navy font-bold text-base mb-4">Already a member? Sign in</h2>
          <label className="block mb-3">
            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Email</div>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required placeholder="you@inn.com"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
          </label>
          <label className="block mb-2">
            <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Password</div>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold" />
          </label>
          <div className="flex justify-end mb-3">
            <button type="button" onClick={forgot} className="text-[11px] text-navy hover:text-gold underline">Forgot password?</button>
          </div>
          {error && <div className="mb-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded p-2">{error}</div>}
          {notice && <div className="mb-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded p-2">{notice}</div>}
          <button type="submit" disabled={busy}
            className="w-full bg-navy text-white font-bold py-2.5 rounded-lg hover:bg-navy-light disabled:opacity-50 transition-colors">
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* Demo quick-fill only when Supabase auth isn't configured (local/demo). */}
        {openMode && (
          <div className="mt-5 bg-white/10 backdrop-blur border border-white/15 rounded-2xl p-4">
            <div className="text-gold text-[10px] uppercase tracking-[3px] font-bold mb-2 text-center">Demo mode — quick access</div>
            <div className="space-y-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button key={a.email} onClick={() => navigate(a.icon === '⚙' ? '/management-console' : '/')}
                  className="w-full text-left bg-white/5 hover:bg-white/20 border border-white/10 rounded-lg px-3 py-2 group">
                  <div className="flex items-center gap-3">
                    <span className="text-gold text-base">{a.icon}</span>
                    <div className="flex-1 min-w-0"><div className="text-white text-sm font-semibold truncate">{a.label}</div><div className="text-white/60 text-[11px]">{a.sub}</div></div>
                    <span className="text-[10px] text-white/40 group-hover:text-gold">Enter →</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="text-center text-[10px] text-white/40 mt-6">
          INNtelligence by The Gracious Collection © 2026
        </div>
      </div>
    </div>
  )
}

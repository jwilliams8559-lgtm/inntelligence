import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
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
  const [requesting, setRequesting] = useState(false)

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

        {!requesting ? (
          <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl p-6">
            <h1 className="text-navy font-bold text-lg mb-4">Sign in</h1>
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
            <div className="text-center text-[11px] text-gray-400 mt-3">
              No account? <button type="button" onClick={() => { setRequesting(true); setError(null); setNotice(null) }} className="text-navy underline hover:text-gold">Request access</button>
            </div>
          </form>
        ) : (
          <RequestAccess onBack={() => setRequesting(false)} />
        )}

        {/* Demo quick-fill only when Supabase auth isn't configured (local/demo). */}
        {openMode && !requesting && (
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

function RequestAccess({ onBack }) {
  const [sent, setSent] = useState(false)
  const [f, setF] = useState({ name: '', inn: '', email: '' })
  const cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'
  if (sent) {
    return (
      <div className="bg-white rounded-2xl shadow-2xl p-6 text-center">
        <div className="text-3xl">📨</div>
        <div className="text-navy font-bold mt-2">Thanks — request received</div>
        <p className="text-gray-500 text-sm mt-1">Jim will reach out to set up your INNtelligence account. Accounts are created individually for each property.</p>
        <button onClick={onBack} className="mt-4 text-xs text-navy underline hover:text-gold">← Back to sign in</button>
      </div>
    )
  }
  return (
    <div className="bg-white rounded-2xl shadow-2xl p-6">
      <h1 className="text-navy font-bold text-lg mb-1">Request access</h1>
      <p className="text-gray-500 text-xs mb-4">INNtelligence accounts are created by our team for each property — no public signup.</p>
      <div className="space-y-3">
        <input className={cls} placeholder="Your name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <input className={cls} placeholder="Inn / property name" value={f.inn} onChange={(e) => setF({ ...f, inn: e.target.value })} />
        <input className={cls} type="email" placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
      </div>
      <a href={`mailto:hello@inntelligence.app?subject=INNtelligence%20access%20request&body=${encodeURIComponent(`Name: ${f.name}\nProperty: ${f.inn}\nEmail: ${f.email}`)}`}
         onClick={() => setSent(true)}
         className="mt-4 block text-center w-full bg-gold text-navy font-bold py-2.5 rounded-lg hover:bg-gold-light">Send request</a>
      <button onClick={onBack} className="mt-3 w-full text-xs text-gray-400 underline hover:text-navy">← Back to sign in</button>
    </div>
  )
}

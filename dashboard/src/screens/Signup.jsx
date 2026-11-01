import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const PLAN_LABELS = { inn: 'Inn', boutique: 'Boutique', signature: 'Signature', collection: 'Collection' }
const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || ''

// Cloudflare Turnstile — only rendered when a site key is configured. Captures a
// token the server verifies; when no key is set the whole widget is skipped and
// the server skips verification too (so local/testing isn't blocked).
function Turnstile({ onToken }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return
    const id = 'cf-turnstile-script'
    function render() {
      if (window.turnstile && ref.current && !ref.current.dataset.rendered) {
        ref.current.dataset.rendered = '1'
        window.turnstile.render(ref.current, { sitekey: TURNSTILE_SITE_KEY, callback: onToken })
      }
    }
    if (!document.getElementById(id)) {
      const s = document.createElement('script')
      s.id = id; s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js'
      s.async = true; s.defer = true; s.onload = render
      document.head.appendChild(s)
    } else { render() }
  }, [onToken])
  if (!TURNSTILE_SITE_KEY) return null
  return <div ref={ref} className="mt-1 flex justify-center" />
}

export default function Signup() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { signup, user, openMode } = useAuth()

  const plan = params.get('plan') || 'boutique'
  const [f, setF] = useState({ propertyName: '', ownerName: '', email: '', password: '', confirm: '' })
  const [turnstileToken, setTurnstileToken] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [verifySent, setVerifySent] = useState(false)

  // Already signed in → skip signup.
  useEffect(() => { if (user && !verifySent) navigate('/onboarding') }, [user, verifySent, navigate])

  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }))
  const cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'

  const submit = async (e) => {
    if (e) e.preventDefault()
    setError(null)
    if (!f.propertyName.trim()) return setError('Please enter your property name.')
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) return setError('Please enter a valid email address.')
    if (f.password.length < 8) return setError('Password must be at least 8 characters.')
    if (f.password !== f.confirm) return setError('Passwords do not match.')
    if (TURNSTILE_SITE_KEY && !turnstileToken) return setError('Please complete the bot check.')
    setBusy(true)
    try {
      const res = await signup({
        email: f.email.trim().toLowerCase(),
        password: f.password,
        property_name: f.propertyName.trim(),
        owner_name: f.ownerName.trim(),
        plan_tier: plan,
        turnstile_token: turnstileToken,
      })
      if (res.needs_verification) { setVerifySent(true); return }
      navigate('/onboarding')
    } catch (ex) {
      setError(ex.message || 'Could not create your account. Please try again.')
    } finally { setBusy(false) }
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

        {verifySent ? (
          <div className="bg-white rounded-2xl shadow-2xl p-6 text-center">
            <div className="text-3xl">📨</div>
            <div className="text-navy font-bold mt-2 text-lg">Check your email</div>
            <p className="text-gray-600 text-sm mt-2">
              We sent a verification link to <span className="font-semibold">{f.email}</span>.
              Click it to confirm your account, then sign in to start your 14-day free trial.
            </p>
            <Link to="/login" className="mt-5 inline-block w-full bg-navy text-white font-bold py-2.5 rounded-lg hover:bg-navy-light">
              Go to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={submit} className="bg-white rounded-2xl shadow-2xl p-6">
            <h1 className="text-navy font-bold text-lg">Start your free trial</h1>
            <p className="text-gray-500 text-xs mt-0.5 mb-4">
              14 days free{PLAN_LABELS[plan] ? ` on the ${PLAN_LABELS[plan]} plan` : ''} · no credit card required.
            </p>

            <label className="block mb-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Property / inn name</div>
              <input className={cls} value={f.propertyName} onChange={set('propertyName')} required placeholder="The Bay Street Inn" />
            </label>
            <label className="block mb-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Your name</div>
              <input className={cls} value={f.ownerName} onChange={set('ownerName')} placeholder="Jane Innkeeper" autoComplete="name" />
            </label>
            <label className="block mb-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Work email</div>
              <input className={cls} type="email" value={f.email} onChange={set('email')} required placeholder="you@inn.com" autoComplete="email" />
            </label>
            <label className="block mb-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Password</div>
              <input className={cls} type="password" value={f.password} onChange={set('password')} required placeholder="At least 8 characters" autoComplete="new-password" />
            </label>
            <label className="block mb-3">
              <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-1">Confirm password</div>
              <input className={cls} type="password" value={f.confirm} onChange={set('confirm')} required autoComplete="new-password" />
            </label>

            <Turnstile onToken={setTurnstileToken} />

            {error && <div className="my-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded p-2">{error}</div>}

            <button type="submit" disabled={busy}
              className="w-full bg-gold text-navy font-bold py-2.5 rounded-lg hover:bg-gold-light disabled:opacity-50 transition-colors mt-1">
              {busy ? 'Creating your account…' : 'Create account & start trial'}
            </button>
            <p className="text-[10px] text-gray-400 text-center mt-3">
              By creating an account you agree to our terms. We'll never charge you without asking first.
            </p>
            <div className="text-center text-[11px] text-gray-400 mt-3">
              Already have an account? <Link to="/login" className="text-navy underline hover:text-gold">Sign in</Link>
            </div>
          </form>
        )}

        {openMode && (
          <div className="mt-4 text-center text-[11px] text-white/50">
            Auth isn't configured in this environment — signup needs Supabase.
          </div>
        )}

        <div className="text-center text-[10px] text-white/40 mt-6">
          INNtelligence by The Gracious Collection © 2026
        </div>
      </div>
    </div>
  )
}

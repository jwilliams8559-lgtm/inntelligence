import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { createCheckoutSession, confirmCheckout } from '../api/client'

const TIER = {
  inn:        { name: 'Inn',        price: 149 },
  boutique:   { name: 'Boutique',   price: 399 },
  signature:  { name: 'Signature',  price: 799 },
  collection: { name: 'Collection', price: 1499 },
}

// Card-up-front gate. A verified owner whose account has no payment method lands
// here before onboarding: add a card to START the 14-day free trial (not charged
// until the trial ends; cancel anytime). Returns from Stripe Checkout, confirms,
// then continues to onboarding.
export default function StartTrial() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { user, refresh, openMode } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [confirming, setConfirming] = useState(false)

  const tier = user?.plan_tier || 'boutique'
  const meta = TIER[tier] || TIER.boutique
  const trialEnd = new Date(Date.now() + 14 * 86400000).toLocaleDateString(undefined,
    { month: 'long', day: 'numeric', year: 'numeric' })

  // Handle the return from Stripe Checkout.
  useEffect(() => {
    const status = params.get('checkout')
    const sessionId = params.get('session_id')
    if (status === 'success' && sessionId) {
      setConfirming(true)
      confirmCheckout(sessionId)
        .then(() => refresh())
        .then(() => navigate('/onboarding', { replace: true }))
        .catch(async () => {
          // Confirm call failed — but the Stripe webhook may have already started
          // the trial. Re-pull context; if we're no longer awaiting payment, proceed.
          try {
            const me = await refresh()
            if (me && me.needs_payment === false) { navigate('/onboarding', { replace: true }); return }
          } catch { /* fall through to error */ }
          setConfirming(false)
          setError('Almost there — if your card went through, give it a few seconds and refresh this page.')
        })
    } else if (status === 'cancelled') {
      setError('Checkout was cancelled. Add a card to start your free trial.')
    }
  }, [params, refresh, navigate])

  async function start() {
    setBusy(true); setError(null)
    try {
      const base = window.location.origin
      const res = await createCheckoutSession(tier, {
        success_url: `${base}/start-trial?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
        cancel_url:  `${base}/start-trial?checkout=cancelled`,
      })
      if (res && res.url) { window.location.href = res.url; return }
      setError('Could not start checkout. Please try again.')
    } catch (ex) {
      setError(ex.message || 'Could not start checkout. Please try again.')
    } finally { setBusy(false) }
  }

  if (confirming) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-navy text-gold">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-gold border-t-transparent rounded-full animate-spin mx-auto" />
          <div className="mt-4 text-sm text-gold-light">Confirming your trial…</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8"
         style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #0F2238 60%, #07172B 100%)' }}>
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="text-gold font-bold text-3xl tracking-wide" style={{ fontFamily: 'Georgia, serif' }}>INNtelligence</div>
          <div className="text-white/40 text-[10px] mt-0.5">by The Gracious Collection</div>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-6">
          <h1 className="text-navy font-bold text-lg">Start your 14-day free trial</h1>
          <p className="text-gray-600 text-sm mt-1">
            You're on the <span className="font-semibold">{meta.name}</span> plan
            {meta.price ? <> (${meta.price.toLocaleString()}/mo)</> : null}. Add a card to begin — we
            <span className="font-semibold"> won't charge you until {trialEnd}</span>, and you can cancel anytime before then.
          </p>

          <ul className="mt-4 space-y-1.5 text-xs text-gray-700">
            <li className="flex gap-2"><span className="text-gold">✓</span><span>Full access for 14 days, free</span></li>
            <li className="flex gap-2"><span className="text-gold">✓</span><span>Cancel in one click before {trialEnd} — no charge</span></li>
            <li className="flex gap-2"><span className="text-gold">✓</span><span>Secure card entry handled by Stripe</span></li>
          </ul>

          {error && <div className="my-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded p-2">{error}</div>}

          <button onClick={start} disabled={busy || openMode}
            className="w-full bg-gold text-navy font-bold py-2.5 rounded-lg hover:bg-gold-light disabled:opacity-50 transition-colors mt-4">
            {busy ? 'Opening secure checkout…' : 'Add card & start free trial'}
          </button>
          {openMode && <p className="text-[10px] text-gray-400 text-center mt-2">Billing isn't configured in this environment.</p>}
          <p className="text-[10px] text-gray-400 text-center mt-3">
            Powered by Stripe. We never see or store your full card number.
          </p>
        </div>

        <div className="text-center text-[10px] text-white/40 mt-6">
          INNtelligence by The Gracious Collection © 2026
        </div>
      </div>
    </div>
  )
}

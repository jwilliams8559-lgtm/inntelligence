import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { createCheckoutSession } from '../api/client'

const TIER_PRICE = { inn: 149, boutique: 399, signature: 799, collection: 1499 }
const TIER_LABEL = { inn: 'Inn', boutique: 'Boutique', signature: 'Signature', collection: 'Collection' }

// Account-level 14-day trial strip. Shown to a trialing self-serve owner across
// the whole app (distinct from the per-feature TrialBanner). Lights up only once
// migration 006 is applied and trial_ends_at is set. Clicking opens Stripe
// Checkout to add a card and convert before the trial ends.
export default function AccountTrialBanner() {
  const { user, demoMode } = useAuth()
  const [loading, setLoading] = useState(false)

  if (!user || demoMode) return null
  if (user.plan_status !== 'trialing' || !user.trial_ends_at) return null

  const ends = new Date(user.trial_ends_at)
  const daysLeft = Math.max(0, Math.ceil((ends - new Date()) / 86400000))
  const tier = user.plan_tier || 'boutique'
  const price = TIER_PRICE[tier]
  const expired = daysLeft <= 0

  async function addPayment() {
    setLoading(true)
    try {
      const res = await createCheckoutSession(tier)
      if (res && res.url) { window.location.href = res.url; return }
    } catch { /* ignore — button re-enables */ }
    setLoading(false)
  }

  return (
    <div className={`w-full px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium border-b
      ${expired ? 'bg-rose-600 text-white border-rose-700' : 'bg-gold/15 text-navy border-gold/30'}`}>
      <div className="min-w-0">
        {expired ? (
          <span className="font-bold">Your free trial has ended — add a payment method to keep INNtelligence running.</span>
        ) : (
          <>
            <span className="font-bold">{daysLeft} day{daysLeft === 1 ? '' : 's'} left in your free trial</span>
            {price && <span className="hidden sm:inline text-navy/70"> — keep {TIER_LABEL[tier]} for ${price.toLocaleString()}/mo</span>}
          </>
        )}
      </div>
      <button onClick={addPayment} disabled={loading}
        className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-bold disabled:opacity-60
          ${expired ? 'bg-white text-rose-700 hover:bg-rose-50' : 'bg-navy text-gold hover:bg-navy-light'}`}>
        {loading ? 'Starting…' : expired ? 'Add payment' : 'Add payment method'}
      </button>
    </div>
  )
}

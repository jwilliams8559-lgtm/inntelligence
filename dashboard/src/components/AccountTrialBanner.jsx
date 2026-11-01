import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { createPortalSession } from '../api/client'

const TIER_PRICE = { inn: 149, boutique: 399, signature: 799, collection: 1499 }
const TIER_LABEL = { inn: 'Inn', boutique: 'Boutique', signature: 'Signature', collection: 'Collection' }

// Account-level status strip (distinct from the per-feature TrialBanner). With
// card-up-front, a trialing owner already has a card on file, so the button opens
// the Stripe billing portal to manage or cancel. past_due owners are prompted to
// update their card. Lights up once migration 006 is applied and trial_ends_at
// is set. Owners still awaiting a card (needs_payment) are routed to /start-trial
// before they ever reach the dashboard, so they don't see this.
export default function AccountTrialBanner() {
  const { user, demoMode } = useAuth()
  const [loading, setLoading] = useState(false)

  if (!user || demoMode) return null
  const status = user.plan_status
  const isTrialing = status === 'trialing' && user.trial_ends_at
  const isPastDue = status === 'past_due'
  if (!isTrialing && !isPastDue) return null

  const ends = isTrialing ? new Date(user.trial_ends_at) : null
  const daysLeft = ends ? Math.max(0, Math.ceil((ends - new Date()) / 86400000)) : 0
  const tier = user.plan_tier || 'boutique'
  const price = TIER_PRICE[tier]

  async function manage() {
    setLoading(true)
    try {
      const res = await createPortalSession({ return_url: window.location.href })
      if (res && res.url) { window.location.href = res.url; return }
    } catch { /* ignore — button re-enables */ }
    setLoading(false)
  }

  return (
    <div className={`w-full px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium border-b
      ${isPastDue ? 'bg-rose-600 text-white border-rose-700' : 'bg-gold/15 text-navy border-gold/30'}`}>
      <div className="min-w-0">
        {isPastDue ? (
          <span className="font-bold">Your last payment failed — please update your card to keep INNtelligence running.</span>
        ) : (
          <>
            <span className="font-bold">{daysLeft} day{daysLeft === 1 ? '' : 's'} left in your free trial</span>
            {price && <span className="hidden sm:inline text-navy/70"> — then {TIER_LABEL[tier]} at ${price.toLocaleString()}/mo. Cancel anytime.</span>}
          </>
        )}
      </div>
      <button onClick={manage} disabled={loading}
        className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-bold disabled:opacity-60
          ${isPastDue ? 'bg-white text-rose-700 hover:bg-rose-50' : 'bg-navy text-gold hover:bg-navy-light'}`}>
        {loading ? 'Opening…' : isPastDue ? 'Update card' : 'Manage billing'}
      </button>
    </div>
  )
}

import { useState } from 'react'
import { usePlanFeatures } from '../hooks/usePlanFeatures'
import { createCheckoutSession } from '../api/client'

const MAILTO = 'mailto:jwilliams8559@gmail.com'
  + '?subject=' + encodeURIComponent('INNtelligence Upgrade Request')
  + '&body='    + encodeURIComponent('I would like to upgrade my INNtelligence plan.')

// Opens when a user clicks a locked feature. `feature` is a catalog key
// (e.g. 'autopilot'). Offers Upgrade (→ Stripe Checkout for the required tier)
// and a one-time 14-day free trial of just this feature.
export default function UpgradeModal({ open, feature, onClose }) {
  const { tierLabel, featureMeta, trialInfo, startTrial, trialLimit } = usePlanFeatures()
  const [loading, setLoading] = useState('')      // '', 'checkout', 'trial'
  const [error, setError] = useState('')
  if (!open || !feature) return null

  const meta = featureMeta(feature)
  const trial = trialInfo(feature)
  const requiredTier = meta.requiredTier
  const priceText = meta.price ? `$${meta.price.toLocaleString()}/mo` : ''

  async function handleUpgrade() {
    setError(''); setLoading('checkout')
    try {
      const res = await createCheckoutSession(requiredTier)
      if (res && res.url) { window.location.href = res.url; return }
      setError('Could not start checkout. Please try again.')
    } catch (e) {
      setError(e.message || 'Could not start checkout.')
    } finally {
      setLoading('')
    }
  }

  async function handleTrial() {
    setError(''); setLoading('trial')
    try {
      const res = await startTrial(feature)
      if (res && res.ok) { onClose(); return }   // unlocked — banner takes over
      setError(res?.message || 'Could not start the trial.')
    } catch (e) {
      setError(e.message || 'Could not start the trial.')
    } finally {
      setLoading('')
    }
  }

  // Trial already used (and not currently active) → Upgrade only.
  const trialUsed = trial.used && !trial.active
  const canTrial  = trial.canTrial && !trial.active
  const limitReason = trial.reason === 'limit_reached'
    ? `You can trial ${trialLimit} features at a time — upgrade or let one finish first.`
    : ''

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/55" />
      <div role="dialog" aria-modal="true"
        className="relative w-full max-w-md rounded-2xl shadow-2xl text-white p-6"
        style={{ backgroundColor: '#0a2342' }} onClick={(e) => e.stopPropagation()}>

        <div className="flex justify-center mb-3">
          <div className="w-14 h-14 rounded-full bg-gold/15 border border-gold/40 flex items-center justify-center text-gold text-2xl">🔒</div>
        </div>

        <div className="text-center">
          <div className="text-gold-light text-xs uppercase tracking-wide font-bold">
            {trialUsed ? 'Trial used' : 'Upgrade required'}
          </div>
          <h3 className="text-xl font-extrabold mt-1">{meta.label}</h3>
          <p className="text-white/70 text-sm mt-2">{meta.value}</p>
        </div>

        {/* Preview placeholder */}
        <div className="mt-4 h-28 rounded-xl border border-white/10 bg-white/5 flex items-center justify-center overflow-hidden relative">
          <div className="absolute inset-0 opacity-20"
               style={{ background: 'repeating-linear-gradient(45deg, #C9A84C22 0 10px, transparent 10px 20px)' }} />
          <span className="relative text-white/40 text-xs uppercase tracking-wide">Preview</span>
        </div>

        <div className="mt-4 rounded-xl bg-white/5 border border-white/10 p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-white/60">Unlocks with</span>
            <span className="text-gold font-semibold">
              {meta.requiredTierLabel}{priceText && <span className="text-white/40 font-normal"> · {priceText}</span>}
            </span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="text-white/60">Your plan</span>
            <span className="text-white/85">{tierLabel}</span>
          </div>
          {trial.active && (
            <div className="mt-2 text-gold-light text-xs">
              Trial active — {trial.daysLeft} day{trial.daysLeft === 1 ? '' : 's'} left.
            </div>
          )}
        </div>

        {error && <p className="text-red-300 text-xs text-center mt-4" role="alert">{error}</p>}
        {limitReason && !error && <p className="text-amber-300 text-xs text-center mt-4">{limitReason}</p>}

        <div className="grid grid-cols-2 gap-3 mt-5">
          <button onClick={handleUpgrade} disabled={!!loading}
            className="px-4 py-2.5 rounded-lg bg-gold text-navy text-sm font-bold text-center hover:bg-gold-light disabled:opacity-60">
            {loading === 'checkout' ? 'Starting…' : `Upgrade to ${meta.requiredTierLabel}`}
          </button>

          {trialUsed ? (
            <button onClick={onClose} disabled={!!loading}
              className="px-4 py-2.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm font-semibold disabled:opacity-50">
              Close
            </button>
          ) : (
            <button onClick={handleTrial} disabled={!!loading || !canTrial}
              title={!canTrial ? limitReason : 'Try this feature free for 14 days'}
              className="px-4 py-2.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed">
              {loading === 'trial' ? 'Starting…' : 'Try free for 14 days'}
            </button>
          )}
        </div>

        <button onClick={onClose} className="w-full mt-3 text-white/40 hover:text-white/70 text-xs">
          Not now
        </button>
      </div>
    </div>
  )
}

export { MAILTO as UPGRADE_MAILTO }

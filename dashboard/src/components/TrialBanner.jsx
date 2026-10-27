import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { PATH_FEATURE } from '../routes'
import { usePlanFeatures } from '../hooks/usePlanFeatures'
import { createCheckoutSession } from '../api/client'

// Shown at the top of a feature screen while that feature is in an active trial:
// "X days left in your [feature] trial — keep it for $[tier price]/mo" + upgrade.
export default function TrialBanner() {
  const { pathname } = useLocation()
  const { featureMeta, trialInfo } = usePlanFeatures()
  const [loading, setLoading] = useState(false)

  const feature = PATH_FEATURE[pathname]
  if (!feature) return null
  const trial = trialInfo(feature)
  if (!trial.active) return null

  const meta = featureMeta(feature)
  const priceText = meta.price ? `$${meta.price.toLocaleString()}/mo` : ''

  async function keepIt() {
    setLoading(true)
    try {
      const res = await createCheckoutSession(meta.requiredTier)
      if (res && res.url) { window.location.href = res.url; return }
    } catch { /* ignore — button just re-enables */ }
    setLoading(false)
  }

  return (
    <div className="w-full px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium bg-gold/15 border-b border-gold/30 text-navy">
      <div className="min-w-0">
        <span className="font-bold">
          {trial.daysLeft} day{trial.daysLeft === 1 ? '' : 's'} left in your {meta.label} trial
        </span>
        {priceText && <span className="hidden sm:inline text-navy/70"> — keep it for {priceText}</span>}
      </div>
      <button onClick={keepIt} disabled={loading}
        className="shrink-0 px-3 py-1.5 rounded-md bg-navy text-gold text-xs font-bold hover:bg-navy-light disabled:opacity-60">
        {loading ? 'Starting…' : `Keep ${meta.label}`}
      </button>
    </div>
  )
}

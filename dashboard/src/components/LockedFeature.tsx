import type { ReactNode } from 'react'
import { usePlanFeatures } from '../hooks/usePlanFeatures'
import type { FeatureGates, PlanTier } from '../hooks/usePlanFeatures'

interface Props {
  featureName: string
  featureKey:  keyof FeatureGates
  description?: string
  upgradeTo?:  PlanTier   // hint which tier unlocks this; auto-derived if omitted
  children:    ReactNode
}

const TIER_PRICE: Record<PlanTier, string> = {
  essentials:   '$399/mo',
  professional: '$699/mo',
  portfolio:    '$1,199/mo',
}

const TIER_LABEL: Record<PlanTier, string> = {
  essentials:   'Essentials',
  professional: 'Professional',
  portfolio:    'Portfolio',
}

/**
 * Renders `children` when the feature is unlocked on the current plan.
 * Otherwise renders a "Upgrade to unlock" overlay card — same navy card
 * background as the rest of the app, with a subtle gold border and a badge.
 *
 * Visual goal: show users WHAT the feature does (so they have something
 * to want), not just blur or hide. The overlay card sits IN PLACE of the
 * children with a small description and CTA.
 */
export default function LockedFeature({
  featureName, featureKey, description, upgradeTo, children,
}: Props) {
  const { features, allTiers, planTier } = usePlanFeatures()

  const unlocked = (() => {
    const v = features[featureKey]
    if (typeof v === 'boolean') return v
    if (typeof v === 'number')  return v > 0   // numeric gates: 0 = locked
    return Boolean(v)
  })()
  if (unlocked) return <>{children}</>

  // Find the lowest tier that unlocks this feature
  const tiers: PlanTier[] = ['essentials', 'professional', 'portfolio']
  const idxNow = tiers.indexOf(planTier)
  const recommendedTier: PlanTier = upgradeTo ?? (() => {
    for (let i = idxNow + 1; i < tiers.length; i++) {
      const t = tiers[i]
      const v = allTiers[t]?.[featureKey]
      const ok = typeof v === 'boolean' ? v : typeof v === 'number' ? v > 0 : Boolean(v)
      if (ok) return t
    }
    return 'professional'
  })()

  return (
    <div className="relative bg-navy/5 border-2 border-gold/30 rounded-xl p-5 flex flex-col items-center justify-center text-center min-h-[160px]">
      <span className="absolute top-2 right-3 text-[9px] uppercase tracking-wide font-bold bg-gold text-white px-2 py-0.5 rounded">
        Upgrade to unlock
      </span>
      <div className="text-3xl mb-2">🔒</div>
      <div className="text-sm font-bold text-navy">{featureName}</div>
      <div className="text-xs text-slate-500 mt-1 max-w-md">
        {description ?? `Available on the ${TIER_LABEL[recommendedTier]} plan.`}
      </div>
      <div className="text-[11px] text-slate-400 mt-1">
        Currently on {TIER_LABEL[planTier]} ({TIER_PRICE[planTier]}). Upgrade to {TIER_LABEL[recommendedTier]} {TIER_PRICE[recommendedTier]}.
      </div>
      <button
        onClick={() => window.alert(`Upgrade to ${TIER_LABEL[recommendedTier]} — coming soon. Email jwilliams8559@gmail.com to discuss.`)}
        className="mt-3 bg-gold text-white text-xs font-bold px-4 py-1.5 rounded-lg hover:bg-gold-dark transition-colors"
      >
        Upgrade to {TIER_LABEL[recommendedTier]} →
      </button>
    </div>
  )
}

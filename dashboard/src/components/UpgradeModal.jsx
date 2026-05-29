import { usePlanFeatures } from '../hooks/usePlanFeatures'

const MAILTO = 'mailto:jwilliams8559@gmail.com'
  + '?subject=' + encodeURIComponent('INNtelligence Upgrade Request')
  + '&body='    + encodeURIComponent('I would like to upgrade my INNtelligence plan.')

// Shown when a user clicks a sidebar item that's locked on their current tier.
// `feature` is one of the keys from usePlanFeatures (e.g. 'guestCrm').
export default function UpgradeModal({ open, feature, onClose }) {
  const { tier, tierLabel, requiredTierFor, requiredTierLabel, requiredTierPrice,
          newFeaturesAtTier, featureLabel } = usePlanFeatures()
  if (!open) return null
  const required = feature ? requiredTierFor(feature) : null
  const requiredLabel = feature ? requiredTierLabel(feature) : ''
  const requiredPrice = feature ? requiredTierPrice(feature) : ''
  const unlockedList  = required ? newFeaturesAtTier(required) : []

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
          <div className="text-gold-light text-xs uppercase tracking-wide font-bold">Upgrade required</div>
          <h3 className="text-xl font-extrabold mt-1">
            This feature requires {requiredLabel || 'a higher plan'}
          </h3>
          {feature && (
            <p className="text-gold-light text-sm mt-1">
              <span className="text-white/70">Locked:</span> {featureLabel(feature)}
            </p>
          )}
          <p className="text-white/70 text-sm mt-3">
            Your current plan: <span className="text-gold font-semibold">{tierLabel}</span>
          </p>
        </div>

        {unlockedList.length > 0 && (
          <div className="mt-5 rounded-xl bg-white/5 border border-white/10 p-4">
            <div className="text-gold-light text-[11px] uppercase tracking-wide font-bold">
              Upgrade to {requiredLabel} {requiredPrice && <span className="text-white/40">· {requiredPrice}</span>}
            </div>
            <div className="text-white/60 text-xs mt-0.5 mb-2">Unlocks:</div>
            <ul className="space-y-1 text-sm">
              {unlockedList.map((l) => (
                <li key={l} className="flex items-center gap-2 text-white/85"><span className="text-gold">✓</span>{l}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 mt-5">
          <button onClick={onClose}
            className="px-4 py-2.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm font-semibold">
            Close
          </button>
          <a href={MAILTO}
            className="px-4 py-2.5 rounded-lg bg-gold text-navy text-sm font-bold text-center hover:bg-gold-light">
            Upgrade Plan
          </a>
        </div>
        <p className="text-[10px] text-white/40 text-center mt-3">
          Stripe checkout coming soon · for now your request goes straight to Jim
        </p>
      </div>
    </div>
  )
}

export { MAILTO as UPGRADE_MAILTO }

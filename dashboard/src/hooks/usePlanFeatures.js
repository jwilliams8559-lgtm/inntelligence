import { useAuth } from '../context/AuthContext'

// Feature flags per plan_tier. founding_member intentionally mirrors boutique.
// Tier ladder: inn ($149) → boutique ($399) → signature ($799) → collection ($1499).
const TIERS = ['inn', 'boutique', 'signature', 'collection']

const BOUTIQUE_ADDS = [
  'guestCrm', 'weddings', 'privateEvents', 'packages', 'giftShop', 'fbYield', 'autopilot',
]
const SIGNATURE_ADDS = ['revenueIntelligence', 'multiProperty', 'advancedAnalytics']
const COLLECTION_ADDS = ['whiteLabel', 'dedicatedSupport', 'apiAccess']

const INN_BASE = [
  'rateCalendar', 'competitiveIntel', 'events', 'otaPublishing',
  'reputation', 'weather', 'historical', 'roiPerformance',
]

const FEATURES_BY_TIER = {
  inn:         new Set(INN_BASE),
  boutique:    new Set([...INN_BASE, ...BOUTIQUE_ADDS]),
  signature:   new Set([...INN_BASE, ...BOUTIQUE_ADDS, ...SIGNATURE_ADDS]),
  collection:  new Set([...INN_BASE, ...BOUTIQUE_ADDS, ...SIGNATURE_ADDS, ...COLLECTION_ADDS]),
  founding_member: new Set([...INN_BASE, ...BOUTIQUE_ADDS]),   // same as boutique
}

// Newly-added features at each tier (used by the upgrade modal).
const NEW_AT_TIER = {
  boutique:   BOUTIQUE_ADDS,
  signature:  SIGNATURE_ADDS,
  collection: COLLECTION_ADDS,
}

// Friendly labels for the upgrade modal.
const FEATURE_LABELS = {
  rateCalendar:        'Rate Calendar',
  competitiveIntel:    'Competitive Intelligence',
  events:              'Events Intelligence',
  otaPublishing:       'OTA Publishing (7 channels)',
  reputation:          'Reputation',
  weather:             'Weather',
  historical:          'Historical Performance',
  roiPerformance:      'ROI Performance',
  guestCrm:            'Guest CRM',
  weddings:            'Weddings',
  privateEvents:       'Private Events',
  packages:            'Packages',
  giftShop:            'Gift Shop',
  fbYield:             'F&B Yield',
  autopilot:           'Autopilot rate publishing',
  revenueIntelligence: 'Revenue Intelligence (gap nights)',
  multiProperty:       'Multi-property console',
  advancedAnalytics:   'Advanced analytics',
  whiteLabel:          'White-label option',
  dedicatedSupport:    'Dedicated support',
  apiAccess:           'API access',
}

const PLAN_LABEL = {
  inn: 'Inn', boutique: 'Boutique',
  signature: 'Signature', collection: 'Collection',
  founding_member: 'Founding Member',
}

const PLAN_PRICE = { inn: '$149/mo', boutique: '$399/mo', signature: '$799/mo', collection: '$1,499/mo' }

// The lowest tier that includes `feature`. Returns null if no paid tier has it.
function _requiredTierFor(feature) {
  for (const t of TIERS) {
    if (FEATURES_BY_TIER[t].has(feature)) return t
  }
  return null
}

export function usePlanFeatures() {
  const { user } = useAuth() || {}
  const rawTier = (user && user.plan_tier) || 'inn'
  const tier = FEATURES_BY_TIER[rawTier] ? rawTier : 'inn'
  const set = FEATURES_BY_TIER[tier]

  const has = (feature) => set.has(feature)

  // Object with boolean flags — `features.guestCRM`, `features.weddings`, etc.
  const flags = {}
  Object.keys(FEATURE_LABELS).forEach((k) => { flags[k] = set.has(k) })
  // Convenience alias matching the spec's naming examples
  flags.guestCRM = flags.guestCrm

  return {
    ...flags,
    has,
    tier,
    tierLabel:    PLAN_LABEL[tier]    || tier,
    requiredTierFor: _requiredTierFor,
    requiredTierLabel: (f) => PLAN_LABEL[_requiredTierFor(f) || ''] || '',
    requiredTierPrice: (f) => PLAN_PRICE[_requiredTierFor(f) || ''] || '',
    newFeaturesAtTier: (t) => (NEW_AT_TIER[t] || []).map((k) => FEATURE_LABELS[k] || k),
    featureLabel: (k) => FEATURE_LABELS[k] || k,
  }
}

export const PLAN_TIERS = TIERS
export const PLAN_LABELS = PLAN_LABEL

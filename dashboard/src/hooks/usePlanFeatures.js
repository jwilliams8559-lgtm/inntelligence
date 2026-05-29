import { useAuth } from '../context/AuthContext'

// Feature flags per plan_tier. founding_member intentionally mirrors professional.
const TIERS = ['starter', 'professional', 'enterprise', 'premium']

const PRO_ADDS = [
  'guestCrm', 'weddings', 'privateEvents', 'packages', 'giftShop', 'fbYield', 'autopilot',
]
const ENT_ADDS = ['revenueIntelligence', 'multiProperty', 'advancedAnalytics']
const PREM_ADDS = ['whiteLabel', 'dedicatedSupport', 'apiAccess']

const STARTER_BASE = [
  'rateCalendar', 'competitiveIntel', 'events', 'otaPublishing',
  'reputation', 'weather', 'historical', 'roiPerformance',
]

const FEATURES_BY_TIER = {
  starter:        new Set(STARTER_BASE),
  professional:   new Set([...STARTER_BASE, ...PRO_ADDS]),
  enterprise:     new Set([...STARTER_BASE, ...PRO_ADDS, ...ENT_ADDS]),
  premium:        new Set([...STARTER_BASE, ...PRO_ADDS, ...ENT_ADDS, ...PREM_ADDS]),
  founding_member: new Set([...STARTER_BASE, ...PRO_ADDS]),   // same as professional
}

// Newly-added features at each tier (used by the upgrade modal).
const NEW_AT_TIER = {
  professional: PRO_ADDS,
  enterprise:   ENT_ADDS,
  premium:      PREM_ADDS,
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
  starter: 'Starter', professional: 'Professional',
  enterprise: 'Enterprise', premium: 'Premium',
  founding_member: 'Founding Member',
}

const PLAN_PRICE = { starter: '$399/mo', professional: '$699/mo', enterprise: '$1,200/mo', premium: '$2,400/mo' }

// The lowest tier that includes `feature`. Returns null if no paid tier has it.
function _requiredTierFor(feature) {
  for (const t of TIERS) {
    if (FEATURES_BY_TIER[t].has(feature)) return t
  }
  return null
}

export function usePlanFeatures() {
  const { user } = useAuth() || {}
  const rawTier = (user && user.plan_tier) || 'starter'
  const tier = FEATURES_BY_TIER[rawTier] ? rawTier : 'starter'
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

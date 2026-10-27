import { useAuth } from '../context/AuthContext'
import { useFeatureAccess } from '../context/FeatureAccessContext'

// ─────────────────────────────────────────────────────────────────────────────
//  Client mirror of engine/features.py. The SERVER is authoritative for access;
//  this catalog drives synchronous rendering (sidebar locks, labels, prices)
//  before the /api/features/access snapshot loads, and in demo / open mode.
//  Keep min_tier values in sync with engine/features.py.
// ─────────────────────────────────────────────────────────────────────────────
const TIER_ORDER = ['inn', 'boutique', 'signature', 'collection']
const TIER_LABEL = { inn: 'Inn', boutique: 'Boutique', signature: 'Signature',
                     collection: 'Collection', founding_member: 'Founding Member' }
const TIER_PRICE = { inn: 149, boutique: 399, signature: 799, collection: 1499 }

const FEATURE_CATALOG = {
  rate_calendar:      { min_tier: 'inn',        label: 'Rate Calendar',            value: '90-day AI rate recommendations for every room, every night.' },
  dynamic_pricing:    { min_tier: 'inn',        label: 'Dynamic Pricing',          value: 'Demand-based pricing with up to 4 rate updates a day.' },
  competitive_intel:  { min_tier: 'inn',        label: 'Competitive Intelligence', value: 'Track competitor rates and position against your comp set.' },
  ota_publishing:     { min_tier: 'inn',        label: 'OTA Publishing',           value: 'Push approved rates to 7 booking channels at once.' },
  guest_crm_basic:    { min_tier: 'inn',        label: 'Guest CRM',                value: 'Guest profiles, stay history, and segments.' },
  reputation:         { min_tier: 'inn',        label: 'Reputation',               value: 'Monitor reviews and ratings across booking sites.' },
  realtime_repricing: { min_tier: 'boutique',   label: 'Real-time Repricing',      value: 'Reprice instantly on every booking and cancellation.' },
  demand_forecast:    { min_tier: 'boutique',   label: 'Demand Forecast',          value: 'Forward-looking occupancy and demand signals.' },
  weather:            { min_tier: 'boutique',   label: 'Weather Intelligence',     value: 'Fold weather-driven demand swings into your rates.' },
  revenue_intel:      { min_tier: 'boutique',   label: 'Revenue Intelligence',     value: 'Find and fill orphan gap nights automatically.' },
  roi_performance:    { min_tier: 'boutique',   label: 'ROI Performance',          value: 'See the revenue lift INNtelligence drives for you.' },
  historical:         { min_tier: 'boutique',   label: 'Historical Performance',   value: 'Benchmark against your own booking history.' },
  events:             { min_tier: 'boutique',   label: 'Events Intelligence',      value: 'Local events that move demand, scored and priced in.' },
  packages:           { min_tier: 'boutique',   label: 'Packages',                 value: 'Build and price revenue-boosting guest packages.' },
  guest_crm_full:     { min_tier: 'boutique',   label: 'Guest CRM + Campaigns',    value: 'Demand-triggered email campaigns to past guests.' },
  fb_yield:           { min_tier: 'signature',  label: 'F&B Yield',                value: 'Yield-manage restaurant covers and F&B revenue.' },
  weddings:           { min_tier: 'signature',  label: 'Weddings',                 value: 'Run your wedding inquiry-to-booking pipeline and pricing.' },
  private_events:     { min_tier: 'signature',  label: 'Private Events',           value: 'Price and manage private event bookings.' },
  gift_shop:          { min_tier: 'signature',  label: 'Gift Shop',                value: 'Sell branded goods and track margin per item.' },
  autopilot:          { min_tier: 'signature',  label: 'Autopilot',                value: 'Hands-off rate publishing while you sleep.' },
  demand_alerts:      { min_tier: 'signature',  label: 'Demand Alerts',            value: 'Surge / competitor / festival / gap alerts in real time.' },
  management_console: { min_tier: 'collection', label: 'Management Console',       value: 'Operate every property from a single console.' },
  portfolio_analytics:{ min_tier: 'collection', label: 'Portfolio Analytics',      value: 'Cross-property revenue analytics and benchmarking.' },
}

const _rank = (t) => {
  const pt = t === 'founding_member' ? 'boutique' : t
  const i = TIER_ORDER.indexOf(pt)
  return i < 0 ? 0 : i
}
const _tierIncludes = (planTier, key) => {
  const m = FEATURE_CATALOG[key]
  return m ? _rank(planTier) >= _rank(m.min_tier) : false
}

export function usePlanFeatures() {
  const { user } = useAuth() || {}
  const { snapshot, startTrial, refresh } = useFeatureAccess()

  const rawTier = (user && user.plan_tier) || 'inn'
  const tier = TIER_LABEL[rawTier] ? rawTier : 'inn'
  const isAdmin = !!(snapshot && snapshot.is_admin)

  // Authoritative access when the snapshot is loaded; else tier-only fallback.
  const has = (key) => {
    if (snapshot && snapshot.features && snapshot.features[key]) return snapshot.features[key].access
    return _tierIncludes(tier, key)
  }
  const inTier = (key) => {
    if (snapshot && snapshot.features && snapshot.features[key]) return snapshot.features[key].in_tier
    return isAdmin || _tierIncludes(tier, key)
  }

  const featureMeta = (key) => {
    const snap = snapshot && snapshot.features && snapshot.features[key]
    const cat = FEATURE_CATALOG[key] || {}
    const mt = (snap && snap.min_tier) || cat.min_tier || 'boutique'
    return {
      key,
      label: (snap && snap.label) || cat.label || key,
      value: (snap && snap.value) || cat.value || '',
      limits: (snap && snap.limits) || {},
      requiredTier: mt,
      requiredTierLabel: TIER_LABEL[mt] || mt,
      price: (snap && snap.price) || TIER_PRICE[mt],
    }
  }

  // Per-feature trial state. Falls back to optimistic values before load.
  const trialInfo = (key) => {
    const snap = snapshot && snapshot.features && snapshot.features[key]
    if (snap) {
      return {
        active: snap.trial.active, used: snap.trial.used,
        daysLeft: snap.trial.days_left, endsAt: snap.trial.ends_at,
        canTrial: snap.can_trial, reason: snap.trial_reason,
      }
    }
    const locked = !_tierIncludes(tier, key)
    return { active: false, used: false, daysLeft: null, endsAt: null,
             canTrial: locked, reason: null }
  }

  return {
    tier,
    tierLabel: TIER_LABEL[tier] || tier,
    isAdmin,
    has,
    inTier,
    featureMeta,
    trialInfo,
    startTrial,
    refresh,
    trialLimit: (snapshot && snapshot.trial_limit) || 2,
    activeTrialCount: (snapshot && snapshot.active_trial_count) || 0,
    catalog: FEATURE_CATALOG,
  }
}

export const PLAN_TIERS = TIER_ORDER
export const PLAN_LABELS = TIER_LABEL
export const FEATURE_KEYS = Object.keys(FEATURE_CATALOG)

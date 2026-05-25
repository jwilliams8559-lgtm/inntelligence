import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type PlanTier = 'essentials' | 'professional' | 'portfolio' | 'enterprise'

export interface FeatureGates {
  max_competitors:      number
  calendar_days:        number
  max_events:           number
  fb_module:            boolean
  fb_yield_module?:     boolean
  packages_module:      boolean
  gift_shop_module:     boolean
  optimization_engine:  boolean
  autopilot:            boolean
  guest_crm:            boolean
  management_console:   boolean
  eve_analysis?:        boolean
  annual_review?:       boolean
  reputation?:          boolean
  direct_booking_tools?:boolean
  gap_night_analysis?:  boolean
  weather_intel?:       boolean
  performance_report?:  boolean
  competitive_response?:boolean
  behavior_tracking?:   boolean
  historical_trends?:   boolean
  multi_property?:      boolean
  white_label?:         boolean
  api_access?:          boolean
  price_per_month:      number
  label:                string
}

export interface PlanContextValue {
  planTier:  PlanTier
  features:  FeatureGates
  allTiers:  Record<PlanTier, FeatureGates>
  isLoading: boolean
  refresh:   () => void
}

const DEFAULT_FEATURES: FeatureGates = {
  max_competitors: 10, calendar_days: 90, max_events: 999,
  fb_module: true, packages_module: true, gift_shop_module: true,
  optimization_engine: true, autopilot: true, guest_crm: true,
  management_console: true, price_per_month: 699, label: 'Professional',
}

const Ctx = createContext<PlanContextValue>({
  planTier: 'professional',
  features: DEFAULT_FEATURES,
  allTiers: { essentials: DEFAULT_FEATURES, professional: DEFAULT_FEATURES, portfolio: DEFAULT_FEATURES, enterprise: DEFAULT_FEATURES },
  isLoading: true,
  refresh: () => {},
})

export function PlanFeaturesProvider({ children }: { children: ReactNode }) {
  const [planTier,  setPlanTier]  = useState<PlanTier>('professional')
  const [features,  setFeatures]  = useState<FeatureGates>(DEFAULT_FEATURES)
  const [allTiers,  setAllTiers]  = useState<Record<PlanTier, FeatureGates>>({
    essentials: DEFAULT_FEATURES, professional: DEFAULT_FEATURES, portfolio: DEFAULT_FEATURES, enterprise: DEFAULT_FEATURES,
  })
  const [isLoading, setIsLoading] = useState(true)

  async function fetchConfig() {
    setIsLoading(true)
    try {
      const r = await fetch('/api/property-config')
      const j = await r.json()
      if (j.plan_tier) setPlanTier(j.plan_tier as PlanTier)
      if (j.features)  setFeatures(j.features)
      if (j.all_tiers) setAllTiers(j.all_tiers)
    } catch {
      // Fallback — keep defaults
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { void fetchConfig() }, [])

  return (
    <Ctx.Provider value={{ planTier, features, allTiers, isLoading, refresh: fetchConfig }}>
      {children}
    </Ctx.Provider>
  )
}

export function usePlanFeatures(): PlanContextValue {
  return useContext(Ctx)
}

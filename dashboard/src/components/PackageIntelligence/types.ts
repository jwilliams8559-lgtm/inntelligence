// Shared types for the Package Intelligence UI.

export interface NationalPackage {
  id: string
  rank: number
  name: string
  prevalence_pct: number
  category: string
  icon: string
  typical_components: string[]
  national_avg_upsell: number
  national_range: [number, number]
  national_take_rate: number
  operational_complexity: 'low' | 'medium' | 'high'
  lead_time_days: number
  seasonality: 'year_round' | 'seasonal'
  seasonality_months?: number[]
  best_room_types: string[]
  competitive_notes: string
  revenue_model: 'fixed_add_on' | 'per_person' | 'pct_of_rate'

  // Server-computed
  est_monthly_rev: number
  est_monthly_label: string
  price_range_label: string
  competitors_offering: string[]
  competitor_avg_price: number | null
  fit_score: number
  fit_label: 'Excellent fit' | 'Strong fit' | 'Good fit' | 'Consider'

  // Present only on recommendations
  recommended_price?: number
  pricing_rationale?: string
}

export interface CompetitiveComparisonRow {
  package_id: string
  package_name: string
  icon: string
  category: string
  national_avg: number
  recommended_price: number
  competitors_offering: string[]
  competitor_count: number
  competitor_avg_price: number | null
  competitive_gap: 'Differentiator' | 'Low competition' | 'Competitive' | 'Saturated'
  your_opportunity: string
  fit_score: number
  fit_label: string
}

export interface ActivePackage {
  id: string
  icon: string
  name: string
  components: string
  description: string
  upsell_price: number
  take_rate: number
  seasonal: string | null
  active: boolean
  coming_soon: boolean
  est_monthly_rev: number
  est_monthly_label: string
}

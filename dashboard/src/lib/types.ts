export interface Tenant   { id: string; name: string; slug: string }
export interface Property { id: string; tenant_id: string; name: string; city: string; state: string; timezone: string }

export interface RoomType {
  id: string; name: string
  base_rate: number; min_rate: number; max_rate: number
  bathroom_type: string | null; bathroom_premium: number | null
  total_count: number
}

export interface RateRec {
  id: string; tenant_id: string; property_id: string; room_type_id: string
  target_date: string; recommended_rate: number | null; current_rate: number | null
  demand_score: number | null; confidence_score: number | null
  reasoning: string | null
  status: 'pending'|'approved'|'rejected'|'auto_published'|'published'|'publish_failed'
  minimum_stay_rec: number | null
  published_at: string | null
  room_types?: RoomType
}

export interface OccSnapshot {
  snapshot_date: string; room_type_id: string
  occupancy_rate: number; adr: number; revpar: number
  rooms_available: number; rooms_occupied: number
}

export interface Booking {
  id: string; check_in: string; check_out: string
  rate_paid: number; booking_source: string; room_type_id: string
  booked_at: string | null
}

export interface CompetitorProp {
  id: string; competitor_name: string | null; name: string | null
  booking_com_id: string | null; active: boolean
  property_tier?: number | null
  property_category?: string | null
  room_count?: number | null
  trip_advisor_rating?: number | null
  distance_miles?: number | null
}

export interface CompRate {
  id: string; competitor_id: string; rate_date: string
  rate_amount: number | null; is_sold_out: boolean; is_stale?: boolean
  competitor_properties?: { competitor_name: string | null; name: string | null }
}

export interface QualityScore {
  id: string; room_type_id: string; total_score: number | null
  furniture_quality: number|null; linens_quality: number|null
  lighting_quality: number|null; bathroom_quality: number|null
  view_quality: number|null; amenity_score: number|null
  staging_score: number|null; overall_aesthetic: number|null
  notes: string | null
}

export type Screen = 'calendar' | 'demand' | 'events' | 'competitive' | 'reputation' | 'fnb' | 'crm' | 'behavior' | 'packages' | 'performance' | 'historical' | 'management' | 'settings'
export type AppRole = 'shg_admin' | 'property_admin' | 'staff' | 'viewer'

export interface Location {
  city: string
  country: string
}

export interface ClickstreamEvent {
  _id?: string
  platform: 'A' | 'B'
  session_id: string
  event_type: 'view' | 'cart' | 'purchase'
  product_id: string
  event_time: string
  device_type: 'mobile' | 'desktop' | 'tablet'
  ip_range: string
  location: Location
  user_agent: string
  hashed_email: string | null
}

export interface SessionLink {
  platform: string
  session_id: string
  linked_at: string
  method: 'deterministic' | 'probabilistic'
  confidence: number
}

export interface UnifiedProfile {
  _id: string
  sessions: SessionLink[]
  event_history: ClickstreamEvent[]
  devices: string[]
  locations: Location[]
  last_intent_profile: string | null
  last_updated: string
}

export interface AdCreative {
  headline: string
  body: string
  cta: string
  product_links: string[]
  generated_at: string
}

export interface AdResponse {
  global_uid: string
  creative: AdCreative
  cached: boolean
  generated_at: string
}

export interface HealthServices {
  mongodb: string
  redis: string
  qdrant: string
  ollama: string
  [key: string]: string
}

export interface HealthStatus {
  status: string
  version: string
  services: HealthServices
}

export interface EvalMetrics {
  deterministic: { precision: number; recall: number; f1: number }
  probabilistic: { precision: number; recall: number; f1: number }
  total_pairs_tested: number
  over_merged_profiles: number
  split_identities: number
}

export interface TrafficMetrics {
  total_events: number
  platform_a_count: number
  platform_b_count: number
  events_by_type: { view: number; cart: number; purchase: number }
  events_last_hour: number
}

export interface ProfilesResponse {
  profiles: UnifiedProfile[]
  total: number
  page: number
}

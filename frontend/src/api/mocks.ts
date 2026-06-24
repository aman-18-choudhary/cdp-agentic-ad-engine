import type { UnifiedProfile, EvalMetrics, TrafficMetrics, ClickstreamEvent } from './types'

export const MOCK_EVAL_METRICS: EvalMetrics = {
  deterministic: { precision: 0.0009, recall: 0.805, f1: 0.0018 },
  probabilistic: { precision: 1.0, recall: 0.76, f1: 0.8636 },
  total_pairs_tested: 400,
  over_merged_profiles: 24,
  split_identities: 87,
}

export const MOCK_TRAFFIC: TrafficMetrics = {
  total_events: 54669,
  platform_a_count: 32801,
  platform_b_count: 21868,
  events_by_type: { view: 40000, cart: 12000, purchase: 2669 },
  events_last_hour: 120,
}

export const MOCK_PROFILE: UnifiedProfile = {
  _id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  sessions: [
    { platform: 'A', session_id: 'sess_abc123', linked_at: new Date().toISOString(), method: 'deterministic', confidence: 0.99 },
    { platform: 'B', session_id: 'sess_xyz789', linked_at: new Date().toISOString(), method: 'probabilistic', confidence: 0.82 },
  ],
  event_history: [],
  devices: ['mobile', 'desktop'],
  locations: [{ city: 'Mumbai', country: 'India' }],
  last_intent_profile: 'User is actively comparing ventilated motorcycle riding gear priced between $150–$300. They have abandoned cart twice on Platform A and viewed 4 similar products on Platform B, indicating high purchase intent.',
  last_updated: new Date().toISOString(),
}

export const MOCK_EVENTS: ClickstreamEvent[] = Array.from({ length: 20 }, (_, i) => ({
  _id: `mock_${i}`,
  platform: i % 3 === 0 ? 'A' : 'B',
  session_id: `sess_mock_${i}`,
  event_type: (['view', 'cart', 'purchase'] as const)[i % 3],
  product_id: `prod_${Math.floor(i / 2)}`,
  event_time: new Date(Date.now() - i * 120000).toISOString(),
  device_type: (['mobile', 'desktop', 'tablet'] as const)[i % 3],
  ip_range: '192.168.1.0/24',
  location: { city: 'Mumbai', country: 'India' },
  user_agent: 'Mozilla/5.0 (CDP Simulator)',
  hashed_email: null,
}))

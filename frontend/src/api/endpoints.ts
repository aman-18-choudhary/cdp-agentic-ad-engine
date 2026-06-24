import { apiClient } from './client'
import type {
  ClickstreamEvent, UnifiedProfile, AdResponse,
  HealthStatus, EvalMetrics, TrafficMetrics, ProfilesResponse,
} from './types'

export const getHealth = () =>
  apiClient.get<HealthStatus>('/health').then(r => r.data)

export const postEvent = (event: ClickstreamEvent) =>
  apiClient.post<{ accepted: boolean; event_id: string; message: string }>('/event', event).then(r => r.data)

export const getProfile = (uid: string) =>
  apiClient.get<{ profile: UnifiedProfile }>(`/profile/${uid}`).then(r => r.data.profile)

export const getAdCreative = (uid: string) =>
  apiClient.get<AdResponse>(`/ad/${uid}`).then(r => r.data)

export const regenerateAd = (uid: string) =>
  apiClient.post<AdResponse>(`/ad/regenerate/${uid}`).then(r => r.data)

export const getRecentEvents = (limit = 50) =>
  apiClient.get<ClickstreamEvent[]>(`/events/recent?limit=${limit}`).then(r => r.data)

export const listProfiles = (page = 1, limit = 20) =>
  apiClient.get<ProfilesResponse>(`/profiles?page=${page}&limit=${limit}`).then(r => r.data)

export const getEvalMetrics = () =>
  apiClient.get<EvalMetrics>('/metrics/evaluation').then(r => r.data)

export const getTrafficMetrics = () =>
  apiClient.get<TrafficMetrics>('/metrics/traffic').then(r => r.data)

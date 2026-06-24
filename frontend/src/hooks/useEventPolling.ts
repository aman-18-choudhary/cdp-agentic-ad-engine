import { useQuery } from '@tanstack/react-query'
import { getRecentEvents } from '@/api/endpoints'
import type { ClickstreamEvent } from '@/api/types'

export function useEventPolling(limit = 50, intervalMs = 2000) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['events', limit],
    queryFn: () => getRecentEvents(limit),
    refetchInterval: intervalMs,
  })

  return {
    events: Array.isArray(data) ? data : ([] as ClickstreamEvent[]),
    isLoading,
    error,
  }
}

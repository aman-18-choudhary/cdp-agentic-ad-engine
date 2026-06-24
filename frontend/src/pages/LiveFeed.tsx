import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getTrafficMetrics, getRecentEvents, postEvent } from '@/api/endpoints'
import { useEventPolling } from '@/hooks/useEventPolling'
import MetricCard from '@/components/shared/MetricCard'
import {
  Activity, Send, Filter, ChevronDown, RefreshCw,
} from 'lucide-react'
import type { ClickstreamEvent } from '@/api/types'

const eventRowColor = (type: string) => {
  switch (type) {
    case 'purchase': return 'bg-cdp-success/5 border-l-cdp-success'
    case 'cart': return 'bg-cdp-warning/5 border-l-cdp-warning'
    default: return 'bg-transparent border-l-transparent'
  }
}

function generateMockEvent(): Partial<ClickstreamEvent> {
  return {
    platform: Math.random() > 0.6 ? 'A' : 'B',
    session_id: crypto.randomUUID(),
    event_type: (['view', 'cart', 'purchase'] as const)[Math.floor(Math.random() * 3)],
    product_id: `prod_${Math.floor(Math.random() * 500)}`,
    event_time: new Date().toISOString(),
    device_type: (['mobile', 'desktop', 'tablet'] as const)[Math.floor(Math.random() * 3)],
    ip_range: `192.168.${Math.floor(Math.random() * 10)}.0/24`,
    location: { city: 'Mumbai', country: 'India' },
    user_agent: 'Mozilla/5.0 (CDP Simulator)',
    hashed_email: null,
  }
}

export default function LiveFeed() {
  const { events } = useEventPolling(50, 2000)
  const { data: traffic } = useQuery({
    queryKey: ['traffic'],
    queryFn: getTrafficMetrics,
    refetchInterval: 5000,
  })
  const queryClient = useQueryClient()
  const [filterType, setFilterType] = useState<string>('all')
  const [filterPlatform, setFilterPlatform] = useState<string>('all')
  const [showSimulator, setShowSimulator] = useState(false)

  const mutation = useMutation({
    mutationFn: postEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      queryClient.invalidateQueries({ queryKey: ['traffic'] })
    },
  })

  const emitEvent = () => {
    const event = generateMockEvent() as ClickstreamEvent
    mutation.mutate(event)
  }

  const filtered = events.filter(e => {
    if (filterType !== 'all' && e.event_type !== filterType) return false
    if (filterPlatform !== 'all' && e.platform !== filterPlatform) return false
    return true
  })

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          title="Total Events"
          value={traffic?.total_events.toLocaleString() ?? '...'}
          icon={<Activity size={14} />}
          delay={0}
        />
        <MetricCard
          title="Platform A"
          value={traffic ? `${((traffic.platform_a_count / traffic.total_events) * 100).toFixed(1)}%` : '...'}
          subtitle={`${traffic?.platform_a_count.toLocaleString() ?? '...'} events`}
          delay={0.05}
        />
        <MetricCard
          title="Platform B"
          value={traffic ? `${((traffic.platform_b_count / traffic.total_events) * 100).toFixed(1)}%` : '...'}
          subtitle={`${traffic?.platform_b_count.toLocaleString() ?? '...'} events`}
          delay={0.1}
        />
        <MetricCard
          title="Purchases"
          value={traffic ? `${((traffic.events_by_type.purchase / traffic.total_events) * 100).toFixed(1)}%` : '...'}
          subtitle={`${traffic?.events_by_type.purchase.toLocaleString() ?? '...'} total`}
          delay={0.15}
        />
      </div>

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <select
            value={filterPlatform}
            onChange={e => setFilterPlatform(e.target.value)}
            className="bg-cdp-card border border-white/10 rounded-lg px-3 py-1.5 text-xs text-cdp-text-muted font-mono outline-none"
          >
            <option value="all">All Platforms</option>
            <option value="A">Platform A</option>
            <option value="B">Platform B</option>
          </select>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="bg-cdp-card border border-white/10 rounded-lg px-3 py-1.5 text-xs text-cdp-text-muted font-mono outline-none"
          >
            <option value="all">All Types</option>
            <option value="view">View</option>
            <option value="cart">Cart</option>
            <option value="purchase">Purchase</option>
          </select>
        </div>

        <button
          onClick={() => setShowSimulator(!showSimulator)}
          className="flex items-center gap-1.5 text-xs text-cdp-accent hover:text-cdp-accent/80 transition-colors"
        >
          <Send size={12} />
          Event Simulator
          <ChevronDown size={10} className={showSimulator ? 'rotate-180' : ''} />
        </button>
      </div>

      {showSimulator && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="bg-cdp-card border border-white/5 rounded-xl p-4 overflow-hidden"
        >
          <div className="flex items-center justify-between">
            <div className="text-xs text-cdp-text-muted">
              Click to emit a simulated clickstream event
            </div>
            <button
              onClick={emitEvent}
              disabled={mutation.isPending}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-cdp-accent text-white text-xs font-medium hover:bg-cdp-accent/90 transition-colors disabled:opacity-50"
            >
              {mutation.isPending ? (
                <RefreshCw size={12} className="animate-spin" />
              ) : (
                <Send size={12} />
              )}
              {mutation.isPending ? 'Emitting...' : 'Emit Event'}
            </button>
          </div>
          {mutation.isSuccess && (
            <div className="mt-2 text-[10px] text-cdp-success">
              Event accepted &mdash; ID: {mutation.data.event_id}
            </div>
          )}
          {mutation.isError && (
            <div className="mt-2 text-[10px] text-cdp-danger">
              Failed: {(mutation.error as Error).message}
            </div>
          )}
        </motion.div>
      )}

      <div className="bg-cdp-card border border-white/5 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/5 text-cdp-text-muted">
                <th className="text-left px-4 py-3 font-medium">Time</th>
                <th className="text-left px-4 py-3 font-medium">Platform</th>
                <th className="text-left px-4 py-3 font-medium">Type</th>
                <th className="text-left px-4 py-3 font-medium">Product ID</th>
                <th className="text-left px-4 py-3 font-medium">Device</th>
                <th className="text-left px-4 py-3 font-medium">City</th>
                <th className="text-left px-4 py-3 font-medium">Session</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 100).map((event, i) => (
                <motion.tr
                  key={event._id || i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(i * 0.002, 0.2) }}
                  className={`border-b border-white/5 border-l-2 ${eventRowColor(event.event_type)} hover:bg-white/[0.02] transition-colors`}
                >
                  <td className="px-4 py-2.5 font-mono text-cdp-text-muted">
                    {new Date(event.event_time).toLocaleTimeString('en-US', { hour12: false })}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`font-medium ${event.platform === 'A' ? 'text-cdp-accent' : 'text-cdp-warning'}`}>
                      {event.platform}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`capitalize ${
                      event.event_type === 'purchase' ? 'text-cdp-success' :
                      event.event_type === 'cart' ? 'text-cdp-warning' : 'text-cdp-text-muted'
                    }`}>
                      {event.event_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-cdp-text-muted">{event.product_id}</td>
                  <td className="px-4 py-2.5 text-cdp-text-muted">{event.device_type}</td>
                  <td className="px-4 py-2.5 text-cdp-text-muted">{event.location?.city ?? '—'}</td>
                  <td className="px-4 py-2.5 font-mono text-cdp-text-muted">
                    {event.session_id.substring(0, 8)}...
                  </td>
                </motion.tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-cdp-text-muted text-xs">
                    No events yet. Use the simulator to emit events.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

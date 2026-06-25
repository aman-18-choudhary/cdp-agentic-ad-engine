import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getTrafficMetrics, getRecentEvents, postEvent } from '@/api/endpoints'
import { useEventPolling } from '@/hooks/useEventPolling'
import MetricCard from '@/components/shared/MetricCard'
import {
  Activity, Send, ChevronDown, RefreshCw, Radio, ShoppingCart, CreditCard, Eye,
} from 'lucide-react'
import type { ClickstreamEvent } from '@/api/types'

const typeColors: Record<string, string> = {
  purchase: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  cart: 'bg-amber-50 text-amber-700 border-amber-200',
  view: 'bg-slate-100 text-slate-600 border-slate-200',
}

const typeIcons: Record<string, React.ReactNode> = {
  purchase: <CreditCard size={12} />,
  cart: <ShoppingCart size={12} />,
  view: <Eye size={12} />,
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
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
            className="bg-white border border-cdp-border rounded-lg px-3 py-2 text-xs text-slate-600 font-medium outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-150"
          >
            <option value="all">All Platforms</option>
            <option value="A">Platform A</option>
            <option value="B">Platform B</option>
          </select>
          <select
            value={filterType}
            onChange={e => setFilterType(e.target.value)}
            className="bg-white border border-cdp-border rounded-lg px-3 py-2 text-xs text-slate-600 font-medium outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-150"
          >
            <option value="all">All Types</option>
            <option value="view">View</option>
            <option value="cart">Cart</option>
            <option value="purchase">Purchase</option>
          </select>
        </div>

        <button
          onClick={() => setShowSimulator(!showSimulator)}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-all duration-150"
        >
          <Send size={12} />
          Event Simulator
          <ChevronDown size={12} className={`transition-transform duration-150 ${showSimulator ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {showSimulator && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2 }}
          className="bg-white border border-cdp-border rounded-xl shadow-card p-5 overflow-hidden"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Radio size={14} className="text-slate-400" />
              Click to emit a simulated clickstream event
            </div>
            <button
              onClick={emitEvent}
              disabled={mutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-all duration-150 disabled:opacity-50 shadow-sm"
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
            <div className="mt-3 text-xs text-emerald-600 font-mono">
              Event accepted — ID: {mutation.data.event_id}
            </div>
          )}
          {mutation.isError && (
            <div className="mt-3 text-xs text-red-600">
              Failed: {(mutation.error as Error).message}
            </div>
          )}
        </motion.div>
      )}

      <div className="bg-white border border-cdp-border rounded-xl shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-cdp-border bg-slate-50/80">
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Time</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Platform</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Type</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Product ID</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Device</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">City</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Session</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 100).map((event, i) => (
                <motion.tr
                  key={event._id || i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: Math.min(i * 0.002, 0.2) }}
                  className={`border-b border-cdp-border/60 hover:bg-slate-50 transition-colors duration-100 ${
                    event.event_type === 'purchase' ? 'border-l-2 border-l-emerald-500' :
                    event.event_type === 'cart' ? 'border-l-2 border-l-amber-500' :
                    'border-l-2 border-l-transparent'
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-slate-500 text-[11px]">
                    {new Date(event.event_time).toLocaleTimeString('en-US', { hour12: false })}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                      event.platform === 'A' ? 'text-blue-600 bg-blue-50' : 'text-amber-600 bg-amber-50'
                    }`}>
                      {event.platform}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${typeColors[event.event_type] || 'text-slate-500 bg-slate-50 border-slate-200'}`}>
                      {typeIcons[event.event_type]}
                      <span className="capitalize">{event.event_type}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-500 text-[11px]">{event.product_id}</td>
                  <td className="px-4 py-3 text-slate-500">{event.device_type}</td>
                  <td className="px-4 py-3 text-slate-500">{event.location?.city ?? '—'}</td>
                  <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">
                    {event.session_id.substring(0, 8)}...
                  </td>
                </motion.tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <Radio size={20} className="text-slate-300" />
                      <span className="text-sm text-slate-400 font-medium">No events yet</span>
                      <span className="text-xs text-slate-400">Use the simulator to emit events.</span>
                    </div>
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

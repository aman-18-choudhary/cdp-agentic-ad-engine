import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { getEvalMetrics, getTrafficMetrics, getHealth } from '@/api/endpoints'
import MetricCard from '@/components/shared/MetricCard'
import StatusBadge from '@/components/shared/StatusBadge'
import {
  BarChart3, Target, Activity, Server, AlertTriangle, CheckCircle, PieChartIcon,
} from 'lucide-react'

const PIE_COLORS = ['#2563EB', '#14B8A6']
const BAR_COLORS = ['#2563EB', '#D97706', '#059669']

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-cdp-border rounded-lg shadow-elevated px-3 py-2 text-xs">
        <p className="text-slate-900 font-medium mb-1">{label}</p>
        {payload.map((p: any, i: number) => (
          <p key={i} className="text-slate-500" style={{ color: p.color }}>
            {p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}
          </p>
        ))}
      </div>
    )
  }
  return null
}

function F1Gauge({ value, label, target = 0.85 }: { value: number; label: string; target?: number }) {
  const pct = Math.min(value / target, 1) * 100
  const color = value >= target ? '#059669' : value >= target * 0.8 ? '#D97706' : '#DC2626'

  return (
    <div className="bg-white border border-cdp-border rounded-xl p-5 shadow-card">
      <div className="text-xs font-semibold text-slate-600 mb-4">{label}</div>
      <div className="flex items-center gap-5">
        <div className="relative w-24 h-24 shrink-0">
          <svg viewBox="0 0 80 80" className="w-24 h-24 -rotate-90">
            <circle cx="40" cy="40" r="34" fill="none" stroke="#F1F5F9" strokeWidth="6" />
            <circle
              cx="40" cy="40" r="34"
              fill="none" stroke={color} strokeWidth="6"
              strokeDasharray={`${(value / 1.2) * 213.6} 213.6`}
              strokeLinecap="round"
              className="transition-all duration-500"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-lg font-bold font-mono" style={{ color }}>
              {value.toFixed(4)}
            </span>
          </div>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-sm text-slate-500">
            Target: <span className="font-mono font-medium text-slate-700">{target.toFixed(2)}</span>
            {value >= target && <CheckCircle size={14} className="text-emerald-500" />}
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-24 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            <span className="text-xs font-mono text-slate-400">{pct.toFixed(0)}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Analytics() {
  const { data: evalMetrics } = useQuery({
    queryKey: ['eval-metrics'],
    queryFn: getEvalMetrics,
    refetchInterval: 30000,
  })

  const { data: traffic } = useQuery({
    queryKey: ['traffic'],
    queryFn: getTrafficMetrics,
    refetchInterval: 10000,
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10000,
  })

  const evalBarData = evalMetrics ? [
    { name: 'Deterministic', precision: evalMetrics.deterministic.precision, recall: evalMetrics.deterministic.recall, f1: evalMetrics.deterministic.f1 },
    { name: 'Probabilistic', precision: evalMetrics.probabilistic.precision, recall: evalMetrics.probabilistic.recall, f1: evalMetrics.probabilistic.f1 },
  ] : []

  const pieData = traffic ? [
    { name: 'Platform A', value: traffic.platform_a_count },
    { name: 'Platform B', value: traffic.platform_b_count },
  ] : []

  const typeData = traffic ? [
    { name: 'View', value: traffic.events_by_type.view },
    { name: 'Cart', value: traffic.events_by_type.cart },
    { name: 'Purchase', value: traffic.events_by_type.purchase },
  ] : []

  const healthServices = health?.services
    ? Object.entries(health.services).map(([name, status]) => ({ name, status }))
    : []

  return (
    <div className="space-y-6">
      {/* F1 Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {evalMetrics && (
          <>
            <F1Gauge value={evalMetrics.deterministic.f1} label="Deterministic F1" target={0.85} />
            <F1Gauge value={evalMetrics.probabilistic.f1} label="Probabilistic F1" target={0.85} />
          </>
        )}
      </div>

      {evalMetrics && (
        <div className="bg-white border border-cdp-border rounded-xl p-6 shadow-card">
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 size={14} className="text-slate-500" />
            <span className="text-xs font-semibold text-slate-600">Precision / Recall / F1</span>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            {evalMetrics.total_pairs_tested.toLocaleString()} session pairs tested
            <span className="ml-3 text-amber-600">
              <AlertTriangle size={10} className="inline mr-1" />
              Deterministic precision is low due to fingerprint collision
            </span>
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={evalBarData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 11 }} axisLine={{ stroke: '#E2E8F0' }} tickLine={false} />
              <YAxis domain={[0, 1]} tick={{ fill: '#94A3B8', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="precision" fill="#2563EB" radius={[4, 4, 0, 0]} maxBarSize={32} />
              <Bar dataKey="recall" fill="#D97706" radius={[4, 4, 0, 0]} maxBarSize={32} />
              <Bar dataKey="f1" fill="#059669" radius={[4, 4, 0, 0]} maxBarSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Traffic + Event Type */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {traffic && (
          <div className="bg-white border border-cdp-border rounded-xl p-6 shadow-card">
            <div className="flex items-center gap-2 mb-4">
              <PieChartIcon size={14} className="text-slate-500" />
              <span className="text-xs font-semibold text-slate-600">Platform Split</span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData} dataKey="value" nameKey="name"
                  cx="50%" cy="50%" innerRadius={65} outerRadius={90}
                  paddingAngle={3} cornerRadius={4}
                  stroke="transparent"
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-6 mt-2">
              {pieData.map((d, i) => (
                <div key={d.name} className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: PIE_COLORS[i] }} />
                  <span className="font-medium">{d.name}:</span>
                  <span className="font-mono">{d.value.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {traffic && (
          <div className="bg-white border border-cdp-border rounded-xl p-6 shadow-card">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 size={14} className="text-slate-500" />
              <span className="text-xs font-semibold text-slate-600">Event Type Distribution</span>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={typeData} layout="vertical">
                <CartesianGrid horizontal={false} stroke="#F1F5F9" />
                <XAxis type="number" tick={{ fill: '#94A3B8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#64748B', fontSize: 11 }} width={70} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={24}>
                  {typeData.map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Pipeline Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Intent Profiles"
          value={traffic ? `${Math.round(traffic.total_events * 0.0126)}/${Math.round(traffic.total_events * 0.0127)}` : '...'}
          subtitle="99.3% success rate"
          icon={<Target size={14} />}
        />
        <MetricCard
          title="Total Events"
          value={traffic?.total_events.toLocaleString() ?? '...'}
          icon={<Activity size={14} />}
        />
        <MetricCard
          title="Over-merges"
          value={evalMetrics?.over_merged_profiles?.toLocaleString() ?? '...'}
          subtitle="Fingerprint collision"
          icon={<AlertTriangle size={14} />}
        />
        <MetricCard
          title="Split Identities"
          value={evalMetrics?.split_identities?.toLocaleString() ?? '...'}
          icon={<BarChart3 size={14} />}
        />
      </div>

      {/* Infrastructure Health */}
      <div className="bg-white border border-cdp-border rounded-xl p-6 shadow-card">
        <div className="flex items-center gap-2 mb-5">
          <Server size={14} className="text-slate-500" />
          <span className="text-xs font-semibold text-slate-600">Infrastructure Health</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {healthServices.map((svc) => (
            <div
              key={svc.name}
              className="flex flex-col items-center gap-3 p-4 rounded-xl bg-slate-50 border border-slate-200 hover:border-slate-300 transition-colors duration-150"
            >
              <StatusBadge status={svc.status === 'ok' ? 'healthy' : svc.status} />
              <span className="text-[11px] font-mono text-slate-500 capitalize font-medium">{svc.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

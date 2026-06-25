import { motion } from 'framer-motion'

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: React.ReactNode
  trend?: { value: number; positive: boolean }
  delay?: number
}

export default function MetricCard({ title, value, subtitle, icon, trend, delay = 0 }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      className="bg-white border border-cdp-border rounded-xl p-5 shadow-card hover:shadow-card-hover transition-shadow duration-200"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500">
          {title}
        </span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <div className="text-2xl font-semibold text-slate-900 font-mono tabular-nums tracking-tight">
        {value}
      </div>
      {subtitle && (
        <div className="text-xs text-slate-400 mt-1">{subtitle}</div>
      )}
      {trend && (
        <div className={`flex items-center gap-1 mt-2 text-xs font-mono ${trend.positive ? 'text-emerald-600' : 'text-red-600'}`}>
          <span>{trend.positive ? '↑' : '↓'}</span>
          {Math.abs(trend.value).toFixed(1)}%
        </div>
      )}
    </motion.div>
  )
}

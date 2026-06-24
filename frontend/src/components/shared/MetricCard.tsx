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
      transition={{ duration: 0.4, delay }}
      className="bg-cdp-card border border-white/5 rounded-xl p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider">
          {title}
        </span>
        {icon && <span className="text-cdp-accent">{icon}</span>}
      </div>
      <div className="text-xl font-bold font-mono text-cdp-text tabular-nums">
        {value}
      </div>
      {subtitle && (
        <div className="text-[10px] text-cdp-text-muted mt-0.5">{subtitle}</div>
      )}
      {trend && (
        <div className={`flex items-center gap-1 mt-1 text-[10px] font-mono ${trend.positive ? 'text-cdp-success' : 'text-cdp-danger'}`}>
          <span>{trend.positive ? '↑' : '↓'}</span>
          {Math.abs(trend.value).toFixed(1)}%
        </div>
      )}
    </motion.div>
  )
}

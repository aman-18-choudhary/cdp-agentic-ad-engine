interface StatusBadgeProps {
  status: 'healthy' | 'degraded' | 'down' | string
  size?: 'sm' | 'md'
}

const colors: Record<string, string> = {
  healthy: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  degraded: 'bg-amber-50 text-amber-700 border-amber-200',
  down: 'bg-red-50 text-red-700 border-red-200',
  ok: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  error: 'bg-red-50 text-red-700 border-red-200',
}

const dots: Record<string, string> = {
  healthy: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  down: 'bg-red-500',
  ok: 'bg-emerald-500',
  error: 'bg-red-500',
}

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = size === 'sm' ? 'text-[11px] px-2.5 py-0.5' : 'text-xs px-3 py-1'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${colors[status] || 'bg-slate-50 text-slate-600 border-slate-200'} ${s}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dots[status] || 'bg-slate-400'}`} />
      <span className="capitalize">{status === 'ok' ? 'healthy' : status}</span>
    </span>
  )
}

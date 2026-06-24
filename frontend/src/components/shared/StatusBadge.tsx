interface StatusBadgeProps {
  status: 'healthy' | 'degraded' | 'down' | string
  size?: 'sm' | 'md'
}

const colors: Record<string, string> = {
  healthy: 'bg-cdp-success/10 text-cdp-success border-cdp-success/20',
  degraded: 'bg-cdp-warning/10 text-cdp-warning border-cdp-warning/20',
  down: 'bg-cdp-danger/10 text-cdp-danger border-cdp-danger/20',
  ok: 'bg-cdp-success/10 text-cdp-success border-cdp-success/20',
}

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const s = size === 'sm' ? 'text-[10px] px-2 py-0.5' : 'text-xs px-2.5 py-1'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-medium ${colors[status] || 'bg-white/5 text-cdp-text-muted border-white/10'} ${s}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${status === 'healthy' || status === 'ok' ? 'bg-cdp-success' : status === 'degraded' ? 'bg-cdp-warning' : 'bg-cdp-danger'}`} />
      {status}
    </span>
  )
}

import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/api/endpoints'
import { Server, Wifi } from 'lucide-react'

const serviceColors: Record<string, string> = {
  ok: 'bg-cdp-success',
  degraded: 'bg-cdp-warning',
  error: 'bg-cdp-danger',
}

const servicePorts: Record<string, string> = {
  mongodb: '27017',
  redis: '6379',
  qdrant: '6333',
  ollama: '11434',
  redpanda: '19093',
}

export default function TopBar({ title }: { title: string }) {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10_000,
  })

  const allOk = health?.status === 'ok'

  return (
    <header className="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-cdp-card/50">
      <h1 className="text-base font-semibold text-cdp-text">{title}</h1>

      <div className="flex items-center gap-4">
        {health?.services && (
          <div className="hidden md:flex items-center gap-3">
            {Object.entries(health.services).map(([name, status]) => (
              <div
                key={name}
                className="flex items-center gap-1.5 text-[10px] font-mono text-cdp-text-muted group relative"
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    serviceColors[status] || 'bg-cdp-muted'
                  }`}
                />
                <span className="capitalize">{name}</span>
                <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 hidden group-hover:block bg-cdp-card border border-white/10 rounded px-2 py-1 text-[9px] whitespace-nowrap z-10">
                  {name}:{servicePorts[name] || '?'} &middot; {status}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1.5 text-[10px] font-mono">
          <Wifi size={12} className={allOk ? 'text-cdp-success' : 'text-cdp-warning'} />
          <span className={allOk ? 'text-cdp-success' : 'text-cdp-warning'}>
            {allOk ? 'All Healthy' : 'Degraded'}
          </span>
        </div>
      </div>
    </header>
  )
}

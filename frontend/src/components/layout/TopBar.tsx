import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/api/endpoints'
import { Shield, ShieldCheck, Server } from 'lucide-react'

const serviceDot: Record<string, string> = {
  ok: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  error: 'bg-red-500',
}

const serviceColors: Record<string, string> = {
  ok: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  degraded: 'text-amber-700 bg-amber-50 border-amber-200',
  error: 'text-red-700 bg-red-50 border-red-200',
}

export default function TopBar({ title }: { title: string }) {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10_000,
  })

  const allOk = health?.status === 'ok'

  return (
    <header className="h-16 border-b border-cdp-border bg-white sticky top-0 z-30 flex items-center justify-between px-8">
      <h1 className="text-lg font-semibold text-slate-900 tracking-tight">{title}</h1>

      <div className="flex items-center gap-4">
        {health?.services && (
          <div className="hidden md:flex items-center gap-2">
            {Object.entries(health.services).map(([name, status]) => (
              <div
                key={name}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium transition-colors ${
                  serviceColors[status] || 'text-slate-500 bg-slate-50 border-slate-200'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${serviceDot[status] || 'bg-slate-400'}`} />
                <span className="capitalize">{name}</span>
              </div>
            ))}
          </div>
        )}

        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors ${
          allOk
            ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
            : 'text-amber-700 bg-amber-50 border-amber-200'
        }`}>
          {allOk ? <ShieldCheck size={14} /> : <Shield size={14} />}
          <span>{allOk ? 'All Healthy' : 'Degraded'}</span>
        </div>
      </div>
    </header>
  )
}

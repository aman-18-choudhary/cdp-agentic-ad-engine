import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getEvalMetrics } from '@/api/endpoints'
import {
  Activity, Fingerprint, Users, Megaphone, BarChart3,
} from 'lucide-react'

const links = [
  { to: '/', label: 'Live Feed', icon: Activity },
  { to: '/identity', label: 'Identity Explorer', icon: Fingerprint },
  { to: '/profiles', label: 'User Profiles', icon: Users },
  { to: '/ads', label: 'Ad Studio', icon: Megaphone },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
]

export default function Sidebar() {
  const { data: evalMetrics } = useQuery({
    queryKey: ['sidebar-eval'],
    queryFn: getEvalMetrics,
    refetchInterval: 30000,
  })
  const f1 = evalMetrics?.probabilistic?.f1

  return (
    <aside className="w-60 shrink-0 h-screen bg-cdp-card border-r border-white/5 flex flex-col">
      <div className="flex items-center gap-2.5 px-5 h-14 border-b border-white/5">
        <div className="w-7 h-7 rounded-md bg-cdp-accent flex items-center justify-center text-xs font-bold">
          C
        </div>
        <span className="font-semibold text-sm text-cdp-text">CDP Dashboard</span>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-cdp-accent/15 text-cdp-accent font-medium'
                  : 'text-cdp-text-muted hover:text-cdp-text hover:bg-white/5'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-3 border-t border-white/5">
        <div className="text-[10px] text-cdp-muted font-mono">
          CDP v1.0 &middot; F1={f1 ? f1.toFixed(4) : '...'}
        </div>
      </div>
    </aside>
  )
}

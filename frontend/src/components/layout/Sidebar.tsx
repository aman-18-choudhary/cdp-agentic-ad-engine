import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getEvalMetrics } from '@/api/endpoints'
import {
  Activity, Fingerprint, Users, Megaphone, BarChart3, ChevronDown,
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
    <aside className="w-64 shrink-0 h-screen bg-white border-r border-cdp-border flex flex-col">
      <div className="flex items-center gap-3 px-6 h-16 border-b border-cdp-border">
        <div className="w-8 h-8 rounded-lg bg-cdp-accent flex items-center justify-center text-sm font-bold text-white shadow-sm">
          C
        </div>
        <div className="flex flex-col">
          <span className="font-semibold text-sm text-cdp-text">CDP</span>
          <span className="text-[10px] text-cdp-text-muted -mt-0.5">Customer Data Platform</span>
        </div>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-0.5">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150 ${
                isActive
                  ? 'bg-blue-50 text-blue-700 font-medium border-l-2 border-blue-600 ml-0 pl-[10px]'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50 border-l-2 border-transparent ml-0 pl-[10px]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={18} className={isActive ? 'text-blue-600' : 'text-slate-400'} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 py-4 border-t border-cdp-border">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-slate-400 font-medium">Identity Resolution</span>
          <span className="text-[11px] font-mono font-medium text-slate-600">
            F1 <span className="text-slate-900">{f1 ? f1.toFixed(4) : '...'}</span>
          </span>
        </div>
        <div className="mt-1.5 h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-500"
            style={{ width: `${f1 ? Math.min(f1 * 100, 100) : 0}%` }}
          />
        </div>
      </div>
    </aside>
  )
}

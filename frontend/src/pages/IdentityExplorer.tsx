import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getProfile, getEvalMetrics } from '@/api/endpoints'
import StatusBadge from '@/components/shared/StatusBadge'
import MetricCard from '@/components/shared/MetricCard'
import { Search, Copy, Fingerprint, BarChart3, Activity, Globe, User, MapPin, Smartphone, Clock, Network } from 'lucide-react'
import type { UnifiedProfile, SessionLink } from '@/api/types'

function SessionGraph({ sessions }: { sessions: SessionLink[] }) {
  if (sessions.length === 0) return null
  const cx = 120
  const cy = 20
  const radius = 14
  const childY = 60
  const spacing = 80

  return (
    <svg viewBox="0 0 240 90" className="w-full max-w-[240px] h-auto">
      <circle cx={cx} cy={cy} r={radius} fill="#2563EB" opacity={0.15} stroke="#2563EB" strokeWidth={2} />
      <text x={cx} y={cy + 1} textAnchor="middle" fill="#2563EB" fontSize="6" fontWeight="bold">UID</text>
      {sessions.slice(0, 3).map((s, i) => {
        const x = cx + (i - (Math.min(sessions.length, 3) - 1) / 2) * spacing
        const color = s.method === 'deterministic' ? '#2563EB' : s.confidence >= 0.85 ? '#059669' : '#D97706'
        return (
          <g key={i}>
            <line x1={cx} y1={cy + radius} x2={x} y2={childY - radius} stroke={color} strokeWidth={1.5} opacity={0.4} />
            <circle cx={x} cy={childY} r={radius} fill="none" stroke={color} strokeWidth={1.5} />
            <text x={x} y={childY + 1} textAnchor="middle" fill={color} fontSize="5" fontWeight="medium">
              {s.session_id.substring(0, 5)}
            </text>
            <text x={x} y={childY + radius + 8} textAnchor="middle" fill="rgba(100,116,139,0.6)" fontSize="4">
              {s.confidence.toFixed(2)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function IdentityExplorer() {
  const [searchUid, setSearchUid] = useState('')
  const [activeUid, setActiveUid] = useState('')

  const { data: profile, isLoading, error } = useQuery({
    queryKey: ['profile', activeUid],
    queryFn: () => getProfile(activeUid),
    enabled: activeUid.length > 0,
  })

  const { data: evalMetrics } = useQuery({
    queryKey: ['eval-metrics'],
    queryFn: getEvalMetrics,
    refetchInterval: 30000,
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchUid.trim()) setActiveUid(searchUid.trim())
  }

  const copyUid = () => {
    if (profile) navigator.clipboard.writeText(profile._id)
  }

  return (
    <div className="space-y-6">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchUid}
            onChange={e => setSearchUid(e.target.value)}
            placeholder="Enter Global UID to explore..."
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-cdp-border rounded-xl text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-150 font-mono shadow-sm"
          />
        </div>
        <button
          type="submit"
          className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-all duration-150 shadow-sm"
        >
          Search
        </button>
      </form>

      {isLoading && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-5">
            <div className="bg-white border border-cdp-border rounded-xl p-5 shadow-card animate-pulse">
              <div className="h-3 w-24 bg-slate-200 rounded mb-4" />
              <div className="h-20 bg-slate-100 rounded" />
            </div>
            <div className="bg-white border border-cdp-border rounded-xl p-5 shadow-card animate-pulse">
              <div className="h-3 w-20 bg-slate-200 rounded mb-3" />
              <div className="h-4 w-full bg-slate-100 rounded mb-2" />
              <div className="h-4 w-3/4 bg-slate-100 rounded mb-3" />
              <div className="flex gap-2 mb-3">
                <div className="h-5 w-16 bg-slate-100 rounded" />
                <div className="h-5 w-20 bg-slate-100 rounded" />
              </div>
              <div className="h-16 bg-slate-100 rounded" />
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center justify-center py-12">
          <Search size={24} className="text-slate-300 mb-3" />
          <p className="text-sm text-slate-500 font-medium">Profile not found</p>
          <p className="text-xs text-slate-400 mt-1">Try a different UID.</p>
        </div>
      )}

      {profile && !isLoading && (
        <>
          {/* Session Graph + Profile Info */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-6">
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="bg-white border border-cdp-border rounded-xl p-5 shadow-card"
            >
              <div className="flex items-center gap-2 mb-4">
                <Network size={14} className="text-slate-500" />
                <span className="text-xs font-semibold text-slate-600 tracking-wide">Session Graph</span>
              </div>
              <SessionGraph sessions={profile.sessions} />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              className="bg-white border border-cdp-border rounded-xl p-6 shadow-card"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Fingerprint size={16} className="text-blue-600" />
                  <span className="text-sm font-semibold text-slate-900">Global UID</span>
                </div>
                <button
                  onClick={copyUid}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-all duration-150"
                >
                  <Copy size={12} /> Copy
                </button>
              </div>
              <code className="text-xs font-mono text-slate-500 break-all bg-slate-50 px-2 py-1 rounded border border-slate-200 block">{profile._id}</code>

              <div className="flex flex-wrap gap-2 mt-4">
                {profile.devices.map((d, i) => (
                  <span key={i} className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 font-medium border border-slate-200">
                    <Smartphone size={10} />
                    {d}
                  </span>
                ))}
              </div>

              <div className="flex flex-wrap gap-3 mt-3 text-xs text-slate-500">
                {profile.locations.map((l, i) => (
                  <span key={i} className="inline-flex items-center gap-1">
                    <MapPin size={10} />
                    {l.city}, {l.country}
                  </span>
                ))}
              </div>

              {profile.last_intent_profile && (
                <div className="mt-5 p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <User size={12} className="text-blue-600" />
                    <span className="text-[11px] font-semibold text-blue-700">Intent Profile</span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {profile.last_intent_profile}
                  </p>
                </div>
              )}

              <div className="mt-4 flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
                <Clock size={11} />
                Last updated: {new Date(profile.last_updated).toLocaleString()}
              </div>
            </motion.div>
          </div>

          {/* Sessions List */}
          <div className="bg-white border border-cdp-border rounded-xl shadow-card overflow-hidden">
            <div className="px-5 py-4 border-b border-cdp-border bg-slate-50/50">
              <span className="text-xs font-semibold text-slate-600">
                Sessions <span className="text-slate-400 font-normal">({profile.sessions.length})</span>
              </span>
            </div>
            <div className="p-5 space-y-2">
              {profile.sessions.map((s, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200 hover:bg-blue-50/50 hover:border-blue-200 transition-all duration-150">
                  <div className="flex items-center gap-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                      s.platform === 'A' ? 'text-blue-600 bg-blue-50' : 'text-amber-600 bg-amber-50'
                    }`}>
                      Platform {s.platform}
                    </span>
                    <span className="text-[11px] font-mono text-slate-500">{s.session_id.substring(0, 12)}...</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={s.method} size="sm" />
                    <div className="flex items-center gap-1.5">
                      <div className={`h-1.5 w-12 rounded-full bg-slate-200 overflow-hidden`}>
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            s.confidence >= 0.85 ? 'bg-emerald-500' : s.confidence >= 0.6 ? 'bg-amber-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${s.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-[11px] font-mono text-slate-500 min-w-[2.5rem]">
                        {(s.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Match Method Stats */}
      {evalMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricCard
            title="Deterministic Matches"
            value={evalMetrics.deterministic.f1.toFixed(4)}
            subtitle={`Precision: ${evalMetrics.deterministic.precision.toFixed(4)} · Recall: ${evalMetrics.deterministic.recall.toFixed(3)}`}
            icon={<BarChart3 size={14} />}
          />
          <MetricCard
            title="Probabilistic Matches"
            value={evalMetrics.probabilistic.f1.toFixed(4)}
            subtitle={`Precision: ${evalMetrics.probabilistic.precision} · Recall: ${evalMetrics.probabilistic.recall.toFixed(2)} · ${evalMetrics.total_pairs_tested} pairs`}
            icon={<Activity size={14} />}
          />
        </div>
      )}
    </div>
  )
}

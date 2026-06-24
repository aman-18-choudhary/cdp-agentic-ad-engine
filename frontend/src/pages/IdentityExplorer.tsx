import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getProfile, getEvalMetrics } from '@/api/endpoints'
import StatusBadge from '@/components/shared/StatusBadge'
import MetricCard from '@/components/shared/MetricCard'
import { Search, Copy, Fingerprint, BarChart3, Activity, Globe } from 'lucide-react'
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
      {/* Center node */}
      <circle cx={cx} cy={cy} r={radius} fill="#3B82F6" opacity={0.2} stroke="#3B82F6" strokeWidth={2} />
      <text x={cx} y={cy + 1} textAnchor="middle" fill="#3B82F6" fontSize="6" fontWeight="bold">UID</text>

      {/* Edges + child nodes */}
      {sessions.slice(0, 3).map((s, i) => {
        const x = cx + (i - (Math.min(sessions.length, 3) - 1) / 2) * spacing
        const color = s.method === 'deterministic' ? '#3B82F6' : s.confidence >= 0.85 ? '#10B981' : '#F59E0B'
        return (
          <g key={i}>
            <line x1={cx} y1={cy + radius} x2={x} y2={childY - radius} stroke={color} strokeWidth={1.5} opacity={0.5} />
            <circle cx={x} cy={childY} r={radius} fill="none" stroke={color} strokeWidth={1.5} />
            <text x={x} y={childY + 1} textAnchor="middle" fill={color} fontSize="5" fontWeight="medium">
              {s.session_id.substring(0, 5)}
            </text>
            <text x={x} y={childY + radius + 8} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize="4">
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
    <div className="space-y-5">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-cdp-text-muted" />
          <input
            type="text"
            value={searchUid}
            onChange={e => setSearchUid(e.target.value)}
            placeholder="Enter Global UID to explore..."
            className="w-full pl-9 pr-4 py-2.5 bg-cdp-card border border-white/10 rounded-xl text-sm text-cdp-text placeholder:text-cdp-text-muted/50 outline-none focus:border-cdp-accent/50 transition-colors font-mono"
          />
        </div>
        <button
          type="submit"
          className="px-5 py-2.5 rounded-xl bg-cdp-accent text-white text-sm font-medium hover:bg-cdp-accent/90 transition-colors"
        >
          Search
        </button>
      </form>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-cdp-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="text-center py-8 text-cdp-text-muted text-sm">
          Profile not found. Try a different UID.
        </div>
      )}

      {profile && !isLoading && (
        <>
          {/* Session Graph + Profile Info */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-5">
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="bg-cdp-card border border-white/5 rounded-xl p-5"
            >
              <div className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider mb-4">
                Session Graph
              </div>
              <SessionGraph sessions={profile.sessions} />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              className="bg-cdp-card border border-white/5 rounded-xl p-5"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Fingerprint size={14} className="text-cdp-accent" />
                  <span className="text-xs font-medium text-cdp-text">Global UID</span>
                </div>
                <button onClick={copyUid} className="flex items-center gap-1 text-[10px] text-cdp-accent hover:text-cdp-accent/80">
                  <Copy size={10} /> Copy
                </button>
              </div>
              <code className="text-xs font-mono text-cdp-text-muted break-all">{profile._id}</code>

              <div className="flex flex-wrap gap-1.5 mt-3">
                {profile.devices.map((d, i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-cdp-text-muted">
                    {d}
                  </span>
                ))}
              </div>

              <div className="mt-3 text-[10px] text-cdp-text-muted">
                {profile.locations.map((l, i) => (
                  <span key={i} className="mr-3">{l.city}, {l.country}</span>
                ))}
              </div>

              {profile.last_intent_profile && (
                <div className="mt-4 p-3 rounded-lg bg-cdp-accent/5 border border-cdp-accent/10">
                  <div className="text-[10px] font-medium text-cdp-text-muted mb-1">Intent Profile</div>
                  <p className="text-[11px] text-cdp-text-muted leading-relaxed">
                    {profile.last_intent_profile}
                  </p>
                </div>
              )}

              <div className="mt-3 text-[9px] text-cdp-text-muted font-mono">
                Last updated: {new Date(profile.last_updated).toLocaleString()}
              </div>
            </motion.div>
          </div>

          {/* Sessions List */}
          <div className="bg-cdp-card border border-white/5 rounded-xl p-5">
            <div className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider mb-3">
              Sessions ({profile.sessions.length})
            </div>
            <div className="space-y-2">
              {profile.sessions.map((s, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/5">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-medium ${s.platform === 'A' ? 'text-cdp-accent' : 'text-cdp-warning'}`}>
                      Platform {s.platform}
                    </span>
                    <span className="text-[10px] font-mono text-cdp-text-muted">{s.session_id.substring(0, 12)}...</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={s.method} />
                    <span className="text-[10px] font-mono text-cdp-text-muted">
                      {(s.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Match Method Stats */}
      {evalMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { listProfiles, getProfile, getAdCreative } from '@/api/endpoints'
import AdCreativeCard from '@/components/shared/AdCreativeCard'
import { Users, ChevronLeft, ChevronRight, X } from 'lucide-react'
import type { UnifiedProfile } from '@/api/types'

export default function UserProfiles() {
  const [page, setPage] = useState(1)
  const [selectedUid, setSelectedUid] = useState<string | null>(null)
  const limit = 20

  const { data, isLoading } = useQuery({
    queryKey: ['profiles', page],
    queryFn: () => listProfiles(page, limit),
  })

  const { data: detailProfile } = useQuery({
    queryKey: ['profile-detail', selectedUid],
    queryFn: () => getProfile(selectedUid!),
    enabled: !!selectedUid,
  })

  const { data: adData } = useQuery({
    queryKey: ['ad-preview', selectedUid],
    queryFn: () => getAdCreative(selectedUid!),
    enabled: !!selectedUid,
  })

  const profiles = Array.isArray(data?.profiles) ? data.profiles : []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / limit)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-cdp-accent" />
          <span className="text-xs text-cdp-text-muted font-mono">
            {total} total profiles
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="p-1.5 rounded-lg bg-cdp-card border border-white/5 text-cdp-text-muted hover:text-cdp-text disabled:opacity-30"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs font-mono text-cdp-text-muted">
            {page} / {totalPages || 1}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="p-1.5 rounded-lg bg-cdp-card border border-white/5 text-cdp-text-muted hover:text-cdp-text disabled:opacity-30"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-cdp-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="bg-cdp-card border border-white/5 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/5 text-cdp-text-muted">
                <th className="text-left px-4 py-3 font-medium">UID</th>
                <th className="text-left px-4 py-3 font-medium">Sessions</th>
                <th className="text-left px-4 py-3 font-medium">Devices</th>
                <th className="text-left px-4 py-3 font-medium">Last City</th>
                <th className="text-left px-4 py-3 font-medium">Last Seen</th>
                <th className="text-left px-4 py-3 font-medium">Intent</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p, i) => (
                <tr
                  key={p._id}
                  onClick={() => setSelectedUid(p._id)}
                  className="border-b border-white/5 hover:bg-white/[0.02] cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-cdp-accent">
                    {p._id.substring(0, 8)}...
                  </td>
                  <td className="px-4 py-3 text-cdp-text-muted">{p.sessions?.length ?? 0}</td>
                  <td className="px-4 py-3 text-cdp-text-muted">{p.devices?.length ?? 0}</td>
                  <td className="px-4 py-3 text-cdp-text-muted">
                    {p.locations?.[0]?.city ?? '—'}
                  </td>
                  <td className="px-4 py-3 font-mono text-cdp-text-muted">
                    {p.last_updated ? new Date(p.last_updated).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-cdp-text-muted max-w-[200px] truncate">
                    {p.last_intent_profile ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail Drawer */}
      <AnimatePresence>
        {selectedUid && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="bg-cdp-card border border-white/5 rounded-xl p-5"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-cdp-accent">{selectedUid}</code>
                <button
                  onClick={() => navigator.clipboard.writeText(selectedUid)}
                  className="text-[9px] text-cdp-text-muted hover:text-cdp-text"
                >
                  Copy
                </button>
              </div>
              <button
                onClick={() => setSelectedUid(null)}
                className="p-1 rounded hover:bg-white/5 text-cdp-text-muted"
              >
                <X size={14} />
              </button>
            </div>

            {detailProfile?.last_intent_profile && (
              <div className="p-3 rounded-lg bg-cdp-accent/5 border border-cdp-accent/10 mb-4">
                <div className="text-[10px] font-medium text-cdp-text-muted mb-1">Intent Profile</div>
                <p className="text-xs text-cdp-text-muted leading-relaxed">
                  {detailProfile.last_intent_profile}
                </p>
              </div>
            )}

            <div className="mb-4">
              <div className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider mb-2">
                Sessions Timeline
              </div>
              <div className="space-y-1.5">
                {detailProfile?.sessions?.map((s, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className={`w-2 h-2 rounded-full ${s.platform === 'A' ? 'bg-cdp-accent' : 'bg-cdp-warning'}`} />
                    <span className="font-mono text-cdp-text-muted">
                      Platform {s.platform} &middot; {s.method} &middot; {(s.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {adData && (
              <div className="max-w-sm">
                <div className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider mb-2">
                  Ad Preview
                </div>
                <AdCreativeCard ad={adData.creative} />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

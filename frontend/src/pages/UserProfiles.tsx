import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { listProfiles, getProfile, getAdCreative } from '@/api/endpoints'
import AdCreativeCard from '@/components/shared/AdCreativeCard'
import { Users, ChevronLeft, ChevronRight, X, Copy, User, Calendar, MapPin, Smartphone } from 'lucide-react'
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-slate-400" />
          <span className="text-xs text-slate-500 font-mono font-medium">
            {total.toLocaleString()} total profiles
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg border border-cdp-border bg-white text-slate-500 hover:text-slate-700 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-xs font-mono text-slate-500 font-medium min-w-[4rem] text-center">
            {page} / {totalPages || 1}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="inline-flex items-center justify-center w-8 h-8 rounded-lg border border-cdp-border bg-white text-slate-500 hover:text-slate-700 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-150"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="bg-white border border-cdp-border rounded-xl shadow-card overflow-hidden animate-pulse">
          <div className="p-4 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4">
                <div className="h-4 w-20 bg-slate-200 rounded" />
                <div className="h-4 w-12 bg-slate-200 rounded" />
                <div className="h-4 w-12 bg-slate-200 rounded" />
                <div className="h-4 w-16 bg-slate-200 rounded" />
                <div className="h-4 w-16 bg-slate-200 rounded" />
                <div className="h-4 flex-1 bg-slate-200 rounded" />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-white border border-cdp-border rounded-xl shadow-card overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-cdp-border bg-slate-50/80">
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">UID</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Sessions</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Devices</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Last City</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Last Seen</th>
                <th className="text-left px-4 py-3.5 font-semibold text-slate-500 text-[11px] tracking-wide">Intent</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p, i) => (
                <tr
                  key={p._id}
                  onClick={() => setSelectedUid(p._id)}
                  className="border-b border-cdp-border/60 hover:bg-slate-50 cursor-pointer transition-colors duration-100"
                >
                  <td className="px-4 py-3.5 font-mono text-blue-600 font-medium">
                    {p._id.substring(0, 8)}...
                  </td>
                  <td className="px-4 py-3.5 text-slate-500 font-medium">{p.sessions?.length ?? 0}</td>
                  <td className="px-4 py-3.5 text-slate-500 font-medium">{p.devices?.length ?? 0}</td>
                  <td className="px-4 py-3.5 text-slate-500">
                    {p.locations?.[0]?.city ?? '—'}
                  </td>
                  <td className="px-4 py-3.5 font-mono text-slate-400 text-[11px]">
                    {p.last_updated ? new Date(p.last_updated).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3.5 text-slate-500 max-w-[200px] truncate">
                    {p.last_intent_profile ?? '—'}
                  </td>
                </tr>
              ))}
              {profiles.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <Users size={20} className="text-slate-300" />
                      <span className="text-sm text-slate-400 font-medium">No profiles found</span>
                    </div>
                  </td>
                </tr>
              )}
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
            transition={{ duration: 0.2 }}
            className="bg-white border border-cdp-border rounded-xl shadow-card p-6"
          >
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono text-blue-600 font-medium bg-blue-50 px-2 py-1 rounded border border-blue-200">
                  {selectedUid}
                </code>
                <button
                  onClick={() => navigator.clipboard.writeText(selectedUid)}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded transition-all duration-150"
                >
                  <Copy size={10} /> Copy
                </button>
              </div>
              <button
                onClick={() => setSelectedUid(null)}
                className="inline-flex items-center justify-center w-7 h-7 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-all duration-150"
              >
                <X size={14} />
              </button>
            </div>

            {detailProfile?.last_intent_profile && (
              <div className="p-4 rounded-lg bg-blue-50 border border-blue-200 mb-5">
                <div className="flex items-center gap-1.5 mb-1">
                  <User size={12} className="text-blue-600" />
                  <span className="text-[11px] font-semibold text-blue-700">Intent Profile</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {detailProfile.last_intent_profile}
                </p>
              </div>
            )}

            <div className="mb-5">
              <div className="flex items-center gap-1.5 mb-3">
                <Calendar size={12} className="text-slate-500" />
                <span className="text-[11px] font-semibold text-slate-600 tracking-wide">Sessions Timeline</span>
                <span className="text-slate-400 text-[11px]">({detailProfile?.sessions?.length ?? 0})</span>
              </div>
              <div className="space-y-1">
                {detailProfile?.sessions?.map((s, i) => (
                  <div key={i} className="flex items-center gap-3 py-1.5">
                    <div className="flex flex-col items-center">
                      <span className={`w-2 h-2 rounded-full ${s.platform === 'A' ? 'bg-blue-500' : 'bg-amber-500'}`} />
                      {i < (detailProfile?.sessions?.length ?? 0) - 1 && (
                        <div className="w-px h-4 bg-slate-200" />
                      )}
                    </div>
                    <span className="text-xs font-mono text-slate-500">
                      <span className={`font-semibold ${s.platform === 'A' ? 'text-blue-600' : 'text-amber-600'}`}>
                        Platform {s.platform}
                      </span> &middot; <span className="capitalize">{s.method}</span> &middot; {(s.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {adData && (
              <div className="max-w-sm">
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-[11px] font-semibold text-slate-600 tracking-wide">Ad Preview</span>
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

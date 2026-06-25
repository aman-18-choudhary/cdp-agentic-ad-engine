import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getAdCreative, regenerateAd } from '@/api/endpoints'
import AdCreativeCard from '@/components/shared/AdCreativeCard'
import { Search, Smartphone, Monitor, Loader2, Zap, RefreshCw } from 'lucide-react'

export default function AdStudio() {
  const [uid, setUid] = useState('')
  const [searchUid, setSearchUid] = useState('')
  const [mobileView, setMobileView] = useState(false)
  const queryClient = useQueryClient()

  const { data: adResponse, isLoading, isError } = useQuery({
    queryKey: ['ad', searchUid],
    queryFn: () => getAdCreative(searchUid),
    enabled: searchUid.length > 0,
  })

  const mutation = useMutation({
    mutationFn: () => regenerateAd(searchUid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ad', searchUid] })
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (uid.trim()) setSearchUid(uid.trim())
  }

  const [batchUids, setBatchUids] = useState('')
  const [batchResults, setBatchResults] = useState<any[]>([])

  const handleBatchFetch = async () => {
    const uids = batchUids.split(',').map(u => u.trim()).filter(Boolean)
    const results = await Promise.allSettled(uids.map(u => getAdCreative(u)))
    setBatchResults(results.map((r, i) => ({
      uid: uids[i],
      data: r.status === 'fulfilled' ? r.value : null,
      error: r.status === 'rejected' ? (r.reason as Error).message : null,
    })))
  }

  return (
    <div className="space-y-6">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={uid}
            onChange={e => setUid(e.target.value)}
            placeholder="Enter Global UID to generate ad..."
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-cdp-border rounded-xl text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-150 font-mono shadow-sm"
          />
        </div>
        <button
          type="submit"
          className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-all duration-150 shadow-sm"
        >
          Fetch Ad
        </button>
      </form>

      {/* Loading State */}
      {isLoading && (
        <div className="bg-white border border-cdp-border rounded-xl shadow-card p-6 animate-pulse">
          <div className="flex flex-col items-center justify-center py-8">
            <Loader2 size={20} className="text-blue-500 animate-spin mb-3" />
            <p className="text-sm text-slate-500 font-medium">Generating ad creative...</p>
            <p className="text-xs text-slate-400 mt-1">Ollama may take 5–15 seconds</p>
          </div>
        </div>
      )}

      {isError && !isLoading && (
        <div className="flex flex-col items-center justify-center py-12">
          <Search size={24} className="text-slate-300 mb-3" />
          <p className="text-sm text-slate-500 font-medium">No ad found for this UID</p>
          <p className="text-xs text-slate-400 mt-1">Try a different one.</p>
        </div>
      )}

      {/* Ad Preview */}
      {adResponse && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => setMobileView(false)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  !mobileView
                    ? 'bg-blue-50 text-blue-700 border border-blue-200 shadow-sm'
                    : 'bg-white text-slate-500 border border-cdp-border hover:bg-slate-50'
                }`}
              >
                <Monitor size={12} /> Desktop
              </button>
              <button
                onClick={() => setMobileView(true)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  mobileView
                    ? 'bg-blue-50 text-blue-700 border border-blue-200 shadow-sm'
                    : 'bg-white text-slate-500 border border-cdp-border hover:bg-slate-50'
                }`}
              >
                <Smartphone size={12} /> Mobile
              </button>
            </div>

            <div className={mobileView ? 'max-w-[320px] mx-auto' : ''}>
              <AdCreativeCard
                ad={adResponse.creative}
                onRegenerate={() => mutation.mutate()}
                regenerating={mutation.isPending}
              />
            </div>

            <div className="mt-3 flex items-center gap-2 text-xs text-slate-400 font-mono">
              <Zap size={12} />
              <span>{adResponse.cached ? 'From cache' : 'Freshly generated'} &middot; {new Date(adResponse.generated_at).toLocaleString()}</span>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white border border-cdp-border rounded-xl p-5 shadow-card"
          >
            <div className="text-xs font-semibold text-slate-600 mb-3">Profile Context</div>
            <div className="text-xs font-mono text-slate-500 break-all mb-4 bg-slate-50 px-2 py-1.5 rounded border border-slate-200">
              UID: {adResponse.global_uid}
            </div>
            {adResponse.creative.product_links.length > 0 && (
              <div>
                <div className="text-[11px] font-medium text-slate-500 mb-2">Product Links</div>
                <div className="space-y-1.5">
                  {adResponse.creative.product_links.map((link, i) => (
                    <div key={i} className="text-[11px] font-mono text-blue-600 bg-blue-50 border border-blue-200 rounded-lg px-3 py-1.5">
                      {link}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        </div>
      )}

      {/* Batch Preview */}
      <div className="bg-white border border-cdp-border rounded-xl p-5 shadow-card">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={14} className="text-slate-500" />
          <span className="text-xs font-semibold text-slate-600">Batch Preview</span>
        </div>
        <div className="flex gap-3 mb-4">
          <input
            type="text"
            value={batchUids}
            onChange={e => setBatchUids(e.target.value)}
            placeholder="Comma-separated UIDs..."
            className="flex-1 px-3 py-2 bg-white border border-cdp-border rounded-lg text-xs text-slate-900 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all duration-150 font-mono"
          />
          <button
            onClick={handleBatchFetch}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-all duration-150 shadow-sm"
          >
            Fetch All
          </button>
        </div>
        {batchResults.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {batchResults.map((r, i) => (
              <div key={i}>
                {r.data ? (
                  <AdCreativeCard ad={r.data.creative} />
                ) : (
                  <div className="bg-white border border-red-200 rounded-xl p-4 shadow-card">
                    <div className="text-xs font-mono text-slate-500 mb-1">{r.uid}</div>
                    <div className="text-xs text-red-600">{r.error}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

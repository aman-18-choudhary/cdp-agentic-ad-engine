import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { getAdCreative, regenerateAd } from '@/api/endpoints'
import AdCreativeCard from '@/components/shared/AdCreativeCard'
import { Search, Smartphone, Monitor, Loader2 } from 'lucide-react'

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
    <div className="space-y-5">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-cdp-text-muted" />
          <input
            type="text"
            value={uid}
            onChange={e => setUid(e.target.value)}
            placeholder="Enter Global UID to generate ad..."
            className="w-full pl-9 pr-4 py-2.5 bg-cdp-card border border-white/10 rounded-xl text-sm text-cdp-text placeholder:text-cdp-text-muted/50 outline-none focus:border-cdp-accent/50 transition-colors font-mono"
          />
        </div>
        <button
          type="submit"
          className="px-5 py-2.5 rounded-xl bg-cdp-accent text-white text-sm font-medium hover:bg-cdp-accent/90 transition-colors"
        >
          Fetch Ad
        </button>
      </form>

      {/* Loading State */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-16">
          <Loader2 size={24} className="text-cdp-accent animate-spin mb-3" />
          <p className="text-xs text-cdp-text-muted animate-pulse">
            Generating ad creative... (Ollama may take 5-15s)
          </p>
        </div>
      )}

      {isError && !isLoading && (
        <div className="text-center py-8 text-cdp-text-muted text-sm">
          No ad found for this UID. Try a different one.
        </div>
      )}

      {/* Ad Preview */}
      {adResponse && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-5">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex items-center gap-2 mb-3">
              <button
                onClick={() => setMobileView(false)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  !mobileView ? 'bg-cdp-accent/10 text-cdp-accent border border-cdp-accent/20' : 'bg-cdp-card text-cdp-text-muted border border-white/5'
                }`}
              >
                <Monitor size={12} /> Desktop
              </button>
              <button
                onClick={() => setMobileView(true)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  mobileView ? 'bg-cdp-accent/10 text-cdp-accent border border-cdp-accent/20' : 'bg-cdp-card text-cdp-text-muted border border-white/5'
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

            <div className="mt-2 text-[10px] text-cdp-text-muted font-mono">
              {adResponse.cached ? 'From cache' : 'Freshly generated'} &middot; {new Date(adResponse.generated_at).toLocaleString()}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-cdp-card border border-white/5 rounded-xl p-4"
          >
            <div className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider mb-3">
              Profile Context
            </div>
            <div className="text-[10px] font-mono text-cdp-text-muted break-all mb-3">
              UID: {adResponse.global_uid}
            </div>
            {adResponse.creative.product_links.length > 0 && (
              <div>
                <div className="text-[10px] text-cdp-text-muted mb-1">Product Links</div>
                <div className="space-y-1">
                  {adResponse.creative.product_links.map((link, i) => (
                    <div key={i} className="text-[10px] font-mono text-cdp-accent bg-cdp-accent/5 rounded px-2 py-1">
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
      <div className="bg-cdp-card border border-white/5 rounded-xl p-5">
        <div className="text-[10px] font-medium text-cdp-text-muted uppercase tracking-wider mb-3">
          Batch Preview
        </div>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={batchUids}
            onChange={e => setBatchUids(e.target.value)}
            placeholder="Comma-separated UIDs..."
            className="flex-1 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-cdp-text placeholder:text-cdp-text-muted/50 outline-none font-mono"
          />
          <button
            onClick={handleBatchFetch}
            className="px-4 py-2 rounded-lg bg-cdp-accent text-white text-xs font-medium hover:bg-cdp-accent/90"
          >
            Fetch All
          </button>
        </div>
        {batchResults.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {batchResults.map((r, i) => (
              <div key={i}>
                {r.data ? (
                  <AdCreativeCard ad={r.data.creative} />
                ) : (
                  <div className="bg-cdp-card border border-white/5 rounded-xl p-4 text-[10px] text-cdp-danger">
                    {r.uid}: {r.error}
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

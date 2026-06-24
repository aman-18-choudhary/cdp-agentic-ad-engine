import type { AdCreative } from '@/api/types'
import { Clock, RefreshCw } from 'lucide-react'

interface Props {
  ad: AdCreative
  onRegenerate?: () => void
  regenerating?: boolean
}

export default function AdCreativeCard({ ad, onRegenerate, regenerating }: Props) {
  const minutesAgo = Math.floor(
    (Date.now() - new Date(ad.generated_at).getTime()) / 60000
  )
  const stale = minutesAgo > 10

  return (
    <div className="bg-cdp-card border border-white/5 rounded-xl overflow-hidden">
      <div className="p-5">
        <h3 className="text-lg font-bold text-cdp-text mb-1">{ad.headline}</h3>
        <p className="text-sm text-cdp-text-muted mb-3">{ad.body}</p>
        <div className="inline-block px-4 py-2 rounded-lg bg-cdp-accent/10 text-cdp-accent text-sm font-medium border border-cdp-accent/20">
          {ad.cta}
        </div>
        {ad.product_links.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {ad.product_links.map((link, i) => (
              <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-cdp-text-muted font-mono">
                {link}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="px-5 py-2.5 border-t border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] text-cdp-text-muted">
          <Clock size={10} />
          <span>{minutesAgo}m ago</span>
          {stale && <span className="text-cdp-warning font-medium">(stale)</span>}
        </div>
        {onRegenerate && (
          <button
            onClick={onRegenerate}
            disabled={regenerating}
            className="flex items-center gap-1 text-[10px] text-cdp-accent hover:text-cdp-accent/80 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={10} className={regenerating ? 'animate-spin' : ''} />
            Regenerate
          </button>
        )}
      </div>
    </div>
  )
}

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
    <div className="bg-white border border-cdp-border rounded-xl shadow-card overflow-hidden hover:shadow-card-hover transition-shadow duration-200">
      <div className="p-6">
        <h3 className="text-xl font-bold text-slate-900 mb-1.5 leading-tight">{ad.headline}</h3>
        <p className="text-sm text-slate-600 mb-4 leading-relaxed">{ad.body}</p>
        <div className="inline-flex items-center px-5 py-2 rounded-lg bg-blue-50 text-blue-700 text-sm font-medium border border-blue-200">
          {ad.cta}
        </div>
        {ad.product_links.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-4">
            {ad.product_links.map((link, i) => (
              <span key={i} className="text-[11px] px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-500 font-mono border border-slate-200">
                {link}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="px-6 py-3 border-t border-cdp-border flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Clock size={12} />
          <span>{minutesAgo}m ago</span>
          {stale && <span className="text-amber-600 font-medium">(stale)</span>}
        </div>
        {onRegenerate && (
          <button
            onClick={onRegenerate}
            disabled={regenerating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition-all duration-150 disabled:opacity-50"
          >
            <RefreshCw size={12} className={regenerating ? 'animate-spin' : ''} />
            Regenerate
          </button>
        )}
      </div>
    </div>
  )
}

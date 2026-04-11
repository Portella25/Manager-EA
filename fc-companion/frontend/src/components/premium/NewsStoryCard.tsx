interface NewsStoryCardProps {
  item: any
  onOpen?: (articleId: string) => void
  compact?: boolean
}

const SLOT_COLORS: Record<string, string> = {
  destaque: 'text-semantic-gold',
  bastidores: 'text-orange-400',
  'análise': 'text-cyan-400',
  mercado: 'text-green-400',
  contexto: 'text-purple-400',
}

function slotBaseKey(slot: string | undefined): string {
  const s = String(slot || '')
  const known = ['destaque', 'bastidores', 'análise', 'mercado', 'contexto'] as const
  for (const k of known) {
    if (s === k || s.startsWith(`${k}_`)) return k
  }
  return s.replace(/_\d+$/, '') || 'destaque'
}

export function NewsStoryCard({ item, onOpen, compact = false }: NewsStoryCardProps) {
  const slotLabel = item.slot_label || item.slot || 'Notícia'
  const slotColor = SLOT_COLORS[slotBaseKey(item.slot)] || 'text-semantic-gold'

  return (
    <button
      onClick={() => onOpen?.(item.article_id)}
      className={`w-full text-left card-base border border-semantic-gold/20 bg-gradient-to-b from-white/10 to-transparent ${compact ? 'p-4' : 'p-5'}`}
    >
      <div className="flex justify-between items-start gap-3 mb-3">
        <span className={`text-[10px] uppercase tracking-[0.2em] font-bold ${slotColor}`}>{slotLabel}</span>
        <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{item.impact || 'Médio'}</span>
      </div>
      <h4 className={`${compact ? 'text-base' : 'text-lg'} font-bold text-white leading-tight`}>{item.headline}</h4>
      <p className="text-sm text-text-secondary mt-3 leading-relaxed">{item.subheadline}</p>
      {!compact && (item.lead || (item.body && item.body.length > 0)) ? (
        <p className="text-xs text-text-secondary/70 mt-2 leading-relaxed line-clamp-2">
          {item.lead && item.lead !== item.subheadline ? item.lead : item.body?.[0]}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {(item.tags || []).slice(0, compact ? 2 : 4).map((tag: string) => (
          <span key={tag} className="px-2 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] uppercase tracking-wide text-text-secondary">
            {tag}
          </span>
        ))}
      </div>
    </button>
  )
}

interface NewsStoryCardProps {
  item: any
  onOpen?: (articleId: string) => void
  compact?: boolean
}

export function NewsStoryCard({ item, onOpen, compact = false }: NewsStoryCardProps) {
  return (
    <button
      onClick={() => onOpen?.(item.article_id)}
      className={`w-full text-left card-base border border-semantic-gold/20 bg-gradient-to-b from-white/10 to-transparent ${compact ? 'p-4' : 'p-5'}`}
    >
      <div className="flex justify-between items-start gap-3 mb-3">
        <span className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold font-bold">{item.slot || 'notícia'}</span>
        <span className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{item.impact || 'impacto médio'}</span>
      </div>
      <h4 className={`${compact ? 'text-base' : 'text-lg'} font-bold text-white leading-tight`}>{item.headline}</h4>
      <p className="text-sm text-text-secondary mt-3 leading-relaxed">{item.subheadline}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {(item.tags || []).slice(0, compact ? 2 : 3).map((tag: string) => (
          <span key={tag} className="px-2 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] uppercase tracking-wide text-text-secondary">
            {tag}
          </span>
        ))}
      </div>
    </button>
  )
}

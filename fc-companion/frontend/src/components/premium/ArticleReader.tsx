interface ArticleReaderProps {
  article: any
  onClose?: () => void
}

export function ArticleReader({ article, onClose }: ArticleReaderProps) {
  return (
    <div className="w-full max-w-md mx-auto bg-[#09110b] border border-white/10 rounded-3xl p-5">
      <div className="flex justify-between items-start gap-4 mb-5">
        <div>
          <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold font-bold mb-2">{article?.slot || 'notícia'}</p>
          <h3 className="text-2xl font-condensed font-bold text-white uppercase leading-tight">{article?.headline}</h3>
        </div>
        {onClose ? (
          <button onClick={onClose} className="text-sm font-bold text-text-secondary whitespace-nowrap">
            Fechar
          </button>
        ) : null}
      </div>

      <p className="text-base text-white/90 leading-relaxed mb-4">{article?.lead}</p>

      <div className="space-y-4 mb-5">
        {(article?.body || []).map((paragraph: string, index: number) => (
          <p key={`${article?.article_id}-${index}`} className="text-sm text-text-secondary leading-relaxed">
            {paragraph}
          </p>
        ))}
      </div>

      <div className="card-base p-4 mb-4">
        <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold font-bold mb-2">Por que isso importa</p>
        <p className="text-sm text-text-secondary leading-relaxed">{article?.why_it_matters}</p>
      </div>

      <div className="card-base p-4 mb-4">
        <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold font-bold mb-2">Efeitos no clube</p>
        <div className="space-y-2">
          {(article?.club_effects || []).map((effect: string) => (
            <p key={effect} className="text-sm text-text-secondary leading-relaxed">• {effect}</p>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {(article?.tags || []).map((tag: string) => (
          <span key={tag} className="px-2 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] uppercase tracking-wide text-text-secondary">
            {tag}
          </span>
        ))}
      </div>
    </div>
  )
}

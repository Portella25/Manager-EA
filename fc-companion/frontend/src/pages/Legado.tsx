import { useState } from 'react'
import { Crown, Swords, TrendingUp, Users } from 'lucide-react'
import { useGameStore } from '../store/useGameStore'

type LegacyCard = {
  card_id: string
  type: string
  title: string
  value?: string
  subtitle?: string
  meta?: Record<string, unknown>
}

type BestXIPlayer = {
  playerid?: number
  name?: string
  overall?: number
  position?: string
}

type LegacyHub = {
  aproveitamento?: {
    pct?: number
    games?: number
    wins?: number
    draws?: number
    losses?: number
    points?: number
    points_possible?: number
  }
  cards?: LegacyCard[]
  best_xi?: { players?: BestXIPlayer[] }
  missing_topics?: string[]
}

function IconForCard({ type }: { type: string }) {
  const common = 'w-5 h-5'
  if (type === 'kpi') return <TrendingUp className={common} />
  if (type === 'record') return <Swords className={common} />
  if (type === 'club') return <Users className={common} />
  if (type === 'streak') return <Crown className={common} />
  return <TrendingUp className={common} />
}

function formatOccuredAt(meta?: Record<string, unknown>) {
  const raw = (meta?.date_raw as unknown) || (meta?.occurred_at as unknown)
  if (!raw) return null
  const s = String(raw)
  return s.length > 10 ? s.slice(0, 10) : s
}

function LegacyStatCard({ card, onOpen }: { card: LegacyCard; onOpen: (card: LegacyCard) => void }) {
  const dateLabel = formatOccuredAt(card.meta)
  const comp = card?.meta?.competition_name ? String(card.meta.competition_name) : null

  return (
    <button
      type="button"
      onClick={() => onOpen(card)}
      className="card-base p-4 text-left w-full hover:bg-white/5 transition"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-text-secondary">
          <IconForCard type={card.type} />
        </div>
        <div className="flex-1">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{card.type}</p>
          <h4 className="text-sm font-bold text-white mt-1">{card.title}</h4>
          <div className="flex items-end justify-between gap-3 mt-2">
            <p className="text-2xl font-condensed font-bold text-white leading-none">{card.value || '--'}</p>
            <div className="text-right">
              {dateLabel ? <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{dateLabel}</p> : null}
              {comp ? <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{comp}</p> : null}
            </div>
          </div>
          {card.subtitle ? <p className="text-xs text-text-secondary mt-2 leading-relaxed">{card.subtitle}</p> : null}
        </div>
      </div>
    </button>
  )
}

export function Legado() {
  const { data, loading } = useGameStore();
  const [selected, setSelected] = useState<LegacyCard | null>(null)

  const legacyProfile = (data?.legacy_profile || {}) as Record<string, unknown>
  const seasonPayoffs = Array.isArray(data?.season_payoffs_recent) ? data.season_payoffs_recent : []
  const legacyHub = (data?.legacy_hub || null) as LegacyHub | null
  const legacyCards = Array.isArray(legacyHub?.cards) ? legacyHub!.cards! : []
  const bestXI = Array.isArray(legacyHub?.best_xi?.players) ? legacyHub!.best_xi!.players! : []
  const aproveitamento = legacyHub?.aproveitamento || {}
  const missingTopics = Array.isArray(legacyHub?.missing_topics) ? legacyHub!.missing_topics! : []

  if (loading && !data) {
    return <div className="text-center text-text-secondary mt-10">Carregando legado...</div>;
  }

  return (
    <div className="space-y-6 pb-6">
      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Legado</h2>
      </div>

      <section className="card-base p-5">
        <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Métrica principal</p>
        <h3 className="font-condensed font-bold text-xl text-white uppercase mt-2">Aproveitamento</h3>
        <div className="flex items-end justify-between gap-4 mt-4">
          <p className="text-4xl font-condensed font-bold text-white leading-none">
            {typeof aproveitamento?.pct === 'number' ? `${aproveitamento.pct.toFixed(1)}%` : '--'}
          </p>
          <div className="text-right">
            <p className="text-xs text-text-secondary">{aproveitamento?.wins ?? 0}V · {aproveitamento?.draws ?? 0}E · {aproveitamento?.losses ?? 0}D</p>
            <p className="text-[11px] uppercase tracking-[0.2em] text-text-secondary mt-1">{aproveitamento?.games ?? 0} jogos · {aproveitamento?.points ?? 0}/{aproveitamento?.points_possible ?? 0} pts</p>
          </div>
        </div>
        <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3">
          <p className="text-xs text-text-secondary leading-relaxed">
            Fórmula: (Vitórias × 3 + Empates × 1) ÷ (Jogos × 3) × 100
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h3 className="font-condensed font-bold text-lg text-white uppercase">Marcos da carreira</h3>
        {legacyCards.length === 0 ? (
          <div className="text-center text-text-secondary py-4 text-sm">Ainda não há marcos suficientes. Continue jogando para o legado começar a se formar.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {legacyCards.map((card) => (
              <LegacyStatCard key={card.card_id} card={card} onOpen={setSelected} />
            ))}
          </div>
        )}
        {missingTopics.length > 0 ? (
          <div className="card-base p-4">
            <p className="text-xs text-text-secondary">Em construção: {missingTopics.map((t: string) => t.split('_').join(' ')).join(', ')}</p>
          </div>
        ) : null}
      </section>

      <section className="card-base p-5">
        <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Identidade atual</p>
        <h3 className="font-condensed font-bold text-lg text-white uppercase mt-2">Melhor XI (snapshot)</h3>
        {bestXI.length === 0 ? (
          <p className="text-sm text-text-secondary mt-3">Sem dados suficientes do elenco ainda.</p>
        ) : (
          <div className="mt-4 space-y-2">
            {bestXI.map((p, idx: number) => (
              <div key={`${p.playerid || idx}`} className="rounded-xl border border-white/10 bg-black/20 p-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-bold text-white truncate">{p.name || `Jogador #${p.playerid || '--'}`}</p>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-text-secondary mt-1">{p.position || 'posição n/d'}</p>
                </div>
                <div className="text-right">
                  <p className="text-xl font-condensed font-bold text-white">{p.overall ?? '--'}</p>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">overall</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card-base p-5 text-center">
        <h3 className="font-condensed font-bold text-xl text-white uppercase">Hall da Fama</h3>
        <p className="text-sm text-text-secondary mt-2">
          {String(legacyProfile.narrative_summary || '') || 'Sua jornada como treinador ainda está no começo. Continue vencendo para escrever seu nome na história.'}
        </p>
      </section>

      <div className="space-y-4">
        <h3 className="font-condensed font-bold text-lg text-white uppercase">Histórico de Temporadas</h3>
        
        {seasonPayoffs.length === 0 ? (
          <div className="text-center text-text-secondary py-4 text-sm">Nenhuma temporada concluída ainda.</div>
        ) : (
          seasonPayoffs.map((payoff: any) => (
            <div key={payoff.id} className="card-base p-4 border-l-4 border-semantic-green">
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="font-bold text-white">{payoff.title}</h4>
                  <p className="text-xs text-text-secondary">{payoff.epilogue}</p>
                </div>
                <div className="text-right">
                  <span className="font-condensed font-bold text-semantic-green">Nota {payoff.grade}</span>
                  <p className="text-[10px] text-text-secondary uppercase">{payoff.final_score} pts</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {selected ? (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-end sm:items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="w-full sm:max-w-lg rounded-2xl border border-white/10 bg-[#0a140d] p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{selected.type}</p>
                <h4 className="text-lg font-bold text-white mt-2">{selected.title}</h4>
              </div>
              <button type="button" onClick={() => setSelected(null)} className="text-xs font-bold text-text-secondary uppercase tracking-wide">Fechar</button>
            </div>
            <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-3xl font-condensed font-bold text-white">{selected.value || '--'}</p>
              {selected.subtitle ? <p className="text-sm text-text-secondary mt-2 leading-relaxed">{selected.subtitle}</p> : null}
              {selected?.meta?.competition_name || selected?.meta?.date_raw ? (
                <p className="text-[11px] uppercase tracking-[0.2em] text-text-secondary mt-3">
                  {[selected?.meta?.competition_name, formatOccuredAt(selected.meta)].filter(Boolean).join(' · ')}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

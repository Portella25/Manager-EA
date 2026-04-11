import { useGameStore } from '../store/useGameStore'

const TIMELINE_PHASE_PT: Record<string, string> = {
  season_arc: 'Arco da temporada',
  season_arc_start: 'Início do arco sazonal',
  season_arc_payoff: 'Desfecho do arco',
  crisis_step: 'Momento da crise',
  crisis_start: 'Crise iniciada',
  calendar: 'Calendário',
  pre_match: 'Pré-jogo',
  post_match: 'Pós-jogo',
  fan_reaction: 'Torcida',
  board_note: 'Diretoria',
  market_watch: 'Mercado',
  achievement: 'Conquista',
  legacy: 'Legado',
}

function timelinePhaseLabel(entry: { phase?: string; phase_label?: string }) {
  if (entry.phase_label?.trim()) return entry.phase_label
  const key = (entry.phase || '').toLowerCase()
  if (TIMELINE_PHASE_PT[key]) return TIMELINE_PHASE_PT[key]
  if (!entry.phase) return 'Momento'
  return entry.phase
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function scoreTone(value?: number | null, inverse = false) {
  const safeValue = Number(value ?? 0)
  if (inverse) {
    if (safeValue >= 75) return 'text-semantic-red'
    if (safeValue >= 50) return 'text-semantic-gold'
    return 'text-semantic-green'
  }
  if (safeValue >= 75) return 'text-semantic-green'
  if (safeValue >= 50) return 'text-semantic-gold'
  return 'text-semantic-red'
}

export function Carreira() {
  const { data, loading } = useGameStore()

  if (loading && !data) {
    return <div className="text-center text-text-secondary mt-10">Carregando carreira...</div>
  }

  const careerState = data?.career_management_state || {}
  const lockerRoom = careerState.locker_room || {}
  const tactical = careerState.tactical || {}
  const coachProfile = data?.coach_profile || {}
  const seasonContext = data?.season_context || {}
  const leagueTable = seasonContext?.league_table || {}
  const nextFixture = seasonContext?.next_fixture || {}
  const playerRelations = [...(data?.player_relations_recent || [])]
    .sort((a: any, b: any) => Number(b?.frustration || 0) - Number(a?.frustration || 0))
    .slice(0, 3)
  const timeline = data?.timeline_recent || []
  const reputation = coachProfile.reputation_score || 50
  const fanSentiment = coachProfile.fan_sentiment_score || 50
  const boardChallenge = data?.board_active_challenge
  const crisis = data?.crisis_active_arc
  const seasonArc = data?.season_arc_active
  const recentForm = seasonContext?.recent_form?.last_5 || []

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Carreira</h2>
      </div>

      <section className="grid grid-cols-2 gap-3">
        <div className="card-base p-4 col-span-2">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Resumo da temporada</p>
          <p className="text-xl font-condensed font-bold text-white mt-2">{seasonArc?.title || 'Ciclo competitivo em andamento'}</p>
          <p className="text-xs text-text-secondary mt-1">{nextFixture?.home_team_name && nextFixture?.away_team_name ? `${nextFixture.home_team_name} x ${nextFixture.away_team_name}` : 'Sem próximo confronto detectado no calendário'}</p>
        </div>
        <div className="card-base p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Posição na liga</p>
          <p className="text-xl font-condensed font-bold text-white mt-2">{leagueTable?.rank ? `${leagueTable.rank}º` : '--'}</p>
          <p className="text-xs text-text-secondary mt-1">{leagueTable?.competition_name || 'Tabela principal não detectada'}</p>
        </div>
        <div className="card-base p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Diretoria e torcida</p>
          <p className="text-xl font-condensed font-bold text-white mt-2">{reputation}% / {fanSentiment}%</p>
          <p className="text-xs text-text-secondary mt-1">Reputação e sentimento do clube</p>
        </div>
      </section>

      <section className="card-base p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Contexto da temporada</p>
            <h3 className="font-condensed font-bold text-xl text-white uppercase mt-2">
              {seasonArc?.title || 'Temporada em andamento'}
            </h3>
            <p className="text-sm text-text-secondary mt-2">
              {nextFixture?.home_team_name && nextFixture?.away_team_name
                ? `${nextFixture.home_team_name} x ${nextFixture.away_team_name} • ${nextFixture.date_label || 'sem data'}`
                : 'Sem próximo jogo identificado no calendário atual'}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-[0.2em] text-semantic-gold">{seasonContext?.game_date?.label || 'Hoje'}</p>
            <p className="text-sm text-white mt-2">{leagueTable?.points ?? '--'} pts</p>
          </div>
        </div>

        <div className="flex gap-1 mt-4">
          {(recentForm.length > 0 ? recentForm : ['-', '-', '-', '-', '-']).map((result: string, index: number) => (
            <span
              key={`${result}-${index}`}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                result === 'W' ? 'bg-semantic-green/20 text-semantic-green' : result === 'L' ? 'bg-semantic-red/20 text-semantic-red' : 'bg-semantic-gold/20 text-semantic-gold'
              }`}
            >
              {result === 'W' ? 'V' : result === 'D' ? 'E' : result}
            </span>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Arco da temporada</p>
            <p className="text-sm font-bold text-white mt-2">{seasonArc?.theme || tactical?.identity_label || 'Sem tema dominante'}</p>
            <p className="text-xs text-text-secondary mt-1">{seasonArc ? `${seasonArc.current_milestone}/${seasonArc.max_milestones} marcos` : 'Sem arco persistido'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Situação institucional</p>
            <p className={`text-sm font-bold mt-2 ${scoreTone(100 - reputation, true)}`}>{boardChallenge?.title || crisis?.title || 'Sem crise ativa'}</p>
            <p className="text-xs text-text-secondary mt-1">{boardChallenge?.description || crisis?.summary || 'Pressão monitorada pelo desempenho recente.'}</p>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4">
        <div className="card-base p-5">
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Vestiário e ambiente</h3>
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Coesão</p>
              <p className={`text-lg font-bold mt-2 ${scoreTone(lockerRoom.cohesion)}`}>{lockerRoom.cohesion ?? '--'}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Confiança média</p>
              <p className={`text-lg font-bold mt-2 ${scoreTone(lockerRoom.trust_avg)}`}>{lockerRoom.trust_avg ?? '--'}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Moral média</p>
              <p className={`text-lg font-bold mt-2 ${scoreTone(lockerRoom.morale_avg)}`}>{lockerRoom.morale_avg ?? '--'}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Estilo do técnico</p>
              <p className="text-lg font-bold text-white mt-2 capitalize">{tactical.coach_style || '--'}</p>
            </div>
          </div>

          <div className="space-y-3 mt-4">
            {playerRelations.length === 0 ? (
              <p className="text-sm text-text-secondary">Ainda não há sinais individuais fortes do vestiário.</p>
            ) : (
              playerRelations.map((player: any) => (
                <div key={player.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-white">{player.player_name}</p>
                      <p className="text-[11px] text-text-secondary mt-1">
                    <span className="font-medium text-white/90">{player.role_label}</span>
                    <span className="mx-1 text-text-secondary/80">·</span>
                    <span>{player.status_label}</span>
                  </p>
                    </div>
                    <p className={`text-sm font-bold ${scoreTone(100 - Number(player.frustration || 0), true)}`}>{player.frustration ?? 0}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card-base p-5">
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Timeline de gestão</h3>
          <div className="space-y-3 mt-4">
            {timeline.length === 0 ? (
              <p className="text-sm text-text-secondary">Sem marcos recentes persistidos para esta carreira.</p>
            ) : (
              timeline.slice(0, 4).map((entry: any) => (
                <div key={entry.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <p className="text-[10px] font-medium tracking-wide text-semantic-gold">{timelinePhaseLabel(entry)}</p>
                  <p className="text-sm font-bold text-white mt-2">{entry.title}</p>
                  <p className="text-xs text-text-secondary mt-1 leading-relaxed">{entry.content}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

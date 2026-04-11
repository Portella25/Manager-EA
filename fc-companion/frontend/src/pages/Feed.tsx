import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { NewsStoryCard } from '../components/premium/NewsStoryCard'
import { SectionHeader } from '../components/premium/SectionHeader'
import { SignalRadarCard } from '../components/premium/SignalRadarCard'
import { useCareerHubStore } from '../store/useCareerHubStore'
import { useGameStore } from '../store/useGameStore'
import { useAppStore } from '../store'

function scoreTone(score?: number | null, inverted = false) {
  const safeScore = Number(score ?? 0)
  if (inverted) {
    if (safeScore >= 75) return 'text-semantic-red'
    if (safeScore >= 50) return 'text-semantic-gold'
    return 'text-semantic-green'
  }
  if (safeScore >= 75) return 'text-semantic-green'
  if (safeScore >= 50) return 'text-semantic-gold'
  return 'text-semantic-red'
}

function severityStyles(severity?: string) {
  if (severity === 'critical') return 'border-semantic-red/40 bg-semantic-red/10'
  if (severity === 'high') return 'border-semantic-gold/40 bg-semantic-gold/10'
  if (severity === 'medium') return 'border-semantic-blue/40 bg-semantic-blue/10'
  return 'border-white/15 bg-white/5'
}

function scoreToneType(score?: number | null, inverted = false): 'positive' | 'warning' | 'danger' {
  const safeScore = Number(score ?? 0)
  if (inverted) {
    if (safeScore >= 75) return 'danger'
    if (safeScore >= 50) return 'warning'
    return 'positive'
  }
  if (safeScore >= 75) return 'positive'
  if (safeScore >= 50) return 'warning'
  return 'danger'
}

export function Feed() {
  const navigate = useNavigate()
  const saveUid = useAppStore((state) => state.saveUid)
  const { startPolling: startGamePolling, stopPolling: stopGamePolling } = useGameStore()
  const { dashboardHome, dailyNews, conferenceContext, loading, error, startPolling, stopPolling } = useCareerHubStore()

  useEffect(() => {
    startGamePolling(saveUid || undefined)
    return () => stopGamePolling()
  }, [saveUid, startGamePolling, stopGamePolling])

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  if (loading && !dashboardHome) {
    return <div className="text-center text-text-secondary mt-10">Carregando hub da carreira...</div>
  }

  if (error && !dashboardHome) {
    return <div className="text-center text-semantic-red mt-10">{error}</div>
  }

  const snapshot = dashboardHome?.snapshot
  const hero = snapshot?.hero
  const heroPanel = dashboardHome?.hero_panel
  const cards = dashboardHome?.cards
  const radars = dashboardHome?.radars
  const alerts = dashboardHome?.alerts || []
  const newsPreview = dashboardHome?.daily_news_preview || dailyNews?.stories || []
  const timelinePreview = dashboardHome?.timeline_preview || []
  const questions = conferenceContext?.questions || []

  return (
    <div className="space-y-6 pb-6">
      <section className="card-base p-5 bg-[radial-gradient(circle_at_top_left,rgba(201,163,74,0.32),transparent_38%),radial-gradient(circle_at_top_right,rgba(31,97,141,0.22),transparent_32%),linear-gradient(180deg,rgba(255,255,255,0.10),rgba(255,255,255,0.02))] border-semantic-gold/25 overflow-hidden relative">
        <div className="absolute inset-0 bg-[linear-gradient(135deg,transparent,rgba(255,255,255,0.04),transparent)] pointer-events-none" />
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-semantic-gold font-bold mb-2">Hub da Carreira</p>
            <h2 className="font-condensed font-bold text-3xl text-white uppercase leading-none">
              {snapshot?.club?.team_name || 'Carreira'}
            </h2>
            <p className="text-sm text-text-secondary mt-2">
              {snapshot?.club?.manager_name || 'Treinador'} • {snapshot?.game_date?.label || 'Hoje'}
            </p>
          </div>
          <div className="text-right">
            <span className={`text-xs font-bold uppercase tracking-wide ${hero?.state_tone === 'danger' ? 'text-semantic-red' : hero?.state_tone === 'warning' ? 'text-semantic-gold' : hero?.state_tone === 'positive' ? 'text-semantic-green' : 'text-text-secondary'}`}>
              {hero?.state_label?.replace('_', ' ') || 'estável'}
            </span>
            <p className="text-xs text-text-secondary mt-2 max-w-[9rem]">
              {snapshot?.club?.competition_focus || 'Temporada em andamento'}
            </p>
          </div>
        </div>

        <div className="mb-5 relative">
          <h3 className="text-2xl font-condensed font-bold text-white uppercase leading-tight">{hero?.headline || 'A carreira entrou em novo ciclo de decisões'}</h3>
          <p className="text-sm text-text-secondary mt-3 leading-relaxed max-w-[22rem]">{hero?.subheadline}</p>
          <div className="flex flex-wrap gap-2 mt-4">
            <button onClick={() => navigate('/coletiva')} className="px-4 py-2 rounded-full bg-semantic-gold text-background font-bold text-xs uppercase tracking-wide">
              Abrir coletiva
            </button>
            <button onClick={() => navigate('/social')} className="px-4 py-2 rounded-full border border-white/15 text-white font-bold text-xs uppercase tracking-wide">
              Rede social
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">Próximo jogo</p>
            <p className="text-sm font-bold text-white leading-snug">
              {heroPanel?.next_fixture ? `${heroPanel.next_fixture.home_team_name} x ${heroPanel.next_fixture.away_team_name}` : 'Sem partida identificada'}
            </p>
            <p className="text-xs text-text-secondary mt-2">
              {[heroPanel?.next_fixture?.date_label, heroPanel?.next_fixture?.competition_name].filter(Boolean).join(' • ') || 'Calendário'}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">Liga e momento</p>
            <p className="text-sm font-bold text-white leading-snug">
              {heroPanel?.league_table?.rank ? `${heroPanel.league_table.rank}º lugar` : 'Posição não detectada'}
            </p>
            <p className="text-xs text-text-secondary mt-2">
              {heroPanel?.league_table?.competition_name
                ? `${heroPanel.league_table.competition_name} • ${heroPanel.league_table.points ?? 0} pts`
                : `${heroPanel?.recent_form?.points_last_5 ?? 0} pts nos últimos 5`}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2 mt-4">
          <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-center">
            <p className="text-[9px] uppercase tracking-[0.2em] text-text-secondary">Vestiário</p>
            <p className={`text-xl font-condensed font-bold mt-1 ${scoreTone(heroPanel?.club_health?.locker_room_score)}`}>{heroPanel?.club_health?.locker_room_score ?? '--'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-center">
            <p className="text-[9px] uppercase tracking-[0.2em] text-text-secondary">Torcida</p>
            <p className={`text-xl font-condensed font-bold mt-1 ${scoreTone(heroPanel?.club_health?.fan_sentiment_score)}`}>{heroPanel?.club_health?.fan_sentiment_score ?? '--'}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-center">
            <p className="text-[9px] uppercase tracking-[0.2em] text-text-secondary">Pressão</p>
            <p className={`text-xl font-condensed font-bold mt-1 ${scoreTone(100 - (heroPanel?.club_health?.board_confidence_score ?? 50), true)}`}>{100 - (heroPanel?.club_health?.board_confidence_score ?? 50)}</p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/status-fisico')}
            className="rounded-xl border border-white/10 bg-black/20 p-2 text-center hover:border-semantic-blue/40 transition-colors w-full"
          >
            <p className="text-[9px] uppercase tracking-[0.2em] text-text-secondary">Médico</p>
            <p className={`text-xl font-condensed font-bold mt-1 ${scoreTone(heroPanel?.club_health?.injury_risk_score, true)}`}>{heroPanel?.club_health?.injury_risk_score ?? '--'}</p>
            <p className="text-[8px] text-semantic-blue mt-1 uppercase">Abrir status físico</p>
          </button>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3">
        <SignalRadarCard
          label="Clima do clube"
          value={heroPanel?.club_health?.locker_room_score ?? '--'}
          subtitle={`Torcida ${heroPanel?.club_health?.fan_sentiment_score ?? '--'} • Pressão ${100 - (heroPanel?.club_health?.board_confidence_score ?? 50)}`}
          tone={scoreToneType(heroPanel?.club_health?.locker_room_score)}
        />
        <div className="card-base p-4 bg-gradient-to-br from-semantic-blue/10 to-transparent">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-3">Decisão do momento</p>
          <h3 className="font-condensed text-xl font-bold text-white uppercase leading-tight">{heroPanel?.strategic_focus?.primary_decision || 'Sem foco estratégico definido'}</h3>
          {heroPanel?.strategic_focus?.secondary_decision && (
            <p className="text-xs text-semantic-gold mt-2">{heroPanel.strategic_focus.secondary_decision}</p>
          )}
          <p className="text-xs text-text-secondary mt-3 leading-relaxed">{heroPanel?.strategic_focus?.why_now}</p>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3">
        <button onClick={() => navigate('/plantel')} className="card-base p-4 text-left">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{cards?.squad?.title || 'Elenco'}</p>
          <p className="text-2xl font-condensed font-bold text-white">{cards?.squad?.highlights?.in_form_count ?? 0}</p>
          <p className="text-xs text-text-secondary mt-1">jogadores em alta</p>
        </button>
        <button onClick={() => navigate('/social')} className="card-base p-4 text-left">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{cards?.news?.title || 'Notícias'}</p>
          <p className="text-2xl font-condensed font-bold text-white">{cards?.news?.stories_count ?? 0}</p>
          <p className="text-xs text-text-secondary mt-1">matérias do dia</p>
        </button>
        <button onClick={() => navigate('/carreira')} className="card-base p-4 text-left">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{cards?.league?.title || 'Temporada'}</p>
          <p className="text-sm font-bold text-white leading-tight">
            {cards?.league?.rank ? `${cards.league.rank}º lugar` : (radars?.season?.arc_title || 'Sem arco ativo')}
          </p>
          <p className="text-xs text-text-secondary mt-1">
            {cards?.league?.competition_name || radars?.season?.milestone_progress || '0/0'}
          </p>
        </button>
        <button onClick={() => navigate('/mercado')} className="card-base p-4 text-left">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">Mercado</p>
          <p className="text-sm font-bold text-white leading-tight">{radars?.squad?.market_interest?.[0] || 'Sem ruído forte no mercado'}</p>
          <p className="text-xs text-text-secondary mt-1">Monitoramento ativo</p>
        </button>
      </section>

      <section className="space-y-3">
        <SectionHeader title="Alertas críticos" subtitle={`${alerts.length} ativos`} />
        {alerts.length === 0 ? (
          <div className="card-base p-4 text-sm text-text-secondary">Nenhum alerta crítico no momento.</div>
        ) : (
          alerts.map((alert: any) => (
            <div key={alert.id} className={`card-base p-4 border ${severityStyles(alert.severity)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{alert.type}</p>
                  <h4 className="font-bold text-white">{alert.title}</h4>
                  <p className="text-sm text-text-secondary mt-2 leading-relaxed">{alert.message}</p>
                </div>
                <button
                  onClick={() => navigate(alert.cta_target || '/')}
                  className="text-xs font-bold text-semantic-gold whitespace-nowrap"
                >
                  {alert.cta_label}
                </button>
              </div>
            </div>
          ))
        )}
      </section>

      <section className="space-y-4">
        <SectionHeader
          title="Notícias do dia"
          subtitle="Até 5 matérias com contexto e impacto no clube"
          actionLabel="Abrir feed completo"
          onAction={() => navigate('/social')}
        />

        <div className="space-y-4">
          {newsPreview.length === 0 ? (
            <div className="card-base p-4 text-sm text-text-secondary">Ainda não há matérias para este dia da carreira.</div>
          ) : (
            newsPreview.map((item: any) => (
              <NewsStoryCard key={item.article_id} item={item} onOpen={(articleId) => navigate(`/social/${articleId}`)} />
            ))
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4">
        <div className="card-base p-4">
          <SectionHeader title="Coletiva contextual" actionLabel="Abrir sala" onAction={() => navigate('/coletiva')} />
          {questions.length === 0 ? (
            <p className="text-sm text-text-secondary">Ainda não há perguntas quentes para a coletiva.</p>
          ) : (
            <div className="space-y-3">
              {questions.slice(0, 2).map((question: any) => (
                <button key={question.question_id} onClick={() => navigate('/coletiva')} className="w-full text-left rounded-xl border border-white/10 bg-white/5 p-3 hover:border-semantic-gold/30">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{question.topic_type}</p>
                  <p className="text-sm font-bold text-white leading-relaxed">{question.question}</p>
                  <p className="text-xs text-text-secondary mt-2">{question.why_now}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card-base p-4 bg-gradient-to-b from-white/10 to-transparent">
          <SectionHeader title="Timeline recente" subtitle={`${timelinePreview.length} marcos`} />
          <div className="space-y-3">
            {timelinePreview.length === 0 ? (
              <p className="text-sm text-text-secondary">Sem marcos recentes no momento.</p>
            ) : (
              timelinePreview.map((entry: any) => (
                <div key={entry.id} className="border-l border-semantic-gold/40 pl-3 relative">
                  <span className="absolute -left-[5px] top-1 h-2.5 w-2.5 rounded-full bg-semantic-gold" />
                  <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold mb-1">{entry.phase}</p>
                  <h4 className="text-sm font-bold text-white">{entry.title}</h4>
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

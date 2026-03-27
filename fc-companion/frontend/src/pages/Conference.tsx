import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchRecentPressConferences, respondPressConference } from '../lib/api'
import { SectionHeader } from '../components/premium/SectionHeader'
import { SignalRadarCard } from '../components/premium/SignalRadarCard'
import { useCareerHubStore } from '../store/useCareerHubStore'
import { useAppStore } from '../store'

function scoreTone(score?: number) {
  const safe = Number(score ?? 0)
  if (safe >= 70) return 'danger'
  if (safe >= 45) return 'warning'
  return 'positive'
}

function responseTemplate(tone: string, question: string) {
  if (tone === 'calmo') return `Mantemos serenidade total sobre isso. ${question} faz parte do contexto, mas o foco segue no trabalho diário e na resposta dentro de campo.`
  if (tone === 'firme') return `Entendo o peso do tema. ${question} exige convicção, e vamos responder com clareza, responsabilidade e desempenho.`
  if (tone === 'confiante') return `O grupo está preparado. ${question} entra no radar natural da coletiva, mas confiamos no plano e no momento do elenco.`
  return `Reconhecemos o contexto. ${question} pede equilíbrio de discurso e compromisso com a evolução do clube.`
}

export function Conference() {
  const navigate = useNavigate()
  const saveUid = useAppStore((state) => state.saveUid)
  const { conferenceContext, loading, error, startPolling, stopPolling } = useCareerHubStore()
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null)
  const [submittingTone, setSubmittingTone] = useState<string | null>(null)
  const [responseResult, setResponseResult] = useState<any | null>(null)
  const [recentConferences, setRecentConferences] = useState<any[]>([])

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  useEffect(() => {
    if (!saveUid) return
    fetchRecentPressConferences(saveUid, 5)
      .then((items) => setRecentConferences(items))
      .catch(() => setRecentConferences([]))
  }, [saveUid, conferenceContext])

  const selectedQuestion = useMemo(
    () => (conferenceContext?.questions || []).find((item: any) => item.question_id === selectedQuestionId) || conferenceContext?.questions?.[0] || null,
    [conferenceContext, selectedQuestionId]
  )

  useEffect(() => {
    if (conferenceContext?.questions?.length && !selectedQuestionId) {
      setSelectedQuestionId(conferenceContext.questions[0].question_id)
    }
  }, [conferenceContext, selectedQuestionId])

  async function handleAnswer(tone: string) {
    if (!selectedQuestion || !saveUid) return
    setSubmittingTone(tone)
    try {
      const answer = responseTemplate(tone, selectedQuestion.question)
      const result = await respondPressConference(selectedQuestion.question, answer, saveUid)
      setResponseResult({ ...result, answer })
      const items = await fetchRecentPressConferences(saveUid, 5)
      setRecentConferences(items)
    } finally {
      setSubmittingTone(null)
    }
  }

  if (loading && !conferenceContext) {
    return <div className="text-center text-text-secondary mt-10">Carregando sala de imprensa...</div>
  }

  if (error && !conferenceContext) {
    return <div className="text-center text-semantic-red mt-10">{error}</div>
  }

  const pressureMap = conferenceContext?.pressure_map || {}
  const hotTopics = conferenceContext?.hot_topics || []
  const questions = conferenceContext?.questions || []

  return (
    <div className="space-y-6 pb-6">
      <section className="card-base p-5 bg-gradient-to-br from-semantic-gold/15 via-white/5 to-transparent border-semantic-gold/25 overflow-hidden">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-semantic-gold font-bold mb-2">Sala de Imprensa</p>
            <h2 className="font-condensed font-bold text-3xl text-white uppercase leading-none">Coletiva dedicada</h2>
            <p className="text-sm text-text-secondary mt-2">
              {conferenceContext?.context_snapshot?.club_name || 'Clube'} • {conferenceContext?.context_snapshot?.game_date || 'Hoje'}
            </p>
          </div>
          <button onClick={() => navigate('/social')} className="text-xs font-bold text-semantic-gold uppercase tracking-wide">
            Social
          </button>
        </div>

        <div className="space-y-3">
          <h3 className="text-xl font-bold text-white leading-tight">
            {conferenceContext?.mode === 'pre_match' ? 'O ambiente pré-jogo está sensível' : conferenceContext?.mode === 'post_match' ? 'A repercussão pós-jogo já está formada' : 'O contexto público da carreira pede respostas'}
          </h3>
          <p className="text-sm text-text-secondary leading-relaxed">
            {conferenceContext?.response_guidance?.recommended_approach || 'Use esta área para responder temas quentes com impacto em reputação, moral e pressão institucional.'}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 mt-5">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">Próximo contexto</p>
            <p className="text-sm font-bold text-white leading-snug">
              {conferenceContext?.context_snapshot?.next_fixture ? `${conferenceContext.context_snapshot.next_fixture.home_team_name} x ${conferenceContext.context_snapshot.next_fixture.away_team_name}` : 'Sem partida ativa'}
            </p>
            <p className="text-xs text-text-secondary mt-2">
              {conferenceContext?.context_snapshot?.next_fixture?.competition_name || conferenceContext?.context_snapshot?.last_result?.score || 'Ciclo atual'}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">Tom sugerido</p>
            <p className="text-sm font-bold text-white leading-snug">{conferenceContext?.response_guidance?.safe_tone || 'equilibrado'}</p>
            <p className="text-xs text-text-secondary mt-2">
              {conferenceContext?.expected_consequences?.positive_path?.[0] || 'Proteja reputação e estabilidade pública.'}
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader title="Mapa de pressão" subtitle="Leia o ambiente antes de responder" />
        <div className="grid grid-cols-2 gap-3">
          <SignalRadarCard label="Diretoria" value={pressureMap.board?.score ?? '--'} subtitle={pressureMap.board?.label} tone={scoreTone(pressureMap.board?.score) as any} />
          <SignalRadarCard label="Torcida" value={pressureMap.fans?.score ?? '--'} subtitle={pressureMap.fans?.label} tone={scoreTone(pressureMap.fans?.score) as any} />
          <SignalRadarCard label="Vestiário" value={pressureMap.locker_room?.score ?? '--'} subtitle={pressureMap.locker_room?.label} tone={scoreTone(pressureMap.locker_room?.score) as any} />
          <SignalRadarCard label="Mídia" value={pressureMap.media?.score ?? '--'} subtitle={pressureMap.media?.label} tone={scoreTone(pressureMap.media?.score) as any} />
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader title="Temas quentes" subtitle={`${hotTopics.length} tópicos no radar`} />
        {hotTopics.length === 0 ? (
          <div className="card-base p-4 text-sm text-text-secondary">Ainda não há temas quentes suficientes para a coletiva.</div>
        ) : (
          hotTopics.map((topic: any) => (
            <div key={topic.topic_id} className="card-base p-4">
              <div className="flex justify-between items-start gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold mb-2">{topic.topic_type}</p>
                  <h4 className="font-bold text-white">{topic.title}</h4>
                  <p className="text-sm text-text-secondary mt-2 leading-relaxed">{topic.summary}</p>
                </div>
                <span className="text-xs font-bold text-text-secondary">{topic.importance}</span>
              </div>
            </div>
          ))
        )}
      </section>

      <section className="space-y-3">
        <SectionHeader title="Perguntas da coletiva" subtitle="Escolha a pauta e o tom da resposta" />
        <div className="space-y-3">
          {questions.map((question: any) => {
            const active = question.question_id === selectedQuestion?.question_id
            return (
              <button
                key={question.question_id}
                onClick={() => setSelectedQuestionId(question.question_id)}
                className={`w-full text-left card-base p-4 border ${active ? 'border-semantic-gold/40 bg-semantic-gold/10' : 'border-white/10'}`}
              >
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{question.topic_type}</p>
                <h4 className="font-bold text-white leading-relaxed">{question.question}</h4>
                <p className="text-xs text-text-secondary mt-2">{question.why_now}</p>
              </button>
            )
          })}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4">
        <div className="card-base p-4">
          <SectionHeader title="Riscos da pergunta" subtitle="Leitura preditiva antes da resposta" />
          {selectedQuestion ? (
            <div className="grid grid-cols-2 gap-3">
              <SignalRadarCard label="Reputação" value={selectedQuestion.predicted_effects?.reputation_risk || '--'} subtitle="risco" tone={selectedQuestion.predicted_effects?.reputation_risk === 'high' ? 'danger' : selectedQuestion.predicted_effects?.reputation_risk === 'medium' ? 'warning' : 'positive'} />
              <SignalRadarCard label="Moral" value={selectedQuestion.predicted_effects?.morale_risk || '--'} subtitle="risco" tone={selectedQuestion.predicted_effects?.morale_risk === 'high' ? 'danger' : selectedQuestion.predicted_effects?.morale_risk === 'medium' ? 'warning' : 'positive'} />
              <SignalRadarCard label="Diretoria" value={selectedQuestion.predicted_effects?.board_sensitivity || '--'} subtitle="sensibilidade" tone={selectedQuestion.predicted_effects?.board_sensitivity === 'high' ? 'danger' : selectedQuestion.predicted_effects?.board_sensitivity === 'medium' ? 'warning' : 'positive'} />
              <SignalRadarCard label="Torcida" value={selectedQuestion.predicted_effects?.fan_sensitivity || '--'} subtitle="sensibilidade" tone={selectedQuestion.predicted_effects?.fan_sensitivity === 'high' ? 'danger' : selectedQuestion.predicted_effects?.fan_sensitivity === 'medium' ? 'warning' : 'positive'} />
            </div>
          ) : (
            <p className="text-sm text-text-secondary">Selecione uma pergunta para ver os riscos estimados.</p>
          )}
        </div>

        <div className="card-base p-4">
          <SectionHeader title="Guidance" subtitle="Como abordar o microfone" />
          <p className="text-sm text-white leading-relaxed">{conferenceContext?.response_guidance?.recommended_approach}</p>
          <div className="mt-4 space-y-2">
            {(conferenceContext?.response_guidance?.danger_zones || []).map((zone: string) => (
              <p key={zone} className="text-xs text-text-secondary">• {zone}</p>
            ))}
          </div>
        </div>
      </section>

      <section className="card-base p-4">
        <SectionHeader title="Responder agora" subtitle="Simule o tom público da entrevista" />
        <div className="grid grid-cols-2 gap-3 mt-4">
          {['calmo', 'firme', 'confiante', 'equilibrado'].map((tone) => (
            <button
              key={tone}
              onClick={() => handleAnswer(tone)}
              disabled={!selectedQuestion || !!submittingTone}
              className={`rounded-2xl border px-4 py-3 text-sm font-bold uppercase tracking-wide transition-colors ${
                submittingTone === tone ? 'border-semantic-gold bg-semantic-gold/20 text-semantic-gold' : 'border-white/10 bg-white/5 text-white hover:border-semantic-gold/40 hover:text-semantic-gold'
              }`}
            >
              {submittingTone === tone ? 'Respondendo...' : tone}
            </button>
          ))}
        </div>
      </section>

      {responseResult ? (
        <section className="card-base p-4 border border-semantic-gold/30 bg-semantic-gold/10">
          <SectionHeader title="Reação imediata" subtitle={responseResult.headline} />
          <p className="text-sm text-white mt-4 leading-relaxed">{responseResult.answer}</p>
          <div className="space-y-2 mt-4">
            <p className="text-xs text-text-secondary">Diretoria: {responseResult.board_reaction}</p>
            <p className="text-xs text-text-secondary">Vestiário: {responseResult.locker_room_reaction}</p>
            <p className="text-xs text-text-secondary">Torcida: {responseResult.fan_reaction}</p>
          </div>
        </section>
      ) : null}

      <section className="space-y-3">
        <SectionHeader title="Histórico recente" subtitle={`${recentConferences.length} respostas registradas`} />
        {recentConferences.length === 0 ? (
          <div className="card-base p-4 text-sm text-text-secondary">Ainda não há coletivas recentes registradas.</div>
        ) : (
          recentConferences.map((item: any) => (
            <div key={item.id} className="card-base p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold mb-2">{item.detected_tone}</p>
              <h4 className="font-bold text-white">{item.headline}</h4>
              <p className="text-sm text-text-secondary mt-2 leading-relaxed">{item.question}</p>
            </div>
          ))
        )}
      </section>
    </div>
  )
}

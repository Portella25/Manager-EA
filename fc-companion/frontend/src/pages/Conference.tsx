import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchRecentPressConferences, respondPressConference } from '../lib/api'
import { SectionHeader } from '../components/premium/SectionHeader'
import { SignalRadarCard } from '../components/premium/SignalRadarCard'
import { useCareerHubStore } from '../store/useCareerHubStore'
import { useAppStore } from '../store'

/** Jornalistas fictícios (Brasil) — nunca repetir no mesmo ciclo de 4. */
const JOURNALIST_POOL = [
  { name: 'Mariana Costa', outlet: 'O Globo Esportivo' },
  { name: 'Rafael Mendes', outlet: 'Estado de Futebol' },
  { name: 'Juliana Prado', outlet: 'Placar Digital' },
  { name: 'Thiago Azevedo', outlet: 'Folha da Bola' },
  { name: 'Camila Rocha', outlet: 'Gazeta do Esporte' },
  { name: 'Bruno Carvalho', outlet: 'Correio do Gol' },
  { name: 'Fernanda Lins', outlet: 'Tribuna da Arquibancada' },
  { name: 'Lucas Oliveira', outlet: 'Diário do Centroavante' },
  { name: 'Patrícia Nunes', outlet: 'Revista da Liga' },
  { name: 'André Freitas', outlet: 'Portal Lance Certo' },
  { name: 'Beatriz Amaral', outlet: 'Jornal do Apito' },
  { name: 'Gustavo Pires', outlet: 'Manchete FC' }
]

function scoreTone(score?: number) {
  const safe = Number(score ?? 0)
  if (safe >= 70) return 'danger'
  if (safe >= 45) return 'warning'
  return 'positive'
}

function audienceFromTopic(topicType: string): 'board' | 'players' | 'staff' {
  const tt = String(topicType || '')
  if (tt === 'board' || tt === 'season') return 'board'
  if (tt === 'locker_room' || tt === 'player') return 'players'
  return 'staff'
}

function topicTypeLabelPt(topicType: string): string {
  const t = String(topicType || '').toLowerCase()
  const map: Record<string, string> = {
    match: 'PARTIDA',
    form: 'FORMA',
    market: 'MERCADO',
    player: 'JOGADOR',
    board: 'DIRETORIA',
    season: 'TEMPORADA',
    locker_room: 'VESTIÁRIO',
    medical: 'DEPARTAMENTO MÉDICO'
  }
  return map[t] || t.toUpperCase() || 'TEMA'
}

function toneDetectedLabelPt(tone: string): string {
  const m: Record<string, string> = {
    positive: 'Positivo',
    negative: 'Negativo',
    neutral: 'Neutro',
    evasive: 'Evasivo',
    aggressive: 'Agressivo',
    calm: 'Calmo',
    motivational: 'Motivacional',
    analytical: 'Analítico'
  }
  return m[String(tone || '').toLowerCase()] || tone || '—'
}

function seededShuffle<T>(arr: T[], seed: string): T[] {
  const out = [...arr]
  let s = 0
  for (let i = 0; i < seed.length; i++) s = (s + seed.charCodeAt(i) * (i + 1)) % 2147483647
  for (let i = out.length - 1; i > 0; i--) {
    s = (s * 48271 + 7) % 2147483647
    const j = s % (i + 1)
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

function buildFillerQuestions(ctx: any, sessionKey: number, need: number): any[] {
  if (need <= 0) return []
  const snap = ctx?.context_snapshot || {}
  const club = snap.club_name || 'Clube'
  const nx = snap.next_fixture
  const tbl = snap.table_summary
  const last = snap.last_result
  const preVespera =
    nx?.home_team_name && nx?.away_team_name
      ? `À véspera de ${nx.home_team_name} x ${nx.away_team_name}, `
      : ''
  const preTabela =
    tbl?.competition_name && tbl?.rank != null && tbl?.points != null
      ? `Na tabela da ${tbl.competition_name}, com o ${club} na ${tbl.rank}ª posição (${tbl.points} pts), `
      : ''
  const preUltimo =
    last?.label && last?.score
      ? `Após a ${last.label} na última partida (${last.score}), `
      : ''
  const templates = [
    `${preVespera || preTabela || ''}o que muda na forma como o ${club} encara a sequência da competição?`,
    `${preUltimo || preVespera || ''}como equilibra resultado imediato e evolução do elenco?`,
    `${preTabela || preVespera || ''}há decisões de escalação que já estão definidas ou ainda em aberto?`,
    `${preVespera || `Sobre o momento do ${club}, `}que mensagem o grupo precisa ouvir antes do próximo desafio?`
  ]
  return templates.slice(0, need).map((question, i) => ({
    question_id: `filler:${sessionKey}:${i}`,
    slot: 100 + i,
    topic_type: 'season',
    question,
    intent: 'complemento de pauta',
    why_now: '',
    entities: [],
    predicted_effects: {}
  }))
}

const TONE_OPTIONS: { id: string; apiStyle: string; shortLabel: string; label: string; hint: string }[] = [
  { id: 'aggressive', apiStyle: 'aggressive', shortLabel: 'Agressivo', label: 'Agressivo / exigente', hint: 'Cobrança firme e direta' },
  { id: 'calm', apiStyle: 'calm', shortLabel: 'Calmo', label: 'Calmo / conciliador', hint: 'Tom controlado e claro' },
  { id: 'motivational', apiStyle: 'motivational', shortLabel: 'Motivacional', label: 'Motivacional', hint: 'Confiança e energia' },
  { id: 'analytical', apiStyle: 'analytical', shortLabel: 'Analítico', label: 'Analítico / frio', hint: 'Foco em processo e dados' }
]

const PRESS_ROOM_BG =
  'linear-gradient(to bottom, rgba(10,20,13,0.94) 0%, rgba(10,20,13,0.88) 100%), url(https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?auto=format&fit=crop&w=1600&q=65)'

export function Conference() {
  const navigate = useNavigate()
  const saveUid = useAppStore((state) => state.saveUid)
  const { conferenceContext, loading, error, startPolling, stopPolling } = useCareerHubStore()
  const [recentConferences, setRecentConferences] = useState<any[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [sessionKey, setSessionKey] = useState(0)
  const [currentStep, setCurrentStep] = useState(0)
  const [phase, setPhase] = useState<'question' | 'answer' | 'done'>('question')
  const [submittingTone, setSubmittingTone] = useState<string | null>(null)
  const [lastAnswer, setLastAnswer] = useState<any | null>(null)
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  useEffect(() => {
    if (!saveUid) return
    fetchRecentPressConferences(saveUid, 20)
      .then((items) => {
        if (!items || items.length === 0) {
          setRecentConferences([])
          return
        }
        const lastDate = items[0]?.game_date
        const lastSession = lastDate
          ? items.filter((it: any) => it.game_date === lastDate)
          : items.slice(0, 4)
        setRecentConferences(lastSession)
      })
      .catch(() => setRecentConferences([]))
  }, [saveUid, conferenceContext])

  useEffect(() => {
    return () => {
      if (advanceTimer.current) clearTimeout(advanceTimer.current)
    }
  }, [])

  const sessionPlan = useMemo(() => {
    const raw = conferenceContext?.questions || []
    const base = raw.slice(0, 4)
    const fillers = buildFillerQuestions(conferenceContext, sessionKey, Math.max(0, 4 - base.length))
    const four = [...base, ...fillers].slice(0, 4)
    const seed = `${saveUid || 'x'}|${sessionKey}|${four.map((q) => q.question_id).join(';')}`
    const shuffled = seededShuffle(JOURNALIST_POOL, seed)
    return four.map((q, i) => ({
      question: q,
      reporter: shuffled[i % shuffled.length]
    }))
  }, [conferenceContext, sessionKey, saveUid])

  const currentItem = sessionPlan[currentStep] || null
  const managerName = conferenceContext?.context_snapshot?.manager_name || 'Treinador'
  const clubName = conferenceContext?.context_snapshot?.club_name || 'Clube'

  const startSession = () => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current)
    setSessionKey((k) => k + 1)
    setCurrentStep(0)
    setPhase('question')
    setLastAnswer(null)
    setModalOpen(true)
  }

  const closeModal = () => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current)
    setModalOpen(false)
    setPhase('question')
    setLastAnswer(null)
  }

  const handleAnswer = async (apiStyle: string, toneShortLabel: string) => {
    if (!currentItem || !saveUid || phase !== 'question') return
    const stepAtSubmit = currentStep
    setSubmittingTone(apiStyle)
    const q = currentItem.question
    const audience = audienceFromTopic(String(q.topic_type || ''))
    try {
      const result = await respondPressConference(String(q.question || ''), '', saveUid, {
        audience,
        responseStyle: apiStyle,
        topicType: String(q.topic_type || 'season')
      })
      setLastAnswer({
        ...result,
        answer: result.answer_rendered || result.answer,
        reporterName: currentItem.reporter.name,
        outlet: currentItem.reporter.outlet,
        chosenToneLabel: toneShortLabel
      })
      setPhase('answer')
      const items = await fetchRecentPressConferences(saveUid, 5)
      setRecentConferences(items)
      if (advanceTimer.current) clearTimeout(advanceTimer.current)
      advanceTimer.current = setTimeout(() => {
        if (stepAtSubmit >= 3) {
          setPhase('done')
        } else {
          setLastAnswer(null)
          setPhase('question')
          setCurrentStep(stepAtSubmit + 1)
        }
      }, 15000)
    } finally {
      setSubmittingTone(null)
    }
  }

  if (loading && !conferenceContext) {
    return <div className="text-center text-text-secondary mt-10">Carregando sala de imprensa…</div>
  }

  if (error && !conferenceContext) {
    return <div className="text-center text-semantic-red mt-10">{error}</div>
  }

  const pressureMap = conferenceContext?.pressure_map || {}
  const hotTopics = conferenceContext?.hot_topics || []
  const isMatchDay = conferenceContext?.is_match_day ?? false
  const matchDayCompleted = conferenceContext?.match_day_completed ?? null
  const conferenceLocked = conferenceContext?.conference_locked ?? false

  const modeLabel = (() => {
    if (isMatchDay && matchDayCompleted) return 'Coletiva pós-jogo'
    if (isMatchDay && !matchDayCompleted) return 'Coletiva pré-jogo'
    return 'Coletiva do dia'
  })()

  const headlineText = (() => {
    if (conferenceLocked) return 'Coletiva já realizada hoje'
    if (isMatchDay && matchDayCompleted) {
      const rl = matchDayCompleted.result_label || 'resultado'
      return `Pós-jogo: a repercussão da ${rl} já está formada`
    }
    if (isMatchDay && !matchDayCompleted) return 'Pré-jogo: o ambiente antes da partida está sensível'
    return 'O contexto público da carreira pede respostas'
  })()

  const matchDaySubtext = (() => {
    if (matchDayCompleted) {
      return `${matchDayCompleted.home_team_name} ${matchDayCompleted.home_score} x ${matchDayCompleted.away_score} ${matchDayCompleted.away_team_name} — ${matchDayCompleted.competition_name || ''}`
    }
    return null
  })()

  return (
    <div className="space-y-6 pb-6">
      <section className="card-base p-5 bg-gradient-to-br from-semantic-gold/15 via-white/5 to-transparent border-semantic-gold/25 overflow-hidden">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-semantic-gold font-bold mb-2">Sala de imprensa</p>
            <h2 className="font-condensed font-bold text-3xl text-white uppercase leading-none">{modeLabel}</h2>
            <p className="text-sm text-text-secondary mt-2">
              {clubName} • {conferenceContext?.context_snapshot?.game_date || 'Hoje'}
              {matchDaySubtext ? ` • ${matchDaySubtext}` : ''}
            </p>
          </div>
          <button type="button" onClick={() => navigate('/social')} className="text-xs font-bold text-semantic-gold uppercase tracking-wide">
            Voltar ao social
          </button>
        </div>

        <div className="space-y-3">
          <h3 className="text-xl font-bold text-white leading-tight">{headlineText}</h3>
          <p className="text-sm text-text-secondary leading-relaxed">
            {conferenceContext?.response_guidance?.recommended_approach ||
              'Responda com clareza: reputação, moral e imagem pública acompanham cada frase.'}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 mt-5">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">Próximo contexto</p>
            <p className="text-sm font-bold text-white leading-snug">
              {conferenceContext?.context_snapshot?.next_fixture
                ? `${conferenceContext.context_snapshot.next_fixture.home_team_name} x ${conferenceContext.context_snapshot.next_fixture.away_team_name}`
                : 'Sem partida ativa'}
            </p>
            <p className="text-xs text-text-secondary mt-2">
              {conferenceContext?.context_snapshot?.next_fixture?.competition_name ||
                conferenceContext?.context_snapshot?.last_result?.score ||
                'Ciclo atual'}
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
          <SignalRadarCard
            label="Diretoria"
            value={pressureMap.board?.score ?? '--'}
            subtitle={pressureMap.board?.label}
            tone={scoreTone(pressureMap.board?.score) as any}
          />
          <SignalRadarCard
            label="Torcida"
            value={pressureMap.fans?.score ?? '--'}
            subtitle={pressureMap.fans?.label}
            tone={scoreTone(pressureMap.fans?.score) as any}
          />
          <SignalRadarCard
            label="Vestiário"
            value={pressureMap.locker_room?.score ?? '--'}
            subtitle={pressureMap.locker_room?.label}
            tone={scoreTone(pressureMap.locker_room?.score) as any}
          />
          <SignalRadarCard
            label="Mídia"
            value={pressureMap.media?.score ?? '--'}
            subtitle={pressureMap.media?.label}
            tone={scoreTone(pressureMap.media?.score) as any}
          />
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader title="Temas quentes" subtitle={`${hotTopics.length} tópicos no radar`} />
        {hotTopics.length === 0 ? (
          <div className="card-base p-4 text-sm text-text-secondary">Ainda não há temas quentes suficientes para a coletiva.</div>
        ) : (
          hotTopics.map((topic: any) => (
            <div key={topic.topic_id} className="card-base p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold mb-2">{topicTypeLabelPt(topic.topic_type)}</p>
              <h4 className="font-bold text-white">{topic.title}</h4>
              <p className="text-sm text-text-secondary mt-2 leading-relaxed">{topic.summary}</p>
            </div>
          ))
        )}
      </section>

      <section className="card-base p-6 flex flex-col items-center text-center gap-4 border-semantic-gold/20">
        <h3 className="font-condensed font-bold text-xl text-white uppercase">
          {conferenceLocked ? 'Coletiva encerrada por hoje' : 'Iniciar coletiva de imprensa'}
        </h3>
        {conferenceLocked ? (
          <p className="text-sm text-text-secondary max-w-md">
            Você já realizou a coletiva deste dia. Aguarde o próximo dia de jogo para uma nova sessão.
          </p>
        ) : (
          <>
            <p className="text-sm text-text-secondary max-w-md">
              Quatro perguntas, uma de cada vez, com jornalistas diferentes. Escolha o tom de cada resposta; o treinador responde em diálogo.
              {isMatchDay && !matchDayCompleted
                ? ' Esta é uma coletiva de pré-jogo.'
                : isMatchDay && matchDayCompleted
                  ? ' Esta é uma coletiva de pós-jogo, com perguntas sobre o resultado.'
                  : ' Coletiva de rotina sobre o momento do clube.'}
            </p>
            <button
              type="button"
              onClick={startSession}
              className="px-8 py-3 rounded-xl bg-semantic-gold text-black font-condensed font-bold text-sm uppercase tracking-widest hover:opacity-95 transition-opacity"
            >
              Ir para coletiva
            </button>
          </>
        )}
      </section>

      <section className="card-base p-4">
        <SectionHeader title="Orientação" subtitle="Como abordar o microfone" />
        <p className="text-sm text-white leading-relaxed">{conferenceContext?.response_guidance?.recommended_approach}</p>
        <div className="mt-4 space-y-2">
          {(conferenceContext?.response_guidance?.danger_zones || []).map((zone: string) => (
            <p key={zone} className="text-xs text-text-secondary">
              • {zone}
            </p>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="Última coletiva"
          subtitle={
            recentConferences.length > 0
              ? `${recentConferences.length} perguntas em ${recentConferences[0]?.game_date || 'data desconhecida'}`
              : 'Nenhuma coletiva registrada'
          }
        />
        {recentConferences.length === 0 ? (
          <div className="card-base p-4 text-sm text-text-secondary">Ainda não há coletivas recentes registradas.</div>
        ) : (
          recentConferences.map((item: any) => (
            <div key={item.id} className="card-base p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold">
                  {toneDetectedLabelPt(item.detected_tone)}
                </span>
                <span className="text-[10px] text-text-secondary">
                  Rep {item.reputation_delta ?? 0} · Moral {item.morale_delta ?? 0}
                </span>
              </div>
              <h4 className="font-bold text-white text-sm">{item.headline}</h4>
              <p className="text-xs text-text-secondary mt-2">{item.question}</p>
              <p className="text-xs text-white/80 mt-1 italic">{item.answer}</p>
            </div>
          ))
        )}
      </section>

      {modalOpen ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            aria-label="Fechar"
            onClick={phase === 'done' ? closeModal : undefined}
          />
          <div
            className="relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl border border-white/15 shadow-2xl"
            style={{ background: PRESS_ROOM_BG, backgroundSize: 'cover', backgroundPosition: 'center' }}
          >
            <div className="p-6 space-y-4 bg-[#0a140d]/75 backdrop-blur-md rounded-2xl">
              <div className="flex justify-between items-center">
                <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold">Coletiva ao vivo</p>
                <button type="button" onClick={closeModal} className="text-xs text-text-secondary hover:text-white">
                  Fechar
                </button>
              </div>

              {phase === 'done' ? (
                <div className="text-center py-8 space-y-4">
                  <p className="font-condensed font-bold text-2xl text-white uppercase">Coletiva encerrada</p>
                  <p className="text-sm text-text-secondary">Quatro rodadas concluídas. Boa sorte no próximo jogo.</p>
                  <button
                    type="button"
                    onClick={closeModal}
                    className="px-6 py-2 rounded-xl border border-semantic-gold/40 text-semantic-gold text-sm font-bold uppercase"
                  >
                    Voltar
                  </button>
                </div>
              ) : phase === 'question' && currentItem ? (
                <>
                  <p className="text-xs text-text-secondary">
                    Pergunta {currentStep + 1} de 4 · {topicTypeLabelPt(currentItem.question.topic_type)}
                  </p>
                  <div className="border-l-2 border-semantic-gold/60 pl-3">
                    <p className="text-[10px] uppercase tracking-widest text-semantic-gold mb-1">Pergunta</p>
                    <p className="text-sm font-bold text-white">
                      {currentItem.reporter.name} <span className="text-text-secondary font-normal">— {currentItem.reporter.outlet}</span>
                    </p>
                    <p className="text-base text-white leading-relaxed mt-3">{currentItem.question.question}</p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-widest text-text-secondary mb-2">Escolha como o treinador responde</p>
                    <div className="grid grid-cols-2 gap-2">
                      {TONE_OPTIONS.map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          disabled={!!submittingTone}
                          onClick={() => handleAnswer(opt.apiStyle, opt.shortLabel)}
                          className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                            submittingTone === opt.apiStyle
                              ? 'border-semantic-gold bg-semantic-gold/20'
                              : 'border-white/15 bg-white/5 hover:border-semantic-gold/40'
                          }`}
                        >
                          <span className="block text-xs font-bold text-white">{opt.label}</span>
                          <span className="block text-[10px] text-text-secondary mt-1">{opt.hint}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : phase === 'answer' && lastAnswer ? (
                <div className="space-y-4">
                  <div className="rounded-xl bg-white/5 border border-white/10 p-3">
                    <p className="text-[10px] uppercase text-semantic-gold mb-1">Pergunta</p>
                    <p className="text-xs text-white">
                      <span className="font-bold">{lastAnswer.reporterName}</span>{' '}
                      <span className="text-text-secondary">({lastAnswer.outlet})</span>
                    </p>
                    <p className="text-sm text-text-secondary mt-2">{currentItem?.question?.question}</p>
                  </div>
                  <div className="rounded-xl bg-semantic-gold/10 border border-semantic-gold/25 p-3">
                    <p className="text-[10px] uppercase text-semantic-gold mb-1">Resposta</p>
                    <p className="text-sm text-white mb-3">
                      <span className="font-bold">Resposta do {managerName}</span>
                      <span className="text-text-secondary font-normal"> — treinador do {clubName}</span>
                    </p>
                    <p className="text-sm text-white leading-relaxed">
                      <span className="text-semantic-gold font-semibold">{lastAnswer.chosenToneLabel}:</span>{' '}
                      {lastAnswer.answer}
                    </p>
                    <p className="text-[10px] text-text-secondary mt-3 pt-3 border-t border-white/10">
                      Leitura automática do tom: {toneDetectedLabelPt(lastAnswer.detected_tone)} · Reputação{' '}
                      {lastAnswer.reputation_delta ?? 0} · Moral {lastAnswer.morale_delta ?? 0}
                    </p>
                  </div>
                  <p className="text-center text-xs text-text-secondary">Próxima pergunta em cerca de 15 segundos…</p>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

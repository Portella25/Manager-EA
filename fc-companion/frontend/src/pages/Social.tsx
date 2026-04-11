import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, Newspaper, Users, Briefcase, UserRound, ChevronDown, AlertTriangle } from 'lucide-react'
import { NewsStoryCard } from '../components/premium/NewsStoryCard'
import { SectionHeader } from '../components/premium/SectionHeader'
import { useCareerHubStore } from '../store/useCareerHubStore'
import { useGameStore } from '../store/useGameStore'
import { useAppStore } from '../store'
import { fetchInternalCommsStep, respondPressConference } from '../lib/api'

type ThreadMsg = { role: 'npc' | 'coach'; text: string }

function formatCommsError(e: unknown) {
  const msg = e instanceof Error ? e.message : String(e)
  const short = msg.length > 320 ? `${msg.slice(0, 320)}…` : msg
  return `Não foi possível carregar o diálogo.\n\n${short}\n\nSe o backend foi atualizado, feche todos os terminais Python (porta 8000) e suba de novo: uvicorn em fc-companion/backend.`
}

function partnershipTier(trust: number, frustration: number) {
  const t = Number.isFinite(trust) ? trust : 50
  const f = Number.isFinite(frustration) ? frustration : 0
  const score = Math.max(0, Math.min(100, Math.round(t - f * 0.25)))
  let label = 'Profissional'
  let color = 'text-white/80'
  let bar = 'from-white/30 to-white/10'
  if (score >= 76) {
    label = 'Parceiro'
    color = 'text-semantic-green'
    bar = 'from-semantic-green to-emerald-600/80'
  } else if (score >= 56) {
    label = 'Próximo'
    color = 'text-sky-300'
    bar = 'from-sky-400 to-sky-700/80'
  } else if (score >= 36) {
    label = 'Neutro'
    color = 'text-white/85'
    bar = 'from-zinc-400 to-zinc-700/80'
  } else if (score >= 20) {
    label = 'Frio'
    color = 'text-amber-200/90'
    bar = 'from-amber-500/90 to-amber-900/70'
  } else {
    label = 'Tenso'
    color = 'text-semantic-red'
    bar = 'from-red-500 to-red-900/80'
  }
  return { score, label, color, bar }
}

function resolveSquadPlayerName(player: Record<string, unknown>) {
  const first = String(player?.firstname || '').trim()
  const last = String(player?.lastname || '').trim()
  const common = String(player?.commonname || '').trim()
  const full = `${first} ${last}`.trim()
  if (player?.player_name && !/^\d+$/.test(String(player.player_name))) return String(player.player_name)
  if (common) return common
  if (full) return full
  if (player?.name && !/^\d+$/.test(String(player.name))) return String(player.name)
  if (last && !/^\d+$/.test(last)) return last
  if (first && !/^\d+$/.test(first)) return first
  return `Jogador #${player?.playerid ?? '--'}`
}

export function Social() {
  const navigate = useNavigate()
  const saveUid = useAppStore((state) => state.saveUid)
  const squad = useGameStore((state) => state.squad)
  const playerRelationsRecent = useGameStore((state) => state.data?.player_relations_recent || []) as Array<{
    playerid?: number
    trust?: number
    frustration?: number
    status_label?: string
  }>
  const { dailyNews, conferenceContext, loading, startPolling, stopPolling } = useCareerHubStore()
  const gameDate = conferenceContext?.context_snapshot?.game_date as string | undefined
  const [activeTab, setActiveTab] = useState<'news' | 'interactions'>('news')
  const [interactionTarget, setInteractionTarget] = useState<'board' | 'staff' | 'players'>('board')
  const [playerScope, setPlayerScope] = useState<'group' | 'one_on_one'>('group')
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null)
  const [newsHookIdx, setNewsHookIdx] = useState<number | null>(null)

  const [thread, setThread] = useState<ThreadMsg[]>([])
  const [coachOptions, setCoachOptions] = useState<Array<{ tone: string; text: string }> | null>(null)
  const [convDone, setConvDone] = useState(false)
  const [stepLoading, setStepLoading] = useState(false)
  const [persistResult, setPersistResult] = useState<any | null>(null)
  /** Uma conversa interna por dia de jogo no save; libera quando o calendário avança */
  const [interactionDayLocked, setInteractionDayLocked] = useState(false)

  useEffect(() => {
    setInteractionDayLocked(false)
  }, [gameDate])

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  useEffect(() => {
    if (interactionTarget !== 'players') {
      setPlayerScope('group')
      setSelectedPlayerId(null)
    }
  }, [interactionTarget])

  useEffect(() => {
    if (playerScope !== 'one_on_one') {
      setSelectedPlayerId(null)
    }
  }, [playerScope])

  const squadSorted = useMemo(() => {
    const list = Array.isArray(squad) ? [...squad] : []
    return list.sort((a, b) =>
      resolveSquadPlayerName(a as Record<string, unknown>).localeCompare(
        resolveSquadPlayerName(b as Record<string, unknown>),
        'pt-BR'
      )
    )
  }, [squad])

  const relationsByPlayerId = useMemo(() => {
    const m = new Map<number, (typeof playerRelationsRecent)[0]>()
    for (const r of playerRelationsRecent) {
      const id = Number(r?.playerid)
      if (Number.isFinite(id) && id > 0) m.set(id, r)
    }
    return m
  }, [playerRelationsRecent])

  const [playerMenuOpen, setPlayerMenuOpen] = useState(false)
  const playerMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!playerMenuOpen) return
    const close = (e: MouseEvent) => {
      if (playerMenuRef.current && !playerMenuRef.current.contains(e.target as Node)) setPlayerMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [playerMenuOpen])

  const newsItems = dailyNews?.stories || []
  const hotQuestions = useMemo(() => conferenceContext?.questions ?? [], [conferenceContext?.questions])
  const interactionPrompts = useMemo(() => {
    const raw = conferenceContext?.interaction_prompts as
      | Record<string, { question?: string; why_now?: string; label?: string; topic_type?: string } | null>
      | undefined
    return raw || null
  }, [conferenceContext?.interaction_prompts])

  const interactionsByTarget = useMemo(() => {
    const boardQuestion = hotQuestions.find((item: any) => item.topic_type === 'board' || item.topic_type === 'season')
    const playerQuestion = hotQuestions.find((item: any) => item.topic_type === 'player' || item.topic_type === 'locker_room')
    const staffQuestion = hotQuestions.find(
      (item: any) => item.topic_type === 'medical' || item.topic_type === 'match' || item.topic_type === 'form' || item.topic_type === 'market'
    )
    return {
      board: boardQuestion,
      players: playerQuestion,
      staff: staffQuestion
    }
  }, [hotQuestions])

  const interactionCopy =
    interactionPrompts?.[interactionTarget] ||
    (interactionTarget === 'board'
      ? interactionsByTarget.board
      : interactionTarget === 'players'
        ? interactionsByTarget.players
        : interactionsByTarget.staff)

  const playerTouchpoints = (conferenceContext?.player_touchpoints || []) as Array<{
    player_id: number
    player_name: string
    hook_label?: string
    context?: string
    suggested_prompt?: string
  }>
  const newsHooks = (conferenceContext?.news_discussion_hooks || []) as Array<{
    article_id?: string
    headline?: string
    lead?: string
  }>

  const touchpointForSelected =
    selectedPlayerId != null ? playerTouchpoints.find((t) => t.player_id === selectedPlayerId) : null
  const selectedPlayerLabel =
    selectedPlayerId != null
      ? resolveSquadPlayerName(
          (squadSorted.find((p) => Number((p as { playerid?: number }).playerid) === selectedPlayerId) ||
            {}) as Record<string, unknown>
        )
      : ''
  const selectedNews = newsHookIdx != null ? newsHooks[newsHookIdx] : null

  const interactionBlocked =
    interactionTarget === 'players' && playerScope === 'one_on_one' && (selectedPlayerId == null || squadSorted.length === 0)

  const npcSpeakerLabel = (() => {
    if (interactionTarget === 'board') return 'Diretoria'
    if (interactionTarget === 'staff') return 'Comissão técnica'
    if (interactionTarget === 'players' && playerScope === 'one_on_one') return selectedPlayerLabel || 'Jogador'
    return 'Elenco (voz do grupo)'
  })()

  const persistInteraction = useCallback(
    async (fullThread: ThreadMsg[]) => {
      const npcText = fullThread.filter((m) => m.role === 'npc').map((m) => m.text).join('\n\n')
      const coachText = fullThread.filter((m) => m.role === 'coach').map((m) => m.text).join('\n\n')
      const oneOnOneOk = interactionTarget === 'players' && playerScope === 'one_on_one' && selectedPlayerId != null
      try {
        const res = await respondPressConference(npcText, coachText, saveUid || undefined, {
          audience: interactionTarget,
          topicType: String(interactionCopy?.topic_type || ''),
          interactionMode: oneOnOneOk ? 'one_on_one' : 'group',
          focusPlayerId: oneOnOneOk ? selectedPlayerId ?? undefined : undefined,
          focusPlayerName: oneOnOneOk ? selectedPlayerLabel : undefined,
          linkedArticleId: selectedNews?.article_id,
          linkedHeadline: selectedNews?.headline,
          socialInternalComms: true
        })
        setPersistResult(res || null)
        setInteractionDayLocked(true)
        useCareerHubStore.getState().fetchHubData(saveUid || undefined)
      } catch {
        setPersistResult(null)
      }
    },
    [
      interactionCopy?.topic_type,
      interactionTarget,
      playerScope,
      saveUid,
      selectedNews?.article_id,
      selectedNews?.headline,
      selectedPlayerId,
      selectedPlayerLabel
    ]
  )

  useEffect(() => {
    if (activeTab !== 'interactions') return
    if (interactionBlocked) {
      setThread([])
      setCoachOptions(null)
      setConvDone(false)
      return
    }
    if (interactionDayLocked) return
    let cancelled = false
    ;(async () => {
      setStepLoading(true)
      setConvDone(false)
      setPersistResult(null)
      setThread([])
      setCoachOptions(null)
      try {
        const oneOnOneOk = interactionTarget === 'players' && playerScope === 'one_on_one' && selectedPlayerId != null
        const res = await fetchInternalCommsStep({
          saveUid: saveUid || undefined,
          audience: interactionTarget,
          interactionMode: oneOnOneOk ? 'one_on_one' : 'group',
          focusPlayerId: oneOnOneOk ? selectedPlayerId ?? undefined : undefined,
          focusPlayerName: oneOnOneOk ? selectedPlayerLabel : undefined,
          linkedHeadline: selectedNews?.headline,
          touchpointContext: touchpointForSelected?.context,
          topicTypeHint: String(interactionCopy?.topic_type || ''),
          messages: []
        })
        if (cancelled) return
        if (res.interaction_locked) {
          setInteractionDayLocked(true)
          setConvDone(false)
        }
        setThread((res.npc_blocks || []).map((t) => ({ role: 'npc' as const, text: t })))
        setCoachOptions(res.coach_options || [])
      } catch (err) {
        if (!cancelled) {
          setThread([{ role: 'npc', text: formatCommsError(err) }])
          setCoachOptions([])
        }
      } finally {
        if (!cancelled) setStepLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [
    activeTab,
    interactionBlocked,
    interactionDayLocked,
    interactionTarget,
    newsHookIdx,
    playerScope,
    saveUid,
    selectedNews?.headline,
    selectedPlayerId,
    selectedPlayerLabel
  ])

  const handlePickCoachOption = async (opt: { tone: string; text: string }) => {
    if (convDone || interactionBlocked || stepLoading || interactionDayLocked) return
    const base: ThreadMsg[] = [...thread, { role: 'coach', text: opt.text }]
    setThread(base)
    setCoachOptions(null)
    setStepLoading(true)
    try {
      const oneOnOneOk = interactionTarget === 'players' && playerScope === 'one_on_one' && selectedPlayerId != null
      const res = await fetchInternalCommsStep({
        saveUid: saveUid || undefined,
        audience: interactionTarget,
        interactionMode: oneOnOneOk ? 'one_on_one' : 'group',
        focusPlayerId: oneOnOneOk ? selectedPlayerId ?? undefined : undefined,
        focusPlayerName: oneOnOneOk ? selectedPlayerLabel : undefined,
        linkedHeadline: selectedNews?.headline,
        touchpointContext: touchpointForSelected?.context,
        topicTypeHint: String(interactionCopy?.topic_type || ''),
        messages: base.map((m) => ({ role: m.role, text: m.text }))
      })
      if (res.conversation_done) {
        const closing = (res.npc_blocks || []).map((t) => ({ role: 'npc' as const, text: t }))
        const full = [...base, ...closing]
        setThread(full)
        setCoachOptions(null)
        setConvDone(true)
        await persistInteraction(full)
      } else {
        const nxt = (res.npc_blocks || []).map((t) => ({ role: 'npc' as const, text: t }))
        setThread([...base, ...nxt])
        setCoachOptions(res.coach_options || [])
      }
    } catch (err) {
      setThread((prev) => [...prev, { role: 'npc', text: formatCommsError(err) }])
      setCoachOptions([])
    } finally {
      setStepLoading(false)
    }
  }

  return (
    <div className="space-y-6 pb-6">
      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Social & Mídia</h2>
      </div>

      <div className="flex bg-[#0a140d]/80 rounded-lg p-1 border border-white/10">
        <button
          onClick={() => setActiveTab('news')}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md font-condensed font-bold text-sm transition-all ${
            activeTab === 'news' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'
          }`}
        >
          <Newspaper className="w-4 h-4" />
          NOTÍCIAS
        </button>
        <button
          onClick={() => setActiveTab('interactions')}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md font-condensed font-bold text-sm transition-all ${
            activeTab === 'interactions' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          INTERAÇÕES
        </button>
      </div>

      {activeTab === 'news' && (
        <div className="space-y-4">
          <SectionHeader
            title="Edição do dia"
            subtitle={dailyNews?.game_date || conferenceContext?.context_snapshot?.game_date || 'Sem data ativa'}
            actionLabel={`${newsItems.length} matérias`}
          />
          {newsItems.length > 0 ? (
            newsItems.map((item: any) => (
              <NewsStoryCard key={item.article_id} item={item} onOpen={(articleId) => navigate(`/social/${articleId}`)} />
            ))
          ) : (
            <div className="text-center py-10 text-text-secondary">
              {loading ? 'Carregando notícias editoriais...' : 'Nenhuma notícia recente disponível.'}
            </div>
          )}
        </div>
      )}

      {activeTab === 'interactions' && (
        <div className="space-y-4">
          <SectionHeader title="Comunicação interna" />

          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            <button
              onClick={() => setInteractionTarget('board')}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-bold whitespace-nowrap transition-all ${
                interactionTarget === 'board' ? 'bg-white text-black border-white' : 'bg-transparent border-white/20 text-text-secondary'
              }`}
            >
              <Briefcase className="w-4 h-4" /> Diretoria
            </button>
            <button
              onClick={() => setInteractionTarget('players')}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-bold whitespace-nowrap transition-all ${
                interactionTarget === 'players' ? 'bg-white text-black border-white' : 'bg-transparent border-white/20 text-text-secondary'
              }`}
            >
              <Users className="w-4 h-4" /> Elenco
            </button>
            <button
              onClick={() => setInteractionTarget('staff')}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-bold whitespace-nowrap transition-all ${
                interactionTarget === 'staff' ? 'bg-white text-black border-white' : 'bg-transparent border-white/20 text-text-secondary'
              }`}
            >
              <UserRound className="w-4 h-4" /> Comissão Técnica
            </button>
          </div>

          {interactionTarget === 'players' && (
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center text-xs">
              <span className="text-text-secondary font-bold uppercase tracking-wide">Âmbito do elenco</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPlayerScope('group')
                    setSelectedPlayerId(null)
                  }}
                  className={`px-3 py-1 rounded-full border font-bold ${playerScope === 'group' ? 'bg-semantic-blue text-black border-semantic-blue' : 'border-white/20 text-text-secondary'}`}
                >
                  Grupo / vestiário
                </button>
                <button
                  type="button"
                  onClick={() => setPlayerScope('one_on_one')}
                  className={`px-3 py-1 rounded-full border font-bold ${playerScope === 'one_on_one' ? 'bg-semantic-blue text-black border-semantic-blue' : 'border-white/20 text-text-secondary'}`}
                >
                  Conversa 1:1
                </button>
              </div>
            </div>
          )}

          {interactionTarget === 'players' && playerScope === 'one_on_one' && (
            <div className="space-y-2">
              <label className="block text-[10px] uppercase tracking-[0.2em] text-text-secondary" htmlFor="social-1on1-player">
                Com quem conversar (plantel)
              </label>
              <div className="relative" ref={playerMenuRef}>
                <button
                  type="button"
                  id="social-1on1-player"
                  onClick={() => setPlayerMenuOpen((o) => !o)}
                  className="w-full flex items-center justify-between gap-3 rounded-xl border border-white/12 bg-gradient-to-br from-[#0d1812] via-[#0a120e] to-[#050a08] px-3 py-3 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] hover:border-semantic-gold/35 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    {selectedPlayerId != null ? (
                      <div className="flex items-center gap-3">
                        {(() => {
                          const raw = squadSorted.find(
                            (x) => Number((x as { playerid?: number }).playerid) === selectedPlayerId
                          ) as Record<string, unknown> | undefined
                          const ov = Number(raw?.overall ?? raw?.overallrating ?? 0) || null
                          const rel = relationsByPlayerId.get(selectedPlayerId)
                          const tr = Number(rel?.trust ?? 50)
                          const fr = Number(rel?.frustration ?? 0)
                          const tier = partnershipTier(tr, fr)
                          return (
                            <>
                              <div className="w-11 h-11 rounded-xl bg-black/50 border border-white/10 flex flex-col items-center justify-center shrink-0">
                                <span className="text-[10px] text-text-secondary leading-none">OVR</span>
                                <span className="text-sm font-black text-white leading-tight">{ov != null ? ov : '—'}</span>
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-bold text-white truncate">
                                  {resolveSquadPlayerName(raw || {})}
                                </p>
                                <div className="mt-1 flex items-center gap-2 flex-wrap">
                                  <span className={`text-[10px] font-bold uppercase tracking-wide ${tier.color}`}>
                                    Parceria {tier.score} · {tier.label}
                                  </span>
                                  {fr >= 45 && (
                                    <span className="inline-flex items-center gap-0.5 text-[9px] font-bold uppercase text-semantic-red/90 bg-semantic-red/10 border border-semantic-red/25 px-1.5 py-0.5 rounded">
                                      <AlertTriangle className="w-3 h-3" /> Tenso
                                    </span>
                                  )}
                                </div>
                                <div className="mt-1.5 h-1.5 rounded-full bg-black/50 overflow-hidden border border-white/5">
                                  <div
                                    className={`h-full rounded-full bg-gradient-to-r ${tier.bar}`}
                                    style={{ width: `${tier.score}%` }}
                                  />
                                </div>
                              </div>
                            </>
                          )
                        })()}
                      </div>
                    ) : (
                      <span className="text-sm text-text-secondary">Toque para escolher um jogador…</span>
                    )}
                  </div>
                  <ChevronDown
                    className={`w-5 h-5 text-semantic-gold/80 shrink-0 transition-transform ${playerMenuOpen ? 'rotate-180' : ''}`}
                  />
                </button>
                {playerMenuOpen && (
                  <div className="absolute z-40 mt-2 w-full rounded-xl border border-white/10 bg-[#070b09] shadow-[0_24px_48px_rgba(0,0,0,0.65)] overflow-hidden backdrop-blur-md">
                    <div className="max-h-[min(60vh,320px)] overflow-y-auto overscroll-contain">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedPlayerId(null)
                          setPlayerMenuOpen(false)
                        }}
                        className="w-full text-left px-3 py-2.5 text-xs text-text-secondary hover:bg-white/5 border-b border-white/5"
                      >
                        Limpar seleção
                      </button>
                      {squadSorted.map((raw) => {
                        const p = raw as { playerid?: number; overall?: number; overallrating?: number; position_label?: string }
                        const id = Number(p.playerid)
                        if (!Number.isFinite(id) || id <= 0) return null
                        const name = resolveSquadPlayerName(raw as Record<string, unknown>)
                        const ov = Number(p.overall ?? p.overallrating ?? 0) || null
                        const pos = String(p.position_label || '—')
                        const rel = relationsByPlayerId.get(id)
                        const tr = Number(rel?.trust ?? 50)
                        const fr = Number(rel?.frustration ?? 0)
                        const tier = partnershipTier(tr, fr)
                        const sel = selectedPlayerId === id
                        return (
                          <button
                            key={id}
                            type="button"
                            onClick={() => {
                              setSelectedPlayerId(id)
                              setPlayerMenuOpen(false)
                            }}
                            className={`w-full flex items-stretch gap-3 px-3 py-2.5 text-left border-b border-white/[0.06] transition-colors ${
                              sel ? 'bg-semantic-gold/10' : 'hover:bg-white/[0.04]'
                            }`}
                          >
                            <div className="w-10 rounded-lg bg-black/40 border border-white/10 flex flex-col items-center justify-center shrink-0 py-1">
                              <span className="text-[8px] text-text-secondary">OVR</span>
                              <span className="text-xs font-black text-white">{ov != null && ov > 0 ? ov : '—'}</span>
                            </div>
                            <div className="flex-1 min-w-0 py-0.5">
                              <p className="text-sm font-bold text-white truncate">{name}</p>
                              <p className="text-[10px] text-text-secondary mt-0.5">{pos}</p>
                              <div className="mt-1.5 flex items-center gap-2">
                                <div className="flex-1 h-1 rounded-full bg-black/60 overflow-hidden border border-white/5">
                                  <div
                                    className={`h-full rounded-full bg-gradient-to-r ${tier.bar}`}
                                    style={{ width: `${tier.score}%` }}
                                  />
                                </div>
                                <span className={`text-[10px] font-bold tabular-nums shrink-0 ${tier.color}`}>{tier.score}</span>
                              </div>
                              <p className="text-[9px] text-text-secondary/90 mt-1">
                                Confiança {tr} · frustração {fr}
                              </p>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
              {squadSorted.length === 0 && (
                <p className="text-xs text-text-secondary">Carregando plantel… abra a página Plantel se continuar vazio.</p>
              )}
              {touchpointForSelected?.context && (
                <p className="text-[11px] text-text-secondary leading-snug border-l-2 border-semantic-gold/40 pl-2">
                  {touchpointForSelected.context}
                </p>
              )}
            </div>
          )}

          {newsHooks.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Ligar à edição do dia (opcional)</p>
              <div className="flex flex-wrap gap-2">
                {newsHooks.map((h, idx) => (
                  <button
                    key={`${h.article_id || idx}-${idx}`}
                    type="button"
                    onClick={() => setNewsHookIdx(newsHookIdx === idx ? null : idx)}
                    className={`px-3 py-1.5 rounded-lg border text-left max-w-full sm:max-w-[48%] ${
                      newsHookIdx === idx ? 'border-semantic-green bg-semantic-green/10' : 'border-white/15 bg-black/20'
                    }`}
                  >
                    <span className="block text-[11px] font-semibold text-white line-clamp-2">{h.headline}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="card-base p-4 min-h-[280px] flex flex-col">
            {interactionDayLocked && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-950/40 px-3 py-2.5 mb-3 text-[11px] text-amber-100/95 leading-relaxed">
                <strong className="text-white">Limite do dia.</strong> Você já usou a interação interna de hoje (diretoria, comissão ou elenco). A próxima fica disponível quando o{' '}
                <strong className="text-white">calendário da carreira</strong> avançar para o próximo dia no jogo.
              </div>
            )}
            <div className="flex-1 space-y-3 mb-4 max-h-[420px] overflow-y-auto pr-1">
              {stepLoading && thread.length === 0 && !interactionDayLocked && (
                <p className="text-sm text-text-secondary animate-pulse">Abrindo conversa…</p>
              )}
              {thread.map((m, i) => (
                <div key={`${i}-${m.role}`} className={`flex gap-2 ${m.role === 'coach' ? 'justify-end' : 'justify-start'}`}>
                  {m.role === 'npc' && (
                    <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                      {interactionTarget === 'board' && <Briefcase className="w-4 h-4 text-white" />}
                      {interactionTarget === 'staff' && <UserRound className="w-4 h-4 text-white" />}
                      {interactionTarget === 'players' && <Users className="w-4 h-4 text-white" />}
                    </div>
                  )}
                  <div
                    className={`max-w-[92%] rounded-2xl px-3 py-2.5 border text-sm leading-relaxed ${
                      m.role === 'coach'
                        ? 'bg-semantic-gold/15 border-semantic-gold/35 text-white rounded-tr-none'
                        : 'bg-white/5 border-white/10 text-white rounded-tl-none'
                    }`}
                  >
                    {m.role === 'npc' && (
                      <p className="text-[10px] uppercase tracking-wider text-semantic-gold/90 mb-1">{npcSpeakerLabel}</p>
                    )}
                    {m.role === 'coach' && (
                      <p className="text-[10px] uppercase tracking-wider text-text-secondary mb-1">Você</p>
                    )}
                    <p className="whitespace-pre-wrap">{m.text}</p>
                  </div>
                </div>
              ))}

              {stepLoading && thread.length > 0 && (
                <div className="flex gap-2 justify-start">
                  <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                    <Users className="w-4 h-4 text-white opacity-50" />
                  </div>
                  <div className="bg-white/5 rounded-2xl rounded-tl-none px-3 py-2 border border-white/10">
                    <div className="flex gap-1 items-center h-5">
                      <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" />
                      <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                      <span className="w-1.5 h-1.5 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }} />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {interactionBlocked && (
              <p className="text-xs text-semantic-gold/90 mb-2">Escolha um jogador no menu acima para iniciar o 1:1.</p>
            )}

            {convDone && interactionDayLocked && (
              <p className="text-xs text-semantic-green mb-3">
                Conversa encerrada — interação de hoje registrada. Volte quando o calendário avançar para outro dia no save.
              </p>
            )}
            {convDone && !interactionDayLocked && (
              <p className="text-xs text-semantic-green mb-3">Conversa encerrada neste tópico.</p>
            )}

            {!interactionDayLocked && !convDone && !interactionBlocked && coachOptions && coachOptions.length > 0 && (
              <div className="space-y-2 mt-auto">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Escolha sua resposta (texto completo)</p>
                <div className="grid grid-cols-1 gap-2">
                  {coachOptions.map((opt, idx) => (
                    <button
                      key={`${opt.tone}-${idx}`}
                      type="button"
                      disabled={stepLoading}
                      onClick={() => handlePickCoachOption(opt)}
                      className="text-left py-2.5 px-3 rounded-xl border border-white/15 bg-black/25 hover:border-semantic-gold/40 hover:bg-white/5 text-xs text-white leading-snug transition-colors disabled:opacity-40 disabled:pointer-events-none"
                    >
                      {opt.text}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {persistResult && (
              <div className="rounded-2xl border border-white/10 bg-black/20 p-3 mt-3">
                <p className="text-sm font-bold text-white">{persistResult.headline || 'Interação registrada'}</p>
                <p className="text-[11px] uppercase tracking-[0.2em] text-text-secondary mt-1">
                  Tom: {String(persistResult.detected_tone || '').toUpperCase()} · Δ reputação {persistResult.reputation_delta ?? 0} · Δ moral{' '}
                  {persistResult.morale_delta ?? 0}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

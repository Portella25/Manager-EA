export const API_BASE = '';

export async function fetchOverview(saveUid?: string) {
  const url = saveUid ? `/companion/overview?save_uid=${saveUid}` : '/companion/overview';
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch overview');
  return res.json();
}

export async function fetchFeed(channel?: string, limit = 30, saveUid?: string) {
  let url = channel ? `/feed/channel/${channel}?limit=${limit}` : `/feed/recent?limit=${limit}`;
  if (saveUid) url += `&save_uid=${saveUid}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch feed');
  return res.json();
}

export async function fetchState() {
  const res = await fetch('/state');
  if (!res.ok) throw new Error('Failed to fetch state');
  return res.json();
}

export async function fetchSquad() {
  const res = await fetch('/state/squad');
  if (!res.ok) throw new Error('Failed to fetch squad');
  return res.json();
}

export async function fetchStandings() {
  const res = await fetch('/state/standings');
  if (!res.ok) throw new Error('Failed to fetch standings');
  return res.json();
}

export async function fetchDashboardHome(saveUid: string, newsLimit = 5, timelineLimit = 6, alertsLimit = 6) {
  const params = new URLSearchParams({
    save_uid: saveUid,
    news_limit: String(newsLimit),
    timeline_limit: String(timelineLimit),
    alerts_limit: String(alertsLimit)
  });
  const res = await fetch(`/dashboard/home?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch dashboard home');
  return res.json();
}

export async function fetchNewsFeedDaily(saveUid: string, date?: string, limit = 7) {
  const params = new URLSearchParams({
    save_uid: saveUid,
    limit: String(limit)
  });
  if (date) params.set('date', date);
  const res = await fetch(`/news/feed/daily?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch daily news feed');
  return res.json();
}

export async function rebuildNewsFeedDaily(saveUid: string, date?: string, limit = 7) {
  const params = new URLSearchParams({
    save_uid: saveUid,
    limit: String(limit)
  });
  if (date) params.set('date', date);
  const res = await fetch(`/news/feed/daily/rebuild?${params.toString()}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to rebuild daily news feed');
  return res.json();
}

export async function fetchConferenceContext(saveUid: string, mode?: string, questionsLimit = 4) {
  const params = new URLSearchParams({
    save_uid: saveUid,
    questions_limit: String(questionsLimit)
  });
  if (mode) params.set('mode', mode);
  const res = await fetch(`/conference/context?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch conference context');
  return res.json();
}

export async function fetchFinanceHub(saveUid?: string, ledgerLimit = 80, transactionsLimit = 40) {
  const params = new URLSearchParams({
    ledger_limit: String(ledgerLimit),
    transactions_limit: String(transactionsLimit)
  })
  if (saveUid) params.set('save_uid', saveUid)
  const res = await fetch(`/finance/hub?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch finance hub')
  return res.json()
}

export async function triggerCrisis(reason: string, severity: string, saveUid?: string) {
  const res = await fetch('/crisis/trigger', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason, severity, save_uid: saveUid })
  });
  if (!res.ok) throw new Error('Failed to trigger crisis');
  return res.json();
}

export async function fetchInternalCommsStep(opts: {
  saveUid?: string
  audience: 'board' | 'players' | 'staff'
  interactionMode: 'group' | 'one_on_one'
  focusPlayerId?: number
  focusPlayerName?: string
  linkedHeadline?: string
  touchpointContext?: string
  topicTypeHint?: string
  messages: Array<{ role: string; text: string }>
}) {
  const body: Record<string, unknown> = {
    save_uid: opts.saveUid,
    audience: opts.audience,
    interaction_mode: opts.interactionMode,
    messages: opts.messages
  }
  if (opts.focusPlayerId != null) body.focus_player_id = opts.focusPlayerId
  if (opts.focusPlayerName) body.focus_player_name = opts.focusPlayerName
  if (opts.linkedHeadline) body.linked_headline = opts.linkedHeadline
  if (opts.touchpointContext) body.touchpoint_context = opts.touchpointContext
  if (opts.topicTypeHint) body.topic_type_hint = opts.topicTypeHint
  const res = await fetch('/companion/internal-comms/step', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) {
    let detail = ''
    try {
      const errBody = await res.json()
      detail = typeof errBody?.detail === 'string' ? errBody.detail : JSON.stringify(errBody)
    } catch {
      detail = res.statusText
    }
    throw new Error(`Comunicação interna (${res.status}): ${detail || res.statusText}`)
  }
  return res.json() as Promise<{
    npc_blocks: string[]
    coach_options: Array<{ tone: string; text: string }>
    conversation_done: boolean
    user_turns_used: number
    max_user_turns: number
    closing_hint?: boolean
    interaction_locked?: boolean
    locked_game_date?: string
  }>
}

export async function respondPressConference(
  question: string,
  answer: string,
  saveUid?: string,
  opts?: {
    audience?: 'board' | 'players' | 'staff'
    responseStyle?: string
    topicType?: string
    focusPlayerId?: number
    focusPlayerName?: string
    interactionMode?: 'group' | 'one_on_one'
    linkedArticleId?: string
    linkedHeadline?: string
    /** Interações da aba Social — conta para limite de 1 conversa interna por dia no save */
    socialInternalComms?: boolean
  }
) {
  const body: Record<string, unknown> = { question, answer: answer || '', save_uid: saveUid }
  if (opts?.socialInternalComms) body.social_internal_comms = true
  if (opts?.audience) body.audience = opts.audience
  if (opts?.responseStyle) body.response_style = opts.responseStyle
  if (opts?.topicType) body.topic_type = opts.topicType
  if (opts?.focusPlayerId != null) body.focus_player_id = opts.focusPlayerId
  if (opts?.focusPlayerName) body.focus_player_name = opts.focusPlayerName
  if (opts?.interactionMode) body.interaction_mode = opts.interactionMode
  if (opts?.linkedArticleId) body.linked_article_id = opts.linkedArticleId
  if (opts?.linkedHeadline) body.linked_headline = opts.linkedHeadline
  const res = await fetch('/press-conference/respond', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error('Failed to respond press conference');
  return res.json();
}

export async function fetchRecentPressConferences(saveUid: string, limit = 10) {
  const params = new URLSearchParams({
    save_uid: saveUid,
    limit: String(limit)
  })
  const res = await fetch(`/press-conference/recent?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch recent press conferences')
  return res.json()
}

export async function uploadTrophyImage(trophyKey: string, file: File): Promise<{ url: string; key: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/uploads/trophy?trophy_key=${encodeURIComponent(trophyKey)}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error('Falha ao enviar imagem do troféu')
  return res.json()
}

export async function uploadClubImage(clubName: string, file: File): Promise<{ url: string; club_name: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`/uploads/club?club_name=${encodeURIComponent(clubName)}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error('Falha ao enviar imagem do clube')
  return res.json()
}

export async function fetchUploadsList(): Promise<{ trophies: string[]; clubs: string[] }> {
  const res = await fetch('/uploads/list')
  if (!res.ok) throw new Error('Falha ao listar uploads')
  return res.json()
}

// Add more API methods as needed

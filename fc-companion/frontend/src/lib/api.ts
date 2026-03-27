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

export async function fetchNewsFeedDaily(saveUid: string, date?: string, limit = 5) {
  const params = new URLSearchParams({
    save_uid: saveUid,
    limit: String(limit)
  });
  if (date) params.set('date', date);
  const res = await fetch(`/news/feed/daily?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch daily news feed');
  return res.json();
}

export async function rebuildNewsFeedDaily(saveUid: string, date?: string, limit = 5) {
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

export async function respondPressConference(question: string, answer: string, saveUid?: string) {
  const res = await fetch('/press-conference/respond', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, answer, save_uid: saveUid })
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

// Add more API methods as needed

import { useCallback, useEffect, useState } from 'react'
import {
  RefreshCw,
  Target,
  Zap,
  Shield,
  Square,
  Octagon,
  Star,
  TrendingUp,
  Activity,
  AlertTriangle,
} from 'lucide-react'

type EnrichedPlayer = {
  playerid: number
  name: string
  position: string
  overall: number
  goals: number
  assists: number
  appearances: number
  clean_sheets: number
  yellow_cards: number
  red_cards: number
  avg_rating: number
  is_goalkeeper?: boolean
  goals_plus_assists?: number
  goals_per_90?: number
  cards_per_90?: number
  clean_sheet_rate?: number
  team_name?: string
}

type CompPayload = {
  competition_id: number
  competition_name: string
  has_player_stats: boolean
  scorers: EnrichedPlayer[]
  assisters: EnrichedPlayer[]
  yellow_cards: EnrichedPlayer[]
  red_cards: EnrichedPlayer[]
  avg_rating: EnrichedPlayer[]
  clean_sheets_goalkeepers: EnrichedPlayer[]
  derived: {
    offensive_contribution: EnrichedPlayer[]
    goals_per_90: EnrichedPlayer[]
    discipline_hot: EnrichedPlayer[]
  }
}

const TOP_RANKING_N = 10

type StatsBundle = { competitions: CompPayload[]; source?: string }

type ApiResponse = {
  club: StatsBundle
  general: StatsBundle
  competitions?: CompPayload[]
  source?: string
}

function positionColor(pos: string) {
  const p = pos.toUpperCase()
  if (p.includes('GOL') || p.includes('GK')) return 'text-yellow-400 bg-yellow-400/10'
  if (p.includes('ZAG') || p.includes('LD') || p.includes('LE') || p.includes('DEF')) return 'text-blue-400 bg-blue-400/10'
  if (p.includes('VOL') || p.includes('MEI') || p.includes('MC') || p.includes('MID')) return 'text-green-400 bg-green-400/10'
  return 'text-orange-400 bg-orange-400/10'
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="w-6 h-6 rounded-full bg-semantic-gold text-black text-xs font-black flex items-center justify-center shrink-0">1</span>
  if (rank === 2) return <span className="w-6 h-6 rounded-full bg-white/30 text-white text-xs font-black flex items-center justify-center shrink-0">2</span>
  if (rank === 3) return <span className="w-6 h-6 rounded-full bg-amber-700/60 text-white text-xs font-black flex items-center justify-center shrink-0">3</span>
  return <span className="w-6 h-6 rounded-full bg-white/5 text-text-secondary text-xs font-bold flex items-center justify-center shrink-0">{rank}</span>
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="card-base p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-semantic-gold">{icon}</span>
        <h3 className="font-condensed font-bold text-sm text-white uppercase tracking-wide">{title}</h3>
      </div>
      {children}
    </section>
  )
}

function RankList({
  players,
  valueKey,
  label,
  format = (v: number) => String(v),
  showTeam = false,
}: {
  players: EnrichedPlayer[]
  valueKey: keyof EnrichedPlayer
  label: string
  format?: (v: number) => string
  showTeam?: boolean
}) {
  const list = players.slice(0, TOP_RANKING_N)
  if (!list.length) return null
  const max = Math.max(...list.map((p) => Number(p[valueKey]) || 0), 1)
  return (
    <div className="space-y-2">
      {list.map((player, i) => {
        const raw = Number(player[valueKey]) || 0
        const pct = Math.min(100, (raw / max) * 100)
        return (
          <div key={`${player.playerid}-${i}`} className="flex items-center gap-3 p-2 rounded-lg bg-white/3 border border-white/5">
            <RankBadge rank={i + 1} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-bold text-white truncate">{player.name}</p>
                {player.position && (
                  <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded ${positionColor(player.position)}`}>
                    {player.position}
                  </span>
                )}
              </div>
              <div className="w-full h-1 rounded-full bg-white/10 mt-1">
                <div className="h-full rounded-full bg-semantic-green" style={{ width: `${pct}%` }} />
              </div>
              <div className="text-[10px] text-text-secondary mt-1 space-y-0.5">
                {showTeam && player.team_name && player.team_name !== '—' && (
                  <p className="text-white/70 font-medium truncate">{player.team_name}</p>
                )}
                {player.appearances > 0 && <p>{player.appearances} jogos</p>}
              </div>
            </div>
            <div className="text-right shrink-0">
              <p className="text-lg font-condensed font-black text-white leading-none">{format(raw)}</p>
              <p className="text-[9px] uppercase text-text-secondary mt-0.5">{label}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function Estatisticas() {
  const [data, setData] = useState<ApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [compIdx, setCompIdx] = useState(0)
  const [scope, setScope] = useState<'club' | 'general'>('club')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/stats/competitions')
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const j: ApiResponse = await r.json()
      setData(j)
      setCompIdx(0)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    setCompIdx(0)
  }, [scope])

  const clubComps = data?.club?.competitions ?? data?.competitions ?? []
  const generalComps = data?.general?.competitions ?? []
  const comps = scope === 'club' ? clubComps : generalComps
  const active = comps[compIdx]

  const showTeam = scope === 'general'

  return (
    <div className="space-y-4 pb-8">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="font-condensed font-bold text-2xl text-white uppercase">Estatísticas</h2>
          <p className="text-[11px] text-text-secondary mt-0.5">
            Competições em que o teu clube está — clube (só o teu plantel) ou geral (como no jogo, todos os jogadores).
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-text-secondary hover:text-white transition"
          aria-label="Atualizar"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {data && (clubComps.length > 0 || generalComps.length > 0) && (
        <div className="flex gap-1 p-1 bg-white/5 rounded-xl max-w-md">
          <button
            type="button"
            onClick={() => setScope('club')}
            className={`flex-1 py-2 rounded-lg text-xs font-bold uppercase tracking-wide transition ${
              scope === 'club' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'
            }`}
          >
            Clube
          </button>
          <button
            type="button"
            onClick={() => setScope('general')}
            className={`flex-1 py-2 rounded-lg text-xs font-bold uppercase tracking-wide transition ${
              scope === 'general' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'
            }`}
          >
            Geral
          </button>
        </div>
      )}

      {error && (
        <div className="card-base p-4 text-sm text-semantic-red">
          {error}
          <button type="button" className="block mt-2 text-xs underline text-text-secondary" onClick={load}>
            Tentar novamente
          </button>
        </div>
      )}

      {loading && !comps.length && <p className="text-text-secondary text-sm py-6 text-center">Carregando…</p>}

      {!loading && !comps.length && !error && (
        <div className="card-base p-6 text-center text-text-secondary text-sm">
          {scope === 'general' && clubComps.length > 0 ? (
            <>
              Aba <strong className="text-white">Geral</strong> precisa de <code className="text-white/80">GetPlayersStats()</code> no export Lua. Atualiza o{' '}
              <code className="text-white/80">companion_export.lua</code> no Live Editor e exporta de novo o <code className="text-white/80">state_lua.json</code>.
            </>
          ) : (
            <>
              Nenhuma competição encontrada em <code className="text-white/80">career_competitionprogress</code>. Entre no modo carreira com o script Lua ativo para exportar{' '}
              <code className="text-white/80">state_lua.json</code>.
            </>
          )}
        </div>
      )}

      {comps.length > 0 && (
        <>
          <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-thin">
            {comps.map((c, i) => (
              <button
                key={`${c.competition_id}-${i}`}
                type="button"
                onClick={() => setCompIdx(i)}
                className={`shrink-0 px-3 py-2 rounded-lg text-[11px] font-bold uppercase tracking-wide border transition ${
                  i === compIdx
                    ? 'bg-semantic-gold text-black border-semantic-gold'
                    : 'bg-white/5 text-text-secondary border-white/10 hover:text-white'
                }`}
              >
                {c.competition_name}
              </button>
            ))}
          </div>

          {active && (
            <div className="space-y-4">
              {!active.has_player_stats && (
                <p className="text-xs text-text-secondary text-center py-2">
                  {scope === 'club'
                    ? 'Sem dados do plantel nesta competição (export Lua / partidas).'
                    : 'Sem dados agregados da competição no jogo para esta prova.'}
                </p>
              )}

              {active.scorers.length > 0 && (
                <Section title="Artilheiros" icon={<Target className="w-4 h-4" />}>
                  <RankList showTeam={showTeam} players={active.scorers} valueKey="goals" label="gols" />
                </Section>
              )}

              {active.assisters.length > 0 && (
                <Section title="Maiores assistências" icon={<Zap className="w-4 h-4" />}>
                  <RankList showTeam={showTeam} players={active.assisters} valueKey="assists" label="assist." />
                </Section>
              )}

              {active.clean_sheets_goalkeepers.length > 0 && (
                <Section title="Jogos sem sofrer gols (goleiros)" icon={<Shield className="w-4 h-4" />}>
                  <RankList showTeam={showTeam} players={active.clean_sheets_goalkeepers} valueKey="clean_sheets" label="jogos s/gol" />
                </Section>
              )}

              {active.yellow_cards.length > 0 && (
                <Section title="Cartões amarelos" icon={<Square className="w-4 h-4" />}>
                  <RankList showTeam={showTeam} players={active.yellow_cards} valueKey="yellow_cards" label="amarelos" />
                </Section>
              )}

              {active.red_cards.length > 0 && (
                <Section title="Cartões vermelhos" icon={<Octagon className="w-4 h-4" />}>
                  <RankList showTeam={showTeam} players={active.red_cards} valueKey="red_cards" label="vermelhos" />
                </Section>
              )}

              {active.avg_rating.length > 0 && (
                <Section title="Nota média" icon={<Star className="w-4 h-4" />}>
                  <RankList
                    showTeam={showTeam}
                    players={active.avg_rating}
                    valueKey="avg_rating"
                    label="média"
                    format={(v) => v.toFixed(1)}
                  />
                </Section>
              )}

              {(active.derived?.offensive_contribution?.length ?? 0) > 0 && (
                <Section title="Contribuição ofensiva (gols + assistências)" icon={<TrendingUp className="w-4 h-4" />}>
                  <RankList
                    showTeam={showTeam}
                    players={active.derived?.offensive_contribution ?? []}
                    valueKey="goals_plus_assists"
                    label="G+A"
                  />
                </Section>
              )}

              {(active.derived?.goals_per_90?.length ?? 0) > 0 && (
                <Section title="Gols / 90 min" icon={<Activity className="w-4 h-4" />}>
                  <RankList
                    showTeam={showTeam}
                    players={active.derived?.goals_per_90 ?? []}
                    valueKey="goals_per_90"
                    label="/90"
                    format={(v) => v.toFixed(2)}
                  />
                </Section>
              )}

              {(active.derived?.discipline_hot?.length ?? 0) > 0 && (
                <Section
                  title="Pressão disciplinar (cartões ponderados / 90)"
                  icon={<AlertTriangle className="w-4 h-4" />}
                >
                  <RankList
                    showTeam={showTeam}
                    players={active.derived?.discipline_hot ?? []}
                    valueKey="cards_per_90"
                    label="/90"
                    format={(v) => v.toFixed(2)}
                  />
                </Section>
              )}

              {active.has_player_stats &&
                !active.scorers.length &&
                !active.assisters.length &&
                !active.clean_sheets_goalkeepers.length &&
                !active.yellow_cards.length &&
                !active.red_cards.length &&
                !active.avg_rating.length &&
                !(active.derived?.offensive_contribution?.length ?? 0) &&
                !(active.derived?.goals_per_90?.length ?? 0) &&
                !(active.derived?.discipline_hot?.length ?? 0) && (
                  <p className="text-xs text-text-secondary text-center py-4">
                    Estatísticas zeradas para esta competição no momento.
                  </p>
                )}

            </div>
          )}
        </>
      )}
    </div>
  )
}

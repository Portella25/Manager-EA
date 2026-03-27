import { useMemo, useState } from 'react'
import { useGameStore } from '../store/useGameStore'

function resolveName(player: any) {
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
  return `Jogador #${player?.playerid || '--'}`
}

function jerseyNumber(player: any) {
  return player?.jerseynumber || player?.jersey_number || player?.kit_number || player?.jersey || '--'
}

function formatMoney(value?: number | null) {
  const safeValue = Number(value ?? 0)
  if (!safeValue) return '—'
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0
  }).format(safeValue)
}

function statTone(value?: number | null) {
  const safeValue = Number(value ?? 0)
  if (safeValue >= 75) return 'text-semantic-green'
  if (safeValue >= 55) return 'text-semantic-gold'
  return 'text-semantic-red'
}

export function Plantel() {
  const { squad, loading } = useGameStore()
  const [viewMode, setViewMode] = useState<'lista' | 'campo'>('campo')
  const players = squad || []

  const sortedPlayers = useMemo(
    () => [...players].sort((a: any, b: any) => Number(b?.overall || 0) - Number(a?.overall || 0)),
    [players]
  )

  const starters = useMemo(() => {
    const selected = {
      GK: sortedPlayers.filter((player: any) => player?.position_group === 'GK').slice(0, 1),
      DEF: sortedPlayers.filter((player: any) => player?.position_group === 'DEF').slice(0, 4),
      MID: sortedPlayers.filter((player: any) => player?.position_group === 'MID').slice(0, 3),
      ATT: sortedPlayers.filter((player: any) => player?.position_group === 'ATT').slice(0, 3)
    }
    const usedIds = new Set([...selected.GK, ...selected.DEF, ...selected.MID, ...selected.ATT].map((player: any) => player.playerid))
    const fillGaps = (group: any[], max: number) => {
      while (group.length < max) {
        const fallback = sortedPlayers.find((player: any) => !usedIds.has(player.playerid))
        if (!fallback) break
        group.push(fallback)
        usedIds.add(fallback.playerid)
      }
    }
    fillGaps(selected.GK, 1)
    fillGaps(selected.DEF, 4)
    fillGaps(selected.MID, 3)
    fillGaps(selected.ATT, 3)
    return selected
  }, [sortedPlayers])

  const summary = useMemo(() => ({
    avgOverall: sortedPlayers.length > 0
      ? Math.round(sortedPlayers.reduce((acc: number, player: any) => acc + Number(player?.overall || 0), 0) / sortedPlayers.length)
      : null,
    contractsTracked: sortedPlayers.filter((player: any) => Boolean(player?.contract_until_label)).length,
    injuriesTracked: sortedPlayers.filter((player: any) => Boolean(player?.injury_status)).length,
    rolesTracked: sortedPlayers.filter((player: any) => Boolean(player?.role_label)).length
  }), [sortedPlayers])

  if (loading && players.length === 0) {
    return <div className="text-center text-text-secondary mt-10">Carregando plantel...</div>
  }

  const renderPlayerNode = (player: any) => {
    const name = resolveName(player)
    const shortName = name.split(' ').slice(-1)[0] || name
    return (
      <div key={player?.playerid} className="flex flex-col items-center gap-1">
        <div className="w-10 h-10 rounded-full bg-white/15 border border-white/30 flex items-center justify-center relative">
          <span className="text-[11px] font-bold text-white">{player?.overall ?? '--'}</span>
          <div className="absolute -top-2 -right-2 bg-black text-white text-[8px] font-bold w-4 h-4 rounded-full flex items-center justify-center border border-white/20">
            {jerseyNumber(player)}
          </div>
        </div>
        <span className="text-[9px] font-bold text-white bg-black/40 px-1.5 py-0.5 rounded max-w-[64px] truncate text-center">
          {shortName}
        </span>
        <span className="text-[8px] uppercase tracking-wide text-text-secondary">{player?.position_label || 'RES'}</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="font-condensed font-bold text-2xl text-white uppercase">Plantel</h2>
          <p className="text-xs text-text-secondary mt-1">Posição BR + overall atual + papel contratual por jogador</p>
        </div>
        <div className="flex space-x-2 bg-white/5 rounded-lg p-1">
          <button
            onClick={() => setViewMode('campo')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${viewMode === 'campo' ? 'bg-semantic-green text-black' : 'text-text-secondary hover:text-white'}`}
          >
            CAMPO
          </button>
          <button
            onClick={() => setViewMode('lista')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${viewMode === 'lista' ? 'bg-semantic-green text-black' : 'text-text-secondary hover:text-white'}`}
          >
            LISTA
          </button>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-3">
        <div className="card-base p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Overall médio</p>
          <p className="text-2xl font-condensed font-bold text-white mt-2">{summary.avgOverall ?? '--'}</p>
        </div>
        <div className="card-base p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Papéis identificados</p>
          <p className="text-2xl font-condensed font-bold text-white mt-2">{summary.rolesTracked}</p>
        </div>
        <div className="card-base p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Contratos rastreados</p>
          <p className="text-2xl font-condensed font-bold text-white mt-2">{summary.contractsTracked}</p>
        </div>
        <div className="card-base p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Status médico</p>
          <p className="text-2xl font-condensed font-bold text-white mt-2">{summary.injuriesTracked}</p>
        </div>
      </section>

      {viewMode === 'campo' ? (
        <div className="relative w-full aspect-[2/3] bg-gradient-to-b from-[#1a4a24] to-[#0f2e16] rounded-xl border-2 border-white/10 overflow-hidden my-4 p-4 flex flex-col justify-between">
          <div className="absolute inset-0 pointer-events-none opacity-20">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-1/6 border-2 border-white rounded-b-lg border-t-0"></div>
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-1/6 border-2 border-white rounded-t-lg border-b-0"></div>
            <div className="absolute top-1/2 left-0 w-full border-t-2 border-white"></div>
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 border-2 border-white rounded-full"></div>
          </div>

          <div className="relative z-10 flex justify-evenly items-center w-full mt-2">
            {starters.ATT.map(renderPlayerNode)}
          </div>
          <div className="relative z-10 flex justify-evenly items-center w-full">
            {starters.MID.map(renderPlayerNode)}
          </div>
          <div className="relative z-10 flex justify-evenly items-center w-full">
            {starters.DEF.map(renderPlayerNode)}
          </div>
          <div className="relative z-10 flex justify-center items-center w-full mb-2">
            {starters.GK.map(renderPlayerNode)}
          </div>
        </div>
      ) : (
        <div className="grid gap-3">
          {sortedPlayers.length === 0 ? (
            <div className="text-center text-text-secondary py-4 text-sm">Nenhum jogador encontrado.</div>
          ) : (
            sortedPlayers.map((player: any) => {
              const name = resolveName(player)
              const subtitle = [
                player?.position_label || 'Posição pendente',
                player?.age ? `${player.age} anos` : null,
                player?.contract_until_label ? `Contrato ${player.contract_until_label}` : null
              ].filter(Boolean).join(' · ')
              const detailLine = [
                player?.role_label ? `Papel ${player.role_label}` : null,
                player?.status_label ? `Clima ${player.status_label}` : null,
                player?.injury_status?.severity ? `Lesão ${player.injury_status.severity}` : null
              ].filter(Boolean).join(' · ')
              const initials = name
                .split(' ')
                .filter(Boolean)
                .slice(0, 2)
                .map((part: string) => part[0]?.toUpperCase() || '')
                .join('') || 'JG'

              return (
                <div key={player.playerid} className="card-base p-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-white/10 rounded-full flex items-center justify-center font-condensed font-bold text-xl text-white relative shrink-0">
                      {initials}
                      <div className="absolute -top-1 -right-1 bg-black text-white text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center border border-white/30">
                        {jerseyNumber(player)}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="font-bold text-white leading-tight truncate">{name}</h3>
                          <p className="text-xs text-text-secondary mt-1">{subtitle || 'Sem dados complementares deste jogador'}</p>
                          {detailLine && <p className="text-[11px] text-text-secondary mt-1 uppercase">{detailLine}</p>}
                        </div>
                        <div className="text-right shrink-0">
                          <p className="font-condensed font-bold text-semantic-green text-2xl leading-none">{player?.overall ?? '--'}</p>
                          <p className="text-[10px] text-text-secondary uppercase mt-1">OVR atual</p>
                          <p className={`text-[10px] uppercase font-bold ${Number(player?.overall_delta || 0) > 0 ? 'text-semantic-green' : Number(player?.overall_delta || 0) < 0 ? 'text-semantic-red' : 'text-text-secondary'}`}>
                            {player?.overall_delta_label || '±0'}
                          </p>
                          <p className="text-[10px] text-text-secondary uppercase">
                            {String(player?.overall_source || '').includes('save_') ? 'save' : String(player?.overall_source || '').includes('reference_') ? 'ref' : 'lua'}
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-2 mt-4">
                        <div className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-text-secondary">Papel</p>
                          <p className="text-sm font-bold text-white mt-1">{player?.role_label || '--'}</p>
                        </div>
                        <div className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-text-secondary">Forma</p>
                          <p className={`text-sm font-bold mt-1 ${statTone(player?.form ? Number(player.form) * 20 : null)}`}>{player?.form ?? '--'}</p>
                        </div>
                        <div className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-text-secondary">Salário</p>
                          <p className="text-sm font-bold text-white mt-1 truncate">{formatMoney(player?.wage_effective || player?.contract_wage)}</p>
                        </div>
                        <div className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-text-secondary">Sharpness</p>
                          <p className="text-sm font-bold text-white mt-1">{player?.sharpness ?? '--'}</p>
                        </div>
                        <div className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-text-secondary">Fitness</p>
                          <p className={`text-sm font-bold mt-1 ${statTone(player?.fitness)}`}>{player?.fitness ?? '--'}</p>
                        </div>
                        <div className="rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                          <p className="text-[10px] uppercase tracking-wide text-text-secondary">Mercado</p>
                          <p className="text-sm font-bold text-white mt-1">{player?.transfer_interest_count ?? 0}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}

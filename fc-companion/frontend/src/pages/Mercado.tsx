import { useMemo, useState } from 'react'
import { useGameStore } from '../store/useGameStore'

type TransferRow = {
  player_name?: string
  fee?: number
  amount?: number
  from_team_name?: string
  to_team_name?: string
  signed_date?: number
  is_loan?: boolean
  type?: string
}

function formatTransferDate(raw: number | undefined): string {
  if (raw == null || raw <= 0) return '—'
  const n = Math.floor(Number(raw))
  if (n < 10000101) return String(raw)
  const y = Math.floor(n / 10000)
  const m = Math.floor((n % 10000) / 100)
  const d = n % 100
  if (y < 2000 || m < 1 || m > 12 || d < 1 || d > 31) return String(raw)
  return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}/${y}`
}

function formatMoney(value: number | undefined | null, isLoan: boolean): string {
  if (isLoan && (!value || value === 0)) return 'Empréstimo'
  if (value == null || value === 0) return 'Grátis'
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1)}M`
  }
  return `R$ ${(value / 1_000).toFixed(0)}K`
}

export function Mercado() {
  const { data, loading } = useGameStore()
  const [viewMode, setViewMode] = useState<'mundo' | 'clube'>('mundo')

  const offers = (data?.state?.transfer_offers || []) as any[]
  const saveHistory = (data?.state?.transfer_history || []) as TransferRow[]
  const marketLive = data?.state?.market_live as
    | {
        history_club?: TransferRow[]
        history_world?: TransferRow[]
        summary?: {
          world_count?: number
          count?: number
          presigned_rows_scanned?: number
          presigned_table_available?: boolean
          le_presigned_has_user_club_rows?: boolean
          club_history_source?: string
          le_club_item_count?: number
        }
        meta_export?: {
          export_version?: string
          source?: string
          user_club_team_id?: number
          user_club_id_seen_in_le_presigned?: boolean
        }
        updated_at?: string
      }
    | undefined

  const thSummary = marketLive?.summary
  const presignedUnavailable = thSummary?.presigned_table_available === false
  const scannedRows = thSummary?.presigned_rows_scanned
  const leHasUserClubRows = thSummary?.le_presigned_has_user_club_rows
  const clubHistorySource = thSummary?.club_history_source
  const leClubGap =
    leHasUserClubRows === false &&
    typeof thSummary?.world_count === 'number' &&
    thSummary.world_count > 0

  const historyClub = useMemo(() => {
    const live = marketLive?.history_club
    if (live && live.length > 0) return live
    return saveHistory
  }, [marketLive?.history_club, saveHistory])

  const historyWorld = useMemo(() => {
    const live = marketLive?.history_world
    if (live && live.length > 0) return live
    return []
  }, [marketLive?.history_world])

  const liveTag =
    marketLive?.meta_export?.source === 'live_editor' ? 'Dados ao vivo (LE)' : 'Save / cache'

  if (loading && !data) {
    return <div className="text-center text-text-secondary mt-10">Carregando mercado...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:justify-between sm:items-center">
        <div>
          <h2 className="font-condensed font-bold text-2xl text-white uppercase">Mercado</h2>
          <p className="text-xs text-text-secondary mt-1">{liveTag}</p>
        </div>
        <div className="flex space-x-2 bg-white/5 rounded-lg p-1 self-start">
          <button
            type="button"
            onClick={() => setViewMode('mundo')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${
              viewMode === 'mundo' ? 'bg-semantic-blue text-black' : 'text-text-secondary hover:text-white'
            }`}
          >
            TODOS OS CLUBES
          </button>
          <button
            type="button"
            onClick={() => setViewMode('clube')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${
              viewMode === 'clube' ? 'bg-semantic-blue text-black' : 'text-text-secondary hover:text-white'
            }`}
          >
            MEU CLUBE
          </button>
        </div>
      </div>

      {viewMode === 'mundo' ? (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Histórico global</h3>
            <span className="text-sm text-text-secondary">{historyWorld.length} registros</span>
          </div>
          <div className="grid gap-3">
            {historyWorld.length === 0 ? (
              <div className="text-center text-text-secondary py-6 text-sm space-y-2">
                <p>
                  Nenhuma transferência global ainda. Garante o script no LE, modo carreira aberto, e pasta{' '}
                  <code className="text-white/80">Desktop\fc_companion\{'{save}'}\transfer_history.json</code>.
                </p>
                {presignedUnavailable ? (
                  <p className="text-semantic-gold/90">
                    O Live Editor não expôs a tabela <code className="text-white/80">career_presignedcontract</code> na memória —
                    tenta recarregar o save no CM ou atualizar o LE.
                  </p>
                ) : typeof scannedRows === 'number' && scannedRows === 0 ? (
                  <p>A tabela de contratos assinados está vazia neste momento (ainda não há transferências registadas no save).</p>
                ) : null}
              </div>
            ) : (
              [...historyWorld].reverse().map((t: TransferRow, i: number) => {
                const fee = t.fee ?? t.amount
                const loan = Boolean(t.is_loan)
                return (
                  <div key={`w-${i}-${t.player_name}`} className="card-base p-3 border-l-4 border-semantic-blue flex flex-col">
                    <div className="flex justify-between items-start mb-2 gap-2">
                      <div>
                        <h4 className="font-bold text-white text-base">{t.player_name || 'Jogador'}</h4>
                        <span className="text-[10px] text-text-secondary">{formatTransferDate(t.signed_date)}</span>
                      </div>
                      <span className="font-condensed font-bold text-semantic-green shrink-0">{formatMoney(fee, loan)}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-text-secondary">
                      <div className="flex flex-col items-start w-[40%] truncate">
                        <span className="text-[9px] uppercase opacity-70">De</span>
                        <span className="font-semibold text-white/80 truncate w-full">{t.from_team_name || '—'}</span>
                      </div>
                      <div className="flex-1 flex justify-center">
                        <span className="text-semantic-blue">→</span>
                      </div>
                      <div className="flex flex-col items-end w-[40%] truncate text-right">
                        <span className="text-[9px] uppercase opacity-70">Para</span>
                        <span className="font-semibold text-white truncate w-full">{t.to_team_name || '—'}</span>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-condensed font-bold text-lg text-white uppercase">Histórico do meu clube</h3>
              <span className="text-sm text-text-secondary">{historyClub.length} registros</span>
            </div>
            {leClubGap ? (
              <p className="text-xs text-semantic-gold/90 bg-white/5 rounded-lg p-3 leading-relaxed">
                O Live Editor devolve transferências globais, mas <strong className="text-white">nenhuma linha na memória usa o ID do teu clube</strong>{' '}
                (<code className="text-white/90">teamid</code>/<code className="text-white/90">offerteamid</code>) — por isso o filtro &quot;meu clube&quot; no LE fica vazio. O companion completa com o{' '}
                <strong className="text-white">histórico extraído do ficheiro de save</strong> (watcher do save). Grava o CM ou reinicia o watcher para atualizar{' '}
                <code className="text-white/80">save_data.json</code>.
              </p>
            ) : null}
            {clubHistorySource === 'save_data_json' ||
            clubHistorySource === 'state_merge' ||
            clubHistorySource === 'save_sqlite_direct' ? (
              <p className="text-xs text-semantic-green/90 bg-white/5 rounded-lg p-2">
                Histórico do clube a partir do <strong className="text-white">ficheiro de save</strong> (SQLite), não só do Live Editor.
              </p>
            ) : null}
            <div className="grid gap-3">
              {historyClub.length === 0 ? (
                <div className="text-center text-text-secondary py-4 text-sm space-y-2">
                  <p>Nenhuma movimentação registrada para o teu clube.</p>
                  {presignedUnavailable ? (
                    <p className="text-semantic-gold/90 text-xs">
                      Sem tabela <code className="text-white/80">career_presignedcontract</code> no LE — o histórico em tempo real não pode ser lido.
                    </p>
                  ) : typeof scannedRows === 'number' && scannedRows === 0 ? (
                    <p className="text-xs">Nenhuma linha na tabela de transferências do jogo (carreira nova ou ainda sem negócios concluídos).</p>
                  ) : null}
                </div>
              ) : (
                [...historyClub].reverse().map((t: TransferRow, i: number) => {
                  const fee = t.fee ?? t.amount
                  const loan = Boolean(t.is_loan)
                  const buy = t.type === 'buy'
                  return (
                    <div
                      key={`c-${i}-${t.player_name}`}
                      className={`card-base p-3 border-l-4 ${buy ? 'border-semantic-green' : 'border-semantic-gold'} flex flex-col`}
                    >
                      <div className="flex justify-between items-start mb-2 gap-2">
                        <div>
                          <h4 className="font-bold text-white text-base">{t.player_name || 'Jogador'}</h4>
                          <span className="text-[10px] uppercase text-text-secondary">
                            {buy ? 'Contratação' : 'Saída'} · {formatTransferDate(t.signed_date)}
                          </span>
                        </div>
                        <span className="font-condensed font-bold text-semantic-green shrink-0">{formatMoney(fee, loan)}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-text-secondary">
                        <div className="flex flex-col items-start w-[40%] truncate">
                          <span className="text-[9px] uppercase opacity-70">De</span>
                          <span className="font-semibold text-white/80 truncate w-full">{t.from_team_name || '—'}</span>
                        </div>
                        <div className="flex-1 flex justify-center">
                          <span className="text-semantic-blue">→</span>
                        </div>
                        <div className="flex flex-col items-end w-[40%] truncate text-right">
                          <span className="text-[9px] uppercase opacity-70">Para</span>
                          <span className="font-semibold text-white truncate w-full">{t.to_team_name || '—'}</span>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-condensed font-bold text-lg text-white uppercase">Propostas / negociações</h3>
              <span className="text-sm text-text-secondary">{offers.length} itens</span>
            </div>
            <div className="grid gap-3">
              {offers.length === 0 ? (
                <div className="text-center text-text-secondary py-4 text-sm">
                  Nenhuma proposta vinda do save. Avança no CM ou gere <code className="text-white/80">save_data.json</code> com ofertas
                  ativas.
                </div>
              ) : (
                [...offers].reverse().map((o: any, i: number) => {
                  const isLoan = Boolean(
                    o.offer_type?.toLowerCase?.().includes('empréstimo') || o.is_loan || o.loan
                  )
                  return (
                    <div
                      key={`o-${i}-${o.player_name}`}
                      className={`card-base p-3 border-l-4 ${isLoan ? 'border-semantic-purple' : 'border-semantic-gold'} flex flex-col`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <h4 className="font-bold text-white text-base">{o.player_name}</h4>
                          <span className="text-[10px] text-text-secondary uppercase">
                            {isLoan ? 'Proposta de empréstimo' : 'Proposta de compra'}
                          </span>
                        </div>
                        <span className="font-condensed font-bold text-semantic-gold text-lg">
                          {formatMoney(o.offer_amount ?? o.fee, isLoan)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs mt-2 bg-white/5 p-2 rounded">
                        <span className="text-text-secondary">
                          Clube interessado: <strong className="text-white">{o.from_team_name || o.interested_team_name || '—'}</strong>
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            o.status?.toLowerCase() === 'aceita'
                              ? 'bg-semantic-green/20 text-semantic-green'
                              : o.status?.toLowerCase() === 'recusada'
                                ? 'bg-semantic-red/20 text-semantic-red'
                                : 'bg-white/10 text-white'
                          }`}
                        >
                          {o.status || 'Pendente'}
                        </span>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { useAppStore } from '../store'
import { useFinanceStore } from '../store/useFinanceStore'

type FinanceTab = 'visao_geral' | 'receitas' | 'despesas' | 'transacoes' | 'orcamento'

function formatMoney(value?: number | null) {
  if (value === null || value === undefined) return '--'
  const safeValue = Number(value)
  if (!Number.isFinite(safeValue)) return '--'
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0
  }).format(safeValue)
}

function amountTone(value?: number | null) {
  if (value === null || value === undefined) return 'text-text-secondary'
  const safeValue = Number(value)
  if (!Number.isFinite(safeValue)) return 'text-text-secondary'
  if (safeValue > 0) return 'text-semantic-green'
  if (safeValue < 0) return 'text-semantic-red'
  return 'text-text-secondary'
}

export function Financas() {
  const saveUid = useAppStore((state) => state.saveUid)
  const { financeHub, loading, error, startPolling, stopPolling } = useFinanceStore()
  const [activeTab, setActiveTab] = useState<FinanceTab>('visao_geral')

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  const overview = financeHub?.overview || {}
  const receitas = financeHub?.receitas || { total: 0, breakdown: [] }
  const despesas = financeHub?.despesas || { total: 0, breakdown: [], wage_tracking: {} }
  const transactions = financeHub?.transactions || { total: 0, items: [] }
  const budget = financeHub?.budget || { current: 0, weekly_allowance: 0, monthly_chart: [], season_baseline: {} }
  const sourceTrace = financeHub?.source_trace || {}
  const hasData = Boolean(financeHub)
  const receitasTotal = receitas?.total ?? (receitas?.breakdown || []).reduce((sum: number, item: any) => sum + Number(item?.amount || 0), 0)
  const despesasTotal = despesas?.total ?? (despesas?.breakdown || []).reduce((sum: number, item: any) => sum + Number(item?.amount || 0), 0)

  const highlightCards = useMemo(
    () => [
      { label: 'Lucro', value: overview.lucro },
      { label: 'Receitas', value: overview.receitas },
      { label: 'Despesas', value: -Math.abs(Number(overview.despesas || 0)) }
    ],
    [overview.despesas, overview.lucro, overview.receitas]
  )

  return (
    <div className="space-y-6 pb-6">
      <div>
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Finanças</h2>
      </div>

      <div className="flex bg-[#0a140d]/80 rounded-lg p-1 border border-white/10 overflow-x-auto">
        <button onClick={() => setActiveTab('visao_geral')} className={`px-3 py-2 rounded-md font-condensed font-bold text-xs uppercase tracking-wide transition-all whitespace-nowrap ${activeTab === 'visao_geral' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'}`}>Visão geral</button>
        <button onClick={() => setActiveTab('receitas')} className={`px-3 py-2 rounded-md font-condensed font-bold text-xs uppercase tracking-wide transition-all whitespace-nowrap ${activeTab === 'receitas' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'}`}>Receitas</button>
        <button onClick={() => setActiveTab('despesas')} className={`px-3 py-2 rounded-md font-condensed font-bold text-xs uppercase tracking-wide transition-all whitespace-nowrap ${activeTab === 'despesas' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'}`}>Despesas</button>
        <button onClick={() => setActiveTab('transacoes')} className={`px-3 py-2 rounded-md font-condensed font-bold text-xs uppercase tracking-wide transition-all whitespace-nowrap ${activeTab === 'transacoes' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'}`}>Transações</button>
        <button onClick={() => setActiveTab('orcamento')} className={`px-3 py-2 rounded-md font-condensed font-bold text-xs uppercase tracking-wide transition-all whitespace-nowrap ${activeTab === 'orcamento' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'}`}>Orçamento</button>
      </div>

      {error && <div className="card-base p-4 text-sm text-semantic-red">{error}</div>}
      {loading && !hasData && <div className="card-base p-4 text-sm text-text-secondary">Carregando módulo financeiro...</div>}

      {activeTab === 'visao_geral' && (
        <section className="space-y-4">
          {(overview.unavailable_metrics || []).length > 0 && (
            <div className="card-base p-3 text-xs text-text-secondary">
              Métricas indisponíveis sem fonte direta do save/Lua: {(overview.unavailable_metrics || []).join(', ')}.
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {highlightCards.map((card) => (
              <div key={card.label} className="card-base p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{card.label}</p>
                <p className={`text-xl font-condensed font-bold mt-2 ${amountTone(card.value)}`}>{formatMoney(card.value)}</p>
              </div>
            ))}
          </div>
          <div className="card-base p-5">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Painel consolidado</h3>
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Valor do clube</p>
                <p className="text-lg font-bold text-white mt-2">{formatMoney(overview.club_value)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Projeção</p>
                <p className={`text-lg font-bold mt-2 ${amountTone(overview.projection)}`}>{formatMoney(overview.projection)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Verba de transferências</p>
                <p className="text-lg font-bold text-white mt-2">{formatMoney(overview.transfer_budget)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Folha anual vs orçamento</p>
                <p className="text-lg font-bold text-white mt-2">{Math.round(Number(overview.wage_utilization || 0) * 100)}%</p>
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === 'receitas' && (
        <section className="card-base p-5">
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Receitas</h3>
          <p className="text-sm text-semantic-green mt-2">{formatMoney(receitasTotal)}</p>
          <div className="space-y-3 mt-4">
            {(receitas.breakdown || []).length === 0 ? (
              <p className="text-sm text-text-secondary">Sem entradas positivas mapeadas no período.</p>
            ) : (
              (receitas.breakdown || []).map((item: any) => (
                <div key={item.label} className="rounded-xl border border-white/10 bg-black/20 p-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-bold text-white">{item.label}</p>
                  <p className="text-sm font-bold text-semantic-green">{formatMoney(item.amount)}</p>
                </div>
              ))
            )}
          </div>
          {(receitas.unavailable_topics || []).length > 0 && (
            <p className="text-xs text-text-secondary mt-4">
              Sem fonte confiável no save/Lua atual para: {(receitas.unavailable_topics || []).join(', ')}.
            </p>
          )}
        </section>
      )}

      {activeTab === 'despesas' && (
        <section className="card-base p-5">
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Despesas</h3>
          <p className="text-sm text-semantic-red mt-2">{despesasTotal == null ? '--' : formatMoney(-Math.abs(Number(despesasTotal)))}</p>
          <div className="space-y-3 mt-4">
            {(despesas.breakdown || []).length === 0 ? (
              <p className="text-sm text-text-secondary">Sem saídas negativas mapeadas no período.</p>
            ) : (
              (despesas.breakdown || []).map((item: any) => (
                <div key={item.label} className="rounded-xl border border-white/10 bg-black/20 p-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-bold text-white">{item.label}</p>
                  <p className="text-sm font-bold text-semantic-red">{formatMoney(-Math.abs(Number(item.amount || 0)))}</p>
                </div>
              ))
            )}
          </div>
          <div className="grid grid-cols-2 gap-3 mt-5">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Folha semanal atletas</p>
              <p className="text-sm font-bold text-white mt-2">{formatMoney(despesas?.wage_tracking?.squad_weekly)}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Salários auxiliares</p>
              <p className="text-sm font-bold text-white mt-2">{formatMoney(despesas?.wage_tracking?.manager_weekly)}</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-3 col-span-2">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Reserva bônus atleta</p>
              <p className="text-sm font-bold text-white mt-2">
                {formatMoney((despesas?.bonus_reserve?.signon_bonus || 0) + (despesas?.bonus_reserve?.performance_bonus_projection || 0))}
              </p>
            </div>
          </div>
          {(despesas.unavailable_topics || []).length > 0 && (
            <p className="text-xs text-text-secondary mt-4">
              Sem fonte confiável no save/Lua atual para: {(despesas.unavailable_topics || []).join(', ')}.
            </p>
          )}
        </section>
      )}

      {activeTab === 'transacoes' && (
        <section className="card-base p-5">
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Transações recentes</h3>
          <p className="text-xs text-text-secondary mt-2">{transactions.total || 0} lançamentos consolidados</p>
          <div className="space-y-3 mt-4">
            {(transactions.items || []).length === 0 ? (
              <p className="text-sm text-text-secondary">Sem transações registradas no ledger.</p>
            ) : (
              (transactions.items || []).map((item: any) => (
                <div key={`${item.id || item.description}-${item.period}`} className="rounded-xl border border-white/10 bg-black/20 p-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-white">{item.description}</p>
                    <p className="text-[11px] uppercase tracking-wide text-text-secondary mt-1">{item.period} · {item.label}</p>
                  </div>
                  <p className={`text-sm font-bold ${amountTone(item.amount)}`}>{formatMoney(item.amount)}</p>
                </div>
              ))
            )}
          </div>
        </section>
      )}

      {activeTab === 'orcamento' && (
        <section className="space-y-4">
          <div className="card-base p-5">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Orçamento atual</h3>
            <p className="text-xl font-condensed font-bold text-white mt-2">{formatMoney(budget.current)}</p>
            <p className="text-sm text-text-secondary mt-1">Verba semanal sugerida: {formatMoney(budget.weekly_allowance)}</p>
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Verba inicial transferências</p>
                <p className="text-sm font-bold text-white mt-2">{formatMoney(budget?.season_baseline?.start_transfer_budget)}</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Verba inicial folha</p>
                <p className="text-sm font-bold text-white mt-2">{formatMoney(budget?.season_baseline?.start_wage_budget)}</p>
              </div>
            </div>
          </div>
          {budget?.season_flow && (
            <div className="card-base p-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-condensed font-bold text-lg text-white uppercase">Fluxo da temporada</h3>
                {typeof budget?.season_flow?.variation_pct === 'number' && (
                  <p className={`text-xs font-bold ${budget.season_flow.variation_pct < 0 ? 'text-semantic-red' : 'text-semantic-green'}`}>
                    Variação {budget.season_flow.variation_pct}%
                  </p>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Receitas</p>
                  <div className="mt-3 space-y-2">
                    {(budget?.season_flow?.income || []).map((item: any) => (
                      <div key={item.label} className="flex items-center justify-between gap-3">
                        <p className="text-xs text-white">{item.label}</p>
                        <p className="text-xs font-bold text-semantic-green">{formatMoney(item.amount)}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Despesas</p>
                  <div className="mt-3 space-y-2">
                    {(budget?.season_flow?.expense || []).map((item: any) => (
                      <div key={item.label} className="flex items-center justify-between gap-3">
                        <p className="text-xs text-white">{item.label}</p>
                        <p className="text-xs font-bold text-semantic-red">{formatMoney(-Math.abs(Number(item.amount || 0)))}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
          <div className="card-base p-5">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Variação por mês</h3>
            <div className="space-y-2 mt-4">
              {(budget.monthly_chart || []).map((item: any) => (
                <div key={item.month} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-bold text-white">{item.month}</p>
                    <p className={`text-sm font-bold ${amountTone(item.net)}`}>{formatMoney(item.net)}</p>
                  </div>
                  <p className="text-[11px] text-text-secondary mt-1">
                    Receitas {formatMoney(item.income)} · Despesas {formatMoney(-Math.abs(Number(item.expense || 0)))}
                  </p>
                </div>
              ))}
            </div>
          </div>
          <div className="card-base p-5">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Rastreamento da origem</h3>
            <div className="space-y-2 mt-3 text-xs text-text-secondary">
              <p>Transfer budget: {sourceTrace.club_transfer_budget_source || '--'}</p>
              <p>Wage budget: {sourceTrace.club_wage_budget_source || '--'}</p>
              <p>Cash balance: {sourceTrace.cash_balance_source || '--'}</p>
              <p>Manager pref: {sourceTrace.manager_pref_source || '--'}</p>
              <p>Squad wages: {sourceTrace.squad_wages_source || '--'}</p>
            </div>
            <div className="mt-4 space-y-2">
              {(sourceTrace.finance_table_candidates || []).slice(0, 6).map((candidate: any) => (
                <div key={candidate.table} className="rounded-lg border border-white/10 bg-black/20 p-2">
                  <p className="text-xs font-bold text-white">{candidate.table}</p>
                  <p className="text-[11px] text-text-secondary mt-1">Campos: {(candidate.column_hits || []).join(', ') || 'sem hits'}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-2">
              {Object.entries(sourceTrace.finance_live_discovered_functions || {}).map(([fnName, fnValue]: any) => (
                <div key={fnName} className="rounded-lg border border-white/10 bg-black/20 p-2">
                  <p className="text-xs font-bold text-white">{fnName}</p>
                  <p className="text-[11px] text-text-secondary mt-1">{typeof fnValue === 'number' ? formatMoney(fnValue) : String(fnValue)}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

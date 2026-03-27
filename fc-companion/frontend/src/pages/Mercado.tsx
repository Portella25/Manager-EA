import { useState } from 'react'
import { useGameStore } from '../store/useGameStore'

export function Mercado() {
  const { data, loading } = useGameStore();
  const [viewMode, setViewMode] = useState<'propostas' | 'historico'>('historico');

  if (loading && !data) {
    return <div className="text-center text-text-secondary mt-10">Carregando mercado...</div>;
  }

  const transferOffers = data?.state?.transfer_offers || [];
  const transferHistory = data?.state?.transfer_history || [];

  const formatCurrency = (value: number | undefined | null) => {
    if (!value || value === 0) return 'Gratuito / Fim de Contrato';
    if (value >= 1000000) {
      return `€ ${(value / 1000000).toFixed(1)}M`;
    }
    return `€ ${(value / 1000).toFixed(0)}K`;
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Mercado</h2>
        <div className="flex space-x-2 bg-white/5 rounded-lg p-1">
          <button 
            onClick={() => setViewMode('historico')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${viewMode === 'historico' ? 'bg-semantic-blue text-black' : 'text-text-secondary hover:text-white'}`}
          >
            MUNDO
          </button>
          <button 
            onClick={() => setViewMode('propostas')}
            className={`px-3 py-1 rounded text-xs font-bold transition-colors ${viewMode === 'propostas' ? 'bg-semantic-blue text-black' : 'text-text-secondary hover:text-white'}`}
          >
            MEU CLUBE
          </button>
        </div>
      </div>

      {viewMode === 'historico' ? (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Transferências Globais</h3>
            <span className="text-sm text-text-secondary">{transferHistory.length} registros</span>
          </div>

          <div className="grid gap-3">
            {transferHistory.length === 0 ? (
              <div className="text-center text-text-secondary py-4 text-sm">Nenhuma transferência registrada recentemente.</div>
            ) : (
              [...transferHistory].reverse().map((t: any, i: number) => (
                <div key={i} className="card-base p-3 border-l-4 border-semantic-blue flex flex-col">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-white text-base">{t.player_name}</h4>
                    <span className="font-condensed font-bold text-semantic-green">{formatCurrency(t.fee)}</span>
                  </div>
                  
                  <div className="flex items-center justify-between text-xs text-text-secondary">
                    <div className="flex flex-col items-start w-[40%] truncate">
                      <span className="text-[9px] uppercase opacity-70">De</span>
                      <span className="font-semibold text-white/80 truncate w-full">{t.from_team_name}</span>
                    </div>
                    
                    <div className="flex-1 flex justify-center">
                      <span className="text-semantic-blue">→</span>
                    </div>

                    <div className="flex flex-col items-end w-[40%] truncate text-right">
                      <span className="text-[9px] uppercase opacity-70">Para</span>
                      <span className="font-semibold text-white truncate w-full">{t.to_team_name}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Caixa de Propostas</h3>
            <span className="text-sm text-text-secondary">{transferOffers.length} propostas</span>
          </div>

          <div className="grid gap-3">
            {transferOffers.length === 0 ? (
              <div className="text-center text-text-secondary py-4 text-sm">Nenhuma proposta na mesa.</div>
            ) : (
              [...transferOffers].reverse().map((o: any, i: number) => {
                const isLoan = o.offer_type?.toLowerCase().includes('empréstimo');
                return (
                  <div key={i} className={`card-base p-3 border-l-4 ${isLoan ? 'border-semantic-purple' : 'border-semantic-gold'} flex flex-col`}>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h4 className="font-bold text-white text-base">{o.player_name}</h4>
                        <span className="text-[10px] text-text-secondary uppercase">{isLoan ? 'Proposta de Empréstimo' : 'Proposta de Compra'}</span>
                      </div>
                      <span className="font-condensed font-bold text-semantic-gold text-lg">{formatCurrency(o.offer_amount)}</span>
                    </div>
                    
                    <div className="flex items-center justify-between text-xs mt-2 bg-white/5 p-2 rounded">
                      <span className="text-text-secondary">Clube interessado: <strong className="text-white">{o.from_team_name}</strong></span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        o.status?.toLowerCase() === 'aceita' ? 'bg-semantic-green/20 text-semantic-green' : 
                        o.status?.toLowerCase() === 'recusada' ? 'bg-semantic-red/20 text-semantic-red' : 
                        'bg-white/10 text-white'
                      }`}>
                        {o.status || 'Pendente'}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
import { useEffect } from 'react'
import { Activity, AlertTriangle } from 'lucide-react'
import { useGameStore } from '../store/useGameStore'
import { useAppStore } from '../store'

export function StatusFisico() {
  const saveUid = useAppStore((s) => s.saveUid)
  const { squad, loading, startPolling, stopPolling } = useGameStore()

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  const injured = (squad || []).filter((p: any) => p?.injury_status && Object.keys(p.injury_status).length > 0)
  const fit = (squad || []).filter((p: any) => !p?.injury_status?.severity)

  return (
    <div className="space-y-6 pb-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-semantic-blue/20 border border-semantic-blue/40 flex items-center justify-center">
          <Activity className="w-5 h-5 text-semantic-blue" />
        </div>
        <div>
          <h2 className="font-condensed font-bold text-2xl text-white uppercase">Status físico</h2>
          <p className="text-xs text-text-secondary">Lesões e disponibilidade a partir do save + export ao vivo</p>
        </div>
      </div>

      {loading && squad.length === 0 ? (
        <div className="card-base p-6 text-text-secondary text-sm">Carregando plantel…</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="card-base p-4">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Disponíveis</p>
              <p className="text-2xl font-condensed font-bold text-semantic-green mt-1">{fit.length}</p>
            </div>
            <div className="card-base p-4 border-semantic-gold/20">
              <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Com alerta / lesão</p>
              <p className="text-2xl font-condensed font-bold text-semantic-gold mt-1">{injured.length}</p>
            </div>
          </div>

          <section className="card-base p-4">
            <h3 className="font-condensed font-bold text-sm text-white uppercase tracking-wide mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-semantic-gold" />
              Lesões e condição
            </h3>
            {injured.length === 0 ? (
              <p className="text-sm text-text-secondary">Nenhum registo de lesão no estado atual.</p>
            ) : (
              <ul className="space-y-2">
                {injured.map((p: any) => (
                  <li
                    key={p.playerid}
                    className="flex justify-between items-start gap-3 border-b border-white/5 pb-2 last:border-0"
                  >
                    <div>
                      <p className="text-sm font-bold text-white">{p.player_name || `ID ${p.playerid}`}</p>
                      <p className="text-xs text-text-secondary">
                        {p.injury_status?.severity ? `Severidade: ${p.injury_status.severity}` : 'Lesão registada'}
                      </p>
                    </div>
                    {p.overall != null && (
                      <span className="text-xs font-mono text-semantic-gold">OVR {p.overall}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}

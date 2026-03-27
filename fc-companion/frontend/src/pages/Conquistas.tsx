import { useGameStore } from '../store/useGameStore'

export function Conquistas() {
  const { data, loading } = useGameStore();

  if (loading && !data) {
    return <div className="text-center text-text-secondary mt-10">Carregando conquistas...</div>;
  }

  const profile = data?.achievements_profile || {};
  const recent = data?.achievements_recent || [];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Conquistas</h2>
        <span className="font-condensed font-bold text-semantic-gold text-xl">{profile.total_points || 0} pts</span>
      </div>

      <div className="space-y-3">
        {recent.length === 0 ? (
          <div className="text-center text-text-secondary py-4 text-sm">Nenhuma conquista desbloqueada.</div>
        ) : (
          recent.map((ach: any) => {
            const isLegendary = ach.rarity === 'lendaria' || ach.rarity === 'epica';
            const colorClass = isLegendary ? 'semantic-gold' : 'semantic-purple';

            return (
              <div key={ach.id} className={`card-base p-4 flex items-center space-x-4 border-l-4 border-${colorClass}`}>
                <div className={`w-12 h-12 rounded-full bg-${colorClass}/20 flex items-center justify-center text-2xl`}>
                  {isLegendary ? '🏆' : '⚡'}
                </div>
                <div className="flex-1">
                  <h3 className={`font-bold text-${colorClass}`}>{ach.title}</h3>
                  <p className="text-xs text-text-secondary">{ach.description}</p>
                </div>
                <div className={`text-${colorClass} font-condensed font-bold`}>
                  +{ach.points}
                </div>
              </div>
            );
          })
        )}

        <div className="card-base p-4 flex items-center space-x-4 opacity-50 grayscale mt-6">
          <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center text-2xl">
            🔒
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-white">Mais Conquistas</h3>
            <p className="text-xs text-text-secondary">Continue jogando para descobrir e desbloquear novas conquistas.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

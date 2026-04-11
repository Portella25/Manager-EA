import { Bell, Settings, User } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useGameStore } from '../store/useGameStore'

export function Header() {
  const { data } = useGameStore();
  const state = data?.state || {};
  const club = state.club || {};
  const manager = state.manager || {};
  const coachProfile = data?.coach_profile || {};
  const legacyProfile = data?.legacy_profile || {};
  const seasonContext = data?.season_context || {};
  const gameDate = seasonContext?.game_date || {};
  const leagueTable = seasonContext?.league_table || {};
  const recentForm = seasonContext?.recent_form?.last_5 || [];

  const clubName = club.team_name || club.name || manager.team_name || 'CLUBE';
  const subtitleParts = [
    gameDate?.label,
    leagueTable?.competition_name || seasonContext?.next_fixture?.competition_name,
    leagueTable?.rank ? `${leagueTable.rank}º lugar` : null
  ].filter(Boolean);
  const repScore = coachProfile.reputation_score || manager.reputation || 50;
  const fanScore = coachProfile.fan_sentiment_score || manager.reputation || 50;
  // Temporada da carreira (save), não "temporadas no legado" / hall of fame
  const tempCount = seasonContext?.career_season ?? legacyProfile.seasons_count ?? 1;
  const repLabel = coachProfile.reputation_label || 'DESCONHECIDO';
  const form = recentForm.length > 0
    ? recentForm.map((item: string) => (item === 'W' ? 'V' : item === 'D' ? 'E' : 'D'))
    : [];

  return (
    <header className="sticky top-0 z-50 bg-[#0a140d]/90 backdrop-blur-md border-b border-white/10 px-4 md:px-6 lg:px-8 py-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {/* Badge Placeholder */}
          <div className="w-10 h-10 rounded-full bg-semantic-gold/20 border border-semantic-gold flex items-center justify-center">
            <span className="text-semantic-gold font-condensed font-bold text-sm">{clubName.substring(0,2).toUpperCase()}</span>
          </div>
          
          <div>
            <h1 className="font-condensed font-bold text-xl leading-tight tracking-wide text-white uppercase">
              {clubName}
            </h1>
            <p className="text-text-secondary text-xs">{subtitleParts.join(' · ') || 'Carreira em andamento'}</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-semantic-gold transition-colors relative">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-2 w-2 h-2 bg-semantic-red rounded-full animate-pulse" />
          </button>
          <Link to="/configuracoes" className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white transition-colors">
            <Settings className="w-5 h-5" />
          </Link>
          <button className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center overflow-hidden">
            <User className="w-4 h-4 text-text-secondary" />
          </button>
        </div>
      </div>

      {/* Stats Strip */}
      <div className="mt-4 flex items-center space-x-2 overflow-x-auto pb-1 no-scrollbar">
        <div className="flex items-center bg-white/5 rounded-full px-3 py-1 border border-white/5">
          <div className="w-5 h-5 rounded-full bg-semantic-blue flex items-center justify-center mr-2">
            <span className="text-[10px] font-bold">VC</span>
          </div>
          <span className="font-condensed font-bold text-semantic-green text-sm mr-1">{repScore}</span>
          <span className="text-[10px] text-text-secondary">REP</span>
        </div>
        
        <div className="flex items-center bg-white/5 rounded-full px-3 py-1 border border-white/5">
          <span className="font-condensed font-bold text-semantic-gold text-sm mr-1">{fanScore}</span>
          <span className="text-[10px] text-text-secondary">TORCIDA</span>
        </div>

        <div className="flex items-center bg-white/5 rounded-full px-3 py-1 border border-white/5">
          <span className="font-condensed font-bold text-white text-sm mr-1">{tempCount}</span>
          <span className="text-[10px] text-text-secondary">TEMP</span>
        </div>

        {/* Form strip */}
        <div className="flex items-center space-x-1 ml-auto pl-2">
          {(form.length > 0 ? form : ['-', '-', '-', '-', '-', '-']).map((res, i) => (
            <span 
              key={i} 
              className={`text-[10px] font-bold w-4 h-4 flex items-center justify-center rounded-sm ${
                res === 'V' ? 'bg-semantic-green/20 text-semantic-green' :
                res === 'E' ? 'bg-semantic-gold/20 text-semantic-gold' :
                'bg-semantic-red/20 text-semantic-red'
              }`}
            >
              {res}
            </span>
          ))}
        </div>
        
        <div className="ml-2 px-2 py-0.5 border border-semantic-gold/50 rounded text-[10px] font-condensed font-bold text-semantic-gold tracking-wider whitespace-nowrap uppercase">
          {repLabel}
        </div>
      </div>
    </header>
  )
}

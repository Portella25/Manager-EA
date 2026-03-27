import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, Newspaper, Users, Briefcase, UserRound } from 'lucide-react'
import { NewsStoryCard } from '../components/premium/NewsStoryCard'
import { SectionHeader } from '../components/premium/SectionHeader'
import { useCareerHubStore } from '../store/useCareerHubStore'
import { useAppStore } from '../store'

export function Social() {
  const navigate = useNavigate()
  const saveUid = useAppStore((state) => state.saveUid)
  const { dailyNews, conferenceContext, loading, startPolling, stopPolling } = useCareerHubStore()
  const [activeTab, setActiveTab] = useState<'news' | 'interactions'>('news')
  const [interactionTarget, setInteractionTarget] = useState<'board' | 'staff' | 'players'>('board')
  const [isTyping, setIsTyping] = useState(false)

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  const newsItems = dailyNews?.stories || []
  const hotQuestions = conferenceContext?.questions || []
  const interactionsByTarget = useMemo(() => {
    const boardQuestion = hotQuestions.find((item: any) => item.topic_type === 'board' || item.topic_type === 'season')
    const playerQuestion = hotQuestions.find((item: any) => item.topic_type === 'player' || item.topic_type === 'locker_room')
    const staffQuestion = hotQuestions.find((item: any) => item.topic_type === 'medical' || item.topic_type === 'match' || item.topic_type === 'tactical')
    return {
      board: boardQuestion,
      players: playerQuestion,
      staff: staffQuestion
    }
  }, [hotQuestions])

  const handleResponse = async (tone: string) => {
    setIsTyping(true)
    setTimeout(() => {
      setIsTyping(false)
    }, 1500)
  }

  const interactionCopy =
    interactionTarget === 'board'
      ? interactionsByTarget.board
      : interactionTarget === 'players'
        ? interactionsByTarget.players
        : interactionsByTarget.staff

  return (
    <div className="space-y-6 pb-6">
      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Social & Mídia</h2>
      </div>

      <div className="flex bg-[#0a140d]/80 rounded-lg p-1 border border-white/10">
        <button
          onClick={() => setActiveTab('news')}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md font-condensed font-bold text-sm transition-all ${
            activeTab === 'news' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'
          }`}
        >
          <Newspaper className="w-4 h-4" />
          NOTÍCIAS
        </button>
        <button
          onClick={() => setActiveTab('interactions')}
          className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md font-condensed font-bold text-sm transition-all ${
            activeTab === 'interactions' ? 'bg-semantic-gold text-black' : 'text-text-secondary hover:text-white'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          INTERAÇÕES
        </button>
      </div>

      {activeTab === 'news' && (
        <div className="space-y-4">
          <SectionHeader title="Edição do dia" subtitle={dailyNews?.game_date || 'Sem data ativa'} actionLabel={`${newsItems.length} matérias`} />
          {newsItems.length > 0 ? (
            newsItems.map((item: any) => (
              <NewsStoryCard key={item.article_id} item={item} onOpen={(articleId) => navigate(`/social/${articleId}`)} />
            ))
          ) : (
            <div className="text-center py-10 text-text-secondary">
              {loading ? 'Carregando notícias editoriais...' : 'Nenhuma notícia recente disponível.'}
            </div>
          )}
        </div>
      )}

      {activeTab === 'interactions' && (
        <div className="space-y-4">
          <SectionHeader title="Interações do dia" subtitle="Temas que podem escalar para coletiva e bastidores" actionLabel="Abrir coletiva" onAction={() => navigate('/coletiva')} />
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            <button 
              onClick={() => setInteractionTarget('board')}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-bold whitespace-nowrap transition-all ${
                interactionTarget === 'board' ? 'bg-white text-black border-white' : 'bg-transparent border-white/20 text-text-secondary'
              }`}
            >
              <Briefcase className="w-4 h-4" /> Diretoria
            </button>
            <button 
              onClick={() => setInteractionTarget('players')}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-bold whitespace-nowrap transition-all ${
                interactionTarget === 'players' ? 'bg-white text-black border-white' : 'bg-transparent border-white/20 text-text-secondary'
              }`}
            >
              <Users className="w-4 h-4" /> Elenco
            </button>
            <button 
              onClick={() => setInteractionTarget('staff')}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border text-xs font-bold whitespace-nowrap transition-all ${
                interactionTarget === 'staff' ? 'bg-white text-black border-white' : 'bg-transparent border-white/20 text-text-secondary'
              }`}
            >
              <UserRound className="w-4 h-4" /> Comissão Técnica
            </button>
          </div>

          <div className="card-base p-4 min-h-[300px] flex flex-col">
            <div className="flex-1 space-y-4 mb-4">
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center shrink-0">
                  {interactionTarget === 'board' && <Briefcase className="w-4 h-4 text-white" />}
                  {interactionTarget === 'players' && <Users className="w-4 h-4 text-white" />}
                  {interactionTarget === 'staff' && <UserRound className="w-4 h-4 text-white" />}
                </div>
                <div className="bg-white/5 rounded-2xl rounded-tl-none p-3 border border-white/10">
                  <p className="text-sm text-white">
                    {interactionCopy?.question || "Ainda não há tema quente suficiente para abrir uma interação contextual."}
                  </p>
                  {interactionCopy?.why_now && (
                    <p className="text-xs text-text-secondary mt-2">
                      {interactionCopy.why_now}
                    </p>
                  )}
                </div>
              </div>

              {isTyping && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-semantic-gold/20 flex items-center justify-center shrink-0">
                    <UserRound className="w-4 h-4 text-semantic-gold" />
                  </div>
                  <div className="bg-semantic-gold/10 rounded-2xl rounded-tl-none p-3 border border-semantic-gold/20">
                    <div className="flex gap-1 items-center h-5">
                      <span className="w-1.5 h-1.5 bg-semantic-gold rounded-full animate-bounce"></span>
                      <span className="w-1.5 h-1.5 bg-semantic-gold rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                      <span className="w-1.5 h-1.5 bg-semantic-gold rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 mt-auto">
              <button 
                onClick={() => handleResponse('agressive')}
                className="py-2 px-3 bg-semantic-red/10 hover:bg-semantic-red/20 border border-semantic-red/30 rounded text-xs font-bold text-white transition-colors"
              >
                Agressivo / Exigente
              </button>
              <button 
                onClick={() => handleResponse('calm')}
                className="py-2 px-3 bg-semantic-blue/10 hover:bg-semantic-blue/20 border border-semantic-blue/30 rounded text-xs font-bold text-white transition-colors"
              >
                Calmo / Conciliador
              </button>
              <button 
                onClick={() => handleResponse('motivational')}
                className="py-2 px-3 bg-semantic-green/10 hover:bg-semantic-green/20 border border-semantic-green/30 rounded text-xs font-bold text-white transition-colors"
              >
                Motivacional
              </button>
              <button 
                onClick={() => handleResponse('analytical')}
                className="py-2 px-3 bg-white/5 hover:bg-white/10 border border-white/20 rounded text-xs font-bold text-white transition-colors"
              >
                Analítico / Frio
              </button>
            </div>

            <button
              onClick={() => navigate('/coletiva')}
              className="w-full mt-3 py-2 px-4 rounded-xl border border-semantic-gold/30 text-semantic-gold text-xs font-bold uppercase tracking-wide"
            >
              Levar para a coletiva dedicada
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

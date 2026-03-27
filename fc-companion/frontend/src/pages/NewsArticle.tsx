import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArticleReader } from '../components/premium/ArticleReader'
import { useCareerHubStore } from '../store/useCareerHubStore'
import { useAppStore } from '../store'

export function NewsArticle() {
  const navigate = useNavigate()
  const { articleId } = useParams()
  const saveUid = useAppStore((state) => state.saveUid)
  const { dailyNews, loading, startPolling, stopPolling } = useCareerHubStore()

  useEffect(() => {
    startPolling(saveUid || undefined)
    return () => stopPolling()
  }, [saveUid, startPolling, stopPolling])

  const article = (dailyNews?.stories || []).find((item: any) => String(item.article_id) === String(articleId))

  if (loading && !article) {
    return <div className="text-center text-text-secondary mt-10">Carregando matéria...</div>
  }

  if (!article) {
    return (
      <div className="space-y-4">
        <div className="card-base p-5">
          <h2 className="font-condensed font-bold text-2xl text-white uppercase">Matéria não encontrada</h2>
          <p className="text-sm text-text-secondary mt-3">A edição atual do dia não contém a matéria solicitada.</p>
          <button onClick={() => navigate('/social')} className="mt-4 text-semantic-gold text-sm font-bold">
            Voltar para Social
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 pb-6">
      <button onClick={() => navigate('/social')} className="text-semantic-gold text-sm font-bold">
        Voltar para Social
      </button>
      <ArticleReader article={article} />
    </div>
  )
}

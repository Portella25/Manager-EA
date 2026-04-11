import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Feed } from './pages/Feed'
import { Plantel } from './pages/Plantel'
import { Carreira } from './pages/Carreira'
import { Legado } from './pages/Legado'
import { Conquistas } from './pages/Conquistas'
import { Configuracoes } from './pages/Configuracoes'
import { Mercado } from './pages/Mercado'
import { Social } from './pages/Social'
import { NewsArticle } from './pages/NewsArticle'
import { Conference } from './pages/Conference'
import { Financas } from './pages/Financas'
import { StatusFisico } from './pages/StatusFisico'
import { Estatisticas } from './pages/Estatisticas'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Feed />} />
          <Route path="plantel" element={<Plantel />} />
          <Route path="carreira" element={<Carreira />} />
          <Route path="legado" element={<Legado />} />
          <Route path="conquistas" element={<Conquistas />} />
          <Route path="configuracoes" element={<Configuracoes />} />
          <Route path="mercado" element={<Mercado />} />
          <Route path="social" element={<Social />} />
          <Route path="financas" element={<Financas />} />
          <Route path="status-fisico" element={<StatusFisico />} />
          <Route path="estatisticas" element={<Estatisticas />} />
          <Route path="social/:articleId" element={<NewsArticle />} />
          <Route path="coletiva" element={<Conference />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App

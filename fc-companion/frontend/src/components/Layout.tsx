import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { BottomNav } from './BottomNav'
import { useAppStore } from '../store'
import { useGameStore } from '../store/useGameStore'
import { useEffect } from 'react'

export function Layout() {
  const customBackground = useAppStore(state => state.customBackground)
  const saveUid = useAppStore(state => state.saveUid)
  const startPolling = useGameStore(state => state.startPolling)
  const stopPolling = useGameStore(state => state.stopPolling)

  useEffect(() => {
    // Start polling game data
    startPolling(saveUid || undefined);
    return () => {
      stopPolling();
    }
  }, [saveUid, startPolling, stopPolling])

  useEffect(() => {
    if (customBackground) {
      document.body.style.backgroundImage = `url(${customBackground})`
      // Add a dark overlay to ensure readability
      document.body.style.boxShadow = "inset 0 0 0 2000px rgba(10, 20, 13, 0.85)"
    } else {
      document.body.style.backgroundImage = 'none'
      document.body.style.boxShadow = 'none'
    }
    
    return () => {
      document.body.style.backgroundImage = 'none'
      document.body.style.boxShadow = 'none'
    }
  }, [customBackground])

  return (
    <div className="flex flex-col min-h-screen bg-transparent max-w-md mx-auto relative shadow-2xl overflow-hidden">
      <Header />
      
      {/* Main scrollable area */}
      <main className="flex-1 overflow-y-auto pb-20 pt-4 px-4 scroll-smooth">
        <Outlet />
      </main>

      <BottomNav />
    </div>
  )
}

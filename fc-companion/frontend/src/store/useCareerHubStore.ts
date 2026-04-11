import { create } from 'zustand'
import { fetchConferenceContext, fetchDashboardHome, fetchNewsFeedDaily, rebuildNewsFeedDaily } from '../lib/api'
import { useAppStore } from './index'

interface CareerHubState {
  dashboardHome: any | null
  dailyNews: any | null
  conferenceContext: any | null
  loading: boolean
  error: string | null
  fetchHubData: (saveUid?: string) => Promise<void>
  rebuildDailyFeed: (saveUid?: string, date?: string) => Promise<void>
  startPolling: (saveUid?: string) => void
  stopPolling: () => void
}

let pollInterval: any = null

function resolveSaveUid(explicitSaveUid?: string): string {
  const appSaveUid = useAppStore.getState().saveUid
  return explicitSaveUid || appSaveUid || 'default_save'
}

export const useCareerHubStore = create<CareerHubState>((set) => ({
  dashboardHome: null,
  dailyNews: null,
  conferenceContext: null,
  loading: false,
  error: null,
  fetchHubData: async (saveUid) => {
    const effectiveSaveUid = resolveSaveUid(saveUid)
    set({ loading: true, error: null })
    try {
      const [dashboardHome, dailyNews, conferenceContext] = await Promise.all([
        fetchDashboardHome(effectiveSaveUid),
        fetchNewsFeedDaily(effectiveSaveUid),
        fetchConferenceContext(effectiveSaveUid, undefined, 6).catch(() => null)
      ])
      set({
        dashboardHome,
        dailyNews,
        conferenceContext,
        loading: false,
        error: null
      })
    } catch (err: any) {
      set({
        loading: false,
        error: err?.message || 'Failed to fetch career hub data'
      })
    }
  },
  rebuildDailyFeed: async (saveUid, date) => {
    const effectiveSaveUid = resolveSaveUid(saveUid)
    set({ loading: true, error: null })
    try {
      const dailyNews = await rebuildNewsFeedDaily(effectiveSaveUid, date)
      const [dashboardHome, conferenceContext] = await Promise.all([
        fetchDashboardHome(effectiveSaveUid),
        fetchConferenceContext(effectiveSaveUid, undefined, 6).catch(() => null)
      ])
      set({
        dailyNews,
        dashboardHome,
        conferenceContext,
        loading: false,
        error: null
      })
    } catch (err: any) {
      set({
        loading: false,
        error: err?.message || 'Failed to rebuild career hub feed'
      })
    }
  },
  startPolling: (saveUid) => {
    if (pollInterval) clearInterval(pollInterval)
    useCareerHubStore.getState().fetchHubData(saveUid)
    pollInterval = setInterval(() => {
      useCareerHubStore.getState().fetchHubData(saveUid)
    }, 5000)
  },
  stopPolling: () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }
}))

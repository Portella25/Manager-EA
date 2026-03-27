import { create } from 'zustand'
import { fetchFinanceHub } from '../lib/api'
import { useAppStore } from './index'

interface FinanceState {
  financeHub: any | null
  loading: boolean
  error: string | null
  fetchFinanceData: (saveUid?: string) => Promise<void>
  startPolling: (saveUid?: string) => void
  stopPolling: () => void
}

let pollInterval: any = null

function resolveSaveUid(explicitSaveUid?: string): string {
  const appSaveUid = useAppStore.getState().saveUid
  return explicitSaveUid || appSaveUid || ''
}

export const useFinanceStore = create<FinanceState>((set) => ({
  financeHub: null,
  loading: false,
  error: null,
  fetchFinanceData: async (saveUid) => {
    const effectiveSaveUid = resolveSaveUid(saveUid)
    set({ loading: true, error: null })
    try {
      const financeHub = await fetchFinanceHub(effectiveSaveUid || undefined)
      set({
        financeHub,
        loading: false,
        error: null
      })
    } catch (err: any) {
      set({
        loading: false,
        error: err?.message || 'Failed to fetch finance hub data'
      })
    }
  },
  startPolling: (saveUid) => {
    if (pollInterval) clearInterval(pollInterval)
    useFinanceStore.getState().fetchFinanceData(saveUid)
    pollInterval = setInterval(() => {
      useFinanceStore.getState().fetchFinanceData(saveUid)
    }, 5000)
  },
  stopPolling: () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }
}))

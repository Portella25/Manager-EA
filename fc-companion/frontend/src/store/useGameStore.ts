import { create } from 'zustand';
import { fetchOverview, fetchSquad, fetchStandings } from '../lib/api';
import { useAppStore } from './index';

interface GameState {
  data: any | null;
  squad: any[];
  standings: any | null;
  loading: boolean;
  error: string | null;
  fetchData: (saveUid?: string) => Promise<void>;
  startPolling: (saveUid?: string) => void;
  stopPolling: () => void;
}

let pollInterval: any = null;

export const useGameStore = create<GameState>((set) => ({
  data: null,
  squad: [],
  standings: null,
  loading: true,
  error: null,
  fetchData: async (saveUid) => {
    try {
      const initialOverview = await fetchOverview(saveUid);
      const detectedSaveUid = initialOverview?.state?.meta?.save_uid;
      const effectiveSaveUid = detectedSaveUid || saveUid;
      if (detectedSaveUid && detectedSaveUid !== useAppStore.getState().saveUid) {
        useAppStore.getState().setSaveUid(detectedSaveUid);
      }
      const [data, squad, standings] = await Promise.all([
        effectiveSaveUid && effectiveSaveUid !== saveUid ? fetchOverview(effectiveSaveUid) : Promise.resolve(initialOverview),
        fetchSquad().catch(() => []),
        fetchStandings().catch(() => null)
      ]);
      set({ data, squad, standings, loading: false, error: null });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },
  startPolling: (saveUid) => {
    if (pollInterval) clearInterval(pollInterval);
    // Fetch immediately
    useGameStore.getState().fetchData(saveUid);
    // Then every 5 seconds
    pollInterval = setInterval(() => {
      useGameStore.getState().fetchData(saveUid);
    }, 5000);
  },
  stopPolling: () => {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }
}));

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  saveUid: string | null
  setSaveUid: (uid: string) => void
  customBackground: string | null
  setCustomBackground: (bg: string | null) => void
  notificationsEnabled: boolean
  setNotificationsEnabled: (enabled: boolean) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      saveUid: 'default_save', // Using a default for now, can be updated later
      setSaveUid: (uid) => set({ saveUid: uid }),
      customBackground: null,
      setCustomBackground: (bg) => set({ customBackground: bg }),
      notificationsEnabled: true,
      setNotificationsEnabled: (enabled) => set({ notificationsEnabled: enabled }),
    }),
    {
      name: 'fc-companion-storage',
    }
  )
)

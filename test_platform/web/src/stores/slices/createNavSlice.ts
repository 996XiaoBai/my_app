import { StateCreator } from 'zustand'
import { NAV_GROUPS } from '@/config/navigation'

export interface NavSlice {
  activeNavId: string
  setActiveNav: (id: string) => void

  focusedNavIndex: number
  setFocusedNavIndex: (index: number) => void
  moveNavFocus: (delta: number) => void
}

export const createNavSlice: StateCreator<NavSlice> = (set) => ({
  activeNavId: 'dashboard',
  setActiveNav: (id) => set({ activeNavId: id }),

  focusedNavIndex: -1,
  setFocusedNavIndex: (index) => set({ focusedNavIndex: index }),
  moveNavFocus: (delta) => set((s) => {
    const allItemsCount = NAV_GROUPS.flatMap(g => g.items).length + 1
    const nextIndex = (s.focusedNavIndex + delta + allItemsCount) % allItemsCount
    return { focusedNavIndex: nextIndex }
  }),
})

import { create } from 'zustand'
import { createUISlice, UISlice } from './slices/createUISlice'
import { createNavSlice, NavSlice } from './slices/createNavSlice'
import { createProjectSlice, ProjectSlice } from './slices/createProjectSlice'
import { resolveAppStoreStorage } from './browserStorage'
import { buildPersistedAppState } from './persistedAppState'
import { NAV_GROUPS, NavItem, NavGroup } from '@/config/navigation'

export type { NavItem, NavGroup }
export { NAV_GROUPS }

/**
 * 聚合应用状态接口
 */
export type AppState = UISlice & NavSlice & ProjectSlice

import { persist } from 'zustand/middleware'

/**
 * 全局应用状态主入口
 * 采用 Slice Pattern 架构，并集成 Persist 中间件确保数据防丢失
 */
export const useAppStore = create<AppState>()(
  persist(
    (...a) => ({
      ...createUISlice(...a),
      ...createNavSlice(...a),
      ...createProjectSlice(...a),
    }),
    {
      name: 'test-platform-storage', // 存储在 localStorage 的 Key
      storage: resolveAppStoreStorage(),
      // 仅持久化关键商业逻辑状态，排除 UI 临时状态（如 Loading）
      partialize: (state) => buildPersistedAppState({
        activeNavId: state.activeNavId,
        activeEnvironment: state.activeEnvironment,
        globalVariables: state.globalVariables,
        expertConflictDecision: state.expertConflictDecision,
        expertDecisionReason: state.expertDecisionReason,
        focusedRowId: state.focusedRowId,
        density: state.density,
        appearance: state.appearance,
        sidebarCollapsed: state.sidebarCollapsed,
        topBarCollapsed: state.topBarCollapsed,
        collaborationRailCollapsed: state.collaborationRailCollapsed,
        sidebarGroupCollapsed: state.sidebarGroupCollapsed,
        requirementContextId: state.requirementContextId,
        moduleSessions: state.moduleSessions,
        taskSnapshots: state.taskSnapshots,
      }),
    }
  )
)

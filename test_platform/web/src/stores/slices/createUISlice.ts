import { StateCreator } from 'zustand'
import { ReviewFinding } from '@/lib/contracts'
import { NAV_GROUPS } from '@/config/navigation'
import {
  createInitialSidebarGroupState,
  setSidebarGroupState,
  toggleSidebarGroupState,
} from '@/lib/sidebarGroups'
import type { ModuleProgressEvent, ModuleSessionState } from '@/lib/moduleSession'
import { clearRecoveredBackendErrors, mergeModuleSession } from '@/lib/moduleSession'
import { buildTaskSnapshot, TaskSnapshot, upsertTaskSnapshot } from '@/lib/taskSnapshots'
import { type Appearance, toggleAppearance } from '@/lib/appearance'
import { getNextDensity, type UIDensity } from '@/lib/uiDensity'

export interface UISlice {
  // 侧边栏
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  topBarCollapsed: boolean
  toggleTopBar: () => void
  collaborationRailCollapsed: boolean
  toggleCollaborationRail: () => void
  sidebarGroupCollapsed: Record<string, boolean>
  toggleSidebarGroup: (groupTitle: string) => void
  setSidebarGroupCollapsed: (groupTitle: string, collapsed: boolean) => void

  // 密度切换
  density: UIDensity
  toggleDensity: () => void

  // 外观模式
  appearance: Appearance
  toggleAppearance: () => void

  // Insight 面板
  insightOpen: boolean
  insightType: 'risk' | 'info' | 'progress'
  insightContent: string | null
  insightSteps: { label: string; status: 'waiting' | 'loading' | 'done' | 'error' }[]
  openInsight: (content: string, type?: 'risk' | 'info' | 'progress') => void
  setInsightSteps: (steps: { label: string; status: 'waiting' | 'loading' | 'done' | 'error' }[]) => void
  updateInsightStep: (index: number, status: 'waiting' | 'loading' | 'done' | 'error') => void
  closeInsight: () => void

  // Command Palette
  commandPaletteOpen: boolean
  toggleCommandPalette: () => void

  // 焦点区域管理 (SIDEBAR | MAIN | INSIGHT)
  activeFocusArea: 'SIDEBAR' | 'MAIN' | 'INSIGHT'
  setActiveFocusArea: (area: 'SIDEBAR' | 'MAIN' | 'INSIGHT') => void

  // 视口感知
  isSmallScreen: boolean
  setIsSmallScreen: (val: boolean) => void

  // V4 & V5: 专家仲裁与高危模式
  expertConflictDecision: string | null
  expertDecisionReason: string | null
  highRiskMode: boolean
  guardrailModalOpen: boolean
  insightFocusMode: boolean
  focusedRowId: string | null
  backendStatus: 'healthy' | 'unstable' | 'offline'
  
  setExpertDecision: (decision: string | null, reason?: string | null) => void
  setHighRiskMode: (val: boolean) => void
  setGuardrailModalOpen: (open: boolean) => void
  setInsightFocusMode: (focus: boolean) => void
  setFocusedRowId: (id: string | null) => void
  setBackendStatus: (status: 'healthy' | 'unstable' | 'offline') => void
  
  // Phase 6: 智能决策与发现
  recommendedRoles: string[]
  reviewFindings: ReviewFinding[]
  requirementContextId: string | null
  moduleSessions: Record<string, ModuleSessionState>
  taskSnapshots: TaskSnapshot[]
  setRecommendedRoles: (roles: string[]) => void
  setReviewFindings: (findings: ReviewFinding[]) => void
  setRequirementContextId: (contextId: string | null) => void
  setModuleSession: (moduleId: string, patch: Partial<ModuleSessionState>) => void
  appendModuleSessionEvent: (moduleId: string, event: ModuleProgressEvent) => void
  clearModuleSession: (moduleId: string) => void
  clearRecoveredBackendErrors: () => void
  captureTaskSnapshot: () => void
  loadTaskSnapshot: (snapshotId: string) => void
  removeTaskSnapshot: (snapshotId: string) => void
}

export const createUISlice: StateCreator<UISlice> = (set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  topBarCollapsed: false,
  toggleTopBar: () => set((s) => ({ topBarCollapsed: !s.topBarCollapsed })),
  collaborationRailCollapsed: false,
  toggleCollaborationRail: () => set((s) => ({ collaborationRailCollapsed: !s.collaborationRailCollapsed })),
  sidebarGroupCollapsed: createInitialSidebarGroupState(NAV_GROUPS.map((group) => group.title)),
  toggleSidebarGroup: (groupTitle) => set((s) => ({
    sidebarGroupCollapsed: toggleSidebarGroupState(s.sidebarGroupCollapsed, groupTitle),
  })),
  setSidebarGroupCollapsed: (groupTitle, collapsed) => set((s) => ({
    sidebarGroupCollapsed: setSidebarGroupState(s.sidebarGroupCollapsed, groupTitle, collapsed),
  })),

  // 密度切换
  density: 'standard' as const,
  toggleDensity: () => set((s) => ({ density: getNextDensity(s.density) })),
  appearance: 'light',
  toggleAppearance: () => set((s) => ({ appearance: toggleAppearance(s.appearance) })),

  insightOpen: false,
  insightType: 'info',
  insightContent: null,
  insightSteps: [],
  openInsight: (content, type = 'info') => set({ insightOpen: true, insightContent: content, insightType: type }),
  setInsightSteps: (steps) => set({ insightSteps: steps, insightOpen: true, insightType: 'progress' }),
  updateInsightStep: (index, status) => set((s) => {
    const newSteps = [...s.insightSteps]
    if (newSteps[index]) newSteps[index].status = status
    return { insightSteps: newSteps }
  }),
  closeInsight: () => set({ insightOpen: false, insightContent: null, insightSteps: [] }),

  commandPaletteOpen: false,
  toggleCommandPalette: () => set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),

  activeFocusArea: 'SIDEBAR',
  setActiveFocusArea: (area) => set({ activeFocusArea: area }),

  isSmallScreen: false,
  setIsSmallScreen: (val) => set({ isSmallScreen: val, sidebarCollapsed: val }),

  expertConflictDecision: null,
  expertDecisionReason: null,
  highRiskMode: false,
  guardrailModalOpen: false,
  insightFocusMode: false,
  focusedRowId: null,
  backendStatus: 'healthy',
  
  setExpertDecision: (decision, reason = null) => set({ expertConflictDecision: decision, expertDecisionReason: reason }),
  setHighRiskMode: (val) => set({ highRiskMode: val }),
  setGuardrailModalOpen: (open) => set({ guardrailModalOpen: open }),
  setInsightFocusMode: (focus) => set({ insightFocusMode: focus }),
  setFocusedRowId: (id) => set({ focusedRowId: id }),
  setBackendStatus: (status) => set({ backendStatus: status }),

  recommendedRoles: [],
  reviewFindings: [],
  requirementContextId: null,
  moduleSessions: {},
  taskSnapshots: [],
  setRecommendedRoles: (roles) => set({ recommendedRoles: roles }),
  setReviewFindings: (findings) => set({ reviewFindings: findings }),
  setRequirementContextId: (contextId) => set({ requirementContextId: contextId }),
  setModuleSession: (moduleId, patch) => set((state) => ({
    moduleSessions: {
      ...state.moduleSessions,
      [moduleId]: mergeModuleSession(state.moduleSessions[moduleId], patch),
    },
  })),
  appendModuleSessionEvent: (moduleId, event) => set((state) => {
    const current = state.moduleSessions[moduleId] || {}
    const nextLogs = [...(current.eventLogs || []), event]
    return {
      moduleSessions: {
        ...state.moduleSessions,
        [moduleId]: mergeModuleSession(current, {
          eventLogs: nextLogs,
        }),
      },
    }
  }),
  clearModuleSession: (moduleId) => set((state) => {
    const nextSessions = { ...state.moduleSessions }
    delete nextSessions[moduleId]
    return { moduleSessions: nextSessions }
  }),
  clearRecoveredBackendErrors: () => set((state) => {
    const nextSessions = clearRecoveredBackendErrors(state.moduleSessions)
    if (nextSessions === state.moduleSessions) {
      return {}
    }
    return { moduleSessions: nextSessions }
  }),
  captureTaskSnapshot: () => set((state) => {
    const snapshot = buildTaskSnapshot({
      moduleSessions: state.moduleSessions,
      reviewFindings: state.reviewFindings,
      requirementContextId: state.requirementContextId,
    })

    if (!snapshot) {
      return {}
    }

    return {
      taskSnapshots: upsertTaskSnapshot(state.taskSnapshots, snapshot),
    }
  }),
  loadTaskSnapshot: (snapshotId) => set((state) => {
    const snapshot = state.taskSnapshots.find((item) => item.id === snapshotId)
    if (!snapshot) {
      return {}
    }

    return {
      moduleSessions: snapshot.moduleSessions,
      reviewFindings: snapshot.reviewFindings,
      requirementContextId: snapshot.requirementContextId,
    }
  }),
  removeTaskSnapshot: (snapshotId) => set((state) => ({
    taskSnapshots: state.taskSnapshots.filter((item) => item.id !== snapshotId),
  })),
})

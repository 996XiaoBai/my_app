import type { TaskSnapshot } from '@/lib/taskSnapshots'
import type { ModuleSessionState } from '@/lib/moduleSession'
import type { UIDensity } from '@/lib/uiDensity'
import type { Appearance } from '@/lib/appearance'

type PersistedAppStateInput = {
  activeNavId: string
  activeEnvironment: string
  globalVariables: Record<string, string>
  expertConflictDecision: string | null
  expertDecisionReason: string | null
  focusedRowId: string | null
  density: UIDensity
  appearance: Appearance
  sidebarCollapsed: boolean
  topBarCollapsed: boolean
  collaborationRailCollapsed: boolean
  sidebarGroupCollapsed: Record<string, boolean>
  requirementContextId: string | null
  moduleSessions: Record<string, ModuleSessionState>
  taskSnapshots: TaskSnapshot[]
}

function sanitizeModuleSession(session: ModuleSessionState): ModuleSessionState {
  return {
    requirement: typeof session.requirement === 'string' ? session.requirement : undefined,
    error: typeof session.error === 'string' ? session.error : null,
    runStatus: typeof session.runStatus === 'string' ? session.runStatus : undefined,
    activeTab: typeof session.activeTab === 'string' ? session.activeTab : undefined,
    downloadBaseName: typeof session.downloadBaseName === 'string' ? session.downloadBaseName : null,
    options: session.options ? { ...session.options } : undefined,
  }
}

export function sanitizePersistedModuleSessions(
  moduleSessions: Record<string, ModuleSessionState>
): Record<string, ModuleSessionState> {
  const sanitized: Record<string, ModuleSessionState> = {}

  Object.entries(moduleSessions).forEach(([moduleId, session]) => {
    sanitized[moduleId] = sanitizeModuleSession(session)
  })

  return sanitized
}

export function sanitizePersistedTaskSnapshots(taskSnapshots: TaskSnapshot[]): TaskSnapshot[] {
  return taskSnapshots.map((snapshot) => ({
    ...snapshot,
    reviewFindings: snapshot.reviewFindings.map((finding) => ({ ...finding })),
    moduleSessions: sanitizePersistedModuleSessions(snapshot.moduleSessions),
  }))
}

export function buildPersistedAppState(state: PersistedAppStateInput): PersistedAppStateInput {
  return {
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
    moduleSessions: sanitizePersistedModuleSessions(state.moduleSessions),
    taskSnapshots: sanitizePersistedTaskSnapshots(state.taskSnapshots),
  }
}

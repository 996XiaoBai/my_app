export interface ModuleProgressEvent {
  type: 'progress'
  stage: string
  message: string
  sequence: number
}

export interface ModuleSessionState {
  requirement?: string
  result?: string | null
  error?: string | null
  runStatus?: string
  activeTab?: string
  downloadBaseName?: string | null
  eventLogs?: ModuleProgressEvent[]
  options?: Record<string, unknown>
}

const BACKEND_UNAVAILABLE_MESSAGE_PATTERN = /后端服务不可达/i

export interface ResolvedModuleSessionState<TOptions extends Record<string, unknown>> {
  requirement: string
  result: string | null
  error: string | null
  runStatus: string
  activeTab: string
  downloadBaseName: string | null
  eventLogs: ModuleProgressEvent[]
  options: TOptions
}

export function mergeModuleSession(
  current: ModuleSessionState | undefined,
  patch: Partial<ModuleSessionState>
): ModuleSessionState {
  return {
    ...(current || {}),
    ...patch,
    options: {
      ...((current && current.options) || {}),
      ...(patch.options || {}),
    },
    eventLogs: patch.eventLogs !== undefined ? patch.eventLogs : current?.eventLogs,
  }
}

export function resolveModuleSession<TOptions extends Record<string, unknown>>(
  session: ModuleSessionState | undefined,
  defaults: {
    runStatus: string
    activeTab: string
    options: TOptions
  }
): ResolvedModuleSessionState<TOptions> {
  return {
    requirement: typeof session?.requirement === 'string' ? session.requirement : '',
    result: typeof session?.result === 'string' ? session.result : null,
    error: typeof session?.error === 'string' ? session.error : null,
    runStatus: typeof session?.runStatus === 'string' ? session.runStatus : defaults.runStatus,
    activeTab: typeof session?.activeTab === 'string' ? session.activeTab : defaults.activeTab,
    downloadBaseName: typeof session?.downloadBaseName === 'string' ? session.downloadBaseName : null,
    eventLogs: Array.isArray(session?.eventLogs) ? session.eventLogs : [],
    options: {
      ...defaults.options,
      ...((session?.options || {}) as Partial<TOptions>),
    },
  }
}

export function serializeModuleSessionResult(value: unknown): string | null {
  if (value == null) {
    return null
  }

  if (typeof value === 'string') {
    return value
  }

  try {
    return JSON.stringify(value)
  } catch {
    return null
  }
}

export function parseStoredModulePayload<T>(value: string | null | undefined, fallback: T): T {
  if (!value) {
    return fallback
  }

  try {
    return JSON.parse(value) as T
  } catch {
    return fallback
  }
}

export function isBackendUnavailableMessage(value: string | null | undefined): boolean {
  return typeof value === 'string' && BACKEND_UNAVAILABLE_MESSAGE_PATTERN.test(value)
}

export function clearRecoveredBackendErrors(
  sessions: Record<string, ModuleSessionState>
): Record<string, ModuleSessionState> {
  let changed = false
  const nextSessions: Record<string, ModuleSessionState> = {}

  Object.entries(sessions).forEach(([moduleId, session]) => {
    if (!isBackendUnavailableMessage(session.error)) {
      nextSessions[moduleId] = session
      return
    }

    changed = true
    nextSessions[moduleId] = {
      ...session,
      error: null,
      runStatus: session.runStatus === 'error' ? 'idle' : session.runStatus,
    }
  })

  return changed ? nextSessions : sessions
}

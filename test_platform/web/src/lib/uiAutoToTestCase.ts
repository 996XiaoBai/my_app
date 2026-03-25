import type { ModuleSessionState } from './moduleSession'

export function buildTestCaseSessionFromUIAuto(input: {
  requirement: string
  result: string
}): Partial<ModuleSessionState> {
  return {
    requirement: input.requirement,
    result: input.result,
    runStatus: 'done',
    activeTab: 'markdown',
    error: null,
    eventLogs: [],
  }
}

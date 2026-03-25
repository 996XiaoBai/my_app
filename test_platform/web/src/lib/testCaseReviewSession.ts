import type { ModuleSessionState } from './moduleSession'

export function buildTestCaseReviewSessionFromTestCase(input: {
  requirement: string
  result: string
}): Partial<ModuleSessionState> {
  return {
    requirement: input.requirement,
    result: null,
    runStatus: 'idle',
    activeTab: 'overview',
    error: null,
    eventLogs: [],
    options: {
      caseInputMode: 'linked',
      caseResult: input.result,
      caseSource: 'generated',
    },
  }
}

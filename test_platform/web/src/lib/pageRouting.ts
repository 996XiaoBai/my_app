export type WorkbenchPageKind =
  | 'dashboard'
  | 'review'
  | 'req-analysis'
  | 'test-cases'
  | 'test-case-review'
  | 'ui-auto'
  | 'weekly-report'
  | 'flowchart'
  | 'api-test'
  | 'generic'
  | 'unknown'

export function resolveWorkbenchPageKind(activeNavId: string): WorkbenchPageKind {
  switch (activeNavId) {
    case 'dashboard':
      return 'dashboard'
    case 'review':
      return 'review'
    case 'req-analysis':
      return 'req-analysis'
    case 'test-cases':
      return 'test-cases'
    case 'test-case-review':
      return 'test-case-review'
    case 'ui-auto':
      return 'ui-auto'
    case 'weekly-report':
      return 'weekly-report'
    case 'flowchart':
      return 'flowchart'
    case 'api-test':
      return 'api-test'
    case 'test-data':
    case 'test-point':
    case 'impact':
    case 'test-plan':
    case 'log-diagnosis':
    case 'perf-test':
      return 'generic'
    default:
      return 'unknown'
  }
}

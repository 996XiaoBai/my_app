import type { ReviewFinding } from './contracts'
import type { ModuleSessionState } from './moduleSession'

export type TaskStageId = 'import' | 'review' | 'design' | 'automation' | 'deliver'

export interface TaskAction {
  label: string
  navId: string
  description: string
}

export interface TaskAssetSummary {
  id: string
  label: string
  navId: string
  sessionKey: string
  done: boolean
}

export interface TaskWorkbenchSummary {
  title: string
  requirement: string
  sourceLabel: string
  riskCount: number
  hasContext: boolean
  currentStage: TaskStageId
  currentStageLabel: string
  primaryAction: TaskAction
  nextActions: TaskAction[]
  assets: TaskAssetSummary[]
}

interface TaskWorkbenchInput {
  moduleSessions: Record<string, ModuleSessionState>
  reviewFindings?: ReviewFinding[]
  requirementContextId?: string | null
}

const STAGE_LABELS: Record<TaskStageId, string> = {
  import: '导入需求',
  review: '风险评审',
  design: '测试设计',
  automation: '自动化生成',
  deliver: '输出沉淀',
}

const TASK_ACTIONS: Record<TaskStageId, TaskAction[]> = {
  import: [
    { label: '开始评审', navId: 'review', description: '先识别风险' },
    { label: '专家模式', navId: 'review', description: '直接去模块' },
  ],
  review: [
    { label: '继续评审', navId: 'review', description: '补角色与风险' },
    { label: '需求分析', navId: 'req-analysis', description: '先拆结构' },
  ],
  design: [
    { label: '测试用例', navId: 'test-cases', description: '继续产出资产' },
    { label: '需求分析', navId: 'req-analysis', description: '补模块与规则' },
    { label: '流程图', navId: 'flowchart', description: '补流程与分支' },
  ],
  automation: [
    { label: 'UI 自动化', navId: 'ui-auto', description: '转自动化产物' },
    { label: '看用例', navId: 'test-cases', description: '先看设计结果' },
  ],
  deliver: [
    { label: '看用例', navId: 'test-cases', description: '继续整理导出' },
    { label: '看流程图', navId: 'flowchart', description: '回看流程与风险' },
  ],
}

const REQUIREMENT_PRIORITY = [
  'review',
  'test-case',
  'req-analysis',
  'flowchart',
  'ui-auto',
  'generic:test-point',
  'generic:test-plan',
  'generic:test-data',
  'generic:impact',
  'generic:log-diagnosis',
]

const ASSET_CONFIG: Omit<TaskAssetSummary, 'done'>[] = [
  { id: 'review', label: '评审报告', navId: 'review', sessionKey: 'review' },
  { id: 'test-point', label: '测试点', navId: 'test-point', sessionKey: 'generic:test-point' },
  { id: 'test-cases', label: '测试用例', navId: 'test-cases', sessionKey: 'test-case' },
  { id: 'flowchart', label: '业务流程图', navId: 'flowchart', sessionKey: 'flowchart' },
  { id: 'ui-auto', label: 'UI 自动化', navId: 'ui-auto', sessionKey: 'ui-auto' },
]

function isCompletedSession(session: ModuleSessionState | undefined): boolean {
  return session?.runStatus === 'done' && Boolean(session.result)
}

function sanitizeTaskTitleLine(line: string): string {
  return line
    .replace(/^#+\s*/, '')
    .replace(/^[-*]\s+/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function pickPrimaryRequirement(moduleSessions: Record<string, ModuleSessionState>): string {
  for (const key of REQUIREMENT_PRIORITY) {
    const requirement = moduleSessions[key]?.requirement
    if (typeof requirement === 'string' && requirement.trim()) {
      return requirement.trim()
    }
  }

  for (const session of Object.values(moduleSessions)) {
    if (typeof session.requirement === 'string' && session.requirement.trim()) {
      return session.requirement.trim()
    }
  }

  return ''
}

export function buildTaskTitle(requirement: string): string {
  const candidate = requirement
    .split('\n')
    .map(sanitizeTaskTitleLine)
    .find((line) => line.length > 0)

  if (!candidate) {
    return '当前测试任务'
  }

  return candidate.length > 20 ? `${candidate.slice(0, 20)}...` : candidate
}

export function buildSeededSessionPatch(
  requirement: string,
  activeTab?: string
): Partial<ModuleSessionState> {
  const trimmed = requirement.trim()
  if (!trimmed) {
    return {}
  }

  return {
    requirement: trimmed,
    ...(activeTab ? { activeTab } : {}),
  }
}

export function buildTaskWorkbenchSummary(input: TaskWorkbenchInput): TaskWorkbenchSummary {
  const requirement = pickPrimaryRequirement(input.moduleSessions)
  const hasContext = Boolean(input.requirementContextId)
  const riskCount = input.reviewFindings?.length || 0

  const assets = ASSET_CONFIG.map((asset) => ({
    ...asset,
    done: isCompletedSession(input.moduleSessions[asset.sessionKey]),
  }))

  const reviewDone = isCompletedSession(input.moduleSessions.review)
  const designDone = assets.some((asset) =>
    ['test-point', 'test-cases', 'flowchart'].includes(asset.id) && asset.done
  )
  const automationDone = assets.some((asset) => asset.id === 'ui-auto' && asset.done)

  let currentStage: TaskStageId = 'import'
  if (requirement || hasContext) {
    currentStage = 'review'
  }
  if (reviewDone) {
    currentStage = 'design'
  }
  if (reviewDone && designDone) {
    currentStage = 'automation'
  }
  if (reviewDone && designDone && automationDone) {
    currentStage = 'deliver'
  }

  const actions = TASK_ACTIONS[currentStage]
  const sourceLabel = hasContext ? '最近上下文' : requirement ? '当前输入' : '待导入'

  return {
    title: buildTaskTitle(requirement),
    requirement,
    sourceLabel,
    riskCount,
    hasContext,
    currentStage,
    currentStageLabel: STAGE_LABELS[currentStage],
    primaryAction: actions[0],
    nextActions: actions,
    assets,
  }
}

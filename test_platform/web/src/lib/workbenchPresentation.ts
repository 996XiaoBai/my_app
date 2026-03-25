import type {
  ApiTestExecutionArtifacts,
  ApiTestExecutionResult,
  ApiTestExecutionStats,
  DashboardMetric,
} from './contracts.ts'
import type { TaskStageId } from './taskWorkbench.ts'

export type PresentationRailStatus = 'idle' | 'running' | 'done' | 'warning'
export type TaskInputMode = 'text' | 'upload' | 'tapd'
export type DashboardQuickAccessTone = 'neutral' | 'accent' | 'success' | 'warning'
export type ResultEmptyMode = 'default' | 'preview'
export type WorkbenchHeaderModule =
  | 'review'
  | 'req-analysis'
  | 'test-case'
  | 'flowchart'
  | 'ui-auto'
  | 'weekly'
  | 'generic'
export type ProgressStepModule = 'test-case' | 'review' | 'ui-auto' | 'weekly'

export interface WorkbenchCopy {
  description: string
  tags: string[]
  emptyTitle: string
  emptyDescription: string
}

export interface TestCaseWorkbenchCopy extends WorkbenchCopy {
  contextHint: string
}

export interface ContextHintWorkbenchCopy extends WorkbenchCopy {
  contextHint: string
}

export interface EmptyStateCopy {
  title: string
  description: string
}

export interface EventLogCopy {
  title: string
  emptyText: string
}

export interface ResultFailureCopy {
  title: string
  actionLabel: string
}

export interface RailStatusBadgeCopy {
  hidden: boolean
  label: string
}

export interface WorkbenchHeaderCopy {
  kicker: string
  title: string
}

export interface WorkbenchRunPresentation {
  stageLabel: string
  primaryActionLabel: string
  railActionLabel: string
}

export interface TopBarPresentation {
  moduleLabel: string
  moduleShortLabel: string
  environmentLabel: string
  environmentBadge: string
  searchPlaceholder: string
}

export interface DashboardQuickAccessCard {
  id: string
  label: string
  navId: string
  stateLabel: string
  actionLabel: string
  tone: DashboardQuickAccessTone
}

export interface DashboardStageTrackItem {
  id: TaskStageId
  label: string
  shortLabel: string
  state: 'completed' | 'active' | 'pending'
}

export interface CollaborationRailOverviewBadge {
  label: string
  tone: DashboardQuickAccessTone
}

export interface CollaborationSectionDigest {
  id: string
  title: string
  countLabel: string
  tone: DashboardQuickAccessTone
}

export interface ApiTestExecutionArtifactCopy {
  key: string
  label: string
  value: string
}

export interface ApiTestExecutionFailureCopy {
  key: string
  title: string
  detail: string
  kind: 'failure' | 'error'
}

export interface ApiTestExecutionPanelCopy {
  statusLabel: string
  summary: string
  statsText: string
  commandText: string
  runDirectoryText: string
  artifacts: ApiTestExecutionArtifactCopy[]
  artifactEmptyText: string
  failureCases: ApiTestExecutionFailureCopy[]
  failureEmptyText: string
  stdoutText: string
  stdoutEmptyText: string
  stderrText: string
  stderrEmptyText: string
}

export interface PresentationRailEntry {
  id: string
  label: string
  value: string
  detail?: string
  status?: PresentationRailStatus
  onClick?: () => void
}

export interface PresentationRailSection {
  id: string
  title: string
  description?: string
  entries: PresentationRailEntry[]
}

const DASHBOARD_METRIC_PRIORITY = ['高风险需求', '已完成资产', '待处理缺陷', '本周执行总量']
const DASHBOARD_QUICK_ACCESS_CONFIG = [
  { id: 'review', label: '需求评审', navId: 'review' },
  { id: 'test-cases', label: '测试用例', navId: 'test-cases' },
  { id: 'req-analysis', label: '需求分析', navId: 'req-analysis' },
  { id: 'flowchart', label: '业务流程图', navId: 'flowchart' },
  { id: 'ui-auto', label: 'UI 自动化', navId: 'ui-auto' },
] as const
const DASHBOARD_STAGE_TRACK = [
  { id: 'import', label: '导入需求', shortLabel: '导入' },
  { id: 'review', label: '风险评审', shortLabel: '评审' },
  { id: 'design', label: '测试设计', shortLabel: '设计' },
  { id: 'automation', label: '自动化生成', shortLabel: '自动化' },
  { id: 'deliver', label: '输出沉淀', shortLabel: '沉淀' },
] as const

const DASHBOARD_METRIC_DELTA_MAP: Record<string, string> = {
  来自最近评审: '最近评审',
  来自流水线回传: '流水线',
  当前任务沉淀: '当前任务',
  等待接入指标: '等待更新',
}
const TOP_BAR_MODULE_SHORT_LABEL_MAP: Record<string, string> = {
  工作台: '工作台',
  需求评审: '评审',
  需求分析: '分析',
  测试点提取: '测试点',
  测试用例: '用例',
  测试数据准备: '数据准备',
  业务流程图: '流程图',
  周报生成: '周报',
  接口测试: '接口',
  性能压测: '性能',
  'UI 自动化': 'UI 自动化',
  设置: '设置',
}
const TOP_BAR_ENVIRONMENT_MAP: Record<string, { label: string; badge: string }> = {
  dev: { label: '开发', badge: 'DEV' },
  test: { label: '测试', badge: 'TEST' },
  staging: { label: '预发', badge: 'PRE' },
  prod: { label: '生产', badge: 'PROD' },
}
const WORKBENCH_HEADER_MAP: Record<Exclude<WorkbenchHeaderModule, 'generic'>, WorkbenchHeaderCopy> = {
  review: { kicker: '风险评审', title: '需求评审' },
  'req-analysis': { kicker: '需求拆解', title: '需求分析' },
  'test-case': { kicker: '测试设计', title: '测试用例' },
  flowchart: { kicker: '流程设计', title: '流程图' },
  'ui-auto': { kicker: '自动化', title: 'UI 自动化' },
  weekly: { kicker: '输出沉淀', title: '测试周报' },
}
const PROGRESS_STEP_LABEL_MAP: Record<ProgressStepModule, Record<string, string>> = {
  'test-case': {
    context: '解析需求',
    associating: '关联风险',
    decomposing: '拆解场景',
    matching: '匹配策略',
    generating: '生成用例',
    evaluating: '整理结果',
    done: '已完成',
  },
  review: {
    reading: '解析需求',
    analyzing: '并行评审',
    grouping: '聚合观点',
    conflicting: '生成结论',
    grading: '整理风险',
    done: '已完成',
  },
  'ui-auto': {
    parsing: '解析输入',
    extracting: '提取结构',
    generating_script: '生成结果',
    organizing: '整理输出',
    done: '已完成',
  },
  weekly: {
    collecting: '整理讨论',
    summarizing: '总结周报',
    publishing: '同步飞书',
    organizing: '整理输出',
    done: '已完成',
  },
}
const API_TEST_EXECUTION_STATUS_LABEL_MAP: Record<string, string> = {
  passed: '通过',
  success: '通过',
  completed: '通过',
  failed: '失败',
  fail: '失败',
  error: '失败',
  running: '执行中',
  executing: '执行中',
  pending: '等待执行',
  skipped: '已跳过',
}
const API_TEST_EXECUTION_ARTIFACT_LABELS: Array<{
  key: Exclude<keyof ApiTestExecutionArtifacts, 'run_dir'>
  label: string
}> = [
  { key: 'generated_script', label: '生成脚本' },
  { key: 'compiled_script', label: '执行脚本' },
  { key: 'junit_xml', label: 'JUnit 报告' },
  { key: 'runtime_config', label: '运行配置' },
  { key: 'asset_snapshot', label: '资产快照' },
  { key: 'case_snapshot', label: '用例快照' },
  { key: 'scene_snapshot', label: '场景快照' },
  { key: 'execution_summary', label: '执行摘要' },
  { key: 'allure_results', label: 'Allure 原始结果' },
  { key: 'allure_archive', label: 'Allure 压缩包' },
]

export function selectPrimaryDashboardMetrics(
  metrics: DashboardMetric[],
  maxCount = 3
): DashboardMetric[] {
  if (metrics.length <= maxCount) {
    return metrics
  }

  const metricMap = new Map(metrics.map((metric) => [metric.label, metric]))
  const selected: DashboardMetric[] = []

  DASHBOARD_METRIC_PRIORITY.forEach((label) => {
    const metric = metricMap.get(label)
    if (metric && selected.length < maxCount) {
      selected.push(metric)
      metricMap.delete(label)
    }
  })

  metrics.forEach((metric) => {
    if (!metricMap.has(metric.label) || selected.length >= maxCount) {
      return
    }
    selected.push(metric)
    metricMap.delete(metric.label)
  })

  return selected
}

export function buildTopBarPresentation(input: {
  moduleLabel: string
  environment: string
}): TopBarPresentation {
  const environment = TOP_BAR_ENVIRONMENT_MAP[input.environment] || {
    label: '环境',
    badge: 'ENV',
  }

  return {
    moduleLabel: input.moduleLabel,
    moduleShortLabel: TOP_BAR_MODULE_SHORT_LABEL_MAP[input.moduleLabel]
      || (input.moduleLabel.length > 4 ? input.moduleLabel.slice(0, 4) : input.moduleLabel),
    environmentLabel: environment.label,
    environmentBadge: environment.badge,
    searchPlaceholder: '搜索任务 / 命令',
  }
}

export function buildDashboardStageTrack(currentStage: TaskStageId): DashboardStageTrackItem[] {
  const currentIndex = DASHBOARD_STAGE_TRACK.findIndex((item) => item.id === currentStage)

  return DASHBOARD_STAGE_TRACK.map((item, index) => ({
    ...item,
    state: index < currentIndex ? 'completed' : index === currentIndex ? 'active' : 'pending',
  }))
}

export function compactDashboardMetricDelta(metric: DashboardMetric): string {
  const trimmed = metric.delta.trim()

  if (!trimmed) {
    return '等待更新'
  }

  if (DASHBOARD_METRIC_DELTA_MAP[trimmed]) {
    return DASHBOARD_METRIC_DELTA_MAP[trimmed]
  }

  return trimmed.length > 8 ? `${trimmed.slice(0, 8)}...` : trimmed
}

function resolveCollaborationSectionTone(
  entries: PresentationRailEntry[]
): DashboardQuickAccessTone {
  const statuses = entries.map((entry) => entry.status || 'idle')

  if (statuses.includes('warning')) {
    return 'warning'
  }

  if (statuses.includes('running')) {
    return 'accent'
  }

  if (statuses.includes('done')) {
    return 'success'
  }

  return 'neutral'
}

export function buildCollaborationRailOverviewBadges(
  sections: PresentationRailSection[]
): CollaborationRailOverviewBadge[] {
  const runningCount = sections.filter((section) =>
    section.entries.some((entry) => entry.status === 'running')
  ).length
  const warningCount = sections.filter((section) =>
    section.entries.some((entry) => entry.status === 'warning')
  ).length

  return [
    { label: `${sections.length} 分区`, tone: 'neutral' },
    ...(runningCount > 0
      ? [{ label: `${runningCount} 进行中`, tone: 'accent' as const }]
      : []),
    ...(warningCount > 0
      ? [{ label: `${warningCount} 需关注`, tone: 'warning' as const }]
      : []),
  ]
}

export function buildCollaborationSectionDigests(
  sections: PresentationRailSection[]
): CollaborationSectionDigest[] {
  return sections.map((section) => ({
    id: section.id,
    title: section.title,
    countLabel: `${section.entries.length} 条`,
    tone: resolveCollaborationSectionTone(section.entries),
  }))
}

export function buildDashboardSnapshotBadges(input: {
  currentStageLabel: string
  riskCount: number
  sourceLabel: string
}): string[] {
  const sourceLabel = input.sourceLabel.includes('上下文')
    ? '上下文'
    : input.sourceLabel.includes('输入')
      ? '当前输入'
      : input.sourceLabel.includes('导入')
        ? '待导入'
        : input.sourceLabel.length > 8
          ? `${input.sourceLabel.slice(0, 8)}...`
          : input.sourceLabel

  return [
    input.currentStageLabel,
    input.riskCount > 0 ? `${input.riskCount} 风险` : '低风险',
    sourceLabel,
  ]
}

export function buildDashboardQuickAccessOverview(
  cards: DashboardQuickAccessCard[]
): string[] {
  const recommendedCount = cards.filter((card) => card.stateLabel === '推荐下一步').length
  const completedCount = cards.filter((card) => ['success', 'warning'].includes(card.tone)).length
  const pendingCount = Math.max(cards.length - recommendedCount - completedCount, 0)

  return [`${recommendedCount} 推荐`, `${completedCount} 完成`, `${pendingCount} 待办`]
}

export function buildDashboardQuickAccessCards(input: {
  currentStage: TaskStageId
  primaryNavId: string
  riskCount: number
  hasRequirement: boolean
  assets: Array<{ id: string; done: boolean }>
}): DashboardQuickAccessCard[] {
  const assetDoneMap = new Map(input.assets.map((asset) => [asset.id, asset.done]))

  return DASHBOARD_QUICK_ACCESS_CONFIG.map((item) => {
    const isRecommended = input.primaryNavId === item.navId
    const isDone = Boolean(assetDoneMap.get(item.id))

    if (item.id === 'review') {
      if (isDone && input.riskCount > 0) {
        return {
          ...item,
          stateLabel: `${input.riskCount} 风险`,
          actionLabel: '看评审',
          tone: 'warning',
        }
      }

      if (isDone) {
        return {
          ...item,
          stateLabel: '已评审',
          actionLabel: '看评审',
          tone: 'success',
        }
      }

      if (!input.hasRequirement) {
        return {
          ...item,
          stateLabel: '开始',
          actionLabel: '开始',
          tone: 'accent',
        }
      }

      return {
        ...item,
        stateLabel: isRecommended ? '推荐下一步' : '待评审',
        actionLabel: '去评审',
        tone: isRecommended ? 'accent' : 'neutral',
      }
    }

    if (item.id === 'req-analysis') {
      if (!input.hasRequirement) {
        return {
          ...item,
          stateLabel: '待输入',
          actionLabel: '去分析',
          tone: 'neutral',
        }
      }

      return {
        ...item,
        stateLabel: isRecommended ? '推荐下一步' : input.currentStage === 'review' ? '待评审' : '可补充',
        actionLabel: '去分析',
        tone: isRecommended ? 'accent' : 'neutral',
      }
    }

    if (isDone) {
        return {
          ...item,
          stateLabel: '已生成',
          actionLabel:
            item.id === 'test-cases'
            ? '看用例'
            : item.id === 'flowchart'
              ? '看流程'
              : '看脚本',
          tone: 'success',
      }
    }

    const pendingStateLabel = !input.hasRequirement
      ? '待输入'
      : isRecommended
        ? '推荐下一步'
        : item.id === 'ui-auto'
          ? input.currentStage === 'review' || input.currentStage === 'import'
            ? '待评审'
            : input.currentStage === 'design'
              ? '待设计'
              : '待生成'
          : input.currentStage === 'review' || input.currentStage === 'import'
            ? '待评审'
            : '可生成'

    return {
      ...item,
      stateLabel: pendingStateLabel,
      actionLabel: '去生成',
      tone: isRecommended ? 'accent' : 'neutral',
    }
  })
}

export function compactRailSections(sections: PresentationRailSection[]): PresentationRailSection[] {
  return sections.map((section) => ({
    id: section.id,
    title: section.title,
    entries: section.entries.map((entry) => ({
      id: entry.id,
      label: entry.label,
      value: entry.value,
      ...(entry.status ? { status: entry.status } : {}),
      ...(entry.onClick ? { onClick: entry.onClick } : {}),
    })),
  }))
}

export function resolveTaskInputMode(input: {
  requirement: string
  filesCount: number
  tapdInput: string
}): TaskInputMode {
  if (input.requirement.trim()) {
    return 'text'
  }

  if (input.filesCount > 0) {
    return 'upload'
  }

  if (input.tapdInput.trim()) {
    return 'tapd'
  }

  return 'text'
}

export function buildHistoryEmptyCopy(): EmptyStateCopy {
  return {
    title: '还没有历史结果',
    description: '完成后保存在这里。',
  }
}

export function buildResultEmptyCopy(input?: {
  mode?: ResultEmptyMode
}): EmptyStateCopy {
  return {
    title: '还没有结果',
    description: input?.mode === 'preview'
      ? '左侧补充后，中间直接展示。'
      : '左侧补充后，直接开始。',
  }
}

export function buildLogEmptyCopy(): string {
  return '开始运行后显示。'
}

export function buildResultFormatErrorCopy(input?: {
  target?: 'markdown' | 'log'
}): EmptyStateCopy {
  return {
    title: '结果暂不可读',
    description: input?.target === 'log' ? '请看执行日志。' : '请看 Markdown 原文。',
  }
}

export function buildResultFailureCopy(input?: {
  mode?: 'generate' | 'process'
}): ResultFailureCopy {
  return {
    title: input?.mode === 'process' ? '处理失败' : '生成失败',
    actionLabel: '重试',
  }
}

export function buildInlineErrorCopy(
  mode: 'generate' | 'process' | 'tapd' | 'export' = 'process'
): string {
  if (mode === 'tapd') {
    return '读取 TAPD 失败'
  }

  if (mode === 'export') {
    return '导出失败'
  }

  return buildResultFailureCopy({
    mode: mode === 'generate' ? 'generate' : 'process',
  }).title
}

export function buildExecutionLogCopy(): EventLogCopy {
  return {
    title: '任务事件',
    emptyText: '等待任务事件...',
  }
}

function buildApiTestExecutionStatusLabel(status?: string): string {
  const normalized = String(status || '').trim().toLowerCase()
  if (!normalized) {
    return '未执行'
  }

  return API_TEST_EXECUTION_STATUS_LABEL_MAP[normalized] || String(status).trim()
}

function buildApiTestExecutionArtifactCopies(
  artifacts?: ApiTestExecutionArtifacts
): ApiTestExecutionArtifactCopy[] {
  if (!artifacts) {
    return []
  }

  return API_TEST_EXECUTION_ARTIFACT_LABELS.flatMap((item) => {
    const value = artifacts[item.key]
    if (typeof value !== 'string' || !value.trim()) {
      return []
    }

    return [{
      key: item.key,
      label: item.label,
      value: value.trim(),
    }]
  })
}

export function buildApiTestExecutionStatsText(stats?: ApiTestExecutionStats): string {
  if (!stats) {
    return '等待执行结果'
  }

  return `总 ${stats.total} / 通过 ${stats.passed} / 失败 ${stats.failed} / 异常 ${stats.errors} / 跳过 ${stats.skipped}`
}

function decodeXmlEntities(value: string): string {
  return value
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, '\'')
    .replace(/&amp;/g, '&')
}

function extractXmlAttribute(source: string, name: string): string {
  const match = source.match(new RegExp(`(?:^|\\s)${name}=(["'])([\\s\\S]*?)\\1`, 'i'))
  return decodeXmlEntities(String(match?.[2] || '').trim())
}

function stripXmlTags(value: string): string {
  return decodeXmlEntities(String(value || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim())
}

export function buildApiTestExecutionFailureCases(
  junitXmlContent?: string
): ApiTestExecutionFailureCopy[] {
  const xml = String(junitXmlContent || '').replace(/<testcase\b[^>]*\/>/gi, '').trim()
  if (!xml) {
    return []
  }

  const cases: ApiTestExecutionFailureCopy[] = []
  const testcasePattern = /<testcase\b([^>]*)>([\s\S]*?)<\/testcase>/gi
  let testcaseMatch: RegExpExecArray | null = testcasePattern.exec(xml)

  while (testcaseMatch) {
    const testcaseAttrs = String(testcaseMatch[1] || '')
    const testcaseBody = String(testcaseMatch[2] || '')
    const failureMatch = testcaseBody.match(/<(failure|error)\b([^>]*)>([\s\S]*?)<\/\1>/i)

    if (failureMatch) {
      const kind = String(failureMatch[1] || '').toLowerCase() === 'error' ? 'error' : 'failure'
      const childAttrs = String(failureMatch[2] || '')
      const message = extractXmlAttribute(childAttrs, 'message')
      const bodyText = stripXmlTags(String(failureMatch[3] || ''))
      const classname = extractXmlAttribute(testcaseAttrs, 'classname')
      const name = extractXmlAttribute(testcaseAttrs, 'name')
      const title = classname && name ? `${classname}::${name}` : name || classname || `失败用例 ${cases.length + 1}`

      cases.push({
        key: `${kind}-${cases.length}`,
        title,
        detail: message || bodyText || (kind === 'error' ? '执行异常' : '断言失败'),
        kind,
      })
    }

    testcaseMatch = testcasePattern.exec(xml)
  }

  return cases
}

export function buildApiTestExecutionPanelCopy(
  execution?: ApiTestExecutionResult
): ApiTestExecutionPanelCopy {
  const commandText = String(execution?.command || '').trim()
  const summaryText = String(execution?.summary || '').trim()
  const runDirectoryText = String(execution?.artifacts?.run_dir || '').trim()
  const stdoutText = String(execution?.stdout || '')
  const stderrText = String(execution?.stderr || '')
  const failureCases = buildApiTestExecutionFailureCases(execution?.junit_xml_content)

  return {
    statusLabel: buildApiTestExecutionStatusLabel(execution?.status),
    summary: summaryText || '当前结果未包含执行摘要。',
    statsText: buildApiTestExecutionStatsText(execution?.stats),
    commandText: commandText || '未记录执行命令',
    runDirectoryText: runDirectoryText || '未记录运行目录',
    artifacts: buildApiTestExecutionArtifactCopies(execution?.artifacts),
    artifactEmptyText: '暂无落盘产物',
    failureCases,
    failureEmptyText: '未解析到失败用例',
    stdoutText,
    stdoutEmptyText: '无标准输出',
    stderrText,
    stderrEmptyText: '无错误输出',
  }
}

export function buildRunStateValue(input: {
  status: 'idle' | 'running' | 'done' | 'error'
  idleLabel?: string
  runningLabel: string
  doneLabel: string
  errorLabel?: string
}): string {
  if (input.status === 'done') {
    return input.doneLabel
  }

  if (input.status === 'running') {
    return input.runningLabel
  }

  if (input.status === 'error') {
    return input.errorLabel || '失败'
  }

  return input.idleLabel || '等待开始'
}

export function buildRailStatusBadgeCopy(status: PresentationRailStatus): RailStatusBadgeCopy {
  if (status === 'idle') {
    return {
      hidden: true,
      label: '',
    }
  }

  if (status === 'running') {
    return {
      hidden: false,
      label: '进行中',
    }
  }

  if (status === 'done') {
    return {
      hidden: false,
      label: '完成',
    }
  }

  return {
    hidden: false,
    label: '注意',
  }
}

export function buildWorkbenchHeaderCopy(input: {
  module: WorkbenchHeaderModule
  label?: string
}): WorkbenchHeaderCopy {
  if (input.module === 'generic') {
    return {
      kicker: '专家模块',
      title: input.label || '专家模块',
    }
  }

  return WORKBENCH_HEADER_MAP[input.module]
}

export function buildProgressStepLabelMap(module: ProgressStepModule): Record<string, string> {
  return { ...PROGRESS_STEP_LABEL_MAP[module] }
}

export function buildReviewWorkbenchCopy(input: {
  selectedRolesCount: number
  findingsCount: number
  hasResult: boolean
  hasContext: boolean
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy()

  return {
    description: input.hasResult ? '先看风险，再继续。' : '先输需求，再看风险。',
    tags: [
      input.hasResult ? '已完成' : '待评审',
      `${input.selectedRolesCount} 个角色`,
      input.findingsCount > 0 ? `${input.findingsCount} 个风险` : input.hasResult ? '评审已完成' : '待生成',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文已接入输入区，可直接补充后开始评审。'
      : '支持粘贴需求、上传文档或读取 TAPD。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildTestCaseWorkbenchCopy(input: {
  hasResult: boolean
  hasContext: boolean
}): TestCaseWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy()

  return {
    description: '直接产出测试资产。',
    tags: [
      input.hasResult ? '已生成' : '待生成',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文已接入输入区，可直接开始生成测试用例。'
      : '支持粘贴需求、上传文档或读取 TAPD。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildRequirementAnalysisWorkbenchCopy(input: {
  hasResult: boolean
  hasContext: boolean
  moduleCount: number
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy({ mode: 'preview' })

  return {
    description: '先拆结构，再继续设计。',
    tags: [
      input.hasResult ? '已生成' : '待生成',
      input.moduleCount > 0 ? `${input.moduleCount} 个模块` : '模块拆解',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文可直接带入输入区，补充后再执行结构化分析。'
      : '支持粘贴需求或上传文档。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildFlowchartWorkbenchCopy(input: {
  moduleCount: number
  warningCount: number
  hasMarkdown: boolean
  hasContext: boolean
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy({ mode: 'preview' })

  return {
    description: input.moduleCount > 0 ? '先看主流程，再补异常。' : '先贴流程，再看图。',
    tags: [
      input.hasMarkdown ? '已生成' : '待生成',
      input.moduleCount > 0 ? `${input.moduleCount} 个模块` : 'Mermaid 图',
      input.warningCount > 0 ? `${input.warningCount} 条风险` : input.hasMarkdown ? '可导出 Markdown' : '待生成',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文已接入输入区，可直接补充后生成流程图。'
      : '支持粘贴流程或上传文档。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildUiAutoWorkbenchCopy(input: {
  taskLabel: string
  frameworkLabel: string
  hasResult: boolean
  hasContext: boolean
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy()

  return {
    description: input.hasResult ? '先看结果，再回写。' : '先定产物，再生成。',
    tags: [
      input.hasResult ? '已生成' : '待生成',
      input.taskLabel,
      input.frameworkLabel,
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文可直接带入输入区，确认任务类型后即可开始生成。'
      : '支持粘贴需求或上传附件。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildWeeklyReportWorkbenchCopy(input: {
  publishToFeishu: boolean
  screenshotsCount: number
  hasResult: boolean
  hasContext: boolean
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy()

  return {
    description: input.hasResult ? '先看结论，再发布。' : '先收结论，再生成周报。',
    tags: [
      input.hasResult ? '已生成' : '待生成',
      input.screenshotsCount > 0 ? `${input.screenshotsCount} 张截图` : 'Markdown 周报',
      input.publishToFeishu ? '飞书同步开启' : '仅 Markdown',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文可直接带入输入区，确认本周结论后即可开始生成。'
      : '支持粘贴讨论结论或上传截图。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildApiTestWorkbenchCopy(input: {
  hasResult: boolean
  hasContext: boolean
  executeAfterGenerate: boolean
  hasExecution: boolean
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy()

  return {
    description: input.hasResult
      ? input.hasExecution ? '先看报告，再决定回放或复跑。' : '先看资产，再决定是否执行。'
      : '先生成资产，再决定是否执行。',
    tags: [
      input.hasResult ? '已生成' : '待生成',
      input.executeAfterGenerate ? '执行模式开启' : '仅生成资产',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文可直接带入输入区，补充 OpenAPI 文档或接口说明后即可开始生成。'
      : '支持上传 OpenAPI 文档或直接粘贴接口说明。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function buildGenericWorkbenchCopy(input: {
  isStructured: boolean
  hasResult: boolean
  hasContext: boolean
}): ContextHintWorkbenchCopy {
  const emptyCopy = buildResultEmptyCopy()

  return {
    description: input.hasResult ? '先看结果，再决定下一步。' : '先交给专家，再看结果。',
    tags: [
      input.hasResult ? '已生成' : '待生成',
      input.isStructured ? '结构化结果' : 'Markdown 结果',
      ...(input.hasContext ? ['已联动'] : []),
    ],
    contextHint: input.hasContext
      ? '最近上下文可直接带入输入区，补充后即可开始处理。'
      : '支持输入内容或上传附件。',
    emptyTitle: emptyCopy.title,
    emptyDescription: emptyCopy.description,
  }
}

export function resolveWorkbenchRunPresentation(input: {
  status: 'idle' | 'running' | 'done' | 'error'
  idleStageLabel: string
  doneStageLabel: string
  idleActionLabel: string
  runningActionLabel: string
}): WorkbenchRunPresentation {
  return {
    stageLabel: input.status === 'done' ? input.doneStageLabel : input.idleStageLabel,
    primaryActionLabel: input.status === 'running' ? input.runningActionLabel : `立即${input.idleActionLabel}`,
    railActionLabel: input.status === 'running' ? input.runningActionLabel : `立即${input.idleActionLabel}`,
  }
}

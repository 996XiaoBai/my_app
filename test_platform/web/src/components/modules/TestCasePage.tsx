'use client'

import { useMemo, useState } from 'react'
import { GitBranch, ListChecks, Play, Sparkles } from 'lucide-react'
import { useAppStore } from '@/stores/useAppStore'
import { useTestGenerator } from '@/hooks/useTestGenerator'
import { apiClient, RunProgressEvent, RunStreamEvent } from '@/lib/api'
import { TestCaseStep, TestCaseSuite } from '@/lib/contracts'
import { downloadMarkdownFile } from '@/lib/markdownFile'
import { buildMarkdownDownloadFilename, resolveTestCaseExportBaseName } from '@/lib/testCaseExportName'
import { buildSeededSessionPatch, buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import { buildTestCaseReviewSessionFromTestCase } from '@/lib/testCaseReviewSession'
import { parseTapdInput } from '@/lib/tapdInput'
import { getTestCaseItems, getTestCaseMarkdown, getVisibleTestCaseColumns, sortTestCasesByPriority } from '@/lib/testCaseResult'
import {
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildProgressStepLabelMap,
  buildResultEmptyCopy,
  buildTestCaseWorkbenchCopy,
  buildWorkbenchHeaderCopy,
  buildRunStateValue,
  compactRailSections,
  resolveTaskInputMode,
  resolveWorkbenchRunPresentation,
  type TaskInputMode,
} from '@/lib/workbenchPresentation'
import {
  getWorkbenchRailWrapperClassName,
  getWorkbenchResultPanelClassName,
  getWorkbenchStackClassName,
} from '@/lib/workbenchLayout'
import {
  getWorkbenchResultActionGroupClassName,
  getWorkbenchModeButtonClassName,
  getWorkbenchModeSwitchClassName,
  getWorkbenchPrimaryActionStripClassName,
  getWorkbenchResultActionClassName,
  getWorkbenchResultTabClassName,
  getWorkbenchResultToolbarClassName,
  getWorkbenchResultToolbarGroupClassName,
  getWorkbenchSecondaryGridClassName,
} from '@/lib/workbenchControls'
import ReactMarkdown from 'react-markdown'
import DataGrid from '@/components/ui/DataGrid'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'

// ─────────────────────────────────────────────────────────────────────────────
// 类型与常量定义
// ─────────────────────────────────────────────────────────────────────────────

type GenStrategy = 'happy' | 'full' | 'negative' | 'smoke'
type GenLevel = 'integration' | 'system' | 'regression'
type GenStatus = 'idle' | 'context' | 'associating' | 'decomposing' | 'matching' | 'generating' | 'evaluating' | 'done' | 'error'
type GenTab = 'markdown' | 'grid' | 'log' | 'history'

const STRATEGIES: { id: GenStrategy; label: string; desc: string }[] = [
  { id: 'happy', label: '核心路径', desc: '主流程' },
  { id: 'full', label: '全量覆盖', desc: '全分支' },
  { id: 'negative', label: '异常攻防', desc: '边界异常' },
  { id: 'smoke', label: '快速冒烟', desc: '快速验证' },
]
const TEST_CASE_HEADER_COPY = buildWorkbenchHeaderCopy({ module: 'test-case' })
const TEST_CASE_PROGRESS_LABELS = buildProgressStepLabelMap('test-case')

const STATUS_STEPS: { status: GenStatus; label: string }[] = [
  { status: 'context', label: TEST_CASE_PROGRESS_LABELS.context },
  { status: 'associating', label: TEST_CASE_PROGRESS_LABELS.associating },
  { status: 'decomposing', label: TEST_CASE_PROGRESS_LABELS.decomposing },
  { status: 'matching', label: TEST_CASE_PROGRESS_LABELS.matching },
  { status: 'generating', label: TEST_CASE_PROGRESS_LABELS.generating },
  { status: 'evaluating', label: TEST_CASE_PROGRESS_LABELS.evaluating },
  { status: 'done', label: TEST_CASE_PROGRESS_LABELS.done },
]

const LEVELS: { id: GenLevel; label: string }[] = [
  { id: 'integration', label: '集成测试' },
  { id: 'system', label: '系统测试' },
  { id: 'regression', label: '回归测试' },
]

const TEST_CASE_SESSION_KEY = 'test-case'

// ─────────────────────────────────────────────────────────────────────────────
// 子组件
// ─────────────────────────────────────────────────────────────────────────────

function ProgressTimeline({ currentStatus }: { currentStatus: GenStatus }) {
  const currentIndex = STATUS_STEPS.findIndex(s => s.status === currentStatus)
  return (
    <div className="space-y-3 py-4">
      {STATUS_STEPS.map((step, i) => {
        const isDone = i < currentIndex || currentStatus === 'done'
        const isActive = i === currentIndex && currentStatus !== 'done'
        return (
          <div key={step.status} className="flex items-center gap-3">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
              isDone ? 'bg-emerald-500/20 border border-emerald-500/40' :
              isActive ? 'border animate-pulse bg-[var(--surface-accent)] border-[color:var(--accent-primary-soft)]' : 'bg-[var(--bg-soft)] border border-[color:var(--border)]'
            }`}>
              {isDone ? <span className="text-emerald-400" style={{ fontSize: '10px' }}>✓</span> :
               isActive ? <div className="w-2 h-2 rounded-full bg-[var(--accent-primary)] animate-pulse" /> :
               <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: 'var(--border)' }} />}
            </div>
            <span className={`transition-colors text-xs ${isDone ? 'text-emerald-500' : isActive ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
              {step.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 主组件
// ─────────────────────────────────────────────────────────────────────────────

export default function TestCasePage() {
  const {
    openInsight,
    reviewFindings,
    requirementContextId,
    moduleSessions,
    setModuleSession,
    appendModuleSessionEvent,
    setActiveNav,
    captureTaskSnapshot,
  } = useAppStore()
  const appearance = useAppStore((s) => s.appearance)
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)
  const { generate } = useTestGenerator()

  const session = moduleSessions[TEST_CASE_SESSION_KEY] || {}
  const sessionOptions = (session.options || {}) as Record<string, unknown>

  // ── 输入与配置状态 ────────────────────────────────────
  const requirement = typeof session.requirement === 'string' ? session.requirement : ''
  const [files, setFiles] = useState<File[]>([])
  const [tapdInput, setTapdInput] = useState('')
  const [tapdLoading, setTapdLoading] = useState(false)
  const [inputMode, setInputMode] = useState<TaskInputMode>(() =>
    resolveTaskInputMode({
      requirement,
      filesCount: 0,
      tapdInput: '',
    })
  )
  const strategy = (sessionOptions.strategy as GenStrategy) || 'happy'
  const level = (sessionOptions.level as GenLevel) || 'system'
  const useRiskLinks = typeof sessionOptions.useRiskLinks === 'boolean' ? sessionOptions.useRiskLinks : true

  // ── 运行状态 ──────────────────────────────────────────
  const runStatus = (session.runStatus as GenStatus) || 'idle'
  const activeTab = (session.activeTab as GenTab) || 'grid'
  const error = typeof session.error === 'string' ? session.error : null
  const eventLogs = (session.eventLogs as RunProgressEvent[]) || []
  const result = typeof session.result === 'string' ? session.result : null
  const persistedDownloadBaseName = typeof session.downloadBaseName === 'string' ? session.downloadBaseName : null

  const activeFiles = inputMode === 'upload' ? files : []
  const inputSourceLabel = inputMode === 'text'
    ? (requirement ? '手动录入' : requirementContextId ? '复用最近评审上下文' : '等待输入')
    : inputMode === 'upload'
      ? (files.length > 0 ? '上传文档' : '等待上传')
      : tapdInput
        ? 'TAPD 拉取中'
        : '等待输入'

  const patchOptions = (patch: Partial<Record<'strategy' | 'level' | 'useRiskLinks', unknown>>) => {
    setModuleSession(TEST_CASE_SESSION_KEY, {
      options: {
        ...sessionOptions,
        ...patch,
      },
    })
  }

  // ── 执行生成 ──────────────────────────────────────────
  const handleRun = async () => {
    if (!requirement && activeFiles.length === 0 && !requirementContextId) {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: '请提供需求描述、上传文档，或复用最近一次评审上下文',
      })
      return
    }
    const nextDownloadBaseName = resolveTestCaseExportBaseName({
      uploadedFilename: activeFiles[0]?.name || null,
      requirement,
      sharedRequirement: taskSummary.requirement,
    })
    setModuleSession(TEST_CASE_SESSION_KEY, {
      runStatus: 'context',
      error: null,
      activeTab: 'grid',
      downloadBaseName: nextDownloadBaseName,
      eventLogs: [],
      result: null,
    })

    try {
      const response = await generate(requirement, activeFiles, {
        strategy,
        level,
        useRiskLinks
      }, (event: RunStreamEvent) => {
        if (event.type === 'progress') {
          setModuleSession(TEST_CASE_SESSION_KEY, {
            runStatus: event.stage as GenStatus,
          })
          appendModuleSessionEvent(TEST_CASE_SESSION_KEY, event)
        }
      })
      if (response.success && response.result) {
        setModuleSession(TEST_CASE_SESSION_KEY, {
          runStatus: 'done',
          result: response.result,
          error: null,
        })
        captureTaskSnapshot()
        openInsight('测试用例已根据指定策略生成完毕。')
      } else {
        setModuleSession(TEST_CASE_SESSION_KEY, {
          runStatus: 'error',
          error: response.error || buildInlineErrorCopy('generate'),
        })
      }
    } catch (err: unknown) {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('generate'),
      })
    }
  }

  // ── 解析并生成 Grid / Markdown 数据 ─────────────────────
  const { gridData, displayMarkdown } = useMemo(() => {
    if (!result) return { gridData: [], displayMarkdown: '' }
    try {
      const parsed = JSON.parse(result) as TestCaseSuite
      if (parsed && (Array.isArray(parsed.items) || Array.isArray(parsed.modules))) {
        const items = sortTestCasesByPriority(getTestCaseItems(parsed))
        const md = getTestCaseMarkdown({
          ...parsed,
          items,
        })
        return { gridData: items, displayMarkdown: md };
      }
    } catch {}
    return { gridData: [], displayMarkdown: result };
  }, [result])

  const columns = useMemo(() => {
    if (gridData.length === 0) return []
      const keyMap: Record<string, string> = {
      'priority': '用例等级',
      'module': '模块',
      'title': '用例标题',
      'precondition': '前置条件',
      'tags': '标签',
      'remark': '备注',
      'steps': '操作流程与预期结果'
    }
    return getVisibleTestCaseColumns(gridData as TestCaseSuite['items']).map(key => ({
      accessorKey: key,
      header: keyMap[key] || key,
      cell: ({ getValue }: { getValue: () => unknown }) => {
        const val = getValue();
        if (Array.isArray(val)) {
          return (
            <div className="space-y-2 py-1">
              <div className="text-[11px] font-semibold text-[var(--text-strong)]">步骤描述</div>
              {val.map((s: unknown, i: number) => {
                if (!s || typeof s !== 'object') {
                  return null
                }
                const step = s as TestCaseStep
                return (
                  <div key={i} className="ml-3 pl-3" style={{ borderLeft: '1px solid var(--border)' }}>
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      <span className="mr-1 text-[var(--accent-primary)]">{i + 1}.</span>
                      {step.action}
                    </div>
                    <div className="mt-1 ml-4 text-[11px]" style={{ color: 'var(--text-primary)', opacity: 0.8 }}>
                      预期结果：{step.expected}
                    </div>
                  </div>
                )
              })}
            </div>
          )
        }
        return <span className="text-xs">{String(val ?? '')}</span>
      },
      size: key === 'steps' || key === 'title' ? 350 : 100
    }))
  }, [gridData])

  const isRunning = !['idle', 'done', 'error'].includes(runStatus)
  const taskSummary = useMemo(
    () =>
      buildTaskWorkbenchSummary({
        moduleSessions,
        reviewFindings,
        requirementContextId,
      }),
    [moduleSessions, requirementContextId, reviewFindings]
  )
  const canNavigateWithCurrentTask = Boolean(requirement || taskSummary.requirement || requirementContextId)
  const strategyLabel = STRATEGIES.find((item) => item.id === strategy)?.label || strategy
  const levelLabel = LEVELS.find((item) => item.id === level)?.label || level
  const runPresentation = resolveWorkbenchRunPresentation({
    status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
    idleStageLabel: '测试设计',
    doneStageLabel: '用例已生成',
    idleActionLabel: '生成',
    runningActionLabel: '生成中',
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const resultEmptyCopy = buildResultEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()
  const testCaseWorkbenchCopy = buildTestCaseWorkbenchCopy({
    hasResult: Boolean(result),
    hasContext: Boolean(requirementContextId),
  })

  const jumpToModule = (navId: 'review' | 'flowchart') => {
    const sourceRequirement = requirement || taskSummary.requirement
    const targetSessionKey = navId === 'review' ? 'review' : 'flowchart'
    const targetTab = navId === 'review' ? 'report' : 'diagram'
    const patch = buildSeededSessionPatch(sourceRequirement, targetTab)

    if (Object.keys(patch).length > 0) {
      setModuleSession(targetSessionKey, patch)
    }
    setActiveNav(navId)
  }

  const jumpToCaseReview = () => {
    if (!result) {
      return
    }

    const sourceRequirement = requirement || taskSummary.requirement
    setModuleSession(
      'test-case-review',
      buildTestCaseReviewSessionFromTestCase({
        requirement: sourceRequirement,
        result,
      })
    )
    setActiveNav('test-case-review')
  }

  const buildExportBaseName = (): string => {
    return resolveTestCaseExportBaseName({
      persistedBaseName: persistedDownloadBaseName,
      uploadedFilename: activeFiles[0]?.name || null,
      requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: (gridData[0] as TestCaseSuite['items'][number] | undefined)?.module || null,
    })
  }

  const triggerFileDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const handleStructuredExport = async (format: 'excel' | 'xmind') => {
    if (!result) {
      return
    }

    try {
      const exported = await apiClient.exportTestCases(result, format, buildExportBaseName())
      triggerFileDownload(exported.blob, exported.filename)
      openInsight(format === 'excel' ? '已导出 TAPD 导入格式 Excel。' : '已导出 XMind 测试用例。')
    } catch (err: unknown) {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: err instanceof Error ? err.message : buildInlineErrorCopy('export'),
      })
    }
  }

  const handleImportTapdRequirement = async () => {
    const tapdCandidate = tapdInput.trim() || requirement.trim()
    const parsed = parseTapdInput(tapdCandidate)

    if (parsed.kind === 'empty') {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: '请输入 TAPD 需求 ID 或链接',
      })
      return
    }

    if (parsed.kind === 'wecom-doc-link') {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: '已识别为腾讯文档链接。读取 TAPD 仅支持 TAPD Story 链接；请将文档正文粘贴到上方，或下载为 Docx/PDF 后上传。',
      })
      return
    }

    if (parsed.kind === 'unsupported-link') {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: '已识别为链接，但不是 TAPD Story 链接。请输入 TAPD Story ID 或 tapd.cn 需求链接。',
      })
      return
    }

    if (!parsed.storyId) {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: '未识别到有效 TAPD Story ID，请检查输入。',
      })
      return
    }

    setTapdLoading(true)
    try {
      const payload = await apiClient.getTapdStory(parsed.storyId)
      setModuleSession(TEST_CASE_SESSION_KEY, {
        requirement: payload.content,
        error: null,
      })
      setInputMode('text')
      openInsight(`已识别并读取 TAPD 需求 ${payload.story_id}，可以继续生成测试用例。`)
    } catch (err: unknown) {
      setModuleSession(TEST_CASE_SESSION_KEY, {
        error: err instanceof Error ? err.message : buildInlineErrorCopy('tapd'),
      })
    } finally {
      setTapdLoading(false)
    }
  }

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '生成状态',
      entries: [
        {
          id: 'run-status',
          label: '当前阶段',
          value: buildRunStateValue({
            status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '等待开始生成',
            runningLabel: STATUS_STEPS.find((step) => step.status === runStatus)?.label || '生成中',
            doneLabel: TEST_CASE_PROGRESS_LABELS.done,
          }),
          status: runStatus === 'done' ? 'done' as const : isRunning ? 'running' as const : error ? 'warning' as const : 'idle' as const,
        },
        {
          id: 'strategy',
          label: '生成策略',
          value: STRATEGIES.find((item) => item.id === strategy)?.label || strategy,
          status: 'idle' as const,
        },
        {
          id: 'coverage',
          label: '结果规模',
          value: result ? `${gridData.length || 1} 条输出` : '尚未生成',
          status: result ? 'done' as const : 'idle' as const,
        },
      ],
    },
    {
      id: 'signals',
      title: '上下文信号',
      entries: [
        {
          id: 'review-risk',
          label: '评审发现',
          value: `${reviewFindings.length} 项`,
          status: reviewFindings.length > 0 ? 'warning' as const : 'idle' as const,
        },
        {
          id: 'source-input',
          label: '需求来源',
          value: inputSourceLabel,
          status: requirement || requirementContextId || activeFiles.length > 0 ? 'done' as const : 'idle' as const,
        },
        {
          id: 'risk-links',
          label: '风险反哺',
          value: useRiskLinks ? '已启用' : '未启用',
          status: useRiskLinks ? 'running' as const : 'idle' as const,
        },
      ],
    },
    {
      id: 'activity',
      title: '下一步建议',
      entries: [
        {
          id: 'review',
          label: '看评审',
          value: '检查覆盖',
          status: reviewFindings.length > 0 ? 'done' as const : 'idle' as const,
          onClick: () => jumpToModule('review'),
        },
        {
          id: 'flowchart',
          label: '去流程图',
          value: '补流程',
          status: result ? 'running' as const : 'idle' as const,
          onClick: () => jumpToModule('flowchart'),
        },
        {
          id: 'history',
          label: '看历史',
          value: '打开历史',
          status: result ? 'done' as const : 'idle' as const,
          onClick: () => setModuleSession(TEST_CASE_SESSION_KEY, { activeTab: 'history' }),
        },
      ],
    },
  ]

  return (
    <div className="animate-fade-in pb-20">
      <div className={getWorkbenchStackClassName()}>
        <div className="space-y-4">
          <section className="console-panel p-5">
            <div className="mb-5 flex items-start justify-between gap-4 border-b pb-4" style={{ borderColor: 'var(--border-soft)' }}>
              <div className="min-w-0">
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <ListChecks className="h-[18px] w-[18px]" />
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{TEST_CASE_HEADER_COPY.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-lg font-semibold text-[var(--text-primary)] lg:text-xl">{TEST_CASE_HEADER_COPY.title}</h1>
                      {testCaseWorkbenchCopy.tags.map((tag) => (
                        <span
                          key={tag}
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                            tag === '已生成'
                              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600'
                              : tag === '已联动'
                                ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                                : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                          }`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                      {testCaseWorkbenchCopy.description}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveNav('dashboard')}
                  className="rounded-xl border border-[color:var(--border-soft)] bg-transparent px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]"
                >
                  回工作台
                </button>
                <button
                  type="button"
                  onClick={() => jumpToModule('review')}
                  disabled={!canNavigateWithCurrentTask}
                  title={canNavigateWithCurrentTask ? '回到当前任务的评审阶段' : '请先录入需求'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    canNavigateWithCurrentTask
                      ? 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)] hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                >
                  看评审
                </button>
                <button
                  type="button"
                  onClick={() => jumpToModule('flowchart')}
                  disabled={!canNavigateWithCurrentTask}
                  title={canNavigateWithCurrentTask ? '继续补齐流程视图' : '请先录入需求'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    canNavigateWithCurrentTask
                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                  >
                  去流程图
                </button>
                <button
                  type="button"
                  onClick={jumpToCaseReview}
                  disabled={!result || !canNavigateWithCurrentTask}
                  title={result && canNavigateWithCurrentTask ? '带着当前生成结果进入测试用例评审' : '请先生成测试用例并确保当前任务存在需求上下文'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    result && canNavigateWithCurrentTask
                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                >
                  去用例评审
                </button>
              </div>
            </div>

            <div className="mb-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="console-kicker">生成输入</div>
                  <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                    {inputMode === 'text' ? '粘贴需求' : inputMode === 'upload' ? '上传文档' : '读取 TAPD'}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="console-chip">{strategyLabel}</span>
                  <span className="console-chip">{levelLabel}</span>
                </div>
              </div>
            </div>

            <div className={getWorkbenchSecondaryGridClassName()}>
              <div className="min-w-0">
                <div className={getWorkbenchModeSwitchClassName()}>
                  {([
                    { id: 'text', label: '粘贴需求' },
                    { id: 'upload', label: '上传文档' },
                    { id: 'tapd', label: '读取 TAPD' },
                  ] as { id: TaskInputMode; label: string }[]).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setInputMode(item.id)}
                      className={getWorkbenchModeButtonClassName(inputMode === item.id)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>

                {inputMode === 'text' && (
                  <textarea
                    value={requirement}
                    onChange={(e) => {
                      setInputMode('text')
                      setModuleSession(TEST_CASE_SESSION_KEY, { requirement: e.target.value })
                    }}
                    placeholder="粘贴 PRD、用户故事或变更点"
                    className="mt-4 h-44 w-full resize-none rounded-2xl border p-4 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                )}

                {inputMode === 'upload' && (
                  <>
                    <FileUploadTrigger
                      ariaLabel="上传附件"
                      className="mt-4 rounded-2xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
                      primaryText={files.length > 0 ? `已选 ${files.length} 个附件` : '上传附件'}
                      onFilesChange={(nextFiles) => {
                        setInputMode('upload')
                        setFiles(nextFiles)
                      }}
                    />
                  </>
                )}

                {inputMode === 'tapd' && (
                  <div className="mt-4 rounded-2xl border px-3 py-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">TAPD 拉取</div>
                    <div className="flex gap-2">
                      <input
                        value={tapdInput}
                        onChange={(event) => {
                          setInputMode('tapd')
                          setTapdInput(event.target.value)
                        }}
                        placeholder="输入 TAPD ID 或链接"
                        className="flex-1 rounded-xl border px-3 py-2 text-xs outline-none transition-colors"
                        style={{ borderColor: 'var(--border)' }}
                      />
                      <button
                        type="button"
                        onClick={handleImportTapdRequirement}
                        disabled={tapdLoading}
                        className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                          tapdLoading
                            ? 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                            : 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                        }`}
                      >
                        {tapdLoading ? '读取中...' : '读取'}
                      </button>
                    </div>
                  </div>
                )}

                {requirementContextId && activeFiles.length === 0 && !requirement && (
                  <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                    <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                      最近上下文
                    </span>
                    <span>{testCaseWorkbenchCopy.contextHint}</span>
                  </div>
                )}
              </div>

              <div className="console-inset p-3.5">
                <div className="mb-3">
                  <div className="console-kicker">生成设置</div>
                  <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">覆盖策略与风险接入</div>
                </div>

                <div
                  className="rounded-2xl border px-3 py-3"
                  style={{
                    borderColor: useRiskLinks ? 'var(--accent-primary-soft)' : 'var(--border-soft)',
                    backgroundColor: useRiskLinks ? 'var(--surface-accent)' : 'var(--surface-panel-muted)',
                  }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
                        <Sparkles className="h-4 w-4 text-[var(--accent-primary)]" />
                        风险反哺
                      </div>
                      <div className="mt-1 text-[11px] text-[var(--text-secondary)]">
                        {reviewFindings.length > 0 ? `已接入 ${reviewFindings.length} 项评审发现` : '当前没有可接入的评审风险'}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => patchOptions({ useRiskLinks: !useRiskLinks })}
                      className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                        useRiskLinks
                          ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                          : 'border-[color:var(--border)] bg-[var(--surface-inset)] text-[var(--text-secondary)]'
                      }`}
                    >
                      {useRiskLinks ? '已启用' : '未启用'}
                    </button>
                  </div>
                </div>

                <div className="mt-4">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">策略</div>
                  <div className="flex flex-wrap gap-2">
                    {STRATEGIES.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => patchOptions({ strategy: item.id })}
                        className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                          strategy === item.id
                            ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                            : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)] hover:border-[color:var(--border-hover)]'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-4">
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">层级</div>
                  <div className="flex flex-wrap gap-2">
                    {LEVELS.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => patchOptions({ level: item.id })}
                        className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                          level === item.id
                            ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                            : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)] hover:border-[color:var(--border-hover)]'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div
              className={getWorkbenchPrimaryActionStripClassName()}
              style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
            >
              <div className="min-w-0">
                <div className="text-sm font-semibold text-[var(--text-primary)]">开始生成</div>
                <div className="mt-1 text-[11px] text-[var(--text-secondary)]">
                  {strategyLabel} · {levelLabel}
                </div>
              </div>
              <button
                type="button"
                onClick={handleRun}
                disabled={isRunning}
                className={`shrink-0 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors ${
                  isRunning
                    ? 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                    : 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  {isRunning ? <div className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" /> : <Play className="h-4 w-4" />}
                  {runPresentation.primaryActionLabel}
                </span>
              </button>
            </div>
          </section>

          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-xs text-red-500">
              {error}
            </div>
          )}
        </div>

        <section className="space-y-2">
          <div className="min-w-0">
            <div className={getWorkbenchResultPanelClassName()}>
              <div className={getWorkbenchResultToolbarClassName()} style={{ borderColor: 'var(--border-soft)' }}>
                <div className={getWorkbenchResultToolbarGroupClassName()}>
                  {[
                    { id: 'grid', label: '用例' },
                    { id: 'markdown', label: 'MD' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setModuleSession(TEST_CASE_SESSION_KEY, { activeTab: tab.id as GenTab })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className={getWorkbenchResultToolbarGroupClassName('end')}>
                  {[
                    { id: 'log', label: '执行' },
                    { id: 'history', label: '历史' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setModuleSession(TEST_CASE_SESSION_KEY, { activeTab: tab.id as GenTab })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}

                  {runStatus === 'done' && (
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      <button
                        type="button"
                        onClick={() => downloadMarkdownFile(displayMarkdown, buildMarkdownDownloadFilename(buildExportBaseName(), '测试用例'))}
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        MD
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleStructuredExport('excel')}
                        title="导出 TAPD Excel"
                        className={getWorkbenchResultActionClassName('accent')}
                      >
                        TAPD
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleStructuredExport('xmind')}
                        title="导出 XMind"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        XMind
                      </button>
                      <button
                        type="button"
                        onClick={jumpToCaseReview}
                        title="带当前结果去做测试用例评审"
                        className={getWorkbenchResultActionClassName('accent')}
                      >
                        送审
                      </button>
                    </div>
                  )}
                </div>
              </div>

            <div className="relative flex-1 overflow-hidden p-5">
              {activeTab === 'history' ? (
                <HistoryReportPanel
                  types={['test_case']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                />
              ) : runStatus === 'idle' ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <GitBranch className="h-7 w-7" />
                  </div>
                  <p className="mt-6 text-xl font-semibold text-[var(--text-primary)]">{resultEmptyCopy.title}</p>
                  <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{resultEmptyCopy.description}</p>
                </div>
              ) : isRunning ? (
                <div className="flex h-full flex-col items-center justify-center py-10">
                  <div className="w-full max-w-2xl space-y-6">
                    <p className="text-center text-xl font-semibold tracking-tight text-[var(--text-primary)]">正在生成用例...</p>
                    <ProgressTimeline currentStatus={runStatus} />
                    <div className="console-panel-muted p-4">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                      <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                    </div>
                  </div>
                </div>
              ) : runStatus === 'done' ? (
                <div className="flex h-full flex-col animate-fade-in">
                  <ResultStageBanner
                    title="测试用例已生成"
                    meta={`${gridData.length} 条用例 · ${strategyLabel}`}
                  />
                  {activeTab === 'grid' && (
                    <div className="flex-1 overflow-hidden rounded-xl border" style={{ borderColor: 'var(--border-soft)' }}>
                      <DataGrid data={gridData} columns={columns} />
                    </div>
                  )}
                  {activeTab === 'markdown' && (
                    <div className={`custom-scrollbar prose prose-sm max-w-none flex-1 overflow-y-auto pr-2 ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                      <ReactMarkdown>{displayMarkdown}</ReactMarkdown>
                    </div>
                  )}
                  {activeTab === 'log' && (
                    <div className="space-y-6 py-4">
                      <ProgressTimeline currentStatus={runStatus} />
                      <div className="console-panel-muted p-4">
                        <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                        <ExecutionEventLog events={eventLogs} />
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>
          </div>
        </section>

        <div className={getWorkbenchRailWrapperClassName(collaborationRailCollapsed)}>
          <CollaborationRail
            title="测试设计"
            subtitle=""
            tags={[
              { label: '测试设计', tone: 'accent' },
              { label: result ? '已有结果' : '待生成', tone: result ? 'success' : 'neutral' },
              { label: `${reviewFindings.length} 个风险`, tone: reviewFindings.length > 0 ? 'warning' : 'neutral' },
            ]}
            sections={compactRailSections(collaborationSections)}
            actions={[
              {
                label: runPresentation.railActionLabel,
                onClick: () => {
                  if (!isRunning) {
                    void handleRun()
                  }
                },
                tone: 'accent',
              },
              { label: '去用例评审', onClick: jumpToCaseReview },
              { label: '去流程图', onClick: () => jumpToModule('flowchart') },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

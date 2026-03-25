'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronDown,
  ChevronUp,
  Clipboard,
  Download,
  FileSearch,
  GitBranch,
  SlidersHorizontal,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import { apiClient, RunProgressEvent, RunStreamEvent } from '@/lib/api'
import { type ReviewFinding, type ReviewRunPayload } from '@/lib/contracts'
import { downloadMarkdownFile } from '@/lib/markdownFile'
import { parseStoredModulePayload, resolveModuleSession, serializeModuleSessionResult } from '@/lib/moduleSession'
import { buildReviewFindingDetails, buildReviewMarkdown } from '@/lib/reviewResult'
import {
  buildReviewRoleSelectionSummary,
  clearReviewRoleSelection,
  getDefaultReviewRoleIds,
  resetReviewRoleSelection,
  validateReviewRoleSelection,
  type ReviewRoleOption,
} from '@/lib/reviewRoleSelect'
import { buildMarkdownDownloadFilename, resolvePreferredDownloadBaseName } from '@/lib/testCaseExportName'
import { parseTapdInput } from '@/lib/tapdInput'
import { buildSeededSessionPatch, buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import {
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildProgressStepLabelMap,
  buildResultFormatErrorCopy,
  buildReviewWorkbenchCopy,
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
  getWorkbenchFindingBadgeClassName,
  getWorkbenchFindingCardClassName,
  getWorkbenchFindingsListClassName,
  getWorkbenchInputFooterClassName,
  getWorkbenchModeButtonClassName,
  getWorkbenchModeSwitchClassName,
  getWorkbenchRailToneClassName,
  getWorkbenchResultActionGroupClassName,
  getWorkbenchResultActionClassName,
  getWorkbenchResultTabClassName,
  getWorkbenchResultToolbarClassName,
  getWorkbenchResultToolbarGroupClassName,
  getWorkbenchSettingsDrawerClassName,
  getWorkbenchSuggestionPanelClassName,
} from '@/lib/workbenchControls'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/stores/useAppStore'

type ReviewDepth = 'quick' | 'standard' | 'deep'
type ReviewStatus = 'idle' | 'reading' | 'analyzing' | 'grouping' | 'conflicting' | 'grading' | 'done' | 'error'
type ReviewTab = 'report' | 'findings' | 'log' | 'history'

const ROLES: ReviewRoleOption[] = [
  { id: 'test', label: '资深测试工程师' },
  { id: 'product', label: '产品经理' },
  { id: 'tech', label: '技术负责人' },
  { id: 'design', label: '设计视角' },
  { id: 'security', label: '安全专家' },
  { id: 'architect', label: '资深架构师（仲裁）' },
]

const DEPTHS: { id: ReviewDepth; label: string; desc: string }[] = [
  { id: 'quick', label: '快速扫一眼', desc: '核心问题' },
  { id: 'standard', label: '标准评审', desc: '常规深挖' },
  { id: 'deep', label: '全力压测', desc: '极端攻防' },
]
const REVIEW_HEADER_COPY = buildWorkbenchHeaderCopy({ module: 'review' })
const REVIEW_PROGRESS_LABELS = buildProgressStepLabelMap('review')

const STATUS_STEPS: { status: ReviewStatus; label: string }[] = [
  { status: 'reading', label: REVIEW_PROGRESS_LABELS.reading },
  { status: 'analyzing', label: REVIEW_PROGRESS_LABELS.analyzing },
  { status: 'grouping', label: REVIEW_PROGRESS_LABELS.grouping },
  { status: 'conflicting', label: REVIEW_PROGRESS_LABELS.conflicting },
  { status: 'grading', label: REVIEW_PROGRESS_LABELS.grading },
  { status: 'done', label: REVIEW_PROGRESS_LABELS.done },
]

const REVIEW_SESSION_KEY = 'review'

function ProgressTimeline({ currentStatus }: { currentStatus: ReviewStatus }) {
  const currentIndex = STATUS_STEPS.findIndex((step) => step.status === currentStatus)

  return (
    <div className="space-y-3 py-2">
      {STATUS_STEPS.map((step, index) => {
        const isDone = index < currentIndex || currentStatus === 'done'
        const isActive = index === currentIndex && currentStatus !== 'done'

        return (
          <div key={step.status} className="flex items-center gap-3">
            <div
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-all ${
                isDone
                  ? 'border border-emerald-500/40 bg-emerald-500/20'
                  : isActive
                    ? 'border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] animate-pulse'
                    : 'border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)]'
              }`}
            >
              {isDone ? (
                <span className="text-[10px] text-emerald-500">✓</span>
              ) : isActive ? (
                <div className="h-2 w-2 rounded-full bg-[var(--accent-primary)] animate-pulse" />
              ) : (
                <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: 'var(--border)' }} />
              )}
            </div>
            <span className={`text-sm ${isDone ? 'text-emerald-500' : isActive ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
              {step.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function FindingCard({ finding }: { finding: ReviewFinding }) {
  const tone = finding.risk_level === 'H' ? 'high' : finding.risk_level === 'M' ? 'medium' : 'low'
  const riskLabel = tone === 'high' ? '高风险' : tone === 'medium' ? '中风险' : '低风险'
  const details = buildReviewFindingDetails(finding)

  return (
    <article className={getWorkbenchFindingCardClassName(tone)}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className={getWorkbenchFindingBadgeClassName(tone)}>
          {riskLabel}
        </span>
        <span className="text-xs font-medium text-[var(--text-secondary)]">{finding.category}</span>
      </div>
      <div className="text-[15px] font-semibold leading-6 text-[var(--text-primary)]">{finding.description}</div>
      {details.map((detail) => (
        <div
          key={detail.key}
          className={
            detail.key === 'source_quote'
              ? 'mt-2.5 rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-3.5 py-2.5'
              : getWorkbenchSuggestionPanelClassName()
          }
        >
          <div
            className={
              detail.key === 'source_quote'
                ? 'mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]'
                : 'mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--accent-blue)]'
            }
          >
            {detail.label}
          </div>
          <div
            className={
              detail.key === 'source_quote'
                ? 'text-sm leading-6 text-[var(--text-primary)]'
                : 'text-sm leading-6 text-[var(--text-secondary)]'
            }
          >
            {detail.content}
          </div>
        </div>
      ))}
    </article>
  )
}

export default function ReviewPage() {
  const {
    openInsight,
    setReviewFindings,
    setRequirementContextId,
    requirementContextId,
    reviewFindings,
    moduleSessions,
    setModuleSession,
    appendModuleSessionEvent,
    setActiveNav,
    captureTaskSnapshot,
    appearance,
  } = useAppStore()
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)

  const session = resolveModuleSession(moduleSessions[REVIEW_SESSION_KEY], {
    runStatus: 'idle',
    activeTab: 'report',
    options: {
      depth: 'standard',
      selectedRoles: getDefaultReviewRoleIds(),
    },
  })
  const sessionOptions = session.options as {
    depth?: ReviewDepth
    selectedRoles?: string[]
  }

  const requirement = session.requirement
  const [files, setFiles] = useState<File[]>([])
  const [tapdInput, setTapdInput] = useState('')
  const [tapdLoading, setTapdLoading] = useState(false)
  const [settingsExpanded, setSettingsExpanded] = useState(false)
  const [roleMenuOpen, setRoleMenuOpen] = useState(false)
  const [inputMode, setInputMode] = useState<TaskInputMode>(() =>
    resolveTaskInputMode({
      requirement,
      filesCount: 0,
      tapdInput: '',
    })
  )
  const depth = sessionOptions.depth || 'standard'
  const selectedRoles = Array.isArray(sessionOptions.selectedRoles) ? sessionOptions.selectedRoles : getDefaultReviewRoleIds()

  const runStatus = session.runStatus as ReviewStatus
  const resultRaw = session.result
  const result = useMemo(() => {
    if (!resultRaw) {
      return null
    }
    return parseStoredModulePayload<ReviewRunPayload>(resultRaw, {
      reports: {
        general: {
          label: '评审报告',
          content: resultRaw,
        },
      },
      findings: [],
    })
  }, [resultRaw])
  const error = session.error
  const activeTab = session.activeTab as ReviewTab
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const resultSectionRef = useRef<HTMLElement>(null)
  const roleMenuRef = useRef<HTMLDivElement>(null)
  const persistedDownloadBaseName = session.downloadBaseName
  const activeRequirement =
    inputMode === 'upload'
      ? ''
      : inputMode === 'tapd'
        ? tapdInput.trim()
          ? requirement
          : ''
        : requirement
  const activeFiles = inputMode === 'upload' ? files : []
  const inputSourceLabel =
    inputMode === 'upload'
      ? files.length > 0
        ? '上传文档'
        : '等待上传'
      : inputMode === 'tapd'
        ? tapdInput.trim()
          ? requirement
            ? 'TAPD 需求'
            : 'TAPD 输入'
          : '等待输入'
      : requirement
        ? '文本录入'
        : '等待输入'

  const scrollToResultSection = () => {
    if (typeof window === 'undefined') {
      return
    }

    window.requestAnimationFrame(() => {
      resultSectionRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    })
  }

  const buildExportBaseName = (): string =>
    resolvePreferredDownloadBaseName({
      persistedBaseName: persistedDownloadBaseName,
      uploadedFilename: activeFiles[0]?.name || null,
      requirement: activeRequirement || requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: '需求评审',
    })

  useEffect(() => {
    if (!settingsExpanded) {
      setRoleMenuOpen(false)
    }
  }, [settingsExpanded])

  useEffect(() => {
    if (!roleMenuOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!(event.target instanceof Node)) {
        return
      }
      if (!roleMenuRef.current?.contains(event.target)) {
        setRoleMenuOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setRoleMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [roleMenuOpen])

  const updateSelectedRoles = (nextRoles: string[]) => {
    setModuleSession(REVIEW_SESSION_KEY, {
      error: null,
      options: {
        ...sessionOptions,
        selectedRoles: nextRoles,
      },
    })
  }

  const handleRun = async () => {
    if (!activeRequirement && activeFiles.length === 0) {
      setModuleSession(REVIEW_SESSION_KEY, {
        error: '请提供需求描述或上传文档',
      })
      return
    }
    const roleValidationError = validateReviewRoleSelection(selectedRoles)
    if (roleValidationError) {
      setSettingsExpanded(true)
      setRoleMenuOpen(true)
      setModuleSession(REVIEW_SESSION_KEY, {
        error: roleValidationError,
      })
      return
    }
    const nextDownloadBaseName = resolvePreferredDownloadBaseName({
      uploadedFilename: activeFiles[0]?.name || null,
      requirement: activeRequirement || requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: '需求评审',
    })
    setModuleSession(REVIEW_SESSION_KEY, {
      runStatus: 'reading',
      error: null,
      result: null,
      downloadBaseName: nextDownloadBaseName,
      activeTab: 'report',
      eventLogs: [],
    })
    setSettingsExpanded(false)
    scrollToResultSection()

    try {
      const res = await apiClient.runSkillStream(
        'review',
        activeRequirement,
        activeFiles,
        { depth },
        selectedRoles,
        undefined,
        undefined,
        undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(REVIEW_SESSION_KEY, {
              runStatus: event.stage as ReviewStatus,
            })
            appendModuleSessionEvent(REVIEW_SESSION_KEY, event)
          }
        }
      )

      if (res.success) {
        let parsedResult: ReviewRunPayload
        try {
          parsedResult = JSON.parse(res.result)
        } catch {
          parsedResult = { reports: { general: { label: '评审报告', content: res.result } }, findings: [] }
        }
        if (parsedResult.findings) {
          setReviewFindings(parsedResult.findings)
        }
        if (res.context_id) {
          setRequirementContextId(res.context_id)
        }
        setModuleSession(REVIEW_SESSION_KEY, {
          result: serializeModuleSessionResult(parsedResult),
          runStatus: 'done',
          error: null,
          activeTab: parsedResult.findings?.length ? 'findings' : 'report',
        })
        scrollToResultSection()
        captureTaskSnapshot()
        openInsight('需求评审已完成，核心风险已在风险看板汇总。')
      }
    } catch (err: unknown) {
      setModuleSession(REVIEW_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('process'),
      })
    }
  }

  const toggleRole = (id: string) => {
    const nextRoles = selectedRoles.includes(id)
      ? selectedRoles.filter((roleId) => roleId !== id)
      : [...selectedRoles, id]

    updateSelectedRoles(nextRoles)
  }

  const handleClearRoles = () => {
    updateSelectedRoles(clearReviewRoleSelection())
  }

  const handleResetRoles = () => {
    updateSelectedRoles(resetReviewRoleSelection())
  }

  const handleRecommend = async () => {
    if (!activeRequirement && activeFiles.length === 0) return
    const previousStatus = runStatus
    setModuleSession(REVIEW_SESSION_KEY, {
      runStatus: 'reading',
    })
    try {
      const res = await apiClient.recommendExperts(activeRequirement, activeFiles)
      if (res.success) {
        updateSelectedRoles(res.recommended)
        openInsight('已根据需求为您勾选建议角色。')
      }
    } finally {
      setModuleSession(REVIEW_SESSION_KEY, {
        runStatus: previousStatus,
      })
    }
  }

  const handleCopyMarkdown = async () => {
    if (!result) return
    const markdown = buildReviewMarkdown(result)
    await navigator.clipboard.writeText(markdown)
    openInsight('Markdown 报告已复制。')
  }

  const handleDownloadMarkdown = () => {
    if (!result) return
    downloadMarkdownFile(buildReviewMarkdown(result), buildMarkdownDownloadFilename(buildExportBaseName(), '需求评审报告'))
    openInsight('Markdown 报告已下载。')
  }

  const handleImportTapdRequirement = async () => {
    const tapdCandidate = tapdInput.trim()
    const parsed = parseTapdInput(tapdCandidate)

    if (parsed.kind === 'empty') {
      setModuleSession(REVIEW_SESSION_KEY, {
        error: '请输入 TAPD 需求 ID 或链接',
      })
      return
    }

    if (parsed.kind === 'wecom-doc-link') {
      setModuleSession(REVIEW_SESSION_KEY, {
        error: '已识别为腾讯文档链接。读取 TAPD 仅支持 TAPD Story 链接；请将文档正文粘贴到上方，或下载为 Docx/PDF 后上传。',
      })
      return
    }

    if (parsed.kind === 'unsupported-link') {
      setModuleSession(REVIEW_SESSION_KEY, {
        error: '已识别为链接，但不是 TAPD Story 链接。请输入 TAPD Story ID 或 tapd.cn 需求链接。',
      })
      return
    }

    if (!parsed.storyId) {
      setModuleSession(REVIEW_SESSION_KEY, {
        error: '未识别到有效 TAPD Story ID，请检查输入。',
      })
      return
    }

    setTapdLoading(true)
    try {
      const payload = await apiClient.getTapdStory(parsed.storyId)
      setModuleSession(REVIEW_SESSION_KEY, {
        requirement: payload.content,
        error: null,
      })
      openInsight(`已识别并读取 TAPD 需求 ${payload.story_id}，可以直接开始评审。`)
    } catch (err: unknown) {
      setModuleSession(REVIEW_SESSION_KEY, {
        error: err instanceof Error ? err.message : buildInlineErrorCopy('tapd'),
      })
    } finally {
      setTapdLoading(false)
    }
  }

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
  const canContinueWithCurrentTask = Boolean(requirement || taskSummary.requirement || requirementContextId)
  const selectedDepthLabel = DEPTHS.find((item) => item.id === depth)?.label || depth
  const runPresentation = resolveWorkbenchRunPresentation({
    status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
    idleStageLabel: '风险评审',
    doneStageLabel: '风险已收敛',
    idleActionLabel: '评审',
    runningActionLabel: '评审中',
  })

  const jumpToNextModule = (navId: 'test-cases' | 'req-analysis' | 'flowchart') => {
    const sourceRequirement = requirement || taskSummary.requirement
    const targetSessionKey =
      navId === 'test-cases' ? 'test-case' : navId === 'req-analysis' ? 'req-analysis' : 'flowchart'
    const targetTab = navId === 'test-cases' ? 'grid' : navId === 'req-analysis' ? 'structured' : 'diagram'

    const patch = buildSeededSessionPatch(sourceRequirement, targetTab)
    if (Object.keys(patch).length > 0) {
      setModuleSession(targetSessionKey, patch)
    }
    setActiveNav(navId)
  }

  const markdown = buildReviewMarkdown(result)
  const findings = result?.findings || []
  const hasHighRiskFinding = findings.some((item) => item.risk_level === 'H')
  const reviewRoleSummary = buildReviewRoleSelectionSummary(selectedRoles, ROLES)
  const roleCompactLabel = reviewRoleSummary.text
  const reviewCopy = buildReviewWorkbenchCopy({
    selectedRolesCount: selectedRoles.length,
    findingsCount: findings.length,
    hasResult: Boolean(result),
    hasContext: Boolean(requirementContextId),
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()
  const logFormatErrorCopy = buildResultFormatErrorCopy({ target: 'log' })
  const railTags =
    findings.length > 0
      ? [{ label: `${findings.length} 个风险`, tone: hasHighRiskFinding ? 'danger' as const : 'warning' as const }]
      : result
        ? [{ label: '评审完成', tone: 'success' as const }]
        : isRunning
          ? [{ label: '评审中', tone: 'accent' as const }]
          : [{ label: '待评审', tone: 'neutral' as const }]
  const railPrimaryAction = !isRunning
    ? result && canContinueWithCurrentTask
      ? {
          label: '去测试用例',
          onClick: () => jumpToNextModule('test-cases'),
          tone: 'accent' as const,
        }
      : {
          label: runPresentation.railActionLabel,
          onClick: () => {
            if (!isRunning) {
              void handleRun()
            }
          },
          tone: 'accent' as const,
        }
    : null
  const collaborationSections: RailSection[] = [
    {
      id: 'summary',
      title: '任务摘要',
      entries: [
        {
          id: 'stage',
          label: '阶段',
          value: buildRunStateValue({
            status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '待评审',
            runningLabel: STATUS_STEPS.find((step) => step.status === runStatus)?.label || '评审中',
            doneLabel: '已完成',
          }),
          status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'risk',
          label: '风险',
          value: findings.length > 0 ? `${findings.length} 项` : result ? '低风险' : '待生成',
          status: findings.length > 0 ? (hasHighRiskFinding ? 'warning' : 'done') : result ? 'done' : 'idle',
        },
        {
          id: 'context',
          label: '上下文',
          value: requirementContextId ? '已建立' : '待建立',
          status: requirementContextId ? 'done' : 'idle',
        },
        {
          id: 'source',
          label: '输入',
          value: inputSourceLabel,
          status: activeRequirement || activeFiles.length > 0 ? 'done' : 'idle',
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
                    <FileSearch className="h-[18px] w-[18px]" />
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{REVIEW_HEADER_COPY.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-lg font-semibold text-[var(--text-primary)] lg:text-xl">{REVIEW_HEADER_COPY.title}</h1>
                      {reviewCopy.tags.map((tag, index) => (
                        <span
                          key={`${tag}-${index}`}
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                            tag === '已完成'
                              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600'
                              : tag === '已联动'
                                ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                                : tag.includes('风险')
                                  ? hasHighRiskFinding
                                    ? 'border-red-500/20 bg-red-500/10 text-red-600'
                                    : 'border-amber-500/20 bg-amber-500/10 text-amber-600'
                                  : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                          }`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                      {reviewCopy.description}
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
                  onClick={() => jumpToNextModule('flowchart')}
                  disabled={!canContinueWithCurrentTask}
                  title={canContinueWithCurrentTask ? '继续生成流程图' : '请先录入需求或完成评审'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    canContinueWithCurrentTask
                      ? 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)] hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                >
                  去流程图
                </button>
                <button
                  type="button"
                  onClick={() => jumpToNextModule('test-cases')}
                  disabled={!canContinueWithCurrentTask}
                  title={canContinueWithCurrentTask ? '继续进入测试设计阶段' : '请先录入需求或完成评审'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    canContinueWithCurrentTask
                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                >
                  去用例
                </button>
              </div>
            </div>

            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <div className="console-kicker">需求输入</div>
                <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                  {inputMode === 'text' ? '手动录入' : inputMode === 'upload' ? '上传文档' : '读取 TAPD'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSettingsExpanded((value) => !value)}
                className="inline-flex items-center gap-2 rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-medium text-[var(--text-primary)] transition-colors hover:border-[color:var(--border-hover)]"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                <span>{selectedDepthLabel} · {roleCompactLabel}</span>
                {settingsExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
            </div>

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

            {settingsExpanded && (
              <div className={getWorkbenchSettingsDrawerClassName()}>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <div className="console-kicker">评审设置</div>
                    <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">角色与深度</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleRecommend()}
                    className={cn(
                      'rounded-full border px-2.5 py-1 text-[11px] font-medium',
                      getWorkbenchRailToneClassName('accent')
                    )}
                  >
                    智能推荐
                  </button>
                </div>

                <div className="grid gap-4 lg:grid-cols-[180px_minmax(0,1fr)]">
                  <div>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                      深度
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {DEPTHS.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          title={item.desc}
                          onClick={() =>
                            setModuleSession(REVIEW_SESSION_KEY, {
                              options: {
                                ...sessionOptions,
                                depth: item.id,
                              },
                            })
                          }
                          className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                            depth === item.id
                              ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                              : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                      角色
                    </div>
                    <div ref={roleMenuRef} className="relative">
                      <button
                        type="button"
                        aria-expanded={roleMenuOpen}
                        aria-haspopup="listbox"
                        onClick={() => setRoleMenuOpen((value) => !value)}
                        className={cn(
                          'flex min-h-11 w-full items-center justify-between gap-3 rounded-2xl border px-3 py-2 text-left transition-colors',
                          roleMenuOpen
                            ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)]'
                            : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] hover:border-[color:var(--border-hover)]'
                        )}
                      >
                        <span className="min-w-0">
                          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                            评审角色
                          </span>
                          {reviewRoleSummary.badgeLabels.length > 0 ? (
                            <span className="flex flex-wrap gap-1.5">
                              {reviewRoleSummary.badgeLabels.map((label) => (
                                <span
                                  key={label}
                                  className="rounded-full border border-[color:var(--accent-primary-soft)] bg-[var(--surface-panel)] px-2 py-1 text-[11px] font-medium text-[var(--accent-primary)]"
                                >
                                  {label}
                                </span>
                              ))}
                              {reviewRoleSummary.overflowCount > 0 ? (
                                <span className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                                  +{reviewRoleSummary.overflowCount}
                                </span>
                              ) : null}
                            </span>
                          ) : (
                            <span className="block text-sm font-medium text-[var(--text-muted)]">{reviewRoleSummary.text}</span>
                          )}
                        </span>
                        {roleMenuOpen ? (
                          <ChevronUp className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
                        ) : (
                          <ChevronDown className="h-4 w-4 shrink-0 text-[var(--text-secondary)]" />
                        )}
                      </button>

                      {roleMenuOpen ? (
                        <div
                          role="listbox"
                          aria-multiselectable="true"
                          className="absolute left-0 top-[calc(100%+0.5rem)] z-20 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-2 shadow-lg"
                        >
                          <div className="space-y-1">
                            {ROLES.map((role) => {
                              const isSelected = selectedRoles.includes(role.id)

                              return (
                                <label
                                  key={role.id}
                                  role="option"
                                  aria-selected={isSelected}
                                  className={cn(
                                    'flex w-full cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-left text-sm transition-colors',
                                    isSelected
                                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--text-primary)]'
                                      : 'border-transparent bg-transparent text-[var(--text-secondary)] hover:border-[color:var(--border-soft)] hover:bg-[var(--surface-panel-muted)]'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => toggleRole(role.id)}
                                    aria-label={role.label}
                                    className="h-4 w-4 rounded border-[color:var(--border)] accent-[var(--accent-primary)]"
                                  />
                                  <span className="min-w-0 flex-1 truncate">{role.label}</span>
                                </label>
                              )
                            })}
                          </div>

                          <div className="mt-2 flex items-center justify-between gap-2 border-t border-[color:var(--border-soft)] px-1 pt-2">
                            <button
                              type="button"
                              onClick={handleClearRoles}
                              className="rounded-xl border border-[color:var(--border-soft)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]"
                            >
                              清空
                            </button>
                            <button
                              type="button"
                              onClick={handleResetRoles}
                              className="rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-3 py-1.5 text-xs font-medium text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]"
                            >
                              重置默认
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {inputMode === 'text' && (
              <textarea
                value={requirement}
                onChange={(event) => {
                  setInputMode('text')
                  setModuleSession(REVIEW_SESSION_KEY, { requirement: event.target.value })
                }}
                placeholder="粘贴需求说明或功能清单"
                className="mt-4 h-52 w-full resize-none rounded-2xl border p-4 text-sm outline-none transition-colors"
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
              <div className="mt-4 rounded-2xl border px-3 py-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel)' }}>
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
                    onClick={() => void handleImportTapdRequirement()}
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

            {requirementContextId && activeFiles.length === 0 && !activeRequirement && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  最近上下文
                </span>
                <span>{reviewCopy.contextHint}</span>
              </div>
            )}

            <div className={getWorkbenchInputFooterClassName()}>
              <div className="min-w-0 text-sm font-medium text-[var(--text-secondary)]">
                {selectedDepthLabel} · {roleCompactLabel}
              </div>
              <button
                type="button"
                onClick={() => void handleRun()}
                disabled={isRunning}
                className={`shrink-0 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors ${
                  isRunning
                    ? 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                    : 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                }`}
              >
                {runPresentation.primaryActionLabel}
              </button>
            </div>

            {error && (
              <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-xs text-red-500">
                {error}
              </div>
            )}
          </section>
        </div>

        <section ref={resultSectionRef} className="space-y-2">
          <div className="min-w-0">
            <div className={getWorkbenchResultPanelClassName()}>
              <div className={getWorkbenchResultToolbarClassName()} style={{ borderColor: 'var(--border-soft)' }}>
                <div className={getWorkbenchResultToolbarGroupClassName()}>
                  {[
                    { id: 'report', label: '报告' },
                    { id: 'findings', label: '风险' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setModuleSession(REVIEW_SESSION_KEY, { activeTab: tab.id as ReviewTab })}
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
                      onClick={() => setModuleSession(REVIEW_SESSION_KEY, { activeTab: tab.id as ReviewTab })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}

                  {runStatus === 'done' && result && (
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      <button
                        type="button"
                        onClick={handleDownloadMarkdown}
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1.5">
                          <Download className="h-3.5 w-3.5" />
                          MD
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleCopyMarkdown()}
                        title="复制 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1.5">
                          <Clipboard className="h-3.5 w-3.5" />
                          复制
                        </span>
                      </button>
                    </div>
                  )}
                </div>
              </div>

            <div className="relative flex-1 overflow-hidden p-5">
              {activeTab === 'history' ? (
                <HistoryReportPanel
                  types={['review']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                />
              ) : runStatus === 'idle' ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <GitBranch className="h-7 w-7" />
                  </div>
                  <p className="mt-6 text-xl font-semibold text-[var(--text-primary)]">{reviewCopy.emptyTitle}</p>
                  <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{reviewCopy.emptyDescription}</p>
                </div>
              ) : isRunning ? (
                <div className="flex h-full flex-col items-center justify-center py-10">
                  <div className="w-full max-w-2xl space-y-6">
                    <p className="text-center text-xl font-semibold tracking-tight text-[var(--text-primary)]">正在评审...</p>
                    <ProgressTimeline currentStatus={runStatus} />
                    <div className="console-panel-muted p-4">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                      <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                    </div>
                  </div>
                </div>
              ) : activeTab === 'findings' ? (
                findings.length > 0 ? (
                  <div className={getWorkbenchFindingsListClassName()}>
                    {findings.map((finding, index) => (
                      <FindingCard key={`${finding.category}-${index}`} finding={finding} />
                    ))}
                  </div>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <p className="text-base font-semibold text-[var(--text-primary)]">暂无结构化风险</p>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">先看评审报告。</p>
                  </div>
                )
              ) : activeTab === 'log' ? (
                <div className="space-y-6 py-4">
                  <ProgressTimeline currentStatus={runStatus} />
                  <div className="console-panel-muted p-4">
                    <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                    <ExecutionEventLog events={eventLogs} />
                  </div>
                </div>
              ) : result ? (
                <div className="flex h-full flex-col animate-fade-in">
                  <ResultStageBanner
                    title="评审已完成"
                    meta={findings.length > 0 ? `${findings.length} 项风险` : '已生成评审报告'}
                    tone={findings.length > 0 ? 'warning' : 'success'}
                  />
                  <div className={`custom-scrollbar prose prose-sm max-w-none flex-1 overflow-y-auto pr-2 ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                    <ReactMarkdown>{markdown}</ReactMarkdown>
                  </div>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <p className="text-base font-semibold text-red-500">{logFormatErrorCopy.title}</p>
                  <p className="mt-2 text-sm text-[var(--text-secondary)]">{logFormatErrorCopy.description}</p>
                </div>
              )}
            </div>
          </div>
          </div>
        </section>

        <div className={getWorkbenchRailWrapperClassName(collaborationRailCollapsed)}>
          <CollaborationRail
            title="任务摘要"
            subtitle=""
            tags={railTags}
            sections={compactRailSections(collaborationSections)}
            actions={railPrimaryAction ? [railPrimaryAction] : []}
          />
        </div>
      </div>
    </div>
  )
}

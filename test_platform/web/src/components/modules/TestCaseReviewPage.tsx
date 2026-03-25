'use client'

import { useMemo, useState } from 'react'
import type { ColumnDef } from '@tanstack/react-table'
import { Clipboard, Download, FileSearch, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import DataGrid from '@/components/ui/DataGrid'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import { apiClient, type RunProgressEvent, type RunStreamEvent } from '@/lib/api'
import { type TestCaseReviewFinding, type TestCaseReviewPayload } from '@/lib/contracts'
import { downloadMarkdownFile } from '@/lib/markdownFile'
import { resolveModuleSession } from '@/lib/moduleSession'
import { parseTestCaseReviewPayload } from '@/lib/structuredResultParsers'
import { parseTapdInput } from '@/lib/tapdInput'
import { getTestCaseItems, getTestCaseMarkdown, getVisibleTestCaseColumns, sortTestCasesByPriority } from '@/lib/testCaseResult'
import { buildMarkdownDownloadFilename, resolvePreferredDownloadBaseName } from '@/lib/testCaseExportName'
import {
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildResultEmptyCopy,
} from '@/lib/workbenchPresentation'
import { useAppStore } from '@/stores/useAppStore'

type RequirementInputMode = 'text' | 'upload' | 'tapd'
type CaseInputMode = 'linked' | 'text' | 'upload'
type TestCaseReviewStatus = 'idle' | 'context' | 'parsing_cases' | 'aligning' | 'reviewing' | 'revising' | 'done' | 'error'
type TestCaseReviewTab = 'overview' | 'findings' | 'revised-grid' | 'revised-markdown' | 'log' | 'history'

const TEST_CASE_REVIEW_SESSION_KEY = 'test-case-review'

const STATUS_STEPS: { status: Exclude<TestCaseReviewStatus, 'idle' | 'error'>; label: string }[] = [
  { status: 'context', label: '解析需求' },
  { status: 'parsing_cases', label: '解析用例' },
  { status: 'aligning', label: '对齐需求' },
  { status: 'reviewing', label: '评审问题' },
  { status: 'revising', label: '生成修订版' },
  { status: 'done', label: '已完成' },
]

function ProgressTimeline({ currentStatus }: { currentStatus: TestCaseReviewStatus }) {
  const currentIndex = STATUS_STEPS.findIndex((step) => step.status === currentStatus)

  return (
    <div className="space-y-3 py-3">
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

function FindingCard({ finding }: { finding: TestCaseReviewFinding }) {
  const tone = finding.risk_level === 'H' ? 'border-red-500/20 bg-red-500/10' : finding.risk_level === 'M' ? 'border-amber-500/20 bg-amber-500/10' : 'border-emerald-500/20 bg-emerald-500/10'
  const label = finding.risk_level === 'H' ? '高风险' : finding.risk_level === 'M' ? '中风险' : '低风险'

  return (
    <article className={`rounded-2xl border p-4 ${tone}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-white/60 bg-white/70 px-2 py-1 text-[11px] font-semibold text-[var(--text-primary)]">
          {label}
        </span>
        <span className="text-xs font-medium text-[var(--text-secondary)]">{finding.category}</span>
      </div>
      <div className="text-sm font-semibold leading-6 text-[var(--text-primary)]">{finding.description}</div>
      {finding.related_requirement_points.length > 0 && (
        <div className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">
          对应需求点：{finding.related_requirement_points.join('；')}
        </div>
      )}
      {finding.related_case_ids.length > 0 && (
        <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
          关联用例：{finding.related_case_ids.join('；')}
        </div>
      )}
      <div className="mt-3 rounded-xl border border-white/60 bg-white/70 px-3 py-2 text-xs leading-6 text-[var(--text-secondary)]">
        建议：{finding.suggestion}
      </div>
    </article>
  )
}

export default function TestCaseReviewPage() {
  const {
    openInsight,
    requirementContextId,
    setRequirementContextId,
    moduleSessions,
    setModuleSession,
    appendModuleSessionEvent,
    setActiveNav,
    captureTaskSnapshot,
    appearance,
  } = useAppStore()

  const session = resolveModuleSession(moduleSessions[TEST_CASE_REVIEW_SESSION_KEY], {
    runStatus: 'idle',
    activeTab: 'overview',
    options: {
      requirementInputMode: 'text',
      caseInputMode: 'text',
      strictness: 'standard',
      checkOutOfScope: true,
      caseContent: '',
      caseResult: '',
      caseSource: '',
    },
  })

  const options = session.options as {
    requirementInputMode?: RequirementInputMode
    caseInputMode?: CaseInputMode
    strictness?: 'standard' | 'strict'
    checkOutOfScope?: boolean
    caseContent?: string
    caseResult?: string
    caseSource?: string
  }

  const [requirementFiles, setRequirementFiles] = useState<File[]>([])
  const [caseFiles, setCaseFiles] = useState<File[]>([])
  const [tapdInput, setTapdInput] = useState('')
  const [tapdLoading, setTapdLoading] = useState(false)

  const requirement = session.requirement
  const runStatus = session.runStatus as TestCaseReviewStatus
  const activeTab = session.activeTab as TestCaseReviewTab
  const error = session.error
  const result = session.result
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const requirementInputMode = options.requirementInputMode || 'text'
  const strictness = options.strictness || 'standard'
  const checkOutOfScope = options.checkOutOfScope !== false
  const caseResult = typeof options.caseResult === 'string' ? options.caseResult : ''
  const caseContent = typeof options.caseContent === 'string' ? options.caseContent : ''
  const caseSource = typeof options.caseSource === 'string' ? options.caseSource : ''
  const caseInputMode = options.caseInputMode || (caseResult ? 'linked' : 'text')
  const payload = useMemo(() => parseTestCaseReviewPayload(result || ''), [result])
  const isRunning = !['idle', 'done', 'error'].includes(runStatus)
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const resultEmptyCopy = buildResultEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()

  const revisedItems = useMemo(() => {
    if (!payload) {
      return []
    }
    return sortTestCasesByPriority(getTestCaseItems(payload.revised_suite))
  }, [payload])

  const revisedMarkdown = useMemo(() => {
    if (!payload) {
      return ''
    }
    return getTestCaseMarkdown(payload.revised_suite)
  }, [payload])

  const columns = useMemo<ColumnDef<Record<string, string>>[]>(() => {
    const visibleColumns = getVisibleTestCaseColumns(revisedItems)
    return visibleColumns.map((key) => ({
      accessorKey: key,
      header: {
        module: '模块',
        title: '用例标题',
        precondition: '前置条件',
        steps: '步骤',
        priority: '优先级',
        tags: '标签',
        remark: '备注',
      }[key] || key,
      cell: (info) => {
        const value = info.getValue()
        if (key === 'steps' && Array.isArray(value)) {
          return value.map((step: { action: string; expected: string }, index: number) => `${index + 1}. ${step.action} -> ${step.expected}`).join('\n')
        }
        return String(value ?? '')
      },
    }))
  }, [revisedItems])

  const buildExportBaseName = () => resolvePreferredDownloadBaseName({
    persistedBaseName: session.downloadBaseName,
    uploadedFilename: caseFiles[0]?.name || requirementFiles[0]?.name || null,
    requirement,
    sharedRequirement: requirement,
    fallbackName: '测试用例评审',
  })

  const patchOptions = (patch: Record<string, unknown>) => {
    setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
      options: {
        ...options,
        ...patch,
      },
    })
  }

  const handleImportTapdRequirement = async () => {
    const parsed = parseTapdInput(tapdInput.trim())
    if (parsed.kind === 'empty') {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '请输入 TAPD 需求 ID 或链接' })
      return
    }
    if (parsed.kind === 'wecom-doc-link') {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '已识别为腾讯文档链接。读取 TAPD 仅支持 TAPD Story 链接；请将文档正文粘贴到上方，或下载为 Docx/PDF 后上传。' })
      return
    }
    if (parsed.kind === 'unsupported-link' || !parsed.storyId) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '未识别到有效 TAPD Story ID，请检查输入。' })
      return
    }

    setTapdLoading(true)
    try {
      const payload = await apiClient.getTapdStory(parsed.storyId)
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
        requirement: payload.content,
        error: null,
        options: {
          ...options,
          requirementInputMode: 'tapd',
        },
      })
      openInsight(`已识别并读取 TAPD 需求 ${payload.story_id}，可以继续导入测试用例评审。`)
    } catch (err: unknown) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
        error: err instanceof Error ? err.message : buildInlineErrorCopy('tapd'),
      })
    } finally {
      setTapdLoading(false)
    }
  }

  const handleRun = async () => {
    const submittedRequirement = requirementInputMode === 'upload' ? '' : requirement
    const hasRequirementContext = Boolean(submittedRequirement.trim() || requirementFiles.length > 0 || requirementContextId)
    if (!hasRequirementContext) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '请先提供需求描述、上传需求文档，或复用最近一次需求上下文' })
      return
    }

    if (caseInputMode === 'linked' && !caseResult) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '当前没有可送审的测试用例结果，请先生成测试用例或改用文本 / 文件导入' })
      return
    }
    if (caseInputMode === 'text' && !caseContent.trim()) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '请粘贴要评审的测试用例内容' })
      return
    }
    if (caseInputMode === 'upload' && caseFiles.length === 0) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { error: '请上传要评审的测试用例文件' })
      return
    }

    const allFiles = [
      ...(requirementInputMode === 'upload' ? requirementFiles : []),
      ...(caseInputMode === 'upload' ? caseFiles : []),
    ]
    const params: Record<string, unknown> = {
      strictness,
      check_out_of_scope: checkOutOfScope,
      requirement_file_indexes: requirementInputMode === 'upload' ? requirementFiles.map((_, index) => index) : [],
      case_file_indexes: caseInputMode === 'upload'
        ? caseFiles.map((_, index) => (requirementInputMode === 'upload' ? requirementFiles.length : 0) + index)
        : [],
    }
    if (caseInputMode === 'linked') {
      params.case_result = caseResult
    } else if (caseInputMode === 'text') {
      params.case_content = caseContent
    }

    setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
      runStatus: 'context',
      error: null,
      result: null,
      activeTab: 'overview',
      eventLogs: [],
      downloadBaseName: buildExportBaseName(),
    })

    try {
      const response = await apiClient.runSkillStream(
        'test-case-review',
        submittedRequirement,
        allFiles,
        params,
        undefined,
        undefined,
        undefined,
        requirementContextId || undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
              runStatus: event.stage as TestCaseReviewStatus,
            })
            appendModuleSessionEvent(TEST_CASE_REVIEW_SESSION_KEY, event)
          }
        },
      )

      if (!response.success || !response.result) {
        setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
          runStatus: 'error',
          error: response.error || buildInlineErrorCopy('process'),
        })
        return
      }

      const nextPayload = parseTestCaseReviewPayload(response.result)
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
        runStatus: 'done',
        result: response.result,
        error: null,
        activeTab: nextPayload && nextPayload.findings.length > 0 ? 'findings' : 'overview',
      })
      if (response.context_id) {
        setRequirementContextId(response.context_id)
      }
      captureTaskSnapshot()
      openInsight('测试用例评审已完成，问题清单和修订建议版测试用例已生成。')
    } catch (err: unknown) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('process'),
      })
    }
  }

  const handleCopyReport = async () => {
    if (!payload?.markdown) {
      return
    }
    await navigator.clipboard.writeText(payload.markdown)
    openInsight('测试用例评审报告已复制。')
  }

  const handleExportStructuredCases = async (format: 'excel' | 'xmind') => {
    if (!payload) {
      return
    }
    try {
      const exported = await apiClient.exportTestCases(
        JSON.stringify(payload.revised_suite),
        format,
        buildExportBaseName(),
      )
      const url = URL.createObjectURL(exported.blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = exported.filename
      anchor.click()
      URL.revokeObjectURL(url)
      openInsight(format === 'excel' ? '已导出修订建议版 TAPD Excel。' : '已导出修订建议版 XMind。')
    } catch (err: unknown) {
      setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, {
        error: err instanceof Error ? err.message : buildInlineErrorCopy('export'),
      })
    }
  }

  const highRiskCount = payload?.findings.filter((item) => item.risk_level === 'H').length || 0
  const mediumRiskCount = payload?.findings.filter((item) => item.risk_level === 'M').length || 0
  const lowRiskCount = payload?.findings.filter((item) => item.risk_level === 'L').length || 0
  const outOfScopeCount = payload?.findings.filter((item) => item.category.includes('需求外')).length || 0
  const coverageGapCount = payload?.findings.filter((item) => item.category.includes('覆盖')).length || 0

  return (
    <div className="animate-fade-in pb-20">
      <div className="space-y-4">
        <section className="console-panel p-5">
          <div className="mb-5 flex items-start justify-between gap-4 border-b pb-4" style={{ borderColor: 'var(--border-soft)' }}>
            <div className="min-w-0">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                  <FileSearch className="h-[18px] w-[18px]" />
                </div>
                <div className="min-w-0">
                  <div className="console-kicker">用例评审</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)] lg:text-xl">测试用例评审</h1>
                    <span className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                      {payload ? '已生成评审结果' : '待评审'}
                    </span>
                    {requirementContextId && (
                      <span className="rounded-full border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent-primary)]">
                        已联动需求上下文
                      </span>
                    )}
                  </div>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
                    基于原始需求评审现有测试用例的覆盖性、一致性和可执行性，并输出修订建议版测试用例。
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
                onClick={() => setActiveNav('test-cases')}
                className="rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-3 py-2 text-xs font-medium text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]"
              >
                去测试用例
              </button>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
            <div className="space-y-4">
              <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel)' }}>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="console-kicker">需求上下文</div>
                    <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">先绑定原始需求</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {([
                      { id: 'text', label: '粘贴需求' },
                      { id: 'upload', label: '上传文档' },
                      { id: 'tapd', label: '读取 TAPD' },
                    ] as { id: RequirementInputMode; label: string }[]).map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => patchOptions({ requirementInputMode: item.id })}
                        className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                          requirementInputMode === item.id
                            ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                            : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {requirementInputMode === 'text' && (
                  <textarea
                    value={requirement}
                    onChange={(event) => setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { requirement: event.target.value })}
                    placeholder="粘贴需求描述、验收标准或业务规则"
                    className="h-40 w-full resize-none rounded-2xl border p-4 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                )}

                {requirementInputMode === 'upload' && (
                  <FileUploadTrigger
                    ariaLabel="上传需求文档"
                    className="rounded-2xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
                    primaryText={requirementFiles.length > 0 ? `已选 ${requirementFiles.length} 个需求附件` : '上传需求文档'}
                    onFilesChange={setRequirementFiles}
                  />
                )}

                {requirementInputMode === 'tapd' && (
                  <div className="rounded-2xl border px-3 py-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">TAPD 拉取</div>
                    <div className="flex gap-2">
                      <input
                        value={tapdInput}
                        onChange={(event) => setTapdInput(event.target.value)}
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
              </div>

              <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel)' }}>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <div className="console-kicker">测试用例来源</div>
                    <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">选择要评审的测试用例</div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {([
                      { id: 'linked', label: '当前结果' },
                      { id: 'text', label: '粘贴文本' },
                      { id: 'upload', label: '上传文件' },
                    ] as { id: CaseInputMode; label: string }[]).map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => patchOptions({ caseInputMode: item.id })}
                        className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                          caseInputMode === item.id
                            ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                            : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                {caseInputMode === 'linked' && (
                  <div className="rounded-2xl border px-4 py-3 text-sm" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">当前带入结果</div>
                    <div className="mt-2 text-[var(--text-primary)]">
                      {caseResult ? `已带入当前测试用例结果${caseSource ? `（${caseSource}）` : ''}` : '当前没有可直接送审的测试用例结果'}
                    </div>
                  </div>
                )}

                {caseInputMode === 'text' && (
                  <textarea
                    value={caseContent}
                    onChange={(event) => patchOptions({ caseContent: event.target.value })}
                    placeholder="粘贴 Markdown、JSON 或结构化测试用例文本"
                    className="h-40 w-full resize-none rounded-2xl border p-4 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                )}

                {caseInputMode === 'upload' && (
                  <FileUploadTrigger
                    ariaLabel="上传测试用例文件"
                    accept=".md,.markdown,.txt,.json,.xlsx,.xls,.xmind"
                    className="rounded-2xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
                    primaryText={caseFiles.length > 0 ? `已选 ${caseFiles.length} 个测试用例文件` : '上传测试用例文件'}
                    onFilesChange={setCaseFiles}
                  />
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel)' }}>
                <div className="console-kicker">评审设置</div>
                <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">首版默认单测试专家评审</div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {([
                    { id: 'standard', label: '标准评审' },
                    { id: 'strict', label: '严格评审' },
                  ] as { id: 'standard' | 'strict'; label: string }[]).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => patchOptions({ strictness: item.id })}
                      className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                        strictness === item.id
                          ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                          : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="mt-4 rounded-2xl border px-3 py-3" style={{ borderColor: checkOutOfScope ? 'var(--accent-primary-soft)' : 'var(--border-soft)', backgroundColor: checkOutOfScope ? 'var(--surface-accent)' : 'var(--surface-panel-muted)' }}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-[var(--text-primary)]">检查需求外场景</div>
                      <div className="mt-1 text-[11px] text-[var(--text-secondary)]">识别测试用例是否扩展出需求未声明的场景</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => patchOptions({ checkOutOfScope: !checkOutOfScope })}
                      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                        checkOutOfScope
                          ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                          : 'border-[color:var(--border)] bg-[var(--surface-inset)] text-[var(--text-secondary)]'
                      }`}
                    >
                      {checkOutOfScope ? '已启用' : '未启用'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                <div className="text-sm font-semibold text-[var(--text-primary)]">开始评审</div>
                <div className="mt-1 text-[11px] text-[var(--text-secondary)]">
                  没有需求上下文时，外部导入测试用例不会允许提交。
                </div>
                <button
                  type="button"
                  onClick={() => void handleRun()}
                  disabled={isRunning}
                  className={`mt-4 inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-colors ${
                    isRunning
                      ? 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                      : 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                  }`}
                >
                  <Send className="h-4 w-4" />
                  {isRunning ? '评审中' : '开始评审'}
                </button>
              </div>
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-3.5 py-3 text-xs text-red-500">
              {error}
            </div>
          )}
        </section>

        <section className="min-w-0">
          <div className="console-panel overflow-hidden p-0">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4" style={{ borderColor: 'var(--border-soft)' }}>
              <div className="flex flex-wrap gap-2">
                {([
                  { id: 'overview', label: '总览' },
                  { id: 'findings', label: '问题' },
                  { id: 'revised-grid', label: '修订用例' },
                  { id: 'revised-markdown', label: '修订 MD' },
                  { id: 'log', label: '执行' },
                  { id: 'history', label: '历史' },
                ] as { id: TestCaseReviewTab; label: string }[]).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setModuleSession(TEST_CASE_REVIEW_SESSION_KEY, { activeTab: tab.id })}
                    className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                        : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {runStatus === 'done' && payload && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => downloadMarkdownFile(payload.markdown || '', buildMarkdownDownloadFilename(buildExportBaseName(), '测试用例评审报告'))}
                    className="rounded-xl border border-[color:var(--border)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <Download className="h-3.5 w-3.5" />
                      报告 MD
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleCopyReport()}
                    className="rounded-xl border border-[color:var(--border)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <Clipboard className="h-3.5 w-3.5" />
                      复制报告
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleExportStructuredCases('excel')}
                    className="rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-3 py-2 text-xs font-medium text-[var(--accent-primary)]"
                  >
                    导出 TAPD
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleExportStructuredCases('xmind')}
                    className="rounded-xl border border-[color:var(--border)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                  >
                    导出 XMind
                  </button>
                </div>
              )}
            </div>

            <div className="p-5">
              {activeTab === 'history' ? (
                <HistoryReportPanel
                  types={['test_case_review']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                />
              ) : runStatus === 'idle' ? (
                <div className="flex h-full flex-col items-center justify-center py-16 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <FileSearch className="h-7 w-7" />
                  </div>
                  <p className="mt-6 text-xl font-semibold text-[var(--text-primary)]">{resultEmptyCopy.title}</p>
                  <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{resultEmptyCopy.description}</p>
                </div>
              ) : isRunning ? (
                <div className="mx-auto max-w-2xl py-8">
                  <p className="text-center text-xl font-semibold tracking-tight text-[var(--text-primary)]">正在评审测试用例...</p>
                  <ProgressTimeline currentStatus={runStatus} />
                  <div className="console-panel-muted p-4">
                    <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                    <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                  </div>
                </div>
              ) : payload ? (
                <div className="animate-fade-in">
                  <ResultStageBanner
                    title="测试用例评审已完成"
                    meta={payload.summary}
                    tone={payload.findings.length > 0 ? 'warning' : 'success'}
                  />

                  {activeTab === 'overview' && (
                    <div className="space-y-5">
                      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
                        {[
                          { label: '高风险', value: String(highRiskCount) },
                          { label: '中风险', value: String(mediumRiskCount) },
                          { label: '低风险', value: String(lowRiskCount) },
                          { label: '覆盖不足', value: String(coverageGapCount) },
                          { label: '需求外场景', value: String(outOfScopeCount) },
                        ].map((item) => (
                          <div key={item.label} className="rounded-2xl border px-4 py-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{item.label}</div>
                            <div className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{item.value}</div>
                          </div>
                        ))}
                      </div>
                      <div className={`custom-scrollbar prose prose-sm max-w-none overflow-y-auto pr-2 ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                        <ReactMarkdown>{payload.markdown || ''}</ReactMarkdown>
                      </div>
                    </div>
                  )}

                  {activeTab === 'findings' && (
                    payload.findings.length > 0 ? (
                      <div className="grid gap-4 xl:grid-cols-2">
                        {payload.findings.map((finding, index) => (
                          <FindingCard key={`${finding.category}-${index}`} finding={finding} />
                        ))}
                      </div>
                    ) : (
                      <div className="py-16 text-center text-sm text-[var(--text-secondary)]">当前没有结构化问题清单。</div>
                    )
                  )}

                  {activeTab === 'revised-grid' && (
                    <div className="overflow-hidden rounded-xl border" style={{ borderColor: 'var(--border-soft)' }}>
                      <DataGrid data={revisedItems as unknown as Record<string, string>[]} columns={columns} />
                    </div>
                  )}

                  {activeTab === 'revised-markdown' && (
                    <div className={`custom-scrollbar prose prose-sm max-w-none overflow-y-auto pr-2 ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                      <ReactMarkdown>{revisedMarkdown}</ReactMarkdown>
                    </div>
                  )}

                  {activeTab === 'log' && (
                    <div className="space-y-6 py-4">
                      <ProgressTimeline currentStatus={runStatus} />
                      <div className="console-panel-muted p-4">
                        <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                        <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-16 text-center text-sm text-[var(--text-secondary)]">当前结果无法解析为结构化测试用例评审结果。</div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

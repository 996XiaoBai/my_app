'use client'

import { useMemo, useState } from 'react'
import { Download, GitBranch, Workflow } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import MermaidDiagram from '@/components/ui/MermaidDiagram'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import { apiClient, RunProgressEvent, RunStreamEvent } from '@/lib/api'
import type { HistoryReportDetail } from '@/lib/contracts'
import { downloadMarkdownFile } from '@/lib/markdownFile'
import { resolveModuleSession } from '@/lib/moduleSession'
import { parseFlowchartPayload } from '@/lib/structuredResultParsers'
import { buildSeededSessionPatch, buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import { buildMarkdownDownloadFilename, resolvePreferredDownloadBaseName } from '@/lib/testCaseExportName'
import {
  buildExecutionLogCopy,
  buildFlowchartWorkbenchCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildResultFormatErrorCopy,
  buildWorkbenchHeaderCopy,
  buildRunStateValue,
  compactRailSections,
  resolveWorkbenchRunPresentation,
} from '@/lib/workbenchPresentation'
import {
  getWorkbenchRailWrapperClassName,
  getWorkbenchResultPanelClassName,
  getWorkbenchStackClassName,
} from '@/lib/workbenchLayout'
import {
  getWorkbenchModeButtonClassName,
  getWorkbenchModeSwitchClassName,
  getWorkbenchPrimaryActionStripClassName,
  getWorkbenchResultActionGroupClassName,
  getWorkbenchResultActionClassName,
  getWorkbenchResultTabClassName,
  getWorkbenchResultToolbarClassName,
  getWorkbenchResultToolbarGroupClassName,
} from '@/lib/workbenchControls'
import { useAppStore } from '@/stores/useAppStore'

type FlowchartTab = 'diagram' | 'markdown' | 'log' | 'history'
type FlowchartStatus = 'idle' | 'context' | 'done' | 'error' | string
type FlowchartInputMode = 'text' | 'upload'

const FLOWCHART_SESSION_KEY = 'flowchart'
const FLOWCHART_HEADER_COPY = buildWorkbenchHeaderCopy({ module: 'flowchart' })

export default function FlowchartPage() {
  const {
    openInsight,
    moduleSessions,
    setModuleSession,
    appendModuleSessionEvent,
    reviewFindings,
    requirementContextId,
    setActiveNav,
    captureTaskSnapshot,
    appearance,
  } = useAppStore()
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)
  const session = resolveModuleSession(moduleSessions[FLOWCHART_SESSION_KEY], {
    runStatus: 'idle',
    activeTab: 'diagram',
    options: {},
  })

  const requirement = session.requirement
  const [files, setFiles] = useState<File[]>([])
  const [inputMode, setInputMode] = useState<FlowchartInputMode>('text')
  const runStage = session.runStatus as FlowchartStatus
  const result = session.result
  const error = session.error
  const activeTab = session.activeTab as FlowchartTab
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const persistedDownloadBaseName = session.downloadBaseName
  const isRunning = !['idle', 'done', 'error'].includes(runStage)
  const payload = result ? parseFlowchartPayload(result) : null
  const markdown = payload?.markdown || ''
  const activeRequirement = inputMode === 'text' ? requirement : ''
  const activeFiles = inputMode === 'upload' ? files : []
  const warningCount = payload?.items.reduce((count, item) => count + (item.warnings?.length || 0), 0) || 0
  const flowchartCopy = buildFlowchartWorkbenchCopy({
    moduleCount: payload?.items.length || 0,
    warningCount,
    hasMarkdown: Boolean(markdown),
    hasContext: Boolean(requirementContextId),
  })
  const resultFormatErrorCopy = buildResultFormatErrorCopy()
  const inputSourceLabel =
    inputMode === 'upload'
      ? files.length > 0
        ? '上传文档'
        : '等待上传'
      : requirement
        ? '文本录入'
        : '等待输入'
  const taskSummary = useMemo(
    () =>
      buildTaskWorkbenchSummary({
        moduleSessions,
        reviewFindings,
        requirementContextId,
      }),
    [moduleSessions, requirementContextId, reviewFindings]
  )
  const runPresentation = resolveWorkbenchRunPresentation({
    status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
    idleStageLabel: '流程设计',
    doneStageLabel: '流程视图已生成',
    idleActionLabel: '生成',
    runningActionLabel: '生成中',
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()

  const buildExportBaseName = (): string =>
    resolvePreferredDownloadBaseName({
      persistedBaseName: persistedDownloadBaseName,
      uploadedFilename: activeFiles[0]?.name || null,
      requirement: activeRequirement || requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: '业务流程图',
    })

  const handleRun = async () => {
    if (!activeRequirement && activeFiles.length === 0) {
      setModuleSession(FLOWCHART_SESSION_KEY, {
        error: '请提供需求内容或上传文档',
      })
      return
    }

    const nextDownloadBaseName = resolvePreferredDownloadBaseName({
      uploadedFilename: activeFiles[0]?.name || null,
      requirement: activeRequirement || requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: '业务流程图',
    })

    setModuleSession(FLOWCHART_SESSION_KEY, {
      runStatus: 'context',
      error: null,
      result: null,
      downloadBaseName: nextDownloadBaseName,
      eventLogs: [],
      activeTab: 'diagram',
    })

    try {
      const response = await apiClient.runSkillStream(
        'flowchart',
        activeRequirement,
        activeFiles,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(FLOWCHART_SESSION_KEY, {
              runStatus: event.stage,
            })
            appendModuleSessionEvent(FLOWCHART_SESSION_KEY, event)
          }
        }
      )

      if (response.success) {
        setModuleSession(FLOWCHART_SESSION_KEY, {
          result: response.result,
          runStatus: 'done',
          error: null,
        })
        captureTaskSnapshot()
        openInsight('业务流程图已生成。')
      } else {
        setModuleSession(FLOWCHART_SESSION_KEY, {
          runStatus: 'error',
          error: buildInlineErrorCopy('generate'),
        })
      }
    } catch (err: unknown) {
      setModuleSession(FLOWCHART_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('generate'),
      })
    }
  }

  const canContinue = Boolean(requirement || taskSummary.requirement || requirementContextId)
  const handleLoadHistoryReport = (report: HistoryReportDetail) => {
    if (!parseFlowchartPayload(report.content)) {
      setModuleSession(FLOWCHART_SESSION_KEY, {
        error: `${resultFormatErrorCopy.title}，${resultFormatErrorCopy.description}`,
        activeTab: 'history',
      })
      return
    }

    setModuleSession(FLOWCHART_SESSION_KEY, {
      result: report.content,
      runStatus: 'done',
      error: null,
      eventLogs: [],
      activeTab: 'diagram',
    })
    openInsight(`已载入历史流程图：${report.filename || '未命名记录'}。`)
  }

  const jumpToModule = (navId: 'review' | 'test-cases') => {
    const sourceRequirement = requirement || taskSummary.requirement
    const targetKey = navId === 'review' ? 'review' : 'test-case'
    const targetTab = navId === 'review' ? 'report' : 'grid'
    const patch = buildSeededSessionPatch(sourceRequirement, targetTab)

    if (Object.keys(patch).length > 0) {
      setModuleSession(targetKey, patch)
    }
    setActiveNav(navId)
  }

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '流程图状态',
      description: '固定展示流程图生成状态、模块数量和风险提示规模。',
      entries: [
        {
          id: 'run',
          label: '当前阶段',
          value: buildRunStateValue({
            status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '等待开始',
            runningLabel: '流程图生成中',
            doneLabel: '流程图生成完成',
          }),
          detail: `当前标签页：${activeTab === 'diagram' ? '流程图' : activeTab === 'markdown' ? 'Markdown' : activeTab === 'log' ? '执行过程' : '历史记录'}`,
          status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'items',
          label: '流程模块',
          value: `${payload?.items.length || 0} 个`,
          detail: payload ? '已生成模块级 Mermaid 图' : '完成后会按模块输出流程图',
          status: payload?.items.length ? 'done' : 'idle',
        },
        {
          id: 'warnings',
          label: '风险提示',
          value: `${warningCount} 条`,
          detail: '聚合流程中的异常路径与风险提示',
          status: warningCount > 0 ? 'warning' : 'idle',
        },
      ],
    },
    {
      id: 'signals',
      title: '流程信号',
      description: '将输入来源、上下文联动和 Markdown 产物集中到右侧。',
      entries: [
        {
          id: 'source',
          label: '输入来源',
          value: inputSourceLabel,
          detail: files.length > 0 ? `已附加 ${files.length} 个文件` : '当前未附加文件',
          status: activeRequirement || activeFiles.length > 0 ? 'done' : 'idle',
        },
        {
          id: 'context',
          label: '任务上下文',
          value: requirementContextId ? '已联动' : '未联动',
          detail: requirementContextId ? '可和评审、测试设计共用同一条需求' : '建议先完成评审建立上下文',
          status: requirementContextId ? 'done' : 'idle',
        },
        {
          id: 'markdown',
          label: 'Markdown 导出',
          value: markdown ? '可导出' : '待生成',
          detail: markdown ? '当前结果已支持导出 .md' : '生成完成后支持导出 Markdown',
          status: markdown ? 'done' : 'idle',
        },
      ],
    },
    {
      id: 'activity',
      title: '下一步建议',
      description: '让流程图页继续承接评审和测试设计动作。',
      entries: [
        {
          id: 'review',
          label: '看评审',
          value: '补风险',
          detail: '适合在流程图生成后回看高风险发现。',
          status: canContinue ? 'idle' : 'idle',
          onClick: () => jumpToModule('review'),
        },
        {
          id: 'testcases',
          label: '去用例',
          value: '继续设计',
          detail: '将当前需求继续带入测试用例页。',
          status: canContinue ? 'running' : 'idle',
          onClick: () => jumpToModule('test-cases'),
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
                    <Workflow className="h-[18px] w-[18px]" />
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{FLOWCHART_HEADER_COPY.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-lg font-semibold text-[var(--text-primary)] lg:text-xl">{FLOWCHART_HEADER_COPY.title}</h1>
                      {flowchartCopy.tags.map((tag) => (
                        <span
                          key={tag}
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                            tag === '已生成'
                              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600'
                              : tag === '已联动'
                                ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                                : tag.includes('风险')
                                  ? 'border-amber-500/20 bg-amber-500/10 text-amber-600'
                                  : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                          }`}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                      {flowchartCopy.description}
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
                  onClick={() => {
                    setInputMode('text')
                    setModuleSession(FLOWCHART_SESSION_KEY, { requirement: taskSummary.requirement })
                  }}
                  disabled={!taskSummary.requirement}
                  title={taskSummary.requirement ? '将当前任务需求填入输入框' : '当前没有可复用的任务需求'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    taskSummary.requirement
                      ? 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)] hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                >
                  带入任务
                </button>
                <button
                  type="button"
                  onClick={() => jumpToModule('test-cases')}
                  disabled={!canContinue}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    canContinue
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
                <div className="console-kicker">流程输入</div>
                <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                  {inputMode === 'text' ? '粘贴流程' : '上传文档'}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="console-chip">{payload?.items.length ? `${payload.items.length} 个模块` : 'Mermaid 输出'}</span>
              </div>
            </div>

            <div className={getWorkbenchModeSwitchClassName()}>
              {([
                { id: 'text', label: '粘贴流程' },
                { id: 'upload', label: '上传文档' },
              ] as { id: FlowchartInputMode; label: string }[]).map((item) => (
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
                onChange={(event) => {
                  setInputMode('text')
                  setModuleSession(FLOWCHART_SESSION_KEY, { requirement: event.target.value })
                }}
                placeholder="粘贴 PRD、交互说明或流程"
                className="mt-4 h-52 w-full resize-none rounded-xl border p-4 text-sm outline-none transition-colors"
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
            {requirementContextId && activeFiles.length === 0 && !requirement && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  最近上下文
                </span>
                <span>{flowchartCopy.contextHint}</span>
              </div>
            )}
            <div
              className={getWorkbenchPrimaryActionStripClassName()}
              style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
            >
              <div className="min-w-0">
                <div className="text-sm font-semibold text-[var(--text-primary)]">开始生成</div>
                <div className="mt-1 text-[11px] text-[var(--text-secondary)]">
                  先提交输入，再输出流程图和风险提示。
                </div>
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
                <span className="inline-flex items-center gap-2">
                  <Workflow className="h-4 w-4" />
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
                    { id: 'diagram', label: '流程' },
                    { id: 'markdown', label: 'MD' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setModuleSession(FLOWCHART_SESSION_KEY, { activeTab: tab.id as FlowchartTab })}
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
                      onClick={() => setModuleSession(FLOWCHART_SESSION_KEY, { activeTab: tab.id as FlowchartTab })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}

                  {runStage === 'done' && markdown && (
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      <button
                        type="button"
                        onClick={() => downloadMarkdownFile(markdown, buildMarkdownDownloadFilename(buildExportBaseName(), '业务流程图'))}
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1.5">
                          <Download className="h-3.5 w-3.5" />
                          MD
                        </span>
                      </button>
                    </div>
                  )}
                </div>
              </div>

            <div className="relative flex-1 overflow-hidden p-5">
              {activeTab === 'history' ? (
                <HistoryReportPanel
                  types={['flowchart']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                  onLoadReport={handleLoadHistoryReport}
                  loadActionLabel="载入流程图"
                />
              ) : runStage === 'idle' ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <GitBranch className="h-7 w-7" />
                  </div>
                  <p className="mt-6 text-xl font-semibold text-[var(--text-primary)]">{flowchartCopy.emptyTitle}</p>
                  <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{flowchartCopy.emptyDescription}</p>
                </div>
              ) : isRunning ? (
                <div className="console-panel-muted h-full p-4">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                  <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                </div>
              ) : activeTab === 'markdown' ? (
                <div className={`custom-scrollbar prose prose-sm max-w-none h-full overflow-y-auto pr-2 ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                  <ReactMarkdown>{markdown}</ReactMarkdown>
                </div>
              ) : activeTab === 'log' ? (
                <div className="console-panel-muted h-full p-4">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                  <ExecutionEventLog events={eventLogs} />
                </div>
              ) : payload ? (
                <div className="custom-scrollbar h-full space-y-6 overflow-y-auto pr-2">
                  <ResultStageBanner
                    title="流程图已生成"
                    meta={`${payload.items.length} 个模块 · ${warningCount} 条风险`}
                    tone={warningCount > 0 ? 'warning' : 'success'}
                  />
                  {payload.items.map((item) => (
                    <div key={`${item.module}-${item.title}`} className="console-panel-muted p-5">
                      <div>
                        <h3 className="text-lg font-semibold text-[var(--text-primary)]">{item.title}</h3>
                        {item.summary && <p className="mt-2 text-sm text-[var(--text-secondary)]">{item.summary}</p>}
                      </div>
                      <div className="mt-4">
                        {item.mermaid ? (
                          <MermaidDiagram code={item.mermaid} title={item.title} />
                        ) : (
                          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-6 text-center">
                            <p className="text-sm font-semibold text-amber-600">{resultFormatErrorCopy.title}</p>
                            <p className="mt-2 text-xs text-amber-700/80">{resultFormatErrorCopy.description}</p>
                          </div>
                        )}
                      </div>
                      {item.warnings && item.warnings.length > 0 && (
                        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-600">
                          <div className="mb-2 font-semibold">风险提示</div>
                          <div className="space-y-1">
                            {item.warnings.map((warning) => (
                              <div key={warning}>- {warning}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <p className="text-base font-semibold text-red-500">{resultFormatErrorCopy.title}</p>
                  <p className="mt-2 text-sm text-[var(--text-secondary)]">{resultFormatErrorCopy.description}</p>
                </div>
              )}
            </div>
          </div>
          </div>
        </section>

        <div className={getWorkbenchRailWrapperClassName(collaborationRailCollapsed)}>
          <CollaborationRail
            title="流程图"
            subtitle=""
            tags={[
              { label: flowchartCopy.tags[0], tone: 'accent' },
              { label: flowchartCopy.tags[1], tone: warningCount > 0 ? 'warning' : markdown ? 'success' : 'neutral' },
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
              { label: '去测试用例', onClick: () => jumpToModule('test-cases') },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

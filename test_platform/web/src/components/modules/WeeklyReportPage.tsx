'use client'

import { useMemo, useState } from 'react'
import { AlertTriangle, Clipboard, Download, ExternalLink, GitBranch, Newspaper } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import { apiClient, RunProgressEvent, RunStreamEvent } from '@/lib/api'
import { downloadMarkdownFile } from '@/lib/markdownFile'
import { resolveModuleSession } from '@/lib/moduleSession'
import { buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import {
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildProgressStepLabelMap,
  buildResultFailureCopy,
  buildWeeklyReportWorkbenchCopy,
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
  getWorkbenchResultActionClassName,
  getWorkbenchResultActionGroupClassName,
  getWorkbenchResultTabClassName,
  getWorkbenchResultToolbarClassName,
  getWorkbenchResultToolbarGroupClassName,
} from '@/lib/workbenchControls'
import { useAppStore } from '@/stores/useAppStore'

type WeeklyRunStatus =
  | 'idle'
  | 'collecting'
  | 'summarizing'
  | 'publishing'
  | 'organizing'
  | 'done'
  | 'error'

type WeeklyTab = 'preview' | 'log' | 'history'

interface WeeklyReportMeta {
  title?: string
  feishu_url?: string | null
  published_to_feishu?: boolean
  publish_requested?: boolean
}

const WEEKLY_PROGRESS_LABELS = buildProgressStepLabelMap('weekly')

const STATUS_STEPS: { status: WeeklyRunStatus; label: string }[] = [
  { status: 'collecting', label: WEEKLY_PROGRESS_LABELS.collecting },
  { status: 'summarizing', label: WEEKLY_PROGRESS_LABELS.summarizing },
  { status: 'publishing', label: WEEKLY_PROGRESS_LABELS.publishing },
  { status: 'organizing', label: WEEKLY_PROGRESS_LABELS.organizing },
  { status: 'done', label: WEEKLY_PROGRESS_LABELS.done },
]

const WEEKLY_REPORT_SESSION_KEY = 'weekly-report'
const WEEKLY_HEADER_COPY = buildWorkbenchHeaderCopy({ module: 'weekly' })

function ProgressTimeline({ currentStatus }: { currentStatus: WeeklyRunStatus }) {
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

function buildMarkdownFilename() {
  const now = new Date()
  const parts = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
    '-',
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0'),
  ]
  return `测试周报-${parts.join('')}.md`
}

export default function WeeklyReportPage() {
  const {
    openInsight,
    moduleSessions,
    setModuleSession,
    appendModuleSessionEvent,
    reviewFindings,
    requirementContextId,
    setActiveNav,
    appearance,
  } = useAppStore()
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)
  const session = resolveModuleSession(moduleSessions[WEEKLY_REPORT_SESSION_KEY], {
    runStatus: 'idle',
    activeTab: 'preview',
    options: {
      extraPrompt: '',
      publishToFeishu: true,
      resultMeta: null,
    },
  })
  const sessionOptions = session.options as {
    extraPrompt?: string
    publishToFeishu?: boolean
    resultMeta?: WeeklyReportMeta | null
  }

  const discussion = session.requirement
  const extraPrompt = typeof sessionOptions.extraPrompt === 'string' ? sessionOptions.extraPrompt : ''
  const publishToFeishu = typeof sessionOptions.publishToFeishu === 'boolean' ? sessionOptions.publishToFeishu : true
  const [files, setFiles] = useState<File[]>([])
  const runStatus = session.runStatus as WeeklyRunStatus
  const activeTab = session.activeTab as WeeklyTab
  const result = session.result || ''
  const resultMeta = (sessionOptions.resultMeta || null) as WeeklyReportMeta | null
  const error = session.error
  const eventLogs = session.eventLogs as RunProgressEvent[]
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
  const weeklyCopy = buildWeeklyReportWorkbenchCopy({
    publishToFeishu,
    screenshotsCount: files.length,
    hasResult: Boolean(result),
    hasContext: Boolean(requirementContextId),
  })
  const runPresentation = resolveWorkbenchRunPresentation({
    status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
    idleStageLabel: '输出沉淀',
    doneStageLabel: '周报已沉淀',
    idleActionLabel: '生成',
    runningActionLabel: '生成中',
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()
  const failureCopy = buildResultFailureCopy()
  const weeklyContextHintVisible = !discussion.trim() && files.length === 0 && Boolean(taskSummary.requirement || requirementContextId)
  const weeklyContextHintLabel = requirementContextId ? '最近上下文' : '当前任务'
  const weeklyContextHintText = requirementContextId
    ? weeklyCopy.contextHint
    : '当前任务已有可复用内容，可点击右上角“带入任务”快速填充输入区。'

  const handleRun = async () => {
    if (!discussion.trim() && files.length === 0) {
      setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
        error: '请提供企业微信讨论内容或上传 TAPD 截图',
      })
      return
    }

    setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
      runStatus: 'collecting',
      activeTab: 'preview',
      result: null,
      error: null,
      eventLogs: [],
      options: {
        ...sessionOptions,
        resultMeta: null,
      },
    })

    try {
      const response = await apiClient.runSkillStream(
        'weekly-report',
        discussion,
        files,
        { publish_to_feishu: publishToFeishu },
        undefined,
        extraPrompt,
        undefined,
        undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
              runStatus: event.stage as WeeklyRunStatus,
            })
            appendModuleSessionEvent(WEEKLY_REPORT_SESSION_KEY, event)
          }
        }
      )

      if (!response.success) {
        throw new Error(buildInlineErrorCopy('generate'))
      }

      setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
        result: response.result,
        runStatus: 'done',
        error: null,
        options: {
          ...sessionOptions,
          resultMeta: (response.meta || {}) as WeeklyReportMeta,
        },
      })
      openInsight('测试周报已生成，可直接复制 Markdown 或查看飞书链接。')
    } catch (err: unknown) {
      setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('generate'),
      })
    }
  }

  const handleCopyMarkdown = async () => {
    if (!result) return
    await navigator.clipboard.writeText(result)
    openInsight('周报 Markdown 已复制。')
  }

  const handleDownloadMarkdown = () => {
    if (!result) return
    downloadMarkdownFile(result, buildMarkdownFilename())
    openInsight('周报 Markdown 已下载。')
  }

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '周报状态',
      description: '固定展示收集、总结、发布和整理阶段。',
      entries: [
        {
          id: 'run',
          label: '当前阶段',
          value: buildRunStateValue({
            status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '等待开始生成',
            runningLabel: STATUS_STEPS.find((step) => step.status === runStatus)?.label || '生成中',
            doneLabel: WEEKLY_PROGRESS_LABELS.done,
          }),
          detail: `当前标签页：${activeTab === 'preview' ? '周报预览' : activeTab === 'log' ? '执行日志' : '历史周报'}`,
          status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'publish',
          label: '飞书发布',
          value: publishToFeishu ? '已开启' : '未开启',
          detail: publishToFeishu ? '生成完成后会尝试同步飞书文档' : '仅生成 Markdown 结果',
          status: publishToFeishu ? 'running' : 'idle',
        },
        {
          id: 'result',
          label: '结果产物',
          value: result ? '已生成周报' : '未生成',
          detail: resultMeta?.title || '完成后会生成结构化 Markdown 周报',
          status: result ? 'done' : 'idle',
        },
      ],
    },
    {
      id: 'signals',
      title: '周报信号',
      description: '汇总输入来源、截图规模和发布结果。',
      entries: [
        {
          id: 'discussion',
          label: '讨论输入',
          value: discussion ? '已录入' : '未录入',
          detail: discussion ? '企业微信讨论内容已提供' : '当前未填写讨论内容',
          status: discussion ? 'done' : 'idle',
        },
        {
          id: 'screenshots',
          label: '截图数量',
          value: `${files.length} 张`,
          detail: files.length > 0 ? '将辅助提取 TAPD 任务和状态信息' : '当前未上传截图',
          status: files.length > 0 ? 'done' : 'idle',
        },
        {
          id: 'feishu',
          label: '发布结果',
          value: resultMeta?.published_to_feishu ? '已同步飞书' : resultMeta?.publish_requested ? '同步失败，已保留 Markdown' : '未发布',
          detail: resultMeta?.feishu_url ? '可直接打开飞书文档' : '如未开启发布，仅保留 Markdown',
          status: resultMeta?.published_to_feishu ? 'done' : resultMeta?.publish_requested ? 'warning' : 'idle',
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
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <Newspaper className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{WEEKLY_HEADER_COPY.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-xl font-semibold text-[var(--text-primary)]">{WEEKLY_HEADER_COPY.title}</h1>
                      {weeklyCopy.tags.map((tag, index) => (
                        <span
                          key={`${tag}-${index}`}
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
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                      {weeklyCopy.description}
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
                  onClick={() => setModuleSession(WEEKLY_REPORT_SESSION_KEY, { requirement: taskSummary.requirement })}
                  disabled={!taskSummary.requirement}
                  title={taskSummary.requirement ? '将当前任务需求填入输入框' : '当前没有可复用的任务需求'}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    taskSummary.requirement
                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                      : 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                  }`}
                >
                  带入任务
                </button>
              </div>
            </div>

            <div className="console-kicker">讨论输入</div>
            <textarea
              value={discussion}
              onChange={(event) => setModuleSession(WEEKLY_REPORT_SESSION_KEY, { requirement: event.target.value })}
              placeholder="粘贴本周结论和待跟进项"
              className="mt-3 h-48 w-full resize-none rounded-xl border p-4 text-sm outline-none transition-colors"
              style={{ borderColor: 'var(--border)' }}
            />

            {weeklyContextHintVisible && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  {weeklyContextHintLabel}
                </span>
                <span>{weeklyContextHintText}</span>
              </div>
            )}
          </section>

          <section className="console-panel p-5">
            <div className="console-kicker">上传截图</div>
            <FileUploadTrigger
              ariaLabel="上传截图"
              accept=".png,.jpg,.jpeg,.bmp,.webp"
              className="mt-4 rounded-xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
              primaryText={files.length > 0 ? `已选 ${files.length} 张截图` : '上传截图'}
              onFilesChange={setFiles}
            />
            {files.length > 0 && (
              <div className="mt-3 space-y-2">
                {files.map((file, index) => (
                  <div key={`${file.name}-${index}`} className="console-inset flex items-center gap-2 px-3 py-2">
                    <span>🖼️</span>
                    <span className="flex-1 truncate text-xs text-[var(--text-primary)]">{file.name}</span>
                    <button
                      type="button"
                      onClick={() => setFiles((prev) => prev.filter((_, itemIndex) => itemIndex !== index))}
                      className="text-xs text-[var(--text-muted)] transition-colors hover:text-red-500"
                    >
                      删除
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="console-panel p-5">
            <div className="console-kicker">补充要求</div>
            <textarea
              value={extraPrompt}
              onChange={(event) =>
                setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
                  options: {
                    ...sessionOptions,
                    extraPrompt: event.target.value,
                  },
                })
              }
              placeholder="例如：突出稳定性、风险治理、自动化收益"
              className="mt-4 h-24 w-full resize-none rounded-xl border p-3 text-sm outline-none transition-colors"
              style={{ borderColor: 'var(--border)' }}
            />
            <div className="mt-4 flex items-center justify-between gap-4 rounded-xl border px-3 py-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
              <div>
                <div className="text-sm font-semibold text-[var(--text-primary)]">同步飞书</div>
                <div className="mt-1 text-[11px] text-[var(--text-secondary)]">关闭后仅保留 MD</div>
              </div>
              <button
                type="button"
                onClick={() =>
                  setModuleSession(WEEKLY_REPORT_SESSION_KEY, {
                    options: {
                      ...sessionOptions,
                  publishToFeishu: !publishToFeishu,
                    },
                  })
                }
                className={`relative h-[22px] w-10 rounded-full transition-colors ${publishToFeishu ? 'bg-[var(--accent-primary)]' : 'bg-[var(--surface-inset)]'}`}
              >
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${publishToFeishu ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </section>

          <button
            onClick={() => void handleRun()}
            disabled={isRunning}
            className={`flex w-full items-center justify-center gap-2 rounded-2xl border px-4 py-4 text-sm font-semibold transition-colors ${
              isRunning
                ? 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                : 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
            }`}
          >
            <Newspaper className="h-4 w-4" />
            {runPresentation.primaryActionLabel}
          </button>

          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-3 text-xs text-red-500">
              {error}
            </div>
          )}
        </div>

        <section className="space-y-2">
          <div className="min-w-0">
            <div className={getWorkbenchResultPanelClassName('block')}>
              <div className={getWorkbenchResultToolbarClassName()} style={{ borderColor: 'var(--border-soft)' }}>
                <div className={getWorkbenchResultToolbarGroupClassName()}>
                  {[
                    { id: 'preview', label: '周报' },
                    { id: 'log', label: '执行' },
                    { id: 'history', label: '历史' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setModuleSession(WEEKLY_REPORT_SESSION_KEY, { activeTab: tab.id as WeeklyTab })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {runStatus === 'done' && result && activeTab !== 'history' && (
                  <div className={getWorkbenchResultToolbarGroupClassName('end')}>
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      {resultMeta?.feishu_url && (
                        <a
                          href={resultMeta.feishu_url}
                          target="_blank"
                          rel="noreferrer"
                          className={getWorkbenchResultActionClassName()}
                          style={{ borderColor: 'var(--border)' }}
                        >
                          <span className="inline-flex items-center gap-1">
                            <ExternalLink className="h-3 w-3" />
                            飞书
                          </span>
                        </a>
                      )}
                      <button
                        onClick={handleDownloadMarkdown}
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Download className="h-3 w-3" />
                          MD
                        </span>
                      </button>
                      <button
                        onClick={() => void handleCopyMarkdown()}
                        title="复制 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Clipboard className="h-3 w-3" />
                          复制
                        </span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

            <div className="p-5">
              {activeTab === 'history' ? (
                <HistoryReportPanel
                  types={['weekly-report']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                />
              ) : runStatus === 'idle' ? (
                <div className="flex min-h-[700px] flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <GitBranch className="h-7 w-7" />
                  </div>
                  <p className="mt-6 text-xl font-semibold text-[var(--text-primary)]">{weeklyCopy.emptyTitle}</p>
                  <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{weeklyCopy.emptyDescription}</p>
                </div>
              ) : isRunning ? (
                <div className="flex min-h-[700px] flex-col items-center justify-center py-12">
                  <div className="w-full max-w-2xl space-y-6">
                    <p className="text-center text-xl font-semibold text-[var(--text-primary)]">正在生成周报...</p>
                    <ProgressTimeline currentStatus={runStatus} />
                    <div className="console-panel-muted p-4">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                      <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                    </div>
                  </div>
                </div>
              ) : runStatus === 'done' ? (
                <div className="animate-fade-in">
                  {activeTab === 'preview' && (
                    <div className="space-y-4">
                      <ResultStageBanner
                        title={resultMeta?.title || '测试周报已生成'}
                        meta={
                          resultMeta?.published_to_feishu
                            ? '已同步飞书'
                            : resultMeta?.publish_requested
                              ? '飞书同步失败，已保留 Markdown'
                              : '仅生成 Markdown'
                        }
                        tone={resultMeta?.publish_requested && !resultMeta?.published_to_feishu ? 'warning' : 'success'}
                      />
                      <div className={`custom-scrollbar prose prose-sm max-w-none min-h-[620px] overflow-y-auto rounded-2xl border p-6 ${appearance === 'dark' ? 'prose-invert' : ''}`} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                        <ReactMarkdown>{result}</ReactMarkdown>
                      </div>
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
              ) : (
                <div className="flex min-h-[700px] flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
                    <AlertTriangle className="h-7 w-7" />
                  </div>
                  <p className="mt-5 text-lg font-semibold text-red-500">{failureCopy.title}</p>
                  <p className="mt-2 text-sm text-[var(--text-secondary)]">{error}</p>
                  <button
                    type="button"
                    onClick={() => void handleRun()}
                    className="mt-6 rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-4 py-2 text-sm font-medium text-[var(--accent-primary)]"
                  >
                    {failureCopy.actionLabel}
                  </button>
                </div>
              )}
            </div>
            </div>
          </div>
        </section>

        <div className={getWorkbenchRailWrapperClassName(collaborationRailCollapsed)}>
          <CollaborationRail
            title="测试周报"
            subtitle=""
            tags={[
              { label: runPresentation.stageLabel, tone: result ? 'success' : isRunning ? 'accent' : 'neutral' },
              { label: weeklyCopy.tags[1], tone: files.length > 0 ? 'accent' : 'neutral' },
              { label: weeklyCopy.tags[2], tone: publishToFeishu ? 'accent' : 'neutral' },
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
              { label: '回工作台', onClick: () => setActiveNav('dashboard') },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

'use client'

import { useMemo, useState } from 'react'
import { Braces, Download, GitBranch, Layers3 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import { apiClient, RunProgressEvent, RunStreamEvent } from '@/lib/api'
import type { RequirementAnalysisPack } from '@/lib/contracts'
import { downloadMarkdownFile } from '@/lib/markdownFile'
import { resolveModuleSession } from '@/lib/moduleSession'
import { parseRequirementAnalysisPayload } from '@/lib/structuredResultParsers'
import { buildSeededSessionPatch, buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import { buildMarkdownDownloadFilename, resolvePreferredDownloadBaseName } from '@/lib/testCaseExportName'
import {
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildRequirementAnalysisWorkbenchCopy,
  buildResultEmptyCopy,
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
  getWorkbenchResultActionClassName,
  getWorkbenchResultActionGroupClassName,
  getWorkbenchResultTabClassName,
  getWorkbenchResultToolbarClassName,
  getWorkbenchResultToolbarGroupClassName,
} from '@/lib/workbenchControls'
import { useAppStore } from '@/stores/useAppStore'

type AnalysisTab = 'structured' | 'markdown' | 'log' | 'history'
type AnalysisStatus = 'idle' | 'context' | 'done' | 'error' | string

const REQUIREMENT_ANALYSIS_SESSION_KEY = 'req-analysis'
const REQUIREMENT_ANALYSIS_HEADER_COPY = buildWorkbenchHeaderCopy({ module: 'req-analysis' })

const SECTION_LABELS: { key: keyof RequirementAnalysisPack['items'][number]; label: string }[] = [
  { key: 'actors', label: '参与角色' },
  { key: 'business_rules', label: '业务规则' },
  { key: 'data_entities', label: '数据实体' },
  { key: 'preconditions', label: '前置条件' },
  { key: 'postconditions', label: '后置条件' },
  { key: 'exceptions', label: '异常处理' },
  { key: 'risks', label: '显性风险' },
  { key: 'open_questions', label: '待确认问题' },
]

function AnalysisSection({
  title,
  values,
}: {
  title: string
  values: string[]
}) {
  return (
    <div className="console-panel-muted p-4">
      <div className="console-kicker">{title}</div>
      <div className="mt-3 space-y-2">
        {values.map((value) => (
          <div key={value} className="text-sm leading-6 text-[var(--text-secondary)]">
            - {value}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function RequirementAnalysisPage() {
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
  const session = resolveModuleSession(moduleSessions[REQUIREMENT_ANALYSIS_SESSION_KEY], {
    runStatus: 'idle',
    activeTab: 'structured',
    options: {},
  })

  const requirement = session.requirement
  const [files, setFiles] = useState<File[]>([])
  const runStage = session.runStatus as AnalysisStatus
  const result = session.result
  const error = session.error
  const activeTab = session.activeTab as AnalysisTab
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const persistedDownloadBaseName = session.downloadBaseName
  const isRunning = !['idle', 'done', 'error'].includes(runStage)

  const payload = result ? parseRequirementAnalysisPayload(result) : null

  const markdown = payload?.markdown || ''
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
    idleStageLabel: '结构化拆解',
    doneStageLabel: '结构已拆清',
    idleActionLabel: '分析',
    runningActionLabel: '分析中',
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const resultEmptyCopy = buildResultEmptyCopy({ mode: 'preview' })
  const eventLogCopy = buildExecutionLogCopy()
  const resultFormatErrorCopy = buildResultFormatErrorCopy()
  const analysisCopy = buildRequirementAnalysisWorkbenchCopy({
    hasResult: Boolean(markdown),
    hasContext: Boolean(requirementContextId),
    moduleCount: payload?.items.length || 0,
  })

  const buildExportBaseName = (): string =>
    resolvePreferredDownloadBaseName({
      persistedBaseName: persistedDownloadBaseName,
      uploadedFilename: files[0]?.name || null,
      requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: '需求结构化分析',
    })

  const handleRun = async () => {
    if (!requirement && files.length === 0) {
      setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, {
        error: '请提供需求内容或上传文档',
      })
      return
    }

    const nextDownloadBaseName = resolvePreferredDownloadBaseName({
      uploadedFilename: files[0]?.name || null,
      requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: '需求结构化分析',
    })

    setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, {
      runStatus: 'context',
      error: null,
      result: null,
      downloadBaseName: nextDownloadBaseName,
      eventLogs: [],
      activeTab: 'structured',
    })

    try {
      const response = await apiClient.runSkillStream(
        'req-analysis',
        requirement,
        files,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, {
              runStatus: event.stage,
            })
            appendModuleSessionEvent(REQUIREMENT_ANALYSIS_SESSION_KEY, event)
          }
        }
      )

      if (response.success) {
        setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, {
          result: response.result,
          runStatus: 'done',
          error: null,
        })
        captureTaskSnapshot()
        openInsight('需求结构化分析已完成。')
      } else {
        setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, {
          runStatus: 'error',
          error: buildInlineErrorCopy('process'),
        })
      }
    } catch (err: unknown) {
      setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('process'),
      })
    }
  }

  const canContinue = Boolean(requirement || taskSummary.requirement || requirementContextId)
  const jumpToModule = (navId: 'test-cases' | 'flowchart') => {
    const sourceRequirement = requirement || taskSummary.requirement
    const targetKey = navId === 'test-cases' ? 'test-case' : 'flowchart'
    const targetTab = navId === 'test-cases' ? 'grid' : 'diagram'
    const patch = buildSeededSessionPatch(sourceRequirement, targetTab)

    if (Object.keys(patch).length > 0) {
      setModuleSession(targetKey, patch)
    }
    setActiveNav(navId)
  }

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '分析状态',
      description: '固定展示结构化分析阶段、模块规模与输出落点。',
      entries: [
        {
          id: 'run',
          label: '当前阶段',
          value: buildRunStateValue({
            status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '等待开始',
            runningLabel: '分析中',
            doneLabel: '结构化分析完成',
          }),
          detail: `当前标签页：${activeTab === 'structured' ? '结构化视图' : activeTab === 'markdown' ? 'Markdown' : activeTab === 'log' ? '执行过程' : '历史记录'}`,
          status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'modules',
          label: '模块拆解',
          value: `${payload?.items.length || 0} 个`,
          detail: payload ? '已提取模块、规则、实体与异常' : '完成后会形成结构化模块清单',
          status: payload?.items.length ? 'done' : 'idle',
        },
        {
          id: 'risk',
          label: '评审风险',
          value: `${reviewFindings.length} 项`,
          detail: reviewFindings.length > 0 ? '可结合评审风险进一步细化规则与异常' : '当前无评审发现回灌',
          status: reviewFindings.length > 0 ? 'warning' : 'idle',
        },
      ],
    },
    {
      id: 'signals',
      title: '结构化信号',
      description: '将输入来源、上下文复用和后续设计动作汇总到侧栏。',
      entries: [
        {
          id: 'source',
          label: '输入来源',
          value: requirement ? '文本录入' : files.length > 0 ? '上传文档' : '等待输入',
          detail: files.length > 0 ? `已附加 ${files.length} 个文件` : '当前未附加文件',
          status: requirement || files.length > 0 ? 'done' : 'idle',
        },
        {
          id: 'context',
          label: '任务上下文',
          value: requirementContextId ? '已联动' : '未联动',
          detail: requirementContextId ? '可跨模块带入同一条需求' : '建议先从评审页建立上下文',
          status: requirementContextId ? 'done' : 'idle',
        },
        {
          id: 'markdown',
          label: 'Markdown 产物',
          value: markdown ? '已生成' : '未生成',
          detail: markdown ? '可直接导出并沉淀为中间设计资产' : '完成后可导出 Markdown',
          status: markdown ? 'done' : 'idle',
        },
      ],
    },
    {
      id: 'activity',
      title: '下一步建议',
      description: '把结构化分析结果直接带到测试设计与流程图阶段。',
      entries: [
        {
          id: 'testcases',
          label: '去用例',
          value: '继续设计',
          detail: '将当前需求带入测试用例页继续产出。',
          status: canContinue ? 'running' : 'idle',
          onClick: () => jumpToModule('test-cases'),
        },
        {
          id: 'flowchart',
          label: '去流程图',
          value: '看流程',
          detail: '适合在结构化拆解后生成 Mermaid 流程图。',
          status: canContinue ? 'idle' : 'idle',
          onClick: () => jumpToModule('flowchart'),
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
                    <Braces className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{REQUIREMENT_ANALYSIS_HEADER_COPY.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-xl font-semibold text-[var(--text-primary)]">{REQUIREMENT_ANALYSIS_HEADER_COPY.title}</h1>
                      {analysisCopy.tags.map((tag) => (
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
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                      {analysisCopy.description}
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
                  onClick={() => setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, { requirement: taskSummary.requirement })}
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

            <div className="console-kicker">需求输入</div>
            <textarea
              value={requirement}
              onChange={(event) => setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, { requirement: event.target.value })}
              placeholder="粘贴 PRD、TAPD 或变更点"
              className="mt-3 h-52 w-full resize-none rounded-xl border p-4 text-sm outline-none transition-colors"
              style={{ borderColor: 'var(--border)' }}
            />

            <FileUploadTrigger
              ariaLabel="上传附件"
              className="mt-3 rounded-xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
              primaryText={files.length > 0 ? `已选 ${files.length} 个附件` : '上传附件'}
              onFilesChange={setFiles}
            />

            {requirementContextId && files.length === 0 && !requirement && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  最近上下文
                </span>
                <span>{analysisCopy.contextHint}</span>
              </div>
            )}
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
            <Layers3 className="h-4 w-4" />
            {runPresentation.primaryActionLabel}
          </button>

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
                    { id: 'structured', label: '结构' },
                    { id: 'markdown', label: 'MD' },
                    { id: 'log', label: '执行' },
                    { id: 'history', label: '历史' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setModuleSession(REQUIREMENT_ANALYSIS_SESSION_KEY, { activeTab: tab.id as AnalysisTab })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {runStage === 'done' && markdown && (
                  <div className={getWorkbenchResultToolbarGroupClassName('end')}>
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      <button
                        type="button"
                        onClick={() => downloadMarkdownFile(markdown, buildMarkdownDownloadFilename(buildExportBaseName(), '需求结构化分析'))}
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Download className="h-3 w-3" />
                          MD
                        </span>
                      </button>
                    </div>
                  </div>
                )}
              </div>

            <div className="relative flex-1 overflow-hidden p-5">
              {activeTab === 'history' ? (
                <HistoryReportPanel
                  types={['req_analysis']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                />
              ) : runStage === 'idle' ? (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
                    <GitBranch className="h-7 w-7" />
                  </div>
                  <p className="mt-6 text-xl font-semibold text-[var(--text-primary)]">{resultEmptyCopy.title}</p>
                  <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{resultEmptyCopy.description}</p>
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
                <div className="custom-scrollbar h-full space-y-4 overflow-y-auto pr-2">
                  <ResultStageBanner
                    title="结构化分析已完成"
                    meta={`${payload.items.length} 个模块`}
                  />
                  {payload.items.map((item) => (
                    <div key={item.module} className="console-panel-muted p-5">
                      <div className="mb-4">
                        <h3 className="text-lg font-semibold text-[var(--text-primary)]">{item.module}</h3>
                        {item.summary && <p className="mt-2 text-sm text-[var(--text-secondary)]">{item.summary}</p>}
                      </div>
                      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                        {SECTION_LABELS.map((section) => {
                          const values = item[section.key]
                          if (!Array.isArray(values) || values.length === 0) {
                            return null
                          }
                          return <AnalysisSection key={`${item.module}-${section.key}`} title={section.label} values={values} />
                        })}
                      </div>
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
            title="需求分析"
            subtitle=""
            tags={[
              { label: '结构化分析', tone: 'accent' },
              { label: `${payload?.items.length || 0} 个模块`, tone: 'neutral' },
              { label: markdown ? '已生成 Markdown' : '待生成', tone: markdown ? 'success' : 'neutral' },
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

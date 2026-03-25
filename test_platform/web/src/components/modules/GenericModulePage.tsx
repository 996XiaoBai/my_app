'use client'

import { useMemo, useState } from 'react'
import { Clipboard, Download, Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import { apiClient, type RunProgressEvent, type RunStreamEvent } from '@/lib/api'
import { type GenericModuleTab, getGenericModuleHistoryTypes } from '@/lib/genericModule'
import { downloadMarkdownFile, downloadSqlFile } from '@/lib/markdownFile'
import { resolveModuleSession } from '@/lib/moduleSession'
import { parseTestDataPayload } from '@/lib/structuredResultParsers'
import { buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import { buildMarkdownDownloadFilename, resolvePreferredDownloadBaseName } from '@/lib/testCaseExportName'
import {
  buildExecutionLogCopy,
  buildGenericWorkbenchCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildWorkbenchHeaderCopy,
  buildRunStateValue,
  compactRailSections,
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
import TestDataPreparationResult from './TestDataPreparationResult'

interface Props {
  id: string
  label: string
  icon: string
  caption: string
}

export default function GenericModulePage({ id, label, icon }: Props) {
  const sessionKey = `generic:${id}`
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
  const collaborationRailCollapsed = useAppStore((state) => state.collaborationRailCollapsed)
  const session = resolveModuleSession(moduleSessions[sessionKey], {
    runStatus: 'idle',
    activeTab: 'result',
    options: {},
  })

  const requirement = session.requirement
  const [files, setFiles] = useState<File[]>([])
  const runStage = session.runStatus
  const result = session.result
  const error = session.error
  const activeTab = session.activeTab as GenericModuleTab
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const persistedDownloadBaseName = session.downloadBaseName
  const isTestDataModule = id === 'test-data'
  const isStructuredModule = isTestDataModule
  const requirementPlaceholder = isTestDataModule
    ? '例如：直播场景 SQL / 商品表数据'
    : '描述要处理的内容'
  const uploadLabel = isTestDataModule ? '上传技术文档' : '上传附件'
  const runButtonLabel = isTestDataModule ? '生成测试数据 SQL' : '立即开始'
  const testDataPayload = isTestDataModule && result ? parseTestDataPayload(result) : null
  const testDataBaseName = (() => {
    const sourceName = (testDataPayload?.documentName || '测试数据准备').trim()
    const basename = sourceName.split(/[\\/]/).pop() || '测试数据准备'
    return basename.replace(/\.[^.]+$/, '') || '测试数据准备'
  })()
  const exportMarkdown = isTestDataModule
    ? testDataPayload?.markdown || result || ''
    : result || ''
  const isRunning = !['idle', 'done', 'error'].includes(runStage)

  const taskSummary = useMemo(
    () =>
      buildTaskWorkbenchSummary({
        moduleSessions,
        reviewFindings,
        requirementContextId,
      }),
    [moduleSessions, requirementContextId, reviewFindings]
  )
  const genericCopy = buildGenericWorkbenchCopy({
    isStructured: isStructuredModule,
    hasResult: Boolean(result),
    hasContext: Boolean(requirementContextId),
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()
  const genericHeaderCopy = buildWorkbenchHeaderCopy({ module: 'generic', label })
  const genericContextHintVisible = !requirement.trim() && files.length === 0 && Boolean(taskSummary.requirement || requirementContextId)
  const genericContextHintLabel = requirementContextId ? '最近上下文' : '当前任务'
  const genericContextHintText = requirementContextId
    ? genericCopy.contextHint
    : '当前任务已有可复用内容，可点击右上角“带入任务”快速填充输入区。'
  const genericDownloadBaseName = resolvePreferredDownloadBaseName({
    persistedBaseName: persistedDownloadBaseName,
    uploadedFilename: files[0]?.name || null,
    requirement,
    sharedRequirement: taskSummary.requirement,
    fallbackName: label,
  })

  const handleRun = async () => {
    if (!requirement && files.length === 0) {
      setModuleSession(sessionKey, {
        error: '请提供相关信息或上传文件',
      })
      return
    }

    const nextDownloadBaseName = resolvePreferredDownloadBaseName({
      uploadedFilename: files[0]?.name || null,
      requirement,
      sharedRequirement: taskSummary.requirement,
      fallbackName: label,
    })

    setModuleSession(sessionKey, {
      runStatus: 'parsing',
      error: null,
      result: null,
      downloadBaseName: nextDownloadBaseName,
      activeTab: 'result',
      eventLogs: [],
    })

    try {
      const res = await apiClient.runSkillStream(
        id,
        requirement,
        files,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(sessionKey, {
              runStatus: event.stage,
            })
            appendModuleSessionEvent(sessionKey, event)
          }
        }
      )

      if (res.success) {
        setModuleSession(sessionKey, {
          result: res.result,
          runStatus: 'done',
          error: null,
        })
        captureTaskSnapshot()
        openInsight(`${label}任务已处理完成。`)
        return
      }

      setModuleSession(sessionKey, {
        runStatus: 'error',
        error: buildInlineErrorCopy('process'),
      })
    } catch (err: unknown) {
      setModuleSession(sessionKey, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('process'),
      })
    }
  }

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '模块状态',
      description: '固定展示当前专家模块的运行状态和结果状态。',
      entries: [
        {
          id: 'run',
          label: '当前阶段',
          value: buildRunStateValue({
            status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '等待开始',
            runningLabel: '处理中',
            doneLabel: '处理完成',
          }),
          detail: `当前标签页：${activeTab === 'result' ? '结果预览' : activeTab === 'log' ? '执行过程' : '历史记录'}`,
          status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'source',
          label: '输入来源',
          value: requirement ? '文本录入' : files.length > 0 ? '上传文件' : '等待输入',
          detail: files.length > 0 ? `已附加 ${files.length} 个文件` : '当前未附加文件',
          status: requirement || files.length > 0 ? 'done' : 'idle',
        },
        {
          id: 'result',
          label: '结果产物',
          value: result ? (isStructuredModule ? '已生成结构化结果' : '已生成 Markdown') : '未生成',
          detail: result ? '可复制、下载并沉淀到历史记录' : '运行完成后将在中间区域展示',
          status: result ? 'done' : 'idle',
        },
      ],
    },
    {
      id: 'signals',
      title: '任务信号',
      description: '将当前任务需求和风险联动固定在右侧。',
      entries: [
        {
          id: 'context',
          label: '任务上下文',
          value: requirementContextId ? '已联动' : '未联动',
          detail: requirementContextId ? '可保持与主任务同一条上下文链路' : '当前模块可独立执行',
          status: requirementContextId ? 'done' : 'idle',
        },
        {
          id: 'risk',
          label: '风险数量',
          value: `${reviewFindings.length} 项`,
          detail: reviewFindings.length > 0 ? '可结合评审发现继续处理当前专家模块任务' : '当前无评审发现回灌',
          status: reviewFindings.length > 0 ? 'warning' : 'idle',
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
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-2xl">
                    {icon}
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{genericHeaderCopy.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-xl font-semibold text-[var(--text-primary)]">{genericHeaderCopy.title}</h1>
                      {genericCopy.tags.map((tag, index) => (
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
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">{genericCopy.description}</p>
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
                  onClick={() => setModuleSession(sessionKey, { requirement: taskSummary.requirement })}
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

            <div className="console-kicker">需求输入</div>
            <textarea
              value={requirement}
              onChange={(event) => setModuleSession(sessionKey, { requirement: event.target.value })}
              placeholder={requirementPlaceholder}
              className="mt-3 h-64 w-full resize-none rounded-xl border p-4 text-sm outline-none transition-colors"
              style={{ borderColor: 'var(--border)' }}
            />

            {genericContextHintVisible && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  {genericContextHintLabel}
                </span>
                <span>{genericContextHintText}</span>
              </div>
            )}

            <FileUploadTrigger
              ariaLabel={uploadLabel}
              className="mt-3 rounded-xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
              primaryText={files.length > 0 ? `已选 ${files.length} 个文件` : uploadLabel}
              onFilesChange={setFiles}
            />
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
            <Sparkles className="h-4 w-4" />
            {isRunning ? '正在处理...' : runButtonLabel}
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
                  {([
                    { id: 'result', label: '结果' },
                    { id: 'log', label: '执行' },
                    { id: 'history', label: '历史' },
                  ] as { id: GenericModuleTab; label: string }[]).map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setModuleSession(sessionKey, { activeTab: tab.id })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {runStage === 'done' && result && activeTab !== 'history' && (
                  <div className={getWorkbenchResultToolbarGroupClassName('end')}>
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      <button
                        onClick={() =>
                          downloadMarkdownFile(
                            exportMarkdown,
                            isTestDataModule
                              ? `${testDataBaseName}.md`
                              : buildMarkdownDownloadFilename(genericDownloadBaseName, label)
                          )
                        }
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Download className="h-3 w-3" />
                          MD
                        </span>
                      </button>
                      {isTestDataModule && testDataPayload?.sqlFileContent && (
                        <button
                          onClick={() => downloadSqlFile(testDataPayload.sqlFileContent, `${testDataBaseName}.sql`)}
                          title="下载 SQL"
                          className={getWorkbenchResultActionClassName()}
                          style={{ borderColor: 'var(--border)' }}
                        >
                          <span className="inline-flex items-center gap-1">
                            <Download className="h-3 w-3" />
                            SQL
                          </span>
                        </button>
                      )}
                      <button
                        onClick={() => navigator.clipboard.writeText(exportMarkdown)}
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
                    types={getGenericModuleHistoryTypes(id)}
                    emptyTitle={historyEmptyCopy.title}
                    emptyDescription={historyEmptyCopy.description}
                  />
                ) : !result && !isRunning ? (
                  <div className="flex min-h-[700px] flex-col items-center justify-center rounded-2xl border border-dashed border-[color:var(--border-soft)] text-center text-[var(--text-secondary)]">
                    <div className="text-5xl">{icon}</div>
                    <p className="mt-4 text-xl font-semibold text-[var(--text-primary)]">{genericCopy.emptyTitle}</p>
                    <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{genericCopy.emptyDescription}</p>
                  </div>
                ) : isRunning || activeTab === 'log' ? (
                  <div className="console-panel-muted min-h-[700px] p-6">
                    <div className="console-kicker text-center">{eventLogCopy.title}</div>
                    <div className="mt-5">
                      <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                    </div>
                  </div>
                ) : isTestDataModule && testDataPayload ? (
                  <div className="custom-scrollbar min-h-[700px] overflow-y-auto rounded-2xl border p-5" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                    <TestDataPreparationResult payload={testDataPayload} appearance={appearance} />
                  </div>
                ) : (
                  <div className={`custom-scrollbar prose prose-base max-w-none min-h-[700px] overflow-y-auto rounded-2xl border p-6 ${appearance === 'dark' ? 'prose-invert' : ''}`} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                    <ReactMarkdown>{exportMarkdown}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        <div className={getWorkbenchRailWrapperClassName(collaborationRailCollapsed)}>
          <CollaborationRail
            title={label}
            subtitle=""
            tags={[
              { label: runStage === 'done' ? '专家产出已完成' : isRunning ? '处理中' : '待处理', tone: result ? 'success' : isRunning ? 'accent' : 'neutral' },
              { label: genericCopy.tags[1], tone: isStructuredModule ? 'accent' : 'neutral' },
              { label: requirementContextId ? '已联动上下文' : '独立执行', tone: requirementContextId ? 'accent' : 'neutral' },
            ]}
            sections={compactRailSections(collaborationSections)}
            actions={[
              {
                label: isRunning ? '进行中' : runButtonLabel,
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

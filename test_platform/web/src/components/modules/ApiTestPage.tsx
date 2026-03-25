'use client'

import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Clipboard, Download, Play, Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import ApiTestExecutionPanel from '@/components/ui/ApiTestExecutionPanel'
import ExecutionEventLog from '@/components/ui/ExecutionEventLog'
import FileUploadTrigger from '@/components/ui/FileUploadTrigger'
import HistoryReportPanel from '@/components/ui/HistoryReportPanel'
import ResultStageBanner from '@/components/ui/ResultStageBanner'
import { apiClient, type RunProgressEvent, type RunStreamEvent } from '@/lib/api'
import { buildApiTestFailureReplayPlan, buildFailedApiTestReplayPack } from '@/lib/apiTestReplay'
import { buildApiTestHistoryOverview, extractApiTestHistorySummary } from '@/lib/apiTestHistory'
import { buildApiTestCaseGroups } from '@/lib/apiTestWorkbench'
import type { ApiTestPack, HistoryReportDetail, HistoryReportSummary } from '@/lib/contracts'
import { getGenericModuleHistoryTypes } from '@/lib/genericModule'
import { downloadBlobFile, downloadMarkdownFile, downloadTextFile } from '@/lib/markdownFile'
import { resolveModuleSession } from '@/lib/moduleSession'
import { parseApiTestPayload } from '@/lib/structuredResultParsers'
import { buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import {
  buildApiTestWorkbenchCopy,
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
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

type ResultTab = 'result' | 'cases' | 'report' | 'log' | 'history'

const API_TEST_CATEGORY_LABELS: Record<string, string> = {
  auth: '鉴权',
  list: '列表',
  detail: '详情',
  create: '新增',
  update: '更新',
  delete: '删除',
  status: '状态',
  batch: '批量',
  unknown: '通用',
}

interface ApiTestModuleOptions extends Record<string, unknown> {
  execute: boolean
  baseUrl: string
  headersText: string
  cookiesText: string
  requestOverridesText: string
  scriptText: string
  historyReportId: string
  timeout: number
  verifySsl: boolean
}

const DEFAULT_API_TEST_OPTIONS: ApiTestModuleOptions = {
  execute: false,
  baseUrl: '',
  headersText: '{\n  "Authorization": ""\n}',
  cookiesText: '{\n  "userId": ""\n}',
  requestOverridesText: '{\n  "platformGoods_add_success": {\n    "title": "自动化回归商品"\n  }\n}',
  scriptText: '',
  historyReportId: '',
  timeout: 15,
  verifySsl: true,
}

function parseJsonObjectInput(value: string, fieldLabel: string): Record<string, unknown> {
  const text = value.trim()
  if (!text) {
    return {}
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error(`${fieldLabel} 必须是合法的 JSON 对象`)
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${fieldLabel} 必须是 JSON 对象`)
  }

  return parsed as Record<string, unknown>
}

function extractApiTestReplayPayload(report: HistoryReportDetail): ApiTestPack | null {
  const meta = report.meta
  if (!meta || typeof meta !== 'object') {
    return null
  }

  const packPayload = (meta as Record<string, unknown>).pack_payload
  if (!packPayload || typeof packPayload !== 'object' || Array.isArray(packPayload)) {
    return null
  }

  const candidate = packPayload as ApiTestPack
  if (!candidate.spec || !Array.isArray(candidate.cases) || !Array.isArray(candidate.scenes)) {
    return null
  }

  return {
    ...candidate,
    markdown: report.content,
  }
}

function buildApiTestPayloadFilenameBase(payload?: ApiTestPack | null): string {
  const sourceName = String(payload?.spec?.title || '接口测试').trim()
  const basename = sourceName.split(/[\\/]/).pop() || '接口测试'
  return basename.replace(/\.[^.]+$/, '').trim() || '接口测试'
}

function buildApiTestHistoryFilenameBase(report: HistoryReportDetail): string {
  const sourceName = String(report.filename || '接口测试').trim()
  const basename = sourceName.split(/[\\/]/).pop() || '接口测试'
  return basename.replace(/\.[^.]+$/, '').trim() || '接口测试'
}

function buildJsonDownloadContent(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2)
}

function resolveApiTestDownloadContent(rawContent: string | undefined, fallbackValue: unknown): string {
  const text = String(rawContent || '').trim()
  return text || buildJsonDownloadContent(fallbackValue)
}

function MetricCard({ label, value, meta }: { label: string; value: string; meta?: string }) {
  return (
    <div
      className="rounded-2xl border p-4"
      style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
    >
      <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">{label}</div>
      <div className="mt-3 text-lg font-semibold text-[var(--text-primary)]">{value}</div>
      {meta ? <div className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{meta}</div> : null}
    </div>
  )
}

function EmptyResultState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center py-16 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
        <Play className="h-7 w-7" />
      </div>
      <p className="mt-5 text-xl font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{description}</p>
    </div>
  )
}

function resolveApiTestPriorityClassName(priority?: string): string {
  if (priority === 'P0') {
    return 'border-rose-500/20 bg-rose-500/10 text-rose-600'
  }
  if (priority === 'P1') {
    return 'border-amber-500/20 bg-amber-500/10 text-amber-700'
  }
  if (priority === 'P2') {
    return 'border-sky-500/20 bg-sky-500/10 text-sky-700'
  }
  return 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
}

function resolveApiTestCategoryLabel(category?: string): string {
  return API_TEST_CATEGORY_LABELS[String(category || '').trim().toLowerCase()] || '通用'
}

function ApiTestCaseCard({ item }: { item: ApiTestPack['cases'][number] }) {
  return (
    <div
      className="rounded-xl border p-3"
      style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${resolveApiTestPriorityClassName(item.priority)}`}
            >
              {item.priority}
            </span>
            <span className="rounded-full border border-[color:var(--border-soft)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
              {resolveApiTestCategoryLabel(item.category)}
            </span>
            {item.resource_key && (
              <span className="rounded-full border border-[color:var(--border-soft)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                {item.resource_key}
              </span>
            )}
          </div>
          <div className="mt-2 text-sm font-medium text-[var(--text-primary)]">{item.title}</div>
        </div>
        <div className="font-mono text-[11px] text-[var(--text-secondary)]">{item.case_id}</div>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-[var(--text-secondary)] md:grid-cols-2">
        <div>
          <div className="text-[11px] text-[var(--text-muted)]">关联接口</div>
          <div className="mt-1 font-mono text-[var(--text-primary)]">{item.operation_id}</div>
        </div>
        <div>
          <div className="text-[11px] text-[var(--text-muted)]">依赖</div>
          <div className="mt-1">{item.depends_on.length > 0 ? item.depends_on.join(' / ') : '无前置依赖'}</div>
        </div>
      </div>

      {(item.extract?.length || item.assertions?.length) ? (
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--text-secondary)]">
          {(item.extract || []).map((rule, index) => (
            <span
              key={`${item.case_id}-extract-${index}`}
              className="rounded-full border border-[color:var(--border-soft)] px-2.5 py-1"
              style={{ backgroundColor: 'var(--surface-panel-muted)' }}
            >
              提取 {rule.name || rule.pick}
            </span>
          ))}
          {(item.assertions || []).slice(0, 3).map((assertion, index) => (
            <span
              key={`${item.case_id}-assert-${index}`}
              className="rounded-full border border-[color:var(--border-soft)] px-2.5 py-1"
              style={{ backgroundColor: 'var(--surface-panel-muted)' }}
            >
              断言 {assertion}
            </span>
          ))}
          {(item.assertions || []).length > 3 && (
            <span
              className="rounded-full border border-[color:var(--border-soft)] px-2.5 py-1"
              style={{ backgroundColor: 'var(--surface-panel-muted)' }}
            >
              其余 {(item.assertions || []).length - 3} 条断言
            </span>
          )}
        </div>
      ) : null}
    </div>
  )
}

export default function ApiTestPage() {
  const sessionKey = 'generic:api-test'
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
    options: DEFAULT_API_TEST_OPTIONS,
  })

  const requirement = session.requirement
  const [files, setFiles] = useState<File[]>([])
  const runStage = session.runStatus
  const result = session.result
  const error = session.error
  const activeTab = session.activeTab as ResultTab
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const apiTestOptions = session.options as ApiTestModuleOptions
  const apiTestPayload = useMemo(() => (result ? parseApiTestPayload(result) : null), [result])
  const apiTestFilenameBase = useMemo(() => buildApiTestPayloadFilenameBase(apiTestPayload), [apiTestPayload])
  const failedReplayPlan = useMemo(() => buildApiTestFailureReplayPlan(apiTestPayload), [apiTestPayload])
  const failedReplayPayload = useMemo(() => buildFailedApiTestReplayPack(apiTestPayload), [apiTestPayload])
  const apiTestCaseGroups = useMemo(() => buildApiTestCaseGroups(apiTestPayload), [apiTestPayload])
  const isRunning = !['idle', 'done', 'error'].includes(runStage)
  const hasExecution = Boolean(apiTestPayload?.execution?.status)

  const taskSummary = useMemo(
    () =>
      buildTaskWorkbenchSummary({
        moduleSessions,
        reviewFindings,
        requirementContextId,
      }),
    [moduleSessions, reviewFindings, requirementContextId]
  )
  const workbenchCopy = buildApiTestWorkbenchCopy({
    hasResult: Boolean(result),
    hasContext: Boolean(requirementContextId),
    executeAfterGenerate: Boolean(apiTestOptions.execute),
    hasExecution,
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()
  const runPresentation = resolveWorkbenchRunPresentation({
    status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
    idleStageLabel: '接口测试工作台',
    doneStageLabel: hasExecution ? '执行结果已生成' : '接口资产已生成',
    idleActionLabel: apiTestOptions.execute ? '生成并执行' : '生成资产',
    runningActionLabel: apiTestOptions.execute ? '执行中' : '生成中',
  })

  useEffect(() => {
    if (!apiTestPayload?.script) {
      return
    }
    if (apiTestOptions.scriptText === apiTestPayload.script) {
      return
    }
    setModuleSession(sessionKey, {
      options: {
        scriptText: apiTestPayload.script,
      },
    })
  }, [apiTestOptions.scriptText, apiTestPayload?.script, sessionKey, setModuleSession])

  const buildApiTestRequestParams = (overrideValues?: Record<string, unknown>): Record<string, unknown> => ({
    execute: Boolean(apiTestOptions.execute),
    base_url: apiTestOptions.baseUrl.trim(),
    headers: parseJsonObjectInput(apiTestOptions.headersText, '请求头配置'),
    cookies: parseJsonObjectInput(apiTestOptions.cookiesText, 'Cookie 配置'),
    request_overrides: parseJsonObjectInput(apiTestOptions.requestOverridesText, '请求覆盖配置'),
    timeout: Number(apiTestOptions.timeout) || 15,
    verify_ssl: Boolean(apiTestOptions.verifySsl),
    ...(overrideValues || {}),
  })

  const handleDownloadHistoryArtifact = async (
    reportId: string,
    artifactKey: string,
    fallbackFilename: string
  ) => {
    try {
      const result = await apiClient.downloadHistoryReportArtifact(reportId, artifactKey, fallbackFilename)
      downloadBlobFile(result.blob, result.filename)
    } catch (err: unknown) {
      setModuleSession(sessionKey, {
        error: err instanceof Error ? err.message : '下载执行产物失败',
      })
    }
  }

  const runApiTestReplayPayload = async (
    replayPayload: ApiTestPack,
    replayRequirement: string,
    fallbackErrorMessage: string
  ) => {
    const manualScript = String(replayPayload.script || apiTestOptions.scriptText || '').trim()
    if (!manualScript) {
      setModuleSession(sessionKey, {
        error: '当前没有可执行的接口测试脚本',
      })
      return
    }

    try {
      const requestParams = buildApiTestRequestParams({
        execute: true,
        manual_script: manualScript,
        pack_payload: {
          ...replayPayload,
          script: manualScript,
        },
      })

      setModuleSession(sessionKey, {
        result: JSON.stringify({
          ...replayPayload,
          script: manualScript,
        }),
        activeTab: 'result',
        runStatus: 'executing',
        error: null,
        eventLogs: [],
        options: {
          scriptText: manualScript,
        },
      })

      const res = await apiClient.runSkillStream(
        'api-test',
        replayRequirement,
        files,
        requestParams,
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
          options: {
            historyReportId: typeof res.meta?.history_report_id === 'string' ? res.meta.history_report_id : '',
          },
        })
        return
      }

      setModuleSession(sessionKey, {
        runStatus: 'error',
        error: buildInlineErrorCopy('process'),
      })
    } catch (err: unknown) {
      setModuleSession(sessionKey, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : fallbackErrorMessage,
      })
    }
  }

  const handleRun = async () => {
    if (!requirement && files.length === 0) {
      setModuleSession(sessionKey, {
        error: '请提供接口说明或上传 OpenAPI 文档',
      })
      return
    }

    let requestParams: Record<string, unknown>
    try {
      requestParams = buildApiTestRequestParams()
    } catch (err: unknown) {
      setModuleSession(sessionKey, {
        error: err instanceof Error ? err.message : '接口测试执行配置解析失败',
      })
      return
    }

    setModuleSession(sessionKey, {
      runStatus: 'parsing',
      error: null,
      result: null,
      activeTab: 'result',
      eventLogs: [],
    })

    try {
      const res = await apiClient.runSkillStream(
        'api-test',
        requirement,
        files,
        requestParams,
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
          options: {
            historyReportId: typeof res.meta?.history_report_id === 'string' ? res.meta.history_report_id : '',
          },
        })
        captureTaskSnapshot()
        openInsight('接口测试任务已处理完成。')
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

  const handleRunCurrentScript = async () => {
    if (!apiTestPayload) {
      setModuleSession(sessionKey, {
        error: '当前没有可复用的接口测试资产',
      })
      return
    }

    await runApiTestReplayPayload(
      {
        ...apiTestPayload,
        script: String(apiTestOptions.scriptText || apiTestPayload.script || ''),
      },
      requirement || `当前资产回放：${apiTestPayload.spec.title || '接口测试'}`,
      '运行当前脚本失败'
    )
  }

  const handleLoadApiTestHistoryReport = (report: HistoryReportDetail) => {
    const replayPayload = extractApiTestReplayPayload(report)
    if (!replayPayload) {
      setModuleSession(sessionKey, {
        error: '该历史记录不包含可恢复的接口测试资产',
      })
      return
    }

    setModuleSession(sessionKey, {
      result: JSON.stringify(replayPayload),
      activeTab: 'result',
      error: null,
      runStatus: 'done',
      options: {
        scriptText: String(replayPayload.script || ''),
        historyReportId: report.id,
      },
    })
  }

  const handleReplayApiTestHistoryReport = async (report: HistoryReportDetail) => {
    const replayPayload = extractApiTestReplayPayload(report)
    if (!replayPayload) {
      setModuleSession(sessionKey, {
        error: '该历史记录不包含可重跑的接口测试资产',
      })
      return
    }

    await runApiTestReplayPayload(
      replayPayload,
      requirement || `历史回放：${report.filename || '接口测试'}`,
      '历史脚本重跑失败'
    )
  }

  const handleReplayFailedCurrentResult = async () => {
    if (!failedReplayPayload || !apiTestPayload) {
      setModuleSession(sessionKey, {
        error: '当前结果未识别到可重跑的失败项',
      })
      return
    }

    await runApiTestReplayPayload(
      {
        ...failedReplayPayload,
        script: String(apiTestOptions.scriptText || apiTestPayload.script || ''),
      },
      requirement || `失败重跑：${apiTestPayload.spec.title || '接口测试'}`,
      '失败项重跑失败'
    )
  }

  const handleReplayFailedHistoryReport = async (report: HistoryReportDetail) => {
    const replayPayload = extractApiTestReplayPayload(report)
    const failedHistoryPayload = buildFailedApiTestReplayPack(replayPayload)
    if (!replayPayload || !failedHistoryPayload) {
      setModuleSession(sessionKey, {
        error: '该历史记录未识别到可重跑的失败项',
      })
      return
    }

    await runApiTestReplayPayload(
      failedHistoryPayload,
      requirement || `失败重跑：${report.filename || '接口测试'}`,
      '历史失败项重跑失败'
    )
  }

  const renderApiTestHistoryActions = (report: HistoryReportDetail) => {
    const replayPayload = extractApiTestReplayPayload(report)
    if (!replayPayload) {
      return null
    }

    const filenameBase = buildApiTestHistoryFilenameBase(report)
    const failedHistoryPayload = buildFailedApiTestReplayPack(replayPayload)

    return (
      <>
        {replayPayload.script && (
          <button
            onClick={() => downloadTextFile(replayPayload.script || '', `${filenameBase}_脚本.py`, 'text/x-python;charset=utf-8')}
            className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
            style={{ borderColor: 'var(--border)' }}
          >
            下载 PY
          </button>
        )}
        {replayPayload.execution?.junit_xml_content && (
          <button
            onClick={() => downloadTextFile(replayPayload.execution?.junit_xml_content || '', `${filenameBase}_报告.xml`, 'application/xml;charset=utf-8')}
            className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
            style={{ borderColor: 'var(--border)' }}
          >
            下载 XML
          </button>
        )}
        {replayPayload.execution?.execution_summary_content && (
          <button
            onClick={() => downloadTextFile(replayPayload.execution?.execution_summary_content || '', `${filenameBase}_执行摘要.json`, 'application/json;charset=utf-8')}
            className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
            style={{ borderColor: 'var(--border)' }}
          >
            下载 JSON
          </button>
        )}
        {replayPayload.execution?.artifacts?.allure_archive && (
          <button
            onClick={() => void handleDownloadHistoryArtifact(report.id, 'allure_archive', `${filenameBase}_allure-results.zip`)}
            className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
            style={{ borderColor: 'var(--border)' }}
          >
            下载 Allure
          </button>
        )}
        <button
          onClick={() => void handleReplayApiTestHistoryReport(report)}
          className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
          style={{ borderColor: 'var(--border)' }}
        >
          恢复并执行
        </button>
        {failedHistoryPayload && (
          <button
            onClick={() => void handleReplayFailedHistoryReport(report)}
            className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
            style={{ borderColor: 'var(--border)' }}
          >
            失败重跑
          </button>
        )}
      </>
    )
  }

  const renderHistorySummary = (
    report: HistoryReportDetail,
    context: { reports: HistoryReportSummary[] }
  ) => {
    const payload = extractApiTestReplayPayload(report)
    if (!payload) {
      return null
    }

    const historyOverview = buildApiTestHistoryOverview(context.reports, report.id)

    return (
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <MetricCard
            label="接口数量"
            value={String(payload.spec.operations.length)}
            meta={`资源组 ${payload.spec.resources.length} 个`}
          />
          <MetricCard
            label="结构化用例"
            value={String(payload.cases.length)}
            meta={`关联场景 ${payload.scenes.length} 个`}
          />
          <MetricCard
            label="套件版本"
            value={payload.suite?.suite_version ? `v${String(payload.suite.suite_version).padStart(3, '0')}` : '未沉淀'}
            meta={payload.suite?.suite_id || payload.report?.headline || '未记录套件摘要'}
          />
          <MetricCard
            label="最近运行数"
            value={String(historyOverview.totalRuns)}
            meta={`通过 ${historyOverview.passedRuns} 次`}
          />
          <MetricCard
            label="平均通过率"
            value={historyOverview.averagePassRateText}
            meta={historyOverview.latestStatusLabel}
          />
          <MetricCard
            label="最近通过率"
            value={historyOverview.latestPassRateText}
            meta="基于最近一次历史执行"
          />
        </div>

        {historyOverview.timeline.length > 0 && (
          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">历史趋势</div>
            <div className="mt-3 space-y-2">
              {historyOverview.timeline.map((item) => (
                <div
                  key={item.id}
                  className={`rounded-xl border px-3 py-3 ${
                    item.isSelected
                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)]'
                      : ''
                  }`}
                  style={{
                    borderColor: item.isSelected ? 'var(--accent-primary-soft)' : 'var(--border-soft)',
                    backgroundColor: item.isSelected ? 'var(--surface-accent)' : 'var(--surface-inset)',
                  }}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium text-[var(--text-primary)]">{item.timestampLabel}</div>
                    <div className="text-xs text-[var(--text-secondary)]">{item.suiteVersionText}</div>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                    <span>{item.statusLabel}</span>
                    <span>{item.passRateText}</span>
                    <span>{item.caseCountText}</span>
                    {item.isSelected && <span className="text-[var(--accent-primary)]">当前查看</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {historyOverview.selectedComparison && (
          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">执行对比</div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border p-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                <div className="text-[11px] text-[var(--text-secondary)]">当前记录</div>
                <div className="mt-2 text-sm text-[var(--text-primary)]">通过率 {historyOverview.selectedComparison.currentPassRateText}</div>
                <div className="mt-1 text-xs text-[var(--text-secondary)]">当前详情面板对应的执行快照</div>
              </div>
              <div className="rounded-xl border p-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                <div className="text-[11px] text-[var(--text-secondary)]">上次同套件</div>
                <div className="mt-2 text-sm text-[var(--text-primary)]">通过率 {historyOverview.selectedComparison.previousPassRateText}</div>
                <div className="mt-1 text-xs text-[var(--text-secondary)]">{historyOverview.selectedComparison.previousTimestampLabel}</div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
              <span className="rounded-full border px-2.5 py-1" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                通过率变化 {historyOverview.selectedComparison.passRateDeltaText}
              </span>
              <span className="rounded-full border px-2.5 py-1" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                用例变化 {historyOverview.selectedComparison.caseCountDeltaText}
              </span>
              <span className="rounded-full border px-2.5 py-1" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                场景变化 {historyOverview.selectedComparison.sceneCountDeltaText}
              </span>
            </div>
          </div>
        )}
      </div>
    )
  }

  const renderHistoryListMeta = (report: HistoryReportSummary) => {
    const summary = extractApiTestHistorySummary(report)
    if (!summary) {
      return null
    }

    return (
      <div className="flex flex-wrap gap-1.5 text-[10px] text-[var(--text-secondary)]">
        {summary.pass_rate != null && (
          <span
            className="rounded-full border px-2 py-0.5"
            style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
          >
            通过率 {summary.pass_rate.toFixed(1)}%
          </span>
        )}
        <span
          className="rounded-full border px-2 py-0.5"
          style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
        >
          用例 {summary.case_count || 0}
        </span>
        {summary.suite_version ? (
          <span
            className="rounded-full border px-2 py-0.5"
            style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
          >
            v{String(summary.suite_version).padStart(3, '0')}
          </span>
        ) : null}
      </div>
    )
  }

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '执行状态',
      description: '固定展示当前资产和执行阶段。',
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
          detail: `当前标签页：${
            activeTab === 'result'
              ? '解析结果'
              : activeTab === 'cases'
                ? '用例'
                : activeTab === 'report'
                  ? '报告'
                  : activeTab === 'log'
                    ? '执行'
                    : '历史'
          }`,
          status: runStage === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'asset',
          label: '资产状态',
          value: apiTestPayload ? '已生成' : '未生成',
          detail: apiTestPayload
            ? `接口 ${apiTestPayload.spec.operations.length} 个 / 用例 ${apiTestPayload.cases.length} 条`
            : '等待本次生成',
          status: apiTestPayload ? 'done' : 'idle',
        },
        {
          id: 'execution',
          label: '执行结果',
          value: apiTestPayload?.execution?.status || '未执行',
          detail: apiTestPayload?.report?.headline || apiTestPayload?.execution?.summary || '当前仅生成资产',
          status: apiTestPayload?.execution?.status === 'passed' ? 'done' : apiTestPayload?.execution?.status ? 'warning' : 'idle',
        },
      ],
    },
    {
      id: 'signals',
      title: '编排信号',
      description: '将上下文、套件和告警固定在右侧。',
      entries: [
        {
          id: 'context',
          label: '任务上下文',
          value: requirementContextId ? '已联动' : '未联动',
          detail: requirementContextId ? '可沿用主任务上下文继续补齐资产。' : '当前模块可独立执行。',
          status: requirementContextId ? 'done' : 'idle',
        },
        {
          id: 'suite',
          label: '套件沉淀',
          value: apiTestPayload?.suite?.suite_version ? `v${String(apiTestPayload.suite.suite_version).padStart(3, '0')}` : '未沉淀',
          detail: apiTestPayload?.suite?.suite_id || '等待首次生成后写入仓库',
          status: apiTestPayload?.suite?.suite_version ? 'done' : 'idle',
        },
        {
          id: 'warnings',
          label: '编排告警',
          value: `${apiTestPayload?.link_plan?.warnings?.length || 0} 条`,
          detail: (apiTestPayload?.link_plan?.warnings || [])[0] || '当前未发现明显编排告警',
          status: (apiTestPayload?.link_plan?.warnings?.length || 0) > 0 ? 'warning' : 'idle',
        },
      ],
    },
  ]

  const resultToolbarActions = runStage === 'done' && result && !['history', 'log'].includes(activeTab)
    ? (
      <div className={getWorkbenchResultToolbarGroupClassName('end')}>
        <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
          <button
            onClick={() => downloadMarkdownFile(apiTestPayload?.markdown || result || '', `${apiTestFilenameBase}.md`)}
            title="下载 Markdown"
            className={getWorkbenchResultActionClassName()}
            style={{ borderColor: 'var(--border)' }}
          >
            <span className="inline-flex items-center gap-1">
              <Download className="h-3 w-3" />
              MD
            </span>
          </button>
          {apiTestPayload?.script && (
            <button
              onClick={() => downloadTextFile(apiTestPayload.script || '', `${apiTestFilenameBase}_脚本.py`, 'text/x-python;charset=utf-8')}
              title="下载 Pytest 脚本"
              className={getWorkbenchResultActionClassName()}
              style={{ borderColor: 'var(--border)' }}
            >
              <span className="inline-flex items-center gap-1">
                <Download className="h-3 w-3" />
                PY
              </span>
            </button>
          )}
          {apiTestPayload?.execution?.junit_xml_content && (
            <button
              onClick={() => downloadTextFile(apiTestPayload.execution?.junit_xml_content || '', `${apiTestFilenameBase}_报告.xml`, 'application/xml;charset=utf-8')}
              title="下载 JUnit XML"
              className={getWorkbenchResultActionClassName()}
              style={{ borderColor: 'var(--border)' }}
            >
              <span className="inline-flex items-center gap-1">
                <Download className="h-3 w-3" />
                XML
              </span>
            </button>
          )}
          {apiTestPayload?.execution?.artifacts?.allure_archive && apiTestOptions.historyReportId && (
            <button
              onClick={() => void handleDownloadHistoryArtifact(apiTestOptions.historyReportId, 'allure_archive', `${apiTestFilenameBase}_allure-results.zip`)}
              title="下载 Allure 结果压缩包"
              className={getWorkbenchResultActionClassName()}
              style={{ borderColor: 'var(--border)' }}
            >
              ALLURE
            </button>
          )}
          {failedReplayPayload && (
            <button
              onClick={() => void handleReplayFailedCurrentResult()}
              title={failedReplayPlan ? `仅重跑 ${failedReplayPlan.failedCaseIds.length + failedReplayPlan.failedSceneIds.length} 个失败项` : '仅重跑失败项'}
              className={getWorkbenchResultActionClassName()}
              style={{ borderColor: 'var(--border)' }}
            >
              失败重跑
            </button>
          )}
          <button
            onClick={() => navigator.clipboard.writeText(apiTestPayload?.markdown || result || '')}
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
    )
    : null

  return (
    <div className="animate-fade-in pb-20">
      <div className={getWorkbenchStackClassName()}>
        <div className="space-y-4">
          <section className="console-panel p-5">
            <div className="mb-5 flex items-start justify-between gap-4 border-b pb-4" style={{ borderColor: 'var(--border-soft)' }}>
              <div className="min-w-0">
                <div className="flex items-start gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-2xl">
                    🔌
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">接口资产</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-xl font-semibold text-[var(--text-primary)]">接口测试工作台</h1>
                      {workbenchCopy.tags.map((tag, index) => (
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
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">{workbenchCopy.description}</p>
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

            <div className="console-kicker">接口输入</div>
            <textarea
              value={requirement}
              onChange={(event) => setModuleSession(sessionKey, { requirement: event.target.value })}
              placeholder="粘贴 OpenAPI JSON、Swagger JSON 或接口说明"
              className="mt-3 h-64 w-full resize-none rounded-xl border p-4 text-sm outline-none transition-colors"
              style={{ borderColor: 'var(--border)' }}
            />

            {workbenchCopy.contextHint && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  上下文
                </span>
                <span>{workbenchCopy.contextHint}</span>
              </div>
            )}

            <div
              className="mt-4 rounded-2xl border p-4"
              style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
            >
              <div className="console-kicker">执行配置</div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="space-y-2 text-sm text-[var(--text-secondary)]">
                  <span className="block text-[var(--text-primary)]">基础地址</span>
                  <input
                    value={apiTestOptions.baseUrl}
                    onChange={(event) => setModuleSession(sessionKey, { options: { baseUrl: event.target.value } })}
                    placeholder="可留空，默认使用 OpenAPI servers[0].url"
                    className="w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                </label>
                <label className="space-y-2 text-sm text-[var(--text-secondary)]">
                  <span className="block text-[var(--text-primary)]">超时时间（秒）</span>
                  <input
                    type="number"
                    min={1}
                    value={String(apiTestOptions.timeout)}
                    onChange={(event) => setModuleSession(sessionKey, { options: { timeout: Number(event.target.value) || 15 } })}
                    className="w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                </label>
                <label className="space-y-2 text-sm text-[var(--text-secondary)]">
                  <span className="block text-[var(--text-primary)]">请求头 JSON</span>
                  <textarea
                    value={apiTestOptions.headersText}
                    onChange={(event) => setModuleSession(sessionKey, { options: { headersText: event.target.value } })}
                    className="h-36 w-full resize-none rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                </label>
                <label className="space-y-2 text-sm text-[var(--text-secondary)]">
                  <span className="block text-[var(--text-primary)]">Cookie JSON</span>
                  <textarea
                    value={apiTestOptions.cookiesText}
                    onChange={(event) => setModuleSession(sessionKey, { options: { cookiesText: event.target.value } })}
                    className="h-36 w-full resize-none rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                </label>
                <label className="space-y-2 text-sm text-[var(--text-secondary)] md:col-span-2">
                  <span className="block text-[var(--text-primary)]">请求覆盖 JSON</span>
                  <textarea
                    value={apiTestOptions.requestOverridesText}
                    onChange={(event) => setModuleSession(sessionKey, { options: { requestOverridesText: event.target.value } })}
                    className="h-40 w-full resize-none rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors"
                    style={{ borderColor: 'var(--border)' }}
                  />
                </label>
                {apiTestPayload && (
                  <label className="space-y-2 text-sm text-[var(--text-secondary)] md:col-span-2">
                    <span className="block text-[var(--text-primary)]">脚本编辑区</span>
                    <textarea
                      value={apiTestOptions.scriptText}
                      onChange={(event) => setModuleSession(sessionKey, { options: { scriptText: event.target.value } })}
                      className="h-72 w-full resize-y rounded-xl border px-3 py-2.5 font-mono text-xs outline-none transition-colors"
                      style={{ borderColor: 'var(--border)' }}
                    />
                  </label>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-[var(--text-secondary)]">
                <label className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={apiTestOptions.execute}
                    onChange={(event) => setModuleSession(sessionKey, { options: { execute: event.target.checked } })}
                  />
                  <span>生成后立即执行</span>
                </label>
                <label className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={apiTestOptions.verifySsl}
                    onChange={(event) => setModuleSession(sessionKey, { options: { verifySsl: event.target.checked } })}
                  />
                  <span>校验 SSL 证书</span>
                </label>
                {apiTestPayload && (
                  <button
                    onClick={() => void handleRunCurrentScript()}
                    disabled={isRunning}
                    className={`rounded-xl border px-3 py-2 text-sm font-medium transition-colors ${
                      isRunning
                        ? 'cursor-not-allowed border-[color:var(--border-soft)] bg-[var(--surface-inset)] text-[var(--text-muted)]'
                        : 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] hover:border-[color:var(--border-hover)]'
                    }`}
                  >
                    运行当前脚本
                  </button>
                )}
              </div>
            </div>

            <FileUploadTrigger
              ariaLabel="上传 OpenAPI 文档"
              className="mt-3 rounded-xl border border-dashed transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
              primaryText={files.length > 0 ? `已选 ${files.length} 个文件` : '上传 OpenAPI JSON / Swagger 文件'}
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
            {isRunning ? '正在处理...' : apiTestOptions.execute ? '生成并执行接口测试' : '生成接口测试资产'}
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
                    { id: 'result', label: '解析' },
                    { id: 'cases', label: '用例' },
                    { id: 'report', label: '报告' },
                    { id: 'log', label: '执行' },
                    { id: 'history', label: '历史' },
                  ] as { id: ResultTab; label: string }[]).map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setModuleSession(sessionKey, { activeTab: tab.id })}
                      className={getWorkbenchResultTabClassName(activeTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {resultToolbarActions}
              </div>

              <div className="min-h-[680px] p-5">
                {activeTab === 'history' ? (
                  <HistoryReportPanel
                    types={getGenericModuleHistoryTypes('api-test')}
                    emptyTitle={historyEmptyCopy.title}
                    emptyDescription={historyEmptyCopy.description}
                    onLoadReport={handleLoadApiTestHistoryReport}
                    loadActionLabel="恢复资产"
                    renderListMeta={renderHistoryListMeta}
                    renderDetailActions={renderApiTestHistoryActions}
                    renderDetailContent={renderHistorySummary}
                  />
                ) : activeTab === 'log' ? (
                  <div className="space-y-4">
                    <ResultStageBanner title={runPresentation.stageLabel} meta={runPresentation.primaryActionLabel} tone={isRunning ? 'warning' : 'neutral'} />
                    <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                  </div>
                ) : runStage === 'idle' && !result ? (
                  <EmptyResultState title={workbenchCopy.emptyTitle} description={workbenchCopy.emptyDescription} />
                ) : isRunning ? (
                  <div className="flex h-full flex-col items-center justify-center py-10">
                    <div className="w-full max-w-3xl space-y-6">
                      <p className="text-center text-xl font-semibold tracking-tight text-[var(--text-primary)]">正在整理接口测试资产...</p>
                      <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                        <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                        <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                      </div>
                    </div>
                  </div>
                ) : runStage === 'done' && apiTestPayload ? (
                  activeTab === 'cases' ? (
                    <div className="animate-fade-in space-y-5">
                      <ResultStageBanner
                        title="结构化用例视图"
                        meta={`${apiTestPayload.cases.length} 条用例 · ${apiTestCaseGroups.sceneGroups.length} 个关联场景`}
                        tone="success"
                      />

                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <MetricCard
                          label="结构化用例"
                          value={String(apiTestPayload.cases.length)}
                          meta={`独立用例 ${apiTestCaseGroups.standaloneCases.length} 条`}
                        />
                        <MetricCard
                          label="关联场景"
                          value={String(apiTestCaseGroups.sceneGroups.length)}
                          meta={`场景定义 ${apiTestPayload.scenes.length} 个`}
                        />
                        <MetricCard
                          label="执行顺序"
                          value={String(apiTestCaseGroups.orderedCases.length)}
                          meta={(apiTestPayload.link_plan?.ordered_case_ids || []).slice(0, 2).join(' / ') || '按用例原始顺序展示'}
                        />
                        <MetricCard
                          label="提取规则"
                          value={String(apiTestPayload.cases.reduce((total, item) => total + (item.extract?.length || 0), 0))}
                          meta={`断言 ${(apiTestPayload.cases || []).reduce((total, item) => total + (item.assertions?.length || 0), 0)} 条`}
                        />
                      </div>

                      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
                        <div className="space-y-4">
                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">场景编排</div>
                            {apiTestCaseGroups.sceneGroups.length > 0 ? (
                              <div className="mt-3 space-y-3">
                                {apiTestCaseGroups.sceneGroups.map((group) => (
                                  <div
                                    key={group.scene.scene_id}
                                    className="rounded-xl border p-3"
                                    style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <div className="text-sm font-medium text-[var(--text-primary)]">{group.scene.title}</div>
                                      <div className="font-mono text-[11px] text-[var(--text-secondary)]">{group.scene.scene_id}</div>
                                    </div>
                                    {group.scene.description && (
                                      <div className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{group.scene.description}</div>
                                    )}
                                    <div className="mt-3 space-y-2">
                                      {group.cases.map((item) => (
                                        <ApiTestCaseCard key={item.case_id} item={item} />
                                      ))}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="mt-3 text-sm text-[var(--text-secondary)]">当前没有识别到需要串联的关联场景。</div>
                            )}
                          </div>

                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">独立用例</div>
                            {apiTestCaseGroups.standaloneCases.length > 0 ? (
                              <div className="mt-3 space-y-2">
                                {apiTestCaseGroups.standaloneCases.map((item) => (
                                  <ApiTestCaseCard key={item.case_id} item={item} />
                                ))}
                              </div>
                            ) : (
                              <div className="mt-3 text-sm text-[var(--text-secondary)]">当前全部用例都已纳入场景链路。</div>
                            )}
                          </div>
                        </div>

                        <div className="space-y-4">
                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">执行顺序总览</div>
                            <div className="mt-3 space-y-2">
                              {apiTestCaseGroups.orderedCases.map((item, index) => (
                                <div
                                  key={`${item.case_id}-${index}`}
                                  className="rounded-xl border px-3 py-2.5"
                                  style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                                >
                                  <div className="flex items-center justify-between gap-3">
                                    <div className="text-sm text-[var(--text-primary)]">{item.title}</div>
                                    <div className="font-mono text-[11px] text-[var(--text-secondary)]">#{String(index + 1).padStart(2, '0')}</div>
                                  </div>
                                  <div className="mt-1 text-xs text-[var(--text-secondary)]">
                                    {item.case_id} · {resolveApiTestCategoryLabel(item.category)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {(apiTestPayload.link_plan?.warnings || []).length > 0 && (
                            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">
                              <div className="text-[11px] font-semibold tracking-[0.16em] text-amber-700 uppercase">编排告警</div>
                              <div className="mt-3 space-y-2 text-xs leading-6 text-amber-700">
                                {(apiTestPayload.link_plan?.warnings || []).map((warning, index) => (
                                  <div key={`${warning}-${index}`}>{warning}</div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : activeTab === 'report' ? (
                    <div className="animate-fade-in space-y-5">
                      <ResultStageBanner
                        title={apiTestPayload.report?.headline || (apiTestPayload.execution?.status ? '接口测试执行报告' : '接口测试报告')}
                        meta={apiTestPayload.execution?.summary || apiTestPayload.summary}
                        tone={apiTestPayload.execution?.status === 'failed' ? 'warning' : 'success'}
                      />

                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <MetricCard
                          label="执行状态"
                          value={apiTestPayload.execution?.status || apiTestPayload.report?.status || '未执行'}
                          meta={apiTestPayload.report?.headline || '等待执行后生成报告'}
                        />
                        <MetricCard
                          label="通过率"
                          value={
                            apiTestPayload.execution?.stats?.total
                              ? `${((apiTestPayload.execution.stats.passed / apiTestPayload.execution.stats.total) * 100).toFixed(1)}%`
                              : '未记录'
                          }
                          meta={apiTestPayload.execution?.summary || '当前没有执行统计'}
                        />
                        <MetricCard
                          label="失败项"
                          value={String(apiTestPayload.report?.failure_cases?.length || 0)}
                          meta={`错误 ${apiTestPayload.execution?.stats?.errors || 0} 条`}
                        />
                        <MetricCard
                          label="报告产物"
                          value={String(apiTestPayload.report?.artifact_labels?.length || 0)}
                          meta="包含 JUnit、摘要和 Allure 等结果"
                        />
                      </div>

                      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
                        <div className="space-y-4">
                          {apiTestPayload.execution?.status ? (
                            <ApiTestExecutionPanel execution={apiTestPayload.execution} />
                          ) : (
                            <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                              <div className="text-sm text-[var(--text-secondary)]">当前只生成了接口测试资产，尚未触发执行。</div>
                            </div>
                          )}

                          {(apiTestPayload.report?.summary_lines || []).length > 0 && (
                            <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                              <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">报告摘要</div>
                              <div className="mt-3 space-y-2 text-sm leading-7 text-[var(--text-secondary)]">
                                {(apiTestPayload.report?.summary_lines || []).map((line, index) => (
                                  <div key={`${line}-${index}`}>- {line}</div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="space-y-4">
                          {(apiTestPayload.report?.artifact_labels || []).length > 0 && (
                            <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                              <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">报告产物</div>
                              <div className="mt-3 space-y-2">
                                {(apiTestPayload.report?.artifact_labels || []).map((artifact) => (
                                  <div
                                    key={artifact.key}
                                    className="rounded-xl border px-3 py-2.5"
                                    style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                                  >
                                    <div className="text-[11px] text-[var(--text-secondary)]">{artifact.label}</div>
                                    <div className="mt-1 break-all font-mono text-xs leading-6 text-[var(--text-primary)]">{artifact.value}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {(apiTestPayload.report?.failure_cases || []).length > 0 && (
                            <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                              <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">报告失败项</div>
                              <div className="mt-3 space-y-2">
                                {(apiTestPayload.report?.failure_cases || []).map((item) => (
                                  <div
                                    key={item.key}
                                    className="rounded-xl border px-3 py-2.5"
                                    style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                                  >
                                    <div className="flex items-center gap-2">
                                      <span className="rounded-full border border-rose-500/20 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-600">
                                        {item.kind === 'error' ? '异常' : '失败'}
                                      </span>
                                      <span className="text-sm text-[var(--text-primary)]">{item.title}</span>
                                    </div>
                                    <div className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{item.detail}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="animate-fade-in space-y-5">
                      <ResultStageBanner
                        title={apiTestPayload.report?.headline || (apiTestPayload.execution?.status ? '接口测试已执行' : '接口测试资产已生成')}
                        meta={apiTestPayload.summary}
                        tone={apiTestPayload.execution?.status === 'failed' ? 'warning' : 'success'}
                      />

                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <MetricCard
                          label="接口总数"
                          value={String(apiTestPayload.spec.operations.length)}
                          meta={`资源组 ${apiTestPayload.spec.resources.length} 个`}
                        />
                        <MetricCard
                          label="结构化用例"
                          value={String(apiTestPayload.cases.length)}
                          meta={`关联场景 ${apiTestPayload.scenes.length} 个`}
                        />
                        <MetricCard
                          label="服务地址"
                          value={String(apiTestPayload.spec.servers.length)}
                          meta={apiTestPayload.spec.servers[0]?.url || '未声明 servers[0].url'}
                        />
                        <MetricCard
                          label="套件版本"
                          value={apiTestPayload.suite?.suite_version ? `v${String(apiTestPayload.suite.suite_version).padStart(3, '0')}` : '未沉淀'}
                          meta={apiTestPayload.suite?.suite_id || '等待首次沉淀'}
                        />
                      </div>

                      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
                        <div className="space-y-4">
                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">资产概览</div>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <div className="rounded-xl border p-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                                <div className="text-[11px] text-[var(--text-secondary)]">文档</div>
                                <div className="mt-1 text-sm font-medium text-[var(--text-primary)]">{apiTestPayload.spec.title}</div>
                                <div className="mt-2 text-xs text-[var(--text-secondary)]">
                                  OpenAPI {apiTestPayload.spec.openapi_version || '未知'} / 版本 {apiTestPayload.spec.version || '未标注'}
                                </div>
                              </div>
                              <div className="rounded-xl border p-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}>
                                <div className="text-[11px] text-[var(--text-secondary)]">鉴权信息</div>
                                <div className="mt-1 text-sm font-medium text-[var(--text-primary)]">
                                  Header {apiTestPayload.spec.auth_profile.required_headers.length} / Cookie {apiTestPayload.spec.auth_profile.required_cookies.length}
                                </div>
                                <div className="mt-2 text-xs text-[var(--text-secondary)]">
                                  {apiTestPayload.spec.auth_profile.required_headers.join(' / ') || '当前未声明必填 Header'}
                                </div>
                              </div>
                            </div>
                          </div>

                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">资源组</div>
                            {apiTestPayload.spec.resources.length > 0 ? (
                              <div className="mt-3 space-y-2">
                                {apiTestPayload.spec.resources.map((resource) => (
                                  <div
                                    key={resource.resource_key}
                                    className="rounded-xl border px-3 py-2.5"
                                    style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <div className="text-sm font-medium text-[var(--text-primary)]">{resource.resource_key}</div>
                                      <div className="text-[11px] text-[var(--text-secondary)]">{resource.tag || '未标注 tag'}</div>
                                    </div>
                                    <div className="mt-2 text-xs text-[var(--text-secondary)]">
                                      回查字段：{resource.lookup_fields.join(' / ') || '未声明'} · 关联接口 {resource.operation_ids.length} 个
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="mt-3 text-sm text-[var(--text-secondary)]">当前规范还没有识别到可沉淀的资源组。</div>
                            )}
                          </div>
                        </div>

                        <div className="space-y-4">
                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">接口清单</div>
                            <div className="mt-3 space-y-2">
                              {apiTestPayload.spec.operations.slice(0, 12).map((operation) => (
                                <div
                                  key={operation.operation_id}
                                  className="rounded-xl border px-3 py-2.5"
                                  style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                                >
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="rounded-full border border-[color:var(--border-soft)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                                      {resolveApiTestCategoryLabel(operation.category)}
                                    </span>
                                    {operation.resource_key && (
                                      <span className="rounded-full border border-[color:var(--border-soft)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                                        {operation.resource_key}
                                      </span>
                                    )}
                                  </div>
                                  <div className="mt-2 text-sm text-[var(--text-primary)]">{operation.summary || operation.operation_id}</div>
                                  <div className="mt-1 font-mono text-[11px] text-[var(--text-secondary)]">{operation.operation_id}</div>
                                </div>
                              ))}
                            </div>
                            {apiTestPayload.spec.operations.length > 12 && (
                              <div className="mt-3 text-xs text-[var(--text-secondary)]">
                                其余 {apiTestPayload.spec.operations.length - 12} 个接口已省略，可在生成的 Markdown 中查看完整清单。
                              </div>
                            )}
                          </div>

                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">关联编排</div>
                            <div className="mt-3 text-sm text-[var(--text-primary)]">
                              {(apiTestPayload.link_plan?.ordered_case_ids || []).length > 0
                                ? apiTestPayload.link_plan?.ordered_case_ids?.join(' → ')
                                : '当前没有可展示的执行顺序'}
                            </div>
                            {(apiTestPayload.link_plan?.warnings || []).length > 0 && (
                              <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-3 text-xs text-amber-700">
                                {(apiTestPayload.link_plan?.warnings || []).map((warning, index) => (
                                  <div key={`${warning}-${index}`}>{warning}</div>
                                ))}
                              </div>
                            )}
                          </div>

                          <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                            <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">套件沉淀</div>
                            <div className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
                              <div>套件 ID：{apiTestPayload.suite?.suite_id || '未沉淀'}</div>
                              <div>版本：{apiTestPayload.suite?.suite_version ? `v${String(apiTestPayload.suite.suite_version).padStart(3, '0')}` : '未生成版本'}</div>
                              <div>路径：{apiTestPayload.suite?.storage_path || '未记录'}</div>
                            </div>
                          </div>

                          <details
                            open
                            className="rounded-2xl border"
                            style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
                          >
                            <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
                              资产 Markdown
                            </summary>
                            <div className="border-t px-4 py-4" style={{ borderColor: 'var(--border-soft)' }}>
                              <div className={`prose prose-sm max-w-none ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                                <ReactMarkdown>{apiTestPayload.markdown || result || ''}</ReactMarkdown>
                              </div>
                            </div>
                          </details>
                        </div>
                      </div>
                    </div>
                  )
                ) : runStage === 'done' && result ? (
                  <div className="animate-fade-in">
                    <ResultStageBanner title="接口测试结果已生成" meta="当前结果未能解析为结构化接口资产，以下展示原始输出。" tone="warning" />
                    <div className={`prose prose-sm max-w-none ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                      <ReactMarkdown>{result}</ReactMarkdown>
                    </div>
                  </div>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
                      <AlertTriangle className="h-7 w-7" />
                    </div>
                    <p className="mt-5 text-lg font-medium text-red-500">接口测试执行失败</p>
                    <p className="mt-2 text-sm text-[var(--text-secondary)]">{error}</p>
                    <button
                      type="button"
                      onClick={() => void handleRun()}
                      className="mt-6 rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-4 py-2 text-sm font-medium text-[var(--accent-primary)]"
                    >
                      重新执行
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        <div className={getWorkbenchRailWrapperClassName(collaborationRailCollapsed)}>
          <CollaborationRail
            title="接口测试"
            subtitle=""
            tags={[
              { label: runPresentation.stageLabel, tone: 'accent' },
              { label: apiTestOptions.execute ? '生成并执行' : '仅生成资产', tone: 'neutral' },
              { label: apiTestPayload ? '已有结果' : '待生成', tone: apiTestPayload ? 'success' : 'neutral' },
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
              {
                label: '去工作台',
                onClick: () => setActiveNav('dashboard'),
              },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

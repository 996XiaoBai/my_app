'use client'

import { useMemo, useState } from 'react'
import { AlertTriangle, Bot, Clipboard, Download, FileCode2, Play } from 'lucide-react'
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
import { buildMarkdownDownloadFilename, resolvePreferredDownloadBaseName } from '@/lib/testCaseExportName'
import {
  buildExecutionLogCopy,
  buildHistoryEmptyCopy,
  buildInlineErrorCopy,
  buildLogEmptyCopy,
  buildProgressStepLabelMap,
  buildResultFailureCopy,
  buildUiAutoWorkbenchCopy,
  buildWorkbenchHeaderCopy,
  buildRunStateValue,
  compactRailSections,
  resolveWorkbenchRunPresentation,
} from '@/lib/workbenchPresentation'
import { buildTestCaseSessionFromUIAuto } from '@/lib/uiAutoToTestCase'
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

type TaskType = 'test-cases' | 'auto-script' | 'page-objects' | 'assertions'
type Framework = 'playwright' | 'cypress' | 'selenium'
type Coverage = 'smoke' | 'core' | 'full'
type RunStatus = 'idle' | 'parsing' | 'extracting' | 'generating_script' | 'organizing' | 'done' | 'error'
type ResultTab = 'result' | 'log' | 'history'

const TASK_TYPES: { id: TaskType; label: string; actionLabel: string }[] = [
  { id: 'test-cases', label: '生成测试用例', actionLabel: '生成用例' },
  { id: 'auto-script', label: '生成自动化脚本', actionLabel: '生成脚本' },
  { id: 'page-objects', label: '提取页面对象', actionLabel: '提取对象' },
  { id: 'assertions', label: '生成断言', actionLabel: '生成断言' },
]

const FRAMEWORKS: { id: Framework; label: string }[] = [
  { id: 'playwright', label: 'Playwright' },
  { id: 'cypress', label: 'Cypress' },
  { id: 'selenium', label: 'Selenium' },
]

const COVERAGES: { id: Coverage; label: string; desc: string }[] = [
  { id: 'smoke', label: '冒烟覆盖', desc: '主流程' },
  { id: 'core', label: '核心流程', desc: '主要场景' },
  { id: 'full', label: '全量覆盖', desc: '全路径' },
]
const UI_AUTO_HEADER_COPY = buildWorkbenchHeaderCopy({ module: 'ui-auto' })
const UI_AUTO_PROGRESS_LABELS = buildProgressStepLabelMap('ui-auto')

const STATUS_STEPS: { status: RunStatus; label: string }[] = [
  { status: 'parsing', label: UI_AUTO_PROGRESS_LABELS.parsing },
  { status: 'extracting', label: UI_AUTO_PROGRESS_LABELS.extracting },
  { status: 'generating_script', label: UI_AUTO_PROGRESS_LABELS.generating_script },
  { status: 'organizing', label: UI_AUTO_PROGRESS_LABELS.organizing },
  { status: 'done', label: UI_AUTO_PROGRESS_LABELS.done },
]

const UI_AUTO_SESSION_KEY = 'ui-auto'
const TEST_CASE_SESSION_KEY = 'test-case'

const EXAMPLE_TEMPLATES: Record<TaskType, string> = {
  'test-cases': `页面：用户登录页面

功能描述：
- 用户可通过手机号 + 密码登录系统
- 支持"记住密码"开关
- 连续 5 次失败锁定账户 15 分钟
- 登录成功跳转至工作台首页

前置条件：
- 测试账号：test@qa.com / 密码：Test@1234
`,
  'auto-script': `页面：商品搜索页面

操作流程：
1. 在搜索框输入关键词"蓝牙耳机"
2. 点击搜索按钮
3. 在结果列表中选择第一个商品
4. 点击"加入购物车"
5. 验证购物车数量 +1

框架选择：Playwright
`,
  'page-objects': `页面 URL：https://example.com/login

需要提取的元素：
- 用户名输入框
- 密码输入框
- 登录按钮
- 错误提示区域
- 记住密码复选框
`,
  'assertions': `测试场景：用户登录成功

执行结果：
- 页面跳转至 /dashboard
- 顶部显示用户名"张三"
- Toast 提示"登录成功"
- Cookie 中存在 auth_token

请生成对应断言代码（Playwright 风格）
`,
}

function mapRunStage(stage: string): RunStatus {
  switch (stage) {
    case 'parsing':
      return 'parsing'
    case 'extracting':
      return 'extracting'
    case 'generating_script':
    case 'generating':
      return 'generating_script'
    case 'organizing':
      return 'organizing'
    default:
      return 'parsing'
  }
}

function ProgressTimeline({ currentStatus }: { currentStatus: RunStatus }) {
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

function EmptyResultState({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="py-6">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
          <Bot className="h-7 w-7" />
        </div>
        <p className="mt-5 text-xl font-semibold text-[var(--text-primary)]">{title}</p>
        <p className="mt-2 max-w-md text-sm leading-7 text-[var(--text-secondary)]">{description}</p>
      </div>
    </div>
  )
}

export default function UIAutoPage() {
  const {
    openInsight,
    setActiveNav,
    moduleSessions,
    setModuleSession,
    appendModuleSessionEvent,
    reviewFindings,
    requirementContextId,
    captureTaskSnapshot,
    appearance,
  } = useAppStore()
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)
  const session = resolveModuleSession(moduleSessions[UI_AUTO_SESSION_KEY], {
    runStatus: 'idle',
    activeTab: 'result',
    options: {
      taskType: 'test-cases',
      framework: 'playwright',
      coverage: 'core',
      includeEdge: true,
      includeAssert: true,
      configExpanded: false,
    },
  })
  const sessionOptions = session.options as {
    taskType?: TaskType
    framework?: Framework
    coverage?: Coverage
    includeEdge?: boolean
    includeAssert?: boolean
    configExpanded?: boolean
  }

  const taskType = sessionOptions.taskType || 'test-cases'
  const description = session.requirement
  const [files, setFiles] = useState<File[]>([])
  const framework = sessionOptions.framework || 'playwright'
  const coverage = sessionOptions.coverage || 'core'
  const includeEdge = typeof sessionOptions.includeEdge === 'boolean' ? sessionOptions.includeEdge : true
  const includeAssert = typeof sessionOptions.includeAssert === 'boolean' ? sessionOptions.includeAssert : true
  const configExpanded = typeof sessionOptions.configExpanded === 'boolean' ? sessionOptions.configExpanded : false

  const runStatus = session.runStatus as RunStatus
  const result = session.result
  const error = session.error
  const resultTab = session.activeTab as ResultTab
  const eventLogs = session.eventLogs as RunProgressEvent[]
  const persistedDownloadBaseName = session.downloadBaseName

  const [isDragging, setIsDragging] = useState(false)
  const currentTask = TASK_TYPES.find((item) => item.id === taskType) || TASK_TYPES[0]
  const downloadBaseName = resolvePreferredDownloadBaseName({
    persistedBaseName: persistedDownloadBaseName,
    uploadedFilename: files[0]?.name || null,
    requirement: description,
    sharedRequirement: '',
    fallbackName: 'UI自动化',
  })

  const handleRun = async () => {
    if (!description && files.length === 0) {
      setModuleSession(UI_AUTO_SESSION_KEY, {
        error: '请填写业务描述或上传相关文档',
      })
      return
    }
    const nextDownloadBaseName = resolvePreferredDownloadBaseName({
      uploadedFilename: files[0]?.name || null,
      requirement: description,
      sharedRequirement: '',
      fallbackName: 'UI自动化',
    })
    setModuleSession(UI_AUTO_SESSION_KEY, {
      runStatus: 'parsing',
      error: null,
      result: null,
      downloadBaseName: nextDownloadBaseName,
      activeTab: 'result',
      eventLogs: [],
    })

    const params = {
      task_type: taskType,
      framework,
      coverage,
      include_edge: includeEdge,
      include_assertion: includeAssert,
    }

    try {
      const res = await apiClient.runSkillStream(
        'ui-auto',
        description,
        files,
        params,
        undefined,
        undefined,
        undefined,
        undefined,
        (event: RunStreamEvent) => {
          if (event.type === 'progress') {
            setModuleSession(UI_AUTO_SESSION_KEY, {
              runStatus: mapRunStage(event.stage),
            })
            appendModuleSessionEvent(UI_AUTO_SESSION_KEY, event)
          }
        }
      )
      if (res.success) {
        setModuleSession(UI_AUTO_SESSION_KEY, {
          result: res.result,
          runStatus: 'done',
          error: null,
        })
        captureTaskSnapshot()
        openInsight('UI 自动化任务已完成，可在结果区复制或导出。')
      } else {
        throw new Error(buildInlineErrorCopy('process'))
      }
    } catch (err: unknown) {
      setModuleSession(UI_AUTO_SESSION_KEY, {
        runStatus: 'error',
        error: err instanceof Error ? err.message : buildInlineErrorCopy('generate'),
      })
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const dropped = Array.from(e.dataTransfer.files)
    setFiles((prev) => [...prev, ...dropped])
  }

  const goToTestCases = () => {
    if (!result) {
      return
    }

    setModuleSession(
      TEST_CASE_SESSION_KEY,
      buildTestCaseSessionFromUIAuto({
        requirement: description,
        result,
      })
    )
    setActiveNav('test-cases')
    openInsight('UI 自动化生成结果已写入测试用例页。')
  }

  const copyToClipboard = () => {
    if (result) {
      navigator.clipboard.writeText(result)
      openInsight('已复制到剪贴板')
    }
  }

  const exportMarkdown = () => {
    if (!result) return
    downloadMarkdownFile(result, buildMarkdownDownloadFilename(downloadBaseName, `UI自动化_${currentTask.label}`))
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
  const automationCopy = buildUiAutoWorkbenchCopy({
    taskLabel: currentTask.label,
    frameworkLabel: FRAMEWORKS.find((item) => item.id === framework)?.label || framework,
    hasResult: Boolean(result),
    hasContext: Boolean(requirementContextId),
  })
  const historyEmptyCopy = buildHistoryEmptyCopy()
  const logEmptyCopy = buildLogEmptyCopy()
  const eventLogCopy = buildExecutionLogCopy()
  const failureCopy = buildResultFailureCopy()
  const selectedCoverageLabel = COVERAGES.find((item) => item.id === coverage)?.label || coverage
  const runPresentation = resolveWorkbenchRunPresentation({
    status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
    idleStageLabel: '自动化产出',
    doneStageLabel: '自动化产出已生成',
    idleActionLabel: currentTask.actionLabel,
    runningActionLabel: '生成中',
  })

  const collaborationSections: RailSection[] = [
    {
      id: 'status',
      title: '生成状态',
      description: '固定展示自动化生成阶段、产物类型与结果规模。',
      entries: [
        {
          id: 'run',
          label: '当前阶段',
          value: buildRunStateValue({
            status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'error' : 'idle',
            idleLabel: '等待开始生成',
            runningLabel: STATUS_STEPS.find((step) => step.status === runStatus)?.label || '生成中',
            doneLabel: UI_AUTO_PROGRESS_LABELS.done,
          }),
          detail: `当前标签页：${resultTab === 'result' ? '结果预览' : resultTab === 'log' ? '执行过程' : '历史记录'}`,
          status: runStatus === 'done' ? 'done' : isRunning ? 'running' : error ? 'warning' : 'idle',
        },
        {
          id: 'task',
          label: '当前任务',
          value: currentTask.label,
          detail: `框架：${FRAMEWORKS.find((item) => item.id === framework)?.label || framework} · 覆盖：${COVERAGES.find((item) => item.id === coverage)?.label || coverage}`,
          status: 'idle',
        },
        {
          id: 'result',
          label: '结果输出',
          value: result ? '已生成' : '未生成',
          detail: result ? '可复制、导出，并在测试用例页继续使用' : '生成完成后会在中间结果区展示',
          status: result ? 'done' : 'idle',
        },
      ],
    },
    {
      id: 'signals',
      title: '自动化信号',
      description: '将输入来源、附件和输出控制条件收拢到同一侧栏。',
      entries: [
        {
          id: 'input',
          label: '输入来源',
          value: description ? '文本录入' : files.length > 0 ? '上传文档' : '等待输入',
          detail: files.length > 0 ? `已附加 ${files.length} 个文件` : '当前未附加文件',
          status: description || files.length > 0 ? 'done' : 'idle',
        },
        {
          id: 'options',
          label: '附加策略',
          value: `${includeEdge ? '含异常场景' : '标准场景'} · ${includeAssert ? '含断言' : '无断言'}`,
          detail: '控制生成结果中是否包含异常路径与断言代码。',
          status: 'idle',
        },
        {
          id: 'context',
          label: '任务上下文',
          value: requirementContextId ? '已联动' : '未联动',
          detail: requirementContextId ? '可沿当前任务继续到测试设计阶段' : '建议先补全评审上下文',
          status: requirementContextId ? 'done' : 'idle',
        },
      ],
    },
    {
      id: 'activity',
      title: '下一步建议',
      description: '让自动化生成页也能继续承接测试设计动作。',
      entries: [
        {
          id: 'testcases',
          label: '看用例',
          value: '继续设计',
          detail: '适合将自动化结果沉淀回测试用例资产。',
          status: result ? 'running' : 'idle',
          onClick: () => setActiveNav('test-cases'),
        },
        {
          id: 'writeback',
          label: '写入用例',
          value: '带入结果',
          detail: '仅在任务类型为测试用例且已生成结果时可直接写入。',
          status: taskType === 'test-cases' && result ? 'done' : 'idle',
          onClick: () => {
            if (taskType === 'test-cases' && result) {
              goToTestCases()
            }
          },
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
                    <Bot className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="console-kicker">{UI_AUTO_HEADER_COPY.kicker}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <h1 className="text-xl font-semibold text-[var(--text-primary)]">{UI_AUTO_HEADER_COPY.title}</h1>
                      {automationCopy.tags.map((tag) => (
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
                      {automationCopy.description}
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
                  onClick={() => setModuleSession(UI_AUTO_SESSION_KEY, { requirement: taskSummary.requirement })}
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
                  onClick={() => setActiveNav('test-cases')}
                  className="rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-3 py-2 text-xs font-medium text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]"
                >
                  看用例
                </button>
              </div>
            </div>

            <div className="console-kicker">任务类型</div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {TASK_TYPES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() =>
                    setModuleSession(UI_AUTO_SESSION_KEY, {
                      options: {
                        ...sessionOptions,
                        taskType: item.id,
                      },
                    })
                  }
                  className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                    taskType === item.id
                      ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)]'
                      : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] hover:border-[color:var(--border-hover)]'
                  }`}
                >
                  <div className="text-sm font-medium text-[var(--text-primary)]">{item.label}</div>
                </button>
              ))}
            </div>
          </section>

          <section className="console-panel p-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="console-kicker">需求输入</div>
              </div>
              <button
                type="button"
                onClick={() => setModuleSession(UI_AUTO_SESSION_KEY, { requirement: EXAMPLE_TEMPLATES[taskType] })}
                className="rounded-full border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent-primary)]"
              >
                填充示例
              </button>
            </div>
            <textarea
              value={description}
              onChange={(e) => setModuleSession(UI_AUTO_SESSION_KEY, { requirement: e.target.value })}
              placeholder="描述页面、场景和目标"
              className="h-40 w-full resize-none rounded-xl border p-4 text-sm outline-none transition-colors"
              style={{ borderColor: 'var(--border)' }}
            />

            {requirementContextId && files.length === 0 && !description && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-600">
                <span className="rounded-full border border-emerald-500/20 bg-white/70 px-2 py-0.5 font-semibold text-emerald-700">
                  最近上下文
                </span>
                <span>{automationCopy.contextHint}</span>
              </div>
            )}
          </section>

          <section className="console-panel overflow-hidden">
            <div className="border-b px-5 py-4" style={{ borderColor: 'var(--border-soft)' }}>
              <div className="console-kicker">上传附件</div>
            </div>
            <div className="p-4">
              <FileUploadTrigger
                ariaLabel="上传附件"
                accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.txt,.md"
                primaryText={files.length > 0 ? `已选 ${files.length} 个文件` : '拖拽或上传'}
                contentClassName="flex-col justify-center"
                onFilesChange={(nextFiles) => {
                  setIsDragging(false)
                  setFiles(nextFiles)
                }}
                onDragOver={(event) => {
                  event.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`rounded-xl border-2 border-dashed py-6 text-center transition-colors ${
                  isDragging
                    ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)]'
                    : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] hover:border-[color:var(--border-hover)]'
                }`}
              >
                <div className="text-sm font-medium text-[var(--text-primary)]">
                  {files.length > 0 ? `已选 ${files.length} 个文件` : '拖拽或上传'}
                </div>
                <div className="mt-1 text-xs text-[var(--text-secondary)]">PRD / 截图 / 文档</div>
              </FileUploadTrigger>

              {files.length > 0 && (
                <div className="mt-3 space-y-2">
                  {files.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="console-inset flex items-center gap-2 px-3 py-2">
                      <FileCode2 className="h-4 w-4 text-[var(--accent-primary)]" />
                      <span className="flex-1 truncate text-xs text-[var(--text-primary)]">{file.name}</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setFiles(files.filter((_, itemIndex) => itemIndex !== index))
                        }}
                        className="text-xs text-[var(--text-muted)] transition-colors hover:text-red-500"
                      >
                        删除
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="console-panel overflow-hidden">
            <button
              type="button"
              onClick={() =>
                setModuleSession(UI_AUTO_SESSION_KEY, {
                  options: {
                    ...sessionOptions,
                    configExpanded: !configExpanded,
                  },
                })
              }
              className="flex w-full items-center justify-between px-5 py-4 transition-colors hover:bg-[var(--surface-inset)]"
            >
              <div className="flex items-center gap-3 text-left">
                <div>
                  <div className="console-kicker">配置</div>
                </div>
                <div className="rounded-full border px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)]" style={{ borderColor: 'var(--border-soft)' }}>
                  {selectedCoverageLabel}
                </div>
              </div>
              <span className={`text-sm text-[var(--text-secondary)] transition-transform ${configExpanded ? 'rotate-180' : ''}`}>▾</span>
            </button>
            {configExpanded && (
              <div className="border-t px-5 pb-5 pt-4" style={{ borderColor: 'var(--border-soft)' }}>
                <div className="space-y-5">
                  <div>
                    <div className="mb-2 text-xs font-medium text-[var(--text-secondary)]">测试框架</div>
                    <div className="flex flex-wrap gap-2">
                      {FRAMEWORKS.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() =>
                            setModuleSession(UI_AUTO_SESSION_KEY, {
                              options: {
                                ...sessionOptions,
                                framework: item.id,
                              },
                            })
                          }
                          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                            framework === item.id
                              ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                              : 'border-[color:var(--border-soft)] text-[var(--text-secondary)]'
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-xs font-medium text-[var(--text-secondary)]">覆盖范围</div>
                    <div className="flex flex-wrap gap-2">
                      {COVERAGES.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() =>
                            setModuleSession(UI_AUTO_SESSION_KEY, {
                              options: {
                                ...sessionOptions,
                                coverage: item.id,
                              },
                            })
                          }
                          className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${
                            coverage === item.id
                              ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                              : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
                          }`}
                          title={item.desc}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-3">
                    {[
                      { label: '包含异常场景', desc: '边界、错误、网络异常', value: includeEdge, optionKey: 'includeEdge' as const },
                      { label: '生成断言代码', desc: '自动补全 expect / assert', value: includeAssert, optionKey: 'includeAssert' as const },
                    ].map((item) => (
                      <div key={item.label} className="flex items-center justify-between gap-4">
                        <div title={item.desc}>
                          <div className="text-sm font-medium text-[var(--text-primary)]">{item.label}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            setModuleSession(UI_AUTO_SESSION_KEY, {
                              options: {
                                ...sessionOptions,
                                [item.optionKey]: !item.value,
                              },
                            })
                          }
                          className={`relative h-[22px] w-10 rounded-full transition-colors ${item.value ? 'bg-[var(--accent-primary)]' : 'bg-[var(--surface-inset)]'}`}
                        >
                          <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${item.value ? 'translate-x-5' : 'translate-x-0.5'}`} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
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
            {isRunning ? <Bot className="h-4 w-4" /> : <Play className="h-4 w-4" />}
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
                    { id: 'result', label: '结果' },
                    { id: 'log', label: '执行' },
                    { id: 'history', label: '历史' },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setModuleSession(UI_AUTO_SESSION_KEY, { activeTab: tab.id as ResultTab })}
                      className={getWorkbenchResultTabClassName(resultTab === tab.id)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {runStatus === 'done' && result && (
                  <div className={getWorkbenchResultToolbarGroupClassName('end')}>
                    <div className={getWorkbenchResultActionGroupClassName()} style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                      <button
                        type="button"
                        onClick={copyToClipboard}
                        title="复制结果"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Clipboard className="h-3 w-3" />
                          复制
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={exportMarkdown}
                        title="下载 Markdown"
                        className={getWorkbenchResultActionClassName()}
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <span className="inline-flex items-center gap-1">
                          <Download className="h-3 w-3" />
                          MD
                        </span>
                      </button>
                      {taskType === 'test-cases' && (
                        <button
                          type="button"
                          onClick={goToTestCases}
                          title="写入测试用例"
                          className={getWorkbenchResultActionClassName('accent')}
                        >
                          <span className="inline-flex items-center gap-1">
                            <FileCode2 className="h-3 w-3" />
                            写入用例
                          </span>
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>

            <div className="relative flex-1 overflow-hidden p-5">
              {resultTab === 'history' ? (
                <HistoryReportPanel
                  types={['ui-auto']}
                  emptyTitle={historyEmptyCopy.title}
                  emptyDescription={historyEmptyCopy.description}
                />
              ) : resultTab === 'log' ? (
                runStatus === 'idle' ? (
                  <div className="flex h-full items-center justify-center text-sm text-[var(--text-secondary)]">
                    {logEmptyCopy}
                  </div>
                ) : (
                  <div className="space-y-6 py-4">
                    <ProgressTimeline currentStatus={runStatus} />
                    <div className="console-panel-muted p-4">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                      <ExecutionEventLog events={eventLogs} />
                    </div>
                  </div>
                )
              ) : runStatus === 'idle' ? (
                <EmptyResultState title={automationCopy.emptyTitle} description={automationCopy.emptyDescription} />
              ) : isRunning ? (
                <div className="flex h-full flex-col items-center justify-center py-10">
                  <div className="w-full max-w-2xl space-y-6">
                    <p className="text-center text-xl font-semibold tracking-tight text-[var(--text-primary)]">正在生成结果...</p>
                    <ProgressTimeline currentStatus={runStatus} />
                    <div className="console-panel-muted p-4">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{eventLogCopy.title}</div>
                      <ExecutionEventLog events={eventLogs} emptyText={eventLogCopy.emptyText} />
                    </div>
                  </div>
                </div>
              ) : runStatus === 'done' && result ? (
                <div className="animate-fade-in">
                  <ResultStageBanner
                    title={`${currentTask.label}已生成`}
                    meta={`${FRAMEWORKS.find((item) => item.id === framework)?.label || framework} · ${selectedCoverageLabel}`}
                  />
                  <div className={`custom-scrollbar prose prose-sm max-w-none h-[680px] overflow-y-auto pr-2 ${appearance === 'dark' ? 'prose-invert' : ''}`}>
                    <ReactMarkdown>{result}</ReactMarkdown>
                  </div>
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10 text-red-500">
                    <AlertTriangle className="h-7 w-7" />
                  </div>
                  <p className="mt-5 text-lg font-medium text-red-500">{failureCopy.title}</p>
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
            title="UI 自动化"
            subtitle=""
            tags={[
              { label: runPresentation.stageLabel, tone: 'accent' },
              { label: currentTask.label, tone: 'neutral' },
              { label: result ? '已有结果' : '待生成', tone: result ? 'success' : 'neutral' },
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
              { label: '去测试用例', onClick: () => setActiveNav('test-cases') },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildApiTestWorkbenchCopy,
  buildApiTestExecutionFailureCases,
  buildApiTestExecutionPanelCopy,
  buildApiTestExecutionStatsText,
  buildInlineErrorCopy,
  buildCollaborationRailOverviewBadges,
  buildCollaborationSectionDigests,
  buildDashboardQuickAccessCards,
  buildDashboardQuickAccessOverview,
  buildDashboardSnapshotBadges,
  buildDashboardStageTrack,
  buildExecutionLogCopy,
  buildRailStatusBadgeCopy,
  buildFlowchartWorkbenchCopy,
  buildGenericWorkbenchCopy,
  buildHistoryEmptyCopy,
  buildLogEmptyCopy,
  buildProgressStepLabelMap,
  buildRequirementAnalysisWorkbenchCopy,
  buildResultEmptyCopy,
  buildResultFailureCopy,
  buildResultFormatErrorCopy,
  buildReviewWorkbenchCopy,
  buildTestCaseWorkbenchCopy,
  buildTopBarPresentation,
  buildUiAutoWorkbenchCopy,
  buildWeeklyReportWorkbenchCopy,
  buildWorkbenchHeaderCopy,
  buildRunStateValue,
  compactDashboardMetricDelta,
  compactRailSections,
  resolveWorkbenchRunPresentation,
  resolveTaskInputMode,
  selectPrimaryDashboardMetrics,
  type PresentationRailSection,
} from './workbenchPresentation.ts'

test('selectPrimaryDashboardMetrics keeps three metrics and prefers task signals', () => {
  const metrics = selectPrimaryDashboardMetrics([
    { label: '本周执行总量', value: '24', delta: '周同比 +4', color: '', bg: '', border: '' },
    { label: '高风险需求', value: '3', delta: '来自最近评审', color: '', bg: '', border: '' },
    { label: '已完成资产', value: '5', delta: '当前任务沉淀', color: '', bg: '', border: '' },
    { label: '待处理缺陷', value: '9', delta: '来自流水线回传', color: '', bg: '', border: '' },
  ])

  assert.deepEqual(
    metrics.map((metric) => metric.label),
    ['高风险需求', '已完成资产', '待处理缺陷']
  )
})

test('compactDashboardMetricDelta trims verbose dashboard metric copy', () => {
  assert.equal(
    compactDashboardMetricDelta({ label: '高风险需求', value: '3', delta: '来自最近评审', color: '', bg: '', border: '' }),
    '最近评审'
  )
  assert.equal(
    compactDashboardMetricDelta({ label: '待处理缺陷', value: '9', delta: '来自流水线回传', color: '', bg: '', border: '' }),
    '流水线'
  )
  assert.equal(
    compactDashboardMetricDelta({ label: '已完成资产', value: '5', delta: '当前任务沉淀', color: '', bg: '', border: '' }),
    '当前任务'
  )
})

test('buildTopBarPresentation keeps top bar labels concise', () => {
  assert.deepEqual(
    buildTopBarPresentation({
      moduleLabel: '需求分析',
      environment: 'staging',
    }),
    {
      moduleLabel: '需求分析',
      moduleShortLabel: '分析',
      environmentLabel: '预发',
      environmentBadge: 'PRE',
      searchPlaceholder: '搜索任务 / 命令',
    }
  )

  assert.deepEqual(
    buildTopBarPresentation({
      moduleLabel: '业务流程图',
      environment: 'test',
    }),
    {
      moduleLabel: '业务流程图',
      moduleShortLabel: '流程图',
      environmentLabel: '测试',
      environmentBadge: 'TEST',
      searchPlaceholder: '搜索任务 / 命令',
    }
  )
})

test('compactRailSections strips prose fields and keeps summary signals only', () => {
  const sections: PresentationRailSection[] = [
    {
      id: 'signals',
      title: '任务信号',
      description: '将上下文、风险和结果沉淀固定在右侧。',
      entries: [
        {
          id: 'risk',
          label: '评审发现',
          value: '4 项',
          detail: '已接入生成策略，可增强高风险覆盖',
          status: 'warning',
        },
      ],
    },
  ]

  assert.deepEqual(compactRailSections(sections), [
    {
      id: 'signals',
      title: '任务信号',
      entries: [
        {
          id: 'risk',
          label: '评审发现',
          value: '4 项',
          status: 'warning',
        },
      ],
    },
  ])
})

test('buildCollaborationRailOverviewBadges summarizes section count and active signals', () => {
  assert.deepEqual(
    buildCollaborationRailOverviewBadges([
      {
        id: 'activity',
        title: '协作动态',
        entries: [{ id: 'a', label: '最近任务', value: '登录流程', status: 'done' }],
      },
      {
        id: 'signals',
        title: '工程信号',
        entries: [
          { id: 'b', label: '风险', value: '2 项', status: 'warning' },
          { id: 'c', label: '状态', value: '处理中', status: 'running' },
        ],
      },
    ]),
    [
      { label: '2 分区', tone: 'neutral' },
      { label: '1 进行中', tone: 'accent' },
      { label: '1 需关注', tone: 'warning' },
    ]
  )
})

test('buildCollaborationSectionDigests condenses section entry count and tone', () => {
  assert.deepEqual(
    buildCollaborationSectionDigests([
      {
        id: 'signals',
        title: '工程信号',
        entries: [
          { id: 'risk', label: '风险', value: '2 项', status: 'warning' },
          { id: 'asset', label: '资产', value: '3/5', status: 'idle' },
        ],
      },
      {
        id: 'agents',
        title: '当前协作建议',
        entries: [{ id: 'next', label: '推荐下一步', value: '生成用例', status: 'running' }],
      },
    ]),
    [
      { id: 'signals', title: '工程信号', countLabel: '2 条', tone: 'warning' },
      { id: 'agents', title: '当前协作建议', countLabel: '1 条', tone: 'accent' },
    ]
  )
})

test('buildDashboardStageTrack marks completed active and pending steps', () => {
  assert.deepEqual(
    buildDashboardStageTrack('design'),
    [
      { id: 'import', label: '导入需求', shortLabel: '导入', state: 'completed' },
      { id: 'review', label: '风险评审', shortLabel: '评审', state: 'completed' },
      { id: 'design', label: '测试设计', shortLabel: '设计', state: 'active' },
      { id: 'automation', label: '自动化生成', shortLabel: '自动化', state: 'pending' },
      { id: 'deliver', label: '输出沉淀', shortLabel: '沉淀', state: 'pending' },
    ]
  )
})

test('buildDashboardQuickAccessOverview summarizes recommended completed and pending cards', () => {
  assert.deepEqual(
    buildDashboardQuickAccessOverview([
      {
        id: 'review',
        label: '需求评审',
        navId: 'review',
        stateLabel: '推荐下一步',
        actionLabel: '立即评审',
        tone: 'accent',
      },
      {
        id: 'test-cases',
        label: '测试用例',
        navId: 'test-cases',
        stateLabel: '已生成',
        actionLabel: '查看用例',
        tone: 'success',
      },
      {
        id: 'flowchart',
        label: '业务流程图',
        navId: 'flowchart',
        stateLabel: '可生成',
        actionLabel: '立即生成',
        tone: 'neutral',
      },
    ]),
    ['1 推荐', '1 完成', '1 待办']
  )
})

test('buildDashboardSnapshotBadges keeps recent task meta short', () => {
  assert.deepEqual(
    buildDashboardSnapshotBadges({
      currentStageLabel: '测试设计',
      riskCount: 0,
      sourceLabel: '最近上下文',
    }),
    ['测试设计', '低风险', '上下文']
  )

  assert.deepEqual(
    buildDashboardSnapshotBadges({
      currentStageLabel: '风险评审',
      riskCount: 3,
      sourceLabel: '当前输入',
    }),
    ['风险评审', '3 风险', '当前输入']
  )
})

test('buildDashboardQuickAccessCards highlights current entry before assets exist', () => {
  assert.deepEqual(
    buildDashboardQuickAccessCards({
      currentStage: 'review',
      primaryNavId: 'review',
      riskCount: 0,
      hasRequirement: true,
      assets: [],
    }),
    [
      {
        id: 'review',
        label: '需求评审',
        navId: 'review',
        stateLabel: '推荐下一步',
        actionLabel: '去评审',
        tone: 'accent',
      },
      {
        id: 'test-cases',
        label: '测试用例',
        navId: 'test-cases',
        stateLabel: '待评审',
        actionLabel: '去生成',
        tone: 'neutral',
      },
      {
        id: 'req-analysis',
        label: '需求分析',
        navId: 'req-analysis',
        stateLabel: '待评审',
        actionLabel: '去分析',
        tone: 'neutral',
      },
      {
        id: 'flowchart',
        label: '业务流程图',
        navId: 'flowchart',
        stateLabel: '待评审',
        actionLabel: '去生成',
        tone: 'neutral',
      },
      {
        id: 'ui-auto',
        label: 'UI 自动化',
        navId: 'ui-auto',
        stateLabel: '待评审',
        actionLabel: '去生成',
        tone: 'neutral',
      },
    ]
  )
})

test('buildDashboardQuickAccessCards compresses module state into short labels', () => {
  assert.deepEqual(
    buildDashboardQuickAccessCards({
      currentStage: 'automation',
      primaryNavId: 'ui-auto',
      riskCount: 2,
      hasRequirement: true,
      assets: [
        { id: 'review', done: true },
        { id: 'test-cases', done: true },
      ],
    }),
    [
      {
        id: 'review',
        label: '需求评审',
        navId: 'review',
        stateLabel: '2 风险',
        actionLabel: '看评审',
        tone: 'warning',
      },
      {
        id: 'test-cases',
        label: '测试用例',
        navId: 'test-cases',
        stateLabel: '已生成',
        actionLabel: '看用例',
        tone: 'success',
      },
      {
        id: 'req-analysis',
        label: '需求分析',
        navId: 'req-analysis',
        stateLabel: '可补充',
        actionLabel: '去分析',
        tone: 'neutral',
      },
      {
        id: 'flowchart',
        label: '业务流程图',
        navId: 'flowchart',
        stateLabel: '可生成',
        actionLabel: '去生成',
        tone: 'neutral',
      },
      {
        id: 'ui-auto',
        label: 'UI 自动化',
        navId: 'ui-auto',
        stateLabel: '推荐下一步',
        actionLabel: '去生成',
        tone: 'accent',
      },
    ]
  )
})

test('resolveTaskInputMode prefers text, then upload, then tapd', () => {
  assert.equal(resolveTaskInputMode({ requirement: '登录锁定规则', filesCount: 0, tapdInput: '' }), 'text')
  assert.equal(resolveTaskInputMode({ requirement: '', filesCount: 2, tapdInput: '12345' }), 'upload')
  assert.equal(resolveTaskInputMode({ requirement: '', filesCount: 0, tapdInput: 'https://www.tapd.cn/123/s/456' }), 'tapd')
  assert.equal(resolveTaskInputMode({ requirement: '', filesCount: 0, tapdInput: '' }), 'text')
})

test('buildHistoryEmptyCopy keeps history panel empty state unified', () => {
  assert.deepEqual(buildHistoryEmptyCopy(), {
    title: '还没有历史结果',
    description: '完成后保存在这里。',
  })
})

test('buildResultEmptyCopy keeps result empty state short in both modes', () => {
  assert.deepEqual(buildResultEmptyCopy(), {
    title: '还没有结果',
    description: '左侧补充后，直接开始。',
  })

  assert.deepEqual(buildResultEmptyCopy({ mode: 'preview' }), {
    title: '还没有结果',
    description: '左侧补充后，中间直接展示。',
  })
})

test('buildLogEmptyCopy keeps idle log hint concise', () => {
  assert.equal(buildLogEmptyCopy(), '开始运行后显示。')
})

test('buildResultFormatErrorCopy keeps unreadable result hint short', () => {
  assert.deepEqual(buildResultFormatErrorCopy(), {
    title: '结果暂不可读',
    description: '请看 Markdown 原文。',
  })

  assert.deepEqual(buildResultFormatErrorCopy({ target: 'log' }), {
    title: '结果暂不可读',
    description: '请看执行日志。',
  })
})

test('buildResultFailureCopy keeps failure state title and retry action short', () => {
  assert.deepEqual(buildResultFailureCopy(), {
    title: '生成失败',
    actionLabel: '重试',
  })

  assert.deepEqual(buildResultFailureCopy({ mode: 'process' }), {
    title: '处理失败',
    actionLabel: '重试',
  })
})

test('buildInlineErrorCopy keeps fallback errors consistent and short', () => {
  assert.equal(buildInlineErrorCopy(), '处理失败')
  assert.equal(buildInlineErrorCopy('generate'), '生成失败')
  assert.equal(buildInlineErrorCopy('tapd'), '读取 TAPD 失败')
  assert.equal(buildInlineErrorCopy('export'), '导出失败')
})

test('buildExecutionLogCopy keeps event panel labels concise', () => {
  assert.deepEqual(buildExecutionLogCopy(), {
    title: '任务事件',
    emptyText: '等待任务事件...',
  })
})

test('buildApiTestExecutionStatsText summarizes api execution counters', () => {
  assert.equal(
    buildApiTestExecutionStatsText({
      total: 5,
      passed: 3,
      failed: 1,
      errors: 1,
      skipped: 0,
    }),
    '总 5 / 通过 3 / 失败 1 / 异常 1 / 跳过 0'
  )

  assert.equal(buildApiTestExecutionStatsText(), '等待执行结果')
})

test('buildApiTestExecutionPanelCopy normalizes execution overview for rendering', () => {
  assert.deepEqual(
    buildApiTestExecutionPanelCopy({
      status: 'failed',
      summary: '1 个用例失败',
      stats: {
        total: 5,
        passed: 3,
        failed: 1,
        errors: 1,
        skipped: 0,
      },
      command: 'pytest -q tests/platform_tests/test_api_suite.py',
      stdout: '3 passed, 1 failed',
      stderr: 'AssertionError: 断言失败',
      junit_xml_content: `<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="5" failures="1" errors="1" skipped="0">
    <testcase classname="test_api_suite" name="test_create_platform_goods" />
    <testcase classname="test_api_suite" name="test_update_platform_goods">
      <failure message="AssertionError">assert 500 == 200</failure>
    </testcase>
    <testcase classname="test_api_suite" name="test_delete_platform_goods">
      <error message="RuntimeError">数据库连接失败</error>
    </testcase>
  </testsuite>
</testsuites>`,
      artifacts: {
        run_dir: 'history/api_test_runs/run-123',
        generated_script: 'history/api_test_runs/run-123/generated_script.py',
        compiled_script: 'history/api_test_runs/run-123/test_api_suite.py',
        junit_xml: 'history/api_test_runs/run-123/junit.xml',
        execution_summary: 'history/api_test_runs/run-123/execution_summary.json',
      },
    }),
    {
      statusLabel: '失败',
      summary: '1 个用例失败',
      statsText: '总 5 / 通过 3 / 失败 1 / 异常 1 / 跳过 0',
      commandText: 'pytest -q tests/platform_tests/test_api_suite.py',
      runDirectoryText: 'history/api_test_runs/run-123',
      artifacts: [
        {
          key: 'generated_script',
          label: '生成脚本',
          value: 'history/api_test_runs/run-123/generated_script.py',
        },
        {
          key: 'compiled_script',
          label: '执行脚本',
          value: 'history/api_test_runs/run-123/test_api_suite.py',
        },
        {
          key: 'junit_xml',
          label: 'JUnit 报告',
          value: 'history/api_test_runs/run-123/junit.xml',
        },
        {
          key: 'execution_summary',
          label: '执行摘要',
          value: 'history/api_test_runs/run-123/execution_summary.json',
        },
      ],
      artifactEmptyText: '暂无落盘产物',
      failureCases: [
        {
          key: 'failure-0',
          title: 'test_api_suite::test_update_platform_goods',
          detail: 'AssertionError',
          kind: 'failure',
        },
        {
          key: 'error-1',
          title: 'test_api_suite::test_delete_platform_goods',
          detail: 'RuntimeError',
          kind: 'error',
        },
      ],
      failureEmptyText: '未解析到失败用例',
      stdoutText: '3 passed, 1 failed',
      stdoutEmptyText: '无标准输出',
      stderrText: 'AssertionError: 断言失败',
      stderrEmptyText: '无错误输出',
    }
  )
})

test('buildApiTestExecutionPanelCopy keeps fallback text stable for empty payloads', () => {
  assert.deepEqual(buildApiTestExecutionPanelCopy(), {
    statusLabel: '未执行',
    summary: '当前结果未包含执行摘要。',
    statsText: '等待执行结果',
    commandText: '未记录执行命令',
    runDirectoryText: '未记录运行目录',
    artifacts: [],
    artifactEmptyText: '暂无落盘产物',
    failureCases: [],
    failureEmptyText: '未解析到失败用例',
    stdoutText: '',
    stdoutEmptyText: '无标准输出',
    stderrText: '',
    stderrEmptyText: '无错误输出',
  })
})

test('buildApiTestExecutionPanelCopy exposes allure artifacts when available', () => {
  const copy = buildApiTestExecutionPanelCopy({
    artifacts: {
      allure_results: 'history/api_test_runs/run-123/allure-results',
      allure_archive: 'history/api_test_runs/run-123/allure-results.zip',
    },
  })

  assert.deepEqual(copy.artifacts, [
    {
      key: 'allure_results',
      label: 'Allure 原始结果',
      value: 'history/api_test_runs/run-123/allure-results',
    },
    {
      key: 'allure_archive',
      label: 'Allure 压缩包',
      value: 'history/api_test_runs/run-123/allure-results.zip',
    },
  ])
})

test('buildApiTestExecutionFailureCases extracts failed and error testcases from junit xml', () => {
  assert.deepEqual(
    buildApiTestExecutionFailureCases(`<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" failures="1" errors="1" skipped="0">
    <testcase classname="test_api_suite" name="test_create_platform_goods">
      <failure message="AssertionError">assert 500 == 200</failure>
    </testcase>
    <testcase classname="test_api_suite" name="test_delete_platform_goods">
      <error message="RuntimeError">数据库连接失败</error>
    </testcase>
  </testsuite>
</testsuites>`),
    [
      {
        key: 'failure-0',
        title: 'test_api_suite::test_create_platform_goods',
        detail: 'AssertionError',
        kind: 'failure',
      },
      {
        key: 'error-1',
        title: 'test_api_suite::test_delete_platform_goods',
        detail: 'RuntimeError',
        kind: 'error',
      },
    ]
  )

  assert.deepEqual(buildApiTestExecutionFailureCases(''), [])
})

test('buildRunStateValue avoids showing idle copy when task already failed', () => {
  assert.equal(
    buildRunStateValue({
      status: 'idle',
      idleLabel: '等待开始',
      runningLabel: '处理中',
      doneLabel: '处理完成',
    }),
    '等待开始'
  )

  assert.equal(
    buildRunStateValue({
      status: 'running',
      idleLabel: '等待开始',
      runningLabel: '处理中',
      doneLabel: '处理完成',
    }),
    '处理中'
  )

  assert.equal(
    buildRunStateValue({
      status: 'done',
      idleLabel: '等待开始',
      runningLabel: '处理中',
      doneLabel: '处理完成',
    }),
    '处理完成'
  )

  assert.equal(
    buildRunStateValue({
      status: 'error',
      idleLabel: '等待开始',
      runningLabel: '处理中',
      doneLabel: '处理完成',
    }),
    '失败'
  )
})

test('buildRailStatusBadgeCopy hides idle badge and shortens visible labels', () => {
  assert.deepEqual(buildRailStatusBadgeCopy('idle'), {
    hidden: true,
    label: '',
  })

  assert.deepEqual(buildRailStatusBadgeCopy('running'), {
    hidden: false,
    label: '进行中',
  })

  assert.deepEqual(buildRailStatusBadgeCopy('done'), {
    hidden: false,
    label: '完成',
  })

  assert.deepEqual(buildRailStatusBadgeCopy('warning'), {
    hidden: false,
    label: '注意',
  })
})

test('buildWorkbenchHeaderCopy keeps page headers short and consistent', () => {
  assert.deepEqual(buildWorkbenchHeaderCopy({ module: 'test-case' }), {
    kicker: '测试设计',
    title: '测试用例',
  })

  assert.deepEqual(buildWorkbenchHeaderCopy({ module: 'weekly' }), {
    kicker: '输出沉淀',
    title: '测试周报',
  })

  assert.deepEqual(buildWorkbenchHeaderCopy({ module: 'generic', label: '测试点提取' }), {
    kicker: '专家模块',
    title: '测试点提取',
  })
})

test('buildProgressStepLabelMap keeps running timeline labels concise', () => {
  assert.deepEqual(buildProgressStepLabelMap('test-case'), {
    context: '解析需求',
    associating: '关联风险',
    decomposing: '拆解场景',
    matching: '匹配策略',
    generating: '生成用例',
    evaluating: '整理结果',
    done: '已完成',
  })

  assert.deepEqual(buildProgressStepLabelMap('review'), {
    reading: '解析需求',
    analyzing: '并行评审',
    grouping: '聚合观点',
    conflicting: '生成结论',
    grading: '整理风险',
    done: '已完成',
  })
})

test('buildReviewWorkbenchCopy keeps review hero and empty state concise', () => {
  assert.deepEqual(
    buildReviewWorkbenchCopy({
      selectedRolesCount: 4,
      findingsCount: 6,
      hasResult: true,
      hasContext: true,
    }),
    {
      description: '先看风险，再继续。',
      tags: ['已完成', '4 个角色', '6 个风险', '已联动'],
      contextHint: '最近上下文已接入输入区，可直接补充后开始评审。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，直接开始。',
    }
  )
})

test('buildTestCaseWorkbenchCopy keeps test-case page focused on direct generation', () => {
  assert.deepEqual(
    buildTestCaseWorkbenchCopy({
      hasResult: true,
      hasContext: true,
    }),
    {
      description: '直接产出测试资产。',
      tags: ['已生成', '已联动'],
      contextHint: '最近上下文已接入输入区，可直接开始生成测试用例。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，直接开始。',
    }
  )
})

test('buildRequirementAnalysisWorkbenchCopy keeps requirement analysis page focused on structure first', () => {
  assert.deepEqual(
    buildRequirementAnalysisWorkbenchCopy({
      hasResult: true,
      hasContext: true,
      moduleCount: 3,
    }),
    {
      description: '先拆结构，再继续设计。',
      tags: ['已生成', '3 个模块', '已联动'],
      contextHint: '最近上下文可直接带入输入区，补充后再执行结构化分析。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，中间直接展示。',
    }
  )
})

test('buildFlowchartWorkbenchCopy favors diagram-first summary copy', () => {
  assert.deepEqual(
    buildFlowchartWorkbenchCopy({
      moduleCount: 3,
      warningCount: 2,
      hasMarkdown: true,
      hasContext: true,
    }),
    {
      description: '先看主流程，再补异常。',
      tags: ['已生成', '3 个模块', '2 条风险', '已联动'],
      contextHint: '最近上下文已接入输入区，可直接补充后生成流程图。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，中间直接展示。',
    }
  )
})

test('buildUiAutoWorkbenchCopy keeps automation page focused on output', () => {
  assert.deepEqual(
    buildUiAutoWorkbenchCopy({
      taskLabel: '生成自动化脚本',
      frameworkLabel: 'Playwright',
      hasResult: false,
      hasContext: true,
    }),
    {
      description: '先定产物，再生成。',
      tags: ['待生成', '生成自动化脚本', 'Playwright', '已联动'],
      contextHint: '最近上下文可直接带入输入区，确认任务类型后即可开始生成。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，直接开始。',
    }
  )
})

test('buildWeeklyReportWorkbenchCopy keeps weekly report summary concise', () => {
  assert.deepEqual(
    buildWeeklyReportWorkbenchCopy({
      publishToFeishu: true,
      screenshotsCount: 5,
      hasResult: false,
      hasContext: true,
    }),
    {
      description: '先收结论，再生成周报。',
      tags: ['待生成', '5 张截图', '飞书同步开启', '已联动'],
      contextHint: '最近上下文可直接带入输入区，确认本周结论后即可开始生成。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，直接开始。',
    }
  )
})

test('buildApiTestWorkbenchCopy keeps api test workbench focused on assets and execution', () => {
  assert.deepEqual(
    buildApiTestWorkbenchCopy({
      hasResult: false,
      hasContext: true,
      executeAfterGenerate: true,
      hasExecution: false,
    }),
    {
      description: '先生成资产，再决定是否执行。',
      tags: ['待生成', '执行模式开启', '已联动'],
      contextHint: '最近上下文可直接带入输入区，补充 OpenAPI 文档或接口说明后即可开始生成。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，直接开始。',
    }
  )
})

test('buildGenericWorkbenchCopy keeps generic expert page concise', () => {
  assert.deepEqual(
    buildGenericWorkbenchCopy({
      isStructured: false,
      hasResult: false,
      hasContext: true,
    }),
    {
      description: '先交给专家，再看结果。',
      tags: ['待生成', 'Markdown 结果', '已联动'],
      contextHint: '最近上下文可直接带入输入区，补充后即可开始处理。',
      emptyTitle: '还没有结果',
      emptyDescription: '左侧补充后，直接开始。',
    }
  )
})

test('resolveWorkbenchRunPresentation switches stage and action labels by status', () => {
  assert.deepEqual(
    resolveWorkbenchRunPresentation({
      status: 'idle',
      idleStageLabel: '测试设计',
      doneStageLabel: '用例已生成',
      idleActionLabel: '生成',
      runningActionLabel: '生成中',
    }),
    {
      stageLabel: '测试设计',
      primaryActionLabel: '立即生成',
      railActionLabel: '立即生成',
    }
  )

  assert.deepEqual(
    resolveWorkbenchRunPresentation({
      status: 'running',
      idleStageLabel: '测试设计',
      doneStageLabel: '用例已生成',
      idleActionLabel: '生成',
      runningActionLabel: '生成中',
    }),
    {
      stageLabel: '测试设计',
      primaryActionLabel: '生成中',
      railActionLabel: '生成中',
    }
  )

  assert.deepEqual(
    resolveWorkbenchRunPresentation({
      status: 'done',
      idleStageLabel: '测试设计',
      doneStageLabel: '用例已生成',
      idleActionLabel: '生成',
      runningActionLabel: '生成中',
    }),
    {
      stageLabel: '用例已生成',
      primaryActionLabel: '立即生成',
      railActionLabel: '立即生成',
    }
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSeededSessionPatch,
  buildTaskTitle,
  buildTaskWorkbenchSummary,
  pickPrimaryRequirement,
} from './taskWorkbench.ts'

test('pickPrimaryRequirement prefers review requirement over later module inputs', () => {
  const requirement = pickPrimaryRequirement({
    'test-case': { requirement: '测试用例里的需求' },
    review: { requirement: '评审里的需求' },
  })

  assert.equal(requirement, '评审里的需求')
})

test('buildTaskTitle uses first meaningful line and trims markdown markers', () => {
  const title = buildTaskTitle('# 登录失败重试与锁定规则说明\n- 第二行')

  assert.equal(title, '登录失败重试与锁定规则说明')
})

test('buildTaskWorkbenchSummary stays in review stage when requirement exists but review is not done', () => {
  const summary = buildTaskWorkbenchSummary({
    moduleSessions: {
      review: { requirement: '用户登录锁定规则' },
    },
    reviewFindings: [],
    requirementContextId: null,
  })

  assert.equal(summary.currentStage, 'review')
  assert.equal(summary.primaryAction.navId, 'review')
  assert.equal(summary.title, '用户登录锁定规则')
  assert.equal(summary.sourceLabel, '当前输入')
})

test('buildTaskWorkbenchSummary recommends design actions after review is complete', () => {
  const summary = buildTaskWorkbenchSummary({
    moduleSessions: {
      review: {
        requirement: '登录失败重试与锁定规则',
        runStatus: 'done',
        result: '{"reports":{}}',
      },
    },
    reviewFindings: [
      {
        risk_level: 'H',
        category: '逻辑缺陷',
        description: '锁定阈值不明确',
        suggestion: '补充阈值定义',
      },
    ],
    requirementContextId: 'ctx-1',
  })

  assert.equal(summary.currentStage, 'design')
  assert.equal(summary.riskCount, 1)
  assert.equal(summary.nextActions[0]?.navId, 'test-cases')
  assert.equal(summary.sourceLabel, '最近上下文')
})

test('buildTaskWorkbenchSummary keeps source label minimal when task is empty', () => {
  const summary = buildTaskWorkbenchSummary({
    moduleSessions: {},
    reviewFindings: [],
    requirementContextId: null,
  })

  assert.equal(summary.currentStage, 'import')
  assert.equal(summary.sourceLabel, '待导入')
})

test('buildTaskWorkbenchSummary moves to automation after design assets are ready', () => {
  const summary = buildTaskWorkbenchSummary({
    moduleSessions: {
      review: {
        requirement: '支付退款流程优化',
        runStatus: 'done',
        result: '{"reports":{}}',
      },
      'test-case': {
        requirement: '支付退款流程优化',
        runStatus: 'done',
        result: '{"items":[]}',
      },
    },
  })

  assert.equal(summary.currentStage, 'automation')
  assert.equal(summary.primaryAction.navId, 'ui-auto')
})

test('buildTaskWorkbenchSummary moves to deliver when automation asset is ready', () => {
  const summary = buildTaskWorkbenchSummary({
    moduleSessions: {
      review: {
        requirement: '账号注销流程',
        runStatus: 'done',
        result: '{"reports":{}}',
      },
      'test-case': {
        requirement: '账号注销流程',
        runStatus: 'done',
        result: '{"items":[]}',
      },
      'ui-auto': {
        requirement: '账号注销流程',
        runStatus: 'done',
        result: '# 自动化脚本',
      },
    },
  })

  assert.equal(summary.currentStage, 'deliver')
  assert.equal(summary.primaryAction.navId, 'test-cases')
})

test('buildSeededSessionPatch only seeds non-empty requirement', () => {
  assert.deepEqual(buildSeededSessionPatch('   '), {})
  assert.deepEqual(buildSeededSessionPatch('登录流程', 'grid'), {
    requirement: '登录流程',
    activeTab: 'grid',
  })
})

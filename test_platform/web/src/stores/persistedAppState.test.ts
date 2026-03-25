import test from 'node:test'
import assert from 'node:assert/strict'

import { buildPersistedAppState, sanitizePersistedModuleSessions } from './persistedAppState.ts'

test('sanitizePersistedModuleSessions removes oversized result payload and execution logs', () => {
  const sessions = sanitizePersistedModuleSessions({
    review: {
      requirement: '登录失败重试规则',
      result: '{"reports":{"test":{"content":"很长的结果"}}}',
      error: '超时',
      runStatus: 'done',
      activeTab: 'report',
      downloadBaseName: '登录需求',
      eventLogs: [
        { type: 'progress', stage: 'reading', message: '读取文档', sequence: 1 },
      ],
      options: { depth: 'deep' },
    },
  })

  assert.deepEqual(sessions, {
    review: {
      requirement: '登录失败重试规则',
      error: '超时',
      runStatus: 'done',
      activeTab: 'report',
      downloadBaseName: '登录需求',
      options: { depth: 'deep' },
    },
  })
})

test('buildPersistedAppState sanitizes module sessions and task snapshot copies together', () => {
  const state = buildPersistedAppState({
    activeNavId: 'review',
    activeEnvironment: 'test',
    globalVariables: {},
    expertConflictDecision: null,
    expertDecisionReason: null,
    focusedRowId: null,
    density: 'standard',
    appearance: 'light',
    sidebarCollapsed: false,
    topBarCollapsed: false,
    collaborationRailCollapsed: false,
    sidebarGroupCollapsed: {},
    requirementContextId: 'ctx-1',
    moduleSessions: {
      review: {
        requirement: '登录失败重试规则',
        result: '{"reports":{}}',
        eventLogs: [{ type: 'progress', stage: 'done', message: '完成', sequence: 1 }],
        runStatus: 'done',
      },
    },
    taskSnapshots: [
      {
        id: 'ctx:1',
        title: '登录失败重试规则',
        requirement: '登录失败重试规则',
        sourceLabel: '当前输入',
        currentStage: 'review',
        currentStageLabel: '风险评审',
        riskCount: 1,
        hasContext: true,
        primaryNavId: 'review',
        updatedAt: '2026-03-23T00:00:00.000Z',
        reviewFindings: [
          {
            risk_level: 'H',
            category: '逻辑缺陷',
            description: '锁定阈值不明确',
            suggestion: '补充阈值定义',
          },
        ],
        requirementContextId: 'ctx-1',
        moduleSessions: {
          review: {
            requirement: '登录失败重试规则',
            result: '{"reports":{}}',
            eventLogs: [{ type: 'progress', stage: 'done', message: '完成', sequence: 1 }],
            runStatus: 'done',
          },
        },
      },
    ],
  })

  assert.equal(state.moduleSessions.review?.result, undefined)
  assert.equal(state.moduleSessions.review?.eventLogs, undefined)
  assert.equal(state.taskSnapshots[0]?.moduleSessions.review?.result, undefined)
  assert.equal(state.taskSnapshots[0]?.moduleSessions.review?.eventLogs, undefined)
  assert.equal(state.taskSnapshots[0]?.moduleSessions.review?.requirement, '登录失败重试规则')
})

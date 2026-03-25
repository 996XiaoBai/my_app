import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildTaskSnapshot,
  buildTaskSnapshotId,
  upsertTaskSnapshot,
} from './taskSnapshots.ts'

test('buildTaskSnapshotId prefers context id when available', () => {
  assert.equal(buildTaskSnapshotId('登录失败重试与锁定规则', 'ctx-login-1'), 'ctx:ctx-login-1')
})

test('buildTaskSnapshot returns null when no requirement or context exists', () => {
  const snapshot = buildTaskSnapshot({
    moduleSessions: {},
    reviewFindings: [],
    requirementContextId: null,
    updatedAt: '2026-03-19T10:00:00.000Z',
  })

  assert.equal(snapshot, null)
})

test('buildTaskSnapshot stores stage, nav and cloned module sessions', () => {
  const snapshot = buildTaskSnapshot({
    moduleSessions: {
      review: {
        requirement: '登录失败重试与锁定规则',
        runStatus: 'done',
        result: '{"reports":{}}',
      },
      'test-case': {
        requirement: '登录失败重试与锁定规则',
        runStatus: 'done',
        result: '{"items":[]}',
      },
    },
    reviewFindings: [
      {
        risk_level: 'H',
        category: '逻辑缺陷',
        description: '锁定阈值不明确',
        suggestion: '补齐阈值定义',
      },
    ],
    requirementContextId: 'ctx-login-1',
    updatedAt: '2026-03-19T10:00:00.000Z',
  })

  assert.ok(snapshot)
  assert.equal(snapshot?.currentStage, 'automation')
  assert.equal(snapshot?.primaryNavId, 'ui-auto')
  assert.equal(snapshot?.riskCount, 1)
  assert.equal(snapshot?.moduleSessions.review?.requirement, '登录失败重试与锁定规则')
})

test('upsertTaskSnapshot replaces duplicate task and keeps latest first', () => {
  const first = buildTaskSnapshot({
    moduleSessions: {
      review: { requirement: '登录规则', runStatus: 'done', result: '{"reports":{}}' },
    },
    updatedAt: '2026-03-19T09:00:00.000Z',
  })
  const second = buildTaskSnapshot({
    moduleSessions: {
      review: { requirement: '支付退款流程', runStatus: 'done', result: '{"reports":{}}' },
    },
    updatedAt: '2026-03-19T10:00:00.000Z',
  })
  const updatedFirst = buildTaskSnapshot({
    moduleSessions: {
      review: { requirement: '登录规则', runStatus: 'done', result: '{"reports":{}}' },
      'test-case': { requirement: '登录规则', runStatus: 'done', result: '{"items":[]}' },
    },
    updatedAt: '2026-03-19T11:00:00.000Z',
  })

  const merged = upsertTaskSnapshot(
    upsertTaskSnapshot([], first!),
    second!
  )
  const updatedMerged = upsertTaskSnapshot(merged, updatedFirst!)

  assert.equal(updatedMerged.length, 2)
  assert.equal(updatedMerged[0]?.title, '登录规则')
  assert.equal(updatedMerged[0]?.currentStage, 'automation')
  assert.equal(updatedMerged[1]?.title, '支付退款流程')
})

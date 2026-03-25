import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clearRecoveredBackendErrors,
  isBackendUnavailableMessage,
  mergeModuleSession,
  parseStoredModulePayload,
  resolveModuleSession,
  serializeModuleSessionResult,
} from './moduleSession.ts'

test('mergeModuleSession keeps previous result when only tab changes', () => {
  const merged = mergeModuleSession(
    {
      requirement: '原始需求',
      result: '{"items":[]}',
      activeTab: 'grid',
      runStatus: 'done',
      eventLogs: [{ type: 'progress', stage: 'done', message: 'done', sequence: 1 }],
    },
    {
      activeTab: 'markdown',
    }
  )

  assert.equal(merged.result, '{"items":[]}')
  assert.equal(merged.activeTab, 'markdown')
  assert.equal(merged.runStatus, 'done')
  assert.equal(merged.eventLogs?.length, 1)
})

test('resolveModuleSession returns defaults for empty session', () => {
  const resolved = resolveModuleSession(undefined, {
    runStatus: 'idle',
    activeTab: 'structured',
    options: {
      view: 'summary',
    },
  })

  assert.equal(resolved.requirement, '')
  assert.equal(resolved.result, null)
  assert.equal(resolved.error, null)
  assert.equal(resolved.runStatus, 'idle')
  assert.equal(resolved.activeTab, 'structured')
  assert.deepEqual(resolved.eventLogs, [])
  assert.deepEqual(resolved.options, { view: 'summary' })
})

test('resolveModuleSession preserves stored state and merges options', () => {
  const resolved = resolveModuleSession(
    {
      requirement: '分析输入',
      result: '{"items":[1]}',
      error: '旧错误',
      runStatus: 'done',
      activeTab: 'markdown',
      eventLogs: [{ type: 'progress', stage: 'done', message: 'done', sequence: 2 }],
      options: {
        view: 'detail',
      },
    },
    {
      runStatus: 'idle',
      activeTab: 'structured',
      options: {
        view: 'summary',
        density: 'comfortable',
      },
    }
  )

  assert.equal(resolved.requirement, '分析输入')
  assert.equal(resolved.result, '{"items":[1]}')
  assert.equal(resolved.error, '旧错误')
  assert.equal(resolved.runStatus, 'done')
  assert.equal(resolved.activeTab, 'markdown')
  assert.equal(resolved.eventLogs.length, 1)
  assert.deepEqual(resolved.options, {
    view: 'detail',
    density: 'comfortable',
  })
})

test('serializeModuleSessionResult stringifies object payloads', () => {
  const value = serializeModuleSessionResult({
    reports: {
      general: {
        label: '评审报告',
        content: 'ok',
      },
    },
  })

  assert.equal(
    value,
    '{"reports":{"general":{"label":"评审报告","content":"ok"}}}'
  )
})

test('parseStoredModulePayload returns fallback for invalid json', () => {
  const parsed = parseStoredModulePayload('not-json', { ok: false })

  assert.deepEqual(parsed, { ok: false })
})

test('isBackendUnavailableMessage detects stale connectivity errors', () => {
  assert.equal(
    isBackendUnavailableMessage('后端服务不可达：请确认 http://localhost:8000 已启动且可访问。'),
    true
  )
  assert.equal(isBackendUnavailableMessage('生成失败'), false)
})

test('clearRecoveredBackendErrors removes stale backend unreachable module errors only', () => {
  const cleared = clearRecoveredBackendErrors({
    review: {
      runStatus: 'error',
      error: '后端服务不可达：请确认 http://localhost:8000 已启动且可访问。',
    },
    'test-case': {
      runStatus: 'error',
      error: '未识别到有效 TAPD Story ID，请检查输入。',
    },
  })

  assert.deepEqual(cleared, {
    review: {
      runStatus: 'idle',
      error: null,
    },
    'test-case': {
      runStatus: 'error',
      error: '未识别到有效 TAPD Story ID，请检查输入。',
    },
  })
})

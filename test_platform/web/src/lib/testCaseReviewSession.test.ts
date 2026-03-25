import test from 'node:test'
import assert from 'node:assert/strict'

import { buildTestCaseReviewSessionFromTestCase } from './testCaseReviewSession.ts'

test('buildTestCaseReviewSessionFromTestCase seeds review session with current case result', () => {
  const session = buildTestCaseReviewSessionFromTestCase({
    requirement: '需求：支持账号密码登录和失败锁定。',
    result: '{"items":[{"id":"case-1","title":"登录成功"}]}',
  })

  assert.deepEqual(session, {
    requirement: '需求：支持账号密码登录和失败锁定。',
    result: null,
    runStatus: 'idle',
    activeTab: 'overview',
    error: null,
    eventLogs: [],
    options: {
      caseInputMode: 'linked',
      caseResult: '{"items":[{"id":"case-1","title":"登录成功"}]}',
      caseSource: 'generated',
    },
  })
})

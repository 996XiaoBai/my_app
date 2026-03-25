import test from 'node:test'
import assert from 'node:assert/strict'

import { buildTestCaseSessionFromUIAuto } from './uiAutoToTestCase.ts'

test('buildTestCaseSessionFromUIAuto resets test-case session to a completed markdown result', () => {
  const session = buildTestCaseSessionFromUIAuto({
    requirement: '帖子详情页评论入口调整',
    result: '# UI 自动化生成的测试用例',
  })

  assert.deepEqual(session, {
    requirement: '帖子详情页评论入口调整',
    result: '# UI 自动化生成的测试用例',
    runStatus: 'done',
    activeTab: 'markdown',
    error: null,
    eventLogs: [],
  })
})

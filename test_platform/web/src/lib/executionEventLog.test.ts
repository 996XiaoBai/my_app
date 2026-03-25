import test from 'node:test'
import assert from 'node:assert/strict'

import {
  classifyExecutionEventGroup,
  groupExecutionEvents,
  type ExecutionEventGroupId,
} from './executionEventLog.ts'
import type { RunProgressEvent } from './api.ts'

test('classify execution events into parse/extract/generate/organize buckets', () => {
  assert.equal(classifyExecutionEventGroup('reading', '📄 正在解析文档并提取上下文...'), 'parsing')
  assert.equal(classifyExecutionEventGroup('decomposing', '🧩 已完成需求模块拆解...'), 'extracting')
  assert.equal(classifyExecutionEventGroup('generating', '🔌 正在解析接口并生成 Pytest 脚本...'), 'generating')
  assert.equal(classifyExecutionEventGroup('grading', '📌 风险等级划分与汇总...'), 'organizing')
})

test('group execution events keeps fixed section order and event membership', () => {
  const events: RunProgressEvent[] = [
    { type: 'progress', stage: 'matching', message: '🧠 正在匹配工程化测试策略...', sequence: 4 },
    { type: 'progress', stage: 'reading', message: '📄 正在解析文档并提取上下文...', sequence: 1 },
    { type: 'progress', stage: 'grading', message: '📌 风险等级划分与汇总...', sequence: 5 },
    { type: 'progress', stage: 'decomposing', message: '🧩 已完成需求模块拆解...', sequence: 3 },
  ]

  const groups = groupExecutionEvents(events)

  assert.deepEqual(
    groups.map((group) => group.id),
    ['parsing', 'extracting', 'generating', 'organizing', 'other'] satisfies ExecutionEventGroupId[]
  )
  assert.equal(groups[0].events[0]?.sequence, 1)
  assert.equal(groups[1].events[0]?.sequence, 3)
  assert.equal(groups[2].events[0]?.sequence, 4)
  assert.equal(groups[3].events[0]?.sequence, 5)
  assert.equal(groups[4].events.length, 0)
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildGenericModuleMarkdownFilename, getGenericModuleHistoryTypes } from './genericModule.ts'

test('getGenericModuleHistoryTypes returns module id for history lookup', () => {
  assert.deepEqual(getGenericModuleHistoryTypes('api-test'), ['api-test'])
  assert.deepEqual(getGenericModuleHistoryTypes('log-diagnosis'), ['log-diagnosis'])
})

test('buildGenericModuleMarkdownFilename appends md suffix', () => {
  assert.equal(buildGenericModuleMarkdownFilename('接口测试'), '接口测试.md')
  assert.equal(buildGenericModuleMarkdownFilename('性能压测.md'), '性能压测.md')
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { parseTapdInput } from './tapdInput.ts'

test('parseTapdInput detects numeric story id', () => {
  const parsed = parseTapdInput('1120340332001008677')

  assert.equal(parsed.kind, 'story-id')
  assert.equal(parsed.storyId, '1120340332001008677')
})

test('parseTapdInput extracts story id from tapd link', () => {
  const parsed = parseTapdInput('https://www.tapd.cn/20340332/stories/view/1120340332001008677')

  assert.equal(parsed.kind, 'tapd-link')
  assert.equal(parsed.storyId, '1120340332001008677')
})

test('parseTapdInput identifies wecom doc link', () => {
  const parsed = parseTapdInput('https://doc.weixin.qq.com/doc/w3_ARKaYQafADoCNnNbk1IznThOiqgi')

  assert.equal(parsed.kind, 'wecom-doc-link')
  assert.equal(parsed.storyId, null)
})

test('parseTapdInput identifies unsupported links', () => {
  const parsed = parseTapdInput('https://example.com/feature/123')

  assert.equal(parsed.kind, 'unsupported-link')
  assert.equal(parsed.storyId, null)
})

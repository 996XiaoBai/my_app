import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveWorkbenchPageKind } from './pageRouting.ts'

test('resolveWorkbenchPageKind routes api-test to dedicated workbench page', () => {
  assert.equal(resolveWorkbenchPageKind('api-test'), 'api-test')
  assert.equal(resolveWorkbenchPageKind('test-case-review'), 'test-case-review')
  assert.equal(resolveWorkbenchPageKind('test-data'), 'generic')
  assert.equal(resolveWorkbenchPageKind('dashboard'), 'dashboard')
  assert.equal(resolveWorkbenchPageKind('unknown-module'), 'unknown')
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildApiUrl, formatApiHttpError, isContextNotFoundDetail } from './apiConfig.ts'

test('buildApiUrl uses configured API base', () => {
  assert.equal(buildApiUrl('/health'), 'http://localhost:8000/health')
  assert.equal(buildApiUrl('run/stream'), 'http://localhost:8000/run/stream')
})

test('formatApiHttpError returns actionable message for 404', () => {
  const message = formatApiHttpError(404, 'Not Found')

  assert.match(message, /后端接口不存在/)
  assert.match(message, /api_server\.py/)
})

test('isContextNotFoundDetail detects backend context missing errors', () => {
  assert.equal(isContextNotFoundDetail('Error: context not found'), true)
  assert.equal(isContextNotFoundDetail('上下文不存在，请重新创建'), true)
  assert.equal(isContextNotFoundDetail('random error'), false)
})

test('formatApiHttpError maps context missing detail to localized guidance', () => {
  const message = formatApiHttpError(400, 'Error: context not found')

  assert.match(message, /上下文已失效/)
  assert.match(message, /自动回退/)
})

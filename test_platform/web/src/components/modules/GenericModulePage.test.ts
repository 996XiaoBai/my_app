import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('GenericModulePage no longer carries dedicated api-test rendering branches', () => {
  const source = readFileSync(new URL('./GenericModulePage.tsx', import.meta.url), 'utf-8')

  assert.equal(source.includes("id === 'api-test'"), false)
  assert.equal(source.includes('ApiTestExecutionPanel'), false)
  assert.equal(source.includes('parseApiTestPayload'), false)
})

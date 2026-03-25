import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveAppStoreStorage } from './browserStorage.ts'

test('resolveAppStoreStorage skips persistence when browser storage is unavailable', () => {
  assert.equal(resolveAppStoreStorage(undefined), undefined)
  assert.equal(resolveAppStoreStorage({}), undefined)
  assert.equal(resolveAppStoreStorage({ localStorage: {} }), undefined)
})

test('resolveAppStoreStorage creates persist storage when localStorage api is complete', () => {
  const records = new Map<string, string>()
  const storage = resolveAppStoreStorage({
    localStorage: {
      getItem: (name) => records.get(name) ?? null,
      setItem: (name, value) => {
        records.set(name, value)
      },
      removeItem: (name) => {
        records.delete(name)
      },
    },
  })

  assert.ok(storage)

  storage.setItem('test-platform-storage', {
    state: { activeNavId: 'dashboard' },
    version: 0,
  })
  assert.deepEqual(storage.getItem('test-platform-storage'), {
    state: { activeNavId: 'dashboard' },
    version: 0,
  })

  storage.removeItem('test-platform-storage')
  assert.equal(storage.getItem('test-platform-storage'), null)
})

test('resolveAppStoreStorage swallows quota exceeded errors and clears stale payload', () => {
  const records = new Map<string, string>([['test-platform-storage', '{"state":{"activeNavId":"review"},"version":0}']])
  const storage = resolveAppStoreStorage({
    localStorage: {
      getItem: (name) => records.get(name) ?? null,
      setItem: () => {
        const error = new Error('Setting the value of test-platform-storage exceeded the quota.')
        error.name = 'QuotaExceededError'
        throw error
      },
      removeItem: (name) => {
        records.delete(name)
      },
    },
  })

  assert.ok(storage)
  assert.doesNotThrow(() => {
    storage.setItem('test-platform-storage', {
      state: { activeNavId: 'dashboard' },
      version: 0,
    })
  })
  assert.equal(records.get('test-platform-storage'), undefined)
})

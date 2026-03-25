import test from 'node:test'
import assert from 'node:assert/strict'

import { notifyHistoryRefresh, subscribeHistoryRefresh } from './historyRefresh.ts'

test('history refresh subscribers are notified once per event', () => {
  let callCount = 0
  const unsubscribe = subscribeHistoryRefresh(() => {
    callCount += 1
  })

  notifyHistoryRefresh()
  unsubscribe()
  notifyHistoryRefresh()

  assert.equal(callCount, 1)
})

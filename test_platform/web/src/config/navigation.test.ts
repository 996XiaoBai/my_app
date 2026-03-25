import test from 'node:test'
import assert from 'node:assert/strict'

import { NAV_GROUPS, VISIBLE_NAV_ITEMS } from './navigation.ts'

test('automation group stays visible in sidebar navigation', () => {
  const automationGroup = NAV_GROUPS.find((group) => group.title === '自动化')

  assert.ok(automationGroup)
  assert.deepEqual(
    automationGroup.items.map((item) => item.id),
    ['api-test', 'perf-test', 'ui-auto']
  )
})

test('automation entries are included in visible navigation items', () => {
  const visibleIds = VISIBLE_NAV_ITEMS.map((item) => item.id)

  assert.ok(visibleIds.includes('api-test'))
  assert.ok(visibleIds.includes('perf-test'))
  assert.ok(visibleIds.includes('ui-auto'))
})

test('test-data entry is visible as a stable module', () => {
  const testDataItem = VISIBLE_NAV_ITEMS.find((item) => item.id === 'test-data')

  assert.ok(testDataItem)
  assert.equal(testDataItem.label, '测试数据准备')
  assert.equal(testDataItem.availability, 'stable')
})

test('test-case-review entry is visible as a stable module', () => {
  const reviewItem = VISIBLE_NAV_ITEMS.find((item) => item.id === 'test-case-review')

  assert.ok(reviewItem)
  assert.equal(reviewItem.label, '测试用例评审')
  assert.equal(reviewItem.availability, 'stable')
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildReviewRoleSelectionSummary,
  clearReviewRoleSelection,
  getDefaultReviewRoleIds,
  resetReviewRoleSelection,
  validateReviewRoleSelection,
  type ReviewRoleOption,
} from './reviewRoleSelect.ts'

const REVIEW_ROLE_OPTIONS: ReviewRoleOption[] = [
  { id: 'test', label: '资深测试工程师' },
  { id: 'product', label: '产品经理' },
  { id: 'tech', label: '技术负责人' },
  { id: 'design', label: '设计视角' },
]

test('getDefaultReviewRoleIds 默认返回资深测试工程师角色', () => {
  assert.deepEqual(getDefaultReviewRoleIds(), ['test'])
})

test('buildReviewRoleSelectionSummary 在未选择角色时返回占位信息', () => {
  assert.deepEqual(buildReviewRoleSelectionSummary([], REVIEW_ROLE_OPTIONS), {
    badgeLabels: [],
    overflowCount: 0,
    text: '请选择评审角色',
  })
})

test('buildReviewRoleSelectionSummary 在单角色时返回单个短标签', () => {
  assert.deepEqual(buildReviewRoleSelectionSummary(['test'], REVIEW_ROLE_OPTIONS), {
    badgeLabels: ['测试'],
    overflowCount: 0,
    text: '测试',
  })
})

test('buildReviewRoleSelectionSummary 在双角色时返回两个短标签', () => {
  assert.deepEqual(buildReviewRoleSelectionSummary(['test', 'product'], REVIEW_ROLE_OPTIONS), {
    badgeLabels: ['测试', '产品'],
    overflowCount: 0,
    text: '测试 / 产品',
  })
})

test('buildReviewRoleSelectionSummary 在超过两个角色时折叠为加N形式', () => {
  assert.deepEqual(buildReviewRoleSelectionSummary(['test', 'product', 'tech', 'design'], REVIEW_ROLE_OPTIONS), {
    badgeLabels: ['测试', '产品'],
    overflowCount: 2,
    text: '测试 / 产品 +2',
  })
})

test('clearReviewRoleSelection 返回空数组', () => {
  assert.deepEqual(clearReviewRoleSelection(), [])
})

test('resetReviewRoleSelection 恢复为默认角色', () => {
  assert.deepEqual(resetReviewRoleSelection(), ['test'])
})

test('validateReviewRoleSelection 在角色为空时返回错误文案', () => {
  assert.equal(validateReviewRoleSelection([]), '请至少选择一个评审角色')
})

test('validateReviewRoleSelection 在至少选择一个角色时通过校验', () => {
  assert.equal(validateReviewRoleSelection(['test']), null)
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getAppearanceDocumentState,
  getAppearanceProfile,
  toggleAppearance,
  type Appearance,
} from './appearance.ts'

test('toggleAppearance switches between dark and light modes', () => {
  assert.equal(toggleAppearance('dark'), 'light')
  assert.equal(toggleAppearance('light'), 'dark')
})

test('getAppearanceDocumentState exposes html attributes for light mode', () => {
  const state = getAppearanceDocumentState('light' satisfies Appearance)

  assert.deepEqual(state, {
    appearance: 'light',
    colorScheme: 'light',
  })
})

test('getAppearanceProfile exposes mode metadata for dark flagship theme', () => {
  const profile = getAppearanceProfile('dark')

  assert.deepEqual(profile, {
    appearance: 'dark',
    label: '深色控制台',
    shortLabel: 'DARK',
    description: '工业控制台风格，强调聚焦感与高密度信息操作。',
    emphasis: 'flagship',
  })
})

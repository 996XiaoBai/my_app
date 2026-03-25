import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getDensityLabel,
  getDensityShortLabel,
  getNextDensity,
} from './uiDensity.ts'

test('getNextDensity cycles through comfortable standard and compact', () => {
  assert.equal(getNextDensity('comfortable'), 'standard')
  assert.equal(getNextDensity('standard'), 'compact')
  assert.equal(getNextDensity('compact'), 'comfortable')
})

test('density labels stay concise and readable', () => {
  assert.equal(getDensityLabel('comfortable'), '宽松')
  assert.equal(getDensityLabel('standard'), '标准')
  assert.equal(getDensityLabel('compact'), '紧凑')
  assert.equal(getDensityShortLabel('comfortable'), 'COMFY')
  assert.equal(getDensityShortLabel('standard'), 'STD')
  assert.equal(getDensityShortLabel('compact'), 'COMPACT')
})

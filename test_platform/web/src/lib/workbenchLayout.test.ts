import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getCollaborationRailWidth,
  getSidebarFooterControlsClassName,
  getSidebarWidth,
  getTopBarHeight,
  getWorkbenchRailWrapperClassName,
  getWorkbenchResultPanelClassName,
  getWorkbenchStackClassName,
} from './workbenchLayout.ts'

test('getTopBarHeight returns compact height when collapsed', () => {
  assert.equal(getTopBarHeight(false), 56)
  assert.equal(getTopBarHeight(true), 40)
})

test('getCollaborationRailWidth returns compact width when collapsed', () => {
  assert.equal(getCollaborationRailWidth(false), '320px')
  assert.equal(getCollaborationRailWidth(true), '72px')
})

test('getSidebarWidth responds to collapse state and density mode', () => {
  assert.equal(getSidebarWidth(false, 'comfortable'), '288px')
  assert.equal(getSidebarWidth(true, 'comfortable'), '76px')
  assert.equal(getSidebarWidth(false, 'standard'), '264px')
  assert.equal(getSidebarWidth(true, 'standard'), '72px')
  assert.equal(getSidebarWidth(false, 'compact'), '240px')
  assert.equal(getSidebarWidth(true, 'compact'), '64px')
})

test('getSidebarFooterControlsClassName keeps footer controls stacked to avoid overlap', () => {
  assert.equal(
    getSidebarFooterControlsClassName(),
    'grid grid-cols-1 gap-2 overflow-hidden'
  )
})

test('getWorkbenchStackClassName returns vertical flow layout for workbench pages', () => {
  assert.equal(getWorkbenchStackClassName(), 'space-y-5')
})

test('getWorkbenchResultPanelClassName keeps result area stacked and scrollable', () => {
  assert.equal(
    getWorkbenchResultPanelClassName(),
    'console-panel flex min-h-[720px] flex-col overflow-hidden'
  )
  assert.equal(
    getWorkbenchResultPanelClassName('block'),
    'console-panel min-h-[720px] overflow-hidden'
  )
})

test('getWorkbenchRailWrapperClassName keeps collapsed rail aligned to the right in stacked mode', () => {
  assert.equal(getWorkbenchRailWrapperClassName(false), 'min-w-0')
  assert.equal(getWorkbenchRailWrapperClassName(true), 'flex justify-end')
})

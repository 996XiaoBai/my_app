import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSidebarGroupDigests,
  createInitialSidebarGroupState,
  ensureSidebarGroupExpanded,
  ensureSidebarGroupExpandedOnNavChange,
  setSidebarGroupState,
  toggleSidebarGroupState,
} from './sidebarGroups.ts'

test('createInitialSidebarGroupState initializes all groups as expanded', () => {
  const state = createInitialSidebarGroupState(['智能分析', '测试工程'])

  assert.deepEqual(state, {
    智能分析: false,
    测试工程: false,
  })
})

test('toggleSidebarGroupState flips one target group only', () => {
  const next = toggleSidebarGroupState(
    {
      智能分析: false,
      测试工程: true,
    },
    '智能分析'
  )

  assert.deepEqual(next, {
    智能分析: true,
    测试工程: true,
  })
})

test('ensureSidebarGroupExpanded reopens the active group', () => {
  const next = ensureSidebarGroupExpanded(
    {
      智能分析: true,
      测试工程: false,
    },
    '智能分析'
  )

  assert.deepEqual(next, {
    智能分析: false,
    测试工程: false,
  })
})

test('ensureSidebarGroupExpandedOnNavChange keeps user-collapsed active group closed until nav changes', () => {
  const state = {
    智能分析: true,
    测试工程: false,
  }

  assert.equal(
    ensureSidebarGroupExpandedOnNavChange(state, '智能分析', 'review', 'review'),
    state
  )

  assert.deepEqual(
    ensureSidebarGroupExpandedOnNavChange(state, '智能分析', 'dashboard', 'review'),
    {
      智能分析: false,
      测试工程: false,
    }
  )
})

test('setSidebarGroupState is stable when target state is unchanged', () => {
  const state = {
    智能分析: false,
  }

  assert.equal(setSidebarGroupState(state, '智能分析', false), state)
})

test('buildSidebarGroupDigests summarizes count and highlights active group', () => {
  const digests = buildSidebarGroupDigests(
    [
      {
        title: '智能分析',
        items: [{ id: 'review' }, { id: 'req-analysis' }],
      },
      {
        title: '自动化',
        items: [{ id: 'ui-auto' }],
      },
    ],
    'ui-auto'
  )

  assert.deepEqual(digests, [
    { title: '智能分析', countLabel: '2 项', tone: 'neutral' },
    { title: '自动化', countLabel: '1 项', tone: 'accent' },
  ])
})

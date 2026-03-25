import test from 'node:test'
import assert from 'node:assert/strict'

import { getTestCaseItems, getTestCaseMarkdown, getVisibleTestCaseColumns, sortTestCasesByPriority } from './testCaseResult.ts'

test('getTestCaseMarkdown prefers backend markdown payload', () => {
  const markdown = getTestCaseMarkdown({
    items: [],
    summary: 'done',
    markdown: '# 自定义测试用例\n\n内容'
  })

  assert.equal(markdown, '# 自定义测试用例\n\n内容')
})

test('sortTestCasesByPriority orders by P0-P3', () => {
  const sorted = sortTestCasesByPriority([
    { id: '3', title: 'low', priority: 'P3', module: 'A', steps: [] },
    { id: '2', title: 'middle', priority: 'P1', module: 'A', steps: [] },
    { id: '1', title: 'highest', priority: 'P0', module: 'A', steps: [] },
  ])

  assert.deepEqual(sorted.map((item) => item.priority), ['P0', 'P1', 'P3'])
})

test('getTestCaseMarkdown nests steps under step description', () => {
  const markdown = getTestCaseMarkdown({
    summary: 'done',
    items: [
      {
        id: '1',
        title: '登录成功',
        priority: 'P1',
        module: '登录',
        steps: [
          { action: '输入账号', expected: '账号输入成功' },
          { action: '点击登录', expected: '进入首页' },
        ],
      },
    ],
  })

  assert.match(markdown, /- 步骤描述：\n  1\. 步骤：输入账号\n     - 预期结果：账号输入成功/)
  assert.match(markdown, /  2\. 步骤：点击登录\n     - 预期结果：进入首页/)
})

test('getVisibleTestCaseColumns omits empty optional fields', () => {
  const columns = getVisibleTestCaseColumns([
    {
      id: '1',
      title: '登录成功',
      priority: 'P1',
      module: '登录',
      precondition: '',
      tags: '',
      remark: '',
      steps: [{ action: '输入账号', expected: '账号输入成功' }],
    },
  ])

  assert.deepEqual(columns, ['module', 'title', 'steps', 'priority'])
})

test('getVisibleTestCaseColumns follows the template field order', () => {
  const columns = getVisibleTestCaseColumns([
    {
      id: '1',
      title: '登录成功',
      priority: 'P0',
      module: '登录',
      precondition: '账号可用',
      tags: '',
      remark: '',
      steps: [{ action: '输入账号', expected: '账号输入成功' }],
    },
  ])

  assert.deepEqual(columns, ['module', 'title', 'precondition', 'steps', 'priority'])
})

test('getTestCaseItems flattens hierarchical modules when items are absent', () => {
  const items = getTestCaseItems({
    summary: 'done',
    items: [],
    modules: [
      {
        name: '账号',
        path: '账号',
        cases: [],
        children: [
          {
            name: '登录',
            path: '账号/登录',
            cases: [
              {
                id: '1',
                title: '登录成功',
                priority: 'P1',
                module: '账号/登录',
                steps: [{ action: '输入账号', expected: '账号输入成功' }],
              },
            ],
            children: [],
          },
        ],
      },
    ],
  })

  assert.equal(items.length, 1)
  assert.equal(items[0]?.module, '账号/登录')
  assert.equal(items[0]?.title, '登录成功')
})

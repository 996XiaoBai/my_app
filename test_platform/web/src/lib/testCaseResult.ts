import type { TestCaseItem, TestCaseModule, TestCasePriority, TestCaseSuite } from './contracts'

const PRIORITY_ORDER: Record<TestCasePriority, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
  P3: 3,
}

const COLUMN_ORDER = ['module', 'title', 'precondition', 'steps', 'priority', 'tags', 'remark'] as const
const REQUIRED_COLUMNS = new Set(['priority', 'module', 'title', 'steps'])

function hasValue(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.length > 0
  }
  return String(value ?? '').trim().length > 0
}

function normalizeExpectedValue(expected: string | undefined): string {
  return String(expected || '').trim() || '待补充预期结果'
}

function flattenTestCaseModules(modules: TestCaseModule[]): TestCaseItem[] {
  const items: TestCaseItem[] = []

  const walk = (nodes: TestCaseModule[]) => {
    nodes.forEach((node) => {
      items.push(...normalizeTestCaseItems(node.cases || []))
      if (Array.isArray(node.children) && node.children.length > 0) {
        walk(node.children)
      }
    })
  }

  walk(modules)
  return items
}

export function normalizeTestCaseItems(items: TestCaseItem[]): TestCaseItem[] {
  return items.map((item) => ({
    ...item,
    steps: item.steps.map((step) => ({
      action: step.action,
      expected: normalizeExpectedValue(step.expected),
    })),
  }))
}

export function getTestCaseItems(payload: Pick<TestCaseSuite, 'items' | 'modules'>): TestCaseItem[] {
  const directItems = normalizeTestCaseItems(payload.items || [])
  if (directItems.length > 0) {
    return directItems
  }
  return flattenTestCaseModules(payload.modules || [])
}

export function sortTestCasesByPriority(items: TestCaseItem[]): TestCaseItem[] {
  return [...normalizeTestCaseItems(items)].sort((left, right) => {
    const leftRank = PRIORITY_ORDER[left.priority] ?? 99
    const rightRank = PRIORITY_ORDER[right.priority] ?? 99
    if (leftRank !== rightRank) {
      return leftRank - rightRank
    }
    return `${left.module}:${left.title}`.localeCompare(`${right.module}:${right.title}`, 'zh-CN')
  })
}

export function getVisibleTestCaseColumns(items: TestCaseItem[]): string[] {
  return COLUMN_ORDER.filter((key) => {
    if (REQUIRED_COLUMNS.has(key)) {
      return true
    }
    return items.some((item) => hasValue(item[key]))
  })
}

export function getTestCaseMarkdown(payload: TestCaseSuite): string {
  if (payload.markdown) {
    return payload.markdown
  }

  const items = sortTestCasesByPriority(getTestCaseItems(payload))
  const sections: string[] = ['# 智能测试用例', '']
  if (payload.summary) {
    sections.push(`> ${payload.summary}`, '')
  }

  let currentModule = ''
  for (const item of items) {
    if (item.module !== currentModule) {
      currentModule = item.module
      sections.push(`## 模块：${currentModule}`, '')
    }

    sections.push(`### case：${item.title}`)
    if (item.precondition) {
      sections.push(`- 前置条件：${item.precondition}`)
    }
    sections.push('- 步骤描述：')

    item.steps.forEach((step, index) => {
      sections.push(`  ${index + 1}. 步骤：${step.action}`)
      sections.push(`     - 预期结果：${step.expected}`)
    })

    sections.push(`- 用例等级：${item.priority}`)
    if (item.tags) {
      sections.push(`- 标签：${item.tags}`)
    }
    if (item.remark) {
      sections.push(`- 备注：${item.remark}`)
    }

    sections.push('', '---', '')
  }

  return sections.join('\n').trimEnd()
}

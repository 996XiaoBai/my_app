export interface NavItem {
  id: string
  label: string
  icon: string
  href: string
  availability?: 'stable' | 'preview'
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

export const ALL_NAV_GROUPS: NavGroup[] = [
  {
    title: '智能分析',
    items: [
      { id: 'review', label: '需求评审', icon: '📝', href: '/review', availability: 'stable' },
      { id: 'req-analysis', label: '需求分析', icon: '🔬', href: '/req-analysis', availability: 'stable' },
      { id: 'test-point', label: '测试点提取', icon: '🎯', href: '/test-point', availability: 'stable' },
      { id: 'impact', label: '影响面分析', icon: '⚡', href: '/impact', availability: 'preview' },
    ],
  },
  {
    title: '测试工程',
    items: [
      { id: 'test-cases', label: '测试用例', icon: '🧪', href: '/test-cases', availability: 'stable' },
      { id: 'test-case-review', label: '测试用例评审', icon: '🧾', href: '/test-case-review', availability: 'stable' },
      { id: 'test-plan', label: '测试方案', icon: '📅', href: '/test-plan', availability: 'preview' },
      { id: 'test-data', label: '测试数据准备', icon: '🏗️', href: '/test-data', availability: 'stable' },
      { id: 'log-diagnosis', label: '日志诊断', icon: '🔍', href: '/log-diagnosis', availability: 'preview' },
    ],
  },
  {
    title: '自动化',
    items: [
      { id: 'api-test', label: '接口测试', icon: '🔌', href: '/api-test', availability: 'stable' },
      { id: 'perf-test', label: '性能压测', icon: '🚀', href: '/perf-test', availability: 'stable' },
      { id: 'ui-auto', label: 'UI 自动化', icon: '🤖', href: '/ui-auto', availability: 'stable' },
    ],
  },
  {
    title: '效能看板',
    items: [
      { id: 'flowchart', label: '业务流程图', icon: '📊', href: '/flowchart', availability: 'stable' },
      { id: 'weekly-report', label: '周报生成', icon: '📰', href: '/weekly-report', availability: 'stable' },
    ],
  },
]

export const NAV_GROUPS: NavGroup[] = ALL_NAV_GROUPS.map((group) => ({
  ...group,
  items: group.items.filter((item) => item.availability !== 'preview'),
})).filter((group) => group.items.length > 0)

export const ALL_NAV_ITEMS: NavItem[] = ALL_NAV_GROUPS.flatMap((group) => group.items)
export const VISIBLE_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((group) => group.items)

export function findNavItem(id: string): NavItem | undefined {
  return ALL_NAV_ITEMS.find((item) => item.id === id)
}

export function isKnownNavId(id: string): boolean {
  return id === 'dashboard' || ALL_NAV_ITEMS.some((item) => item.id === id)
}

'use client'

import { useHotkeys } from 'react-hotkeys-hook'
import { useAppStore, NAV_GROUPS } from '@/stores/useAppStore'

/**
 * 全局快捷键管理器
 * 负责监听 J/K 导航、Enter 确认、以及 P/T/I 等功能直达键
 */
export default function ShortcutManager() {
  const { 
    moveNavFocus, 
    focusedNavIndex, 
    activeNavId,
    setActiveNav,
    toggleSidebar,
    openInsight,
    insightOpen,
    closeInsight,
    setFocusedNavIndex,
    activeFocusArea,
    setActiveFocusArea
  } = useAppStore()

  const flatNavItems = [
    { id: 'dashboard', label: '仪表盘' },
    ...NAV_GROUPS.flatMap(g => g.items)
  ]

  // Tab: 在侧边栏、主区域、Insight 之间跳转
  useHotkeys('tab', (e) => {
    e.preventDefault()
    const areas: ('SIDEBAR' | 'MAIN' | 'INSIGHT')[] = ['SIDEBAR', 'MAIN']
    if (insightOpen) areas.push('INSIGHT')
    
    const currentIndex = areas.indexOf(activeFocusArea)
    const nextArea = areas[(currentIndex + 1) % areas.length]
    setActiveFocusArea(nextArea)
    
    // 如果回到了侧边栏，重置焦点索引到当前激活的
    if (nextArea === 'SIDEBAR') {
      const activeIdx = flatNavItems.findIndex(i => i.id === activeNavId)
      setFocusedNavIndex(activeIdx)
    }
  })

  // J: 向下移动
  useHotkeys('j', (e) => {
    if (activeFocusArea !== 'SIDEBAR') return
    e.preventDefault()
    moveNavFocus(1)
  })

  // K: 向上移动
  useHotkeys('k', (e) => {
    if (activeFocusArea !== 'SIDEBAR') return
    e.preventDefault()
    moveNavFocus(-1)
  })

  // Enter: 选定当前 Focus 的项
  useHotkeys('enter', (e) => {
    if (focusedNavIndex >= 0 && focusedNavIndex < flatNavItems.length) {
      e.preventDefault()
      const target = flatNavItems[focusedNavIndex]
      setActiveNav(target.id)
    }
  })

  // P: 跳转需求评审 (Prompt Review)
  useHotkeys('p', (e) => {
    e.preventDefault()
    setActiveNav('review')
  })

  // T: 跳转测试用例 (Test Case)
  useHotkeys('t', (e) => {
    e.preventDefault()
    setActiveNav('test-cases')
  })

  // I: 开关 Insight 面板
  useHotkeys('i', (e) => {
    e.preventDefault()
    if (insightOpen) {
      closeInsight()
    } else {
      openInsight('AI 实时分析面板已唤起。')
    }
  })

  // B: 开关侧边栏 (Sidebar)
  useHotkeys('b', (e) => {
    e.preventDefault()
    toggleSidebar()
  })

  // ?: 显示快捷键帮助
  useHotkeys('shift+/', (e) => {
    e.preventDefault()
    openInsight(`
### ⌨️ 快捷键指南

**导航 (Focus: SIDEBAR)**
- \`j\` / \`k\` : 上下切换菜单项
- \`enter\` : 进入选中功能

**全局直达**
- \`p\` : 需求评审 (Prompt)
- \`t\` : 用例生成 (Test Case)
- \`i\` : 开关 Insight 面板
- \`b\` : 开关侧边栏 (Sidebar)
- \`⌘K\` : 全局搜索

**通用**
- \`tab\` : 在 [侧栏 / 主区 / 面板] 间切换焦点
- \`esc\` : 关闭浮窗 / 清除焦点
    `, 'info')
  })

  // Esc: 关闭所有弹窗
  useHotkeys('esc', () => {
    closeInsight()
    setFocusedNavIndex(-1)
  })

  return (
    <button 
      onClick={() => openInsight('请按 \`Shift + ?\` 呼出快捷键指南', 'info')}
      className="fixed bottom-6 right-6 z-50 w-10 h-10 rounded-full bg-[#14151A]/80 backdrop-blur-md border border-white/10 flex items-center justify-center text-[#8B949E] hover:text-[#8B5CF6] hover:border-[#8B5CF6]/40 transition-all hover:scale-110 shadow-2xl"
      title="快捷键帮助 (?)"
    >
      <span className="text-sm font-bold">?</span>
    </button>
  )
}

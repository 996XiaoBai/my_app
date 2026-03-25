'use client'

import { useEffect } from 'react'
import { useAppStore } from '@/stores/useAppStore'
import { syncAppearanceToDocument } from '@/lib/appearance'
import { getSidebarWidth, getTopBarHeight } from '@/lib/workbenchLayout'

/**
 * 布局外壳组件
 * 负责：
 * 1. 根据侧边栏折叠状态动态调整主内容区域的 margin
 * 2. 将密度模式 (comfortable/standard/compact) 同步到 <html> 元素的 data-density 属性
 */
export function LayoutShell({ children }: { children: React.ReactNode }) {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed)
  const topBarCollapsed = useAppStore((s) => s.topBarCollapsed)
  const density = useAppStore((s) => s.density)
  const appearance = useAppStore((s) => s.appearance)
  const topBarHeight = getTopBarHeight(topBarCollapsed)
  const sidebarWidth = getSidebarWidth(sidebarCollapsed, density)

  // 同步 density 到 <html> 元素，驱动 CSS 变量切换
  useEffect(() => {
    document.documentElement.setAttribute('data-density', density)
  }, [density])

  useEffect(() => {
    syncAppearanceToDocument(appearance)
  }, [appearance])

  return (
    <main
      className="min-h-screen transition-[margin-left] duration-300"
      style={{ paddingTop: `${topBarHeight}px`, marginLeft: sidebarWidth }}
    >
      <div className="px-4 py-5 lg:px-5 lg:py-6">{children}</div>
    </main>
  )
}

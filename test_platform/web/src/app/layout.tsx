import type { Metadata } from 'next'
import './globals.css'
import TopBar from '@/components/layout/TopBar'
import Sidebar from '@/components/layout/Sidebar'
import InsightPanel from '@/components/layout/InsightPanel'
import CommandPalette from '@/components/layout/CommandPalette'
import ShortcutManager from '@/components/layout/ShortcutManager'
import NavigationStateSync from '@/components/layout/NavigationStateSync'
import ViewportListener from '@/components/layout/ViewportListener'
import { LayoutShell } from './LayoutShell'

export const metadata: Metadata = {
  title: '测试平台 · QA Workbench',
  description: 'AI 驱动的高效测试工程生产力工具',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" data-appearance="light" data-density="standard">
      <body>
        {/* 全局逻辑与浮层 */}
        <ViewportListener />
        <NavigationStateSync />
        <ShortcutManager />
        <CommandPalette />
        <InsightPanel />

        {/* 三段式骨架 */}
        <TopBar />
        <Sidebar />

        {/* 主内容区域：自适应侧边栏宽度 */}
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  )
}

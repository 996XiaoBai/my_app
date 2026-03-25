'use client'

import { useAppStore } from '@/stores/useAppStore'
import Dashboard from '@/components/dashboard/Dashboard'
import FlowchartPage from '@/components/modules/FlowchartPage'
import RequirementAnalysisPage from '@/components/modules/RequirementAnalysisPage'
import ReviewPage from '@/components/modules/ReviewPage'
import TestCasePage from '@/components/modules/TestCasePage'
import TestCaseReviewPage from '@/components/modules/TestCaseReviewPage'
import ApiTestPage from '@/components/modules/ApiTestPage'
import GenericModulePage from '@/components/modules/GenericModulePage'
import UIAutoPage from '@/components/modules/UIAutoPage'
import WeeklyReportPage from '@/components/modules/WeeklyReportPage'
import { findNavItem } from '@/config/navigation'
import { resolveWorkbenchPageKind } from '@/lib/pageRouting'

/**
 * 功能模块占位页面
 */
function ModulePlaceholder({ id }: { id: string }) {
  const item = findNavItem(id)
  
  if (!item) return <div className="p-8 text-center text-red-500">Module {id} not found</div>

  return (
    <div className="max-w-4xl mx-auto py-20 text-center animate-fade-in">
      <div className="text-6xl mb-6">{item.icon}</div>
      <h1 className="text-4xl font-bold text-[#F2F2F2] mb-4">{item.label}</h1>
      <p className="text-[#8B949E] max-w-md mx-auto leading-relaxed">
        该能力当前不在主导航中。<br />
        如需恢复为正式入口，建议先补齐独立配置、导出和任务闭环。
      </p>
      <div className="mt-10 p-4 rounded-xl border border-[#8B5CF6]/20 bg-[#8B5CF6]/5 text-xs font-mono text-[#8B5CF6]/60">
        Active Node ID: {id}
      </div>
    </div>
  )
}

/**
 * 主页面：作为客户端路由分配器
 */
export default function Page() {
  const activeNavId = useAppStore((s) => s.activeNavId)

  switch (resolveWorkbenchPageKind(activeNavId)) {
    case 'dashboard':
      return <Dashboard />
    case 'review':
      return <ReviewPage />
    case 'req-analysis':
      return <RequirementAnalysisPage />
    case 'test-cases':
      return <TestCasePage />
    case 'test-case-review':
      return <TestCaseReviewPage />
    case 'ui-auto':
      return <UIAutoPage />
    case 'weekly-report':
      return <WeeklyReportPage />
    case 'flowchart':
      return <FlowchartPage />
    case 'api-test':
      return <ApiTestPage />
    default:
      break
  }

  const navItem = findNavItem(activeNavId)
  if (navItem) {
    const caption = navItem.id === 'test-data'
      ? '上传研发技术文档，提取表结构并生成可直接使用的 MySQL 查询与插入 SQL。'
      : `${navItem.label}功能模块，支持文档上传与 AI 深度处理。`

    return (
      <GenericModulePage 
        id={navItem.id}
        label={navItem.label}
        icon={navItem.icon}
        caption={caption}
      />
    )
  }

  return <ModulePlaceholder id={activeNavId} />
}

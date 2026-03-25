'use client'

import React from 'react'
import {
  ChevronUp,
  ChevronDown,
  Flag,
  FolderKanban,
  Menu,
  Route,
  Search,
} from 'lucide-react'

import { findNavItem } from '@/config/navigation'
import { buildApiUrl } from '@/lib/apiConfig'
import { buildTopBarPresentation } from '@/lib/workbenchPresentation'
import { getTopBarHeight } from '@/lib/workbenchLayout'
import { useAppStore } from '@/stores/useAppStore'

export default function TopBar() {
  const {
    currentProject,
    currentVersion,
    activeEnvironment,
    activeNavId,
    toggleSidebar,
    toggleTopBar,
    toggleCommandPalette,
    sidebarCollapsed,
    topBarCollapsed,
  } = useAppStore()

  const currentModuleLabel = activeNavId === 'dashboard'
    ? '工作台'
    : (findNavItem(activeNavId)?.label || '未命名模块')
  const topBarPresentation = buildTopBarPresentation({
    moduleLabel: currentModuleLabel,
    environment: activeEnvironment,
  })
  const topBarHeight = getTopBarHeight(topBarCollapsed)

  if (topBarCollapsed) {
    return (
      <header
        className="fixed inset-x-0 top-0 z-50 flex items-center gap-2 border-b px-3 backdrop-blur-xl lg:px-4"
        style={{
          height: `${topBarHeight}px`,
          backgroundColor: 'color-mix(in srgb, var(--surface-sidebar) 88%, transparent)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <button
            onClick={toggleSidebar}
            aria-label={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
            className="flex items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
            style={{ width: 'var(--click-min)', height: 'var(--click-min)' }}
          >
            <Menu style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
          </button>

          <div className="hidden min-w-0 items-center gap-2 sm:flex">
            <span className="truncate text-sm font-semibold text-[var(--text-primary)]">{currentProject}</span>
            <span className="rounded-md border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2 py-0.5 font-mono text-[11px] text-[var(--accent-primary)]">
              {currentVersion}
            </span>
          </div>
        </div>

        <div className="hidden min-w-0 flex-1 items-center gap-2 rounded-xl border px-3 py-2 md:flex" style={{ borderColor: 'var(--border)' }}>
          <Route className="h-4 w-4 shrink-0 text-[var(--accent-primary)]" />
          <span className="truncate text-sm font-medium text-[var(--text-primary)]" title={topBarPresentation.moduleLabel}>
            {topBarPresentation.moduleShortLabel}
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <BackendHealthStatus />

          <div className="flex items-center gap-2 rounded-xl border px-3 py-2" style={{ borderColor: 'var(--border)' }}>
            <Flag className="h-4 w-4 text-[var(--text-muted)]" />
            <span className="font-mono text-[11px] text-[var(--text-secondary)]">{topBarPresentation.environmentBadge}</span>
          </div>

          <button
            type="button"
            onClick={toggleTopBar}
            aria-label="展开顶栏"
            className="flex items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
            style={{ width: 'var(--click-min)', height: 'var(--click-min)', borderColor: 'var(--border)' }}
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>
      </header>
    )
  }

  return (
    <header
      className="fixed inset-x-0 top-0 z-50 flex items-center gap-3 border-b px-4 backdrop-blur-xl lg:px-5"
      style={{
        height: `${topBarHeight}px`,
        backgroundColor: 'color-mix(in srgb, var(--surface-sidebar) 88%, transparent)',
        borderColor: 'var(--border)',
      }}
    >
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={toggleSidebar}
          aria-label={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          className="flex items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
          style={{ width: 'var(--click-min)', height: 'var(--click-min)' }}
        >
          <Menu style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
        </button>

        <button
          type="button"
          className="hidden items-center gap-2 rounded-xl border px-3 py-2 text-left transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] sm:flex"
          style={{ borderColor: 'var(--border)' }}
        >
          <FolderKanban className="h-4 w-4 text-[var(--accent-primary)]" />
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-[var(--text-primary)]">{currentProject}</div>
          </div>
          <span className="rounded-md border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2 py-0.5 font-mono text-[11px] text-[var(--accent-primary)]">
            {currentVersion}
          </span>
        </button>
      </div>

      <div className="hidden min-w-0 flex-1 md:flex">
        <button
          onClick={toggleCommandPalette}
          className="flex h-10 w-full max-w-xl items-center gap-3 rounded-xl border px-4 transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
          style={{ borderColor: 'var(--border)', backgroundColor: 'var(--surface-panel)' }}
        >
          <Search className="h-4 w-4 text-[var(--text-muted)]" />
          <span className="truncate text-sm text-[var(--text-secondary)]">{topBarPresentation.searchPlaceholder}</span>
          <kbd className="ml-auto rounded-md border border-[color:var(--border-soft)] bg-[var(--surface-inset)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-muted)]">
            ⌘K
          </kbd>
        </button>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <BackendHealthStatus />

        <div className="hidden items-center gap-2 rounded-xl border px-3 py-2 lg:flex" style={{ borderColor: 'var(--border)' }}>
          <Route className="h-4 w-4 text-[var(--accent-primary)]" />
          <div className="max-w-[140px] truncate text-sm font-medium text-[var(--text-primary)]" title={topBarPresentation.moduleLabel}>
            {topBarPresentation.moduleShortLabel}
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-xl border px-3 py-2" style={{ borderColor: 'var(--border)' }}>
          <Flag className="h-4 w-4 text-[var(--text-muted)]" />
          <span className="font-mono text-[11px] text-[var(--text-primary)]" title={topBarPresentation.environmentLabel}>
            {topBarPresentation.environmentBadge}
          </span>
        </div>

        <button
          type="button"
          onClick={toggleTopBar}
          aria-label="收起顶栏"
          className="flex items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
          style={{ width: 'var(--click-min)', height: 'var(--click-min)', borderColor: 'var(--border)' }}
        >
          <ChevronUp className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}

function BackendHealthStatus() {
  const { backendStatus, setBackendStatus, clearRecoveredBackendErrors } = useAppStore()

  React.useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(buildApiUrl('/health'))
        if (res.ok) {
          setBackendStatus('healthy')
          clearRecoveredBackendErrors()
        }
        else setBackendStatus('unstable')
      } catch {
        setBackendStatus('offline')
      }
    }

    const timer = setInterval(check, 5000)
    void check()
    return () => clearInterval(timer)
  }, [clearRecoveredBackendErrors, setBackendStatus])

  const statusMap = {
    healthy: {
      dot: 'bg-emerald-500',
      text: 'text-emerald-500',
      label: '在线',
    },
    unstable: {
      dot: 'bg-amber-500',
      text: 'text-amber-500',
      label: '波动',
    },
    offline: {
      dot: 'bg-red-500',
      text: 'text-red-500',
      label: '离线',
    },
  }

  const current = statusMap[backendStatus]

  return (
    <div className="flex items-center gap-2 rounded-xl border px-3 py-2" style={{ borderColor: 'var(--border)' }}>
      <div className={`h-2 w-2 rounded-full ${current.dot}`} />
      <span className={`font-mono text-[11px] ${current.text}`}>{current.label}</span>
    </div>
  )
}

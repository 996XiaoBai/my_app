'use client'

import React from 'react'
import {
  BarChart3,
  Bot,
  CalendarRange,
  ChevronsLeft,
  ChevronsRight,
  ChevronDown,
  ChevronRight,
  Database,
  FileSearch,
  LayoutDashboard,
  type LucideIcon,
  Newspaper,
  PlugZap,
  Rocket,
  Rows3,
  SearchCode,
  Settings,
  SunMoon,
  Target,
  Telescope,
  Zap,
} from 'lucide-react'

import { getAppearanceProfile } from '@/lib/appearance'
import { getDensityLabel, getDensityShortLabel, getNextDensity } from '@/lib/uiDensity'
import { buildSidebarGroupDigests, ensureSidebarGroupExpandedOnNavChange } from '@/lib/sidebarGroups'
import { cn } from '@/lib/utils'
import { getSidebarFooterControlsClassName, getSidebarWidth, getTopBarOffset } from '@/lib/workbenchLayout'
import { NAV_GROUPS, useAppStore } from '@/stores/useAppStore'

const ICON_MAP: Record<string, LucideIcon> = {
  review: FileSearch,
  'req-analysis': Telescope,
  'test-point': Target,
  impact: Zap,
  'test-cases': Target,
  'test-plan': CalendarRange,
  'test-data': Database,
  'log-diagnosis': SearchCode,
  'api-test': PlugZap,
  'perf-test': Rocket,
  'ui-auto': Bot,
  flowchart: BarChart3,
  'weekly-report': Newspaper,
  dashboard: LayoutDashboard,
  settings: Settings,
}

export default function Sidebar() {
  const {
    currentProject,
    sidebarCollapsed,
    topBarCollapsed,
    toggleSidebar,
    sidebarGroupCollapsed,
    toggleSidebarGroup,
    setSidebarGroupCollapsed,
    activeNavId,
    setActiveNav,
    focusedNavIndex,
    setFocusedNavIndex,
    activeFocusArea,
    highRiskMode,
    insightOpen,
    density,
    toggleDensity,
    appearance,
    toggleAppearance,
  } = useAppStore()
  const previousActiveNavIdRef = React.useRef(activeNavId)

  React.useEffect(() => {
    if (insightOpen && window.innerWidth < 1200 && !sidebarCollapsed) {
      toggleSidebar()
    }
  }, [insightOpen, sidebarCollapsed, toggleSidebar])

  React.useEffect(() => {
    const activeGroup = NAV_GROUPS.find((group) => group.items.some((item) => item.id === activeNavId))
    const nextState = ensureSidebarGroupExpandedOnNavChange(
      sidebarGroupCollapsed,
      activeGroup?.title,
      previousActiveNavIdRef.current,
      activeNavId
    )

    previousActiveNavIdRef.current = activeNavId

    if (activeGroup && nextState !== sidebarGroupCollapsed) {
      setSidebarGroupCollapsed(activeGroup.title, false)
    }
  }, [activeNavId, setSidebarGroupCollapsed, sidebarGroupCollapsed])

  const flattenedNavItems = [{ id: 'dashboard' }, ...NAV_GROUPS.flatMap((group) => group.items)]
  const appearanceProfile = getAppearanceProfile(appearance)
  const sidebarGroupDigests = React.useMemo(
    () => new Map(buildSidebarGroupDigests(NAV_GROUPS, activeNavId).map((group) => [group.title, group])),
    [activeNavId]
  )
  const densityLabel = getDensityLabel(density)
  const densityShortLabel = getDensityShortLabel(density)
  const nextDensityLabel = getDensityLabel(getNextDensity(density))
  const sidebarTop = getTopBarOffset(topBarCollapsed)
  const sidebarWidth = getSidebarWidth(sidebarCollapsed, density)
  const pulseStyle = highRiskMode
    ? ({ '--pulse-color': 'rgba(245, 158, 11, 0.24)' } as React.CSSProperties)
    : ({ '--pulse-color': 'rgba(15, 118, 110, 0.22)' } as React.CSSProperties)
  const densityUi = density === 'comfortable'
    ? {
        projectPadding: 'px-3 py-3',
        navPadding: 'px-2.5 py-3',
        sectionGap: 'mb-3',
        groupTogglePadding: 'px-3 py-2',
        groupListGap: 'space-y-1',
        itemPadding: 'px-3 py-2.5',
        collapsedItemPadding: 'px-2.5',
        footerPadding: 'p-2.5',
        footerGap: 'space-y-2',
        footerActionPadding: 'px-3 py-2.5',
        dashboardIconBox: 'h-10 w-10',
        itemIconBox: 'h-8 w-8',
        groupLabel: 'text-[11px]',
        itemLabel: 'text-sm',
        footerLabel: 'text-sm',
        rowGap: 'gap-3',
        showProjectMeta: true,
        showGroupCount: true,
      }
    : density === 'standard'
      ? {
          projectPadding: 'px-2.5 py-2.5',
          navPadding: 'px-2 py-2.5',
          sectionGap: 'mb-2.5',
          groupTogglePadding: 'px-2.5 py-1.5',
          groupListGap: 'space-y-0.5',
          itemPadding: 'px-2.5 py-2',
          collapsedItemPadding: 'px-2',
          footerPadding: 'p-2',
          footerGap: 'space-y-1.5',
          footerActionPadding: 'px-2.5 py-2',
          dashboardIconBox: 'h-9 w-9',
          itemIconBox: 'h-[1.875rem] w-[1.875rem]',
          groupLabel: 'text-[10px]',
          itemLabel: 'text-[13px]',
          footerLabel: 'text-[13px]',
          rowGap: 'gap-2.5',
          showProjectMeta: true,
          showGroupCount: true,
        }
      : {
          projectPadding: 'px-2 py-2',
          navPadding: 'px-1.5 py-2',
          sectionGap: 'mb-2',
          groupTogglePadding: 'px-2 py-1.5',
          groupListGap: 'space-y-0.5',
          itemPadding: 'px-2 py-1.5',
          collapsedItemPadding: 'px-1.5',
          footerPadding: 'p-1.5',
          footerGap: 'space-y-1.5',
          footerActionPadding: 'px-2 py-1.5',
          dashboardIconBox: 'h-8 w-8',
          itemIconBox: 'h-7 w-7',
          groupLabel: 'text-[10px]',
          itemLabel: 'text-[13px]',
          footerLabel: 'text-[13px]',
          rowGap: 'gap-2',
          showProjectMeta: false,
          showGroupCount: false,
        }

  return (
    <aside
      className={cn(
        'fixed bottom-0 left-0 z-40 flex flex-col border-r transition-all duration-300 ease-in-out',
        activeFocusArea !== 'SIDEBAR' ? 'opacity-75 saturate-[0.92]' : 'opacity-100'
      )}
      style={{
        top: sidebarTop,
        width: sidebarWidth,
        backgroundColor: 'var(--surface-sidebar)',
        borderColor: 'var(--border)',
      }}
    >
      <button
        type="button"
        onClick={() => setActiveNav('dashboard')}
        aria-label="返回仪表盘"
        aria-current={activeNavId === 'dashboard' ? 'page' : undefined}
        className={cn(
          'border-b transition-colors',
          densityUi.projectPadding,
          activeNavId === 'dashboard' ? 'bg-[var(--surface-accent)]' : 'hover:bg-[var(--surface-inset)]'
        )}
        style={{ borderColor: 'var(--border-soft)' }}
      >
        <div className={cn('flex items-center', densityUi.rowGap, sidebarCollapsed && 'justify-center')}>
          <div className={cn(
            'flex items-center justify-center rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]',
            densityUi.dashboardIconBox
          )}>
            <LayoutDashboard className="h-[18px] w-[18px]" />
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0 text-left">
              <div className="truncate text-sm font-semibold text-[var(--text-primary)]">{currentProject}</div>
              {densityUi.showProjectMeta && (
                <div className="mt-1 text-[11px] text-[var(--text-muted)]">测试工作台</div>
              )}
            </div>
          )}
        </div>
      </button>

      <nav className={cn('custom-scrollbar flex-1 overflow-y-auto', densityUi.navPadding)}>
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className={densityUi.sectionGap}>
            {!sidebarCollapsed && (
              <button
                type="button"
                onClick={() => toggleSidebarGroup(group.title)}
                className={cn(
                  'flex w-full items-center justify-between rounded-xl text-left transition-colors hover:bg-[var(--surface-inset)]',
                  densityUi.groupTogglePadding
                )}
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className={cn(
                    'truncate font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]',
                    densityUi.groupLabel
                  )}>
                    {group.title}
                  </span>
                  {densityUi.showGroupCount && (
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-[10px] font-medium',
                        sidebarGroupDigests.get(group.title)?.tone === 'accent'
                          ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                          : 'border-[color:var(--border-soft)] bg-[var(--surface-panel)] text-[var(--text-secondary)]'
                      )}
                    >
                      {sidebarGroupDigests.get(group.title)?.countLabel}
                    </span>
                  )}
                </div>
                <div className="flex items-center">
                  {sidebarGroupCollapsed[group.title] ? (
                    <ChevronRight className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                  )}
                </div>
              </button>
            )}

            <div className={cn(densityUi.groupListGap, !sidebarCollapsed && sidebarGroupCollapsed[group.title] && 'hidden')}>
              {group.items.map((item) => {
                const globalIndex = flattenedNavItems.findIndex((candidate) => candidate.id === item.id)
                const isActive = activeNavId === item.id
                const isFocused = focusedNavIndex === globalIndex
                const Icon = ICON_MAP[item.id] || Target

                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveNav(item.id)}
                    onMouseEnter={() => setFocusedNavIndex(globalIndex)}
                    title={sidebarCollapsed ? item.label : undefined}
                    className={cn(
                      'relative flex w-full items-center rounded-xl border text-left transition-all',
                      densityUi.rowGap,
                      densityUi.itemPadding,
                      sidebarCollapsed ? cn('justify-center', densityUi.collapsedItemPadding) : '',
                      isActive
                        ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--text-primary)]'
                        : 'border-transparent text-[var(--text-secondary)] hover:border-[color:var(--border-soft)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]',
                      isFocused && 'border-[color:var(--border-hover)]',
                      isActive && item.id === 'impact' && 'animate-status-pulse'
                    )}
                    style={{
                      ...((item.id === 'impact' || isActive) ? pulseStyle : {}),
                      minHeight: 'var(--click-row)',
                    }}
                    >
                    <div
                      className={cn(
                        'flex shrink-0 items-center justify-center rounded-lg',
                        densityUi.itemIconBox,
                        isActive
                          ? 'bg-[var(--surface-panel)] text-[var(--accent-primary)]'
                          : 'bg-[var(--surface-panel-muted)] text-[var(--text-muted)]'
                      )}
                    >
                      <Icon style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
                    </div>

                    {!sidebarCollapsed && (
                      <div className="min-w-0 flex-1">
                        <div className={cn('truncate font-medium', densityUi.itemLabel)}>{item.label}</div>
                      </div>
                    )}

                    {isActive && (
                      <span className={cn(
                        'rounded-full bg-[var(--accent-primary)]',
                        sidebarCollapsed ? 'absolute left-0 h-7 w-0.5' : 'h-2 w-2'
                      )}
                      />
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className={cn('border-t', densityUi.footerPadding)} style={{ borderColor: 'var(--border-soft)' }}>
        {!sidebarCollapsed ? (
          <div className={densityUi.footerGap}>
            <div className="flex flex-wrap gap-2 px-1">
              <span className="rounded-full border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2.5 py-1 text-[11px] font-medium text-[var(--accent-primary)]">
                {appearanceProfile.shortLabel}
              </span>
              <span className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                {densityLabel}
              </span>
            </div>

            <div className={getSidebarFooterControlsClassName()}>
              <button
                type="button"
                onClick={toggleAppearance}
                className={cn(
                  'flex w-full items-center justify-between gap-2 overflow-hidden rounded-xl border text-left transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]',
                  densityUi.footerActionPadding
                )}
                style={{ borderColor: 'var(--border)', minHeight: 'var(--click-min)' }}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <SunMoon className="h-4 w-4 text-[var(--accent-primary)]" />
                  <div className={cn('truncate font-medium text-[var(--text-primary)]', densityUi.footerLabel)}>主题</div>
                </div>
                <span className="shrink-0 text-[11px] font-medium text-[var(--text-secondary)]">
                  {appearance === 'light' ? 'DARK' : 'LIGHT'}
                </span>
              </button>

              <button
                type="button"
                onClick={toggleDensity}
                title={`切换到${nextDensityLabel}模式`}
                className={cn(
                  'flex w-full items-center justify-between gap-2 overflow-hidden rounded-xl border text-left transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]',
                  densityUi.footerActionPadding
                )}
                style={{ borderColor: 'var(--border)', minHeight: 'var(--click-min)' }}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Rows3 className="h-4 w-4 text-[var(--text-secondary)]" />
                  <div className={cn('truncate font-medium text-[var(--text-primary)]', densityUi.footerLabel)}>密度</div>
                </div>
                <span className="shrink-0 rounded-md border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2 py-1 font-mono text-[11px] text-[var(--text-secondary)]">
                  {densityShortLabel}
                </span>
              </button>

              <button
                type="button"
                onClick={toggleSidebar}
                className={cn(
                  'flex w-full items-center justify-between gap-2 overflow-hidden rounded-xl border text-left transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]',
                  densityUi.footerActionPadding
                )}
                style={{ borderColor: 'var(--border)', minHeight: 'var(--click-min)' }}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <ChevronsLeft className="h-4 w-4 text-[var(--text-secondary)]" />
                  <div className={cn('truncate font-medium text-[var(--text-primary)]', densityUi.footerLabel)}>侧栏</div>
                </div>
                <span className="shrink-0 rounded-md border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)]">
                  收起
                </span>
              </button>
            </div>
          </div>
        ) : (
          <div className={densityUi.footerGap}>
            <button
              type="button"
              onClick={toggleAppearance}
              title={`切换到${appearance === 'dark' ? '浅色' : '暗色'}模式`}
              className="flex w-full items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
              style={{ borderColor: 'var(--border)', height: 'var(--click-min)' }}
            >
              <SunMoon className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={toggleDensity}
              title={`切换到${nextDensityLabel}模式`}
              className="flex w-full items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
              style={{ borderColor: 'var(--border)', height: 'var(--click-min)' }}
            >
              <Rows3 className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={toggleSidebar}
              title="展开侧栏"
              className="flex w-full items-center justify-center rounded-xl border text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
              style={{ borderColor: 'var(--border)', height: 'var(--click-min)' }}
            >
              <ChevronsRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  )
}

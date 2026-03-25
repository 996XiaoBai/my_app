'use client'

import {
  ArrowRight,
  Bot,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

import {
  buildCollaborationRailOverviewBadges,
  buildRailStatusBadgeCopy,
} from '@/lib/workbenchPresentation'
import {
  getWorkbenchRailEntryClassName,
  getWorkbenchRailListClassName,
  getWorkbenchRailSectionClassName,
  getWorkbenchRailToneClassName,
} from '@/lib/workbenchControls'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/stores/useAppStore'

export type RailTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger'
export type RailStatus = 'idle' | 'running' | 'done' | 'warning'

export interface RailTag {
  label: string
  tone?: RailTone
}

export interface RailAction {
  label: string
  onClick: () => void
  tone?: RailTone
}

export interface RailEntry {
  id: string
  label: string
  value: string
  detail?: string
  status?: RailStatus
  onClick?: () => void
}

export interface RailSection {
  id: string
  title: string
  description?: string
  entries: RailEntry[]
}

interface Props {
  title: string
  subtitle: string
  tags?: RailTag[]
  actions?: RailAction[]
  sections: RailSection[]
}

const statusToneMap: Record<RailStatus, RailTone> = {
  idle: 'neutral',
  running: 'accent',
  done: 'success',
  warning: 'warning',
}

export default function CollaborationRail({
  title,
  subtitle,
  tags = [],
  actions = [],
  sections,
}: Props) {
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)
  const toggleCollaborationRail = useAppStore((s) => s.toggleCollaborationRail)
  const overviewBadges = buildCollaborationRailOverviewBadges(sections)
  const hasSingleMirroredSection = sections.length === 1 && sections[0]?.title === title

  if (collaborationRailCollapsed) {
    return (
      <aside className="console-rail flex h-full min-h-[640px] flex-col items-center justify-between px-2 py-3">
        <button
          type="button"
          onClick={toggleCollaborationRail}
          aria-label="展开协作侧栏"
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <div className="flex flex-col items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
            <Bot className="h-4 w-4" />
          </div>
          <div
            className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]"
            style={{ writingMode: 'vertical-rl' }}
          >
            协作侧栏
          </div>
        </div>

        <div className="rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2 py-2 text-center">
          <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">分区</div>
          <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{sections.length}</div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="console-rail flex h-full min-h-[640px] flex-col p-3.5">
      <div className="border-b console-divider pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]">
            <Bot className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-[var(--text-primary)]">{title}</h2>
          </div>
          <button
            type="button"
            onClick={toggleCollaborationRail}
            aria-label="收起协作侧栏"
            className="ml-auto flex h-9 w-9 items-center justify-center rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        {subtitle.trim() && (
          <p className="mt-3 text-xs leading-6 text-[var(--text-secondary)]">{subtitle}</p>
        )}
        {(overviewBadges.length > 0 || tags.length > 0) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {(tags.length > 0 ? tags : overviewBadges).map((badge) => (
              <span
                key={badge.label}
                className={cn(
                  'inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium',
                  getWorkbenchRailToneClassName(badge.tone || 'neutral')
                )}
              >
                {badge.label}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="custom-scrollbar mt-3 flex-1 space-y-3 overflow-y-auto pr-1">
        {sections.map((section) => {
          return (
            <section key={section.id} className={getWorkbenchRailSectionClassName()}>
              {!hasSingleMirroredSection && (
                <div className="mb-1.5">
                  <h3 className="min-w-0 truncate text-sm font-semibold text-[var(--text-primary)]">{section.title}</h3>
                </div>
              )}
              <div className={getWorkbenchRailListClassName()}>
                {section.entries.map((entry, index) => {
                  const railStatus = entry.status || 'idle'
                  const statusBadge = buildRailStatusBadgeCopy(railStatus)
                  const entryKey = `${section.id}:${entry.id}:${index}`

                  const content = (
                    <div className={getWorkbenchRailEntryClassName()}>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="truncate text-[11px] font-medium text-[var(--text-muted)]">{entry.label}</div>
                          {!statusBadge.hidden && (
                            <span
                              className={cn(
                                'rounded-full border px-2 py-0.5 text-[10px] font-semibold',
                                getWorkbenchRailToneClassName(statusToneMap[railStatus])
                              )}
                            >
                              {statusBadge.label}
                            </span>
                          )}
                        </div>
                        {entry.detail && (
                          <p className="mt-1 text-[11px] leading-5 text-[var(--text-secondary)]">{entry.detail}</p>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5 pl-3">
                        <div className="text-sm font-semibold text-[var(--text-primary)]">{entry.value}</div>
                        {entry.onClick && <ArrowRight className="h-3.5 w-3.5 text-[var(--text-muted)]" />}
                      </div>
                    </div>
                  )

                  if (!entry.onClick) {
                    return <div key={entryKey}>{content}</div>
                  }

                  return (
                    <button
                      key={entryKey}
                      type="button"
                      onClick={entry.onClick}
                      className="-mx-2 block w-[calc(100%+1rem)] rounded-xl px-2 text-left transition-colors hover:bg-[var(--surface-panel-muted)]"
                    >
                      {content}
                    </button>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>

      {actions.length > 0 && (
        <div className="mt-3 flex flex-col gap-2 border-t console-divider pt-3">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              onClick={action.onClick}
              className={cn(
                'flex min-h-[40px] items-center justify-between rounded-xl border px-3 py-2 text-left text-sm font-medium transition-colors',
                getWorkbenchRailToneClassName(action.tone || 'neutral')
              )}
            >
              <span>{action.label}</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          ))}
        </div>
      )}
    </aside>
  )
}

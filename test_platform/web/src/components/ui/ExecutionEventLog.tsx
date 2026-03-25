'use client'

import { useMemo, useState } from 'react'
import type { RunProgressEvent } from '@/lib/api'
import { groupExecutionEvents, type ExecutionEventGroupId } from '@/lib/executionEventLog'

interface Props {
  events: RunProgressEvent[]
  emptyText?: string
}

const DEFAULT_EXPANDED: Record<ExecutionEventGroupId, boolean> = {
  parsing: true,
  extracting: true,
  generating: true,
  organizing: true,
  other: false,
}

export default function ExecutionEventLog({ events, emptyText = '暂无执行事件' }: Props) {
  const [expanded, setExpanded] = useState<Record<ExecutionEventGroupId, boolean>>(DEFAULT_EXPANDED)
  const groups = useMemo(() => groupExecutionEvents(events).filter((group) => group.events.length > 0), [events])

  if (groups.length === 0) {
    return <div className="text-[var(--text-muted)]">{emptyText}</div>
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <div
          key={group.id}
          className="rounded-xl overflow-hidden"
          style={{ border: '1px solid var(--border-soft)', backgroundColor: 'var(--bg-soft)' }}
        >
          <button
            onClick={() => setExpanded((prev) => ({ ...prev, [group.id]: !prev[group.id] }))}
            className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg-muted)] transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-[var(--text-primary)] font-medium">{group.label}</span>
              <span className="rounded-full px-2 py-0.5 text-[11px] text-[var(--text-secondary)]" style={{ border: '1px solid var(--border)' }}>
                {group.events.length} 条
              </span>
            </div>
            <span className={`text-[var(--text-secondary)] transition-transform ${expanded[group.id] ? 'rotate-180' : ''}`}>▾</span>
          </button>
          {expanded[group.id] && (
            <div className="space-y-2 p-4" style={{ borderTop: '1px solid var(--border-soft)' }}>
              {group.events.map((event) => (
                <div
                  key={`${group.id}-${event.sequence}`}
                  className="rounded-lg px-3 py-2 text-sm text-[var(--text-strong)]"
                  style={{ border: '1px solid var(--border-soft)', backgroundColor: 'var(--bg-contrast)' }}
                >
                  <span className="mr-2 font-mono text-[var(--text-secondary)]">#{String(event.sequence).padStart(2, '0')}</span>
                  {event.message}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

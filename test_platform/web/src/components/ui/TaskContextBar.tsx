'use client'

import { ArrowRight, FolderInput, ShieldAlert, Workflow } from 'lucide-react'

import { cn } from '@/lib/utils'

interface TaskContextAction {
  label: string
  onClick: () => void
  tone?: 'primary' | 'secondary' | 'muted'
  disabled?: boolean
  title?: string
}

interface Props {
  title: string
  stageLabel: string
  sourceLabel: string
  riskCount?: number
  hasContext?: boolean
  actions?: TaskContextAction[]
}

export default function TaskContextBar({
  title,
  stageLabel,
  sourceLabel,
  riskCount = 0,
  hasContext = false,
  actions = [],
}: Props) {
  return (
    <section className="console-panel mb-5 overflow-hidden">
      <div className="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_auto]" style={{ borderColor: 'var(--border-soft)' }}>
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent-primary)]">
              <Workflow className="h-3 w-3" />
              {stageLabel}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--border)] bg-[var(--surface-inset)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]">
              <FolderInput className="h-3 w-3" />
              {sourceLabel}
            </span>
            {hasContext && (
              <span className="inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-500">
                已联动
              </span>
            )}
            {riskCount > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-500">
                <ShieldAlert className="h-3 w-3" />
                {riskCount} 风险
              </span>
            )}
          </div>
          <h2 className="truncate text-lg font-semibold text-[var(--text-primary)] lg:text-xl">{title}</h2>
        </div>

        {actions.length > 0 && (
          <div className="flex flex-wrap gap-2 lg:justify-end">
            {actions.map((action) => {
              const tone = action.tone || 'secondary'
              const className =
                tone === 'primary'
                  ? 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)] shadow-[0_10px_24px_rgba(15,118,110,0.08)] hover:border-[color:var(--border-hover)]'
                  : tone === 'muted'
                    ? 'border-[color:var(--border-soft)] bg-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                    : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)] hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]'

              return (
                <button
                  key={action.label}
                  type="button"
                  onClick={action.onClick}
                  disabled={action.disabled}
                  title={action.title}
                  className={cn(
                    'flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
                    className,
                    action.disabled && 'cursor-not-allowed opacity-40'
                  )}
                >
                  <span>{action.label}</span>
                  {!action.disabled && <ArrowRight className="h-3.5 w-3.5" />}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}

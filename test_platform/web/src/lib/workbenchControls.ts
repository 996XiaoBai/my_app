export type WorkbenchResultActionTone = 'neutral' | 'accent'
export type WorkbenchRiskTone = 'high' | 'medium' | 'low'
export type WorkbenchRailTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger'

export function getWorkbenchModeSwitchClassName(): string {
  return 'inline-flex flex-wrap gap-1 rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] p-1'
}

export function getWorkbenchModeButtonClassName(active: boolean): string {
  return active
    ? 'rounded-xl border border-[color:var(--border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-medium text-[var(--text-primary)] shadow-[0_6px_18px_rgba(15,23,42,0.05)]'
    : 'rounded-xl border border-transparent px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]'
}

export function getWorkbenchSecondaryGridClassName(): string {
  return 'mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.95fr)]'
}

export function getWorkbenchSettingsDrawerClassName(): string {
  return 'mt-3 rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]'
}

export function getWorkbenchPrimaryActionStripClassName(): string {
  return 'mt-4 flex items-center justify-between gap-4 rounded-2xl border px-3.5 py-3'
}

export function getWorkbenchInputFooterClassName(): string {
  return 'mt-4 flex items-end justify-between gap-4 border-t border-[color:var(--border-soft)] pt-4'
}

export function getWorkbenchResultToolbarClassName(): string {
  return 'flex flex-wrap items-center gap-1.5 border-b px-3 py-2'
}

export function getWorkbenchResultToolbarGroupClassName(align: 'start' | 'end' = 'start'): string {
  return align === 'end'
    ? 'ml-auto flex flex-wrap items-center gap-1.5'
    : 'flex min-w-0 flex-wrap items-center gap-1.5'
}

export function getWorkbenchResultTabClassName(active: boolean): string {
  return active
    ? 'rounded-lg border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-primary)]'
    : 'rounded-lg border border-transparent px-2.5 py-1 text-[11px] font-medium text-[var(--text-muted)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]'
}

export function getWorkbenchResultActionClassName(
  tone: WorkbenchResultActionTone = 'neutral'
): string {
  return tone === 'accent'
    ? 'rounded-lg border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2 py-1 text-[10px] font-medium text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]'
    : 'rounded-lg border px-2 py-1 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]'
}

export function getWorkbenchResultActionGroupClassName(): string {
  return 'flex flex-wrap items-center gap-1 rounded-lg border px-1 py-1'
}

export function getWorkbenchFindingsListClassName(): string {
  return 'custom-scrollbar h-full space-y-2.5 overflow-y-auto pr-2'
}

export function getWorkbenchFindingCardClassName(level: WorkbenchRiskTone): string {
  const toneClass = level === 'high'
    ? 'border-l-red-600'
    : level === 'medium'
      ? 'border-l-amber-500'
      : 'border-l-emerald-600'

  return `rounded-2xl border border-[color:var(--border-soft)] border-l-4 ${toneClass} bg-[var(--surface-panel)] p-3.5 shadow-[0_8px_24px_rgba(15,23,42,0.04)]`
}

export function getWorkbenchFindingBadgeClassName(level: WorkbenchRiskTone): string {
  if (level === 'high') {
    return 'rounded-full bg-red-600 px-2.5 py-1 text-[11px] font-semibold text-white'
  }

  if (level === 'medium') {
    return 'rounded-full bg-amber-500 px-2.5 py-1 text-[11px] font-semibold text-slate-950'
  }

  return 'rounded-full bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white'
}

export function getWorkbenchSuggestionPanelClassName(): string {
  return 'mt-2.5 rounded-xl border border-sky-200/80 bg-sky-50/90 px-3.5 py-2.5'
}

export function getWorkbenchRailToneClassName(tone: WorkbenchRailTone): string {
  if (tone === 'accent') {
    return 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
  }

  if (tone === 'success') {
    return 'border-emerald-600 bg-emerald-600 text-white'
  }

  if (tone === 'warning') {
    return 'border-amber-500 bg-amber-500 text-slate-950'
  }

  if (tone === 'danger') {
    return 'border-red-600 bg-red-600 text-white'
  }

  return 'border-[color:var(--border)] bg-[var(--surface-panel)] text-[var(--text-secondary)]'
}

export function getWorkbenchRailSectionClassName(): string {
  return 'rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-3'
}

export function getWorkbenchRailListClassName(): string {
  return 'divide-y divide-[color:var(--border-soft)]'
}

export function getWorkbenchRailEntryClassName(): string {
  return 'flex items-start justify-between gap-3 py-2.5'
}

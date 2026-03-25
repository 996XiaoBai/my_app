import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getWorkbenchFindingBadgeClassName,
  getWorkbenchFindingCardClassName,
  getWorkbenchFindingsListClassName,
  getWorkbenchInputFooterClassName,
  getWorkbenchModeButtonClassName,
  getWorkbenchModeSwitchClassName,
  getWorkbenchPrimaryActionStripClassName,
  getWorkbenchResultActionClassName,
  getWorkbenchResultActionGroupClassName,
  getWorkbenchResultTabClassName,
  getWorkbenchResultToolbarClassName,
  getWorkbenchResultToolbarGroupClassName,
  getWorkbenchRailEntryClassName,
  getWorkbenchRailListClassName,
  getWorkbenchRailSectionClassName,
  getWorkbenchRailToneClassName,
  getWorkbenchSettingsDrawerClassName,
  getWorkbenchSuggestionPanelClassName,
  getWorkbenchSecondaryGridClassName,
} from './workbenchControls.ts'

test('getWorkbenchModeSwitchClassName keeps input source toggles inside one muted rail', () => {
  assert.equal(
    getWorkbenchModeSwitchClassName(),
    'inline-flex flex-wrap gap-1 rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] p-1'
  )
})

test('getWorkbenchModeButtonClassName distinguishes active and inactive states without heavy noise', () => {
  assert.equal(
    getWorkbenchModeButtonClassName(true),
    'rounded-xl border border-[color:var(--border)] bg-[var(--surface-panel)] px-3 py-2 text-xs font-medium text-[var(--text-primary)] shadow-[0_6px_18px_rgba(15,23,42,0.05)]'
  )
  assert.equal(
    getWorkbenchModeButtonClassName(false),
    'rounded-xl border border-transparent px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]'
  )
})

test('getWorkbenchSecondaryGridClassName keeps input and settings merged into one dense card', () => {
  assert.equal(
    getWorkbenchSecondaryGridClassName(),
    'mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.95fr)]'
  )
})

test('getWorkbenchPrimaryActionStripClassName keeps CTA attached to the input card', () => {
  assert.equal(
    getWorkbenchPrimaryActionStripClassName(),
    'mt-4 flex items-center justify-between gap-4 rounded-2xl border px-3.5 py-3'
  )
})

test('getWorkbenchResultToolbarClassName and getWorkbenchResultTabClassName keep result tabs lightweight', () => {
  assert.equal(
    getWorkbenchResultToolbarClassName(),
    'flex flex-wrap items-center gap-1.5 border-b px-3 py-2'
  )
  assert.equal(
    getWorkbenchResultToolbarGroupClassName(),
    'flex min-w-0 flex-wrap items-center gap-1.5'
  )
  assert.equal(
    getWorkbenchResultToolbarGroupClassName('end'),
    'ml-auto flex flex-wrap items-center gap-1.5'
  )
  assert.equal(
    getWorkbenchResultTabClassName(true),
    'rounded-lg border border-[color:var(--border-soft)] bg-[var(--surface-panel)] px-2.5 py-1 text-[11px] font-semibold text-[var(--text-primary)]'
  )
  assert.equal(
    getWorkbenchResultTabClassName(false),
    'rounded-lg border border-transparent px-2.5 py-1 text-[11px] font-medium text-[var(--text-muted)] hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]'
  )
})

test('getWorkbenchResultActionClassName only elevates the single export action that needs emphasis', () => {
  assert.equal(
    getWorkbenchResultActionClassName(),
    'rounded-lg border px-2 py-1 text-[10px] font-medium text-[var(--text-secondary)] transition-colors hover:border-[color:var(--border-hover)] hover:text-[var(--text-primary)]'
  )
  assert.equal(
    getWorkbenchResultActionClassName('accent'),
    'rounded-lg border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2 py-1 text-[10px] font-medium text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]'
  )
  assert.equal(
    getWorkbenchResultActionGroupClassName(),
    'flex flex-wrap items-center gap-1 rounded-lg border px-1 py-1'
  )
})

test('review settings are compacted into a lightweight drawer and inline footer', () => {
  assert.equal(
    getWorkbenchSettingsDrawerClassName(),
    'mt-3 rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]'
  )
  assert.equal(
    getWorkbenchInputFooterClassName(),
    'mt-4 flex items-end justify-between gap-4 border-t border-[color:var(--border-soft)] pt-4'
  )
})

test('review findings switch back to a single readable feed with strong priority cues', () => {
  assert.equal(
    getWorkbenchFindingsListClassName(),
    'custom-scrollbar h-full space-y-2.5 overflow-y-auto pr-2'
  )
  assert.equal(
    getWorkbenchFindingCardClassName('high'),
    'rounded-2xl border border-[color:var(--border-soft)] border-l-4 border-l-red-600 bg-[var(--surface-panel)] p-3.5 shadow-[0_8px_24px_rgba(15,23,42,0.04)]'
  )
  assert.equal(
    getWorkbenchFindingCardClassName('medium'),
    'rounded-2xl border border-[color:var(--border-soft)] border-l-4 border-l-amber-500 bg-[var(--surface-panel)] p-3.5 shadow-[0_8px_24px_rgba(15,23,42,0.04)]'
  )
  assert.equal(
    getWorkbenchFindingBadgeClassName('high'),
    'rounded-full bg-red-600 px-2.5 py-1 text-[11px] font-semibold text-white'
  )
  assert.equal(
    getWorkbenchSuggestionPanelClassName(),
    'mt-2.5 rounded-xl border border-sky-200/80 bg-sky-50/90 px-3.5 py-2.5'
  )
})

test('collaboration rail uses white cards and stronger solid badges instead of stacked grey blocks', () => {
  assert.equal(
    getWorkbenchRailSectionClassName(),
    'rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-3'
  )
  assert.equal(
    getWorkbenchRailListClassName(),
    'divide-y divide-[color:var(--border-soft)]'
  )
  assert.equal(
    getWorkbenchRailEntryClassName(),
    'flex items-start justify-between gap-3 py-2.5'
  )
  assert.equal(
    getWorkbenchRailToneClassName('success'),
    'border-emerald-600 bg-emerald-600 text-white'
  )
  assert.equal(
    getWorkbenchRailToneClassName('warning'),
    'border-amber-500 bg-amber-500 text-slate-950'
  )
})

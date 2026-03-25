import type { CSSProperties } from 'react'
import type { UIDensity } from './uiDensity'

export const TOP_BAR_EXPANDED_HEIGHT = 56
export const TOP_BAR_COLLAPSED_HEIGHT = 40
export const COLLABORATION_RAIL_EXPANDED_WIDTH = '320px'
export const COLLABORATION_RAIL_COLLAPSED_WIDTH = '72px'
export const SIDEBAR_WIDTH_MAP: Record<UIDensity, { expanded: string; collapsed: string }> = {
  comfortable: { expanded: '288px', collapsed: '76px' },
  standard: { expanded: '264px', collapsed: '72px' },
  compact: { expanded: '240px', collapsed: '64px' },
}
export type WorkbenchResultPanelMode = 'flex' | 'block'

export function getTopBarHeight(collapsed: boolean): number {
  return collapsed ? TOP_BAR_COLLAPSED_HEIGHT : TOP_BAR_EXPANDED_HEIGHT
}

export function getTopBarOffset(collapsed: boolean): string {
  return `${getTopBarHeight(collapsed)}px`
}

export function getCollaborationRailWidth(collapsed: boolean): string {
  return collapsed ? COLLABORATION_RAIL_COLLAPSED_WIDTH : COLLABORATION_RAIL_EXPANDED_WIDTH
}

export function getSidebarWidth(collapsed: boolean, density: UIDensity): string {
  const width = SIDEBAR_WIDTH_MAP[density] || SIDEBAR_WIDTH_MAP.standard
  return collapsed ? width.collapsed : width.expanded
}

export function getSidebarFooterControlsClassName(): string {
  return 'grid grid-cols-1 gap-2 overflow-hidden'
}

export function getRailWidthStyle(collapsed: boolean): CSSProperties {
  return {
    '--rail-width': getCollaborationRailWidth(collapsed),
  } as CSSProperties
}

export function getWorkbenchStackClassName(): string {
  return 'space-y-5'
}

export function getWorkbenchResultPanelClassName(
  mode: WorkbenchResultPanelMode = 'flex'
): string {
  return mode === 'block'
    ? 'console-panel min-h-[720px] overflow-hidden'
    : 'console-panel flex min-h-[720px] flex-col overflow-hidden'
}

export function getWorkbenchRailWrapperClassName(collapsed: boolean): string {
  return collapsed ? 'flex justify-end' : 'min-w-0'
}

export type SidebarGroupCollapsedState = Record<string, boolean>
export type SidebarDigestTone = 'neutral' | 'accent'

export interface SidebarGroupDigest {
  title: string
  countLabel: string
  tone: SidebarDigestTone
}

interface SidebarGroupInput {
  title: string
  items: Array<{ id: string }>
}

export function createInitialSidebarGroupState(groupTitles: string[]): SidebarGroupCollapsedState {
  return groupTitles.reduce<SidebarGroupCollapsedState>((acc, title) => {
    acc[title] = false
    return acc
  }, {})
}

export function toggleSidebarGroupState(
  state: SidebarGroupCollapsedState,
  groupTitle: string
): SidebarGroupCollapsedState {
  return {
    ...state,
    [groupTitle]: !state[groupTitle],
  }
}

export function setSidebarGroupState(
  state: SidebarGroupCollapsedState,
  groupTitle: string,
  collapsed: boolean
): SidebarGroupCollapsedState {
  if (state[groupTitle] === collapsed) {
    return state
  }

  return {
    ...state,
    [groupTitle]: collapsed,
  }
}

export function ensureSidebarGroupExpanded(
  state: SidebarGroupCollapsedState,
  groupTitle: string | null | undefined
): SidebarGroupCollapsedState {
  if (!groupTitle || !state[groupTitle]) {
    return state
  }

  return {
    ...state,
    [groupTitle]: false,
  }
}

export function ensureSidebarGroupExpandedOnNavChange(
  state: SidebarGroupCollapsedState,
  groupTitle: string | null | undefined,
  previousActiveNavId: string | null | undefined,
  nextActiveNavId: string
): SidebarGroupCollapsedState {
  if (!previousActiveNavId || previousActiveNavId === nextActiveNavId) {
    return state
  }

  return ensureSidebarGroupExpanded(state, groupTitle)
}

export function buildSidebarGroupDigests(
  groups: SidebarGroupInput[],
  activeNavId: string
): SidebarGroupDigest[] {
  return groups.map((group) => ({
    title: group.title,
    countLabel: `${group.items.length} 项`,
    tone: group.items.some((item) => item.id === activeNavId) ? 'accent' : 'neutral',
  }))
}

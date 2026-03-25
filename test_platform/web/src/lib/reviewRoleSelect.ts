export type ReviewRoleOption = {
  id: string
  label: string
}

type ReviewRoleSelectionSummary = {
  badgeLabels: string[]
  overflowCount: number
  text: string
}

const DEFAULT_REVIEW_ROLE_IDS = ['test'] as const
const REVIEW_ROLE_SHORT_LABELS: Record<string, string> = {
  test: '测试',
  product: '产品',
  tech: '技术',
  design: '设计',
  security: '安全',
  architect: '架构',
}
const EMPTY_REVIEW_ROLE_TEXT = '请选择评审角色'
const REVIEW_ROLE_REQUIRED_TEXT = '请至少选择一个评审角色'

function resolveReviewRoleShortLabel(role: ReviewRoleOption): string {
  return REVIEW_ROLE_SHORT_LABELS[role.id] || role.label
}

export function getDefaultReviewRoleIds(): string[] {
  return [...DEFAULT_REVIEW_ROLE_IDS]
}

export function clearReviewRoleSelection(): string[] {
  return []
}

export function resetReviewRoleSelection(): string[] {
  return getDefaultReviewRoleIds()
}

export function validateReviewRoleSelection(selectedRoleIds: string[]): string | null {
  if (selectedRoleIds.length === 0) {
    return REVIEW_ROLE_REQUIRED_TEXT
  }

  return null
}

export function buildReviewRoleSelectionSummary(
  selectedRoleIds: string[],
  roleOptions: ReviewRoleOption[]
): ReviewRoleSelectionSummary {
  if (selectedRoleIds.length === 0) {
    return {
      badgeLabels: [],
      overflowCount: 0,
      text: EMPTY_REVIEW_ROLE_TEXT,
    }
  }

  const roleById = new Map(roleOptions.map((role) => [role.id, role]))
  const selectedLabels = selectedRoleIds
    .map((roleId) => roleById.get(roleId))
    .filter((role): role is ReviewRoleOption => Boolean(role))
    .map(resolveReviewRoleShortLabel)

  if (selectedLabels.length === 0) {
    return {
      badgeLabels: [],
      overflowCount: 0,
      text: EMPTY_REVIEW_ROLE_TEXT,
    }
  }

  const badgeLabels = selectedLabels.slice(0, 2)
  const overflowCount = Math.max(selectedLabels.length - badgeLabels.length, 0)
  const text = overflowCount > 0 ? `${badgeLabels.join(' / ')} +${overflowCount}` : badgeLabels.join(' / ')

  return {
    badgeLabels,
    overflowCount,
    text,
  }
}

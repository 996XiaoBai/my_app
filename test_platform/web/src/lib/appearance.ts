export type Appearance = 'dark' | 'light'

export interface AppearanceDocumentState {
  appearance: Appearance
  colorScheme: 'dark' | 'light'
}

export interface AppearanceProfile {
  appearance: Appearance
  label: string
  shortLabel: string
  description: string
  emphasis: 'flagship' | 'daily'
}

const APPEARANCE_PROFILES: Record<Appearance, AppearanceProfile> = {
  light: {
    appearance: 'light',
    label: '浅色专业',
    shortLabel: 'LIGHT',
    description: '默认日常工作模式，强调可读性与信息清晰度。',
    emphasis: 'daily',
  },
  dark: {
    appearance: 'dark',
    label: '深色控制台',
    shortLabel: 'DARK',
    description: '工业控制台风格，强调聚焦感与高密度信息操作。',
    emphasis: 'flagship',
  },
}

export function toggleAppearance(current: Appearance): Appearance {
  return current === 'dark' ? 'light' : 'dark'
}

export function getAppearanceProfile(appearance: Appearance): AppearanceProfile {
  return APPEARANCE_PROFILES[appearance]
}

export function getAppearanceDocumentState(
  appearance: Appearance
): AppearanceDocumentState {
  return {
    appearance,
    colorScheme: appearance === 'light' ? 'light' : 'dark',
  }
}

export function syncAppearanceToDocument(
  appearance: Appearance,
  doc: Document = document
) {
  const state = getAppearanceDocumentState(appearance)
  const root = doc.documentElement

  root.setAttribute('data-appearance', state.appearance)
  root.style.colorScheme = state.colorScheme
}

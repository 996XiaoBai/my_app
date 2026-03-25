export type UIDensity = 'comfortable' | 'standard' | 'compact'

const DENSITY_ORDER: UIDensity[] = ['comfortable', 'standard', 'compact']

const DENSITY_LABEL_MAP: Record<UIDensity, string> = {
  comfortable: '宽松',
  standard: '标准',
  compact: '紧凑',
}

const DENSITY_SHORT_LABEL_MAP: Record<UIDensity, string> = {
  comfortable: 'COMFY',
  standard: 'STD',
  compact: 'COMPACT',
}

export function getNextDensity(density: UIDensity): UIDensity {
  const index = DENSITY_ORDER.indexOf(density)

  if (index === -1) {
    return 'standard'
  }

  return DENSITY_ORDER[(index + 1) % DENSITY_ORDER.length]
}

export function getDensityLabel(density: UIDensity): string {
  return DENSITY_LABEL_MAP[density]
}

export function getDensityShortLabel(density: UIDensity): string {
  return DENSITY_SHORT_LABEL_MAP[density]
}

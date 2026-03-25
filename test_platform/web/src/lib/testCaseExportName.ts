function normalizeBaseName(rawValue: string): string {
  const trimmed = String(rawValue || '').trim()
  if (!trimmed) {
    return ''
  }

  const basename = trimmed.split(/[\\/]/).pop() || ''
  const withoutExtension = basename.replace(/\.[^.]+$/, '').trim()
  return withoutExtension || basename.trim()
}

interface ResolveDownloadBaseNameInput {
  persistedBaseName?: string | null
  uploadedFilename?: string | null
  requirement?: string | null
  sharedRequirement?: string | null
  fallbackName?: string | null
}

export function resolvePreferredDownloadBaseName(
  input: ResolveDownloadBaseNameInput
): string {
  const preferredName = normalizeBaseName(input.persistedBaseName || '')
  if (preferredName) {
    return preferredName
  }

  const uploadedName = normalizeBaseName(input.uploadedFilename || '')
  if (uploadedName) {
    return uploadedName
  }

  const sourceText = String(input.requirement || input.sharedRequirement || '').trim()
  if (sourceText) {
    const firstLine = sourceText
      .split('\n')
      .map((line) => line.trim())
      .find(Boolean)

    if (firstLine) {
      return firstLine.slice(0, 24)
    }
  }

  const fallbackName = normalizeBaseName(input.fallbackName || '')
  if (fallbackName) {
    return fallbackName
  }

  return '测试用例'
}

export function buildMarkdownDownloadFilename(baseName: string, suffixLabel: string): string {
  const normalizedBaseName = normalizeBaseName(baseName)
  const normalizedSuffix = String(suffixLabel || '').trim()
  const fileBaseName = normalizedBaseName || '测试平台'

  if (!normalizedSuffix) {
    return `${fileBaseName}.md`
  }

  return `${fileBaseName}_${normalizedSuffix}.md`
}

export function resolveTestCaseExportBaseName(
  input: ResolveDownloadBaseNameInput
): string {
  return resolvePreferredDownloadBaseName(input)
}

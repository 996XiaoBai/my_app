export type TapdInputKind =
  | 'empty'
  | 'story-id'
  | 'tapd-link'
  | 'wecom-doc-link'
  | 'unsupported-link'
  | 'plain-text'

export interface TapdInputParseResult {
  kind: TapdInputKind
  storyId: string | null
  firstUrl: string | null
}

function extractFirstUrl(value: string): string | null {
  const match = value.match(/https?:\/\/[^\s]+/i)
  return match?.[0] || null
}

function extractStoryId(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  if (/^\d+$/.test(trimmed)) {
    return trimmed
  }

  const viewMatch = trimmed.match(/\/view\/(\d+)/i)
  if (viewMatch?.[1]) {
    return viewMatch[1]
  }

  const queryMatch = trimmed.match(/[?&]story_id=(\d+)/i)
  if (queryMatch?.[1]) {
    return queryMatch[1]
  }

  return null
}

export function parseTapdInput(rawInput: string): TapdInputParseResult {
  const input = rawInput.trim()
  if (!input) {
    return {
      kind: 'empty',
      storyId: null,
      firstUrl: null,
    }
  }

  const firstUrl = extractFirstUrl(input)
  const urlLike = firstUrl || (/^https?:\/\//i.test(input) ? input : null)

  if (urlLike) {
    let host = ''
    try {
      host = new URL(urlLike).hostname.toLowerCase()
    } catch {
      return {
        kind: 'unsupported-link',
        storyId: null,
        firstUrl: urlLike,
      }
    }

    if (host.includes('doc.weixin.qq.com')) {
      return {
        kind: 'wecom-doc-link',
        storyId: null,
        firstUrl: urlLike,
      }
    }

    if (host.includes('tapd.cn')) {
      return {
        kind: 'tapd-link',
        storyId: extractStoryId(urlLike),
        firstUrl: urlLike,
      }
    }

    return {
      kind: 'unsupported-link',
      storyId: null,
      firstUrl: urlLike,
    }
  }

  const storyId = extractStoryId(input)
  if (storyId) {
    return {
      kind: 'story-id',
      storyId,
      firstUrl: null,
    }
  }

  return {
    kind: 'plain-text',
    storyId: null,
    firstUrl: null,
  }
}

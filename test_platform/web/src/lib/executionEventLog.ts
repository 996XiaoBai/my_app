import type { RunProgressEvent } from './api'

export type ExecutionEventGroupId = 'parsing' | 'extracting' | 'generating' | 'organizing' | 'other'

export interface ExecutionEventGroup {
  id: ExecutionEventGroupId
  label: string
  events: RunProgressEvent[]
}

const GROUP_ORDER: ExecutionEventGroupId[] = ['parsing', 'extracting', 'generating', 'organizing', 'other']

const GROUP_LABELS: Record<ExecutionEventGroupId, string> = {
  parsing: '解析',
  extracting: '提取',
  generating: '生成',
  organizing: '整理',
  other: '其他',
}

export function classifyExecutionEventGroup(stage: string, message: string): ExecutionEventGroupId {
  const normalizedStage = String(stage || '').toLowerCase()
  const text = String(message || '')

  if (['reading', 'context', 'parsing'].includes(normalizedStage)) {
    return 'parsing'
  }

  if (['extracting', 'decomposing', 'associating'].includes(normalizedStage)) {
    return 'extracting'
  }

  if (['analyzing', 'grouping', 'conflicting', 'matching', 'generating', 'generating_script'].includes(normalizedStage)) {
    return 'generating'
  }

  if (['grading', 'evaluating', 'organizing'].includes(normalizedStage)) {
    return 'organizing'
  }

  if (/提取|拆解|关联|匹配/.test(text)) {
    return 'extracting'
  }

  if (/分析|生成|脚本|仲裁|冲突/.test(text)) {
    return 'generating'
  }

  if (/汇总|整理|格式化|洞察/.test(text)) {
    return 'organizing'
  }

  if (/解析/.test(text)) {
    return 'parsing'
  }

  return 'other'
}

export function groupExecutionEvents(events: RunProgressEvent[]): ExecutionEventGroup[] {
  const grouped = new Map<ExecutionEventGroupId, RunProgressEvent[]>()
  GROUP_ORDER.forEach((groupId) => grouped.set(groupId, []))

  events
    .slice()
    .sort((left, right) => left.sequence - right.sequence)
    .forEach((event) => {
      const groupId = classifyExecutionEventGroup(event.stage, event.message)
      grouped.get(groupId)?.push(event)
    })

  return GROUP_ORDER.map((groupId) => ({
    id: groupId,
    label: GROUP_LABELS[groupId],
    events: grouped.get(groupId) || [],
  }))
}

import type { ReviewFinding } from './contracts'
import type { ModuleSessionState } from './moduleSession'
import { buildTaskWorkbenchSummary, type TaskWorkbenchSummary } from './taskWorkbench.ts'

export interface TaskSnapshot {
  id: string
  title: string
  requirement: string
  sourceLabel: string
  currentStage: TaskWorkbenchSummary['currentStage']
  currentStageLabel: string
  riskCount: number
  hasContext: boolean
  primaryNavId: string
  updatedAt: string
  reviewFindings: ReviewFinding[]
  requirementContextId: string | null
  moduleSessions: Record<string, ModuleSessionState>
}

interface BuildTaskSnapshotInput {
  moduleSessions: Record<string, ModuleSessionState>
  reviewFindings?: ReviewFinding[]
  requirementContextId?: string | null
  updatedAt?: string
}

function normalizeIdPart(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
}

export function buildTaskSnapshotId(requirement: string, requirementContextId?: string | null): string {
  if (requirementContextId) {
    return `ctx:${normalizeIdPart(requirementContextId)}`
  }

  const normalizedRequirement = normalizeIdPart(requirement || 'task')
  return `task:${normalizedRequirement || 'untitled'}`
}

function cloneModuleSessions(
  moduleSessions: Record<string, ModuleSessionState>
): Record<string, ModuleSessionState> {
  const cloned: Record<string, ModuleSessionState> = {}

  Object.entries(moduleSessions).forEach(([key, session]) => {
    cloned[key] = {
      ...session,
      eventLogs: Array.isArray(session.eventLogs)
        ? session.eventLogs.map((event) => ({ ...event }))
        : session.eventLogs,
      options: session.options ? { ...session.options } : session.options,
    }
  })

  return cloned
}

export function buildTaskSnapshot(input: BuildTaskSnapshotInput): TaskSnapshot | null {
  const summary = buildTaskWorkbenchSummary({
    moduleSessions: input.moduleSessions,
    reviewFindings: input.reviewFindings,
    requirementContextId: input.requirementContextId,
  })

  if (!summary.requirement && !summary.hasContext) {
    return null
  }

  return {
    id: buildTaskSnapshotId(summary.requirement, input.requirementContextId),
    title: summary.title,
    requirement: summary.requirement,
    sourceLabel: summary.sourceLabel,
    currentStage: summary.currentStage,
    currentStageLabel: summary.currentStageLabel,
    riskCount: summary.riskCount,
    hasContext: summary.hasContext,
    primaryNavId: summary.primaryAction.navId,
    updatedAt: input.updatedAt || new Date().toISOString(),
    reviewFindings: [...(input.reviewFindings || [])],
    requirementContextId: input.requirementContextId || null,
    moduleSessions: cloneModuleSessions(input.moduleSessions),
  }
}

export function upsertTaskSnapshot(
  snapshots: TaskSnapshot[],
  snapshot: TaskSnapshot,
  limit: number = 6
): TaskSnapshot[] {
  const merged = [snapshot, ...snapshots.filter((item) => item.id !== snapshot.id)]

  merged.sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
  return merged.slice(0, limit)
}

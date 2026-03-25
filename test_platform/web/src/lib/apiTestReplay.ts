import type { ApiTestCase, ApiTestPack, ApiTestScene } from './contracts.ts'
import { buildApiTestExecutionFailureCases } from './workbenchPresentation.ts'

export interface ApiTestFailureReplayPlan {
  failedCaseIds: string[]
  failedSceneIds: string[]
  unmatchedFailureTitles: string[]
  replayCases: ApiTestCase[]
  replayScenes: ApiTestScene[]
}

function buildSafePythonName(value: string): string {
  const normalized: string[] = []

  for (const character of String(value || '')) {
    if (/^[a-z0-9_]$/i.test(character)) {
      normalized.push(character)
      continue
    }
    normalized.push('_')
  }

  return normalized.join('').replace(/^_+|_+$/g, '') || 'generated'
}

function extractFailureTestName(title: string): string {
  const normalizedTitle = String(title || '').trim()
  if (!normalizedTitle) {
    return ''
  }

  const segments = normalizedTitle.split('::').map((item) => item.trim()).filter(Boolean)
  return segments[segments.length - 1] || normalizedTitle
}

function addCaseWithDependencies(
  caseId: string,
  caseIndex: Map<string, ApiTestCase>,
  selectedCaseIds: Set<string>,
  visitingCaseIds: Set<string>
): void {
  if (!caseId || selectedCaseIds.has(caseId) || visitingCaseIds.has(caseId)) {
    return
  }

  const targetCase = caseIndex.get(caseId)
  if (!targetCase) {
    return
  }

  visitingCaseIds.add(caseId)
  for (const dependencyId of targetCase.depends_on || []) {
    addCaseWithDependencies(String(dependencyId || ''), caseIndex, selectedCaseIds, visitingCaseIds)
  }
  visitingCaseIds.delete(caseId)
  selectedCaseIds.add(caseId)
}

export function buildApiTestFailureReplayPlan(pack?: ApiTestPack | null): ApiTestFailureReplayPlan | null {
  if (!pack || !Array.isArray(pack.cases) || !Array.isArray(pack.scenes)) {
    return null
  }

  const failures = buildApiTestExecutionFailureCases(pack.execution?.junit_xml_content)
  if (failures.length === 0) {
    return null
  }

  const caseIdByTestName = new Map<string, string>()
  const sceneIdByTestName = new Map<string, string>()

  for (const item of pack.cases) {
    caseIdByTestName.set(`test_case_${buildSafePythonName(item.case_id)}`, item.case_id)
  }
  for (const item of pack.scenes) {
    sceneIdByTestName.set(`test_scene_${buildSafePythonName(item.scene_id)}`, item.scene_id)
  }

  const failedCaseIds = new Set<string>()
  const failedSceneIds = new Set<string>()
  const unmatchedFailureTitles: string[] = []

  for (const failure of failures) {
    const testName = extractFailureTestName(failure.title)
    const matchedCaseId = caseIdByTestName.get(testName)
    if (matchedCaseId) {
      failedCaseIds.add(matchedCaseId)
      continue
    }

    const matchedSceneId = sceneIdByTestName.get(testName)
    if (matchedSceneId) {
      failedSceneIds.add(matchedSceneId)
      continue
    }

    unmatchedFailureTitles.push(failure.title)
  }

  if (failedCaseIds.size === 0 && failedSceneIds.size === 0) {
    return null
  }

  const selectedSceneIds = new Set<string>(failedSceneIds)
  const selectedCaseIds = new Set<string>()
  const caseIndex = new Map(pack.cases.map((item) => [item.case_id, item] as const))
  const replayScenes = pack.scenes.filter((item) => selectedSceneIds.has(item.scene_id))

  for (const scene of replayScenes) {
    for (const caseId of scene.steps || []) {
      addCaseWithDependencies(String(caseId || ''), caseIndex, selectedCaseIds, new Set<string>())
    }
  }

  for (const caseId of failedCaseIds) {
    addCaseWithDependencies(caseId, caseIndex, selectedCaseIds, new Set<string>())
  }

  const replayCases = pack.cases.filter((item) => selectedCaseIds.has(item.case_id))
  if (replayCases.length === 0 && replayScenes.length === 0) {
    return null
  }

  return {
    failedCaseIds: Array.from(failedCaseIds),
    failedSceneIds: Array.from(failedSceneIds),
    unmatchedFailureTitles,
    replayCases,
    replayScenes,
  }
}

export function buildFailedApiTestReplayPack(pack?: ApiTestPack | null): ApiTestPack | null {
  const replayPlan = buildApiTestFailureReplayPlan(pack)
  if (!pack || !replayPlan) {
    return null
  }

  return {
    ...pack,
    summary: `失败重跑子集：${replayPlan.replayCases.length} 条用例，${replayPlan.replayScenes.length} 个场景。`,
    cases: replayPlan.replayCases,
    scenes: replayPlan.replayScenes,
    execution: undefined,
    report: undefined,
    link_plan: undefined,
    suite: undefined,
  }
}

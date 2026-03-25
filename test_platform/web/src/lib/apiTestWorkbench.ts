import type { ApiTestCase, ApiTestPack, ApiTestScene } from './contracts.ts'

export interface ApiTestSceneGroup {
  scene: ApiTestScene
  cases: ApiTestCase[]
}

export interface ApiTestCaseGroups {
  orderedCases: ApiTestCase[]
  sceneGroups: ApiTestSceneGroup[]
  standaloneCases: ApiTestCase[]
}

function uniqueCaseIds(caseIds: string[]): string[] {
  const visited = new Set<string>()
  const result: string[] = []

  caseIds.forEach((caseId) => {
    const normalized = String(caseId || '').trim()
    if (!normalized || visited.has(normalized)) {
      return
    }
    visited.add(normalized)
    result.push(normalized)
  })

  return result
}

export function buildApiTestCaseGroups(payload?: ApiTestPack | null): ApiTestCaseGroups {
  if (!payload) {
    return {
      orderedCases: [],
      sceneGroups: [],
      standaloneCases: [],
    }
  }

  const caseIndex = new Map<string, ApiTestCase>(
    payload.cases
      .filter((item): item is ApiTestCase => Boolean(item?.case_id))
      .map((item) => [item.case_id, item])
  )
  const sceneIndex = new Map<string, ApiTestScene>(
    payload.scenes
      .filter((item): item is ApiTestScene => Boolean(item?.scene_id))
      .map((item) => [item.scene_id, item])
  )

  const orderedCaseIds = uniqueCaseIds(
    Array.isArray(payload.link_plan?.ordered_case_ids) && payload.link_plan?.ordered_case_ids.length > 0
      ? payload.link_plan.ordered_case_ids
      : payload.cases.map((item) => item.case_id)
  )
  const orderedCases = orderedCaseIds
    .map((caseId) => caseIndex.get(caseId))
    .filter((item): item is ApiTestCase => Boolean(item))

  const consumedCaseIds = new Set<string>()
  const sceneGroups: ApiTestSceneGroup[] = []

  if (Array.isArray(payload.link_plan?.scene_orders) && payload.link_plan.scene_orders.length > 0) {
    payload.link_plan.scene_orders.forEach((sceneOrder) => {
      const scene = sceneIndex.get(sceneOrder.scene_id)
      if (!scene) {
        return
      }
      const cases = uniqueCaseIds(sceneOrder.ordered_steps || [])
        .map((caseId) => caseIndex.get(caseId))
        .filter((item): item is ApiTestCase => Boolean(item))
      if (cases.length === 0) {
        return
      }
      cases.forEach((item) => consumedCaseIds.add(item.case_id))
      sceneGroups.push({ scene, cases })
    })
  } else {
    payload.scenes.forEach((scene) => {
      const cases = uniqueCaseIds(scene.steps || [])
        .map((caseId) => caseIndex.get(caseId))
        .filter((item): item is ApiTestCase => Boolean(item))
      if (cases.length === 0) {
        return
      }
      cases.forEach((item) => consumedCaseIds.add(item.case_id))
      sceneGroups.push({ scene, cases })
    })
  }

  const standaloneCaseIds = uniqueCaseIds(
    Array.isArray(payload.link_plan?.standalone_case_ids) && payload.link_plan?.standalone_case_ids.length > 0
      ? payload.link_plan.standalone_case_ids
      : orderedCases
          .map((item) => item.case_id)
          .filter((caseId) => !consumedCaseIds.has(caseId))
  )

  const standaloneCases = standaloneCaseIds
    .map((caseId) => caseIndex.get(caseId))
    .filter((item): item is ApiTestCase => Boolean(item))

  const existingStandaloneIds = new Set(standaloneCases.map((item) => item.case_id))
  orderedCases.forEach((item) => {
    if (consumedCaseIds.has(item.case_id) || existingStandaloneIds.has(item.case_id)) {
      return
    }
    standaloneCases.push(item)
    existingStandaloneIds.add(item.case_id)
  })

  return {
    orderedCases,
    sceneGroups,
    standaloneCases,
  }
}


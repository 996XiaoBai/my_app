import test from 'node:test'
import assert from 'node:assert/strict'

import { buildApiTestCaseGroups } from './apiTestWorkbench.ts'
import type { ApiTestPack } from './contracts.ts'

function createPayload(): ApiTestPack {
  return {
    summary: '已生成接口测试资产。',
    spec: {
      title: '商品中心',
      servers: [{ url: 'https://example.com' }],
      auth_profile: { required_headers: ['Authorization'], required_cookies: ['sessionid'] },
      resources: [{ resource_key: 'goods', lookup_fields: ['id'], operation_ids: ['goods_create', 'goods_publish'] }],
      operations: [
        { operation_id: 'goods_create', category: 'create', resource_key: 'goods' },
        { operation_id: 'goods_publish', category: 'status', resource_key: 'goods' },
        { operation_id: 'goods_detail', category: 'detail', resource_key: 'goods' },
        { operation_id: 'health_check', category: 'unknown' },
      ],
    },
    cases: [
      {
        case_id: 'goods_create_success',
        title: '新增商品成功',
        operation_id: 'goods_create',
        resource_key: 'goods',
        category: 'create',
        priority: 'P0',
        depends_on: [],
      },
      {
        case_id: 'goods_publish_success',
        title: '发布商品成功',
        operation_id: 'goods_publish',
        resource_key: 'goods',
        category: 'status',
        priority: 'P1',
        depends_on: ['goods_create_success'],
      },
      {
        case_id: 'goods_detail_success',
        title: '查询商品详情',
        operation_id: 'goods_detail',
        resource_key: 'goods',
        category: 'detail',
        priority: 'P1',
        depends_on: ['goods_create_success'],
      },
      {
        case_id: 'health_check_success',
        title: '健康检查成功',
        operation_id: 'health_check',
        category: 'unknown',
        priority: 'P2',
        depends_on: [],
      },
    ],
    scenes: [
      {
        scene_id: 'goods_crud_flow',
        title: '商品创建发布链路',
        steps: ['goods_create_success', 'goods_publish_success'],
      },
    ],
    link_plan: {
      ordered_case_ids: [
        'goods_create_success',
        'goods_publish_success',
        'goods_detail_success',
        'health_check_success',
      ],
      standalone_case_ids: ['goods_detail_success', 'health_check_success'],
      scene_orders: [
        {
          scene_id: 'goods_crud_flow',
          ordered_steps: ['goods_create_success', 'goods_publish_success'],
        },
      ],
    },
  }
}

test('buildApiTestCaseGroups orders scene and standalone cases by linking plan', () => {
  const view = buildApiTestCaseGroups(createPayload())

  assert.deepEqual(
    view.orderedCases.map((item) => item.case_id),
    ['goods_create_success', 'goods_publish_success', 'goods_detail_success', 'health_check_success']
  )
  assert.equal(view.sceneGroups.length, 1)
  assert.equal(view.sceneGroups[0].scene.scene_id, 'goods_crud_flow')
  assert.deepEqual(
    view.sceneGroups[0].cases.map((item) => item.case_id),
    ['goods_create_success', 'goods_publish_success']
  )
  assert.deepEqual(
    view.standaloneCases.map((item) => item.case_id),
    ['goods_detail_success', 'health_check_success']
  )
})

test('buildApiTestCaseGroups falls back to raw scene steps and remaining cases when linking plan is absent', () => {
  const payload = createPayload()
  payload.link_plan = undefined

  const view = buildApiTestCaseGroups(payload)

  assert.deepEqual(
    view.sceneGroups[0].cases.map((item) => item.case_id),
    ['goods_create_success', 'goods_publish_success']
  )
  assert.deepEqual(
    view.standaloneCases.map((item) => item.case_id),
    ['goods_detail_success', 'health_check_success']
  )
})


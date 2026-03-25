import test from 'node:test'
import assert from 'node:assert/strict'

import type { ApiTestPack } from './contracts.ts'
import {
  buildApiTestFailureReplayPlan,
  buildFailedApiTestReplayPack,
} from './apiTestReplay.ts'

function buildSamplePack(junitXmlContent: string): ApiTestPack {
  return {
    summary: '接口测试资产已生成',
    spec: {
      title: '商品接口',
      servers: [{ url: 'https://example.com' }],
      auth_profile: {
        required_headers: [],
        required_cookies: [],
      },
      resources: [],
      operations: [
        {
          operation_id: 'POST /goods/create',
          category: 'create',
          resource_key: 'goods',
        },
        {
          operation_id: 'POST /goods/publish',
          category: 'status',
          resource_key: 'goods',
        },
        {
          operation_id: 'GET /health',
          category: 'list',
        },
      ],
    },
    cases: [
      {
        case_id: 'goods_create_success',
        title: '创建商品成功',
        operation_id: 'POST /goods/create',
        category: 'create',
        resource_key: 'goods',
        priority: 'P0',
        depends_on: [],
      },
      {
        case_id: 'goods_publish_success',
        title: '发布商品成功',
        operation_id: 'POST /goods/publish',
        category: 'status',
        resource_key: 'goods',
        priority: 'P0',
        depends_on: ['goods_create_success'],
      },
      {
        case_id: 'health_check_success',
        title: '健康检查成功',
        operation_id: 'GET /health',
        category: 'list',
        priority: 'P1',
        depends_on: [],
      },
    ],
    scenes: [
      {
        scene_id: 'goods_publish_flow',
        title: '商品发布链路',
        steps: ['goods_create_success', 'goods_publish_success'],
      },
    ],
    script: 'import pytest',
    execution: {
      status: 'failed',
      junit_xml_content: junitXmlContent,
    },
    link_plan: {
      ordered_case_ids: ['goods_create_success', 'goods_publish_success', 'health_check_success'],
      standalone_case_ids: ['health_check_success'],
      scene_orders: [
        {
          scene_id: 'goods_publish_flow',
          ordered_steps: ['goods_create_success', 'goods_publish_success'],
        },
      ],
    },
    markdown: '# 接口测试',
  }
}

test('buildApiTestFailureReplayPlan extracts failed scene and standalone case from junit xml', () => {
  const pack = buildSamplePack(`<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" failures="2" errors="0" skipped="0">
    <testcase classname="test_api_suite" name="test_scene_goods_publish_flow">
      <failure message="场景失败">AssertionError</failure>
    </testcase>
    <testcase classname="test_api_suite" name="test_case_health_check_success">
      <failure message="健康检查失败">AssertionError</failure>
    </testcase>
  </testsuite>
</testsuites>`)

  const replayPlan = buildApiTestFailureReplayPlan(pack)

  assert.ok(replayPlan)
  assert.deepEqual(replayPlan.failedSceneIds, ['goods_publish_flow'])
  assert.deepEqual(replayPlan.failedCaseIds, ['health_check_success'])
  assert.deepEqual(
    replayPlan.replayScenes.map((scene) => scene.scene_id),
    ['goods_publish_flow']
  )
  assert.deepEqual(
    replayPlan.replayCases.map((item) => item.case_id),
    ['goods_create_success', 'goods_publish_success', 'health_check_success']
  )
})

test('buildApiTestFailureReplayPlan expands standalone case dependencies', () => {
  const pack = buildSamplePack(`<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="test_api_suite" name="test_case_goods_publish_success">
      <failure message="发布失败">AssertionError</failure>
    </testcase>
  </testsuite>
</testsuites>`)

  const replayPlan = buildApiTestFailureReplayPlan({
    ...pack,
    scenes: [],
  })

  assert.ok(replayPlan)
  assert.deepEqual(replayPlan.failedSceneIds, [])
  assert.deepEqual(replayPlan.failedCaseIds, ['goods_publish_success'])
  assert.deepEqual(
    replayPlan.replayCases.map((item) => item.case_id),
    ['goods_create_success', 'goods_publish_success']
  )
})

test('buildFailedApiTestReplayPack returns replay subset and clears stale execution result', () => {
  const pack = buildSamplePack(`<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="test_api_suite" name="test_case_health_check_success">
      <failure message="健康检查失败">AssertionError</failure>
    </testcase>
  </testsuite>
</testsuites>`)

  const replayPack = buildFailedApiTestReplayPack(pack)

  assert.ok(replayPack)
  assert.equal(replayPack.execution, undefined)
  assert.equal(replayPack.report, undefined)
  assert.equal(replayPack.link_plan, undefined)
  assert.equal(replayPack.suite, undefined)
  assert.deepEqual(replayPack.scenes, [])
  assert.deepEqual(
    replayPack.cases.map((item) => item.case_id),
    ['health_check_success']
  )
  assert.match(replayPack.summary, /失败重跑/)
})

test('buildFailedApiTestReplayPack returns null when junit xml has no replayable failures', () => {
  const pack = buildSamplePack(`<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0">
    <testcase classname="test_api_suite" name="test_case_health_check_success" />
  </testsuite>
</testsuites>`)

  assert.equal(buildFailedApiTestReplayPack(pack), null)
})

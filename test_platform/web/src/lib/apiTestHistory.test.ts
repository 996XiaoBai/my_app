import test from 'node:test'
import assert from 'node:assert/strict'

import type { HistoryReportSummary } from './contracts.ts'
import { buildApiTestHistoryOverview } from './apiTestHistory.ts'

function buildHistoryItem(input: {
  id: string
  timestamp: string
  status: string
  passed: number
  failed: number
  total: number
  suiteVersion?: number
}): HistoryReportSummary {
  return {
    id: input.id,
    timestamp: input.timestamp,
    filename: `run-${input.id}`,
    type: 'api_test_gen',
    meta: {
      api_test_summary: {
        spec_title: '默认模块',
        suite_id: 'api_suite_default',
        suite_version: input.suiteVersion,
        status: input.status,
        case_count: 4,
        scene_count: 1,
        report_headline: '默认模块：执行结果',
        pass_rate: input.total > 0 ? Number(((input.passed / input.total) * 100).toFixed(1)) : null,
        stats: {
          total: input.total,
          passed: input.passed,
          failed: input.failed,
          errors: 0,
          skipped: 0,
        },
      },
    },
  }
}

test('buildApiTestHistoryOverview summarizes recent trend and selected comparison', () => {
  const overview = buildApiTestHistoryOverview(
    [
      buildHistoryItem({ id: 'run-003', timestamp: '2026-03-22T10:00:00', status: 'passed', passed: 4, failed: 0, total: 4, suiteVersion: 3 }),
      buildHistoryItem({ id: 'run-002', timestamp: '2026-03-21T10:00:00', status: 'failed', passed: 3, failed: 1, total: 4, suiteVersion: 2 }),
      buildHistoryItem({ id: 'run-001', timestamp: '2026-03-20T10:00:00', status: 'failed', passed: 2, failed: 2, total: 4, suiteVersion: 1 }),
    ],
    'run-003'
  )

  assert.equal(overview.totalRuns, 3)
  assert.equal(overview.passedRuns, 1)
  assert.equal(overview.averagePassRateText, '75.0%')
  assert.equal(overview.latestStatusLabel, '最近通过')
  assert.equal(overview.selectedComparison?.previousRunId, 'run-002')
  assert.equal(overview.selectedComparison?.passRateDeltaText, '+25.0%')
  assert.equal(overview.timeline[0].isSelected, true)
  assert.equal(overview.timeline[1].statusLabel, '失败')
})

test('buildApiTestHistoryOverview returns stable empty comparison when no previous comparable run exists', () => {
  const overview = buildApiTestHistoryOverview(
    [buildHistoryItem({ id: 'run-001', timestamp: '2026-03-22T10:00:00', status: 'passed', passed: 1, failed: 0, total: 1 })],
    'run-001'
  )

  assert.equal(overview.selectedComparison, null)
  assert.equal(overview.averagePassRateText, '100.0%')
  assert.equal(overview.timeline.length, 1)
})

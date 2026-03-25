import type {
  ApiTestExecutionStats,
  ApiTestHistorySummary,
  HistoryReportDetail,
  HistoryReportSummary,
} from './contracts.ts'

export interface ApiTestHistoryTimelineItem {
  id: string
  timestampLabel: string
  statusLabel: string
  passRateText: string
  suiteVersionText: string
  caseCountText: string
  isSelected: boolean
}

export interface ApiTestHistoryComparison {
  previousRunId: string
  previousTimestampLabel: string
  currentPassRateText: string
  previousPassRateText: string
  passRateDeltaText: string
  caseCountDeltaText: string
  sceneCountDeltaText: string
}

export interface ApiTestHistoryOverview {
  totalRuns: number
  passedRuns: number
  averagePassRateText: string
  latestStatusLabel: string
  latestPassRateText: string
  timeline: ApiTestHistoryTimelineItem[]
  selectedComparison: ApiTestHistoryComparison | null
}

interface ApiTestHistoryRecord {
  id: string
  timestamp: string
  summary: ApiTestHistorySummary
}

function normalizeNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function normalizeStats(value: unknown): ApiTestExecutionStats | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return undefined
  }

  const candidate = value as Record<string, unknown>
  return {
    total: normalizeNumber(candidate.total),
    passed: normalizeNumber(candidate.passed),
    failed: normalizeNumber(candidate.failed),
    errors: normalizeNumber(candidate.errors),
    skipped: normalizeNumber(candidate.skipped),
  }
}

function buildSummaryFromPackPayload(meta: Record<string, unknown>): ApiTestHistorySummary | null {
  const packPayload = meta.pack_payload
  if (!packPayload || typeof packPayload !== 'object' || Array.isArray(packPayload)) {
    return null
  }

  const payload = packPayload as Record<string, unknown>
  const spec = payload.spec as Record<string, unknown> | undefined
  const suite = payload.suite as Record<string, unknown> | undefined
  const report = payload.report as Record<string, unknown> | undefined
  const execution = payload.execution as Record<string, unknown> | undefined
  const cases = Array.isArray(payload.cases) ? payload.cases : []
  const scenes = Array.isArray(payload.scenes) ? payload.scenes : []
  const stats = normalizeStats(execution?.stats)
  const passRate = stats && stats.total > 0 ? Number(((stats.passed / stats.total) * 100).toFixed(1)) : null

  return {
    spec_title: String(spec?.title || '').trim(),
    suite_id: String(suite?.suite_id || '').trim(),
    suite_version: typeof suite?.suite_version === 'number' ? suite.suite_version : undefined,
    status: String(execution?.status || '').trim(),
    case_count: cases.length,
    scene_count: scenes.length,
    report_headline: String(report?.headline || '').trim(),
    stats,
    pass_rate: passRate,
  }
}

export function extractApiTestHistorySummary(
  report: Pick<HistoryReportSummary, 'meta'> | Pick<HistoryReportDetail, 'meta'>
): ApiTestHistorySummary | null {
  if (!report.meta || typeof report.meta !== 'object' || Array.isArray(report.meta)) {
    return null
  }

  const meta = report.meta as Record<string, unknown>
  const summary = meta.api_test_summary
  if (summary && typeof summary === 'object' && !Array.isArray(summary)) {
    const candidate = summary as Record<string, unknown>
    return {
      spec_title: String(candidate.spec_title || '').trim(),
      suite_id: String(candidate.suite_id || '').trim(),
      suite_version: typeof candidate.suite_version === 'number' ? candidate.suite_version : undefined,
      status: String(candidate.status || '').trim(),
      case_count: normalizeNumber(candidate.case_count),
      scene_count: normalizeNumber(candidate.scene_count),
      report_headline: String(candidate.report_headline || '').trim(),
      stats: normalizeStats(candidate.stats),
      pass_rate: typeof candidate.pass_rate === 'number' ? candidate.pass_rate : null,
    }
  }

  return buildSummaryFromPackPayload(meta)
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '未记录'
  }
  return `${value.toFixed(1)}%`
}

function formatHistoryTimestamp(value?: string): string {
  if (!value) {
    return '时间未知'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatStatusLabel(status?: string): string {
  const normalized = String(status || '').trim().toLowerCase()
  if (normalized === 'passed') {
    return '通过'
  }
  if (['failed', 'error'].includes(normalized)) {
    return '失败'
  }
  if (['running', 'executing'].includes(normalized)) {
    return '执行中'
  }
  return '未执行'
}

function formatDelta(value: number): string {
  if (value === 0) {
    return '持平'
  }
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`
}

function formatCountDelta(value: number): string {
  if (value === 0) {
    return '持平'
  }
  return `${value > 0 ? '+' : ''}${value} 条`
}

function normalizeHistoryRecords(reports: HistoryReportSummary[]): ApiTestHistoryRecord[] {
  return reports
    .map((report) => ({
      id: report.id,
      timestamp: String(report.timestamp || ''),
      summary: extractApiTestHistorySummary(report) || {},
    }))
    .filter((item) => Boolean(item.summary.stats || item.summary.status || item.summary.suite_id || item.summary.spec_title))
}

export function buildApiTestHistoryOverview(
  reports: HistoryReportSummary[],
  selectedReportId?: string
): ApiTestHistoryOverview {
  const records = normalizeHistoryRecords(reports).sort((left, right) => {
    const leftTime = new Date(left.timestamp).getTime()
    const rightTime = new Date(right.timestamp).getTime()
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
      return 0
    }
    return rightTime - leftTime
  })

  const passRateValues = records
    .map((item) => item.summary.pass_rate)
    .filter((value): value is number => typeof value === 'number')
  const passedRuns = records.filter((item) => String(item.summary.status || '').trim().toLowerCase() === 'passed').length
  const latestRecord = records[0]
  const selectedRecord = records.find((item) => item.id === selectedReportId) || latestRecord

  let selectedComparison: ApiTestHistoryComparison | null = null
  if (selectedRecord) {
    const comparableRecord = records
      .slice(records.findIndex((item) => item.id === selectedRecord.id) + 1)
      .find((item) => {
        const selectedSuiteId = String(selectedRecord.summary.suite_id || '').trim()
        const currentSuiteId = String(item.summary.suite_id || '').trim()
        if (selectedSuiteId && currentSuiteId) {
          return selectedSuiteId === currentSuiteId
        }
        return String(selectedRecord.summary.spec_title || '').trim() === String(item.summary.spec_title || '').trim()
      })

    if (comparableRecord) {
      selectedComparison = {
        previousRunId: comparableRecord.id,
        previousTimestampLabel: formatHistoryTimestamp(comparableRecord.timestamp),
        currentPassRateText: formatPercent(selectedRecord.summary.pass_rate),
        previousPassRateText: formatPercent(comparableRecord.summary.pass_rate),
        passRateDeltaText: formatDelta((selectedRecord.summary.pass_rate || 0) - (comparableRecord.summary.pass_rate || 0)),
        caseCountDeltaText: formatCountDelta((selectedRecord.summary.case_count || 0) - (comparableRecord.summary.case_count || 0)),
        sceneCountDeltaText: formatCountDelta((selectedRecord.summary.scene_count || 0) - (comparableRecord.summary.scene_count || 0)),
      }
    }
  }

  return {
    totalRuns: records.length,
    passedRuns,
    averagePassRateText: passRateValues.length > 0
      ? `${(passRateValues.reduce((total, value) => total + value, 0) / passRateValues.length).toFixed(1)}%`
      : '未记录',
    latestStatusLabel: latestRecord ? `最近${formatStatusLabel(latestRecord.summary.status)}` : '暂无历史',
    latestPassRateText: latestRecord ? formatPercent(latestRecord.summary.pass_rate) : '未记录',
    timeline: records.slice(0, 6).map((item) => ({
      id: item.id,
      timestampLabel: formatHistoryTimestamp(item.timestamp),
      statusLabel: formatStatusLabel(item.summary.status),
      passRateText: formatPercent(item.summary.pass_rate),
      suiteVersionText: item.summary.suite_version ? `v${String(item.summary.suite_version).padStart(3, '0')}` : '未版本化',
      caseCountText: `${item.summary.case_count || 0} 条用例 / ${item.summary.scene_count || 0} 个场景`,
      isSelected: item.id === selectedRecord?.id,
    })),
    selectedComparison,
  }
}

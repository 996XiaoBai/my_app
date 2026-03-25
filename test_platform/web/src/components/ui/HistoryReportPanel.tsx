'use client'

import { ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { apiClient } from '@/lib/api'
import { HistoryReportDetail, HistoryReportSummary } from '@/lib/contracts'
import { subscribeHistoryRefresh } from '@/lib/historyRefresh'
import { useAppStore } from '@/stores/useAppStore'

interface Props {
  types: string[]
  emptyTitle: string
  emptyDescription: string
  onLoadReport?: (report: HistoryReportDetail) => void
  loadActionLabel?: string
  renderListMeta?: (report: HistoryReportSummary) => ReactNode
  renderDetailActions?: (report: HistoryReportDetail) => ReactNode
  renderDetailContent?: (
    report: HistoryReportDetail,
    context: { reports: HistoryReportSummary[] }
  ) => ReactNode
}

const TYPE_LABELS: Record<string, string> = {
  review: '需求评审',
  test_case: '测试用例',
  req_analysis: '需求分析',
  test_point: '测试点提取',
  impact_analysis: '影响面分析',
  test_plan: '测试方案',
  test_data: '测试数据准备',
  log_diagnosis: '日志诊断',
  flowchart: '业务流程图',
  api_test_gen: '接口测试',
  api_perf_test_gen: '性能压测',
  auto_script_gen: 'UI 自动化',
  weekly_report: '测试周报',
}

function formatTimestamp(timestamp?: string): string {
  if (!timestamp) {
    return '时间未知'
  }

  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) {
    return timestamp
  }

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function HistoryReportPanel({
  types,
  emptyTitle,
  emptyDescription,
  onLoadReport,
  loadActionLabel = '载入',
  renderListMeta,
  renderDetailActions,
  renderDetailContent,
}: Props) {
  const appearance = useAppStore((state) => state.appearance)
  const [reports, setReports] = useState<HistoryReportSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedReport, setSelectedReport] = useState<HistoryReportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const typeKey = types.join(',')
  const selectedIdRef = useRef<string | null>(null)

  useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  const loadDetail = useCallback(async (reportId: string) => {
    setDetailLoading(true)
    try {
      const detail = await apiClient.getHistoryReport(reportId)
      selectedIdRef.current = reportId
      setSelectedId(reportId)
      setSelectedReport(detail)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '读取历史详情失败')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  const loadReports = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const reportTypes = typeKey ? typeKey.split(',') : []
      const items = await apiClient.getHistoryReports(reportTypes, 20)
      setReports(items)

      if (items.length === 0) {
        selectedIdRef.current = null
        setSelectedId(null)
        setSelectedReport(null)
        return
      }

      const currentSelectedId = selectedIdRef.current
      const nextId = items.some((item) => item.id === currentSelectedId) ? currentSelectedId : items[0].id
      if (nextId) {
        await loadDetail(nextId)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '读取历史记录失败')
      setReports([])
      selectedIdRef.current = null
      setSelectedId(null)
      setSelectedReport(null)
    } finally {
      setLoading(false)
    }
  }, [loadDetail, typeKey])

  useEffect(() => {
    void loadReports()
  }, [loadReports, typeKey])

  useEffect(() => {
    return subscribeHistoryRefresh(() => {
      void loadReports()
    })
  }, [loadReports])

  const detailContent = selectedReport ? renderDetailContent?.(selectedReport, { reports }) : null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[var(--text-primary)] font-semibold text-sm">历史</p>
          <p className="text-[var(--text-secondary)] text-xs mt-1">最近结果。</p>
        </div>
        <button
          onClick={() => void loadReports()}
          className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
          style={{ borderColor: 'var(--border)' }}
        >
          刷新
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3 text-red-400 text-xs">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 text-[var(--text-secondary)]">
          <div className="w-6 h-6 border-2 border-white/10 border-t-[#8B5CF6] rounded-full animate-spin mb-4" />
          <p className="text-sm">正在读取...</p>
        </div>
      ) : reports.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center" style={{ color: 'var(--text-muted)' }}>
          <span className="text-4xl mb-4">🕑</span>
          <p className="font-medium text-sm text-[var(--text-secondary)]">{emptyTitle}</p>
          <p className="mt-2 text-xs">{emptyDescription}</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid var(--border-soft)', backgroundColor: 'var(--bg-contrast)' }}>
            <div className="px-4 py-3 text-xs font-semibold tracking-[1px] text-[var(--text-secondary)] uppercase" style={{ borderBottom: '1px solid var(--border-soft)' }}>
              列表
            </div>
            <div className="max-h-[560px] overflow-y-auto">
              {reports.map((report) => {
                const active = report.id === selectedId
                return (
                  <button
                    key={report.id}
                    onClick={() => void loadDetail(report.id)}
                    className={`w-full text-left px-4 py-3 transition-all ${
                      active ? 'bg-[#8B5CF6]/10 border-[#8B5CF6]/15' : 'hover:bg-[var(--bg-soft)]'
                    }`}
                    style={{ borderBottom: '1px solid var(--border-soft)' }}
                  >
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        active ? 'bg-[#8B5CF6]/20 text-[#A78BFA]' : 'bg-[var(--bg-muted)] text-[var(--text-secondary)]'
                      }`}>
                        {TYPE_LABELS[report.type] || report.type}
                      </span>
                    </div>
                    <p className={`font-medium text-sm truncate ${active ? 'text-[var(--text-primary)]' : 'text-[var(--text-strong)]'}`}>
                      {report.filename || '未命名历史记录'}
                    </p>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-1">{formatTimestamp(report.timestamp)}</p>
                    {renderListMeta ? <div className="mt-2">{renderListMeta(report)}</div> : null}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="rounded-2xl overflow-hidden min-h-[560px]" style={{ border: '1px solid var(--border-soft)', backgroundColor: 'var(--bg-soft)' }}>
            {detailLoading && !selectedReport ? (
              <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)]">
                <div className="w-6 h-6 border-2 border-white/10 border-t-[#8B5CF6] rounded-full animate-spin mb-4" />
                <p className="text-sm">正在读取历史详情...</p>
              </div>
            ) : selectedReport ? (
              <>
                <div className="px-5 py-4 flex items-start justify-between gap-4" style={{ borderBottom: '1px solid var(--border-soft)' }}>
                  <div className="min-w-0">
                    <p className="text-[var(--text-primary)] font-semibold text-sm truncate">
                      {selectedReport.filename || '未命名历史记录'}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 mt-2 text-[11px] text-[var(--text-secondary)]">
                      <span>{TYPE_LABELS[selectedReport.type] || selectedReport.type}</span>
                      <span>•</span>
                      <span>{formatTimestamp(selectedReport.timestamp)}</span>
                    </div>
                  </div>
                  <div className="flex flex-wrap justify-end gap-2 flex-shrink-0">
                    {onLoadReport && (
                      <button
                        onClick={() => onLoadReport(selectedReport)}
                        className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        {loadActionLabel}
                      </button>
                    )}
                    {renderDetailActions?.(selectedReport)}
                    <button
                      onClick={() => void navigator.clipboard.writeText(selectedReport.content)}
                      className="px-3 py-1.5 rounded-lg border text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all text-[11px]"
                      style={{ borderColor: 'var(--border)' }}
                    >
                      复制 Markdown
                    </button>
                  </div>
                </div>
                <div className="p-5 overflow-y-auto max-h-[500px]">
                  {detailContent}
                  <div className={`prose prose-sm max-w-none ${appearance === 'dark' ? 'prose-invert' : ''} ${detailContent ? 'mt-5' : ''}`}>
                    <ReactMarkdown>{selectedReport.content}</ReactMarkdown>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-[var(--text-secondary)]">
                <p className="text-sm">请选择左侧历史记录查看详情。</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

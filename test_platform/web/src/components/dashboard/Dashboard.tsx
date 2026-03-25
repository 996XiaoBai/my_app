'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  CheckCircle2,
  Gauge,
  Layers3,
  MessageSquareText,
  ShieldAlert,
  SquareTerminal,
} from 'lucide-react'

import CollaborationRail, { type RailSection } from '@/components/ui/CollaborationRail'
import { apiClient } from '@/lib/api'
import type { DashboardActivity, DashboardMetric } from '@/lib/contracts'
import { buildTaskWorkbenchSummary } from '@/lib/taskWorkbench'
import { formatTimeAgo } from '@/lib/utils'
import {
  buildDashboardQuickAccessCards,
  buildDashboardQuickAccessOverview,
  buildDashboardSnapshotBadges,
  buildDashboardStageTrack,
  compactDashboardMetricDelta,
  compactRailSections,
  selectPrimaryDashboardMetrics,
} from '@/lib/workbenchPresentation'
import { getRailWidthStyle } from '@/lib/workbenchLayout'
import { useAppStore } from '@/stores/useAppStore'

const quickAccessToneClasses = {
  neutral: 'border-[color:var(--border)] bg-[var(--surface-inset)] text-[var(--text-secondary)]',
  accent: 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] text-[var(--accent-primary)]',
  success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-500',
  warning: 'border-amber-500/20 bg-amber-500/10 text-amber-500',
} as const

const quickAccessSurfaceClasses = {
  neutral: 'border-[color:var(--border-soft)] bg-[var(--surface-panel)]',
  accent: 'border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)]/70',
  success: 'border-emerald-500/20 bg-emerald-500/5',
  warning: 'border-amber-500/20 bg-amber-500/5',
} as const

function normalizeMetricTone(index: number) {
  const tones = [
    'text-[var(--accent-primary)]',
    'text-amber-500',
    'text-emerald-500',
    'text-red-500',
  ]

  return tones[index % tones.length]
}

export default function Dashboard() {
  const {
    currentProject,
    currentVersion,
    pipelineStatus,
    openInsight,
    setActiveNav,
    moduleSessions,
    reviewFindings,
    requirementContextId,
    taskSnapshots,
    loadTaskSnapshot,
  } = useAppStore()
  const collaborationRailCollapsed = useAppStore((s) => s.collaborationRailCollapsed)

  const [metrics, setMetrics] = useState<DashboardMetric[]>([])
  const [recentActivities, setRecentActivities] = useState<DashboardActivity[]>([])

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await apiClient.getDashboardStats()
        setMetrics(Array.isArray(data.metrics) ? data.metrics : [])
        setRecentActivities(Array.isArray(data.recent_activities) ? data.recent_activities : [])
      } catch (error) {
        console.error('Fetch stats failed:', error)
      }
    }

    void fetchStats()
    const timer = setInterval(fetchStats, 15000)
    return () => clearInterval(timer)
  }, [])

  const taskSummary = useMemo(
    () =>
      buildTaskWorkbenchSummary({
        moduleSessions,
        reviewFindings,
        requirementContextId,
      }),
    [moduleSessions, requirementContextId, reviewFindings]
  )

  const displayMetrics = metrics.length > 0
    ? metrics
    : [
        { label: '本周执行总量', value: '-', delta: '等待接入指标', color: '', bg: '', border: '' },
        { label: '高风险需求', value: String(taskSummary.riskCount || 0), delta: '来自最近评审', color: '', bg: '', border: '' },
        { label: '已完成资产', value: String(taskSummary.assets.filter((asset) => asset.done).length), delta: '当前任务沉淀', color: '', bg: '', border: '' },
        { label: '待处理缺陷', value: String(pipelineStatus.fail), delta: '来自流水线回传', color: '', bg: '', border: '' },
      ]
  const primaryMetrics = selectPrimaryDashboardMetrics(displayMetrics)
  const quickAccessCards = buildDashboardQuickAccessCards({
    currentStage: taskSummary.currentStage,
    primaryNavId: taskSummary.primaryAction.navId,
    riskCount: taskSummary.riskCount,
    hasRequirement: Boolean(taskSummary.requirement || taskSummary.hasContext),
    assets: taskSummary.assets.map((asset) => ({
      id: asset.id,
      done: asset.done,
    })),
  })
  const quickAccessOverview = buildDashboardQuickAccessOverview(quickAccessCards)
  const stageTrack = buildDashboardStageTrack(taskSummary.currentStage)

  const completedAssets = taskSummary.assets.filter((asset) => asset.done)
  const recentTaskSnapshots = taskSnapshots.slice(0, 4)

  const restoreTaskSnapshot = (snapshotId: string, navId: string) => {
    loadTaskSnapshot(snapshotId)
    setActiveNav(navId)
  }

  const railLayoutStyle = getRailWidthStyle(collaborationRailCollapsed)

  const collaborationSections: RailSection[] = [
    {
      id: 'activity',
      title: '最近动态',
      description: '像 issue / copilot 一样聚合任务恢复点、运行反馈与历史动作。',
      entries: (recentTaskSnapshots.length > 0
        ? recentTaskSnapshots.slice(0, 3).map((snapshot) => ({
            id: snapshot.id,
            label: snapshot.title,
            value: snapshot.currentStageLabel,
            detail: `${snapshot.sourceLabel} · ${formatTimeAgo(new Date(snapshot.updatedAt))}`,
            status: 'done' as const,
            onClick: () => restoreTaskSnapshot(snapshot.id, snapshot.primaryNavId),
          }))
        : recentActivities.slice(0, 3).map((activity) => ({
            id: String(activity.id),
            label: activity.action,
            value: activity.target,
            detail: `${formatTimeAgo(new Date(activity.timestamp))} · ${activity.status === 'running' ? '执行中' : activity.status === 'fail' ? '需关注' : '已完成'}`,
            status: activity.status === 'running' ? 'running' as const : activity.status === 'fail' ? 'warning' as const : 'done' as const,
            onClick: () => openInsight(`最近动作：${activity.action} · ${activity.target}`),
          }))),
    },
    {
      id: 'agents',
      title: '下一步',
      description: '围绕当前任务主线给出下一步可执行动作。',
      entries: taskSummary.nextActions.map((action, index) => ({
        id: action.navId,
        label: index === 0 ? '推荐下一步' : '并行补充',
        value: action.label,
        detail: action.description,
        status: index === 0 ? 'running' as const : 'idle' as const,
        onClick: () => setActiveNav(action.navId),
      })),
    },
    {
      id: 'signals',
      title: '任务信号',
      description: '把风险、上下文和资产完成度收拢到同一侧栏。',
      entries: [
        {
          id: 'context',
          label: '上下文',
          value: taskSummary.hasContext ? '已联动' : '待联动',
          detail: taskSummary.hasContext ? '可跨模块连续工作' : '建议先从需求评审导入上下文',
          status: taskSummary.hasContext ? 'done' : 'warning',
        },
        {
          id: 'risk',
          label: '风险',
          value: taskSummary.riskCount > 0 ? `${taskSummary.riskCount} 风险` : '低风险',
          detail: taskSummary.riskCount > 0 ? '建议先处理高风险发现，再扩展设计' : '当前未发现高风险阻断',
          status: taskSummary.riskCount > 0 ? 'warning' : 'done',
        },
        {
          id: 'assets',
          label: '资产',
          value: `${completedAssets.length}/${taskSummary.assets.length}`,
          detail: '评审、设计与自动化资产的完成度',
          status: completedAssets.length === taskSummary.assets.length ? 'done' : 'idle',
        },
      ],
    },
  ]

  return (
    <div className="animate-fade-in">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_var(--rail-width)]" style={railLayoutStyle}>
        <div className="space-y-5">
          <section className="console-panel overflow-hidden">
            <div className="grid gap-5 border-b px-5 py-5 xl:grid-cols-[minmax(0,1fr)_auto]" style={{ borderColor: 'var(--border-soft)' }}>
              <div className="min-w-0">
                <div className="mb-3 flex flex-wrap gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent-primary)]">
                    <SquareTerminal className="h-3 w-3" />
                    {taskSummary.currentStageLabel}
                  </span>
                  <span className="inline-flex items-center rounded-full border border-[color:var(--border)] bg-[var(--surface-inset)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]">
                    {currentVersion}
                  </span>
                  {taskSummary.hasContext && (
                    <span className="inline-flex items-center rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-500">
                      已联动
                    </span>
                  )}
                  {taskSummary.riskCount > 0 && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-500">
                      <ShieldAlert className="h-3 w-3" />
                      {taskSummary.riskCount} 风险
                    </span>
                  )}
                </div>
                <h1 className="text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
                  {taskSummary.title}
                </h1>
                <div className="mt-3 truncate text-sm font-medium text-[var(--text-secondary)]">
                  {currentProject || '任务工作台'}
                </div>
              </div>

              <div className="flex flex-wrap items-start gap-2 xl:justify-end">
                <button
                  type="button"
                  onClick={() => setActiveNav('review')}
                  className="flex items-center gap-2 rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-4 py-2.5 text-sm font-semibold text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]"
                >
                  新建任务
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    recentTaskSnapshots[0]
                      ? restoreTaskSnapshot(recentTaskSnapshots[0].id, recentTaskSnapshots[0].primaryNavId)
                      : setActiveNav(taskSummary.primaryAction.navId)
                  }
                  className="rounded-xl border px-4 py-2.5 text-sm font-medium text-[var(--text-primary)] transition-colors hover:border-[color:var(--border-hover)] hover:bg-[var(--surface-inset)]"
                  style={{ borderColor: 'var(--border)' }}
                >
                  {recentTaskSnapshots[0] ? '恢复' : '继续'}
                </button>
              </div>
            </div>

            <div className="grid gap-5 px-5 py-5 lg:grid-cols-[minmax(0,1fr)_300px]">
              <div>
                <div className="console-kicker">阶段</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="console-chip">{taskSummary.sourceLabel}</span>
                  <span className="console-chip">{taskSummary.primaryAction.label}</span>
                  <span className="console-chip">{completedAssets.length}/{taskSummary.assets.length} 完成</span>
                </div>

                <div className="mt-4 rounded-2xl border p-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
                  <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
                    {stageTrack.map((step, index) => (
                      <div
                        key={step.id}
                        className="rounded-xl border px-3 py-3"
                        style={{
                          borderColor: step.state === 'active' ? 'var(--border-hover)' : 'var(--border-soft)',
                          backgroundColor: step.state === 'active'
                            ? 'var(--surface-accent)'
                            : step.state === 'completed'
                              ? 'color-mix(in srgb, var(--accent-emerald) 10%, var(--surface-panel))'
                              : 'var(--surface-panel)',
                        }}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
                            {String(index + 1).padStart(2, '0')}
                          </span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              step.state === 'completed'
                                ? 'bg-emerald-500/10 text-emerald-500'
                                : step.state === 'active'
                                  ? 'bg-[var(--surface-panel)] text-[var(--accent-primary)]'
                                  : 'bg-[var(--surface-inset)] text-[var(--text-muted)]'
                            }`}
                          >
                            {step.shortLabel}
                          </span>
                        </div>
                        <div className="mt-2 text-sm font-medium text-[var(--text-primary)]">{step.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="console-panel-muted p-4">
                <div className="console-kicker">下一步</div>
                <button
                  type="button"
                  onClick={() => setActiveNav(taskSummary.primaryAction.navId)}
                  className="mt-3 flex w-full items-center justify-between rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] px-4 py-3 text-left text-sm font-semibold text-[var(--accent-primary)] transition-colors hover:border-[color:var(--border-hover)]"
                >
                  <span>{taskSummary.primaryAction.label}</span>
                  <ArrowRight className="h-3.5 w-3.5 shrink-0" />
                </button>
                <div className="mt-2 space-y-2">
                  {taskSummary.nextActions.slice(1).map((action) => (
                    <button
                      key={action.label}
                      type="button"
                      onClick={() => setActiveNav(action.navId)}
                      className="console-inset flex w-full items-start justify-between gap-3 px-3 py-3 text-left transition-colors hover:border-[color:var(--border-hover)]"
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-[var(--text-primary)]">{action.label}</div>
                      </div>
                      <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {primaryMetrics.map((metric, index) => (
              <div key={metric.label} className="console-panel p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold text-[var(--text-primary)]">{metric.label}</div>
                  <span className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]">
                    {compactDashboardMetricDelta(metric)}
                  </span>
                </div>
                <div className={`mt-3 text-[28px] font-semibold tracking-tight ${normalizeMetricTone(index)}`}>
                  {metric.value}
                </div>
              </div>
            ))}
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <div className="console-panel overflow-hidden">
              <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: 'var(--border-soft)' }}>
                <div className="text-sm font-semibold text-[var(--text-primary)]">最近任务</div>
                <Layers3 className="h-4 w-4 text-[var(--accent-primary)]" />
              </div>

              <div className="divide-y console-divider">
                {recentTaskSnapshots.length > 0 ? (
                  recentTaskSnapshots.map((snapshot) => (
                    <button
                      key={snapshot.id}
                      type="button"
                      onClick={() => restoreTaskSnapshot(snapshot.id, snapshot.primaryNavId)}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-[var(--surface-inset)]"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--accent-primary)]">
                        <CheckCircle2 className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-[var(--text-primary)]">{snapshot.title}</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {buildDashboardSnapshotBadges(snapshot).map((badge) => (
                            <span
                              key={`${snapshot.id}-${badge}`}
                              className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]"
                            >
                              {badge}
                            </span>
                          ))}
                        </div>
                      </div>
                      <span className="shrink-0 font-mono text-[11px] text-[var(--text-muted)]">
                        {formatTimeAgo(new Date(snapshot.updatedAt))}
                      </span>
                    </button>
                  ))
                ) : recentActivities.length > 0 ? (
                  recentActivities.map((activity) => (
                    <button
                      key={activity.id}
                      type="button"
                      onClick={() => openInsight(`最近动作：${activity.action} · ${activity.target}`)}
                      className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-[var(--surface-inset)]"
                    >
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--accent-primary)]">
                        <MessageSquareText className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-[var(--text-primary)]">{activity.action}</div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <span className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]">
                            {activity.status === 'running' ? '执行中' : activity.status === 'fail' ? '需关注' : '已完成'}
                          </span>
                          <span className="max-w-[220px] truncate rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]">
                            {activity.target}
                          </span>
                        </div>
                      </div>
                      <span className="shrink-0 font-mono text-[11px] text-[var(--text-muted)]">
                        {formatTimeAgo(new Date(activity.timestamp))}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="flex min-h-[260px] items-center justify-center px-6 text-center text-sm leading-7 text-[var(--text-secondary)]">
                    还没有任务，从“新建任务”开始。
                  </div>
                )}
              </div>
            </div>

            <div>
              <section className="console-panel p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <div className="console-kicker">快捷入口</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {quickAccessOverview.map((item) => (
                        <span
                          key={item}
                          className="rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)]"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                  <Gauge className="h-4 w-4 text-[var(--accent-primary)]" />
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {quickAccessCards.map((card) => (
                    <button
                      key={card.id}
                      type="button"
                      onClick={() => setActiveNav(card.navId)}
                      className={`flex min-h-[116px] w-full flex-col justify-between rounded-2xl border px-3.5 py-3.5 text-left transition-colors hover:border-[color:var(--border-hover)] ${quickAccessSurfaceClasses[card.tone]}`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-start justify-between gap-3">
                          <div className="text-sm font-semibold text-[var(--text-primary)]">{card.label}</div>
                          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${quickAccessToneClasses[card.tone]}`}>
                            {card.stateLabel}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-medium text-[var(--text-secondary)]">{card.actionLabel}</span>
                        <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[color:var(--border-soft)] bg-[var(--surface-panel)] text-[var(--text-muted)]">
                          <ArrowRight className="h-3.5 w-3.5" />
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            </div>
          </section>
        </div>

        <CollaborationRail
          title="任务协作"
          subtitle=""
          tags={[
            { label: taskSummary.currentStageLabel, tone: 'accent' },
            { label: taskSummary.riskCount > 0 ? `${taskSummary.riskCount} 风险` : '低风险', tone: taskSummary.riskCount > 0 ? 'warning' : 'neutral' },
          ]}
          sections={compactRailSections(collaborationSections)}
          actions={[
            { label: '去评审', onClick: () => setActiveNav('review'), tone: 'accent' },
            { label: '去用例', onClick: () => setActiveNav('test-cases') },
          ]}
        />
      </div>
    </div>
  )
}

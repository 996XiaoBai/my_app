'use client'

import React, { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Maximize2,
  MessageSquareText,
  Minimize2,
  Terminal,
  X,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import { getTopBarOffset } from '@/lib/workbenchLayout'
import { useAppStore } from '@/stores/useAppStore'

export default function InsightPanel() {
  const {
    insightOpen,
    insightContent,
    insightType,
    insightSteps,
    insightFocusMode,
    highRiskMode,
    topBarCollapsed,
    expertConflictDecision,
    closeInsight,
    setInsightFocusMode,
    setExpertDecision,
  } = useAppStore()

  const [reasonDraft, setReasonDraft] = useState('')

  if (!insightOpen) return null

  const panelTop = getTopBarOffset(topBarCollapsed)

  return (
    <>
      <div
        className={cn(
          'fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-all duration-500 pointer-events-none',
          insightFocusMode && 'opacity-100 pointer-events-auto'
        )}
        onClick={() => setInsightFocusMode(false)}
      />

      <aside
        aria-label="AI 洞察面板"
        className={cn(
          'fixed z-[55] border backdrop-blur-xl transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]',
          insightFocusMode
            ? 'inset-4 w-auto rounded-3xl translate-x-0 opacity-100 scale-100'
            : `top-14 right-4 bottom-4 w-80 rounded-3xl ${insightOpen ? 'translate-x-0 opacity-100 scale-100' : 'translate-x-12 opacity-0 scale-95 pointer-events-none'}`
        )}
        style={{
          ...(insightFocusMode ? {} : { top: panelTop }),
          backgroundColor: 'color-mix(in srgb, var(--surface-rail) 94%, transparent)',
          borderColor: 'var(--border)',
          boxShadow: 'var(--shadow-rail)',
        }}
      >
        <div
          className="flex items-center justify-between border-b px-5"
          style={{ minHeight: 'var(--click-row)', borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
        >
          <div className="flex items-center gap-2">
            <div
              className={cn(
                'h-2 w-2 rounded-full transition-all duration-1000',
                highRiskMode ? 'bg-amber-500 animate-status-pulse' : 'bg-[var(--accent-primary)]'
              )}
            />
            <span className="font-mono text-[var(--font-xs)] font-bold uppercase tracking-wider text-[var(--text-primary)]">
              洞察控制台
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setInsightFocusMode(!insightFocusMode)}
              className="flex items-center justify-center rounded-lg text-[var(--text-secondary)] transition-all hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
              style={{ width: 'var(--click-min)', height: 'var(--click-min)' }}
            >
              {insightFocusMode ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
            <button
              onClick={closeInsight}
              className="flex items-center justify-center rounded-lg text-[var(--text-secondary)] transition-all hover:bg-[var(--surface-inset)] hover:text-[var(--text-primary)]"
              style={{ width: 'var(--click-min)', height: 'var(--click-min)' }}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div
          className={cn(
            'custom-scrollbar h-[calc(100%-48px)] overflow-y-auto p-5',
            insightFocusMode ? 'grid grid-cols-2 gap-8 content-start' : 'space-y-6'
          )}
        >
          <div className="space-y-6">
            {insightType === 'progress' && (
              <div className="space-y-4">
                {insightSteps.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <div className="flex flex-col items-center">
                      <div
                        className={cn(
                          'flex h-6 w-6 items-center justify-center rounded-full border-2 transition-all',
                          step.status === 'done'
                            ? 'border-[color:var(--accent-primary)] bg-[var(--surface-accent)] text-[var(--accent-primary)]'
                            : step.status === 'loading'
                              ? 'border-[var(--accent-primary)] border-t-transparent animate-spin'
                              : 'border-[color:var(--border-soft)] text-[var(--text-muted)]'
                        )}
                      >
                        {step.status === 'done' && <CheckCircle2 className="h-3.5 w-3.5" />}
                      </div>
                      {idx < insightSteps.length - 1 && (
                        <div
                          className="my-1 h-6 w-[2px]"
                          style={{ backgroundColor: step.status === 'done' ? 'color-mix(in srgb, var(--accent-primary) 40%, transparent)' : 'var(--border-soft)' }}
                        />
                      )}
                    </div>
                    <p
                      className={cn(
                        'pt-0.5 text-[var(--font-sm)] font-medium',
                        step.status === 'done'
                          ? 'text-[var(--text-primary)]'
                          : step.status === 'loading'
                            ? 'text-[var(--accent-primary)]'
                            : 'text-[var(--text-muted)]'
                      )}
                    >
                      {step.label}
                    </p>
                  </div>
                ))}
              </div>
            )}

            {insightContent && (
              <div className="space-y-4">
                <div
                  className={cn(
                    'animate-scale-in rounded-xl border p-4',
                    insightType === 'risk'
                      ? 'border-amber-500/20 bg-amber-500/[0.06]'
                      : 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)]'
                  )}
                >
                  {insightType === 'risk' && (
                    <div className="mb-3 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                      <span className="text-[var(--font-xs)] font-bold uppercase tracking-widest text-amber-500">
                        潜在高危风险
                      </span>
                    </div>
                  )}
                  <div className="text-[var(--text-secondary)]" style={{ fontSize: 'var(--font-base)', lineHeight: 'var(--lh-relaxed)' }}>
                    {insightContent}
                  </div>
                </div>

                {insightType === 'risk' && insightContent.includes('冲突') && (
                  <div className="space-y-4 rounded-xl border border-[color:var(--accent-primary-soft)] bg-[var(--surface-accent)] p-4">
                    <div className="flex items-center gap-2 border-b pb-2" style={{ borderColor: 'var(--border-soft)' }}>
                      <MessageSquareText className="h-4 w-4 text-[var(--accent-primary)]" />
                      <p className="text-[var(--font-xs)] font-bold uppercase tracking-wider text-[var(--text-primary)]">
                        专家仲裁审计
                      </p>
                    </div>

                    <div className="space-y-2">
                      {['FINANCIAL', 'SECURITY'].map((decision) => (
                        <button
                          key={decision}
                          onClick={() => setExpertDecision(decision, reasonDraft)}
                          disabled={!reasonDraft.trim()}
                          className={cn(
                            'flex w-full items-center justify-between rounded-lg border px-4 text-left transition-all',
                            expertConflictDecision === decision
                              ? 'border-[color:var(--accent-primary)] bg-[var(--accent-primary)] text-[var(--surface-panel)]'
                              : 'border-[color:var(--border-soft)] bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50'
                          )}
                          style={{ fontSize: 'var(--font-sm)', minHeight: 'var(--click-min)' }}
                        >
                          <span>{decision === 'FINANCIAL' ? '采纳财务审计视角' : '采纳安全专家视角'}</span>
                          {expertConflictDecision === decision ? <CheckCircle2 className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                      ))}
                    </div>

                    <div className="space-y-2 pt-2">
                      <label className="text-[var(--font-xs)] font-bold uppercase text-[var(--text-secondary)]">
                        决策理由（审计必填）
                      </label>
                      <textarea
                        value={reasonDraft}
                        onChange={(e) => setReasonDraft(e.target.value)}
                        placeholder="请填写本次决策的工程依据..."
                        className="h-24 w-full resize-none rounded-lg border p-3 text-[var(--text-primary)] outline-none transition-all"
                        style={{ backgroundColor: 'var(--surface-panel)', borderColor: 'var(--border-soft)' }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {insightFocusMode && (
            <div className="animate-fade-in">
              <div
                className="flex h-full flex-col gap-4 rounded-2xl border p-6"
                style={{ backgroundColor: 'var(--surface-panel-muted)', borderColor: 'var(--border-soft)' }}
              >
                <div className="flex items-center gap-2 border-b pb-2" style={{ borderColor: 'var(--border-soft)' }}>
                  <Terminal className="h-4 w-4 text-[var(--text-secondary)]" />
                  <h4 className="text-[var(--font-xs)] font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                    深度工程追踪台
                  </h4>
                </div>
                <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto font-mono text-[var(--text-secondary)]" style={{ fontSize: 'var(--font-sm)' }}>
                  <p className="text-[var(--accent-primary)]">{'// 分析器正在索引仓库：my-billing-service'}</p>
                  <p className="flex items-center gap-2 text-emerald-500">
                    <Activity className="h-4 w-4" /> 已识别核心逻辑：src/logic/precision.go:45
                  </p>
                  <div
                    className="rounded-xl border p-4 leading-relaxed"
                    style={{ fontSize: 'var(--font-xs)', backgroundColor: 'var(--surface-panel)', borderColor: 'var(--border-soft)' }}
                  >
                    <p className="text-red-400 opacity-60">- amount_f64 := req.Body.Price * (1.0 - discount)</p>
                    <p className="text-emerald-400">+ amount_dec := decimal.NewFromFloat(req.Body.Price).Mul(decimal.NewFromFloat(1.0).Sub(discount_dec))</p>
                  </div>
                  <p className="italic text-amber-500/80">
                    影响：该改动将传播至 Kafka 事件 &quot;order.created.v1&quot;，下游账本存在 1 分精度偏差风险。
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}

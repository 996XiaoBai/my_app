'use client'

import type { ApiTestExecutionResult } from '@/lib/contracts'
import { buildApiTestExecutionPanelCopy } from '@/lib/workbenchPresentation'

interface Props {
  execution?: ApiTestExecutionResult
  className?: string
}

function resolveStatusClassName(status?: string): string {
  const normalized = String(status || '').trim().toLowerCase()

  if (['passed', 'success', 'completed'].includes(normalized)) {
    return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
  }

  if (['failed', 'fail', 'error'].includes(normalized)) {
    return 'border-amber-500/25 bg-amber-500/10 text-amber-300'
  }

  if (['running', 'executing'].includes(normalized)) {
    return 'border-sky-500/25 bg-sky-500/10 text-sky-300'
  }

  return 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]'
}

export default function ApiTestExecutionPanel({ execution, className = '' }: Props) {
  const copy = buildApiTestExecutionPanelCopy(execution)
  const normalizedStatus = String(execution?.status || '').trim().toLowerCase()
  const shouldShowFailureSection = copy.failureCases.length > 0 || ['failed', 'fail', 'error'].includes(normalizedStatus)

  return (
    <section className={`space-y-4 ${className}`.trim()}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
          <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">执行状态</div>
          <div className={`mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${resolveStatusClassName(execution?.status)}`}>
            {copy.statusLabel}
          </div>
          {execution?.run_id && (
            <div className="mt-3 text-[11px] text-[var(--text-secondary)]">
              批次：<span className="font-mono">{execution.run_id}</span>
            </div>
          )}
        </div>

        <div className="rounded-2xl border p-4 md:col-span-1 xl:col-span-3" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
          <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">执行统计</div>
          <div className="mt-3 text-sm font-medium text-[var(--text-primary)]">{copy.statsText}</div>
          <div className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{copy.summary}</div>
        </div>

        <div className="rounded-2xl border p-4 md:col-span-2" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
          <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">执行命令</div>
          <pre className="mt-3 whitespace-pre-wrap break-all font-mono text-xs leading-6 text-[var(--text-primary)]">
            {copy.commandText}
          </pre>
        </div>

        <div className="rounded-2xl border p-4 md:col-span-2" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
          <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">运行目录</div>
          <pre className="mt-3 whitespace-pre-wrap break-all font-mono text-xs leading-6 text-[var(--text-primary)]">
            {copy.runDirectoryText}
          </pre>
        </div>
      </div>

      <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
        <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">产物路径</div>
        {copy.artifacts.length > 0 ? (
          <div className="mt-3 space-y-2">
            {copy.artifacts.map((artifact) => (
              <div
                key={artifact.key}
                className="rounded-xl border px-3 py-2.5"
                style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
              >
                <div className="text-[11px] text-[var(--text-secondary)]">{artifact.label}</div>
                <pre className="mt-1 whitespace-pre-wrap break-all font-mono text-xs leading-6 text-[var(--text-primary)]">
                  {artifact.value}
                </pre>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-3 text-sm text-[var(--text-secondary)]">{copy.artifactEmptyText}</div>
        )}
      </div>

      {shouldShowFailureSection && (
        <div className="rounded-2xl border p-4" style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}>
          <div className="text-[11px] font-semibold tracking-[0.16em] text-[var(--text-muted)] uppercase">失败用例</div>
          {copy.failureCases.length > 0 ? (
            <div className="mt-3 space-y-2">
              {copy.failureCases.map((item) => (
                <div
                  key={item.key}
                  className="rounded-xl border px-3 py-2.5"
                  style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-inset)' }}
                >
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                      item.kind === 'error'
                        ? 'border-amber-500/25 bg-amber-500/10 text-amber-300'
                        : 'border-rose-500/25 bg-rose-500/10 text-rose-300'
                    }`}>
                      {item.kind === 'error' ? '异常' : '失败'}
                    </span>
                    <span className="font-mono text-xs text-[var(--text-primary)] break-all">{item.title}</span>
                  </div>
                  <div className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{item.detail}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 text-sm text-[var(--text-secondary)]">{copy.failureEmptyText}</div>
          )}
        </div>
      )}

      <div className="grid gap-3 xl:grid-cols-2">
        <details
          open={Boolean(copy.stdoutText)}
          className="rounded-2xl border"
          style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
        >
          <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
            标准输出
          </summary>
          <div className="border-t px-4 py-3" style={{ borderColor: 'var(--border-soft)' }}>
            <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-6 text-[var(--text-secondary)]">
              {copy.stdoutText || copy.stdoutEmptyText}
            </pre>
          </div>
        </details>

        <details
          open={Boolean(copy.stderrText)}
          className="rounded-2xl border"
          style={{ borderColor: 'var(--border-soft)', backgroundColor: 'var(--surface-panel-muted)' }}
        >
          <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
            错误输出
          </summary>
          <div className="border-t px-4 py-3" style={{ borderColor: 'var(--border-soft)' }}>
            <pre className="whitespace-pre-wrap break-all font-mono text-xs leading-6 text-[var(--text-secondary)]">
              {copy.stderrText || copy.stderrEmptyText}
            </pre>
          </div>
        </details>
      </div>
    </section>
  )
}

'use client'

import ReactMarkdown from 'react-markdown'

import type { TestDataPack } from '@/lib/contracts'

type MarkdownTable = {
  headers: string[]
  rows: string[][]
}

function parseMarkdownTable(markdown: string): MarkdownTable | null {
  const lines = markdown
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length < 2 || !lines[0].includes('|') || !lines[1].includes('---')) {
    return null
  }

  const parseRow = (line: string) =>
    line
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((cell) => cell.trim().replace(/\\\|/g, '|'))

  const headers = parseRow(lines[0])
  const rows = lines.slice(2).map(parseRow).filter((row) => row.length > 0)

  if (headers.length === 0) {
    return null
  }

  return { headers, rows }
}

function SqlBlock({ title, sql }: { title: string; sql: string }) {
  return (
    <div className="console-panel-muted p-4">
      <div className="console-kicker">{title}</div>
      <pre className="mt-3 overflow-x-auto rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-4 text-xs leading-6 text-[var(--text-primary)]">
        <code>{sql || '-- 暂无 SQL'}</code>
      </pre>
    </div>
  )
}

function SectionMarkdown({
  title,
  markdown,
  appearance,
}: {
  title: string
  markdown: string
  appearance: 'light' | 'dark'
}) {
  return (
    <div className="console-panel-muted p-4">
      <div className="console-kicker">{title}</div>
      <div className={`mt-3 prose prose-sm max-w-none ${appearance === 'dark' ? 'prose-invert' : ''}`}>
        <ReactMarkdown>{markdown || '- 暂无内容'}</ReactMarkdown>
      </div>
    </div>
  )
}

function FieldSummaryTable({ markdown }: { markdown: string }) {
  const table = parseMarkdownTable(markdown)

  if (!table) {
    return (
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown>{markdown || '- 暂无字段摘要'}</ReactMarkdown>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)]">
      <table className="min-w-full text-left text-xs">
        <thead>
          <tr className="border-b border-[color:var(--border-soft)] text-[var(--text-secondary)]">
            {table.headers.map((header) => (
              <th key={header} className="px-3 py-2 font-semibold">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, rowIndex) => (
            <tr key={`${row.join('|')}-${rowIndex}`} className="border-b border-[color:var(--border-soft)] last:border-b-0">
              {table.headers.map((_, cellIndex) => (
                <td key={`${rowIndex}-${cellIndex}`} className="px-3 py-2 text-[var(--text-primary)]">
                  {row[cellIndex] || '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function TestDataPreparationResult({
  payload,
  appearance,
}: {
  payload: TestDataPack
  appearance: 'light' | 'dark'
}) {
  return (
    <div className="space-y-5">
      <section className="console-panel-muted p-5">
        <div className="console-kicker">识别摘要</div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {payload.metrics.map((metric) => (
            <div
              key={`${metric.label}:${metric.value}`}
              className="rounded-2xl border border-[color:var(--border-soft)] bg-[var(--surface-panel)] p-4"
            >
              <div className="text-[11px] uppercase tracking-[1.5px] text-[var(--text-muted)]">{metric.label}</div>
              <div className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{metric.value}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <SectionMarkdown title="表清单" markdown={payload.tableListMarkdown} appearance={appearance} />
          <SectionMarkdown title="场景清单" markdown={payload.scenarioListMarkdown} appearance={appearance} />
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="console-kicker">按表 SQL</div>
            <div className="mt-1 text-sm text-[var(--text-secondary)]">每张表固定展示字段摘要，以及查询、插入、更新、删除模板。</div>
          </div>
          <div className="console-chip">{payload.tables.length} 张表</div>
        </div>

        {payload.tables.length === 0 ? (
          <div className="console-panel-muted p-5 text-sm text-[var(--text-secondary)]">当前没有可展示的按表 SQL。</div>
        ) : (
          payload.tables.map((table) => (
            <article key={table.title} className="console-panel overflow-hidden">
              <div className="border-b px-5 py-4" style={{ borderColor: 'var(--border-soft)' }}>
                <div className="console-kicker">数据表</div>
                <h3 className="mt-1 text-base font-semibold text-[var(--text-primary)]">{table.title}</h3>
              </div>
              <div className="grid gap-4 p-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="console-panel-muted p-4">
                  <div className="console-kicker">字段摘要</div>
                  <div className="mt-3">
                    <FieldSummaryTable markdown={table.fieldSummaryMarkdown} />
                  </div>
                </div>
                <div className="space-y-4">
                  <SqlBlock title="SELECT" sql={table.selectSql} />
                  <SqlBlock title="INSERT" sql={table.insertSql} />
                  <SqlBlock title="UPDATE" sql={table.updateSql} />
                  <SqlBlock title="DELETE" sql={table.deleteSql} />
                </div>
              </div>
            </article>
          ))
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="console-kicker">按场景 SQL</div>
            <div className="mt-1 text-sm text-[var(--text-secondary)]">按测试动作组织查询、插入、更新、删除 SQL，便于直接复制使用。</div>
          </div>
          <div className="console-chip">{payload.scenarios.length} 个场景</div>
        </div>

        {payload.scenarios.length === 0 ? (
          <div className="console-panel-muted p-5 text-sm text-[var(--text-secondary)]">当前没有可展示的按场景 SQL。</div>
        ) : (
          payload.scenarios.map((scenario) => (
            <article key={scenario.title} className="console-panel overflow-hidden">
              <div className="border-b px-5 py-4" style={{ borderColor: 'var(--border-soft)' }}>
                <div className="console-kicker">业务场景</div>
                <h3 className="mt-1 text-base font-semibold text-[var(--text-primary)]">{scenario.title}</h3>
              </div>
              <div className="grid gap-4 p-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                <SectionMarkdown title="依赖表" markdown={scenario.dependencyMarkdown} appearance={appearance} />
                <div className="space-y-4">
                  <SqlBlock title="SELECT" sql={scenario.selectSql} />
                  <SqlBlock title="INSERT" sql={scenario.insertSql} />
                  <SqlBlock title="UPDATE" sql={scenario.updateSql} />
                  <SqlBlock title="DELETE" sql={scenario.deleteSql} />
                </div>
              </div>
            </article>
          ))
        )}
      </section>

      <section className="console-panel-muted p-5">
        <div className="console-kicker">识别告警</div>
        <div className={`mt-3 prose prose-sm max-w-none ${appearance === 'dark' ? 'prose-invert' : ''}`}>
          <ReactMarkdown>{payload.warningsMarkdown || '- 未发现明显告警。'}</ReactMarkdown>
        </div>
      </section>
    </div>
  )
}

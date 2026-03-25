import type {
  ApiTestPack,
  FlowchartPack,
  RequirementAnalysisPack,
  TestCaseReviewPayload,
  TestDataMetric,
  TestDataPack,
} from './contracts'

function parseJsonPayload<T>(value: string): T | null {
  try {
    const parsed = JSON.parse(value) as T
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function parseRequirementAnalysisPayload(value: string): RequirementAnalysisPack | null {
  const payload = parseJsonPayload<RequirementAnalysisPack>(value)
  if (!payload || !Array.isArray(payload.items)) {
    return null
  }
  return payload
}

export function parseTestCaseReviewPayload(value: string): TestCaseReviewPayload | null {
  const payload = parseJsonPayload<TestCaseReviewPayload>(value)
  if (
    !payload ||
    !Array.isArray(payload.findings) ||
    !Array.isArray(payload.reviewed_cases) ||
    !payload.revised_suite ||
    !Array.isArray(payload.revised_suite.items)
  ) {
    return null
  }
  return payload
}

export function parseApiTestPayload(value: string): ApiTestPack | null {
  const payload = parseJsonPayload<ApiTestPack>(value)
  if (!payload || !payload.spec || !Array.isArray(payload.cases) || !Array.isArray(payload.scenes)) {
    return null
  }
  return payload
}

export function parseFlowchartPayload(value: string): FlowchartPack | null {
  const payload = parseJsonPayload<FlowchartPack>(value)
  if (payload && Array.isArray(payload.items)) {
    return {
      ...payload,
      items: payload.items.map((item) => ({
        ...item,
        mermaid: extractFlowchartCode(item?.mermaid),
      })),
    }
  }
  return parseFlowchartMarkdown(value)
}

function extractJsonLikeStringField(text: string, fieldNames: string[]): string {
  for (const fieldName of fieldNames) {
    const keyPattern = new RegExp(`"${fieldName}"\\s*:\\s*"`, 'i')
    const keyMatch = keyPattern.exec(text)
    if (!keyMatch) {
      continue
    }

    const start = keyMatch.index + keyMatch[0].length
    const nextFieldPattern = /",\s*(?:\r?\n\s*)?"[^"\n]+"\s*:/g
    nextFieldPattern.lastIndex = start
    const nextFieldMatch = nextFieldPattern.exec(text)
    if (nextFieldMatch) {
      return decodeJsonLikeString(text.slice(start, nextFieldMatch.index))
    }

    const closingPattern = /"\s*[\]}]/g
    closingPattern.lastIndex = start
    const closingMatch = closingPattern.exec(text)
    if (closingMatch) {
      return decodeJsonLikeString(text.slice(start, closingMatch.index))
    }

    return decodeJsonLikeString(text.slice(start))
  }

  return ''
}

function decodeJsonLikeString(value: string): string {
  return value
    .replace(/\\r/g, '\r')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\')
}

function extractFlowchartCode(value: unknown): string {
  if (Array.isArray(value)) {
    for (const item of value) {
      const code = extractFlowchartCode(item)
      if (code) {
        return code
      }
    }
    return ''
  }

  if (value && typeof value === 'object') {
    const candidate = value as Record<string, unknown>
    return extractFlowchartCode(candidate.mermaid ?? candidate.code ?? candidate.diagram ?? '')
  }

  const text = String(value ?? '').trim()
  if (!text) {
    return ''
  }

  const codeBlockMatch = text.match(/```(?:mermaid)?\s*([\s\S]*?)```/i)
  if (codeBlockMatch?.[1]) {
    return extractFlowchartCode(codeBlockMatch[1])
  }

  if (text.startsWith('{') || text.startsWith('[')) {
    try {
      return extractFlowchartCode(JSON.parse(text))
    } catch {
      const extractedField = extractJsonLikeStringField(text, ['mermaid', 'code', 'diagram'])
      if (extractedField) {
        return normalizeFlowchartText(extractedField)
      }
    }
  }

  return normalizeFlowchartText(text)
}

function normalizeFlowchartText(value: string): string {
  const normalized = value
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+%%.*$/, '').trimEnd())
    .filter((line, index) => line || index === 0)
    .join('\n')
    .trim()

  const repaired = repairMermaidStructure(normalized)

  return /^(flowchart|graph)\s+(TD|TB|BT|RL|LR)\b/i.test(repaired) ? repaired : ''
}

function repairMermaidStructure(value: string): string {
  if (!value) {
    return ''
  }

  const repairedLines = value.split('\n').map(repairMermaidLine)
  const subgraphCount = repairedLines.filter((line) => line.trim().startsWith('subgraph ')).length
  const endCount = repairedLines.filter((line) => line.trim() === 'end').length

  if (endCount < subgraphCount) {
    repairedLines.push(...Array.from({ length: subgraphCount - endCount }, () => 'end'))
  }

  return repairedLines.join('\n').trim()
}

function repairMermaidLine(value: string): string {
  const replacements: Array<[RegExp, string]> = [
    [/\["([^"\n]*)"\)/g, '["$1"]'],
    [/\["([^"\n]*)"\}/g, '["$1"]'],
    [/\("([^"\n]*)"\]/g, '("$1")'],
    [/\("([^"\n]*)"\}/g, '("$1")'],
    [/\{"([^"\n]*)"\]/g, '{"$1"}'],
    [/\{"([^"\n]*)"\)/g, '{"$1"}'],
    [/\[(?:\\\/|\/)"([^"\n]*)"(?:\\\/|\/)\]/g, '["$1"]'],
    [/\{(?:\\\/|\/)"([^"\n]*)"(?:\\\/|\/)\}/g, '["$1"]'],
  ]

  const repaired = replacements.reduce((current, [pattern, replacement]) => current.replace(pattern, replacement), value)

  return repaired.replace(
    /^(\s*subgraph\s+[^\s\[]+)\[([^\]\n"]*\([^)\n"]*\)[^\]\n"]*)\](\s*)$/g,
    '$1["$2"]$3'
  )
}

function parseFlowchartMarkdown(value: string): FlowchartPack | null {
  const markdown = String(value ?? '').trim()
  if (!markdown.includes('## ') || !markdown.includes('```')) {
    return null
  }

  type ParsedFlowchartItem = FlowchartPack['items'][number]
  const items = splitByHeading(markdown, '## ')
    .map<ParsedFlowchartItem | null>((block) => {
      const warnings = extractFlowchartWarnings(block.content)
      const summary = stripFlowchartSectionArtifacts(block.content)
      const mermaid = extractFlowchartCode(block.content)
      if (!summary && !mermaid && warnings.length === 0) {
        return null
      }
      return {
        module: block.title,
        title: block.title,
        summary,
        mermaid,
        warnings,
      }
    })
    .filter((item): item is ParsedFlowchartItem => item !== null)

  if (items.length === 0) {
    return null
  }

  const summary = extractFlowchartHistorySummary(markdown) || `已完成 ${items.length} 个模块的业务流程提取。`
  return {
    items,
    summary,
    markdown: markdown.endsWith('\n') ? markdown : `${markdown}\n`,
  }
}

function extractFlowchartHistorySummary(markdown: string): string {
  const leadIn = markdown.split(/^##\s+/m)[0] || ''
  return leadIn
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith('>'))
    .map((line) => line.replace(/^>\s?/, '').trim())
    .join(' ')
    .trim()
}

function extractFlowchartWarnings(content: string): string[] {
  const match = content.match(/###\s+风险提示\s*([\s\S]*)$/m)
  if (!match?.[1]) {
    return []
  }

  return match[1]
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2).trim())
    .filter(Boolean)
}

function stripFlowchartSectionArtifacts(content: string): string {
  return content
    .replace(/```(?:mermaid)?[\s\S]*?```/gi, '')
    .replace(/###\s+风险提示[\s\S]*$/m, '')
    .trim()
}

type HeadingBlock = {
  title: string
  content: string
}

function splitByHeading(value: string, headingPrefix: '# ' | '## ' | '### '): HeadingBlock[] {
  const lines = value.replace(/\r\n/g, '\n').split('\n')
  const blocks: HeadingBlock[] = []
  let currentTitle: string | null = null
  let currentLines: string[] = []

  for (const line of lines) {
    if (line.startsWith(headingPrefix)) {
      if (currentTitle !== null) {
        blocks.push({
          title: currentTitle,
          content: currentLines.join('\n').trim(),
        })
      }
      currentTitle = line.slice(headingPrefix.length).trim()
      currentLines = []
      continue
    }

    if (currentTitle !== null) {
      currentLines.push(line)
    }
  }

  if (currentTitle !== null) {
    blocks.push({
      title: currentTitle,
      content: currentLines.join('\n').trim(),
    })
  }

  return blocks
}

function extractCodeBlock(value: string): string {
  const sqlMatch = value.match(/```sql\s*([\s\S]*?)```/i)
  if (sqlMatch?.[1]) {
    return sqlMatch[1].trim()
  }

  const genericMatch = value.match(/```\s*([\s\S]*?)```/)
  if (genericMatch?.[1]) {
    return genericMatch[1].trim()
  }

  return value.trim()
}

function buildMetrics(summaryMarkdown: string): TestDataMetric[] {
  return summaryMarkdown
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.startsWith('- '))
    .map((line) => line.slice(2))
    .map((line) => {
      const [label, ...rest] = line.split('：')
      return {
        label: (label || '').trim(),
        value: rest.join('：').trim(),
      }
    })
    .filter((item) => item.label && item.value)
}

function extractSectionLeadIn(sectionContent: string, subsectionPrefix: '## ' | '### '): string {
  const lines = sectionContent.replace(/\r\n/g, '\n').split('\n')
  const leadIn: string[] = []

  for (const line of lines) {
    if (line.startsWith(subsectionPrefix)) {
      break
    }
    leadIn.push(line)
  }

  return leadIn.join('\n').trim()
}

type TestDataJsonColumn = {
  name?: string
  sql_type?: string
  type?: string
  description?: string
  primary_key?: boolean
  required?: boolean
}

type TestDataJsonTable = {
  name?: string
  display_name?: string
  description?: string
  columns?: TestDataJsonColumn[]
  select_sql?: string
  insert_sql?: string
  update_sql?: string
  delete_sql?: string
}

type TestDataJsonScenario = {
  name?: string
  tables?: string[]
  select_sql?: string
  insert_sql?: string
  update_sql?: string
  delete_sql?: string
}

type TestDataJsonPayload = {
  document_name?: string
  summary?: string
  markdown?: string
  sql_file_content?: string
  tables?: TestDataJsonTable[]
  scenarios?: TestDataJsonScenario[]
  warnings?: string[]
}

function escapeMarkdownCell(value: string): string {
  return value.replace(/\|/g, '\\|')
}

function buildFieldSummaryMarkdown(columns: TestDataJsonColumn[] | undefined): string {
  const rows = [
    '| 字段 | 类型 | 主键 | 必填 | 说明 |',
    '| --- | --- | --- | --- | --- |',
  ]

  if (!Array.isArray(columns) || columns.length === 0) {
    rows.push('| - | - | - | - | 未识别到字段 |')
    return rows.join('\n')
  }

  for (const column of columns) {
    rows.push(
      `| ${column.name || '-'} | ${column.sql_type || column.type || 'UNKNOWN'} | ${column.primary_key ? '是' : '否'} | ${column.required ? '是' : '否'} | ${escapeMarkdownCell(column.description || '-')} |`
    )
  }

  return rows.join('\n')
}

function buildSummaryMarkdownFromPayload(payload: TestDataJsonPayload): string {
  const lines: string[] = []
  if (payload.document_name) {
    lines.push(`- 文档名称：${payload.document_name}`)
  }
  if (payload.summary) {
    lines.push(`- 处理摘要：${payload.summary}`)
  }
  lines.push(`- 识别表数量：${Array.isArray(payload.tables) ? payload.tables.length : 0}`)
  lines.push(`- 生成场景数量：${Array.isArray(payload.scenarios) ? payload.scenarios.length : 0}`)
  return lines.join('\n')
}

function buildTableListMarkdown(tables: TestDataJsonTable[] | undefined): string {
  if (!Array.isArray(tables) || tables.length === 0) {
    return '- 未识别到可生成 SQL 的表结构。'
  }

  return tables
    .map((table) => `- \`${table.name || 'unknown_table'}\`：${Array.isArray(table.columns) ? table.columns.length : 0} 个字段`)
    .join('\n')
}

function buildScenarioListMarkdown(scenarios: TestDataJsonScenario[] | undefined): string {
  if (!Array.isArray(scenarios) || scenarios.length === 0) {
    return '- 未生成可用的场景 SQL。'
  }

  return scenarios
    .map((scenario) => `- ${scenario.name || '未命名场景'}：${Array.isArray(scenario.tables) && scenario.tables.length > 0 ? scenario.tables.join(', ') : '未关联表'}`)
    .join('\n')
}

function buildDependencyMarkdown(tables: string[] | undefined): string {
  if (!Array.isArray(tables) || tables.length === 0) {
    return '- 未识别到依赖表'
  }

  return tables.map((table) => `- \`${table}\``).join('\n')
}

function buildWarningsMarkdown(warnings: string[] | undefined): string {
  if (!Array.isArray(warnings) || warnings.length === 0) {
    return '- 未发现明显告警。'
  }

  return warnings.map((warning) => `- ${warning}`).join('\n')
}

function parseTestDataJsonPayload(payload: TestDataJsonPayload): TestDataPack {
  const summaryMarkdown = buildSummaryMarkdownFromPayload(payload)
  const tables = Array.isArray(payload.tables) ? payload.tables : []
  const scenarios = Array.isArray(payload.scenarios) ? payload.scenarios : []

  return {
    documentName: payload.document_name,
    summaryMarkdown,
    metrics: buildMetrics(summaryMarkdown),
    tableListMarkdown: buildTableListMarkdown(tables),
    scenarioListMarkdown: buildScenarioListMarkdown(scenarios),
    tables: tables.map((table) => ({
      title: `${table.display_name || table.description || table.name || 'unknown_table'} (\`${table.name || 'unknown_table'}\`)`,
      fieldSummaryMarkdown: buildFieldSummaryMarkdown(table.columns),
      selectSql: table.select_sql || '',
      insertSql: table.insert_sql || '',
      updateSql: table.update_sql || '',
      deleteSql: table.delete_sql || '',
    })),
    scenarios: scenarios.map((scenario) => ({
      title: scenario.name || '未命名场景',
      dependencyMarkdown: buildDependencyMarkdown(scenario.tables),
      selectSql: scenario.select_sql || '',
      insertSql: scenario.insert_sql || '',
      updateSql: scenario.update_sql || '',
      deleteSql: scenario.delete_sql || '',
    })),
    warningsMarkdown: buildWarningsMarkdown(payload.warnings),
    markdown: payload.markdown || '',
    sqlFileContent: payload.sql_file_content || '',
  }
}

function parseTestDataMarkdown(markdown: string): TestDataPack | null {
  const topLevelSections = splitByHeading(markdown, '# ')
  if (topLevelSections.length === 0) {
    return null
  }

  const summarySection = topLevelSections.find((section) => section.title === '识别摘要')
  const tableSection = topLevelSections.find((section) => section.title === '按表 SQL')
  const scenarioSection = topLevelSections.find((section) => section.title === '按场景 SQL')
  const warningSection = topLevelSections.find((section) => section.title === '识别告警')

  if (!summarySection || !tableSection || !scenarioSection || !warningSection) {
    return null
  }

  const summarySubsections = splitByHeading(summarySection.content, '## ')
  const tableListMarkdown = summarySubsections.find((section) => section.title === '表清单')?.content || ''
  const scenarioListMarkdown = summarySubsections.find((section) => section.title === '场景清单')?.content || ''
  const summaryLeadIn = extractSectionLeadIn(summarySection.content, '## ')

  const tables = splitByHeading(tableSection.content, '## ').map((section) => {
    const subsections = splitByHeading(section.content, '### ')
    return {
      title: section.title,
      fieldSummaryMarkdown: subsections.find((item) => item.title === '字段摘要')?.content || '',
      selectSql: extractCodeBlock(subsections.find((item) => item.title === 'SELECT')?.content || ''),
      insertSql: extractCodeBlock(subsections.find((item) => item.title === 'INSERT')?.content || ''),
      updateSql: extractCodeBlock(subsections.find((item) => item.title === 'UPDATE')?.content || ''),
      deleteSql: extractCodeBlock(subsections.find((item) => item.title === 'DELETE')?.content || ''),
    }
  })

  const scenarios = splitByHeading(scenarioSection.content, '## ').map((section) => {
    const subsections = splitByHeading(section.content, '### ')
    return {
      title: section.title,
      dependencyMarkdown: subsections.find((item) => item.title === '依赖表')?.content || '',
      selectSql: extractCodeBlock(subsections.find((item) => item.title === 'SELECT')?.content || ''),
      insertSql: extractCodeBlock(subsections.find((item) => item.title === 'INSERT')?.content || ''),
      updateSql: extractCodeBlock(subsections.find((item) => item.title === 'UPDATE')?.content || ''),
      deleteSql: extractCodeBlock(subsections.find((item) => item.title === 'DELETE')?.content || ''),
    }
  })

  return {
    documentName: buildMetrics(summaryLeadIn).find((item) => item.label === '文档名称')?.value,
    summaryMarkdown: summaryLeadIn,
    metrics: buildMetrics(summaryLeadIn),
    tableListMarkdown,
    scenarioListMarkdown,
    tables,
    scenarios,
    warningsMarkdown: warningSection.content,
    markdown,
    sqlFileContent: '',
  }
}

export function parseTestDataPayload(value: string): TestDataPack | null {
  const payload = parseJsonPayload<TestDataJsonPayload>(value)

  if (
    payload &&
    (
      Array.isArray(payload.tables)
      || Array.isArray(payload.scenarios)
      || Array.isArray(payload.warnings)
      || typeof payload.sql_file_content === 'string'
      || typeof payload.document_name === 'string'
      || typeof payload.summary === 'string'
    )
  ) {
    return parseTestDataJsonPayload(payload)
  }

  if (payload?.markdown) {
    return parseTestDataMarkdown(payload.markdown)
  }

  return parseTestDataMarkdown(value)
}

/**
 * 解析 Markdown 表格为 JSON 对象数组 (增强容错版)
 */
export type MarkdownTableRow = Record<string, string>

export function parseMarkdownTable(markdown: string): MarkdownTableRow[] {
  if (!markdown || !markdown.includes('|')) return []

  const lines = markdown.trim().split('\n').map(l => l.trim())
  
  // 找到第一个包含 | 的行作为潜在表头
  const firstTableIndex = lines.findIndex(l => l.includes('|'))
  if (firstTableIndex === -1) return []

  // 提取表头
  const headers = lines[firstTableIndex]
    .split('|')
    .map(h => h.trim())
    .filter(h => h !== '')

  if (headers.length === 0) return []

  // 跳过表头和分割线行 (---)
  const dataLines = lines.slice(firstTableIndex + 2)

  return dataLines
    .filter(line => line.includes('|'))
    .map(line => {
      // 容错：如果行首没 |, 自动补
      let processedLine = line.startsWith('|') ? line : `|${line}`
      // 容错：如果行尾没 |, 自动补
      if (!processedLine.endsWith('|')) processedLine += '|'

      const values = processedLine
        .split('|')
        .map(v => v.trim())
        .filter((_, i, arr) => i > 0 && i < arr.length - 1) // 移除行首尾的空值

      const obj: MarkdownTableRow = {}
      headers.forEach((header, i) => {
        // 如果列数不匹配，用空字符串填充
        obj[header] = (values[i] !== undefined) ? values[i] : ''
      })
      
      // 增加原始行备份，用于白屏还原
      obj._raw = line
      return obj
    })
}

/**
 * 提取所有 Markdown 表格内容
 */
export function extractMarkdownTables(text: string): string[] {
  const tableRegex = /\|(.+)\|\n\|([\s\-|:]+)\|\n((\|(.+)\|\n?)+)/g
  const matches = text.match(tableRegex)
  return matches || []
}

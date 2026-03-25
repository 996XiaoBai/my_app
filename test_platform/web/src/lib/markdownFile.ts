export function downloadBlobFile(blob: Blob, filename: string): void {
  if (!blob || blob.size === 0) {
    return
  }

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function downloadTextFile(content: string, filename: string, mimeType: string): void {
  if (!content) {
    return
  }

  downloadBlobFile(new Blob([content], { type: mimeType }), filename)
}

export function downloadMarkdownFile(content: string, filename: string): void {
  const resolvedFilename = filename.endsWith('.md') ? filename : `${filename}.md`
  downloadTextFile(content, resolvedFilename, 'text/markdown;charset=utf-8')
}

export function downloadSqlFile(content: string, filename: string): void {
  const resolvedFilename = filename.endsWith('.sql') ? filename : `${filename}.sql`
  downloadTextFile(content, resolvedFilename, 'application/sql;charset=utf-8')
}

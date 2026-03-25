import type { ReviewFinding, ReviewRunPayload } from './contracts'

const FINDINGS_JSON_BLOCK = /<findings_json>[\s\S]*?<\/findings_json>/gi

export type ReviewFindingDetail = {
  key: 'source_quote' | 'suggestion'
  label: string
  content: string
}

export function sanitizeReviewReportContent(content: string): string {
  return content.replace(FINDINGS_JSON_BLOCK, '').trim()
}

export function buildReviewMarkdown(payload: ReviewRunPayload | null): string {
  if (!payload) {
    return ''
  }

  if (payload.markdown) {
    return payload.markdown
  }

  const sections: string[] = ['# 智能需求评审报告', '']

  Object.values(payload.reports || {}).forEach((report) => {
    const content = sanitizeReviewReportContent(report.content || '')
    if (!content) {
      return
    }
    sections.push(`## ${report.label || '评审报告'}`, '', content, '')
  })

  if (payload.findings?.length) {
    sections.push('## 风险看板', '')
    payload.findings.forEach((finding, index) => {
      sections.push(`${index + 1}. [${finding.risk_level}] ${finding.category}：${finding.description}`)
      if (finding.source_quote?.trim()) {
        sections.push(`   - 原文：${finding.source_quote.trim()}`)
      }
      if (finding.suggestion?.trim()) {
        sections.push(`   - 建议：${finding.suggestion.trim()}`)
      }
      sections.push('')
    })
  }

  return sections.join('\n').trim()
}

export function buildReviewFindingDetails(finding: ReviewFinding): ReviewFindingDetail[] {
  const details: ReviewFindingDetail[] = []

  if (finding.source_quote?.trim()) {
    details.push({
      key: 'source_quote',
      label: '原文引用',
      content: finding.source_quote.trim(),
    })
  }

  if (finding.suggestion?.trim()) {
    details.push({
      key: 'suggestion',
      label: '评审建议',
      content: finding.suggestion.trim(),
    })
  }

  return details
}

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildReviewFindingDetails, buildReviewMarkdown } from './reviewResult.ts'

test('buildReviewMarkdown uses stable risk formatting and includes source quote before suggestion', () => {
  const markdown = buildReviewMarkdown({
    reports: {
      test: {
        label: '测试视角',
        content: '## 灵魂追问\n\n- 请确认登录失败提示。\n',
      },
    },
    findings: [
      {
        risk_level: 'H',
        category: '逻辑缺陷',
        description: '失败重试口径缺失',
        source_quote: '需求中仅描述“失败后可重试”，未说明次数和提示。',
        suggestion: '补充失败重试次数、提示文案与锁定条件。',
      },
    ],
  })

  assert.match(markdown, /1\. \[H\] 逻辑缺陷：失败重试口径缺失/)
  assert.match(markdown, /- 原文：需求中仅描述“失败后可重试”，未说明次数和提示。/)
  assert.match(markdown, /- 建议：补充失败重试次数、提示文案与锁定条件。/)
  assert.equal(markdown.includes('[H][逻辑缺陷]'), false)
})

test('buildReviewFindingDetails keeps source quote and suggestion in a unified order', () => {
  const details = buildReviewFindingDetails({
    risk_level: 'M',
    category: '易用性建议',
    description: '登录失败引导不足',
    source_quote: '需求仅写“失败后提示错误”。',
    suggestion: '补充找回密码与联系客服入口。',
  })

  assert.deepEqual(details, [
    { key: 'source_quote', label: '原文引用', content: '需求仅写“失败后提示错误”。' },
    { key: 'suggestion', label: '评审建议', content: '补充找回密码与联系客服入口。' },
  ])
})

test('buildReviewFindingDetails omits empty source quote to stay compatible with old payloads', () => {
  const details = buildReviewFindingDetails({
    risk_level: 'L',
    category: '逻辑缺陷',
    description: '兼容旧数据',
    suggestion: '保持旧数据可显示。',
  })

  assert.deepEqual(details, [
    { key: 'suggestion', label: '评审建议', content: '保持旧数据可显示。' },
  ])
})

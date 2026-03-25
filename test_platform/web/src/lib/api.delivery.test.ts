import test from 'node:test'
import assert from 'node:assert/strict'

import { apiClient, extractFilenameFromContentDisposition } from './api.ts'

test('extractFilenameFromContentDisposition decodes utf-8 filename* value', () => {
  const filename = extractFilenameFromContentDisposition(
    'attachment; filename="test-cases.xlsx"; filename*=UTF-8\'\'%E7%99%BB%E5%BD%95%E6%A8%A1%E5%9D%97_%E6%B5%8B%E8%AF%95%E7%94%A8%E4%BE%8B.xlsx',
    'fallback.xlsx'
  )

  assert.equal(filename, '登录模块_测试用例.xlsx')
})

test('getTapdStory requests encoded story input and returns parsed payload', async () => {
  const originalFetch = globalThis.fetch
  let requestedUrl = ''

  globalThis.fetch = (async (input: string | URL | Request) => {
    requestedUrl = String(input)
    return new Response(
      JSON.stringify({
        success: true,
        story_id: '1120340332001008677',
        content: '【需求标题】登录优化',
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    )
  }) as typeof fetch

  try {
    const payload = await apiClient.getTapdStory('https://www.tapd.cn/20340332/stories/view/1120340332001008677')

    assert.match(requestedUrl, /\/api\/tapd\/story\?input=/)
    assert.match(requestedUrl, /stories%2Fview%2F1120340332001008677/)
    assert.equal(payload.story_id, '1120340332001008677')
    assert.match(payload.content, /登录优化/)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('exportTestCases posts json payload and returns decoded filename', async () => {
  const originalFetch = globalThis.fetch
  let requestInit: RequestInit | undefined

  globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
    requestInit = init
    return new Response('excel-binary', {
      status: 200,
      headers: {
        'Content-Disposition': 'attachment; filename="test-cases.xlsx"; filename*=UTF-8\'\'%E7%99%BB%E5%BD%95%E6%A8%A1%E5%9D%97_%E6%B5%8B%E8%AF%95%E7%94%A8%E4%BE%8B.xlsx',
      },
    })
  }) as typeof fetch

  try {
    const exported = await apiClient.exportTestCases(
      '{"items":[],"summary":"done"}',
      'excel',
      '登录模块'
    )

    assert.equal(requestInit?.method, 'POST')
    assert.deepEqual(requestInit?.headers, { 'Content-Type': 'application/json' })
    assert.deepEqual(JSON.parse(String(requestInit?.body)), {
      format: 'excel',
      result: '{"items":[],"summary":"done"}',
      filename: '登录模块',
    })
    assert.equal(exported.filename, '登录模块_测试用例.xlsx')
    assert.equal(await exported.blob.text(), 'excel-binary')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('exportTestCases 在无法读取下载头时回退到请求文件名', async () => {
  const originalFetch = globalThis.fetch

  globalThis.fetch = (async () => {
    return new Response('xmind-binary', {
      status: 200,
    })
  }) as typeof fetch

  try {
    const exported = await apiClient.exportTestCases(
      '{"items":[],"summary":"done"}',
      'xmind',
      '登录需求说明_v2.docx'
    )

    assert.equal(exported.filename, '登录需求说明_v2_测试用例.xmind')
    assert.equal(await exported.blob.text(), 'xmind-binary')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('downloadHistoryReportArtifact returns blob and decoded filename', async () => {
  const originalFetch = globalThis.fetch
  let requestedUrl = ''

  globalThis.fetch = (async (input: string | URL | Request) => {
    requestedUrl = String(input)
    return new Response('allure-zip-binary', {
      status: 200,
      headers: {
        'Content-Disposition': 'attachment; filename="allure-results.zip"; filename*=UTF-8\'\'%E9%BB%98%E8%AE%A4%E6%A8%A1%E5%9D%97_allure-results.zip',
      },
    })
  }) as typeof fetch

  try {
    const artifact = await apiClient.downloadHistoryReportArtifact('report-001', 'allure_archive', 'fallback.zip')

    assert.match(requestedUrl, /\/api\/history\/reports\/report-001\/artifacts\/allure_archive$/)
    assert.equal(artifact.filename, '默认模块_allure-results.zip')
    assert.equal(await artifact.blob.text(), 'allure-zip-binary')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('downloadHistoryReportArtifact keeps backend detail when artifact is missing', async () => {
  const originalFetch = globalThis.fetch

  globalThis.fetch = (async () => {
    return new Response(JSON.stringify({ detail: '历史产物不存在' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  try {
    await assert.rejects(
      () => apiClient.downloadHistoryReportArtifact('report-001', 'allure_archive'),
      /历史产物不存在/
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('runSkillStream retries without context when backend context is missing', async () => {
  const originalFetch = globalThis.fetch
  const requests: FormData[] = []

  globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
    requests.push(init?.body as FormData)

    if (requests.length === 1) {
      return new Response(JSON.stringify({ detail: 'Error: context not found' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(JSON.stringify({
          type: 'result',
          success: true,
          result: 'retry-success',
          context_id: 'ctx-new',
        }) + '\n'))
        controller.close()
      },
    })

    return new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  try {
    const payload = await apiClient.runSkillStream(
      'test_case',
      '登录流程',
      [],
      undefined,
      undefined,
      undefined,
      undefined,
      'ctx-old'
    )

    assert.equal(requests.length, 2)
    assert.equal(requests[0].get('context_id'), 'ctx-old')
    assert.equal(requests[1].get('context_id'), null)
    assert.equal(payload.success, true)
    assert.equal(payload.result, 'retry-success')
    assert.equal(payload.context_id, 'ctx-new')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('runSkillStream retries when stream event reports context missing', async () => {
  const originalFetch = globalThis.fetch
  const requests: FormData[] = []

  globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
    requests.push(init?.body as FormData)

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        if (requests.length === 1) {
          controller.enqueue(encoder.encode(JSON.stringify({
            type: 'error',
            message: 'Error: context not found',
          }) + '\n'))
        } else {
          controller.enqueue(encoder.encode(JSON.stringify({
            type: 'result',
            success: true,
            result: 'stream-retry-success',
            context_id: 'ctx-fresh',
          }) + '\n'))
        }
        controller.close()
      },
    })

    return new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  try {
    const payload = await apiClient.runSkillStream(
      'test_case',
      '登录流程',
      [],
      undefined,
      undefined,
      undefined,
      undefined,
      'ctx-stale'
    )

    assert.equal(requests.length, 2)
    assert.equal(requests[0].get('context_id'), 'ctx-stale')
    assert.equal(requests[1].get('context_id'), null)
    assert.equal(payload.success, true)
    assert.equal(payload.result, 'stream-retry-success')
    assert.equal(payload.context_id, 'ctx-fresh')
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('runSkillStream maps test-case-review mode to test_case_review', async () => {
  const originalFetch = globalThis.fetch
  let requestBody: FormData | null = null

  globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
    requestBody = init?.body as FormData

    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(JSON.stringify({
          type: 'result',
          success: true,
          result: '{"summary":"ok","findings":[],"reviewed_cases":[],"revised_suite":{"items":[],"summary":"done"}}',
        }) + '\n'))
        controller.close()
      },
    })

    return new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch

  try {
    const payload = await apiClient.runSkillStream(
      'test-case-review',
      '登录需求',
    )

    assert.equal(requestBody?.get('mode'), 'test_case_review')
    assert.equal(payload.success, true)
  } finally {
    globalThis.fetch = originalFetch
  }
})

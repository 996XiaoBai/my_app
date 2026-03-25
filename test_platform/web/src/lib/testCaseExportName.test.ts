import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildMarkdownDownloadFilename,
  resolvePreferredDownloadBaseName,
  resolveTestCaseExportBaseName,
} from './testCaseExportName.ts'

test('resolveTestCaseExportBaseName 优先使用已持久化的下载基名', () => {
  const filename = resolveTestCaseExportBaseName({
    persistedBaseName: '登录需求文档',
    uploadedFilename: '购物车需求.docx',
    requirement: '这是新的文本需求',
  })

  assert.equal(filename, '登录需求文档')
})

test('resolveTestCaseExportBaseName 使用上传文件名并去掉扩展名', () => {
  const filename = resolveTestCaseExportBaseName({
    uploadedFilename: '需求评审.v2.docx',
  })

  assert.equal(filename, '需求评审.v2')
})

test('resolveTestCaseExportBaseName 在无文件时回退到需求首行', () => {
  const filename = resolveTestCaseExportBaseName({
    requirement: '用户登录后可提交订单\n第二行内容',
  })

  assert.equal(filename, '用户登录后可提交订单')
})

test('resolvePreferredDownloadBaseName 优先使用上传文件名主干', () => {
  const filename = resolvePreferredDownloadBaseName({
    uploadedFilename: '登录流程评审稿-v3.pdf',
    requirement: '这里是文本需求',
    fallbackName: '默认名称',
  })

  assert.equal(filename, '登录流程评审稿-v3')
})

test('buildMarkdownDownloadFilename 使用基名和模块后缀拼接', () => {
  const filename = buildMarkdownDownloadFilename('登录流程评审稿-v3', '需求评审报告')

  assert.equal(filename, '登录流程评审稿-v3_需求评审报告.md')
})

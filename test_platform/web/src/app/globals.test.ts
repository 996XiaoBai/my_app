import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('globals.css uses standard density as baseline and exposes comfortable compact overrides', async () => {
  const css = await readFile(new URL('./globals.css', import.meta.url), 'utf8')

  assert.match(css, /排版 Design Tokens \(Standard 模式 · 默认\)/)
  assert.match(css, /--space-row:\s*0\.5rem;/)
  assert.match(css, /--space-cell:\s*0\.625rem;/)
  assert.match(css, /--click-row:\s*2\.5rem;/)
  assert.match(css, /\[data-density="comfortable"\]\s*\{/)
  assert.match(css, /\[data-density="compact"\]\s*\{/)
})

test('globals.css keeps prose colors bound to theme variables in light mode', async () => {
  const css = await readFile(new URL('./globals.css', import.meta.url), 'utf8')

  assert.match(css, /\.prose\s*\{[\s\S]*color:\s*var\(--review-prose-body\);/)
  assert.match(css, /\.prose h2\s*\{[\s\S]*color:\s*var\(--review-prose-heading\)\s*!important;/)
  assert.match(css, /\.prose blockquote\s*\{[\s\S]*color:\s*var\(--review-prose-quote-text\)\s*!important;/)
})

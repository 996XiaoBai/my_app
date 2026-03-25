'use client'

import { useMemo } from 'react'

interface Props {
  code: string
  title?: string
}

function escapeForTemplate(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/`/g, '\\`')
    .replace(/\$\{/g, '\\${')
}

export default function MermaidDiagram({ code, title }: Props) {
  const srcDoc = useMemo(() => {
    const escapedCode = escapeForTemplate(code)
    const safeTitle = escapeForTemplate(title || '业务流程图')
    return `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
      body { margin: 0; padding: 12px; background: #0b0d10; color: #f2f2f2; font-family: sans-serif; }
      #root { border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; background: rgba(255,255,255,0.02); padding: 12px; }
      h1 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #c9d1d9; }
      #graph { display: flex; justify-content: center; }
      svg { max-width: 100%; height: auto; background: white; border-radius: 12px; }
      .error { display: grid; gap: 8px; color: #fed7aa; white-space: normal; font-size: 12px; line-height: 1.6; padding: 20px; border: 1px solid rgba(251,146,60,0.28); border-radius: 12px; background: rgba(120,53,15,0.28); }
      .error strong { color: #fdba74; font-size: 13px; }
      .error code { color: #fde68a; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    </style>
  </head>
  <body>
    <div id="root">
      <h1>${safeTitle}</h1>
      <div id="graph">正在渲染流程图...</div>
    </div>
    <script>
      const code = \`${escapedCode}\`;
      mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
      });
      mermaid.render('mermaid-graph', code)
        .then(({ svg }) => {
          document.getElementById('graph').innerHTML = svg;
        })
        .catch(() => {
          document.getElementById('graph').innerHTML =
            '<div class="error"><strong>结果暂不可读</strong><div>请看 <code>Markdown</code> 原文。</div></div>';
        });
    </script>
  </body>
</html>`
  }, [code, title])

  return (
    <iframe
      title={title || '业务流程图'}
      srcDoc={srcDoc}
      className="w-full min-h-[420px] rounded-2xl border border-white/[0.06] bg-black/20"
    />
  )
}

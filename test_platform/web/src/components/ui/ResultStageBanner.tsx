'use client'

type ResultStageTone = 'success' | 'warning' | 'neutral'

interface Props {
  title: string
  meta?: string
  tone?: ResultStageTone
}

const TONE_CLASSNAME: Record<ResultStageTone, string> = {
  success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
  warning: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
  neutral: 'border-[color:var(--border-soft)] bg-[var(--surface-panel-muted)] text-[var(--text-secondary)]',
}

export default function ResultStageBanner({ title, meta, tone = 'success' }: Props) {
  return (
    <div className={`mb-5 flex items-center gap-2 rounded-xl border px-4 py-2.5 ${TONE_CLASSNAME[tone]}`}>
      <span className="text-sm">●</span>
      <span className="text-sm font-medium">{title}</span>
      {meta ? <span className="ml-auto text-[11px] opacity-80">{meta}</span> : null}
    </div>
  )
}

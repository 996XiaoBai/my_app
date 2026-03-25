export type GenericModuleTab = 'result' | 'log' | 'history'

export function getGenericModuleHistoryTypes(id: string): string[] {
  return [id]
}

export function buildGenericModuleMarkdownFilename(label: string): string {
  return label.endsWith('.md') ? label : `${label}.md`
}

const DEFAULT_API_BASE = 'http://localhost:8000'

export const API_BASE = (process.env.NEXT_PUBLIC_QA_API_BASE || DEFAULT_API_BASE).replace(/\/$/, '')

export function buildApiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE}${normalizedPath}`
}

export function isContextNotFoundDetail(detail?: string): boolean {
  if (!detail) {
    return false
  }

  return /context not found/i.test(detail) || /上下文.*不存在/.test(detail)
}

export function formatApiHttpError(status: number, detail?: string): string {
  if (status === 404) {
    if (detail && detail !== 'Not Found') {
      return detail
    }
    return '后端接口不存在：当前前端连接的不是最新版测试平台后端。请确认 8000 端口运行的是最新 `test_platform/api_server.py`，或检查 `NEXT_PUBLIC_QA_API_BASE` 配置。'
  }

  if (isContextNotFoundDetail(detail)) {
    return '当前任务上下文已失效（通常是后端重启后内存上下文被清理）。系统将自动回退为无上下文执行，请重试本次操作。'
  }

  if (detail && detail !== 'Not Found') {
    return detail
  }

  return '接口请求失败，请检查后端服务状态。'
}

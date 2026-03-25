import type { DashboardStats, HistoryReportDetail, HistoryReportSummary } from './contracts'
import { API_BASE, buildApiUrl, formatApiHttpError, isContextNotFoundDetail } from './apiConfig.ts'
import { notifyHistoryRefresh } from './historyRefresh.ts'
import { buildInlineErrorCopy } from './workbenchPresentation.ts'

/**
 * QA Workbench API Client
 * 封装与 Python FastAPI 后端的交互
 */

const MODE_ALIASES: Record<string, string> = {
  'req-analysis': 'req_analysis',
  'test-point': 'test_point',
  'test-case-review': 'test_case_review',
  impact: 'impact_analysis',
  'test-plan': 'test_plan',
  'test-data': 'test_data',
  'log-diagnosis': 'log_diagnosis',
  'api-test': 'api_test_gen',
  'perf-test': 'api_perf_test_gen',
  'ui-auto': 'auto_script_gen',
  'weekly-report': 'weekly_report',
}

function resolveMode(mode: string): string {
  return MODE_ALIASES[mode] || mode
}

export interface RunResult {
  success: boolean;
  result: string;
  error?: string;
  insight?: string;
  context_id?: string;
  cache_hit?: boolean;
  meta?: Record<string, unknown>;
}

export interface TapdStoryResult {
  success: boolean
  story_id: string
  content: string
}

export type TestCaseExportFormat = 'excel' | 'xmind'

export interface TestCaseExportResult {
  blob: Blob
  filename: string
}

export interface RunProgressEvent {
  type: 'progress';
  stage: string;
  message: string;
  sequence: number;
}

export interface RunErrorEvent {
  type: 'error';
  message: string;
}

export interface RunResultEvent extends RunResult {
  type: 'result';
}

export type RunStreamEvent = RunProgressEvent | RunErrorEvent | RunResultEvent;

export function extractFilenameFromContentDisposition(
  contentDisposition: string | null,
  fallbackFilename: string
): string {
  if (!contentDisposition) {
    return fallbackFilename
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }

  const plainMatch = contentDisposition.match(/filename="([^"]+)"/i)
  if (plainMatch?.[1]) {
    return plainMatch[1]
  }

  return fallbackFilename
}

function buildStructuredExportFallbackFilename(
  filename: string,
  extension: '.xlsx' | '.xmind'
): string {
  const trimmed = String(filename || '').trim()
  const basename = trimmed.split(/[\\/]/).pop() || ''
  const withoutExtension = basename.replace(/\.[^.]+$/, '').trim()
  const resolvedBaseName = withoutExtension || basename || '测试用例'
  return `${resolvedBaseName}_测试用例${extension}`
}

export const apiClient = {
  /**
   * 健康检查
   */
  async health(): Promise<boolean> {
    try {
      const res = await fetch(buildApiUrl('/health'));
      const data = await res.json();
      return data.status === 'ok';
    } catch {
      return false;
    }
  },

  /**
   * 获取仪表盘大盘统计数据
   */
  async getDashboardStats(): Promise<DashboardStats> {
    try {
      const res = await fetch(buildApiUrl('/api/dashboard/stats'));
      if (!res.ok) throw new Error('API Request Failed');
      return await res.json();
    } catch (e) {
      console.error(e);
      return { metrics: [], recent_activities: [] };
    }
  },

  async getHistoryReports(types?: string[], limit: number = 20): Promise<HistoryReportSummary[]> {
    const searchParams = new URLSearchParams()
    searchParams.set('limit', String(limit))
    if (types && types.length > 0) {
      searchParams.set('types', types.map((type) => resolveMode(type)).join(','))
    }

    const response = await fetch(`${buildApiUrl('/api/history/reports')}?${searchParams.toString()}`)
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(formatApiHttpError(response.status, error.detail))
    }

    const payload = await response.json()
    return payload.items || []
  },

  async getHistoryReport(reportId: string): Promise<HistoryReportDetail> {
    const response = await fetch(buildApiUrl(`/api/history/reports/${reportId}`))
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(formatApiHttpError(response.status, error.detail))
    }
    return response.json()
  },

  async downloadHistoryReportArtifact(
    reportId: string,
    artifactKey: string,
    fallbackFilename?: string
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(buildApiUrl(`/api/history/reports/${reportId}/artifacts/${artifactKey}`))
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(formatApiHttpError(response.status, error.detail))
    }

    return {
      blob: await response.blob(),
      filename: extractFilenameFromContentDisposition(
        response.headers.get('content-disposition'),
        fallbackFilename || `${artifactKey}.bin`
      ),
    }
  },

  async getTapdStory(input: string): Promise<TapdStoryResult> {
    const searchParams = new URLSearchParams()
    searchParams.set('input', input)

    const response = await fetch(`${buildApiUrl('/api/tapd/story')}?${searchParams.toString()}`)
    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(formatApiHttpError(response.status, error.detail))
    }

    return response.json()
  },

  async exportTestCases(
    result: string,
    format: TestCaseExportFormat,
    filename: string = '测试用例'
  ): Promise<TestCaseExportResult> {
    const response = await fetch(buildApiUrl('/api/test-cases/export'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        format,
        result,
        filename,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(formatApiHttpError(response.status, error.detail))
    }

    const extension = format === 'excel' ? '.xlsx' : '.xmind'
    return {
      blob: await response.blob(),
      filename: extractFilenameFromContentDisposition(
        response.headers.get('content-disposition'),
        buildStructuredExportFallbackFilename(filename, extension)
      ),
    }
  },

  /**
   * 执行技能模式
   */
  async runSkill(
    mode: string,
    requirement: string,
    files?: File[],
    params?: Record<string, unknown>,
    roles?: string[],
    extraPrompt?: string,
    historicalFindings?: string,
    contextId?: string
  ): Promise<RunResult> {
    const formData = new FormData();
    formData.append('mode', resolveMode(mode));
    formData.append('requirement', requirement);
    if (params) {
      formData.append('params', JSON.stringify(params));
    }
    if (roles) {
      formData.append('roles', JSON.stringify(roles));
    }
    if (extraPrompt) {
      formData.append('extra_prompt', extraPrompt);
    }
    if (historicalFindings) {
      formData.append('historical_findings', historicalFindings);
    }
    if (contextId) {
      formData.append('context_id', contextId);
    }
    if (files) {
      files.forEach((file) => {
        formData.append('files', file);
      });
    }

    let response: Response
    try {
      response = await fetch(buildApiUrl('/run'), {
        method: 'POST',
        body: formData,
      })
    } catch {
      throw new Error(`后端服务不可达：请确认 ${API_BASE} 已启动且可访问。`)
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      const detail = typeof error?.detail === 'string' ? error.detail : undefined
      if (contextId && isContextNotFoundDetail(detail)) {
        // 上下文已失效时自动降级重试，避免后端重启后前端任务链被卡死。
        return apiClient.runSkill(mode, requirement, files, params, roles, extraPrompt, historicalFindings)
      }
      throw new Error(formatApiHttpError(response.status, detail))
    }

    const payload = await response.json();
    if (payload?.success) {
      notifyHistoryRefresh()
    }
    return payload;
  },

  async runSkillStream(
    mode: string,
    requirement: string,
    files?: File[],
    params?: Record<string, unknown>,
    roles?: string[],
    extraPrompt?: string,
    historicalFindings?: string,
    contextId?: string,
    onEvent?: (event: RunStreamEvent) => void
  ): Promise<RunResult> {
    const formData = new FormData();
    formData.append('mode', resolveMode(mode));
    formData.append('requirement', requirement);
    if (params) {
      formData.append('params', JSON.stringify(params));
    }
    if (roles) {
      formData.append('roles', JSON.stringify(roles));
    }
    if (extraPrompt) {
      formData.append('extra_prompt', extraPrompt);
    }
    if (historicalFindings) {
      formData.append('historical_findings', historicalFindings);
    }
    if (contextId) {
      formData.append('context_id', contextId);
    }
    if (files) {
      files.forEach((file) => {
        formData.append('files', file);
      });
    }

    let response: Response
    try {
      response = await fetch(buildApiUrl('/run/stream'), {
        method: 'POST',
        body: formData,
      })
    } catch {
      throw new Error(`后端服务不可达：请确认 ${API_BASE} 已启动且可访问。`)
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      const detail = typeof error?.detail === 'string' ? error.detail : undefined
      if (contextId && isContextNotFoundDetail(detail)) {
        // 上下文已失效时自动降级重试，避免后端重启后前端任务链被卡死。
        return apiClient.runSkillStream(mode, requirement, files, params, roles, extraPrompt, historicalFindings, undefined, onEvent)
      }
      throw new Error(formatApiHttpError(response.status, detail))
    }

    if (!response.body) {
      throw new Error('Streaming response is not available');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResult: RunResult | null = null;

    const processLine = (line: string) => {
      const trimmed = line.trim();
      if (!trimmed) {
        return;
      }
      const event = JSON.parse(trimmed) as RunStreamEvent;
      onEvent?.(event);
      if (event.type === 'error') {
        throw new Error(event.message || buildInlineErrorCopy('process'));
      }
      if (event.type === 'result') {
        finalResult = {
          success: event.success,
          result: event.result,
          insight: event.insight,
          context_id: event.context_id,
          cache_hit: event.cache_hit,
          meta: event.meta,
        };
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          processLine(line);
        }

        if (done) {
          break;
        }
      }

      if (buffer.trim()) {
        processLine(buffer);
      }
    } catch (streamError: unknown) {
      const message = streamError instanceof Error ? streamError.message : ''
      if (contextId && isContextNotFoundDetail(message)) {
        // 后端可能在流式事件阶段返回 context not found，需要同样降级重试。
        return apiClient.runSkillStream(mode, requirement, files, params, roles, extraPrompt, historicalFindings, undefined, onEvent)
      }
      throw streamError
    }

    const resolvedResult = finalResult as RunResult | null
    if (!resolvedResult) {
      throw new Error('流式执行结束，但未收到最终结果');
    }

    if (resolvedResult.success) {
      notifyHistoryRefresh()
    }

    return resolvedResult;
  },

  /**
   * 智能推荐专家
   */
  async recommendExperts(requirement: string, files?: File[]): Promise<{ success: boolean; recommended: string[] }> {
    const formData = new FormData();
    formData.append('requirement', requirement);
    if (files) {
      files.forEach((file) => formData.append('files', file));
    }

    const response = await fetch(buildApiUrl('/recommend-experts'), {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      return { success: false, recommended: ['product', 'test'] };
    }

    return response.json();
  },
};

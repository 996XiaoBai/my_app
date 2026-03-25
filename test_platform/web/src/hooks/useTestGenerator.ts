'use client'

import { useState } from 'react'
import { useAppStore } from '@/stores/useAppStore'
import { apiClient, RunStreamEvent } from '@/lib/api'
import { ReviewFinding } from '@/lib/contracts'
import { buildInlineErrorCopy } from '@/lib/workbenchPresentation'

/**
 * 测试用例生成领域的 Coordinator Hook
 * 隔离 UI 与复杂的 AI 业务编排逻辑
 */
export function useTestGenerator() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const { 
    setInsightSteps, 
    updateInsightStep, 
    openInsight, 
    setActiveFocusArea,
    activeEnvironment,
    globalVariables,
    setHighRiskMode,
    reviewFindings,
    requirementContextId,
    setRequirementContextId
  } = useAppStore()

  const generate = async (
    requirement: string,
    files: File[],
    options?: { strategy?: string, level?: string, useRiskLinks?: boolean },
    onEvent?: (event: RunStreamEvent) => void
  ) => {
    if (!requirement && files.length === 0 && !requirementContextId) {
      const message = '请提供需求内容、上传文档，或复用最近一次评审上下文'
      setError(message)
      return { success: false, error: message }
    }

    setLoading(true)
    setError(null)

    // 2. 准备执行上下文参数
    const executionParams = {
      environment: activeEnvironment,
      variables: globalVariables,
      timestamp: new Date().toISOString(),
      strategy: options?.strategy || 'happy',
      level: options?.level || 'system',
      useRiskLinks: options?.useRiskLinks ?? true
    }

    try {
      const steps = [
        { label: '解析需求内容与附件', status: 'loading' as const },
        { label: 'AI 模型语义建模 (Dify)', status: 'waiting' as const },
        { label: '提取功能点与测试边界', status: 'waiting' as const },
        { label: '生成结构化测试用例', status: 'waiting' as const },
      ]
      setInsightSteps(steps)

      // 组装历史评审发现 (仅在开启关联时)
      const historicalFindings = (options?.useRiskLinks !== false && reviewFindings && reviewFindings.length > 0)
        ? reviewFindings.map((f: ReviewFinding) => `- [${f.risk_level || 'M'}][${f.category || '逻辑'}] ${f.description}: ${f.suggestion}`).join('\n')
        : undefined

      const res = await apiClient.runSkillStream(
        'test_case',
        requirement,
        files,
        executionParams,
        ['Senior QA Expert', 'Business Analyst', 'Security Specialist'],
        options?.strategy || 'happy',
        historicalFindings,
        requirementContextId || undefined,
        (event) => {
          onEvent?.(event)
          if (event.type !== 'progress') {
            return
          }
          if (event.stage === 'context') {
            updateInsightStep(0, 'done')
            updateInsightStep(1, 'loading')
          } else if (event.stage === 'matching') {
            updateInsightStep(1, 'done')
            updateInsightStep(2, 'loading')
          } else if (event.stage === 'generating') {
            updateInsightStep(2, 'done')
            updateInsightStep(3, 'loading')
          } else if (event.stage === 'evaluating') {
            updateInsightStep(3, 'done')
          }
        }
      )
      
      if (res.success) {
        updateInsightStep(1, 'done')
        updateInsightStep(2, 'done')
        updateInsightStep(3, 'done')

        if (res.context_id) {
          setRequirementContextId(res.context_id)
        }
        setActiveFocusArea('MAIN')
        
        // 动态风险评审建议 (AI Insight)
        if (res.insight) {
          // 根据敏感词触发高风险流光
          if (res.insight.includes('资金') || res.insight.includes('资损') || res.insight.includes('安全') || res.insight.includes('高危')) {
            setHighRiskMode(true)
            openInsight(res.insight, 'risk')
          } else {
            setHighRiskMode(false)
            openInsight(res.insight, 'info')
          }
        }
        return {
          success: true,
          result: res.result,
        }
      } else {
        const message = buildInlineErrorCopy('generate')
        setError(message)
        updateInsightStep(1, 'error')
        return { success: false, error: message }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : buildInlineErrorCopy('generate')
      setError(msg)
      openInsight(`系统异常: ${msg}`, 'risk')
      return { success: false, error: msg }
    } finally {
      setLoading(false)
    }
  }

  return {
    generate,
    loading,
    error,
    setError
  }
}

import { StateCreator } from 'zustand'

export interface ProjectSlice {
  currentProject: string
  currentVersion: string
  activeEnvironment: 'dev' | 'test' | 'staging' | 'prod'
  globalVariables: Record<string, string>
  pipelineStatus: {
    running: number
    success: number
    fail: number
  }
  setEnvironment: (env: 'dev' | 'test' | 'staging' | 'prod') => void
  setGlobalVariable: (key: string, value: string) => void
}

export const createProjectSlice: StateCreator<ProjectSlice> = (set) => ({
  currentProject: '测试平台',
  currentVersion: 'web-beta',
  activeEnvironment: 'test',
  globalVariables: {
    'BASE_URL': 'http://localhost:3000',
    'TIMEOUT': '30000',
  },
  pipelineStatus: {
    running: 0,
    success: 0,
    fail: 0,
  },
  setEnvironment: (env) => set({ activeEnvironment: env }),
  setGlobalVariable: (key, value) => set((s) => ({
    globalVariables: { ...s.globalVariables, [key]: value }
  })),
})

'use client'

import React, { useState, useEffect } from 'react'
import { ShieldAlert, CheckCircle2, Loader2, X, Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CheckItem {
  id: string
  label: string
  status: 'waiting' | 'loading' | 'success' | 'warning' | 'error'
  detail?: string
}

const INITIAL_ITEMS: CheckItem[] = [
  { id: 'db', label: 'Database Sandbox Snapshot', status: 'waiting' },
  { id: 'config', label: 'Nacos Configuration Sync', status: 'waiting' },
  { id: 'runner', label: 'Remote Runner Image (v3.2.1)', status: 'waiting' }
]

function buildInitialItems(): CheckItem[] {
  return INITIAL_ITEMS.map((item) => ({ ...item }))
}

export default function GuardrailModal({ 
  isOpen, 
  onClose, 
  onConfirm 
}: { 
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
}) {
  const [items, setItems] = useState<CheckItem[]>(() => buildInitialItems())

  const handleClose = () => {
    setItems(buildInitialItems())
    onClose()
  }

  useEffect(() => {
    if (!isOpen) {
      return
    }

    // 模拟自动化预检
    const startPreflight = async () => {
      const update = (id: string, partial: Partial<CheckItem>) => {
        setItems(prev => prev.map(item => item.id === id ? { ...item, ...partial } : item))
      }

      update('db', { status: 'loading' })
      await new Promise(r => setTimeout(r, 800))
      update('db', { status: 'success', detail: 'Snapshot: staging_v3_copy' })

      update('config', { status: 'loading' })
      await new Promise(r => setTimeout(r, 600))
      update('config', { status: 'success', detail: 'Version: master_env_20240314' })

      update('runner', { status: 'loading' })
      await new Promise(r => setTimeout(r, 1200))
      update('runner', { status: 'success', detail: 'Image: registry.infra/qa-runner:stable' })
    }

    void startPreflight()
  }, [isOpen])

  if (!isOpen) return null

  const allSuccess = items.every(i => i.status === 'success')

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={handleClose} />
      
      <div className="relative w-full max-w-md bg-[#14151A] border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-scale-in">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-amber-500" />
            <h3 className="text-sm font-bold text-[#F2F2F2] uppercase tracking-wider font-mono">Environment Pre-flight Check</h3>
          </div>
          <button onClick={handleClose} className="text-[#8B949E] hover:text-[#F2F2F2]">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <p className="text-[#8B949E] leading-relaxed" style={{ fontSize: 'var(--font-xs)' }}>
            检测到当前执行影响面涉及核心财务组件。请确认测试环境数据已锁定，且配置下发版本与 Git 分支匹配。
          </p>

          <div className="space-y-3">
            {items.map((item) => (
              <div key={item.id} className="p-3 bg-white/[0.02] border border-white/5 rounded-lg flex items-center justify-between transition-all">
                <div className="flex items-center gap-3">
                  {item.status === 'loading' && <Loader2 className="w-4 h-4 text-[#8B5CF6] animate-spin" />}
                  {item.status === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-500" />}
                  {item.status === 'waiting' && <Terminal className="w-4 h-4 text-[#8B949E]/40" />}
                  <div className="flex flex-col">
                    <span className="font-medium text-[#F2F2F2]" style={{ fontSize: 'var(--font-xs)' }}>{item.label}</span>
                    {item.detail && <span className="text-[#8B949E] font-mono" style={{ fontSize: 'var(--font-xs)' }}>{item.detail}</span>}
                  </div>
                </div>
                {item.status === 'success' && <span className="font-bold text-emerald-500 tracking-tighter uppercase" style={{ fontSize: 'var(--font-xs)' }}>Matched</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-white/[0.01] border-t border-white/5 flex gap-3">
          <button 
            onClick={handleClose}
            className="flex-1 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-[#8B949E] transition-all"
            style={{ fontSize: 'var(--font-xs)' }}
          >
            Cancel Run
          </button>
          <button 
            onClick={onConfirm}
            disabled={!allSuccess}
            className={cn(
              "flex-1 py-2 rounded-lg font-bold transition-all flex items-center justify-center gap-2",
              allSuccess 
                ? "bg-[#8B5CF6] text-white shadow-[0_4px_12px_rgba(139,92,246,0.3)]" 
                : "bg-white/5 text-[#8B949E] cursor-not-allowed"
            )}
          >
            {allSuccess ? 'Confirm & Execute' : 'Running Checks...'}
          </button>
        </div>
      </div>
    </div>
  )
}

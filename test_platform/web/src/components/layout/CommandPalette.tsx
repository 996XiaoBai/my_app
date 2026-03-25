'use client'

import { useState, useEffect, useRef } from 'react'
import { useHotkeys } from 'react-hotkeys-hook'
import { useAppStore, NAV_GROUPS, NavItem } from '@/stores/useAppStore'

/**
 * Command Palette (⌘K 全局搜索)
 * 支持搜索最近任务与功能模块并快速导航
 */
export default function CommandPalette() {
  const {
    commandPaletteOpen,
    toggleCommandPalette,
    setActiveNav,
    taskSnapshots,
    loadTaskSnapshot,
  } = useAppStore()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const openPalette = () => {
    setQuery('')
    setSelectedIndex(0)
    toggleCommandPalette()
  }

  // 所有可搜索的导航项 (包含仪表盘)
  const allItems: NavItem[] = [
    { id: 'dashboard', label: '仪表盘', icon: '📊', href: '/' },
    ...NAV_GROUPS.flatMap((g) => g.items)
  ]

  const normalizedQuery = query.trim().toLowerCase()
  const filteredTasks = normalizedQuery
    ? taskSnapshots.filter(
        (snapshot) =>
          snapshot.title.toLowerCase().includes(normalizedQuery) ||
          snapshot.requirement.toLowerCase().includes(normalizedQuery)
      )
    : taskSnapshots.slice(0, 5)

  const filteredModules = normalizedQuery
    ? allItems.filter(
        (item) =>
          item.label.toLowerCase().includes(normalizedQuery) ||
          item.id.toLowerCase().includes(normalizedQuery)
      )
    : allItems

  const sections = [
    {
      title: '最近任务',
      items: filteredTasks.map((snapshot) => ({
        key: `task:${snapshot.id}`,
        icon: '🗂️',
        title: snapshot.title,
        subtitle: `${snapshot.currentStageLabel} · 风险 ${snapshot.riskCount}`,
        actionLabel: '恢复',
        onSelect: () => {
          loadTaskSnapshot(snapshot.id)
          setActiveNav(snapshot.primaryNavId)
          toggleCommandPalette()
        },
      })),
    },
    {
      title: '功能模块',
      items: filteredModules.map((item) => ({
        key: `module:${item.id}`,
        icon: item.icon,
        title: item.label,
        subtitle: item.id,
        actionLabel: '打开',
        onSelect: () => {
          setActiveNav(item.id)
          toggleCommandPalette()
        },
      })),
    },
  ].filter((section) => section.items.length > 0)

  const flattenedItems = sections.flatMap((section) => section.items)

  // ⌘K 快捷键绑定
  useHotkeys('mod+k', (e) => {
    e.preventDefault()
    if (commandPaletteOpen) {
      toggleCommandPalette()
      return
    }
    openPalette()
  }, { enableOnFormTags: true })

  // 打开时自动聚焦
  useEffect(() => {
    if (!commandPaletteOpen) {
      return
    }

    const timer = window.setTimeout(() => inputRef.current?.focus(), 50)
    return () => window.clearTimeout(timer)
  }, [commandPaletteOpen])

  // 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => Math.min(i + 1, flattenedItems.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && flattenedItems[selectedIndex]) {
      e.preventDefault()
      flattenedItems[selectedIndex].onSelect()
    } else if (e.key === 'Escape') {
      toggleCommandPalette()
    }
  }

  if (!commandPaletteOpen) return null

  return (
    <>
      {/* 遮罩 */}
      <div
        className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
        onClick={toggleCommandPalette}
      />

      {/* 面板 */}
      <div className="fixed inset-x-0 top-[20%] z-[61] mx-auto w-full max-w-lg">
        <div className="mx-4 overflow-hidden rounded-2xl border border-white/[0.1] bg-[#1A1B20] shadow-2xl shadow-black/40">
          {/* 搜索输入框 */}
          <div className="flex items-center gap-3 px-5 border-b border-white/[0.06]">
            <svg style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} className="text-[#8B949E] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setSelectedIndex(0)
              }}
              onKeyDown={handleKeyDown}
              placeholder="搜索任务、需求、功能模块..."
              aria-label="全局搜索功能"
              className="flex-1 py-4 bg-transparent text-[#F2F2F2] placeholder-[#8B949E]/60 outline-none"
              style={{ fontSize: 'var(--font-sm)' }}
            />
            <kbd className="font-mono text-[#8B949E] bg-white/[0.06] border border-white/[0.1] px-2 py-1 rounded" style={{ fontSize: 'var(--font-xs)' }}>
              ESC
            </kbd>
          </div>

          {/* 搜索结果 */}
          <div className="max-h-80 overflow-y-auto py-2 scrollbar-thin">
            {flattenedItems.length === 0 ? (
              <div className="px-5 py-8 text-center text-[#8B949E]" style={{ fontSize: 'var(--font-sm)' }}>
                未找到匹配的任务或功能模块
              </div>
            ) : (
              sections.map((section) => (
                <div key={section.title}>
                  <div className="px-5 py-2 text-[11px] font-semibold uppercase tracking-[1px] text-[#8B949E]">
                    {section.title}
                  </div>
                  {section.items.map((item) => {
                    const idx = flattenedItems.findIndex((entry) => entry.key === item.key)
                    return (
                      <button
                        key={item.key}
                        onClick={item.onSelect}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`w-full flex items-center gap-3 px-5 text-left transition-colors ${
                          idx === selectedIndex
                            ? 'bg-[#8B5CF6]/15 text-[#F2F2F2]'
                            : 'text-[#A1A1AA] hover:bg-white/[0.04]'
                        }`}
                        style={{ minHeight: 'var(--click-row)' }}
                      >
                        <span className="text-lg w-7 text-center">{item.icon}</span>
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-medium" style={{ fontSize: 'var(--font-sm)' }}>{item.title}</div>
                          <div className="truncate text-xs text-[#8B949E]">{item.subtitle}</div>
                        </div>
                        {idx === selectedIndex && (
                          <span className="ml-auto font-mono text-[#8B949E]" style={{ fontSize: 'var(--font-xs)' }}>
                            ↵ {item.actionLabel}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>
              ))
            )}
          </div>

          {/* 底部提示 */}
          <div className="px-5 py-2.5 border-t border-white/[0.06] flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-[#8B949E]" style={{ fontSize: 'var(--font-xs)' }}>
              <kbd className="font-mono bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 rounded">↑↓</kbd>
              导航
            </span>
            <span className="flex items-center gap-1.5 text-[#8B949E]" style={{ fontSize: 'var(--font-xs)' }}>
              <kbd className="font-mono bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 rounded">↵</kbd>
              打开
            </span>
            <span className="flex items-center gap-1.5 text-[#8B949E]" style={{ fontSize: 'var(--font-xs)' }}>
              <kbd className="font-mono bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 rounded">esc</kbd>
              关闭
            </span>
          </div>
        </div>
      </div>
    </>
  )
}

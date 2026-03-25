'use client'

import { useEffect } from 'react'
import { useAppStore } from '@/stores/useAppStore'

/**
 * 视口监听器
 * 自动检测 13 寸 MBP 等小屏幕分辨率 (通常逻辑宽度 < 1440px)
 */
export default function ViewportListener() {
  const setIsSmallScreen = useAppStore((s) => s.setIsSmallScreen)

  useEffect(() => {
    const handleResize = () => {
      // 1440px 是 MacBook Pro 13 的典型逻辑宽度
      const isSmall = window.innerWidth < 1440
      setIsSmallScreen(isSmall)
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [setIsSmallScreen])

  return null
}

'use client'

import { useEffect, useRef } from 'react'
import { useAppStore } from '@/stores/useAppStore'
import { isKnownNavId } from '@/config/navigation'

function readNavIdFromUrl(): string {
  const params = new URLSearchParams(window.location.search)
  const rawValue = params.get('module') || 'dashboard'
  return isKnownNavId(rawValue) ? rawValue : 'dashboard'
}

export default function NavigationStateSync() {
  const activeNavId = useAppStore((state) => state.activeNavId)
  const setActiveNav = useAppStore((state) => state.setActiveNav)
  const initializedRef = useRef(false)
  const lastNavRef = useRef<string>('dashboard')

  useEffect(() => {
    const currentNavId = useAppStore.getState().activeNavId
    const navIdFromUrl = readNavIdFromUrl()
    lastNavRef.current = navIdFromUrl

    if (navIdFromUrl !== currentNavId) {
      setActiveNav(navIdFromUrl)
    } else {
      initializedRef.current = true
    }

    const handlePopState = () => {
      const nextNavId = readNavIdFromUrl()
      lastNavRef.current = nextNavId
      setActiveNav(nextNavId)
    }

    window.addEventListener('popstate', handlePopState)

    return () => window.removeEventListener('popstate', handlePopState)
  }, [setActiveNav])

  useEffect(() => {
    if (!initializedRef.current) {
      if (activeNavId === lastNavRef.current) {
        initializedRef.current = true
      }
      return
    }

    if (activeNavId === lastNavRef.current) {
      return
    }

    const url = new URL(window.location.href)
    if (activeNavId === 'dashboard') {
      url.searchParams.delete('module')
    } else {
      url.searchParams.set('module', activeNavId)
    }

    const nextUrl = `${url.pathname}${url.search}${url.hash}`
    window.history.pushState({ module: activeNavId }, '', nextUrl)
    lastNavRef.current = activeNavId
  }, [activeNavId])

  return null
}

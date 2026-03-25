'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallbackTitle?: string
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 flex flex-col items-center justify-center border border-dashed border-red-500/30 bg-red-500/5 rounded-2xl min-h-[200px] text-center space-y-4">
          <AlertCircle className="w-10 h-10 text-red-500/50" />
          <div className="space-y-1">
            <h3 className="font-bold text-red-400" style={{ fontSize: 'var(--font-xs)' }}>{this.props.fallbackTitle || 'Runtime Integration Error'}</h3>
            <p className="text-red-400/60 font-mono" style={{ fontSize: 'var(--font-xs)' }}>
              {this.state.error?.message || 'Unexpected parsing failure in data module'}
            </p>
          </div>
          <button 
            onClick={() => this.setState({ hasError: false })}
            className="flex items-center gap-2 px-4 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg transition-all"
            style={{ fontSize: 'var(--font-xs)' }}
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Try Restore
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

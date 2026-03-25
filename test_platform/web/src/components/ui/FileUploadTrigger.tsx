'use client'

import { useId, type DragEventHandler, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface FileUploadTriggerProps {
  ariaLabel?: string
  accept?: string
  multiple?: boolean
  className?: string
  contentClassName?: string
  inputClassName?: string
  primaryText?: string
  secondaryText?: string
  children?: ReactNode
  onFilesChange: (files: File[]) => void
  onDragOver?: DragEventHandler<HTMLElement>
  onDragLeave?: DragEventHandler<HTMLElement>
  onDrop?: DragEventHandler<HTMLElement>
}

export default function FileUploadTrigger({
  ariaLabel = '上传文件',
  accept,
  multiple = true,
  className,
  contentClassName,
  inputClassName,
  primaryText = '',
  secondaryText = '选择',
  children,
  onFilesChange,
  onDragOver,
  onDragLeave,
  onDrop,
}: FileUploadTriggerProps) {
  const inputId = useId()

  return (
    <div
      className={cn('relative overflow-hidden text-sm', className)}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      <input
        id={inputId}
        aria-label={ariaLabel}
        type="file"
        multiple={multiple}
        accept={accept}
        className={cn('absolute inset-0 z-10 cursor-pointer opacity-0', inputClassName)}
        onClick={(event) => {
          event.currentTarget.value = ''
        }}
        onChange={(event) => {
          onFilesChange(Array.from(event.target.files || []))
        }}
      />
      <div
        className={cn(
          'pointer-events-none flex w-full items-center justify-between px-3 py-3',
          contentClassName
        )}
      >
        {children ?? (
          <>
            <span className="text-[var(--text-primary)]">{primaryText}</span>
            <span className="text-[11px] text-[var(--text-muted)]">{secondaryText}</span>
          </>
        )}
      </div>
    </div>
  )
}

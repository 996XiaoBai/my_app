import React, { useState, useEffect } from 'react'
import { useAppStore } from '@/stores/useAppStore'
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  getSortedRowModel,
  SortingState,
  VisibilityState,
} from '@tanstack/react-table'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronUp, Search, Download, Trash2, Send } from 'lucide-react'
import { ErrorBoundary } from './ErrorBoundary'

interface DataGridProps<TData> {
  data: TData[]
  columns: ColumnDef<TData>[]
  title?: string
  loading?: boolean
  onBulkSync?: (rows: TData[]) => void
  onBulkDelete?: (rows: TData[]) => void
}

export default function DataGrid<TData>({ 
  data, 
  columns, 
  title,
  loading,
  onBulkSync,
  onBulkDelete
}: DataGridProps<TData>) {
  const { activeFocusArea, setActiveFocusArea } = useAppStore()
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')
  const [rowSelection, setRowSelection] = useState({})
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({})
  
  // 13" MBP 极窄屏优化策略 (Column Priority)
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth
      const isMBP13 = width < 1200
      const isUltraNarrow = width < 900
      
      setColumnVisibility({
        '优先级': !isUltraNarrow,
        '模块': !isMBP13,
        '创建人': !isMBP13,
        '标签': !isUltraNarrow,
        '执行状态': true,
      })
    }
    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // TanStack Table 当前与 React Compiler 的 memo 语义不兼容，这里显式豁免该规则。
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter,
      rowSelection,
      columnVisibility,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: setRowSelection,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableRowSelection: true,
  })

  // [Phase 5] 0 延迟焦点恢复逻辑
  const focusedRowId = useAppStore(s => s.focusedRowId)
  React.useLayoutEffect(() => {
    if (focusedRowId && activeFocusArea === 'MAIN') {
      const el = document.getElementById(`row-${focusedRowId}`)
      if (el) {
        el.scrollIntoView({ behavior: 'auto', block: 'nearest' })
      }
    }
  }, [focusedRowId, activeFocusArea])

  const selectedRows = table.getSelectedRowModel().rows
  const hasBulkActions = Boolean(onBulkSync || onBulkDelete)

  return (
    <div 
      onClick={() => setActiveFocusArea('MAIN')}
      className={cn(
        "flex flex-col h-full rounded-xl overflow-hidden transition-all duration-500 shadow-2xl",
        activeFocusArea === 'MAIN' ? "ring-2 ring-[#8B5CF6]/30 border-[#8B5CF6]/20" : "opacity-75 saturate-[0.6] scale-[0.99]"
      )}
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: activeFocusArea === 'MAIN' ? '1px solid rgba(139, 92, 246, 0.2)' : '1px solid var(--border-soft)',
        boxShadow: 'var(--shadow-elevated)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 backdrop-blur-md"
        style={{
          minHeight: 'var(--click-row)',
          borderBottom: '1px solid var(--border-soft)',
          backgroundColor: 'var(--bg-soft)',
        }}
      >
        <div className="flex items-center gap-3">
          {title && <h2 className="font-semibold text-[var(--text-primary)]" style={{ fontSize: 'var(--font-sm)' }}>{title}</h2>}
          <div className="relative group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)] transition-colors group-focus-within:text-[#8B5CF6]" style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
            <input 
              value={globalFilter ?? ''}
              onChange={e => setGlobalFilter(e.target.value)}
              placeholder="快速过滤..."
              className="pl-9 pr-3 rounded-lg outline-none focus:border-[#8B5CF6]/50 transition-all w-64 focus:w-80"
              style={{ border: '1px solid var(--border)', fontSize: 'var(--font-xs)', height: 'var(--click-min)' }}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
           <button
             type="button"
             disabled
             className="flex items-center justify-center rounded-lg text-[var(--text-secondary)] opacity-40 transition-all"
             title="导出能力待接通"
             style={{ width: 'var(--click-min)', height: 'var(--click-min)' }}
           >
             <Download style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
           </button>
        </div>
      </div>

      {/* Table Container */}
      <div className="flex-1 overflow-auto custom-scrollbar">
        <table className="w-full text-left border-collapse table-fixed">
          <thead className="sticky top-0 z-10">
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id} className="backdrop-blur-sm shadow-sm" style={{ backgroundColor: 'color-mix(in srgb, var(--bg-elevated) 95%, transparent)' }}>
                {headerGroup.headers.map(header => (
                  <th 
                    key={header.id}
                    className="px-4 font-semibold text-[var(--text-secondary)] cursor-pointer hover:bg-[var(--bg-soft)] transition-colors group"
                    style={{ borderBottom: '1px solid var(--border-soft)', width: header.getSize(), fontSize: 'var(--font-xs)', height: 'var(--click-row)', lineHeight: 'var(--lh-tight)' }}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                        {{
                          asc: <ChevronUp style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} className="text-[#8B5CF6]" />,
                          desc: <ChevronDown style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} className="text-[#8B5CF6]" />,
                        }[header.column.getIsSorted() as string] ?? (
                          <ChevronDown
                            style={{
                              width: 'var(--icon-sm)',
                              height: 'var(--icon-sm)',
                              color: 'var(--text-muted)',
                            }}
                          />
                        )}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="py-20 text-center text-[var(--text-secondary)] font-mono animate-pulse" style={{ fontSize: 'var(--font-xs)' }}>
                  正在加载高性能 DataGrid 引擎...
                </td>
              </tr>
            ) : table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-20 text-center text-[var(--text-secondary)] font-mono" style={{ fontSize: 'var(--font-xs)' }}>
                  没有匹配的数据
                </td>
              </tr>
            ) : (
              <ErrorBoundary fallbackTitle="DataGrid 行渲染异常">
                {table.getRowModel().rows.map(row => (
                  <tr 
                    key={row.id} 
                    id={`row-${row.id}`}
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest('button')) return
                      row.toggleSelected(true)
                      useAppStore.getState().setFocusedRowId(row.id)
                    }}
                    className={cn(
                      "group hover:bg-[#8B5CF6]/5 transition-colors cursor-pointer",
                      row.getIsSelected() || useAppStore.getState().focusedRowId === row.id ? "bg-[#8B5CF6]/10" : ""
                    )}
                    style={{ borderBottom: '1px solid var(--border-soft)' }}
                  >
                    {row.getVisibleCells().map(cell => (
                      <td 
                        key={cell.id} 
                        className="px-4 text-[var(--text-strong)] font-mono truncate transition-all group-hover:text-[var(--text-primary)]"
                        style={{ fontSize: 'var(--font-xs)', padding: `var(--space-cell) 1rem`, lineHeight: 'var(--lh-normal)' }}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </ErrorBoundary>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer / Info */}
      <div
        className="px-5 flex items-center justify-between font-mono text-[var(--text-secondary)]"
        style={{
          fontSize: 'var(--font-xs)',
          minHeight: 'var(--click-min)',
          borderTop: '1px solid var(--border-soft)',
          backgroundColor: 'var(--bg-soft)',
        }}
      >
        <div>
          共 {table.getFilteredRowModel().rows.length} 条记录
          {selectedRows.length > 0 && (
            <span className="ml-3 text-[#8B5CF6] font-bold">
              已选择 {selectedRows.length} 条
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>{sorting.length > 0 ? '已排序' : '按默认顺序'}</span>
          <div className="w-1 h-1 rounded-full bg-[#8B5CF6]/40" />
          <span>高密度视图</span>
        </div>
      </div>

      {/* Floating Bulk Bar */}
      {selectedRows.length > 0 && hasBulkActions && (
        <div
          className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-4 px-6 py-3 border border-[#8B5CF6]/50 rounded-full shadow-[0_0_30px_rgba(139,92,246,0.3)] backdrop-blur-xl animate-scale-in z-50"
          style={{ backgroundColor: 'color-mix(in srgb, var(--bg-elevated) 94%, transparent)' }}
        >
          <div className="flex items-center gap-2 pr-4" style={{ borderRight: '1px solid var(--border)' }}>
            <div className="w-2 h-2 rounded-full bg-[#8B5CF6] animate-pulse" />
            <span className="font-bold text-[var(--text-primary)]" style={{ fontSize: 'var(--font-xs)' }}>已选中 {selectedRows.length} 项</span>
          </div>
          
          <div className="flex items-center gap-4">
            {onBulkSync && (
              <button 
                onClick={() => onBulkSync(selectedRows.map(r => r.original))}
                className="flex items-center gap-2 font-semibold text-[var(--text-primary)] hover:text-[#8B5CF6] transition-colors"
                style={{ fontSize: 'var(--font-xs)' }}
              >
                <Send style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
                批量同步
              </button>
            )}
            <button 
              onClick={() => onBulkDelete?.(selectedRows.map(r => r.original))}
              className="flex items-center gap-2 font-semibold text-red-400 hover:text-red-300 transition-colors"
              style={{ fontSize: 'var(--font-xs)' }}
            >
              <Trash2 style={{ width: 'var(--icon-sm)', height: 'var(--icon-sm)' }} />
              删除
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

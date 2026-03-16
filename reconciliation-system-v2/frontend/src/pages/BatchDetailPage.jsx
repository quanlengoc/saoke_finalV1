import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { reconciliationApi, reconciliationApiV2, reportsApi, approvalsApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'

const statusColors = {
  'UPLOADING': 'bg-gray-100 text-gray-800',
  'PROCESSING': 'bg-yellow-100 text-yellow-800',
  'COMPLETED': 'bg-green-100 text-green-800',
  'ERROR': 'bg-red-100 text-red-800',
  'CANCELLED': 'bg-orange-100 text-orange-800',
  'PENDING_APPROVAL': 'bg-purple-100 text-purple-800',
  'APPROVED': 'bg-blue-100 text-blue-800',
  // Legacy
  'REJECTED': 'bg-red-100 text-red-800',
  'FAILED': 'bg-red-100 text-red-800',
  'PENDING': 'bg-yellow-100 text-yellow-800',
}

const statusLabels = {
  'UPLOADING': 'Khởi tạo',
  'PROCESSING': 'Đang xử lý',
  'COMPLETED': 'Hoàn tất',
  'ERROR': 'Lỗi',
  'CANCELLED': 'Tạm dừng',
  'PENDING_APPROVAL': 'Chờ phê duyệt',
  'APPROVED': 'Đã phê duyệt',
  // Legacy
  'REJECTED': 'Từ chối (cũ)',
  'FAILED': 'Thất bại (cũ)',
  'PENDING': 'Chờ xử lý (cũ)',
}

// Helper function to format timestamp dd-mm-yyyy hh24:mi:ss
const formatTimestamp = (isoString) => {
  if (!isoString) return ''
  try {
    const date = new Date(isoString)
    const day = String(date.getDate()).padStart(2, '0')
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const year = date.getFullYear()
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${day}-${month}-${year} ${hours}:${minutes}:${seconds}`
  } catch {
    return isoString
  }
}

/**
 * Dynamic output detail section component.
 * Handles its own state and query for any output type.
 * Supports optional filter columns (e.g., for A1 with status filters).
 */
function OutputDetailSection({ outputName, batchId, outputStats }) {
  const [page, setPage] = useState(0)
  // draftFilters = what user is currently typing (not yet applied)
  // appliedFilters = what's actually sent to the API (applied on button click)
  const [draftFilters, setDraftFilters] = useState({})
  const [appliedFilters, setAppliedFilters] = useState({})
  const [wrapText, setWrapText] = useState(false)
  const pageSize = 50

  // Filter columns come from outputStats.filter_columns
  const filterColumns = outputStats?.filter_columns || {}

  // Detect if filter_columns uses new format (object with type) or old format (array of values)
  const isNewFilterFormat = (colConfig) => {
    return colConfig && typeof colConfig === 'object' && !Array.isArray(colConfig) && colConfig.type
  }

  // Helper: extract active filters from a filter state object
  const extractActiveFilters = (filterState) => {
    return Object.entries(filterState)
      .filter(([, f]) => {
        if (typeof f === 'string') return !!f
        return f && (f.value || f.min != null || f.max != null)
      })
      .map(([col, f]) => {
        if (typeof f === 'string') return { col, op: 'eq', value: f }
        return { col, ...f }
      })
      .filter(f => f.value || f.min != null || f.max != null)
  }

  // Build query params using appliedFilters (not draft)
  const buildPreviewParams = () => {
    const params = { skip: page * pageSize, limit: pageSize }
    const activeFilters = extractActiveFilters(appliedFilters)
    if (activeFilters.length > 0) {
      params.filters = JSON.stringify(activeFilters)
    }
    return params
  }

  const { data: previewData } = useQuery({
    queryKey: ['preview', batchId, outputName.toLowerCase(), page, appliedFilters],
    queryFn: () => reportsApi.preview(batchId, outputName.toLowerCase(), buildPreviewParams()),
    enabled: !!batchId,
  })

  const preview = previewData?.data
  const total = outputStats?.total ?? preview?.total ?? 0

  // Collect all status breakdowns from outputStats (skip those with >20 values — too many for badges)
  const statusBreakdowns = outputStats
    ? Object.entries(outputStats).filter(([k, v]) => k.startsWith('by_') && typeof v === 'object' && Object.keys(v).length <= 20)
    : []

  // Check if any filter is applied
  const hasActiveFilters = extractActiveFilters(appliedFilters).length > 0
  // Check if draft differs from applied (user changed something but hasn't searched yet)
  const hasDraftChanges = JSON.stringify(draftFilters) !== JSON.stringify(appliedFilters)

  // Build filters JSON for download
  const buildDownloadFilters = () => {
    const activeFilters = extractActiveFilters(appliedFilters)
    return activeFilters.length > 0 ? JSON.stringify(activeFilters) : null
  }

  // Apply filters (triggered by Search button or Enter key)
  const applyFilters = () => {
    setAppliedFilters({ ...draftFilters })
    setPage(0)
  }

  // Clear all filters
  const clearFilters = () => {
    setDraftFilters({})
    setAppliedFilters({})
    setPage(0)
  }

  // Handle Enter key in filter inputs
  const handleFilterKeyDown = (e) => {
    if (e.key === 'Enter') {
      applyFilters()
    }
  }

  // Update a draft filter value (does NOT trigger API call)
  const updateFilter = (colName, filterData) => {
    setDraftFilters(prev => ({ ...prev, [colName]: filterData }))
  }

  // Render filter control based on data type
  const renderFilterControl = (colName, colConfig) => {
    // Old format: colConfig is an array of string values
    if (Array.isArray(colConfig)) {
      return (
        <div key={colName} className="flex items-center gap-2">
          <label className="text-xs text-gray-600 font-medium whitespace-nowrap">{colName}:</label>
          <select
            value={draftFilters[colName] || ''}
            onChange={(e) => updateFilter(colName, e.target.value)}
            className="px-2 py-1 border rounded text-xs min-w-[120px]"
          >
            <option value="">Tất cả</option>
            {colConfig.map(val => (
              <option key={val} value={val}>{val}</option>
            ))}
          </select>
        </div>
      )
    }

    // New format: colConfig is {type, values?, min?, max?}
    if (!isNewFilterFormat(colConfig)) return null

    const filterState = draftFilters[colName] || {}

    switch (colConfig.type) {
      case 'string': {
        // Dropdown if ≤ 20 values, otherwise text input with operator
        if (colConfig.values && colConfig.values.length <= 20) {
          return (
            <div key={colName} className="flex items-center gap-2">
              <label className="text-xs text-gray-600 font-medium whitespace-nowrap">{colName}:</label>
              <select
                value={filterState.value || ''}
                onChange={(e) => updateFilter(colName, e.target.value ? { op: 'eq', value: e.target.value } : {})}
                className="px-2 py-1 border rounded text-xs min-w-[120px]"
              >
                <option value="">Tất cả</option>
                {colConfig.values.map(val => {
                  const byKey = `by_${colName}`
                  const count = outputStats?.[byKey]?.[val]
                  return (
                    <option key={val} value={val}>{val}{count != null ? ` (${count})` : ''}</option>
                  )
                })}
              </select>
            </div>
          )
        }
        // Text input with operator for many values
        return (
          <div key={colName} className="flex items-center gap-1">
            <label className="text-xs text-gray-600 font-medium whitespace-nowrap">{colName}:</label>
            <select
              value={filterState.op || 'eq'}
              onChange={(e) => updateFilter(colName, { ...filterState, op: e.target.value })}
              className="px-1 py-1 border rounded text-xs w-16"
            >
              <option value="eq">=</option>
              <option value="like">Chứa</option>
            </select>
            <input
              type="text"
              value={filterState.value || ''}
              onChange={(e) => updateFilter(colName, e.target.value ? { op: filterState.op || 'eq', value: e.target.value } : {})}
              onKeyDown={handleFilterKeyDown}
              placeholder="Nhập giá trị..."
              className="px-2 py-1 border rounded text-xs w-32"
            />
          </div>
        )
      }

      case 'number': {
        return (
          <div key={colName} className="flex items-center gap-1">
            <label className="text-xs text-gray-600 font-medium whitespace-nowrap">{colName}:</label>
            <input
              type="number"
              value={filterState.min ?? ''}
              onChange={(e) => {
                const val = e.target.value
                updateFilter(colName, {
                  op: 'range',
                  min: val !== '' ? Number(val) : null,
                  max: filterState.max ?? null,
                })
              }}
              onKeyDown={handleFilterKeyDown}
              placeholder={colConfig.min != null ? `Min (${colConfig.min})` : 'Min'}
              className="px-2 py-1 border rounded text-xs w-28"
            />
            <span className="text-xs text-gray-400">-</span>
            <input
              type="number"
              value={filterState.max ?? ''}
              onChange={(e) => {
                const val = e.target.value
                updateFilter(colName, {
                  op: 'range',
                  min: filterState.min ?? null,
                  max: val !== '' ? Number(val) : null,
                })
              }}
              onKeyDown={handleFilterKeyDown}
              placeholder={colConfig.max != null ? `Max (${colConfig.max})` : 'Max'}
              className="px-2 py-1 border rounded text-xs w-28"
            />
          </div>
        )
      }

      case 'date': {
        return (
          <div key={colName} className="flex items-center gap-1">
            <label className="text-xs text-gray-600 font-medium whitespace-nowrap">{colName}:</label>
            <input
              type="date"
              value={filterState.min || ''}
              onChange={(e) => {
                updateFilter(colName, {
                  op: 'range',
                  min: e.target.value || null,
                  max: filterState.max ?? null,
                })
              }}
              onKeyDown={handleFilterKeyDown}
              className="px-2 py-1 border rounded text-xs"
              title={colConfig.min ? `Từ ${colConfig.min}` : 'Từ ngày'}
            />
            <span className="text-xs text-gray-400">-</span>
            <input
              type="date"
              value={filterState.max || ''}
              onChange={(e) => {
                updateFilter(colName, {
                  op: 'range',
                  min: filterState.min ?? null,
                  max: e.target.value || null,
                })
              }}
              onKeyDown={handleFilterKeyDown}
              className="px-2 py-1 border rounded text-xs"
              title={colConfig.max ? `Đến ${colConfig.max}` : 'Đến ngày'}
            />
          </div>
        )
      }

      case 'boolean': {
        return (
          <div key={colName} className="flex items-center gap-2">
            <label className="text-xs text-gray-600 font-medium whitespace-nowrap">{colName}:</label>
            <select
              value={filterState.value || ''}
              onChange={(e) => updateFilter(colName, e.target.value ? { op: 'eq', value: e.target.value } : {})}
              className="px-2 py-1 border rounded text-xs min-w-[100px]"
            >
              <option value="">Tất cả</option>
              {(colConfig.values || ['true', 'false']).map(val => (
                <option key={val} value={val}>{val}</option>
              ))}
            </select>
          </div>
        )
      }

      default:
        return null
    }
  }

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-gray-700 flex items-center gap-2">
          <span className="text-blue-500">📄</span> Chi tiết {outputName} ({total.toLocaleString()} bản ghi)
          {hasActiveFilters && <span className="text-xs text-orange-600 font-normal ml-1">(Đang lọc)</span>}
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => reportsApi.download(batchId, outputName.toLowerCase(), 'csv', null, buildDownloadFilters()).catch(() => toast.error('Lỗi tải file CSV'))}
            className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
          >
            {hasActiveFilters ? '📥 CSV (lọc)' : '📥 CSV'}
          </button>
          <button
            onClick={() => reportsApi.download(batchId, outputName.toLowerCase(), 'xlsx', null, buildDownloadFilters()).catch(() => toast.error('Lỗi tải file Excel'))}
            className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
          >
            {hasActiveFilters ? '📥 Excel (lọc)' : '📥 Excel'}
          </button>
          <button
            onClick={() => setWrapText(!wrapText)}
            className={`px-3 py-1 border rounded text-xs hover:bg-gray-50 ${wrapText ? 'bg-blue-100 border-blue-300 text-blue-700' : ''}`}
          >
            {wrapText ? '↩ Wrap ON' : '↩ Wrap OFF'}
          </button>
        </div>
      </div>

      {/* Status breakdown badges */}
      {statusBreakdowns.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {statusBreakdowns.map(([key, counts]) =>
            Object.entries(counts).map(([st, count]) => (
              <span key={`${key}_${st}`} className={`px-2 py-1 rounded text-xs ${
                st.includes('MATCHED') || st.includes('OK') ? 'bg-green-100 text-green-700' :
                st.includes('NOT') ? 'bg-red-100 text-red-700' :
                st.includes('RIGHT_ONLY') ? 'bg-purple-100 text-purple-700' :
                st.includes('MISMATCH') || st.includes('ERROR') ? 'bg-orange-100 text-orange-700' :
                'bg-gray-100 text-gray-700'
              }`}>
                {key.replace('by_', '')}: {st} ({count})
              </span>
            ))
          )}
        </div>
      )}

      {/* Dynamic filters (for outputs that have filter columns) */}
      {filterColumns && Object.keys(filterColumns).length > 0 && (
        <div className="mb-4 flex items-center gap-3 flex-wrap bg-gray-50 p-3 rounded-lg">
          <span className="text-sm font-medium text-gray-600 flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            Lọc:
          </span>
          {Object.entries(filterColumns).map(([colName, colConfig]) =>
            renderFilterControl(colName, colConfig)
          )}
          <button
            onClick={applyFilters}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              hasDraftChanges
                ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
                : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
            }`}
          >
            Tìm kiếm
          </button>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-2 py-1 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
            >
              Xóa lọc
            </button>
          )}
        </div>
      )}

      {/* Data table */}
      <div className="overflow-x-auto max-h-96 border rounded">
        {preview ? (
          <>
            <table className="w-full text-xs">
              <thead className="bg-gray-100 sticky top-0">
                <tr>
                  {preview.columns?.map((col) => (
                    <th key={col} className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {preview.data?.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    {preview.columns?.map((col) => (
                      <td key={col} className={`px-3 py-2 ${wrapText ? 'whitespace-pre-wrap break-words max-w-md' : 'whitespace-nowrap max-w-xs truncate'}`} title={String(row[col] ?? '')}>
                        {row[col]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t">
              <p className="text-xs text-gray-500">
                {page * pageSize + 1} - {Math.min((page + 1) * pageSize, preview.total)} / {preview.total}
              </p>
              <div className="flex gap-1">
                <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="px-2 py-0.5 border rounded text-xs hover:bg-gray-100 disabled:opacity-50">←</button>
                <button onClick={() => setPage(page + 1)} disabled={(page + 1) * pageSize >= preview.total} className="px-2 py-0.5 border rounded text-xs hover:bg-gray-100 disabled:opacity-50">→</button>
              </div>
            </div>
          </>
        ) : (
          <div className="p-4 text-center text-gray-500 text-sm">Không có dữ liệu {outputName}</div>
        )}
      </div>
    </div>
  )
}

/**
 * Sort output names by step_order from stats.output_order.
 * Falls back to alphabetical sort if output_order is not available.
 */
function sortOutputsByStepOrder(outputNames, outputOrder) {
  if (!outputOrder || Object.keys(outputOrder).length === 0) {
    return [...outputNames].sort()
  }
  return [...outputNames].sort((a, b) => {
    const orderA = outputOrder[a]?.step_order ?? 999
    const orderB = outputOrder[b]?.step_order ?? 999
    return orderA - orderB
  })
}

/**
 * Step logs viewer - reusable for both current and historical runs
 */
function StepLogsList({ stepLogs, isProcessing, expandedPreviews, setExpandedPreviews }) {
  if (!stepLogs || stepLogs.length === 0) {
    if (isProcessing) {
      return (
        <div className="flex items-center justify-center py-8 gap-3 text-yellow-600">
          <svg className="animate-spin h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="font-medium">Đang khởi tạo workflow...</span>
        </div>
      )
    }
    return (
      <div className="text-center py-6 text-gray-400 text-sm">Không có log</div>
    )
  }

  return (
    <div className="space-y-2">
      {stepLogs.map((log, idx) => (
        <div key={idx}>
          <div className={`flex items-start gap-4 p-3 rounded-lg ${
            log.status === 'error' ? 'bg-red-50 border-l-4 border-red-500' :
            log.status === 'ok' ? 'bg-green-50 border-l-4 border-green-500' :
            log.status === 'warning' ? 'bg-yellow-50 border-l-4 border-yellow-500' :
            log.status === 'start' ? 'bg-blue-50 border-l-4 border-blue-500' :
            'bg-gray-50 border-l-4 border-gray-300'
          }`}>
            <span className="text-xs text-gray-400 whitespace-nowrap font-mono min-w-[140px]">
              {formatTimestamp(log.time || log.timestamp)}
            </span>
            <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
              log.status === 'error' ? 'bg-red-200 text-red-700' :
              log.status === 'ok' ? 'bg-green-200 text-green-700' :
              log.status === 'warning' ? 'bg-yellow-200 text-yellow-700' :
              log.status === 'start' ? 'bg-blue-200 text-blue-700' :
              'bg-gray-200 text-gray-700'
            }`}>
              {log.step}
            </span>
            <span className="text-sm text-gray-700 flex-1">{log.message}</span>
            {log.data_preview && (
              <button
                onClick={() => setExpandedPreviews(prev => ({
                  ...prev,
                  [idx]: !prev[idx]
                }))}
                className="text-xs px-2 py-1 rounded bg-indigo-100 text-indigo-700 hover:bg-indigo-200 transition whitespace-nowrap flex items-center gap-1"
              >
                <span>{expandedPreviews[idx] ? '▼' : '▶'}</span>
                Xem {log.data_preview.total_rows > 10 ? '10/' : ''}{log.data_preview.total_rows} dòng
              </button>
            )}
          </div>

          {log.data_preview && expandedPreviews[idx] && (
            <div className="ml-4 mt-1 mb-2 border border-indigo-200 rounded-lg overflow-hidden">
              <div className="bg-indigo-50 px-3 py-2 flex items-center justify-between">
                <span className="text-xs font-semibold text-indigo-700">
                  📊 {log.data_preview.display_name} ({log.data_preview.source_name}) — {log.data_preview.total_rows} bản ghi, hiển thị {Math.min(10, log.data_preview.rows?.length || 0)} dòng đầu
                </span>
                <span className="text-xs text-indigo-500">{log.data_preview.columns?.length || 0} cột</span>
              </div>
              <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                <table className="min-w-full text-xs">
                  <thead className="bg-indigo-100 sticky top-0">
                    <tr>
                      <th className="px-2 py-1.5 text-left font-semibold text-indigo-800 border-r border-indigo-200">#</th>
                      {log.data_preview.columns?.map((col, colIdx) => (
                        <th key={colIdx} className="px-2 py-1.5 text-left font-semibold text-indigo-800 border-r border-indigo-200 whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {log.data_preview.rows?.map((row, rowIdx) => (
                      <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        <td className="px-2 py-1 text-gray-400 border-r border-gray-200 font-mono">{rowIdx + 1}</td>
                        {log.data_preview.columns?.map((col, colIdx) => (
                          <td key={colIdx} className="px-2 py-1 border-r border-gray-200 whitespace-nowrap max-w-[200px] truncate" title={String(row[col] ?? '')}>
                            {row[col] != null ? String(row[col]) : <span className="text-gray-300 italic">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ))}

      {isProcessing && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-yellow-50 border-l-4 border-yellow-400 animate-pulse">
          <span className="text-xs text-gray-400 whitespace-nowrap font-mono min-w-[140px]">...</span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-yellow-200 text-yellow-700">processing</span>
          <span className="text-sm text-yellow-700 flex-1">Đang xử lý bước tiếp theo...</span>
        </div>
      )}
    </div>
  )
}

/**
 * Run History Tab component.
 * Shows a table of all runs and lets the user view logs for each run.
 */
function RunHistoryTab({ batch, expandedPreviews, setExpandedPreviews, selectedRunNumber, setSelectedRunNumber }) {
  const runHistory = batch.run_history || []
  const isProcessing = batch.status === 'PROCESSING'

  // Fetch logs for a selected past run
  const { data: selectedRunData, isLoading: isLoadingRunLogs } = useQuery({
    queryKey: ['runLogs', batch.batch_id, selectedRunNumber],
    queryFn: () => reconciliationApiV2.getRunLogs(batch.batch_id, selectedRunNumber),
    enabled: !!selectedRunNumber,
  })

  // Determine which logs to display
  // If no run is selected or latest run is selected → use batch.step_logs (live-updating)
  const latestRunNumber = runHistory.length > 0 ? runHistory[0]?.run_number : null
  const isViewingLatest = !selectedRunNumber || selectedRunNumber === latestRunNumber
  const displayLogs = isViewingLatest ? batch.step_logs : (selectedRunData?.data?.step_logs || [])

  const runStatusColors = {
    PROCESSING: 'bg-yellow-100 text-yellow-800',
    COMPLETED: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
    ERROR: 'bg-red-100 text-red-800',
  }

  const triggeredByLabels = {
    initial: 'Lần đầu',
    rerun: 'Chạy lại',
  }

  return (
    <div className="space-y-4">
      {/* Run history table */}
      {runHistory.length > 0 && (
        <div>
          <h3 className="font-medium text-gray-700 flex items-center gap-2 mb-3">
            <span className="text-purple-500">🔄</span> Lịch sử chạy ({runHistory.length} lần)
          </h3>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Lần</th>
                  <th className="px-3 py-2 text-left">Loại</th>
                  <th className="px-3 py-2 text-left">Trạng thái</th>
                  <th className="px-3 py-2 text-left">Bắt đầu</th>
                  <th className="px-3 py-2 text-left">Thời gian</th>
                  <th className="px-3 py-2 text-left">Lỗi</th>
                  <th className="px-3 py-2 text-center">Logs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runHistory.map((run) => {
                  const isSelected = selectedRunNumber === run.run_number || (isViewingLatest && run.run_number === latestRunNumber && !selectedRunNumber)
                  return (
                    <tr key={run.run_number} className={`${isSelected ? 'bg-purple-50' : 'hover:bg-gray-50'} transition`}>
                      <td className="px-3 py-2 font-mono font-semibold text-gray-700">#{run.run_number}</td>
                      <td className="px-3 py-2">
                        <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                          {triggeredByLabels[run.triggered_by] || run.triggered_by}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${runStatusColors[run.status] || 'bg-gray-100 text-gray-800'}`}>
                          {run.status}
                          {run.status === 'PROCESSING' && (
                            <span className="ml-1 inline-block w-1.5 h-1.5 bg-yellow-600 rounded-full animate-pulse" />
                          )}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500 font-mono">{formatTimestamp(run.started_at)}</td>
                      <td className="px-3 py-2 text-xs text-gray-500">
                        {run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : run.status === 'PROCESSING' ? '...' : '-'}
                      </td>
                      <td className="px-3 py-2 text-xs text-red-600 max-w-[200px] truncate" title={run.error_message || ''}>
                        {run.error_message || '-'}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button
                          onClick={() => {
                            setSelectedRunNumber(run.run_number === latestRunNumber ? null : run.run_number)
                            setExpandedPreviews({})
                          }}
                          className={`text-xs px-2 py-1 rounded transition ${
                            isSelected
                              ? 'bg-purple-200 text-purple-800 font-semibold'
                              : 'bg-gray-100 text-gray-600 hover:bg-purple-100 hover:text-purple-700'
                          }`}
                        >
                          {isSelected ? '✓ Đang xem' : 'Xem log'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Step logs section */}
      <div>
        <h3 className="font-medium text-gray-700 flex items-center gap-2">
          <span className="text-purple-500">📜</span>
          {selectedRunNumber && !isViewingLatest
            ? `Chi tiết lần chạy #${selectedRunNumber}`
            : 'Chi tiết xử lý hiện tại'
          }
          {isProcessing && isViewingLatest && (
            <span className="ml-2 text-sm text-yellow-600 font-normal flex items-center gap-1">
              <svg className="animate-spin h-4 w-4 text-yellow-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Đang xử lý... (cập nhật mỗi 2s)
            </span>
          )}
        </h3>

        {/* Processing progress bar */}
        {isProcessing && isViewingLatest && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-3">
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 border-3 border-yellow-400 border-t-transparent rounded-full animate-spin"></div>
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800">Đang thực thi workflow đối soát</p>
                <p className="text-xs text-yellow-600 mt-0.5">
                  {(isViewingLatest ? batch.step_logs : displayLogs)?.length || 0} bước đã ghi nhận • Quá trình này có thể mất vài phút
                </p>
              </div>
            </div>
            <div className="mt-3 flex gap-1">
              {['load_data', 'matching', 'build_outputs', 'complete'].map((phase, i) => {
                const logs = isViewingLatest ? batch.step_logs : displayLogs
                const phaseReached = logs?.some(l => l.step?.includes(phase.split('_')[0]))
                const phaseDone = logs?.some(l => l.step?.includes(phase.split('_')[0]) && l.status === 'ok')
                return (
                  <div key={phase} className="flex items-center gap-1">
                    {i > 0 && <div className={`w-8 h-0.5 ${phaseDone ? 'bg-green-400' : phaseReached ? 'bg-yellow-400' : 'bg-gray-200'}`} />}
                    <div className={`w-3 h-3 rounded-full ${
                      phaseDone ? 'bg-green-500' : phaseReached ? 'bg-yellow-500 animate-pulse' : 'bg-gray-300'
                    }`} />
                    <span className={`text-xs ${phaseDone ? 'text-green-700' : phaseReached ? 'text-yellow-700' : 'text-gray-400'}`}>
                      {phase === 'load_data' ? 'Tải dữ liệu' : phase === 'matching' ? 'So khớp' : phase === 'build_outputs' ? 'Xuất kết quả' : 'Hoàn thành'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {isLoadingRunLogs && !isViewingLatest ? (
          <div className="flex items-center justify-center py-8 gap-3 text-gray-500">
            <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Đang tải log...</span>
          </div>
        ) : (
          <div className="mt-3">
            <StepLogsList
              stepLogs={displayLogs}
              isProcessing={isProcessing && isViewingLatest}
              expandedPreviews={expandedPreviews}
              setExpandedPreviews={setExpandedPreviews}
            />
          </div>
        )}
      </div>

      {/* Empty state when no runs and not processing */}
      {runHistory.length === 0 && !isProcessing && (!batch.step_logs || batch.step_logs.length === 0) && (
        <div className="text-center py-8 text-gray-500">
          <div className="text-4xl mb-3">📋</div>
          <p>Chưa có lịch sử xử lý</p>
        </div>
      )}
    </div>
  )
}

const auditActionLabels = {
  'SUBMIT': 'Gửi phê duyệt',
  'APPROVE': 'Phê duyệt',
  'REJECT': 'Từ chối',
  'CREATE': 'Tạo mới',
  'UPDATE': 'Cập nhật',
  'RUN': 'Chạy đối soát',
  'RERUN': 'Chạy lại',
  'STOP': 'Dừng',
}

function AuditHistoryTab({ batchId }) {
  const { data: auditData, isLoading } = useQuery({
    queryKey: ['auditHistory', batchId],
    queryFn: () => approvalsApi.getHistory(batchId),
    enabled: !!batchId,
  })

  const logs = auditData?.data || []

  if (isLoading) {
    return <div className="text-center py-8 text-gray-500">Đang tải...</div>
  }

  if (logs.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <div className="text-4xl mb-3">🕐</div>
        <p>Chưa có lịch sử chuyển trạng thái</p>
      </div>
    )
  }

  return (
    <div className="space-y-0">
      {/* Timeline */}
      <div className="relative">
        {logs.map((log, idx) => (
          <div key={idx} className="flex gap-4 pb-6 relative">
            {/* Timeline line */}
            {idx < logs.length - 1 && (
              <div className="absolute left-[15px] top-8 bottom-0 w-0.5 bg-gray-200" />
            )}
            {/* Dot */}
            <div className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 ${
              log.action === 'APPROVE' ? 'bg-green-500' :
              log.action === 'REJECT' ? 'bg-red-500' :
              log.action === 'SUBMIT' ? 'bg-blue-500' :
              'bg-gray-400'
            }`}>
              {log.action === 'APPROVE' ? '✓' :
               log.action === 'REJECT' ? '✕' :
               log.action === 'SUBMIT' ? '→' : '•'}
            </div>
            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-gray-800">
                  {auditActionLabels[log.action] || log.action}
                </span>
                {log.old_values?.status && log.new_values?.status && (
                  <span className="text-xs text-gray-500">
                    {statusLabels[log.old_values.status] || log.old_values.status} → {statusLabels[log.new_values.status] || log.new_values.status}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500 mt-0.5">
                {log.user_email} • {formatTimestamp(log.timestamp)}
              </p>
              {log.summary && (
                <p className="text-xs text-gray-400 mt-1">{log.summary}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function BatchDetailPage() {
  const { batchId } = useParams()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [activeMainTab, setActiveMainTab] = useState('results') // results, report, history, audit
  const [expandedPreviews, setExpandedPreviews] = useState({}) // track which data previews are open
  const [selectedRunNumber, setSelectedRunNumber] = useState(null) // which run's logs to view
  
  // Track whether user triggered a rerun (to show progress and auto-switch tabs)
  const [isRerunTriggered, setIsRerunTriggered] = useState(false)
  const prevStatusRef = useRef(null)
  
  // Fetch batch details - try V2 first, fallback to V1
  // Poll every 2s when batch is PROCESSING for real-time step progress
  const { data: batchData, isLoading } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: async () => {
      try {
        return await reconciliationApiV2.getBatch(batchId)
      } catch {
        return await reconciliationApi.getBatch(batchId)
      }
    },
    refetchInterval: (query) => {
      const status = query?.state?.data?.data?.status
      return status === 'PROCESSING' ? 2000 : false
    },
  })
  
  // Detect status transitions (PROCESSING → COMPLETED/ERROR) and show toast
  useEffect(() => {
    const currentStatus = batchData?.data?.status
    if (prevStatusRef.current === 'PROCESSING' && currentStatus && currentStatus !== 'PROCESSING') {
      // Workflow just finished
      setIsRerunTriggered(false)
      queryClient.invalidateQueries({ queryKey: ['stats', batchId] })
      queryClient.invalidateQueries({ queryKey: ['preview', batchId] })
      if (currentStatus === 'COMPLETED') {
        toast.success('Đối soát hoàn tất thành công!')
        setActiveMainTab('results')
      } else if (currentStatus === 'ERROR') {
        toast.error('Đối soát thất bại: ' + (batchData?.data?.error_message || 'Lỗi không xác định'))
      }
    }
    // Auto-switch to history tab when page loads with PROCESSING status
    if (currentStatus === 'PROCESSING' && !isRerunTriggered) {
      setIsRerunTriggered(true)
      setActiveMainTab('history')
    }
    // Auto-switch to history tab when page loads with ERROR/FAILED and there are step_logs
    if ((currentStatus === 'ERROR' || currentStatus === 'FAILED') && !prevStatusRef.current && batchData?.data?.step_logs?.length > 0) {
      setActiveMainTab('history')
    }
    prevStatusRef.current = currentStatus
  }, [batchData?.data?.status])
  
  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['stats', batchId],
    queryFn: () => reportsApi.getStats(batchId),
    enabled: !!batchData?.data,
  })
  
  const batch = batchData?.data
  const stats = statsData?.data
  
  // Mutations - try V2 first, fallback to V1
  const rerunMutation = useMutation({
    mutationFn: async () => {
      try {
        return await reconciliationApiV2.rerunBatch(batchId)
      } catch {
        return await reconciliationApi.rerunBatch(batchId)
      }
    },
    onSuccess: () => {
      // Backend now returns immediately with PROCESSING status
      // Switch to history tab and start polling for real-time progress
      setIsRerunTriggered(true)
      setActiveMainTab('history')
      toast('Đang chạy lại đối soát...', { icon: '⏳' })
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
    },
    onError: (err) => {
      const detail = err.response?.data?.detail
      const msg = Array.isArray(detail) 
        ? detail.map(e => e.msg || JSON.stringify(e)).join('; ')
        : (typeof detail === 'string' ? detail : 'Lỗi khi chạy lại')
      toast.error(msg)
    },
  })
  
  const submitMutation = useMutation({
    mutationFn: () => approvalsApi.submit(batchId),
    onSuccess: () => {
      toast.success('Đã gửi phê duyệt')
      queryClient.invalidateQueries(['batch', batchId])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })
  
  const stopMutation = useMutation({
    mutationFn: async () => {
      try {
        return await reconciliationApiV2.stopBatch(batchId)
      } catch {
        return await reconciliationApi.stopBatch(batchId)
      }
    },
    onSuccess: () => {
      toast.success('Đã dừng batch')
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
    },
    onError: (err) => {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : 'Lỗi khi dừng batch'
      toast.error(msg)
    },
  })
  
  // State for report generation logs
  const [reportLogs, setReportLogs] = useState(null)
  
  const generateReportMutation = useMutation({
    mutationFn: () => reportsApi.generateReport(batchId),
    onSuccess: (response) => {
      const data = response.data
      setReportLogs(data.logs || [])
      if (data.success) {
        toast.success('Đã tạo báo cáo')
      } else {
        toast.error('Tạo báo cáo thất bại - xem logs để biết chi tiết')
      }
      queryClient.invalidateQueries(['batch', batchId])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Đang tải...</div>
      </div>
    )
  }
  
  if (!batch) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Không tìm thấy batch</div>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold text-gray-800">{batch.batch_id}</h1>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[batch.status] || 'bg-gray-100 text-gray-800'}`}>
                {statusLabels[batch.status] || batch.status}
              </span>
            </div>
            <p className="text-gray-500 mt-1">
              {batch.partner_code} / {batch.service_code} • Kỳ: {batch.period_from} - {batch.period_to}
            </p>
            {batch.error_message && batch.status !== 'COMPLETED' && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-700 font-medium text-sm mb-1">❌ Lỗi xử lý:</p>
                <pre className="text-red-600 text-sm whitespace-pre-wrap break-words font-mono">{batch.error_message}</pre>
              </div>
            )}
          </div>
          
          <div className="flex gap-2">
            {/* COMPLETED: Chạy lại + Gửi phê duyệt */}
            {batch.status === 'COMPLETED' && (
              <>
                <button
                  onClick={() => rerunMutation.mutate()}
                  disabled={rerunMutation.isPending}
                  className="px-4 py-2 border rounded-lg hover:bg-gray-50 transition"
                >
                  Chạy lại
                </button>
                <button
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                >
                  Gửi phê duyệt
                </button>
              </>
            )}
            {/* ERROR / CANCELLED / UPLOADING: Chạy lại */}
            {['ERROR', 'CANCELLED', 'UPLOADING'].includes(batch.status) && (
              <button
                onClick={() => rerunMutation.mutate()}
                disabled={rerunMutation.isPending}
                className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
              >
                Chạy lại
              </button>
            )}
            {/* PENDING_APPROVAL: hiển thị trạng thái */}
            {batch.status === 'PENDING_APPROVAL' && (
              <div className="px-4 py-2 bg-purple-100 text-purple-800 rounded-lg text-sm font-medium">
                Đang chờ phê duyệt
              </div>
            )}
            {batch.status === 'PROCESSING' && (
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 px-4 py-2 bg-yellow-100 text-yellow-800 rounded-lg">
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="text-sm font-medium">Đang xử lý...</span>
                </div>
                <button
                  onClick={() => stopMutation.mutate()}
                  disabled={stopMutation.isPending}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition disabled:opacity-50"
                >
                  {stopMutation.isPending ? 'Đang dừng...' : '🛑 Dừng'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Files Uploaded Section - Dynamic from config data sources */}
      {(batch.data_sources?.length > 0 || batch.files_uploaded) && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">📁 File đã upload</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {batch.data_sources?.length > 0 ? (
              /* V2: Dynamic sources from config */
              batch.data_sources.map((ds) => (
                <div key={ds.source_name} className="border rounded-lg p-4">
                  <h3 className="font-medium text-gray-700 mb-2">
                    {ds.source_name} - {ds.display_name}
                    {ds.is_required && <span className="ml-1 text-red-500 text-xs">*</span>}
                  </h3>
                  {ds.files?.length > 0 ? (
                    <ul className="space-y-1">
                      {ds.files.map((fileName, idx) => (
                        <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                          <span className="text-green-500">✓</span>
                          <span className="truncate" title={fileName}>
                            {/* Remove the 000_ prefix added during upload */}
                            {fileName.replace(/^\d{3}_/, '')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-gray-400 italic">Không có file</p>
                  )}
                </div>
              ))
            ) : (
              /* V1 Fallback: Hardcoded B1/B2/B3 */
              <>
                {['b1', 'b2', 'b3', 'b4'].map((key) => {
                  const label = { b1: 'B1', b2: 'B2', b3: 'B3', b4: 'B4' }[key]
                  const files = batch.files_uploaded?.[key] || batch.files_uploaded?.[key.toUpperCase()] || []
                  return (
                    <div key={key} className="border rounded-lg p-4">
                      <h3 className="font-medium text-gray-700 mb-2">{label}</h3>
                      {files.length > 0 ? (
                        <ul className="space-y-1">
                          {files.map((path, idx) => (
                            <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                              <span className="text-green-500">✓</span>
                              <span className="truncate" title={path}>{typeof path === 'string' ? path.split(/[/\\]/).pop() : path}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-gray-400 italic">Không có file</p>
                      )}
                    </div>
                  )
                })}
              </>
            )}
          </div>
        </div>
      )}
      
      {/* MAIN TABS: Kết quả | Báo cáo | Lịch sử */}
      {['COMPLETED', 'APPROVED', 'PENDING_APPROVAL', 'PROCESSING', 'ERROR', 'FAILED', 'CANCELLED'].includes(batch.status) && (
        <div className="bg-white rounded-xl shadow-sm">
          <div className="border-b flex">
            <button
              onClick={() => !['PROCESSING', 'ERROR', 'FAILED'].includes(batch.status) && setActiveMainTab('results')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'results' && !['PROCESSING', 'ERROR', 'FAILED'].includes(batch.status) ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700'} ${['PROCESSING', 'ERROR', 'FAILED'].includes(batch.status) ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              📊 Kết quả
            </button>
            <button
              onClick={() => !['PROCESSING', 'ERROR', 'FAILED'].includes(batch.status) && setActiveMainTab('report')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'report' && !['PROCESSING', 'ERROR', 'FAILED'].includes(batch.status) ? 'border-b-2 border-green-600 text-green-600' : 'text-gray-500 hover:text-gray-700'} ${['PROCESSING', 'ERROR', 'FAILED'].includes(batch.status) ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              📄 Báo cáo
            </button>
            <button
              onClick={() => setActiveMainTab('history')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'history' ? 'border-b-2 border-purple-600 text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
            >
              📜 Lịch sử xử lý
              {batch.run_history?.length > 0 && (
                <span className="ml-1 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full font-semibold">
                  {batch.run_history.length}
                </span>
              )}
              {batch.status === 'PROCESSING' && (
                <span className="ml-2 inline-block w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />
              )}
            </button>
            <button
              onClick={() => setActiveMainTab('audit')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'audit' ? 'border-b-2 border-amber-600 text-amber-600' : 'text-gray-500 hover:text-gray-700'}`}
            >
              🕐 Lịch sử trạng thái
            </button>
          </div>
          
          <div className="p-6">
            {/* ===== TAB: KẾT QUẢ ===== */}
            {activeMainTab === 'results' && (
              <div className="space-y-6">
                {/* 1. Khối dữ liệu đầu vào */}
                <div className="border rounded-lg p-4 bg-gray-50">
                  <h3 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <span className="text-blue-500">📁</span> Dữ liệu đầu vào
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                    {batch?.data_sources?.length > 0 ? (
                      batch.data_sources.map((ds, idx) => {
                        const key = `total_${ds.source_name.toLowerCase()}`
                        const colors = ['text-blue-600', 'text-purple-600', 'text-teal-600', 'text-orange-600', 'text-pink-600']
                        return (
                          <div key={ds.source_name} className="bg-white rounded-lg p-3 border text-center">
                            <p className="text-xs text-gray-500 mb-1">{ds.source_name} ({ds.display_name})</p>
                            <p className={`text-xl font-bold ${colors[idx % colors.length]}`}>
                              {(stats?.basic_stats?.[key])?.toLocaleString() || 0}
                            </p>
                          </div>
                        )
                      })
                    ) : (
                      <>
                        <div className="bg-white rounded-lg p-3 border text-center">
                          <p className="text-xs text-gray-500 mb-1">B1 (Sao kê)</p>
                          <p className="text-xl font-bold text-blue-600">{stats?.basic_stats?.total_b1?.toLocaleString() || 0}</p>
                        </div>
                        <div className="bg-white rounded-lg p-3 border text-center">
                          <p className="text-xs text-gray-500 mb-1">B4 (Đối tác)</p>
                          <p className="text-xl font-bold text-orange-600">{stats?.basic_stats?.total_b4?.toLocaleString() || 0}</p>
                        </div>
                      </>
                    )}
                  </div>
                </div>
                
                {/* 2. Khối kết quả so khớp - bảng theo step */}
                <div className="border rounded-lg p-4 bg-gray-50">
                  <h3 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <span className="text-green-500">🔗</span> Kết quả so khớp
                  </h3>
                  {stats?.output_order && Object.keys(stats.output_order).length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm border-collapse">
                        <thead>
                          <tr className="bg-white border">
                            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 border">Step</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 border">Nguồn trái</th>
                            <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600 border">Số bản ghi</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 border">Nguồn phải</th>
                            <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600 border">Số bản ghi</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 border">Kết quả</th>
                            <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600 border">Số bản ghi</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortOutputsByStepOrder(Object.keys(stats.output_order), stats.output_order).map(outputName => {
                            const info = stats.output_order[outputName]
                            const leftKey = `total_${info.left_source?.toLowerCase()}`
                            const rightKey = `total_${info.right_source?.toLowerCase()}`
                            const outputDetails = stats?.basic_stats?.output_details || {}
                            // Lookup count: basic_stats.total_xxx → output_details (from summary_stats) → output_stats (from CSV) → '-'
                            const leftCount = stats?.basic_stats?.[leftKey] || outputDetails[info.left_source]?.row_count || stats?.output_stats?.[info.left_source]?.total || '-'
                            const rightCount = stats?.basic_stats?.[rightKey] || outputDetails[info.right_source]?.row_count || stats?.output_stats?.[info.right_source]?.total || '-'
                            const resultCount = outputDetails[outputName]?.row_count || stats?.output_stats?.[outputName]?.total || '-'
                            return (
                              <tr key={outputName} className="border hover:bg-blue-50">
                                <td className="px-3 py-2 border font-medium text-gray-700">{info.step_order}</td>
                                <td className="px-3 py-2 border text-blue-700 font-medium">{info.left_source}</td>
                                <td className="px-3 py-2 border text-right font-semibold text-blue-600">{typeof leftCount === 'number' ? leftCount.toLocaleString() : leftCount}</td>
                                <td className="px-3 py-2 border text-purple-700 font-medium">{info.right_source}</td>
                                <td className="px-3 py-2 border text-right font-semibold text-purple-600">{typeof rightCount === 'number' ? rightCount.toLocaleString() : rightCount}</td>
                                <td className="px-3 py-2 border text-green-700 font-medium">{outputName}</td>
                                <td className="px-3 py-2 border text-right font-semibold text-green-600">{typeof resultCount === 'number' ? resultCount.toLocaleString() : resultCount}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-4 text-gray-500 text-sm">Chưa có dữ liệu kết quả so khớp.</div>
                  )}
                </div>
                
                {/* 3. Chi tiết từng output - sorted by step_order */}
                {stats?.file_results && sortOutputsByStepOrder(
                  Object.keys(stats.file_results),
                  stats?.output_order
                ).map(outputName => (
                    <OutputDetailSection
                      key={outputName}
                      outputName={outputName}
                      batchId={batchId}
                      outputStats={stats?.output_stats?.[outputName]}
                    />
                ))}
                
                {/* Fallback: show A2 from legacy stats if file_results not available */}
                {!stats?.file_results && stats?.output_stats?.A2?.total > 0 && (
                  <OutputDetailSection
                    outputName="A2"
                    batchId={batchId}
                    outputStats={stats?.output_stats?.A2}
                  />
                )}
              </div>
            )}
            
            {/* ===== TAB: BÁO CÁO ===== */}
            {activeMainTab === 'report' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-gray-700 flex items-center gap-2">
                    <span className="text-green-500">📄</span> Báo cáo đối soát
                  </h3>
                  {['COMPLETED', 'APPROVED'].includes(batch.status) && (
                    <button
                      onClick={() => generateReportMutation.mutate()}
                      disabled={generateReportMutation.isPending}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm"
                    >
                      {generateReportMutation.isPending ? '⏳ Đang tạo...' : '📊 Tạo báo cáo mới'}
                    </button>
                  )}
                </div>
                
                {/* Display generated report if exists */}
                {batch.file_report ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 bg-green-50">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">📊</span>
                        <div>
                          <p className="font-medium text-gray-700">Báo cáo đối soát</p>
                          <p className="text-xs text-gray-500">
                            {batch.file_report.split('/').pop() || batch.file_report.split('\\').pop()}
                          </p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => reportsApi.download(batchId, 'report', 'xlsx').catch(e => toast.error('Lỗi tải file'))}
                          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
                        >
                          📥 Tải xuống Excel
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-6xl mb-4">📭</div>
                    <p className="font-medium">Chưa có báo cáo nào được tạo</p>
                    <p className="text-sm mt-2">Nhấn "Tạo báo cáo mới" để tạo báo cáo từ kết quả đối soát</p>
                  </div>
                )}
                
                {/* Report Generation Logs */}
                {reportLogs && reportLogs.length > 0 && (
                  <div className="border-t pt-4 mt-4">
                    <h4 className="text-sm font-medium text-gray-600 mb-3 flex items-center gap-2">
                      📋 Logs tạo báo cáo
                      <button 
                        onClick={() => setReportLogs(null)}
                        className="text-xs text-gray-400 hover:text-gray-600"
                      >
                        ✕ Đóng
                      </button>
                    </h4>
                    <div className="bg-gray-900 text-gray-100 rounded-lg p-4 max-h-96 overflow-auto text-xs font-mono">
                      {reportLogs.map((log, idx) => (
                        <div key={idx} className={`mb-2 ${
                          log.status === 'error' ? 'text-red-400' : 
                          log.status === 'warning' ? 'text-yellow-400' : 
                          log.status === 'ok' ? 'text-green-400' : 'text-gray-300'
                        }`}>
                          <span className="text-gray-500">[{log.time?.split('T')[1]?.split('.')[0] || ''}]</span>
                          <span className={`ml-2 px-1 rounded ${
                            log.status === 'error' ? 'bg-red-900' : 
                            log.status === 'warning' ? 'bg-yellow-900' : 
                            log.status === 'ok' ? 'bg-green-900' : 'bg-gray-700'
                          }`}>
                            {log.status?.toUpperCase()}
                          </span>
                          <span className="ml-2 text-blue-300">[{log.step}]</span>
                          <span className="ml-2">{log.message}</span>
                          {log.sql && (
                            <div className="mt-1 ml-4 text-gray-400 bg-gray-800 p-2 rounded">
                              SQL: {log.sql}
                            </div>
                          )}
                          {log.result && (
                            <div className="mt-1 ml-4 text-cyan-300">
                              → Result: {log.result}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Quick download buttons - dynamic from file_results */}
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-gray-600 mb-3">📥 Tải nhanh dữ liệu</h4>
                  <div className="flex gap-3 flex-wrap">
                    {/* Dynamic: iterate all available outputs */}
                    {stats?.file_results ? (
                      sortOutputsByStepOrder(Object.keys(stats.file_results), stats?.output_order).map(outputName => (
                        <div key={outputName} className="flex gap-1">
                          <button
                            onClick={() => reportsApi.download(batchId, outputName.toLowerCase(), 'xlsx').catch(() => toast.error('Lỗi tải file'))}
                            className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                          >
                            📊 {outputName} Excel
                          </button>
                          <button
                            onClick={() => reportsApi.download(batchId, outputName.toLowerCase(), 'csv').catch(() => toast.error('Lỗi tải file'))}
                            className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                          >
                            📄 {outputName} CSV
                          </button>
                        </div>
                      ))
                    ) : (
                      <>
                        {/* Fallback: hardcoded A1 */}
                        <button
                          onClick={() => reportsApi.download(batchId, 'a1', 'xlsx').catch(() => toast.error('Lỗi tải file'))}
                          className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                        >
                          📊 A1 Excel
                        </button>
                        <button
                          onClick={() => reportsApi.download(batchId, 'a1', 'csv').catch(() => toast.error('Lỗi tải file'))}
                          className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                        >
                          📄 A1 CSV
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {/* ===== TAB: LỊCH SỬ XỬ LÝ ===== */}
            {activeMainTab === 'history' && (
              <RunHistoryTab
                batch={batch}
                expandedPreviews={expandedPreviews}
                setExpandedPreviews={setExpandedPreviews}
                selectedRunNumber={selectedRunNumber}
                setSelectedRunNumber={setSelectedRunNumber}
              />
            )}

            {/* ===== TAB: LỊCH SỬ TRẠNG THÁI ===== */}
            {activeMainTab === 'audit' && (
              <AuditHistoryTab batchId={batchId} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

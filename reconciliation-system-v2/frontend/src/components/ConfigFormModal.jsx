/**
 * ConfigFormModal Component
 * 
 * Form đầy đủ để tạo/sửa cấu hình đối soát
 * Bao gồm:
 * - Thông tin cơ bản (partner, service, validity)
 * - File config (B1, B2, B3)
 * - Data B4 config
 * - Matching rules (Key Match + Amount Match)
 * - Output columns config
 */

import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { configsApi } from '../services/api'

const TABS = [
  { id: 'basic', label: 'Thông tin cơ bản', icon: '📋' },
  { id: 'files', label: 'Cấu hình File', icon: '📁' },
  { id: 'b4', label: 'Nguồn dữ liệu B4', icon: '🗄️' },
  { id: 'matching', label: 'Quy tắc Matching', icon: '🔗' },
  { id: 'status', label: 'Combine Status', icon: '🎯' },
  { id: 'output', label: 'Cấu hình Output', icon: '📤' },
  { id: 'report', label: 'Report Template', icon: '📊' },
]

const DEFAULT_CONFIG = {
  partner_code: '',
  partner_name: '',
  service_code: '',
  service_name: '',
  valid_from: new Date().toISOString().split('T')[0],
  valid_to: null,
  file_b1_config: {
    header_row: 1,
    data_start_row: 2,
    columns: {}
  },
  file_b2_config: null,
  file_b3_config: null,
  data_b4_config: {
    db_connection: 'vnptmoney_main',
    sql_file: '',
    sql_params: {},
    mock_file: ''
  },
  matching_rules_b1b4: {
    match_type: 'expression',
    key_match: {
      left: { column: '', transforms: [] },
      right: { column: '', transforms: [] },
      compare_type: 'exact'
    },
    amount_match: {
      left: { column: '', transforms: [] },
      right: { column: '', transforms: [] },
      compare_type: 'tolerance',
      tolerance: 0,
      tolerance_type: 'absolute'
    },
    status_logic: {
      all_match: 'MATCHED',
      key_match_amount_mismatch: 'MISMATCH',
      no_key_match: 'NOT_FOUND'
    }
  },
  matching_rules_b1b2: null,
  matching_rules_b3a1: null,
  status_combine_rules: {
    rules: [
      { b1b4: 'MATCHED', b1b2: 'NOT_FOUND', final: 'OK' },
      { b1b4: 'MATCHED', b1b2: 'MATCHED', final: 'REFUNDED' },
      { b1b4: 'NOT_FOUND', b1b2: '*', final: 'NOT_IN_SYSTEM' },
      { b1b4: 'MISMATCH', b1b2: '*', final: 'AMOUNT_ERROR' }
    ],
    default: 'UNKNOWN'
  },
  output_a1_config: {
    columns: []
  },
  output_a2_config: null,
  report_template_path: null,
  report_cell_mapping: null
}

function FileConfigEditor({ config, onChange, label }) {
  // Use columns directly from config props, no local state sync issues
  const columns = config?.columns || {}
  const [newColumn, setNewColumn] = useState({ name: '', excel: '' })
  
  const handleAddColumn = () => {
    if (newColumn.name && newColumn.excel) {
      const updated = { ...columns, [newColumn.name]: newColumn.excel }
      onChange({ ...config, columns: updated })
      setNewColumn({ name: '', excel: '' })
    }
  }
  
  const handleRemoveColumn = (name) => {
    const { [name]: _, ...rest } = columns
    onChange({ ...config, columns: rest })
  }
  
  return (
    <div className="border rounded-lg p-4 bg-white">
      <h4 className="font-medium text-gray-700 mb-3">{label}</h4>
      
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-sm text-gray-600">Dòng header</label>
          <input
            type="number"
            value={config?.header_row || 1}
            onChange={(e) => onChange({ ...config, header_row: parseInt(e.target.value) || 1 })}
            className="w-full px-3 py-2 border rounded mt-1"
            min="1"
          />
        </div>
        <div>
          <label className="text-sm text-gray-600">Dòng bắt đầu data</label>
          <input
            type="number"
            value={config?.data_start_row || 2}
            onChange={(e) => onChange({ ...config, data_start_row: parseInt(e.target.value) || 2 })}
            className="w-full px-3 py-2 border rounded mt-1"
            min="1"
          />
        </div>
      </div>
      
      <div className="mb-3">
        <label className="text-sm text-gray-600 block mb-2">Mapping cột:</label>
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {Object.entries(columns).map(([name, excel]) => (
            <div key={name} className="flex items-center gap-2 bg-gray-50 p-2 rounded">
              <span className="flex-1 font-medium text-sm">{name}</span>
              <span className="text-gray-400">→</span>
              <span className="text-blue-600 font-mono text-sm">{excel}</span>
              <button
                onClick={() => handleRemoveColumn(name)}
                className="text-red-500 hover:bg-red-50 p-1 rounded"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>
      
      <div className="flex gap-2">
        <input
          type="text"
          value={newColumn.name}
          onChange={(e) => setNewColumn({ ...newColumn, name: e.target.value })}
          placeholder="Tên cột (VD: txn_id)"
          className="flex-1 px-3 py-2 border rounded text-sm"
        />
        <input
          type="text"
          value={newColumn.excel}
          onChange={(e) => setNewColumn({ ...newColumn, excel: e.target.value.toUpperCase() })}
          placeholder="Cột Excel (A, B, C...)"
          className="w-20 px-3 py-2 border rounded text-sm text-center"
        />
        <button
          onClick={handleAddColumn}
          disabled={!newColumn.name || !newColumn.excel}
          className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          +
        </button>
      </div>
    </div>
  )
}

function OutputColumnsEditor({ config, onChange, b1Columns, b4Columns, b2Columns = [], b3Columns = [], a1Columns = [], label = "Cấu hình cột output A1", showB2B3 = false, showA1 = false }) {
  const columns = config?.columns || []
  
  const handleAddColumn = () => {
    onChange({
      ...config,
      columns: [...columns, { name: '', source: 'B1', column: '' }]
    })
  }
  
  const handleUpdateColumn = (idx, field, value) => {
    const updated = [...columns]
    updated[idx] = { ...updated[idx], [field]: value }
    
    // Khi thay đổi cột nguồn, tự động set alias = tên cột nguồn
    if (field === 'column' && value) {
      updated[idx].name = value
    }
    // Khi đổi source, reset column và name
    if (field === 'source') {
      updated[idx].column = ''
      updated[idx].name = ''
    }
    
    onChange({ ...config, columns: updated })
  }
  
  const handleRemoveColumn = (idx) => {
    onChange({ ...config, columns: columns.filter((_, i) => i !== idx) })
  }
  
  const getAvailableColumns = (source) => {
    switch (source) {
      case 'B1': return b1Columns || []
      case 'B2': return b2Columns || []
      case 'B3': return b3Columns || []
      case 'B4': return b4Columns || []
      case 'A1': return a1Columns || []
      case '_SYSTEM': return ['status_b1b4', 'status_b1b2', 'status_b3a1', 'final_status', 'diff_amount', 'match_date']
      default: return []
    }
  }

  const getSourceLabel = (source) => {
    switch (source) {
      case 'B1': return 'B1 (Sao kê)'
      case 'B2': return 'B2 (Hoàn tiền)'
      case 'B3': return 'B3 (Đối tác)'
      case 'B4': return 'B4 (Hệ thống)'
      case 'A1': return 'A1 (Kết quả)'
      case '_SYSTEM': return 'Hệ thống'
      case '_CALC': return 'Tính toán'
      default: return source
    }
  }
  
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-medium text-gray-700">{label}</h4>
        <button
          onClick={handleAddColumn}
          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          + Thêm cột
        </button>
      </div>

      {/* Header row */}
      {columns.length > 0 && (
        <div className="flex items-center gap-2 px-2 text-xs text-gray-500 font-medium">
          <span className="w-28">Nguồn</span>
          <span className="flex-1">Cột nguồn</span>
          <span className="flex-1">Tên alias (output)</span>
          <span className="w-8"></span>
        </div>
      )}
      
      <div className="space-y-2">
        {columns.map((col, idx) => (
          <div key={idx} className="flex items-center gap-2 bg-gray-50 p-2 rounded">
            {/* 1. Nguồn */}
            <select
              value={col.source}
              onChange={(e) => handleUpdateColumn(idx, 'source', e.target.value)}
              className="w-28 px-2 py-1 border rounded text-sm"
            >
              <option value="B1">B1 (Sao kê)</option>
              {showB2B3 && <option value="B2">B2 (Hoàn)</option>}
              {showB2B3 && <option value="B3">B3 (Đối tác)</option>}
              <option value="B4">B4 (HT)</option>
              {showA1 && <option value="A1">A1 (KQ)</option>}
              <option value="_SYSTEM">Hệ thống</option>
              <option value="_CALC">Tính toán</option>
            </select>

            {/* 2. Cột nguồn hoặc công thức */}
            {col.source === '_CALC' ? (
              <input
                type="text"
                value={col.formula || ''}
                onChange={(e) => handleUpdateColumn(idx, 'formula', e.target.value)}
                placeholder="Công thức tính toán"
                className="flex-1 px-2 py-1 border rounded text-sm font-mono"
              />
            ) : (
              <select
                value={col.column}
                onChange={(e) => handleUpdateColumn(idx, 'column', e.target.value)}
                className="flex-1 px-2 py-1 border rounded text-sm"
              >
                <option value="">-- Chọn cột --</option>
                {getAvailableColumns(col.source).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}

            {/* 3. Tên alias */}
            <input
              type="text"
              value={col.name}
              onChange={(e) => handleUpdateColumn(idx, 'name', e.target.value)}
              placeholder="Tên cột output"
              className="flex-1 px-2 py-1 border rounded text-sm"
            />

            {/* Xóa */}
            <button
              onClick={() => handleRemoveColumn(idx)}
              className="p-1 text-red-500 hover:bg-red-50 rounded w-8 flex justify-center"
            >
              ✕
            </button>
          </div>
        ))}

        {columns.length === 0 && (
          <div className="text-center py-4 text-gray-400 text-sm italic">
            Chưa có cột nào. Bấm "+ Thêm cột" để bắt đầu.
          </div>
        )}
      </div>
    </div>
  )
}

// Status Combine Rules Editor
function StatusCombineEditor({ config, onChange, hasB2 }) {
  const rules = config?.rules || []
  const defaultStatus = config?.default || 'UNKNOWN'

  const handleAddRule = () => {
    onChange({
      ...config,
      rules: [...rules, { b1b4: 'MATCHED', b1b2: hasB2 ? 'NOT_FOUND' : '*', final: '' }]
    })
  }

  const handleUpdateRule = (idx, field, value) => {
    const updated = [...rules]
    updated[idx] = { ...updated[idx], [field]: value }
    onChange({ ...config, rules: updated })
  }

  const handleRemoveRule = (idx) => {
    onChange({ ...config, rules: rules.filter((_, i) => i !== idx) })
  }

  const STATUS_OPTIONS_B1B4 = ['MATCHED', 'MISMATCH', 'NOT_FOUND', '*']
  const STATUS_OPTIONS_B1B2 = ['MATCHED', 'NOT_FOUND', '*']

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-medium text-gray-700">Quy tắc kết hợp trạng thái</h4>
          <p className="text-sm text-gray-500">Xác định trạng thái cuối cùng dựa trên kết quả matching B1-B4 và B1-B2</p>
        </div>
        <button
          onClick={handleAddRule}
          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          + Thêm rule
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border rounded-lg overflow-hidden">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-700">Status B1↔B4</th>
              {hasB2 && <th className="px-3 py-2 text-left font-medium text-gray-700">Status B1↔B2</th>}
              <th className="px-3 py-2 text-left font-medium text-gray-700">→ Final Status</th>
              <th className="px-3 py-2 w-12"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rules.map((rule, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                <td className="px-3 py-2">
                  <select
                    value={rule.b1b4}
                    onChange={(e) => handleUpdateRule(idx, 'b1b4', e.target.value)}
                    className="w-full px-2 py-1 border rounded"
                  >
                    {STATUS_OPTIONS_B1B4.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </td>
                {hasB2 && (
                  <td className="px-3 py-2">
                    <select
                      value={rule.b1b2}
                      onChange={(e) => handleUpdateRule(idx, 'b1b2', e.target.value)}
                      className="w-full px-2 py-1 border rounded"
                    >
                      {STATUS_OPTIONS_B1B2.map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                )}
                <td className="px-3 py-2">
                  <input
                    type="text"
                    value={rule.final}
                    onChange={(e) => handleUpdateRule(idx, 'final', e.target.value)}
                    className="w-full px-2 py-1 border rounded"
                    placeholder="VD: OK, REFUNDED, ERROR"
                  />
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => handleRemoveRule(idx)}
                    className="p-1 text-red-500 hover:bg-red-50 rounded"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3 bg-gray-50 p-3 rounded-lg">
        <label className="text-sm font-medium text-gray-700">Trạng thái mặc định (không khớp rule nào):</label>
        <input
          type="text"
          value={defaultStatus}
          onChange={(e) => onChange({ ...config, default: e.target.value })}
          className="px-3 py-1 border rounded w-32"
          placeholder="UNKNOWN"
        />
      </div>
    </div>
  )
}

// Report Template Editor - Supports multiple sheets
function ReportTemplateEditor({ config, onChange, reportCellMapping, onCellMappingChange }) {
  // Use sheets directly from props, no local state to avoid sync issues
  const sheets = reportCellMapping?.sheets || []
  const [activeSheetIdx, setActiveSheetIdx] = useState(0)

  // Ensure activeSheetIdx is valid when sheets change
  useEffect(() => {
    if (sheets.length > 0 && activeSheetIdx >= sheets.length) {
      setActiveSheetIdx(sheets.length - 1)
    }
  }, [sheets.length, activeSheetIdx])

  const updateSheets = (newSheets) => {
    onCellMappingChange({ ...reportCellMapping, sheets: newSheets })
  }

  const handleAddSheet = () => {
    const newSheets = [...sheets, {
      sheet_name: `Sheet${sheets.length + 1}`,
      static_cells: {},
      sql_cells: [],
      data_start_cell: null,
      data_sql: null,
      columns: []
    }]
    updateSheets(newSheets)
    setActiveSheetIdx(newSheets.length - 1)
  }

  const handleRemoveSheet = (idx) => {
    if (sheets.length <= 1) return
    const newSheets = sheets.filter((_, i) => i !== idx)
    updateSheets(newSheets)
    if (activeSheetIdx >= newSheets.length) {
      setActiveSheetIdx(newSheets.length - 1)
    }
  }

  const handleUpdateSheetName = (idx, name) => {
    const newSheets = [...sheets]
    newSheets[idx] = { ...newSheets[idx], sheet_name: name }
    updateSheets(newSheets)
  }

  const handleAddSqlCell = () => {
    if (sheets.length === 0) {
      handleAddSheet()
      return
    }
    const newSheets = [...sheets]
    const currentSheet = { ...newSheets[activeSheetIdx] }
    currentSheet.sql_cells = [...(currentSheet.sql_cells || []), { cell: '', sql: '' }]
    newSheets[activeSheetIdx] = currentSheet
    updateSheets(newSheets)
  }

  const handleUpdateSqlCell = (cellIdx, field, value) => {
    const newSheets = [...sheets]
    const currentSheet = { ...newSheets[activeSheetIdx] }
    const newSqlCells = [...(currentSheet.sql_cells || [])]
    newSqlCells[cellIdx] = { ...newSqlCells[cellIdx], [field]: value }
    currentSheet.sql_cells = newSqlCells
    newSheets[activeSheetIdx] = currentSheet
    updateSheets(newSheets)
  }

  const handleRemoveSqlCell = (cellIdx) => {
    const newSheets = [...sheets]
    const currentSheet = { ...newSheets[activeSheetIdx] }
    currentSheet.sql_cells = (currentSheet.sql_cells || []).filter((_, i) => i !== cellIdx)
    newSheets[activeSheetIdx] = currentSheet
    updateSheets(newSheets)
  }

  const handleUpdateDataTable = (field, value) => {
    if (activeSheetIdx >= sheets.length) return
    const newSheets = [...sheets]
    newSheets[activeSheetIdx] = { ...newSheets[activeSheetIdx], [field]: value }
    updateSheets(newSheets)
  }

  // Get current sheet safely
  const currentSheet = activeSheetIdx < sheets.length ? sheets[activeSheetIdx] : null

  return (
    <div className="space-y-6">
      {/* Template File Path */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Đường dẫn file template (Excel)
        </label>
        <input
          type="text"
          value={config || ''}
          onChange={(e) => onChange(e.target.value || null)}
          className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
          placeholder="VD: templates/shared/report_template.xlsx"
        />
        <p className="text-xs text-gray-500 mt-1">
          Đường dẫn tương đối từ thư mục storage/templates/. Nếu sheet không tồn tại sẽ tự động tạo mới.
        </p>
      </div>

      {/* Sheet Tabs */}
      <div className="border-t pt-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-gray-700">📊 Cấu hình các Sheet</h4>
          <button
            onClick={handleAddSheet}
            className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
          >
            + Thêm Sheet
          </button>
        </div>

        {/* Sheet tabs */}
        {sheets.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4 border-b pb-3">
            {sheets.map((sheet, idx) => (
              <div
                key={idx}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-t-lg cursor-pointer transition ${
                  activeSheetIdx === idx
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <span onClick={() => setActiveSheetIdx(idx)} className="text-sm">
                  {sheet.sheet_name || `Sheet${idx + 1}`}
                </span>
                {sheets.length > 1 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemoveSheet(idx)
                    }}
                    className={`ml-1 p-0.5 rounded hover:bg-red-500 hover:text-white ${
                      activeSheetIdx === idx ? 'text-white/70' : 'text-gray-400'
                    }`}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Current sheet config */}
        {currentSheet && (
          <div className="space-y-4">
            {/* Sheet name */}
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-gray-700">Tên Sheet:</label>
              <input
                type="text"
                value={currentSheet.sheet_name || ''}
                onChange={(e) => handleUpdateSheetName(activeSheetIdx, e.target.value)}
                className="flex-1 max-w-xs px-3 py-1.5 border rounded focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="VD: TongHop, ChiTiet, BaoCao"
              />
              <span className="text-xs text-gray-500">
                (Nếu không tồn tại trong template sẽ tạo sheet mới)
              </span>
            </div>

            {/* SQL Cells for this sheet */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h5 className="font-medium text-gray-700">Các ô tổng hợp dữ liệu (SQL)</h5>
                  <p className="text-xs text-gray-500">Điền giá trị vào ô cụ thể trong sheet này</p>
                </div>
                <button
                  onClick={handleAddSqlCell}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  + Thêm SQL Cell
                </button>
              </div>

              <div className="space-y-2">
                {(currentSheet.sql_cells || []).map((item, idx) => (
                  <div key={idx} className="bg-white p-3 rounded border flex items-start gap-3">
                    <div className="w-20">
                      <label className="text-xs text-gray-500">Ô Excel</label>
                      <input
                        type="text"
                        value={item.cell}
                        onChange={(e) => handleUpdateSqlCell(idx, 'cell', e.target.value.toUpperCase())}
                        className="w-full px-2 py-1 border rounded text-sm font-mono mt-1"
                        placeholder="C10"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-xs text-gray-500">Câu SQL</label>
                      <textarea
                        value={item.sql}
                        onChange={(e) => handleUpdateSqlCell(idx, 'sql', e.target.value)}
                        className="w-full px-2 py-1 border rounded text-sm font-mono mt-1 h-14"
                        placeholder="SELECT COUNT(*) FROM a1_result WHERE final_status = 'OK'"
                      />
                    </div>
                    <button
                      onClick={() => handleRemoveSqlCell(idx)}
                      className="p-1 text-red-500 hover:bg-red-50 rounded mt-4"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                {(currentSheet.sql_cells || []).length === 0 && (
                  <div className="text-center py-3 text-gray-400 text-sm">
                    Chưa có SQL cell nào cho sheet này
                  </div>
                )}
              </div>
            </div>

            {/* Data Table config (optional) */}
            <div className="bg-yellow-50 p-4 rounded-lg">
              <h5 className="font-medium text-gray-700 mb-3">📋 Bảng dữ liệu (tùy chọn)</h5>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-600">Ô bắt đầu bảng</label>
                  <input
                    type="text"
                    value={currentSheet.data_start_cell || ''}
                    onChange={(e) => handleUpdateDataTable('data_start_cell', e.target.value.toUpperCase() || null)}
                    className="w-full px-2 py-1 border rounded text-sm font-mono mt-1"
                    placeholder="VD: A5"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-600">Các cột (cách nhau bởi dấu phẩy)</label>
                  <input
                    type="text"
                    value={(currentSheet.columns || []).join(', ')}
                    onChange={(e) => handleUpdateDataTable('columns', e.target.value.split(',').map(c => c.trim()).filter(c => c))}
                    className="w-full px-2 py-1 border rounded text-sm font-mono mt-1"
                    placeholder="VD: A, B, C, D, E"
                  />
                </div>
              </div>
              <div className="mt-3">
                <label className="text-xs text-gray-600">SQL lấy dữ liệu bảng</label>
                <textarea
                  value={currentSheet.data_sql || ''}
                  onChange={(e) => handleUpdateDataTable('data_sql', e.target.value || null)}
                  className="w-full px-2 py-1 border rounded text-sm font-mono mt-1 h-16"
                  placeholder="VD: SELECT txn_id, amount, status FROM a1_result ORDER BY txn_date"
                />
              </div>
            </div>
          </div>
        )}

        {sheets.length === 0 && (
          <div className="text-center py-8 bg-gray-100 rounded-lg">
            <p className="text-gray-500 mb-2">Chưa có sheet nào được cấu hình</p>
            <button
              onClick={handleAddSheet}
              className="text-blue-600 hover:underline"
            >
              + Thêm sheet đầu tiên
            </button>
          </div>
        )}

        {/* Example SQL templates */}
        <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm">
          <p className="font-medium text-blue-800 mb-2">Ví dụ câu SQL tổng hợp:</p>
          <ul className="text-blue-700 space-y-1 text-xs font-mono">
            <li>• SELECT COUNT(*) FROM a1_result WHERE final_status = 'OK'</li>
            <li>• SELECT SUM(amount) FROM a1_result WHERE final_status = 'MATCHED'</li>
            <li>• SELECT COUNT(*) FROM a2_result WHERE status = 'NOT_FOUND'</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Matching Rules Editor - Rewritten from scratch for stability
// ============================================================================
function MatchingRulesEditor({ 
  config, 
  onChange, 
  leftColumns = [], 
  rightColumns = [], 
  leftLabel = "B1 (Sao kê)", 
  rightLabel = "B4 (Hệ thống)",
  leftPrefix = "b1",
  rightPrefix = "b4",
  title = "Quy tắc Matching"
}) {
  // Safe getter with defaults
  const safeArray = (val) => Array.isArray(val) ? val : []
  const safeObj = (val) => (val && typeof val === 'object' && !Array.isArray(val)) ? val : {}
  
  // Extract config with safe defaults
  const keyMatchConfig = safeObj(config?.key_match)
  const amountMatchConfig = safeObj(config?.amount_match)
  const statusLogic = config?.status_logic || { all_match: 'MATCHED', key_match_amount_mismatch: 'MISMATCH', no_key_match: 'NOT_FOUND' }
  const expressionMode = config?.expression_mode || 'simple'
  const keyExpression = config?.key_expression || ''
  const amountExpression = config?.amount_expression || ''

  // Local state
  const [showAdvanced, setShowAdvanced] = useState({})
  const [textInputs, setTextInputs] = useState({})
  const [isExpressionMode, setIsExpressionMode] = useState(expressionMode === 'advanced')

  const SIMPLE_TRANSFORMS = [
    { id: 'strip', label: 'Trim khoảng trắng' },
    { id: 'upper', label: 'Viết HOA' },
    { id: 'lower', label: 'Viết thường' },
    { id: 'trim_zero', label: 'Bỏ số 0 đầu' },
  ]

  // Get parts for a side safely
  const getParts = (matchType, side) => {
    const matchConfig = matchType === 'key' ? keyMatchConfig : amountMatchConfig
    const sideConfig = safeObj(matchConfig[side])
    return safeArray(sideConfig.parts)
  }

  // Get transforms for a side safely
  const getTransforms = (matchType, side) => {
    const matchConfig = matchType === 'key' ? keyMatchConfig : amountMatchConfig
    const sideConfig = safeObj(matchConfig[side])
    return safeArray(sideConfig.transforms)
  }

  // Update entire config
  const updateConfig = (updates) => {
    onChange({ ...config, ...updates })
  }

  // Update a match config
  const updateMatch = (matchType, updates) => {
    const matchKey = matchType === 'key' ? 'key_match' : 'amount_match'
    const currentMatch = matchType === 'key' ? keyMatchConfig : amountMatchConfig
    updateConfig({ [matchKey]: { ...currentMatch, ...updates } })
  }

  // Update a side of a match config
  const updateSide = (matchType, side, updates) => {
    const matchConfig = matchType === 'key' ? keyMatchConfig : amountMatchConfig
    const currentSide = safeObj(matchConfig[side])
    updateMatch(matchType, { [side]: { ...currentSide, ...updates } })
  }

  // Add a part (column or text)
  const addPart = (matchType, side, type, value) => {
    if (!value) return
    const parts = getParts(matchType, side)
    updateSide(matchType, side, { parts: [...parts, { type, value }] })
  }

  // Remove a part
  const removePart = (matchType, side, index) => {
    const parts = getParts(matchType, side)
    updateSide(matchType, side, { parts: parts.filter((_, i) => i !== index) })
  }

  // Move a part
  const movePart = (matchType, side, index, direction) => {
    const parts = [...getParts(matchType, side)]
    const newIndex = direction === 'up' ? index - 1 : index + 1
    if (newIndex < 0 || newIndex >= parts.length) return
    ;[parts[index], parts[newIndex]] = [parts[newIndex], parts[index]]
    updateSide(matchType, side, { parts })
  }

  // Toggle transform
  const toggleTransform = (matchType, side, transformId) => {
    const transforms = getTransforms(matchType, side)
    const newTransforms = transforms.includes(transformId)
      ? transforms.filter(t => t !== transformId)
      : [...transforms, transformId]
    updateSide(matchType, side, { transforms: newTransforms })
  }

  // Text input helpers
  const getTextInput = (key) => textInputs[key] || ''
  const setTextInput = (key, value) => setTextInputs(prev => ({ ...prev, [key]: value }))

  // Get advanced config for a side
  const getAdvancedConfig = (matchType, side) => {
    const matchConfig = matchType === 'key' ? keyMatchConfig : amountMatchConfig
    return safeObj(matchConfig[side])
  }

  // Generate expression preview with advanced config support
  const generateExprFromSide = (matchType, side, prefix) => {
    const parts = getParts(matchType, side)
    const transforms = getTransforms(matchType, side)
    const advConfig = getAdvancedConfig(matchType, side)
    
    if (!parts || parts.length === 0) return ''
    
    // Build parts expression
    const partsExpr = parts.map(p => {
      if (!p || !p.value) return "''"
      if (p.type === 'text') return `'${p.value}'`
      return `${prefix}['${p.value}'].astype(str)`
    }).join(' + ')
    
    let expr = parts.length > 1 ? `(${partsExpr})` : partsExpr
    
    // Apply basic transforms
    safeArray(transforms).forEach(t => {
      if (t === 'strip') expr = `${expr}.str.strip()`
      if (t === 'upper') expr = `${expr}.str.upper()`
      if (t === 'lower') expr = `${expr}.str.lower()`
      if (t === 'trim_zero') expr = `${expr}.str.lstrip('0')`
    })
    
    // Apply advanced config: substring
    if (advConfig.substring_start != null || advConfig.substring_end != null) {
      const start = advConfig.substring_start ?? ''
      const end = advConfig.substring_end ?? ''
      expr = `${expr}.str[${start}:${end}]`
    }
    
    // Apply advanced config: regex extract
    if (advConfig.regex_pattern) {
      expr = `${expr}.str.extract(r'${advConfig.regex_pattern}', expand=False)`
    }
    
    // Apply advanced config: replace
    if (advConfig.replace_pattern) {
      const replaceWith = advConfig.replace_with || ''
      expr = `${expr}.str.replace(r'${advConfig.replace_pattern}', '${replaceWith}', regex=True)`
    }
    
    return expr
  }

  const generateKeyExpression = () => {
    const leftParts = getParts('key', 'left')
    const rightParts = getParts('key', 'right')
    if (leftParts.length === 0 || rightParts.length === 0) return ''
    const leftExpr = generateExprFromSide('key', 'left', leftPrefix)
    const rightExpr = generateExprFromSide('key', 'right', rightPrefix)
    return `${leftExpr} == ${rightExpr}`
  }

  const generateAmountExpression = () => {
    const leftParts = getParts('amount', 'left')
    const rightParts = getParts('amount', 'right')
    const leftCol = leftParts.find(p => p && p.type === 'column')
    const rightCol = rightParts.find(p => p && p.type === 'column')
    if (!leftCol || !rightCol) return ''
    const tolerance = amountMatchConfig.tolerance ?? 0
    const leftTransforms = getTransforms('amount', 'left')
    const rightTransforms = getTransforms('amount', 'right')
    const advLeft = getAdvancedConfig('amount', 'left')
    const advRight = getAdvancedConfig('amount', 'right')
    
    // Build amount expressions - PIPELINE ORDER:
    // 1. Base column
    // 2. Basic transforms (strip, upper, lower, trim_zero)
    // 3. Advanced transforms (substring, regex, replace)
    // 4. Number normalization (final step before comparison)
    
    let leftExpr = `${leftPrefix}['${leftCol.value}']`
    let rightExpr = `${rightPrefix}['${rightCol.value}']`
    
    // STEP 1: Apply basic transforms (strip, upper, lower, trim_zero)
    leftTransforms.forEach(t => {
      if (t === 'strip') leftExpr = `${leftExpr}.str.strip()`
      if (t === 'upper') leftExpr = `${leftExpr}.str.upper()`
      if (t === 'lower') leftExpr = `${leftExpr}.str.lower()`
      if (t === 'trim_zero') leftExpr = `${leftExpr}.str.lstrip('0')`
    })
    
    rightTransforms.forEach(t => {
      if (t === 'strip') rightExpr = `${rightExpr}.str.strip()`
      if (t === 'upper') rightExpr = `${rightExpr}.str.upper()`
      if (t === 'lower') rightExpr = `${rightExpr}.str.lower()`
      if (t === 'trim_zero') rightExpr = `${rightExpr}.str.lstrip('0')`
    })
    
    // STEP 2: Apply advanced transforms (substring)
    if (advLeft.substring_start != null || advLeft.substring_end != null) {
      const start = advLeft.substring_start ?? ''
      const end = advLeft.substring_end ?? ''
      leftExpr = `${leftExpr}.str[${start}:${end}]`
    }
    if (advRight.substring_start != null || advRight.substring_end != null) {
      const start = advRight.substring_start ?? ''
      const end = advRight.substring_end ?? ''
      rightExpr = `${rightExpr}.str[${start}:${end}]`
    }
    
    // STEP 3: Apply regex extraction (if specified)
    if (advLeft.regex_pattern) {
      leftExpr = `${leftExpr}.str.extract(r'${advLeft.regex_pattern}', expand=False)`
    }
    if (advRight.regex_pattern) {
      rightExpr = `${rightExpr}.str.extract(r'${advRight.regex_pattern}', expand=False)`
    }
    
    // STEP 4: Apply replace (if specified)
    if (advLeft.replace_pattern) {
      const replaceWith = advLeft.replace_with || ''
      leftExpr = `${leftExpr}.str.replace(r'${advLeft.replace_pattern}', '${replaceWith}', regex=True)`
    }
    if (advRight.replace_pattern) {
      const replaceWith = advRight.replace_with || ''
      rightExpr = `${rightExpr}.str.replace(r'${advRight.replace_pattern}', '${replaceWith}', regex=True)`
    }
    
    // STEP 5: Number normalization - FINAL STEP (convert to float)
    if (advLeft.numberTransform?.enabled) {
      // Use ?? to preserve empty string (means "no separator")
      const ts = advLeft.numberTransform.thousandSeparator ?? ''
      const ds = advLeft.numberTransform.decimalSeparator ?? ''
      leftExpr = `normalize_number(${leftExpr}, '${ts}', '${ds}')`
    } else {
      leftExpr = `${leftExpr}.astype(float)`
    }
    
    if (advRight.numberTransform?.enabled) {
      // Use ?? to preserve empty string (means "no separator")
      const ts = advRight.numberTransform.thousandSeparator ?? ''
      const ds = advRight.numberTransform.decimalSeparator ?? ''
      rightExpr = `normalize_number(${rightExpr}, '${ts}', '${ds}')`
    } else {
      rightExpr = `${rightExpr}.astype(float)`
    }
    
    // Build comparison
    if (tolerance === 0) {
      return `${leftExpr} == ${rightExpr}`
    }
    
    if (amountMatchConfig.tolerance_type === 'percent') {
      return `abs(${leftExpr} - ${rightExpr}) <= ${leftExpr} * ${tolerance / 100}`
    }
    return `abs(${leftExpr} - ${rightExpr}) <= ${tolerance}`
  }

  // Render one side panel
  const renderSidePanel = (matchType, side, label, columns) => {
    const inputKey = `${matchType}_${side}`
    const advancedKey = `${matchType}_${side}`
    const parts = getParts(matchType, side)
    const transforms = getTransforms(matchType, side)
    const matchConfig = matchType === 'key' ? keyMatchConfig : amountMatchConfig
    const sideConfig = safeObj(matchConfig[side])
    const textValue = getTextInput(inputKey)
    const safeColumns = safeArray(columns)

    return (
      <div className="bg-white p-3 rounded-lg border">
        <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
        
        {/* Parts list */}
        <div className="mb-2 space-y-1 min-h-[40px]">
          {parts.length === 0 && (
            <div className="text-gray-400 text-xs italic py-1">Chưa có thành phần nào</div>
          )}
          {parts.map((part, idx) => {
            if (!part) return null
            const pType = part.type || 'column'
            const pValue = part.value || ''
            return (
              <div key={idx} className="flex items-center gap-1 bg-gray-50 p-1 rounded text-xs">
                <span className="text-gray-400 w-4 text-center">{idx + 1}</span>
                {pType === 'column' ? (
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded font-mono flex-1 truncate">{pValue}</span>
                ) : (
                  <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded font-mono flex-1 truncate">'{pValue}'</span>
                )}
                <button type="button" onClick={() => movePart(matchType, side, idx, 'up')} disabled={idx === 0}
                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30">↑</button>
                <button type="button" onClick={() => movePart(matchType, side, idx, 'down')} disabled={idx === parts.length - 1}
                  className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30">↓</button>
                <button type="button" onClick={() => removePart(matchType, side, idx)}
                  className="p-0.5 text-red-400 hover:text-red-600">×</button>
              </div>
            )
          })}
        </div>

        {/* Add column */}
        <div className="flex gap-1 mb-1">
          <select
            value=""
            onChange={(e) => { if (e.target.value) addPart(matchType, side, 'column', e.target.value) }}
            className="flex-1 px-2 py-1 border rounded text-xs"
          >
            <option value="">+ Thêm cột...</option>
            {safeColumns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </div>

        {/* Add text */}
        <div className="flex gap-1 mb-2">
          <input
            type="text"
            value={textValue}
            onChange={(e) => setTextInput(inputKey, e.target.value)}
            className="flex-1 px-2 py-1 border rounded text-xs font-mono"
            placeholder="Nhập text tĩnh (VD: BXL, -, &)"
          />
          <button
            type="button"
            onClick={() => { if (textValue) { addPart(matchType, side, 'text', textValue); setTextInput(inputKey, '') } }}
            className="px-2 py-1 text-xs bg-amber-500 text-white rounded hover:bg-amber-600"
          >
            + Text
          </button>
        </div>

        {/* Preview */}
        {parts.length > 0 && (
          <div className="text-xs bg-gray-100 p-1.5 rounded mb-2 font-mono text-gray-600 break-all">
            <span className="text-gray-400">Preview: </span>
            {parts.map((p, i) => {
              if (!p) return null
              return (
                <span key={i}>
                  {i > 0 && <span className="text-purple-500"> || </span>}
                  {p.type === 'column' ? (
                    <span className="text-blue-600">[{p.value}]</span>
                  ) : (
                    <span className="text-amber-600">'{p.value}'</span>
                  )}
                </span>
              )
            })}
          </div>
        )}

        {/* Transforms */}
        <div className="flex flex-wrap gap-2 mb-2">
          {SIMPLE_TRANSFORMS.map(t => (
            <label key={t.id} className="flex items-center gap-1 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={transforms.includes(t.id)}
                onChange={() => toggleTransform(matchType, side, t.id)}
                className="w-3 h-3"
              />
              {t.label}
            </label>
          ))}
        </div>

        {/* Advanced toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(prev => ({ ...prev, [advancedKey]: !prev[advancedKey] }))}
          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          {showAdvanced[advancedKey] ? '▼' : '▶'} Cấu hình nâng cao
        </button>

        {showAdvanced[advancedKey] && (
          <div className="mt-2 p-2 bg-gray-50 rounded border text-xs space-y-2">
            <div className="flex items-center gap-2">
              <label className="w-20 text-gray-600">Substring:</label>
              <input type="number" value={sideConfig.substring_start ?? ''} 
                onChange={(e) => updateSide(matchType, side, { substring_start: e.target.value === '' ? null : parseInt(e.target.value) })}
                className="w-16 px-2 py-0.5 border rounded text-center" placeholder="start" />
              <span>→</span>
              <input type="number" value={sideConfig.substring_end ?? ''} 
                onChange={(e) => updateSide(matchType, side, { substring_end: e.target.value === '' ? null : parseInt(e.target.value) })}
                className="w-16 px-2 py-0.5 border rounded text-center" placeholder="end" />
            </div>
            <div className="flex items-center gap-2">
              <label className="w-20 text-gray-600">Regex:</label>
              <input type="text" value={sideConfig.regex_pattern || ''} 
                onChange={(e) => updateSide(matchType, side, { regex_pattern: e.target.value || null })}
                className="flex-1 px-2 py-0.5 border rounded font-mono" placeholder="VD: (\d{10,15})" />
            </div>
            <div className="flex items-center gap-2">
              <label className="w-20 text-gray-600">Replace:</label>
              <input type="text" value={sideConfig.replace_pattern || ''} 
                onChange={(e) => updateSide(matchType, side, { replace_pattern: e.target.value || null })}
                className="w-24 px-2 py-0.5 border rounded font-mono" placeholder="pattern" />
              <span>→</span>
              <input type="text" value={sideConfig.replace_with || ''} 
                onChange={(e) => updateSide(matchType, side, { replace_with: e.target.value || null })}
                className="w-24 px-2 py-0.5 border rounded font-mono" placeholder="với" />
            </div>
            
            {/* Number Transform Section - IN Advanced section (after text transforms) */}
            {matchType === 'amount' && (
              <div className="pt-2 border-t mt-2">
                <div className="flex items-center gap-2 mb-2">
                  <input
                    type="checkbox"
                    id={`${advancedKey}-number-transform`}
                    checked={sideConfig.numberTransform?.enabled || false}
                    onChange={(e) => {
                      if (e.target.checked) {
                        updateSide(matchType, side, {
                          numberTransform: {
                            enabled: true,
                            thousandSeparator: ',',
                            decimalSeparator: '.'
                          }
                        })
                      } else {
                        updateSide(matchType, side, { numberTransform: null })
                      }
                    }}
                    className="w-3 h-3"
                  />
                  <label htmlFor={`${advancedKey}-number-transform`} className="font-medium text-gray-700 cursor-pointer">
                    🔢 Transform số (chuẩn hóa format)
                  </label>
                </div>

                {sideConfig.numberTransform?.enabled && (() => {
                  // Calculate display values for dropdowns
                  // Use ?? to preserve empty string '', only fallback for null/undefined
                  const thousandSep = sideConfig.numberTransform.thousandSeparator
                  const decimalSep = sideConfig.numberTransform.decimalSeparator
                  
                  // '' means "none", null/undefined means use default
                  const thousandDisplay = thousandSep === '' ? 'none' : (thousandSep ?? ',')
                  const decimalDisplay = decimalSep === '' ? 'none' : (decimalSep ?? '.')
                  
                  return (
                  <div className="ml-5 p-2 bg-blue-50 rounded border border-blue-200 space-y-2">
                    <div className="flex items-center gap-2">
                      <label className="text-gray-600 w-28">Dấu ngăn nghìn:</label>
                      <select
                        value={thousandDisplay}
                        onChange={(e) => {
                          const newVal = e.target.value === 'none' ? '' : e.target.value
                          updateSide(matchType, side, {
                            numberTransform: { 
                              enabled: true,
                              thousandSeparator: newVal,
                              decimalSeparator: decimalSep ?? '.'  // Use ?? to preserve empty string
                            }
                          })
                        }}
                        className="px-2 py-0.5 border rounded"
                      >
                        <option value=",">Dấu phẩy (,) - VD: 1,000</option>
                        <option value=".">Dấu chấm (.) - VD: 1.000</option>
                        <option value="none">Không có</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-gray-600 w-28">Dấu thập phân:</label>
                      <select
                        value={decimalDisplay}
                        onChange={(e) => {
                          const newVal = e.target.value === 'none' ? '' : e.target.value
                          updateSide(matchType, side, {
                            numberTransform: { 
                              enabled: true,
                              thousandSeparator: thousandSep ?? ',',  // Use ?? to preserve empty string
                              decimalSeparator: newVal
                            }
                          })
                        }}
                        className="px-2 py-0.5 border rounded"
                      >
                        <option value=".">Dấu chấm (.) - VD: 10.50</option>
                        <option value=",">Dấu phẩy (,) - VD: 10,50</option>
                        <option value="none">Không có (số nguyên)</option>
                      </select>
                    </div>
                    <div className="text-blue-700 bg-blue-100 p-1 rounded text-xs">
                      Ví dụ: "20,000" → 20000 | "1.000,50" → 1000.50
                    </div>
                  </div>
                  )
                })()}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-800 text-lg">{title}</h3>
        <div className="flex items-center gap-1">
          <span className="text-sm text-gray-600 mr-2">Chế độ:</span>
          <button type="button"
            onClick={() => { setIsExpressionMode(false); updateConfig({ expression_mode: 'simple' }) }}
            className={`px-3 py-1 text-sm rounded-l border ${!isExpressionMode ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'}`}
          >Cơ bản</button>
          <button type="button"
            onClick={() => { setIsExpressionMode(true); updateConfig({ expression_mode: 'advanced' }) }}
            className={`px-3 py-1 text-sm rounded-r border-t border-r border-b ${isExpressionMode ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-gray-700 border-gray-300'}`}
          >🧑‍💻 Expression</button>
        </div>
      </div>

      {/* EXPRESSION MODE */}
      {isExpressionMode && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 space-y-4">
          <div className="text-sm text-purple-700">
            <strong>Chế độ Expression:</strong> Viết trực tiếp biểu thức Pandas để so khớp.
          </div>
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium text-gray-700">🔑 Key Match Expression</label>
              <button type="button" onClick={() => updateConfig({ key_expression: generateKeyExpression() })}
                className="text-xs text-purple-600 hover:underline">Tạo từ UI</button>
            </div>
            <textarea value={keyExpression} onChange={(e) => updateConfig({ key_expression: e.target.value })}
              className="w-full px-3 py-2 border rounded font-mono text-sm h-20" placeholder="VD: left['txn_id'] == right['ref']" />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium text-gray-700">💰 Amount Match Expression</label>
              <button type="button" onClick={() => updateConfig({ amount_expression: generateAmountExpression() })}
                className="text-xs text-purple-600 hover:underline">Tạo từ UI</button>
            </div>
            <textarea value={amountExpression} onChange={(e) => updateConfig({ amount_expression: e.target.value })}
              className="w-full px-3 py-2 border rounded font-mono text-sm h-20" placeholder="VD: abs(left['amount'] - right['amount']) <= 0.01" />
          </div>
        </div>
      )}

      {/* SIMPLE MODE */}
      {!isExpressionMode && (
        <>
          {/* KEY MATCH */}
          <div className="border rounded-lg p-4 bg-blue-50">
            <h4 className="font-medium text-blue-800 mb-4">🔑 Key Match (So khớp mã giao dịch)</h4>
            <p className="text-xs text-blue-600 mb-3">Chọn cột hoặc thêm text để ghép thành key.</p>
            <div className="grid grid-cols-2 gap-4">
              {renderSidePanel('key', 'left', `📄 ${leftLabel}`, leftColumns)}
              {renderSidePanel('key', 'right', `🗄️ ${rightLabel}`, rightColumns)}
            </div>
            <div className="mt-3">
              <label className="text-sm text-gray-600">Kiểu so sánh:</label>
              <select value={keyMatchConfig.compare_type || 'exact'}
                onChange={(e) => updateMatch('key', { compare_type: e.target.value })}
                className="ml-2 px-3 py-1 border rounded">
                <option value="exact">Chính xác (=)</option>
                <option value="like">Chứa (LIKE)</option>
                <option value="fuzzy">Gần đúng (Fuzzy)</option>
              </select>
            </div>
          </div>

          {/* AMOUNT MATCH - Simplified: only single column selection */}
          <div className="border rounded-lg p-4 bg-green-50">
            <h4 className="font-medium text-green-800 mb-4">💰 Amount Match (So khớp số tiền)</h4>
            <div className="grid grid-cols-2 gap-4">
              {/* Left side - simple column select */}
              <div className="bg-white p-3 rounded-lg border">
                <label className="block text-sm font-medium text-gray-700 mb-2">📄 {leftLabel}</label>
                <select
                  value={(amountMatchConfig.left?.parts?.[0]?.type === 'column' ? amountMatchConfig.left?.parts?.[0]?.value : '') || ''}
                  onChange={(e) => {
                    const newParts = e.target.value ? [{ type: 'column', value: e.target.value }] : []
                    updateSide('amount', 'left', { parts: newParts })
                  }}
                  className="w-full px-3 py-2 border rounded"
                >
                  <option value="">-- Chọn cột số tiền --</option>
                  {leftColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                
                {/* Basic Transforms */}
                <div className="flex flex-wrap gap-2 mt-2 mb-2">
                  {SIMPLE_TRANSFORMS.map(t => (
                    <label key={t.id} className="flex items-center gap-1 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(amountMatchConfig.left?.transforms || []).includes(t.id)}
                        onChange={() => toggleTransform('amount', 'left', t.id)}
                        className="w-3 h-3"
                      />
                      {t.label}
                    </label>
                  ))}
                </div>

                {/* Advanced options toggle */}
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(prev => ({ ...prev, ['amount_left']: !prev['amount_left'] }))}
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                  >
                    <span>{showAdvanced['amount_left'] ? '▼' : '▶'}</span>
                    <span>Cấu hình nâng cao</span>
                  </button>
                  
                  {showAdvanced['amount_left'] && (
                    <div className="mt-2 p-2 bg-gray-50 rounded border text-xs space-y-2">
                      {/* Substring */}
                      <div className="flex items-center gap-2">
                        <label className="w-20 text-gray-600">Substring:</label>
                        <input type="number" value={amountMatchConfig.left?.substring_start ?? ''} 
                          onChange={(e) => updateSide('amount', 'left', { substring_start: e.target.value === '' ? null : parseInt(e.target.value) })}
                          className="w-16 px-2 py-0.5 border rounded text-center" placeholder="start" />
                        <span>→</span>
                        <input type="number" value={amountMatchConfig.left?.substring_end ?? ''} 
                          onChange={(e) => updateSide('amount', 'left', { substring_end: e.target.value === '' ? null : parseInt(e.target.value) })}
                          className="w-16 px-2 py-0.5 border rounded text-center" placeholder="end" />
                      </div>
                      {/* Regex */}
                      <div className="flex items-center gap-2">
                        <label className="w-20 text-gray-600">Regex:</label>
                        <input type="text" value={amountMatchConfig.left?.regex_pattern || ''} 
                          onChange={(e) => updateSide('amount', 'left', { regex_pattern: e.target.value || null })}
                          className="flex-1 px-2 py-0.5 border rounded font-mono" placeholder="VD: (\d+)" />
                      </div>
                      {/* Replace */}
                      <div className="flex items-center gap-2">
                        <label className="w-20 text-gray-600">Replace:</label>
                        <input type="text" value={amountMatchConfig.left?.replace_pattern || ''} 
                          onChange={(e) => updateSide('amount', 'left', { replace_pattern: e.target.value || null })}
                          className="w-24 px-2 py-0.5 border rounded font-mono" placeholder="pattern" />
                        <span>→</span>
                        <input type="text" value={amountMatchConfig.left?.replace_with || ''} 
                          onChange={(e) => updateSide('amount', 'left', { replace_with: e.target.value || null })}
                          className="w-24 px-2 py-0.5 border rounded font-mono" placeholder="với" />
                      </div>
                      
                      {/* Number Transform */}
                      <div className="pt-2 border-t mt-2">
                        <div className="flex items-center gap-2 mb-2">
                          <input
                            type="checkbox"
                            id="amount-left-number-transform"
                            checked={amountMatchConfig.left?.numberTransform?.enabled || false}
                            onChange={(e) => {
                              if (e.target.checked) {
                                updateSide('amount', 'left', {
                                  numberTransform: { enabled: true, thousandSeparator: ',', decimalSeparator: '.' }
                                })
                              } else {
                                updateSide('amount', 'left', { numberTransform: null })
                              }
                            }}
                            className="w-3 h-3"
                          />
                          <label htmlFor="amount-left-number-transform" className="font-medium text-gray-700 cursor-pointer">
                            🔢 Transform số (chuẩn hóa format)
                          </label>
                        </div>
                        
                        {amountMatchConfig.left?.numberTransform?.enabled && (() => {
                          const nt = amountMatchConfig.left.numberTransform
                          const tsDisplay = nt.thousandSeparator === '' ? 'none' : (nt.thousandSeparator ?? ',')
                          const dsDisplay = nt.decimalSeparator === '' ? 'none' : (nt.decimalSeparator ?? '.')
                          return (
                            <div className="ml-5 p-2 bg-blue-50 rounded border border-blue-200 space-y-1">
                              <div className="flex items-center gap-2">
                                <label className="text-gray-600 w-24">Ngăn nghìn:</label>
                                <select value={tsDisplay} onChange={(e) => {
                                  const val = e.target.value === 'none' ? '' : e.target.value
                                  updateSide('amount', 'left', {
                                    numberTransform: { ...nt, thousandSeparator: val }
                                  })
                                }} className="px-2 py-0.5 border rounded">
                                  <option value=",">Dấu phẩy (,)</option>
                                  <option value=".">Dấu chấm (.)</option>
                                  <option value="none">Không có</option>
                                </select>
                              </div>
                              <div className="flex items-center gap-2">
                                <label className="text-gray-600 w-24">Thập phân:</label>
                                <select value={dsDisplay} onChange={(e) => {
                                  const val = e.target.value === 'none' ? '' : e.target.value
                                  updateSide('amount', 'left', {
                                    numberTransform: { ...nt, decimalSeparator: val }
                                  })
                                }} className="px-2 py-0.5 border rounded">
                                  <option value=".">Dấu chấm (.)</option>
                                  <option value=",">Dấu phẩy (,)</option>
                                  <option value="none">Không có</option>
                                </select>
                              </div>
                            </div>
                          )
                        })()}
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              {/* Right side - simple column select */}
              <div className="bg-white p-3 rounded-lg border">
                <label className="block text-sm font-medium text-gray-700 mb-2">🗄️ {rightLabel}</label>
                <select
                  value={(amountMatchConfig.right?.parts?.[0]?.type === 'column' ? amountMatchConfig.right?.parts?.[0]?.value : '') || ''}
                  onChange={(e) => {
                    const newParts = e.target.value ? [{ type: 'column', value: e.target.value }] : []
                    updateSide('amount', 'right', { parts: newParts })
                  }}
                  className="w-full px-3 py-2 border rounded"
                >
                  <option value="">-- Chọn cột số tiền --</option>
                  {rightColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                
                {/* Basic Transforms */}
                <div className="flex flex-wrap gap-2 mt-2 mb-2">
                  {SIMPLE_TRANSFORMS.map(t => (
                    <label key={t.id} className="flex items-center gap-1 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(amountMatchConfig.right?.transforms || []).includes(t.id)}
                        onChange={() => toggleTransform('amount', 'right', t.id)}
                        className="w-3 h-3"
                      />
                      {t.label}
                    </label>
                  ))}
                </div>

                {/* Advanced options toggle */}
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(prev => ({ ...prev, ['amount_right']: !prev['amount_right'] }))}
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                  >
                    <span>{showAdvanced['amount_right'] ? '▼' : '▶'}</span>
                    <span>Cấu hình nâng cao</span>
                  </button>
                  
                  {showAdvanced['amount_right'] && (
                    <div className="mt-2 p-2 bg-gray-50 rounded border text-xs space-y-2">
                      {/* Substring */}
                      <div className="flex items-center gap-2">
                        <label className="w-20 text-gray-600">Substring:</label>
                        <input type="number" value={amountMatchConfig.right?.substring_start ?? ''} 
                          onChange={(e) => updateSide('amount', 'right', { substring_start: e.target.value === '' ? null : parseInt(e.target.value) })}
                          className="w-16 px-2 py-0.5 border rounded text-center" placeholder="start" />
                        <span>→</span>
                        <input type="number" value={amountMatchConfig.right?.substring_end ?? ''} 
                          onChange={(e) => updateSide('amount', 'right', { substring_end: e.target.value === '' ? null : parseInt(e.target.value) })}
                          className="w-16 px-2 py-0.5 border rounded text-center" placeholder="end" />
                      </div>
                      {/* Regex */}
                      <div className="flex items-center gap-2">
                        <label className="w-20 text-gray-600">Regex:</label>
                        <input type="text" value={amountMatchConfig.right?.regex_pattern || ''} 
                          onChange={(e) => updateSide('amount', 'right', { regex_pattern: e.target.value || null })}
                          className="flex-1 px-2 py-0.5 border rounded font-mono" placeholder="VD: (\d+)" />
                      </div>
                      {/* Replace */}
                      <div className="flex items-center gap-2">
                        <label className="w-20 text-gray-600">Replace:</label>
                        <input type="text" value={amountMatchConfig.right?.replace_pattern || ''} 
                          onChange={(e) => updateSide('amount', 'right', { replace_pattern: e.target.value || null })}
                          className="w-24 px-2 py-0.5 border rounded font-mono" placeholder="pattern" />
                        <span>→</span>
                        <input type="text" value={amountMatchConfig.right?.replace_with || ''} 
                          onChange={(e) => updateSide('amount', 'right', { replace_with: e.target.value || null })}
                          className="w-24 px-2 py-0.5 border rounded font-mono" placeholder="với" />
                      </div>
                      
                      {/* Number Transform */}
                      <div className="pt-2 border-t mt-2">
                        <div className="flex items-center gap-2 mb-2">
                          <input
                            type="checkbox"
                            id="amount-right-number-transform"
                            checked={amountMatchConfig.right?.numberTransform?.enabled || false}
                            onChange={(e) => {
                              if (e.target.checked) {
                                updateSide('amount', 'right', {
                                  numberTransform: { enabled: true, thousandSeparator: ',', decimalSeparator: '.' }
                                })
                              } else {
                                updateSide('amount', 'right', { numberTransform: null })
                              }
                            }}
                            className="w-3 h-3"
                          />
                          <label htmlFor="amount-right-number-transform" className="font-medium text-gray-700 cursor-pointer">
                            🔢 Transform số (chuẩn hóa format)
                          </label>
                        </div>
                        
                        {amountMatchConfig.right?.numberTransform?.enabled && (() => {
                          const nt = amountMatchConfig.right.numberTransform
                          const tsDisplay = nt.thousandSeparator === '' ? 'none' : (nt.thousandSeparator ?? ',')
                          const dsDisplay = nt.decimalSeparator === '' ? 'none' : (nt.decimalSeparator ?? '.')
                          return (
                            <div className="ml-5 p-2 bg-blue-50 rounded border border-blue-200 space-y-1">
                              <div className="flex items-center gap-2">
                                <label className="text-gray-600 w-24">Ngăn nghìn:</label>
                                <select value={tsDisplay} onChange={(e) => {
                                  const val = e.target.value === 'none' ? '' : e.target.value
                                  updateSide('amount', 'right', {
                                    numberTransform: { ...nt, thousandSeparator: val }
                                  })
                                }} className="px-2 py-0.5 border rounded">
                                  <option value=",">Dấu phẩy (,)</option>
                                  <option value=".">Dấu chấm (.)</option>
                                  <option value="none">Không có</option>
                                </select>
                              </div>
                              <div className="flex items-center gap-2">
                                <label className="text-gray-600 w-24">Thập phân:</label>
                                <select value={dsDisplay} onChange={(e) => {
                                  const val = e.target.value === 'none' ? '' : e.target.value
                                  updateSide('amount', 'right', {
                                    numberTransform: { ...nt, decimalSeparator: val }
                                  })
                                }} className="px-2 py-0.5 border rounded">
                                  <option value=".">Dấu chấm (.)</option>
                                  <option value=",">Dấu phẩy (,)</option>
                                  <option value="none">Không có</option>
                                </select>
                              </div>
                            </div>
                          )
                        })()}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-4 bg-yellow-50 p-3 rounded-lg">
              <label className="text-sm font-medium text-gray-700">Độ lệch cho phép:</label>
              <input type="number" value={amountMatchConfig.tolerance || 0}
                onChange={(e) => updateMatch('amount', { tolerance: parseFloat(e.target.value) || 0 })}
                className="w-24 px-3 py-1 border rounded" />
              <select value={amountMatchConfig.tolerance_type || 'absolute'}
                onChange={(e) => updateMatch('amount', { tolerance_type: e.target.value })}
                className="px-3 py-1 border rounded">
                <option value="absolute">Tuyệt đối (VNĐ)</option>
                <option value="percent">Phần trăm (%)</option>
              </select>
            </div>
          </div>

          {/* STATUS LOGIC */}
          <div className="border rounded-lg p-4 bg-gray-50">
            <h4 className="font-medium text-gray-700 mb-3">⚙️ Logic xác định Status</h4>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <label className="text-gray-600 block mb-1">✅ Key + Amount khớp:</label>
                <input type="text" value={statusLogic.all_match || 'MATCHED'}
                  onChange={(e) => updateConfig({ status_logic: { ...statusLogic, all_match: e.target.value } })}
                  className="w-full px-2 py-1 border rounded" />
              </div>
              <div>
                <label className="text-gray-600 block mb-1">⚠️ Key khớp, Amount lệch:</label>
                <input type="text" value={statusLogic.key_match_amount_mismatch || 'MISMATCH'}
                  onChange={(e) => updateConfig({ status_logic: { ...statusLogic, key_match_amount_mismatch: e.target.value } })}
                  className="w-full px-2 py-1 border rounded" />
              </div>
              <div>
                <label className="text-gray-600 block mb-1">❌ Không tìm thấy Key:</label>
                <input type="text" value={statusLogic.no_key_match || 'NOT_FOUND'}
                  onChange={(e) => updateConfig({ status_logic: { ...statusLogic, no_key_match: e.target.value } })}
                  className="w-full px-2 py-1 border rounded" />
              </div>
            </div>
          </div>

          {/* PREVIEW */}
          <div className="border rounded-lg p-4 bg-indigo-50">
            <h4 className="font-medium text-indigo-800 mb-3">👀 Expression Preview</h4>
            <div className="space-y-2">
              <div>
                <label className="text-xs text-indigo-600">🔑 Key Match:</label>
                <div className="bg-white border rounded p-2 font-mono text-xs break-all min-h-[28px]">
                  {generateKeyExpression() || <span className="text-gray-400 italic">Chưa cấu hình</span>}
                </div>
              </div>
              <div>
                <label className="text-xs text-indigo-600">💰 Amount Match:</label>
                <div className="bg-white border rounded p-2 font-mono text-xs break-all min-h-[28px]">
                  {generateAmountExpression() || <span className="text-gray-400 italic">Chưa cấu hình</span>}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default function ConfigFormModal({ isOpen, onClose, editConfig = null }) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('basic')
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [showJsonModal, setShowJsonModal] = useState(false)
  
  // Extract column names from file config
  const b1Columns = Object.keys(config.file_b1_config?.columns || {})
  const b2Columns = Object.keys(config.file_b2_config?.columns || {})
  const b3Columns = Object.keys(config.file_b3_config?.columns || {})
  // B4 columns from config or default
  const b4Columns = config.data_b4_config?.columns || ['transaction_ref', 'partner_ref', 'transaction_date', 'total_amount', 'quantity', 'status']
  // A1 columns from output A1 config
  const a1Columns = (config.output_a1_config?.columns || []).map(c => c.name).filter(Boolean)
  
  useEffect(() => {
    if (editConfig) {
      setConfig(editConfig)
    } else {
      setConfig(DEFAULT_CONFIG)
    }
  }, [editConfig, isOpen])
  
  // Mutations - pass finalConfig to onSuccess to update local state
  const createMutation = useMutation({
    mutationFn: ({ data, closeAfter }) => configsApi.create(data),
    onSuccess: (response, { data, closeAfter }) => {
      toast.success('Tạo cấu hình thành công')
      queryClient.invalidateQueries(['configs'])
      // Update local config with saved data + returned ID
      const savedConfig = { ...data, id: response?.data?.id || data.id }
      setConfig(savedConfig)
      if (closeAfter) {
        onClose()
      }
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Lỗi tạo cấu hình')
    }
  })
  
  const updateMutation = useMutation({
    mutationFn: ({ id, data, closeAfter }) => configsApi.update(id, data),
    onSuccess: (response, { data, closeAfter }) => {
      toast.success('Cập nhật cấu hình thành công')
      queryClient.invalidateQueries(['configs'])
      // Update local config with saved data
      setConfig(data)
      if (closeAfter) {
        onClose()
      }
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Lỗi cập nhật cấu hình')
    }
  })
  
  const handleSubmit = (closeAfter = true) => {
    // Build final config - remove UI-only fields
    const finalConfig = { ...config }
    delete finalConfig._matchingSubTab  // UI state only, don't save to JSON
    
    // Rebuild rules[] array from key_match and amount_match configs for each matching rule set
    const rebuildRules = (matchingConfig, leftPrefix = 'b1', rightPrefix = 'b4') => {
      if (!matchingConfig) return matchingConfig
      
      const safeObj = (val) => (val && typeof val === 'object' && !Array.isArray(val)) ? val : {}
      const safeArray = (val) => Array.isArray(val) ? val : []
      
      const keyMatch = safeObj(matchingConfig.key_match)
      const amountMatch = safeObj(matchingConfig.amount_match)
      
      // Check if we're in advanced mode - if so, use the manually edited expressions
      const isAdvanced = matchingConfig.expression_mode === 'advanced'
      const manualKeyExpr = matchingConfig.key_expression || ''
      const manualAmountExpr = matchingConfig.amount_expression || ''
      
      // Generate expression from side config
      const buildExpr = (sideConfig, prefix) => {
        const parts = safeArray(sideConfig?.parts)
        const transforms = safeArray(sideConfig?.transforms)
        if (parts.length === 0) return `${prefix}['']`
        
        // Build parts
        const partsExpr = parts.map(p => {
          if (!p?.value) return "''"
          if (p.type === 'text') return `'${p.value}'`
          return `${prefix}['${p.value}'].astype(str)`
        }).join(' + ')
        
        let expr = parts.length > 1 ? `(${partsExpr})` : partsExpr
        
        // Apply transforms
        transforms.forEach(t => {
          if (t === 'strip') expr = `${expr}.str.strip()`
          if (t === 'upper') expr = `${expr}.str.upper()`
          if (t === 'lower') expr = `${expr}.str.lower()`
          if (t === 'trim_zero') expr = `${expr}.str.lstrip('0')`
        })
        
        // Apply substring
        if (sideConfig?.substring_start != null || sideConfig?.substring_end != null) {
          const start = sideConfig.substring_start ?? ''
          const end = sideConfig.substring_end ?? ''
          expr = `${expr}.str[${start}:${end}]`
        }
        
        // Apply regex
        if (sideConfig?.regex_pattern) {
          expr = `${expr}.str.extract(r'${sideConfig.regex_pattern}', expand=False)`
        }
        
        // Apply replace
        if (sideConfig?.replace_pattern) {
          const replaceWith = sideConfig.replace_with || ''
          expr = `${expr}.str.replace(r'${sideConfig.replace_pattern}', '${replaceWith}', regex=True)`
        }
        
        return expr
      }
      
      // Generate key match expression with correct prefixes
      const leftKeyExpr = buildExpr(keyMatch.left, leftPrefix)
      const rightKeyExpr = buildExpr(keyMatch.right, rightPrefix)
      
      // Use compare_type to determine expression operator
      const compareType = keyMatch.compare_type || 'exact'
      let keyExpression
      if (compareType === 'like') {
        keyExpression = `${rightKeyExpr}.str.contains(${leftKeyExpr}, na=False)`
      } else if (compareType === 'fuzzy') {
        keyExpression = `fuzzy_match(${leftKeyExpr}, ${rightKeyExpr})`
      } else {
        keyExpression = `${leftKeyExpr} == ${rightKeyExpr}`
      }
      
      // Generate amount match expression with correct prefixes
      const leftAmountParts = safeArray(amountMatch.left?.parts)
      const rightAmountParts = safeArray(amountMatch.right?.parts)
      const leftAmountCol = leftAmountParts.find(p => p?.type === 'column')
      const rightAmountCol = rightAmountParts.find(p => p?.type === 'column')
      
      // Get transforms and advanced config
      const leftAmountTransforms = safeArray(amountMatch.left?.transforms)
      const rightAmountTransforms = safeArray(amountMatch.right?.transforms)
      const leftAmountAdv = safeObj(amountMatch.left)
      const rightAmountAdv = safeObj(amountMatch.right)
      const leftNumberTransform = amountMatch.left?.numberTransform || null
      const rightNumberTransform = amountMatch.right?.numberTransform || null
      
      let amountExpression = ''
      if (leftAmountCol && rightAmountCol) {
        const tolerance = amountMatch.tolerance ?? 0
        
        // Build left and right expressions with full pipeline
        let leftExpr = `${leftPrefix}['${leftAmountCol.value}']`
        let rightExpr = `${rightPrefix}['${rightAmountCol.value}']`
        
        // Apply basic transforms
        leftAmountTransforms.forEach(t => {
          if (t === 'strip') leftExpr = `${leftExpr}.str.strip()`
          if (t === 'upper') leftExpr = `${leftExpr}.str.upper()`
          if (t === 'lower') leftExpr = `${leftExpr}.str.lower()`
          if (t === 'trim_zero') leftExpr = `${leftExpr}.str.lstrip('0')`
        })
        rightAmountTransforms.forEach(t => {
          if (t === 'strip') rightExpr = `${rightExpr}.str.strip()`
          if (t === 'upper') rightExpr = `${rightExpr}.str.upper()`
          if (t === 'lower') rightExpr = `${rightExpr}.str.lower()`
          if (t === 'trim_zero') rightExpr = `${rightExpr}.str.lstrip('0')`
        })
        
        // Apply substring
        if (leftAmountAdv.substring_start != null || leftAmountAdv.substring_end != null) {
          const start = leftAmountAdv.substring_start ?? ''
          const end = leftAmountAdv.substring_end ?? ''
          leftExpr = `${leftExpr}.str[${start}:${end}]`
        }
        if (rightAmountAdv.substring_start != null || rightAmountAdv.substring_end != null) {
          const start = rightAmountAdv.substring_start ?? ''
          const end = rightAmountAdv.substring_end ?? ''
          rightExpr = `${rightExpr}.str[${start}:${end}]`
        }
        
        // Apply regex
        if (leftAmountAdv.regex_pattern) {
          leftExpr = `${leftExpr}.str.extract(r'${leftAmountAdv.regex_pattern}', expand=False)`
        }
        if (rightAmountAdv.regex_pattern) {
          rightExpr = `${rightExpr}.str.extract(r'${rightAmountAdv.regex_pattern}', expand=False)`
        }
        
        // Apply replace
        if (leftAmountAdv.replace_pattern) {
          const replaceWith = leftAmountAdv.replace_with || ''
          leftExpr = `${leftExpr}.str.replace(r'${leftAmountAdv.replace_pattern}', '${replaceWith}', regex=True)`
        }
        if (rightAmountAdv.replace_pattern) {
          const replaceWith = rightAmountAdv.replace_with || ''
          rightExpr = `${rightExpr}.str.replace(r'${rightAmountAdv.replace_pattern}', '${replaceWith}', regex=True)`
        }
        
        // Apply number normalization (final step)
        if (leftNumberTransform?.enabled) {
          // Use ?? to preserve empty string (means "no separator")
          const ts = leftNumberTransform.thousandSeparator ?? ''
          const ds = leftNumberTransform.decimalSeparator ?? ''
          leftExpr = `normalize_number(${leftExpr}, '${ts}', '${ds}')`
        } else {
          leftExpr = `${leftExpr}.astype(float)`
        }
        if (rightNumberTransform?.enabled) {
          // Use ?? to preserve empty string (means "no separator")
          const ts = rightNumberTransform.thousandSeparator ?? ''
          const ds = rightNumberTransform.decimalSeparator ?? ''
          rightExpr = `normalize_number(${rightExpr}, '${ts}', '${ds}')`
        } else {
          rightExpr = `${rightExpr}.astype(float)`
        }
        
        // Build comparison
        if (tolerance === 0) {
          amountExpression = `${leftExpr} == ${rightExpr}`
        } else if (amountMatch.tolerance_type === 'percent') {
          amountExpression = `abs(${leftExpr} - ${rightExpr}) <= ${leftExpr} * ${tolerance / 100}`
        } else {
          amountExpression = `abs(${leftExpr} - ${rightExpr}) <= ${tolerance}`
        }
      }
      
      // Build rules array - preserve ALL config from UI
      const rules = [
        {
          rule_name: 'key_match',
          type: 'expression',
          expression: keyExpression,
          compare_type: compareType,  // Save compare_type for backend
          _ui_config: { 
            mode: 'simple', 
            left: keyMatch.left, 
            right: keyMatch.right, 
            compareType: compareType  // Use actual value from UI
          }
        }
      ]
      
      if (amountExpression) {
        rules.push({
          rule_name: 'amount_match',
          type: 'expression',
          expression: amountExpression,
          // Include number transforms for engine to apply
          left_number_transform: leftNumberTransform,
          right_number_transform: rightNumberTransform,
          tolerance: amountMatch.tolerance ?? 0,  // Save tolerance
          tolerance_type: amountMatch.tolerance_type || 'absolute',  // Save tolerance type
          _ui_config: { 
            mode: 'simple', 
            left: amountMatch.left, 
            right: amountMatch.right,
            tolerance: amountMatch.tolerance ?? 0,
            tolerance_type: amountMatch.tolerance_type || 'absolute'
          }
        })
      }
      
      // If in advanced mode, use the manually edited expressions instead
      const finalKeyExpr = isAdvanced && manualKeyExpr ? manualKeyExpr : keyExpression
      const finalAmountExpr = isAdvanced && manualAmountExpr ? manualAmountExpr : amountExpression
      
      // Update rules with final expressions
      if (rules.length > 0 && rules[0].rule_name === 'key_match') {
        rules[0].expression = finalKeyExpr
      }
      if (rules.length > 1 && rules[1].rule_name === 'amount_match') {
        rules[1].expression = finalAmountExpr
      }
      
      console.log('[CONFIG] Rebuilt rules for', leftPrefix, '->', rightPrefix, ':', 
        isAdvanced ? '(ADVANCED MODE)' : '(SIMPLE MODE)', 
        rules.map(r => r.expression))
      
      return {
        ...matchingConfig,
        match_type: 'expression',
        rules,
        key_expression: finalKeyExpr,
        amount_expression: finalAmountExpr
      }
    }
    
    // Rebuild all matching rules with correct prefixes
    // B1B4 is always enabled
    if (finalConfig.matching_rules_b1b4) {
      finalConfig.matching_rules_b1b4 = rebuildRules(finalConfig.matching_rules_b1b4, 'b1', 'b4')
    }
    
    // B1B2 and B3A1 - only rebuild if enabled, otherwise clean up
    if (finalConfig.matching_rules_b1b2?.enabled) {
      finalConfig.matching_rules_b1b2 = rebuildRules(finalConfig.matching_rules_b1b2, 'b1', 'b2')
    } else if (finalConfig.matching_rules_b1b2) {
      // Keep only enabled: false to indicate it's disabled
      finalConfig.matching_rules_b1b2 = { enabled: false }
    }
    
    if (finalConfig.matching_rules_b3a1?.enabled) {
      finalConfig.matching_rules_b3a1 = rebuildRules(finalConfig.matching_rules_b3a1, 'b3', 'a1')
    } else if (finalConfig.matching_rules_b3a1) {
      // Keep only enabled: false to indicate it's disabled
      finalConfig.matching_rules_b3a1 = { enabled: false }
    }
    
    // Determine if this is update or create
    // Pass closeAfter directly to mutation to avoid race condition with state
    const configId = editConfig?.id || config.id
    if (configId) {
      updateMutation.mutate({ id: configId, data: finalConfig, closeAfter })
    } else {
      createMutation.mutate({ data: finalConfig, closeAfter })
    }
  }
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between bg-gray-50 rounded-t-xl">
          <h2 className="text-lg font-semibold text-gray-800">
            {editConfig ? 'Chỉnh sửa cấu hình' : 'Tạo cấu hình mới'}
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-200 rounded">✕</button>
        </div>
        
        {/* Tabs */}
        <div className="flex border-b bg-gray-50">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 bg-white'
                  : 'border-transparent text-gray-600 hover:text-gray-800'
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Basic Info */}
          {activeTab === 'basic' && (
            <div className="space-y-4 max-w-2xl">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Mã đối tác <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.partner_code}
                    onChange={(e) => setConfig({ ...config, partner_code: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VD: SACOMBANK, VCB"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tên đối tác <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.partner_name}
                    onChange={(e) => setConfig({ ...config, partner_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VD: Ngân hàng Sacombank"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Mã dịch vụ <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.service_code}
                    onChange={(e) => setConfig({ ...config, service_code: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VD: TOPUP, PINCODE"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tên dịch vụ <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.service_name}
                    onChange={(e) => setConfig({ ...config, service_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VD: Nạp tiền điện thoại"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Có hiệu lực từ <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={config.valid_from}
                    onChange={(e) => setConfig({ ...config, valid_from: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Đến ngày (để trống = vô hạn)
                  </label>
                  <input
                    type="date"
                    value={config.valid_to || ''}
                    onChange={(e) => setConfig({ ...config, valid_to: e.target.value || null })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>
            </div>
          )}
          
          {/* File Config */}
          {activeTab === 'files' && (
            <div className="space-y-4">
              <FileConfigEditor
                config={config.file_b1_config}
                onChange={(val) => setConfig({ ...config, file_b1_config: val })}
                label="📄 File B1 - Sao kê đối tác (bắt buộc)"
              />
              
              <div className="border-t pt-4">
                <label className="flex items-center gap-2 mb-3">
                  <input
                    type="checkbox"
                    checked={!!config.file_b2_config}
                    onChange={(e) => setConfig({ 
                      ...config, 
                      file_b2_config: e.target.checked 
                        ? { header_row: 1, data_start_row: 2, columns: {} }
                        : null 
                    })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-sm font-medium text-gray-700">Có file B2 (hoàn tiền)</span>
                </label>
                {config.file_b2_config && (
                  <FileConfigEditor
                    config={config.file_b2_config}
                    onChange={(val) => setConfig({ ...config, file_b2_config: val })}
                    label="💸 File B2 - Hoàn tiền"
                  />
                )}
              </div>

              <div className="border-t pt-4">
                <label className="flex items-center gap-2 mb-3">
                  <input
                    type="checkbox"
                    checked={!!config.file_b3_config}
                    onChange={(e) => setConfig({ 
                      ...config, 
                      file_b3_config: e.target.checked 
                        ? { header_row: 1, data_start_row: 2, columns: {} }
                        : null 
                    })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-sm font-medium text-gray-700">Có file B3 (chi tiết đối tác)</span>
                </label>
                {config.file_b3_config && (
                  <FileConfigEditor
                    config={config.file_b3_config}
                    onChange={(val) => setConfig({ ...config, file_b3_config: val })}
                    label="📋 File B3 - Chi tiết đối tác"
                  />
                )}
              </div>
            </div>
          )}
          
          {/* B4 Config */}
          {activeTab === 'b4' && (
            <div className="space-y-4 max-w-2xl">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Database Connection
                </label>
                <select
                  value={config.data_b4_config?.db_connection || ''}
                  onChange={(e) => setConfig({
                    ...config,
                    data_b4_config: { ...config.data_b4_config, db_connection: e.target.value }
                  })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="">-- Chọn connection --</option>
                  <option value="vnptmoney_main">vnptmoney_main (Production)</option>
                  <option value="vnptmoney_dev">vnptmoney_dev (Development)</option>
                  <option value="sqlite_local">sqlite_local (Testing)</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  SQL File (relative to sql_templates/)
                </label>
                <input
                  type="text"
                  value={config.data_b4_config?.sql_file || ''}
                  onChange={(e) => setConfig({
                    ...config,
                    data_b4_config: { ...config.data_b4_config, sql_file: e.target.value }
                  })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                  placeholder="VD: shared/query_b4_topup.sql"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Mock File (cho testing)
                </label>
                <input
                  type="text"
                  value={config.data_b4_config?.mock_file || ''}
                  onChange={(e) => setConfig({
                    ...config,
                    data_b4_config: { ...config.data_b4_config, mock_file: e.target.value }
                  })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono"
                  placeholder="VD: SACOMBANK_TOPUP_b4_mock.csv"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  SQL Parameters (JSON)
                </label>
                <textarea
                  value={JSON.stringify(config.data_b4_config?.sql_params || {}, null, 2)}
                  onChange={(e) => {
                    try {
                      const params = JSON.parse(e.target.value)
                      setConfig({
                        ...config,
                        data_b4_config: { ...config.data_b4_config, sql_params: params }
                      })
                    } catch (err) {
                      // Invalid JSON - ignore
                    }
                  }}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm h-24"
                  placeholder='{"service_id": "TOPUP", "partner_id": "SACOMBANK"}'
                />
              </div>

              {/* B4 Columns Configuration */}
              <div className="border-t pt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Cấu hình cột B4 (danh sách cột sẽ dùng cho matching)
                </label>
                <p className="text-xs text-gray-500 mb-3">
                  Định nghĩa các cột sẽ được trả về từ SQL query hoặc mock file. Mỗi cột cách nhau bởi dấu phẩy.
                </p>
                <input
                  type="text"
                  value={(config.data_b4_config?.columns || []).join(', ')}
                  onChange={(e) => {
                    const cols = e.target.value.split(',').map(c => c.trim()).filter(c => c)
                    setConfig({
                      ...config,
                      data_b4_config: { ...config.data_b4_config, columns: cols }
                    })
                  }}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
                  placeholder="transaction_ref, partner_ref, transaction_date, total_amount, quantity, status"
                />
                {(config.data_b4_config?.columns || []).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(config.data_b4_config?.columns || []).map((col, idx) => (
                      <span key={idx} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-mono">
                        {col}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Matching Rules */}
          {activeTab === 'matching' && (
            <div className="space-y-4">
              {/* Sub-tabs for matching types */}
              <div className="flex items-center gap-2 border-b">
                <button
                  onClick={() => setConfig({ ...config, _matchingSubTab: 'b1b4' })}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
                    (config._matchingSubTab || 'b1b4') === 'b1b4' 
                      ? 'border-blue-600 text-blue-600' 
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  🔗 B1 ↔ B4
                </button>
                <button
                  onClick={() => setConfig({ ...config, _matchingSubTab: 'b1b2' })}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition flex items-center gap-2 ${
                    config._matchingSubTab === 'b1b2' 
                      ? 'border-green-600 text-green-600' 
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  💸 B1 ↔ B2
                  {config.matching_rules_b1b2?.enabled && <span className="w-2 h-2 bg-green-500 rounded-full"></span>}
                </button>
                <button
                  onClick={() => setConfig({ ...config, _matchingSubTab: 'b3a1' })}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition flex items-center gap-2 ${
                    config._matchingSubTab === 'b3a1' 
                      ? 'border-purple-600 text-purple-600' 
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  📋 B3 ↔ A1
                  {config.matching_rules_b3a1?.enabled && <span className="w-2 h-2 bg-purple-500 rounded-full"></span>}
                </button>
              </div>

              {/* B1 ↔ B4 Matching (always enabled) */}
              {(config._matchingSubTab || 'b1b4') === 'b1b4' && (
                <MatchingRulesEditor
                  config={config.matching_rules_b1b4}
                  onChange={(val) => setConfig({ ...config, matching_rules_b1b4: val })}
                  leftColumns={b1Columns}
                  rightColumns={b4Columns}
                  leftLabel="B1 (Sao kê)"
                  rightLabel="B4 (Hệ thống)"
                  leftPrefix="b1"
                  rightPrefix="b4"
                  title="🔗 Matching B1 ↔ B4 (Sao kê vs Hệ thống)"
                />
              )}

              {/* B1 ↔ B2 Matching (optional) */}
              {config._matchingSubTab === 'b1b2' && (
                <div className="space-y-4">
                  {/* Enable/Disable toggle */}
                  <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg border border-green-200">
                    <input
                      type="checkbox"
                      id="enable-b1b2"
                      checked={config.matching_rules_b1b2?.enabled || false}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setConfig({ 
                            ...config, 
                            matching_rules_b1b2: {
                              enabled: true,
                              key_match: { left: { parts: [] }, right: { parts: [] }, compare_type: 'exact' },
                              amount_match: { left: { parts: [] }, right: { parts: [] }, tolerance: 0 },
                              status_logic: { all_match: 'MATCHED', no_key_match: 'NOT_FOUND' }
                            }
                          })
                        } else {
                          setConfig({ ...config, matching_rules_b1b2: { enabled: false } })
                        }
                      }}
                      className="w-4 h-4 text-green-600"
                    />
                    <label htmlFor="enable-b1b2" className="text-sm font-medium text-green-800 cursor-pointer">
                      Bật cấu hình Matching B1 ↔ B2 (Sao kê vs Hoàn tiền)
                    </label>
                  </div>

                  {config.matching_rules_b1b2?.enabled && (
                    <MatchingRulesEditor
                      config={config.matching_rules_b1b2}
                      onChange={(val) => setConfig({ ...config, matching_rules_b1b2: { ...val, enabled: true } })}
                      leftColumns={b1Columns}
                      rightColumns={b2Columns}
                      leftLabel="B1 (Sao kê)"
                      rightLabel="B2 (Hoàn tiền)"
                      leftPrefix="b1"
                      rightPrefix="b2"
                      title="💸 Matching B1 ↔ B2"
                    />
                  )}

                  {!config.matching_rules_b1b2?.enabled && (
                    <div className="text-center py-8 bg-gray-50 rounded-lg text-gray-500">
                      <p>Tick checkbox ở trên để bật cấu hình matching B1 ↔ B2</p>
                      <p className="text-xs mt-1">Dùng để đối soát sao kê với file hoàn tiền</p>
                    </div>
                  )}
                </div>
              )}

              {/* B3 ↔ A1 Matching (optional) */}
              {config._matchingSubTab === 'b3a1' && (
                <div className="space-y-4">
                  {/* Enable/Disable toggle */}
                  <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg border border-purple-200">
                    <input
                      type="checkbox"
                      id="enable-b3a1"
                      checked={config.matching_rules_b3a1?.enabled || false}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setConfig({ 
                            ...config, 
                            matching_rules_b3a1: {
                              enabled: true,
                              key_match: { left: { parts: [] }, right: { parts: [] }, compare_type: 'exact' },
                              amount_match: { left: { parts: [] }, right: { parts: [] }, tolerance: 0 },
                              status_logic: { all_match: 'MATCHED', no_key_match: 'NOT_FOUND' }
                            }
                          })
                        } else {
                          setConfig({ ...config, matching_rules_b3a1: { enabled: false } })
                        }
                      }}
                      className="w-4 h-4 text-purple-600"
                    />
                    <label htmlFor="enable-b3a1" className="text-sm font-medium text-purple-800 cursor-pointer">
                      Bật cấu hình Matching B3 ↔ A1 (Đối tác vs Kết quả)
                    </label>
                  </div>

                  {config.matching_rules_b3a1?.enabled && (
                    <>
                      <MatchingRulesEditor
                        config={config.matching_rules_b3a1}
                        onChange={(val) => setConfig({ ...config, matching_rules_b3a1: { ...val, enabled: true } })}
                        leftColumns={b3Columns}
                        rightColumns={[...b1Columns, ...b4Columns, 'final_status', 'status_b1b4']}
                        leftLabel="B3 (Chi tiết đối tác - Chuẩn)"
                        rightLabel="A1 (Kết quả B1↔B4)"
                        leftPrefix="b3"
                        rightPrefix="a1"
                        title="📋 Matching B3 ↔ A1 → A2"
                      />
                      <div className="p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
                        <strong>Lưu ý:</strong> B3 là nguồn chuẩn. Kết quả matching B3↔A1 sẽ tạo ra file A2 (các giao dịch lệch)
                      </div>
                    </>
                  )}

                  {!config.matching_rules_b3a1?.enabled && (
                    <div className="text-center py-8 bg-gray-50 rounded-lg text-gray-500">
                      <p>Tick checkbox ở trên để bật cấu hình matching B3 ↔ A1</p>
                      <p className="text-xs mt-1">Dùng để đối soát chi tiết đối tác với kết quả đối soát B1↔B4</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Status Combine Tab */}
          {activeTab === 'status' && (
            <div className="space-y-6">
              <StatusCombineEditor
                config={config.status_combine_rules}
                onChange={(val) => setConfig({ ...config, status_combine_rules: val })}
                hasB2={!!config.file_b2_config}
              />
            </div>
          )}
          
          {/* Output Config */}
          {activeTab === 'output' && (
            <div className="space-y-6">
              {/* A1 Output */}
              <div className="border rounded-lg p-4">
                <OutputColumnsEditor
                  config={config.output_a1_config}
                  onChange={(val) => setConfig({ ...config, output_a1_config: val })}
                  b1Columns={b1Columns}
                  b2Columns={b2Columns}
                  b3Columns={b3Columns}
                  b4Columns={b4Columns}
                  label="📗 Cấu hình cột output A1 (Khớp)"
                  showB2B3={!!config.file_b2_config || !!config.file_b3_config}
                />
              </div>

              {/* A2 Output */}
              <div className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-4">
                  <input
                    type="checkbox"
                    checked={!!config.output_a2_config}
                    onChange={(e) => setConfig({
                      ...config,
                      output_a2_config: e.target.checked ? { columns: [] } : null
                    })}
                    className="w-4 h-4 rounded"
                  />
                  <span className="font-medium text-gray-700">Cấu hình output A2 (Lệch/Không khớp)</span>
                </div>
                {config.output_a2_config && (
                  <OutputColumnsEditor
                    config={config.output_a2_config}
                    onChange={(val) => setConfig({ ...config, output_a2_config: val })}
                    b1Columns={b1Columns}
                    b2Columns={b2Columns}
                    b3Columns={b3Columns}
                    b4Columns={b4Columns}
                    a1Columns={a1Columns}
                    label="📕 Cấu hình cột output A2 (Lệch)"
                    showB2B3={!!config.file_b2_config || !!config.file_b3_config}
                    showA1={true}
                  />
                )}
              </div>
            </div>
          )}

          {/* Report Template Tab */}
          {activeTab === 'report' && (
            <div className="space-y-6">
              <ReportTemplateEditor
                config={config.report_template_path}
                onChange={(val) => setConfig({ ...config, report_template_path: val })}
                reportCellMapping={config.report_cell_mapping}
                onCellMappingChange={(val) => setConfig({ ...config, report_cell_mapping: val })}
              />
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="p-4 border-t bg-gray-50 rounded-b-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border rounded-lg hover:bg-gray-100 transition"
            >
              Hủy
            </button>
            <button
              onClick={() => setShowJsonModal(true)}
              className="px-4 py-2 border border-blue-500 text-blue-600 rounded-lg hover:bg-blue-50 transition"
            >
              Xem JSON
            </button>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleSubmit(false)}
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50"
            >
              {createMutation.isPending || updateMutation.isPending ? 'Đang lưu...' : '💾 Lưu & Tiếp tục'}
            </button>
            <button
              onClick={() => handleSubmit(true)}
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
            >
              {createMutation.isPending || updateMutation.isPending ? 'Đang lưu...' : '✅ Lưu & Đóng'}
            </button>
          </div>
        </div>

        {/* JSON Preview Modal */}
        {showJsonModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
              <div className="p-4 border-b flex items-center justify-between bg-gray-50 rounded-t-xl">
                <h3 className="text-lg font-semibold text-gray-800">📋 Xem cấu hình JSON</h3>
                <button onClick={() => setShowJsonModal(false)} className="p-2 hover:bg-gray-200 rounded">✕</button>
              </div>
              <div className="flex-1 overflow-auto p-4">
                <pre className="bg-gray-900 text-green-400 p-4 rounded-lg text-xs font-mono whitespace-pre-wrap overflow-x-auto">
                  {JSON.stringify(config, null, 2)}
                </pre>
              </div>
              <div className="p-4 border-t bg-gray-50 flex justify-end gap-2">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(JSON.stringify(config, null, 2))
                    toast.success('Đã copy JSON!')
                  }}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  📋 Copy JSON
                </button>
                <button
                  onClick={() => setShowJsonModal(false)}
                  className="px-4 py-2 border rounded-lg hover:bg-gray-100"
                >
                  Đóng
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

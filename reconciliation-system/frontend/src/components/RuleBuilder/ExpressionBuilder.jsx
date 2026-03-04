/**
 * ExpressionBuilder Component
 * 
 * UI để xây dựng expression theo chế độ Simple Mode
 * - Chọn cột cho bên trái (B1) và bên phải (B4)
 * - Ghép nhiều cột với text
 * - Chọn các transform (strip, upper, lower, trim_zero, substring, regex)
 */

import { useState } from 'react'

const SIMPLE_TRANSFORMS = [
  { id: 'strip', label: 'Trim khoảng trắng', description: 'Xóa khoảng trắng đầu/cuối' },
  { id: 'upper', label: 'Viết HOA', description: 'Chuyển thành chữ in hoa' },
  { id: 'lower', label: 'Viết thường', description: 'Chuyển thành chữ thường' },
  { id: 'trim_zero', label: 'Bỏ số 0 đầu', description: 'Xóa số 0 ở đầu chuỗi' },
]

const ADVANCED_TRANSFORMS = [
  { id: 'substring', label: 'Cắt chuỗi (substring)', description: 'Lấy một phần chuỗi theo vị trí', hasParams: true, params: ['start', 'end'] },
  { id: 'regex_extract', label: 'Regex Extract', description: 'Trích xuất theo regex pattern', hasParams: true, params: ['pattern'] },
  { id: 'replace', label: 'Thay thế', description: 'Thay thế chuỗi', hasParams: true, params: ['old', 'new'] },
  { id: 'remove_prefix', label: 'Xóa tiền tố', description: 'Xóa chuỗi ở đầu', hasParams: true, params: ['prefix'] },
  { id: 'remove_suffix', label: 'Xóa hậu tố', description: 'Xóa chuỗi ở cuối', hasParams: true, params: ['suffix'] },
]

function SideBuilder({ side, label, config, onChange, columns }) {
  const { parts = [], transforms = [], advancedTransforms = [], numberTransform = null } = config
  const [showAdvanced, setShowAdvanced] = useState(advancedTransforms.length > 0)
  
  const handleAddPart = (type) => {
    const newPart = type === 'column' 
      ? { type: 'column', value: columns[0] || '' }
      : { type: 'text', value: '' }
    onChange({
      ...config,
      parts: [...parts, newPart]
    })
  }
  
  const handleUpdatePart = (index, field, value) => {
    const newParts = [...parts]
    newParts[index] = { ...newParts[index], [field]: value }
    onChange({ ...config, parts: newParts })
  }
  
  const handleRemovePart = (index) => {
    const newParts = parts.filter((_, i) => i !== index)
    onChange({ ...config, parts: newParts })
  }
  
  const handleMovePart = (index, direction) => {
    const newParts = [...parts]
    const newIndex = index + direction
    if (newIndex < 0 || newIndex >= parts.length) return
    ;[newParts[index], newParts[newIndex]] = [newParts[newIndex], newParts[index]]
    onChange({ ...config, parts: newParts })
  }
  
  const handleToggleTransform = (transformId) => {
    // Check if it's a simple transform (string) 
    const simpleIds = SIMPLE_TRANSFORMS.map(t => t.id)
    if (simpleIds.includes(transformId)) {
      const newTransforms = transforms.includes(transformId)
        ? transforms.filter(t => t !== transformId)
        : [...transforms, transformId]
      onChange({ ...config, transforms: newTransforms })
    }
  }

  const handleAddAdvancedTransform = (transformDef) => {
    const newAdvanced = [...advancedTransforms]
    const newTransform = { type: transformDef.id, params: {} }
    // Initialize default params
    if (transformDef.id === 'substring') {
      newTransform.params = { start: 0, end: 10 }
    } else if (transformDef.id === 'regex_extract') {
      newTransform.params = { pattern: '(.+)' }
    } else if (transformDef.id === 'replace') {
      newTransform.params = { old: '', new: '' }
    } else if (transformDef.id === 'remove_prefix' || transformDef.id === 'remove_suffix') {
      newTransform.params = { value: '' }
    }
    newAdvanced.push(newTransform)
    onChange({ ...config, advancedTransforms: newAdvanced })
  }

  const handleUpdateAdvancedTransform = (index, paramName, value) => {
    const newAdvanced = [...advancedTransforms]
    newAdvanced[index] = {
      ...newAdvanced[index],
      params: { ...newAdvanced[index].params, [paramName]: value }
    }
    onChange({ ...config, advancedTransforms: newAdvanced })
  }

  const handleRemoveAdvancedTransform = (index) => {
    const newAdvanced = advancedTransforms.filter((_, i) => i !== index)
    onChange({ ...config, advancedTransforms: newAdvanced })
  }
  
  // Generate preview
  const generatePreview = () => {
    if (parts.length === 0) return '(chưa cấu hình)'
    return parts.map(p => {
      if (p.type === 'column') return `${side}['${p.value}']`
      return `'${p.value}'`
    }).join(' || ')
  }
  
  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <h4 className="font-medium text-gray-700 mb-3">{label}</h4>
      
      {/* Parts List */}
      <div className="space-y-2 mb-3">
        {parts.length === 0 && (
          <p className="text-sm text-gray-400 italic">Chưa có thành phần nào</p>
        )}
        {parts.map((part, idx) => (
          <div key={idx} className="flex items-center gap-2 bg-white p-2 rounded border">
            {/* Move buttons */}
            <div className="flex flex-col gap-0.5">
              <button
                onClick={() => handleMovePart(idx, -1)}
                disabled={idx === 0}
                className="text-gray-400 hover:text-gray-600 disabled:opacity-30 text-xs"
              >
                ▲
              </button>
              <button
                onClick={() => handleMovePart(idx, 1)}
                disabled={idx === parts.length - 1}
                className="text-gray-400 hover:text-gray-600 disabled:opacity-30 text-xs"
              >
                ▼
              </button>
            </div>
            
            {/* Part type */}
            <select
              value={part.type}
              onChange={(e) => handleUpdatePart(idx, 'type', e.target.value)}
              className="px-2 py-1 border rounded text-sm bg-gray-50"
            >
              <option value="column">Cột</option>
              <option value="text">Text</option>
            </select>
            
            {/* Value */}
            {part.type === 'column' ? (
              <select
                value={part.value}
                onChange={(e) => handleUpdatePart(idx, 'value', e.target.value)}
                className="flex-1 px-2 py-1 border rounded text-sm"
              >
                <option value="">-- Chọn cột --</option>
                {columns.map(col => (
                  <option key={col} value={col}>{col}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={part.value}
                onChange={(e) => handleUpdatePart(idx, 'value', e.target.value)}
                placeholder="Nhập text..."
                className="flex-1 px-2 py-1 border rounded text-sm"
              />
            )}
            
            {/* Remove */}
            <button
              onClick={() => handleRemovePart(idx)}
              className="p-1 text-red-500 hover:bg-red-50 rounded"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      
      {/* Add buttons */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => handleAddPart('column')}
          className="px-3 py-1 text-sm border border-blue-500 text-blue-600 rounded hover:bg-blue-50"
        >
          + Thêm Cột
        </button>
        <button
          onClick={() => handleAddPart('text')}
          className="px-3 py-1 text-sm border border-gray-400 text-gray-600 rounded hover:bg-gray-50"
        >
          + Thêm Text
        </button>
      </div>
      
      {/* Transforms */}
      <div className="border-t pt-3">
        <label className="text-sm font-medium text-gray-600 mb-2 block">Transform cơ bản:</label>
        <div className="flex flex-wrap gap-3">
          {SIMPLE_TRANSFORMS.map(t => (
            <label key={t.id} className="flex items-center gap-1.5 cursor-pointer" title={t.description}>
              <input
                type="checkbox"
                checked={transforms.includes(t.id)}
                onChange={() => handleToggleTransform(t.id)}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm text-gray-700">{t.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Advanced Transforms Toggle */}
      <div className="mt-3 pt-3 border-t">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-blue-600 hover:underline flex items-center gap-1"
        >
          {showAdvanced ? '▼' : '▶'} Transform nâng cao (substring, regex...)
        </button>
        
        {showAdvanced && (
          <div className="mt-3 space-y-3">
            {/* List of added advanced transforms */}
            {advancedTransforms.map((adv, idx) => {
              const transformDef = ADVANCED_TRANSFORMS.find(t => t.id === adv.type)
              return (
                <div key={idx} className="bg-yellow-50 p-3 rounded border border-yellow-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-sm text-yellow-800">{transformDef?.label || adv.type}</span>
                    <button
                      onClick={() => handleRemoveAdvancedTransform(idx)}
                      className="text-red-500 hover:bg-red-100 p-1 rounded text-xs"
                    >
                      ✕ Xóa
                    </button>
                  </div>
                  
                  {/* Params based on type */}
                  {adv.type === 'substring' && (
                    <div className="flex items-center gap-2 text-sm">
                      <label className="text-gray-600">Từ vị trí:</label>
                      <input
                        type="number"
                        value={adv.params?.start || 0}
                        onChange={(e) => handleUpdateAdvancedTransform(idx, 'start', parseInt(e.target.value) || 0)}
                        className="w-16 px-2 py-1 border rounded"
                        min="0"
                      />
                      <label className="text-gray-600">đến:</label>
                      <input
                        type="number"
                        value={adv.params?.end || 10}
                        onChange={(e) => handleUpdateAdvancedTransform(idx, 'end', parseInt(e.target.value) || 10)}
                        className="w-16 px-2 py-1 border rounded"
                        min="0"
                      />
                      <span className="text-xs text-gray-500">(0 = đầu chuỗi)</span>
                    </div>
                  )}
                  
                  {adv.type === 'regex_extract' && (
                    <div className="flex items-center gap-2 text-sm">
                      <label className="text-gray-600">Pattern:</label>
                      <input
                        type="text"
                        value={adv.params?.pattern || ''}
                        onChange={(e) => handleUpdateAdvancedTransform(idx, 'pattern', e.target.value)}
                        className="flex-1 px-2 py-1 border rounded font-mono"
                        placeholder="VD: ATBB:(\w+) hoặc (\d+)"
                      />
                    </div>
                  )}
                  
                  {adv.type === 'replace' && (
                    <div className="flex items-center gap-2 text-sm">
                      <label className="text-gray-600">Tìm:</label>
                      <input
                        type="text"
                        value={adv.params?.old || ''}
                        onChange={(e) => handleUpdateAdvancedTransform(idx, 'old', e.target.value)}
                        className="w-24 px-2 py-1 border rounded"
                      />
                      <label className="text-gray-600">Thay bằng:</label>
                      <input
                        type="text"
                        value={adv.params?.new || ''}
                        onChange={(e) => handleUpdateAdvancedTransform(idx, 'new', e.target.value)}
                        className="w-24 px-2 py-1 border rounded"
                      />
                    </div>
                  )}
                  
                  {(adv.type === 'remove_prefix' || adv.type === 'remove_suffix') && (
                    <div className="flex items-center gap-2 text-sm">
                      <label className="text-gray-600">{adv.type === 'remove_prefix' ? 'Tiền tố:' : 'Hậu tố:'}</label>
                      <input
                        type="text"
                        value={adv.params?.value || ''}
                        onChange={(e) => handleUpdateAdvancedTransform(idx, 'value', e.target.value)}
                        className="w-32 px-2 py-1 border rounded"
                      />
                    </div>
                  )}
                </div>
              )
            })}
            
            {/* Add advanced transform dropdown */}
            <div className="flex items-center gap-2">
              <select
                className="px-3 py-1 border rounded text-sm"
                onChange={(e) => {
                  const transformDef = ADVANCED_TRANSFORMS.find(t => t.id === e.target.value)
                  if (transformDef) {
                    handleAddAdvancedTransform(transformDef)
                    e.target.value = ''
                  }
                }}
                defaultValue=""
              >
                <option value="">+ Thêm transform nâng cao...</option>
                {ADVANCED_TRANSFORMS.map(t => (
                  <option key={t.id} value={t.id}>{t.label}</option>
                ))}
              </select>
            </div>

            {/* Help text for substring example */}
            <div className="text-xs text-gray-500 bg-gray-100 p-2 rounded">
              <strong>Ví dụ substring:</strong> Chuỗi "ATBB:BLX040014504 VNT-TOPUP..."<br/>
              → Từ vị trí 5, đến 17 sẽ lấy được "BLX040014504"<br/>
              <strong>Ví dụ regex:</strong> Pattern <code>ATBB:(\w+)</code> sẽ trích xuất "BLX040014504"
            </div>
          </div>
        )}
      </div>

      {/* Number Transform Section */}
      <div className="mt-3 pt-3 border-t">
        <div className="flex items-center gap-2 mb-2">
          <input
            type="checkbox"
            id={`${side}-number-transform`}
            checked={numberTransform?.enabled || false}
            onChange={(e) => {
              if (e.target.checked) {
                onChange({
                  ...config,
                  numberTransform: {
                    enabled: true,
                    thousandSeparator: ',',
                    decimalSeparator: '.'
                  }
                })
              } else {
                onChange({ ...config, numberTransform: null })
              }
            }}
            className="w-4 h-4 rounded"
          />
          <label htmlFor={`${side}-number-transform`} className="text-sm font-medium text-gray-700 cursor-pointer">
            🔢 Transform số (chuẩn hóa format số)
          </label>
        </div>

        {numberTransform?.enabled && (
          <div className="ml-6 p-3 bg-blue-50 rounded-lg border border-blue-200 space-y-3">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">Dấu ngăn nghìn:</label>
                <select
                  value={numberTransform.thousandSeparator || ','}
                  onChange={(e) => onChange({
                    ...config,
                    numberTransform: { ...numberTransform, thousandSeparator: e.target.value }
                  })}
                  className="px-2 py-1 border rounded text-sm"
                >
                  <option value=",">Dấu phẩy (,) - VD: 1,000</option>
                  <option value=".">Dấu chấm (.) - VD: 1.000</option>
                  <option value="">Không có</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-600">Dấu thập phân:</label>
                <select
                  value={numberTransform.decimalSeparator || '.'}
                  onChange={(e) => onChange({
                    ...config,
                    numberTransform: { ...numberTransform, decimalSeparator: e.target.value }
                  })}
                  className="px-2 py-1 border rounded text-sm"
                >
                  <option value=".">Dấu chấm (.) - VD: 10.50</option>
                  <option value=",">Dấu phẩy (,) - VD: 10,50</option>
                  <option value="">Không có (số nguyên)</option>
                </select>
              </div>
            </div>
            <div className="text-xs text-blue-700 bg-blue-100 p-2 rounded">
              <strong>Kết quả:</strong> "{numberTransform.thousandSeparator === ',' ? '1,000' : numberTransform.thousandSeparator === '.' ? '1.000' : '1000'}" 
              → "1000" | 
              "{numberTransform.decimalSeparator === '.' ? '10.50' : numberTransform.decimalSeparator === ',' ? '10,50' : '10'}" 
              → "{numberTransform.decimalSeparator ? '10.50' : '10'}"
            </div>
          </div>
        )}
      </div>
      
      {/* Preview */}
      <div className="mt-3 pt-3 border-t">
        <label className="text-xs font-medium text-gray-500 block mb-1">Preview:</label>
        <code className="text-xs text-gray-600 bg-white px-2 py-1 rounded border block">
          {generatePreview()}
        </code>
      </div>
    </div>
  )
}

export default function ExpressionBuilder({ 
  uiConfig, 
  onChange, 
  b1Columns, 
  b4Columns,
  leftLabel = "📄 Bên trái - Sao kê (B1)",
  rightLabel = "🗄️ Bên phải - Hệ thống (B4)"
}) {
  const handleLeftChange = (newLeft) => {
    onChange('left', newLeft)
  }
  
  const handleRightChange = (newRight) => {
    onChange('right', newRight)
  }
  
  return (
    <div className="grid grid-cols-2 gap-4">
      <SideBuilder
        side="B1"
        label={leftLabel}
        config={uiConfig.left}
        onChange={handleLeftChange}
        columns={b1Columns}
      />
      <SideBuilder
        side="B4"
        label={rightLabel}
        config={uiConfig.right}
        onChange={handleRightChange}
        columns={b4Columns}
      />
    </div>
  )
}

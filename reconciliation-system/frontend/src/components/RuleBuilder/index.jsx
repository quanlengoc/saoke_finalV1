/**
 * RuleBuilder Component
 * 
 * Cho phép người dùng cấu hình rule matching theo 2 chế độ:
 * 1. Simple Mode: Chọn cột, transform, kiểu so sánh → Tự động gen expression
 * 2. Advanced Mode: Edit expression trực tiếp
 */

import { useState, useEffect, useCallback } from 'react'
import ExpressionBuilder from './ExpressionBuilder'
import ExpressionEditor from './ExpressionEditor'

// Hàm generate expression từ UI config
export function generateExpression(ruleConfig, leftPrefix = 'b1', rightPrefix = 'b4') {
  const { left, right, compareType, tolerance = 0, toleranceType = 'absolute' } = ruleConfig
  
  // Build expression cho mỗi bên
  const leftExpr = buildSideExpr(leftPrefix, left)
  const rightExpr = buildSideExpr(rightPrefix, right)
  
  // Tạo expression theo compareType
  switch (compareType) {
    case 'exact':
      return `${leftExpr} == ${rightExpr}`
    case 'like':
      return `${leftExpr}.str.contains(${rightExpr}, regex=False, na=False)`
    case 'fuzzy':
      return `fuzzy_match(${leftExpr}, ${rightExpr}, threshold=0.85)`
    case 'tolerance':
      if (toleranceType === 'percent') {
        return `(abs(${leftExpr}.astype(float) - ${rightExpr}.astype(float)) / ${rightExpr}.astype(float).replace(0, 1)) <= ${tolerance / 100}`
      }
      return `abs(${leftExpr}.astype(float) - ${rightExpr}.astype(float)) <= ${tolerance}`
    default:
      return `${leftExpr} == ${rightExpr}`
  }
}

function buildSideExpr(prefix, sideConfig) {
  if (!sideConfig || !sideConfig.parts || sideConfig.parts.length === 0) {
    return `${prefix}['']`
  }
  
  const { parts, transforms = [], advancedTransforms = [] } = sideConfig
  
  // Build expression từ parts
  let expr
  if (parts.length === 1 && parts[0].type === 'column') {
    expr = `${prefix}['${parts[0].value}']`
  } else {
    // Ghép nhiều phần (column + text)
    const partExprs = parts.map(p => {
      if (p.type === 'column') {
        return `${prefix}['${p.value}'].astype(str)`
      } else {
        return `'${p.value}'`
      }
    })
    expr = `(${partExprs.join(' + ')})`
  }
  
  // Apply simple transforms
  if (transforms.includes('strip')) expr += '.str.strip()'
  if (transforms.includes('upper')) expr += '.str.upper()'
  if (transforms.includes('lower')) expr += '.str.lower()'
  if (transforms.includes('trim_zero')) expr += ".str.lstrip('0')"

  // Apply advanced transforms
  for (const adv of advancedTransforms) {
    if (adv.type === 'substring') {
      const start = adv.params?.start || 0
      const end = adv.params?.end || null
      expr = `${expr}.astype(str).str.slice(${start}, ${end})`
    } else if (adv.type === 'regex_extract') {
      const pattern = adv.params?.pattern || '(.+)'
      expr = `${expr}.astype(str).str.extract(r'${pattern}', expand=False)`
    } else if (adv.type === 'replace') {
      const old = adv.params?.old || ''
      const newStr = adv.params?.new || ''
      expr = `${expr}.astype(str).str.replace('${old}', '${newStr}', regex=False)`
    } else if (adv.type === 'remove_prefix') {
      const value = adv.params?.value || ''
      expr = `${expr}.astype(str).str.lstrip('${value}')`
    } else if (adv.type === 'remove_suffix') {
      const value = adv.params?.value || ''
      expr = `${expr}.astype(str).str.rstrip('${value}')`
    }
  }
  
  return expr
}

// Parse expression để extract UI config (best effort)
export function parseExpression(expression) {
  // This is a simplified parser - complex expressions will default to advanced mode
  const config = {
    mode: 'advanced',
    left: { parts: [], transforms: [] },
    right: { parts: [], transforms: [] },
    compareType: 'exact',
    tolerance: 0,
    toleranceType: 'absolute'
  }
  
  if (!expression) return config
  
  // Try to parse simple exact match: b1['col'] == b4['col']
  const exactMatch = expression.match(/b1\['(\w+)'\](.*)== b4\['(\w+)'\](.*)/)
  if (exactMatch) {
    config.mode = 'simple'
    config.left.parts = [{ type: 'column', value: exactMatch[1] }]
    config.right.parts = [{ type: 'column', value: exactMatch[3] }]
    config.compareType = 'exact'
    
    // Extract transforms
    const leftTransforms = exactMatch[2]
    const rightTransforms = exactMatch[4]
    if (leftTransforms.includes('.str.strip()')) config.left.transforms.push('strip')
    if (leftTransforms.includes('.str.upper()')) config.left.transforms.push('upper')
    if (leftTransforms.includes('.str.lower()')) config.left.transforms.push('lower')
    if (rightTransforms.includes('.str.strip()')) config.right.transforms.push('strip')
    if (rightTransforms.includes('.str.upper()')) config.right.transforms.push('upper')
    if (rightTransforms.includes('.str.lower()')) config.right.transforms.push('lower')
    
    return config
  }
  
  // Try to parse tolerance match: abs(b1['amount'] - b4['total_amount']) <= 100
  const toleranceMatch = expression.match(/abs\(b1\['(\w+)'\].*- b4\['(\w+)'\].*\)\s*<=\s*([\d.]+)/)
  if (toleranceMatch) {
    config.mode = 'simple'
    config.left.parts = [{ type: 'column', value: toleranceMatch[1] }]
    config.right.parts = [{ type: 'column', value: toleranceMatch[2] }]
    config.compareType = 'tolerance'
    config.tolerance = parseFloat(toleranceMatch[3])
    return config
  }
  
  // Can't parse - use advanced mode
  return config
}

export default function RuleBuilder({ 
  rule, 
  onChange, 
  b1Columns = [], 
  b4Columns = [],
  onRemove,
  index,
  leftLabel = "📄 Bên trái - Sao kê (B1)",
  rightLabel = "🗄️ Bên phải - Hệ thống (B4)",
  leftPrefix = "b1",
  rightPrefix = "b4"
}) {
  const [mode, setMode] = useState('simple')
  const [uiConfig, setUiConfig] = useState({
    left: { parts: [], transforms: [] },
    right: { parts: [], transforms: [] },
    compareType: 'exact',
    tolerance: 0,
    toleranceType: 'absolute'
  })
  const [expression, setExpression] = useState('')
  const [isCollapsed, setIsCollapsed] = useState(false)
  
  // Initialize from rule
  useEffect(() => {
    if (rule?._ui_config) {
      setMode(rule._ui_config.mode || 'simple')
      setUiConfig({
        left: rule._ui_config.left || { parts: [], transforms: [] },
        right: rule._ui_config.right || { parts: [], transforms: [] },
        compareType: rule._ui_config.compareType || 'exact',
        tolerance: rule._ui_config.tolerance || 0,
        toleranceType: rule._ui_config.toleranceType || 'absolute'
      })
    }
    if (rule?.expression) {
      setExpression(rule.expression)
    }
  }, [])
  
  // Update expression when uiConfig changes (in simple mode)
  // Use JSON.stringify to force deep comparison
  const uiConfigStr = JSON.stringify(uiConfig)
  useEffect(() => {
    if (mode === 'simple') {
      const newExpr = generateExpression(uiConfig, leftPrefix, rightPrefix)
      setExpression(newExpr)
      console.log('[RuleBuilder] Generated expression:', newExpr, 'with prefixes:', leftPrefix, rightPrefix)
    }
  }, [uiConfigStr, mode, leftPrefix, rightPrefix])
  
  // Notify parent of changes
  const handleChange = useCallback(() => {
    const updatedRule = {
      ...rule,
      expression,
      _ui_config: {
        mode,
        ...uiConfig
      }
    }
    console.log('[RuleBuilder] Sending to parent:', updatedRule.expression)
    onChange(updatedRule)
  }, [rule, expression, mode, uiConfigStr, onChange])
  
  useEffect(() => {
    handleChange()
  }, [expression, mode, uiConfigStr])
  
  const handleModeSwitch = (newMode) => {
    if (newMode === 'advanced' && mode === 'simple') {
      // Switching to advanced - expression already generated
      setMode('advanced')
    } else if (newMode === 'simple' && mode === 'advanced') {
      // Try to parse expression back to simple config
      const parsed = parseExpression(expression)
      if (parsed.mode === 'simple') {
        setUiConfig({
          left: parsed.left,
          right: parsed.right,
          compareType: parsed.compareType,
          tolerance: parsed.tolerance,
          toleranceType: parsed.toleranceType
        })
        setMode('simple')
      } else {
        // Can't parse - keep advanced mode
        alert('Expression quá phức tạp, không thể chuyển về chế độ đơn giản')
      }
    }
  }
  
  const handleUiConfigChange = (field, value) => {
    setUiConfig(prev => ({
      ...prev,
      [field]: value
    }))
  }
  
  return (
    <div className="border rounded-lg bg-white shadow-sm mb-4">
      {/* Header */}
      <div 
        className="flex items-center justify-between p-4 bg-gray-50 rounded-t-lg cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-3">
          <span className="text-gray-400">{isCollapsed ? '▶' : '▼'}</span>
          <span className="font-medium text-gray-800">
            Rule {index + 1}: {rule?.rule_name || 'New Rule'}
          </span>
          <span className={`px-2 py-0.5 text-xs rounded ${
            mode === 'simple' ? 'bg-green-100 text-green-700' : 'bg-purple-100 text-purple-700'
          }`}>
            {mode === 'simple' ? 'Đơn giản' : 'Nâng cao'}
          </span>
        </div>
        <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
          <select
            value={mode}
            onChange={(e) => handleModeSwitch(e.target.value)}
            className="text-sm border rounded px-2 py-1"
          >
            <option value="simple">Chế độ đơn giản</option>
            <option value="advanced">Chế độ nâng cao</option>
          </select>
          {onRemove && (
            <button
              onClick={onRemove}
              className="p-1 text-red-500 hover:bg-red-50 rounded"
              title="Xóa rule"
            >
              ✕
            </button>
          )}
        </div>
      </div>
      
      {/* Body */}
      {!isCollapsed && (
        <div className="p-4 space-y-4">
          {/* Rule Name */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tên Rule
              </label>
              <input
                type="text"
                value={rule?.rule_name || ''}
                onChange={(e) => onChange({ ...rule, rule_name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="VD: key_match, amount_match"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Loại Rule
              </label>
              <select
                value={uiConfig.compareType}
                onChange={(e) => handleUiConfigChange('compareType', e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="exact">So khớp chính xác (=)</option>
                <option value="like">Chứa (LIKE)</option>
                <option value="tolerance">Cho phép lệch (số tiền)</option>
                <option value="fuzzy">Gần đúng (Fuzzy)</option>
              </select>
            </div>
          </div>
          
          {mode === 'simple' ? (
            <ExpressionBuilder
              uiConfig={uiConfig}
              onChange={handleUiConfigChange}
              b1Columns={b1Columns}
              b4Columns={b4Columns}
              leftLabel={leftLabel}
              rightLabel={rightLabel}
            />
          ) : (
            <ExpressionEditor
              expression={expression}
              onChange={setExpression}
            />
          )}
          
          {/* Tolerance settings */}
          {uiConfig.compareType === 'tolerance' && mode === 'simple' && (
            <div className="bg-yellow-50 p-3 rounded-lg">
              <div className="flex items-center gap-4">
                <label className="text-sm font-medium text-gray-700">
                  Độ lệch cho phép:
                </label>
                <input
                  type="number"
                  value={uiConfig.tolerance}
                  onChange={(e) => handleUiConfigChange('tolerance', parseFloat(e.target.value) || 0)}
                  className="w-24 px-3 py-1 border rounded focus:ring-2 focus:ring-blue-500 outline-none"
                />
                <select
                  value={uiConfig.toleranceType}
                  onChange={(e) => handleUiConfigChange('toleranceType', e.target.value)}
                  className="px-3 py-1 border rounded focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="absolute">Tuyệt đối (VNĐ)</option>
                  <option value="percent">Phần trăm (%)</option>
                </select>
              </div>
            </div>
          )}
          
          {/* Expression Preview */}
          <div className="bg-gray-100 p-3 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">
                Expression (Pandas)
              </label>
              <button
                onClick={() => navigator.clipboard.writeText(expression)}
                className="text-xs text-blue-600 hover:underline"
              >
                Sao chép
              </button>
            </div>
            <code className="block text-sm text-gray-800 bg-white p-2 rounded border font-mono break-all">
              {expression || '(chưa có expression)'}
            </code>
          </div>
        </div>
      )}
    </div>
  )
}

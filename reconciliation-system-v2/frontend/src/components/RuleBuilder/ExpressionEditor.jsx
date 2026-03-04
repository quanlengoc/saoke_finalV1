/**
 * ExpressionEditor Component
 * 
 * Editor cho Advanced Mode - cho phép người dùng viết expression trực tiếp
 * Có syntax highlighting đơn giản và validation cơ bản
 */

import { useState, useEffect } from 'react'

const EXPRESSION_EXAMPLES = [
  {
    label: 'So khớp exact',
    code: "b1['column1'] == b4['column2']"
  },
  {
    label: 'So khớp với transform',
    code: "b1['column1'].str.strip().str.upper() == b4['column2'].str.strip().str.upper()"
  },
  {
    label: 'Ghép 2 cột',
    code: "(b1['col1'].astype(str) + '-' + b1['col2'].astype(str)) == b4['combined_col']"
  },
  {
    label: 'So sánh số với tolerance',
    code: "abs(b1['amount'].astype(float) - b4['total_amount'].astype(float)) <= 100"
  },
  {
    label: 'So sánh % lệch',
    code: "(abs(b1['amount'].astype(float) - b4['amount'].astype(float)) / b4['amount'].astype(float)) <= 0.01"
  },
  {
    label: 'Chứa substring',
    code: "b1['description'].str.contains(b4['keyword'], regex=False, na=False)"
  }
]

const SYNTAX_KEYWORDS = [
  // Pandas methods
  '.str.strip()', '.str.upper()', '.str.lower()', '.str.lstrip(',
  '.astype(str)', '.astype(float)', '.astype(int)',
  '.str.contains(', '.str.replace(',
  // Python functions
  'abs(', 'len(',
  // Comparison
  '==', '<=', '>=', '!=', '<', '>',
  // DataFrame refs
  "b1['", "b4['", "']"
]

function highlightSyntax(code) {
  if (!code) return ''
  
  let highlighted = code
  // Escape HTML
  highlighted = highlighted.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  
  // Highlight strings
  highlighted = highlighted.replace(/'([^']+)'/g, '<span class="text-green-600">\'$1\'</span>')
  
  // Highlight brackets
  highlighted = highlighted.replace(/\[/g, '<span class="text-purple-600">[</span>')
  highlighted = highlighted.replace(/\]/g, '<span class="text-purple-600">]</span>')
  
  // Highlight DataFrame refs
  highlighted = highlighted.replace(/b1/g, '<span class="text-blue-600 font-semibold">b1</span>')
  highlighted = highlighted.replace(/b4/g, '<span class="text-orange-600 font-semibold">b4</span>')
  
  // Highlight methods
  highlighted = highlighted.replace(/\.str\./g, '<span class="text-purple-500">.str.</span>')
  highlighted = highlighted.replace(/\.astype/g, '<span class="text-purple-500">.astype</span>')
  
  // Highlight comparison operators
  highlighted = highlighted.replace(/==/g, '<span class="text-red-500">==</span>')
  highlighted = highlighted.replace(/&lt;=/g, '<span class="text-red-500">&lt;=</span>')
  highlighted = highlighted.replace(/&gt;=/g, '<span class="text-red-500">&gt;=</span>')
  
  return highlighted
}

function validateExpression(expression) {
  const errors = []
  
  if (!expression) {
    errors.push('Expression không được để trống')
    return errors
  }
  
  // Check balanced brackets
  const openBrackets = (expression.match(/\[/g) || []).length
  const closeBrackets = (expression.match(/\]/g) || []).length
  if (openBrackets !== closeBrackets) {
    errors.push('Dấu ngoặc vuông [] không cân bằng')
  }
  
  // Check balanced parentheses
  const openParens = (expression.match(/\(/g) || []).length
  const closeParens = (expression.match(/\)/g) || []).length
  if (openParens !== closeParens) {
    errors.push('Dấu ngoặc tròn () không cân bằng')
  }
  
  // Check balanced quotes
  const quotes = (expression.match(/'/g) || []).length
  if (quotes % 2 !== 0) {
    errors.push('Dấu nháy đơn \' không cân bằng')
  }
  
  // Check for DataFrame references
  if (!expression.includes('b1[') && !expression.includes('b4[')) {
    errors.push("Expression phải chứa ít nhất một tham chiếu đến b1['...'] hoặc b4['...']")
  }
  
  // Check for comparison operator
  if (!expression.includes('==') && !expression.includes('<=') && 
      !expression.includes('>=') && !expression.includes('!=') &&
      !expression.includes('.str.contains(')) {
    errors.push('Expression nên chứa toán tử so sánh (==, <=, >=, !=) hoặc .str.contains()')
  }
  
  return errors
}

export default function ExpressionEditor({ expression, onChange }) {
  const [errors, setErrors] = useState([])
  const [showExamples, setShowExamples] = useState(false)
  
  useEffect(() => {
    const validationErrors = validateExpression(expression)
    setErrors(validationErrors)
  }, [expression])
  
  const insertExample = (code) => {
    onChange(code)
    setShowExamples(false)
  }
  
  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowExamples(!showExamples)}
            className={`px-3 py-1 text-sm rounded ${
              showExamples ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'
            } hover:bg-blue-100`}
          >
            📝 Ví dụ
          </button>
        </div>
        {errors.length > 0 && (
          <span className="text-sm text-red-500">
            ⚠️ {errors.length} lỗi
          </span>
        )}
      </div>
      
      {/* Examples dropdown */}
      {showExamples && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-sm text-blue-800 mb-2 font-medium">Chọn ví dụ:</p>
          <div className="space-y-1">
            {EXPRESSION_EXAMPLES.map((ex, idx) => (
              <button
                key={idx}
                onClick={() => insertExample(ex.code)}
                className="w-full text-left px-3 py-2 bg-white rounded border hover:bg-blue-100 transition"
              >
                <p className="text-sm font-medium text-gray-800">{ex.label}</p>
                <code className="text-xs text-gray-500">{ex.code}</code>
              </button>
            ))}
          </div>
        </div>
      )}
      
      {/* Editor */}
      <div className="relative">
        <textarea
          value={expression}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full h-32 px-4 py-3 font-mono text-sm border rounded-lg resize-none focus:ring-2 focus:outline-none ${
            errors.length > 0 
              ? 'border-red-300 focus:ring-red-200' 
              : 'border-gray-300 focus:ring-blue-200'
          }`}
          placeholder="Nhập Pandas expression... VD: b1['txn_id'] == b4['transaction_ref']"
          spellCheck={false}
        />
      </div>
      
      {/* Highlighted preview */}
      <div className="bg-gray-900 text-gray-100 p-3 rounded-lg font-mono text-sm overflow-x-auto">
        <div 
          className="whitespace-pre-wrap"
          dangerouslySetInnerHTML={{ __html: highlightSyntax(expression) || '<span class="text-gray-500">Preview...</span>' }}
        />
      </div>
      
      {/* Errors */}
      {errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <p className="text-sm font-medium text-red-800 mb-1">Lỗi phát hiện:</p>
          <ul className="list-disc list-inside text-sm text-red-700 space-y-0.5">
            {errors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Help */}
      <div className="text-xs text-gray-500 space-y-1">
        <p><strong>Gợi ý:</strong></p>
        <ul className="list-disc list-inside space-y-0.5 ml-2">
          <li><code className="bg-gray-100 px-1">b1['column']</code> - Truy cập cột từ sao kê (B1)</li>
          <li><code className="bg-gray-100 px-1">b4['column']</code> - Truy cập cột từ hệ thống (B4)</li>
          <li><code className="bg-gray-100 px-1">.str.strip().str.upper()</code> - Chuẩn hóa chuỗi</li>
          <li><code className="bg-gray-100 px-1">.astype(float)</code> - Chuyển sang số</li>
          <li><code className="bg-gray-100 px-1">abs(a - b) {'<='} tolerance</code> - So sánh với độ lệch</li>
        </ul>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { 
  ArrowLeftIcon,
  ArrowPathIcon,
  PlusIcon,
  TrashIcon,
  CheckIcon,
  XMarkIcon,
  ChevronUpIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline'
import { 
  configsApiV2, 
  dataSourcesApiV2, 
  workflowsApiV2, 
  outputsApiV2 
} from '../../services/api'

const SOURCE_TYPES = [
  { value: 'FILE_UPLOAD', label: 'File Upload', color: 'bg-blue-100 text-blue-800' },
  { value: 'DATABASE', label: 'Database', color: 'bg-green-100 text-green-800' },
  { value: 'SFTP', label: 'SFTP', color: 'bg-purple-100 text-purple-800' },
  { value: 'API', label: 'API', color: 'bg-orange-100 text-orange-800' },
]

const JOIN_TYPES = ['left', 'inner', 'right', 'outer']

// ===== HELPER FUNCTIONS (outside component for reuse) =====
// Convert columns array sang object cho backend
const convertColumnsToObject = (columns) => {
  if (!columns) return {}
  if (!Array.isArray(columns)) return columns // đã là object
  
  const result = {}
  columns.forEach(col => {
    if (col.alias && col.source) {
      result[col.alias] = col.source
    }
  })
  return result
}

export default function ConfigEditV2Page() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isNew = !id || id === 'new'
  
  // Config state
  const [config, setConfig] = useState({
    partner_code: '',
    partner_name: '',
    service_code: '',
    service_name: '',
    is_active: true,
    valid_from: new Date().toISOString().split('T')[0],
    valid_to: '',
    report_template_path: '',
  })
  
  // Related data
  const [dataSources, setDataSources] = useState([])
  const [workflowSteps, setWorkflowSteps] = useState([])
  const [outputConfigs, setOutputConfigs] = useState([])
  
  // UI state
  const [loading, setLoading] = useState(!isNew)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('basic')
  const [expandedSection, setExpandedSection] = useState(null)
  // hasChanges và markChanged được giữ lại để hiển thị indicator tổng thể
  const [hasChanges, setHasChanges] = useState(false)
  
  // Track changes (được gọi từ các hàm update)
  const markChanged = () => setHasChanges(true)

  useEffect(() => {
    if (!isNew) {
      loadConfig()
    }
  }, [id])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const [configRes, sourcesRes, workflowsRes, outputsRes] = await Promise.all([
        configsApiV2.get(id),
        dataSourcesApiV2.getByConfig(id),
        workflowsApiV2.getByConfig(id),
        outputsApiV2.getByConfig(id)
      ])
      
      setConfig({
        partner_code: configRes.data.partner_code,
        partner_name: configRes.data.partner_name,
        service_code: configRes.data.service_code,
        service_name: configRes.data.service_name,
        is_active: configRes.data.is_active,
        valid_from: configRes.data.valid_from,
        valid_to: configRes.data.valid_to || '',
        report_template_path: configRes.data.report_template_path || '',
        report_cell_mapping: configRes.data.report_cell_mapping || { sheets: [] },
      })
      setDataSources(sourcesRes.data)
      // Normalize workflow steps - đảm bảo output_type có giá trị
      console.log('📦 Raw workflows from API:', workflowsRes.data)
      const normalizedWorkflows = workflowsRes.data.map(ws => ({
        ...ws,
        output_type: ws.output_type || (ws.is_final_output ? 'report' : 'intermediate'),
        output_columns: ws.output_columns || []
      }))
      console.log('📦 Normalized workflows:', normalizedWorkflows)
      setWorkflowSteps(normalizedWorkflows.sort((a, b) => a.step_order - b.step_order))
      setOutputConfigs(outputsRes.data.sort((a, b) => a.display_order - b.display_order))
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải cấu hình')
    } finally {
      setLoading(false)
    }
  }

  const handleConfigChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }))
    markChanged()
  }

  // ===== DATA SOURCES =====
  const addDataSource = () => {
    const newSource = {
      id: `new_${Date.now()}`,
      isNew: true,
      source_name: `B${dataSources.length + 1}`,
      source_type: 'FILE_UPLOAD',
      display_name: '',
      is_required: false,
      display_order: dataSources.length,
      file_config: { header_row: 1, data_start_row: 2, sheet_name: '', columns: {} },
      db_config: null,
      sftp_config: null,
      api_config: null,
    }
    setDataSources([...dataSources, newSource])
    markChanged()
  }

  const updateDataSource = (index, field, value) => {
    const updated = [...dataSources]
    
    // Khi thay đổi source_type, reset config tương ứng
    if (field === 'source_type') {
      const resetConfigs = {
        file_config: null,
        db_config: null,
        sftp_config: null,
        api_config: null
      }
      
      // Khởi tạo config mặc định cho loại mới
      if (value === 'FILE_UPLOAD') {
        resetConfigs.file_config = { header_row: 1, data_start_row: 2, sheet_name: '', columns: {} }
      } else if (value === 'DATABASE') {
        resetConfigs.db_config = { db_connection: '', sql_file: '' }
      } else if (value === 'SFTP') {
        resetConfigs.sftp_config = { host: '', path_pattern: '', username: '', columns: {} }
      } else if (value === 'API') {
        resetConfigs.api_config = { url: '', method: 'GET', headers: {} }
      }
      
      updated[index] = { ...updated[index], [field]: value, ...resetConfigs, isModified: true }
    } else {
      updated[index] = { ...updated[index], [field]: value, isModified: true }
    }
    setDataSources(updated)
    markChanged()
  }
  
  // Helper để cập nhật nested config
  const updateDataSourceConfig = (index, configType, configField, value) => {
    const updated = [...dataSources]
    const currentConfig = updated[index][configType] || {}
    updated[index] = {
      ...updated[index],
      [configType]: { ...currentConfig, [configField]: value },
      isModified: true
    }
    setDataSources(updated)
  }

  const removeDataSource = (index) => {
    if (!confirm('Xóa nguồn dữ liệu này?')) return
    const updated = [...dataSources]
    if (updated[index].isNew) {
      updated.splice(index, 1)
    } else {
      updated[index] = { ...updated[index], isDeleted: true }
    }
    setDataSources(updated)
    markChanged()
  }

  // ===== WORKFLOW STEPS =====
  const addWorkflowStep = () => {
    const newStep = {
      id: `new_${Date.now()}`,
      isNew: true,
      step_order: workflowSteps.length + 1,
      step_name: `Step ${workflowSteps.length + 1}`,
      left_source: '',
      right_source: '',
      join_type: 'left',
      output_name: `A${workflowSteps.length + 1}`,
      output_type: 'intermediate',  // Thêm output_type mặc định
      is_final_output: false,
      matching_rules: { match_type: 'expression', rules: [], status_logic: {} },
      output_columns: [],  // Thêm output_columns mặc định
    }
    setWorkflowSteps([...workflowSteps, newStep])
    markChanged()
  }

  const updateWorkflowStep = (stepId, field, value) => {
    const stepIndex = workflowSteps.findIndex(ws => ws.id === stepId)
    if (stepIndex === -1) return
    
    const updated = [...workflowSteps]
    updated[stepIndex] = { ...updated[stepIndex], [field]: value, isModified: true }
    setWorkflowSteps(updated)
    markChanged()
  }
  
  // Update nhiều field cùng lúc để tránh race condition
  const updateWorkflowStepMulti = (stepId, updates) => {
    const stepIndex = workflowSteps.findIndex(ws => ws.id === stepId)
    if (stepIndex === -1) return
    
    const updated = [...workflowSteps]
    updated[stepIndex] = { ...updated[stepIndex], ...updates, isModified: true }
    setWorkflowSteps(updated)
    markChanged()
  }

  const removeWorkflowStep = (stepId) => {
    if (!confirm('Xóa bước workflow này?')) return
    const stepIndex = workflowSteps.findIndex(ws => ws.id === stepId)
    if (stepIndex === -1) return
    
    const updated = [...workflowSteps]
    if (updated[stepIndex].isNew) {
      updated.splice(stepIndex, 1)
    } else {
      updated[stepIndex] = { ...updated[stepIndex], isDeleted: true }
    }
    setWorkflowSteps(updated)
    markChanged()
  }

  const moveWorkflowStep = (stepId, direction) => {
    // Chỉ di chuyển trong visibleSteps (không bị deleted)
    const visibleSteps = workflowSteps.filter(ws => !ws.isDeleted)
    const visibleIndex = visibleSteps.findIndex(ws => ws.id === stepId)
    if (visibleIndex === -1) return
    
    const newVisibleIndex = visibleIndex + direction
    if (newVisibleIndex < 0 || newVisibleIndex >= visibleSteps.length) return
    
    // Swap trong visibleSteps
    const reorderedVisible = [...visibleSteps]
    ;[reorderedVisible[visibleIndex], reorderedVisible[newVisibleIndex]] = 
     [reorderedVisible[newVisibleIndex], reorderedVisible[visibleIndex]]
    
    // Cập nhật step_order và isModified
    reorderedVisible.forEach((step, i) => {
      step.step_order = i + 1
      step.isModified = true
    })
    
    // Merge lại với deleted items (giữ nguyên)
    const deletedSteps = workflowSteps.filter(ws => ws.isDeleted)
    setWorkflowSteps([...reorderedVisible, ...deletedSteps])
    markChanged()
  }

  // ===== OUTPUT CONFIGS =====
  const addOutputConfig = () => {
    const newOutput = {
      id: `new_${Date.now()}`,
      isNew: true,
      output_name: `A${outputConfigs.length + 1}`,
      display_name: '',
      use_for_report: true,
      display_order: outputConfigs.length,
      columns_config: { columns: [] },
    }
    setOutputConfigs([...outputConfigs, newOutput])
    markChanged()
  }

  const updateOutputConfig = (index, field, value) => {
    const updated = [...outputConfigs]
    updated[index] = { ...updated[index], [field]: value, isModified: true }
    setOutputConfigs(updated)
    markChanged()
  }

  const removeOutputConfig = (index) => {
    if (!confirm('Xóa output config này?')) return
    const updated = [...outputConfigs]
    if (updated[index].isNew) {
      updated.splice(index, 1)
    } else {
      updated[index] = { ...updated[index], isDeleted: true }
    }
    setOutputConfigs(updated)
    markChanged()
  }

  // Get available sources for workflow dropdown
  const getAvailableSources = () => {
    const sources = dataSources
      .filter(ds => !ds.isDeleted)
      .map(ds => ds.source_name)
    
    // Add outputs from previous steps
    workflowSteps
      .filter(ws => !ws.isDeleted)
      .forEach(ws => {
        if (!sources.includes(ws.output_name)) {
          sources.push(ws.output_name)
        }
      })
    
    return sources
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header với nút Save nổi bật */}
      <div className="flex justify-between items-start">
        <div>
          <Link 
            to="/admin/configs-v2" 
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <ArrowLeftIcon className="h-4 w-4 mr-1" />
            Quay lại danh sách
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              {isNew ? 'Tạo cấu hình mới' : 'Chỉnh sửa cấu hình'}
            </h1>
            {hasChanges && (
              <span className="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded-full font-medium">
                ● Có thay đổi chưa lưu
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-3 items-center">
          <Link
            to="/admin/configs-v2"
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-700"
          >
            ← Quay lại danh sách
          </Link>
        </div>
      </div>

      {/* Hướng dẫn */}
      <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 rounded-lg flex items-center">
        <span className="text-lg mr-2">💡</span>
        <span>
          Mỗi tab có nút <strong>"LƯU"</strong> riêng. Thay đổi sẽ được lưu ngay vào database khi bạn bấm nút Lưu trong từng tab.
        </span>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">{error}</div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { key: 'basic', label: 'Thông tin cơ bản' },
            { key: 'sources', label: `Nguồn dữ liệu (${dataSources.filter(d => !d.isDeleted).length})` },
            { key: 'workflow', label: `Workflow (${workflowSteps.filter(w => !w.isDeleted).length})` },
            { key: 'report', label: '📊 Report Template' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-lg shadow p-6">
        {/* Basic Info Tab */}
        {activeTab === 'basic' && (
          <BasicInfoTab
            config={config}
            handleConfigChange={handleConfigChange}
            configId={id}
            isNew={isNew}
            navigate={navigate}
          />
        )}

        {/* Data Sources Tab */}
        {activeTab === 'sources' && (
          <DataSourcesTab
            dataSources={dataSources}
            setDataSources={setDataSources}
            configId={id}
            isNewConfig={isNew}
            onReload={loadConfig}
          />
        )}

        {/* Workflow Tab */}
        {activeTab === 'workflow' && (
          <WorkflowTab
            workflowSteps={workflowSteps}
            setWorkflowSteps={setWorkflowSteps}
            dataSources={dataSources}
            configId={id}
            isNewConfig={isNew}
            addWorkflowStep={addWorkflowStep}
            updateWorkflowStep={updateWorkflowStep}
            updateWorkflowStepMulti={updateWorkflowStepMulti}
            removeWorkflowStep={removeWorkflowStep}
            moveWorkflowStep={moveWorkflowStep}
            getAvailableSources={getAvailableSources}
            onReload={loadConfig}
          />
        )}

        {/* Report Template Tab */}
        {activeTab === 'report' && (
          <ReportTemplateTab
            config={config}
            handleConfigChange={handleConfigChange}
            configId={id}
            isNewConfig={isNew}
            workflowSteps={workflowSteps}
          />
        )}
      </div>
    </div>
  )
}

// ============================================
// BASIC INFO TAB COMPONENT (với nút lưu riêng)
// ============================================
function BasicInfoTab({ config, handleConfigChange, configId, isNew, navigate }) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  
  const saveBasicInfo = async () => {
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    
    try {
      // Chuẩn bị data - chuyển empty string thành null cho các field optional
      const configData = {
        ...config,
        valid_to: config.valid_to || null,
        report_template_path: config.report_template_path || null,
      }
      console.log('📤 Sending config data:', configData)
      
      if (isNew) {
        // Tạo mới config
        const response = await configsApiV2.create(configData)
        console.log('✅ Created config response:', response)
        // axios response có data trong response.data
        const newId = response?.data?.id
        if (!newId) {
          console.error('Response không có id:', response)
          throw new Error('Không nhận được ID cấu hình mới từ server')
        }
        setSaveSuccess(true)
        // Redirect to edit page với ID mới
        setTimeout(() => {
          navigate(`/admin/configs-v2/${newId}`, { replace: true })
        }, 1000)
      } else {
        // Cập nhật config
        const response = await configsApiV2.update(configId, configData)
        console.log('✅ Updated config:', response)
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      }
    } catch (error) {
      console.error('❌ Failed to save config:', error)
      setSaveError(error.response?.data?.detail || error.message || 'Không thể lưu cấu hình')
    } finally {
      setSaving(false)
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header với nút lưu */}
      <div className="flex justify-between items-center border-b pb-4">
        <div className="flex items-center gap-4">
          <h3 className="font-medium text-gray-700">Thông tin cơ bản</h3>
          {saveSuccess && (
            <span className="text-sm text-green-600">✓ Đã lưu thành công!</span>
          )}
        </div>
        <button
          onClick={saveBasicInfo}
          disabled={saving}
          className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
        >
          {saving ? (
            <>
              <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Đang lưu...
            </>
          ) : (
            <>💾 {isNew ? 'TẠO CẤU HÌNH' : 'LƯU THÔNG TIN'}</>
          )}
        </button>
      </div>
      
      {/* Error message */}
      {saveError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠️ {saveError}
        </div>
      )}
      
      {/* Info for new config */}
      {isNew && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-800 text-sm">
          💡 Sau khi tạo cấu hình, bạn có thể tiếp tục cấu hình Nguồn dữ liệu, Workflow và Output.
        </div>
      )}
      
      {/* Form fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Partner Code *
          </label>
          <input
            type="text"
            value={config.partner_code}
            onChange={(e) => handleConfigChange('partner_code', e.target.value.toUpperCase())}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="VD: SACOMBANK"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Partner Name *
          </label>
          <input
            type="text"
            value={config.partner_name}
            onChange={(e) => handleConfigChange('partner_name', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="VD: Ngân hàng Sacombank"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Service Code *
          </label>
          <input
            type="text"
            value={config.service_code}
            onChange={(e) => handleConfigChange('service_code', e.target.value.toUpperCase())}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="VD: TOPUP"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Service Name *
          </label>
          <input
            type="text"
            value={config.service_name}
            onChange={(e) => handleConfigChange('service_name', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="VD: Nạp tiền điện thoại"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Hiệu lực từ *
          </label>
          <input
            type="date"
            value={config.valid_from}
            onChange={(e) => handleConfigChange('valid_from', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Hiệu lực đến
          </label>
          <input
            type="date"
            value={config.valid_to}
            onChange={(e) => handleConfigChange('valid_to', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Report Template Path
          </label>
          <input
            type="text"
            value={config.report_template_path}
            onChange={(e) => handleConfigChange('report_template_path', e.target.value)}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="templates/shared/REPORT_TEMPLATE.xlsx"
          />
        </div>
        <div className="md:col-span-2">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={config.is_active}
              onChange={(e) => handleConfigChange('is_active', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 mr-2"
            />
            <span className="text-sm font-medium text-gray-700">Active (Đang sử dụng)</span>
          </label>
        </div>
      </div>
    </div>
  )
}

// ============================================
// DATA SOURCES TAB COMPONENT
// ============================================
const SOURCE_TYPE_STYLES = {
  FILE_UPLOAD: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'File Upload' },
  DATABASE: { bg: 'bg-green-100', text: 'text-green-800', label: 'Database' },
  SFTP: { bg: 'bg-purple-100', text: 'text-purple-800', label: 'SFTP' },
  API: { bg: 'bg-orange-100', text: 'text-orange-800', label: 'API' },
}

function DataSourcesTab({ dataSources, setDataSources, configId, isNewConfig, onReload }) {
  const [editingSource, setEditingSource] = useState(null) // index of source being edited
  const [editForm, setEditForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [deleting, setDeleting] = useState(null) // index đang xóa

  const openEditor = (index) => {
    const source = dataSources[index]
    setEditForm(JSON.parse(JSON.stringify(source))) // deep copy
    setEditingSource(index)
    setSaveError(null)
  }

  const closeEditor = () => {
    setEditingSource(null)
    setEditForm(null)
    setSaveError(null)
  }

  // Thêm nguồn mới (local state only cho đến khi save)
  const addDataSource = () => {
    const newSource = {
      id: `new_${Date.now()}`,
      source_name: `B${dataSources.length + 1}`,
      source_type: 'FILE_UPLOAD',
      display_name: '',
      is_required: true,
      file_config: { header_row: 1, data_start_row: 2, sheet_name: '', columns: [] },
      db_config: null,
      sftp_config: null,
      api_config: null,
      isNew: true,
      isModified: false
    }
    setDataSources(prev => [...prev, newSource])
    // Mở editor ngay cho source mới
    setEditForm(JSON.parse(JSON.stringify(newSource)))
    setEditingSource(dataSources.length)
  }

  // LƯU TRỰC TIẾP VÀO DATABASE
  const saveSource = async () => {
    if (isNewConfig) {
      // Nếu là config mới, phải lưu config trước
      setSaveError('Vui lòng lưu cấu hình chính trước khi thêm nguồn dữ liệu.')
      return
    }

    setSaving(true)
    setSaveError(null)

    try {
      // Convert columns từ array sang object cho backend
      const formData = { ...editForm }
      if (formData.file_config?.columns && Array.isArray(formData.file_config.columns)) {
        formData.file_config.columns = convertColumnsToObject(formData.file_config.columns)
      }

      // Xóa các field UI-only
      delete formData.isNew
      delete formData.isModified
      delete formData.isDeleted

      if (editForm.isNew || String(editForm.id).startsWith('new_')) {
        // TẠO MỚI - thêm config_id vào data
        formData.config_id = parseInt(configId)
        delete formData.id  // Xóa ID tạm
        const response = await dataSourcesApiV2.create(formData)
        console.log('✅ Created data source:', response.data)
        
        // Cập nhật local state với ID từ server
        const updated = [...dataSources]
        updated[editingSource] = { ...response.data, isNew: false, isModified: false }
        setDataSources(updated)
      } else {
        // CẬP NHẬT
        const response = await dataSourcesApiV2.update(editForm.id, formData)
        console.log('✅ Updated data source:', response.data)
        
        // Cập nhật local state
        const updated = [...dataSources]
        updated[editingSource] = { ...response.data, isNew: false, isModified: false }
        setDataSources(updated)
      }

      closeEditor()
    } catch (error) {
      console.error('❌ Failed to save data source:', error)
      setSaveError(error.response?.data?.detail || error.message || 'Không thể lưu nguồn dữ liệu')
    } finally {
      setSaving(false)
    }
  }

  // XÓA TRỰC TIẾP TỪ DATABASE  
  const removeDataSource = async (index) => {
    const source = dataSources[index]
    
    // Nếu là source mới chưa lưu, xóa khỏi local state luôn
    if (source.isNew || String(source.id).startsWith('new_')) {
      setDataSources(prev => prev.filter((_, i) => i !== index))
      return
    }

    if (isNewConfig) {
      setDataSources(prev => prev.filter((_, i) => i !== index))
      return
    }

    if (!confirm(`Xóa nguồn "${source.source_name}"? Thao tác này không thể hoàn tác.`)) {
      return
    }

    setDeleting(index)
    try {
      await dataSourcesApiV2.delete(source.id)
      console.log('✅ Deleted data source:', source.id)
      setDataSources(prev => prev.filter((_, i) => i !== index))
    } catch (error) {
      console.error('❌ Failed to delete data source:', error)
      alert('Không thể xóa nguồn dữ liệu: ' + (error.response?.data?.detail || error.message))
    } finally {
      setDeleting(null)
    }
  }

  const handleFormChange = (field, value) => {
    setEditForm(prev => ({ ...prev, [field]: value }))
  }

  const handleConfigChange = (configType, field, value) => {
    setEditForm(prev => ({
      ...prev,
      [configType]: { ...(prev[configType] || {}), [field]: value }
    }))
  }

  // Column mapping helpers - sử dụng array với stable ID thay vì object
  // Format: [{ id: 'col_1', alias: 'txn_id', source: 'A' }, ...]
  const getColumnsArray = () => {
    const columns = editForm.file_config?.columns
    if (!columns) return []
    
    // Nếu đã là array, return luôn
    if (Array.isArray(columns)) return columns
    
    // Convert từ object sang array
    return Object.entries(columns).map(([alias, source], idx) => ({
      id: `col_${idx}_${Date.now()}`,
      alias,
      source
    }))
  }

  const setColumnsArray = (newArray) => {
    // Lưu dạng array
    handleConfigChange('file_config', 'columns', newArray)
  }

  const addColumnMapping = () => {
    const currentColumns = getColumnsArray()
    setColumnsArray([
      ...currentColumns,
      { id: `col_${Date.now()}`, alias: '', source: '' }
    ])
  }

  const updateColumnMapping = (id, field, value) => {
    const currentColumns = getColumnsArray()
    const updated = currentColumns.map(col => 
      col.id === id ? { ...col, [field]: value } : col
    )
    setColumnsArray(updated)
  }

  const removeColumnMapping = (id) => {
    const currentColumns = getColumnsArray()
    setColumnsArray(currentColumns.filter(col => col.id !== id))
  }

  const visibleSources = dataSources.filter(ds => !ds.isDeleted)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-600">
          {visibleSources.length} nguồn dữ liệu đã cấu hình
        </p>
        <button
          onClick={addDataSource}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 shadow-md font-medium transition-colors"
        >
          <PlusIcon className="h-4 w-4 mr-1" />
          Thêm nguồn mới
        </button>
      </div>

      {/* Sources List Table */}
      {visibleSources.length > 0 ? (
        <div className="border rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tên nguồn</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Loại</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tên hiển thị</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cấu hình</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bắt buộc</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Thao tác</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {dataSources.map((ds, index) => {
                if (ds.isDeleted) return null
                const typeStyle = SOURCE_TYPE_STYLES[ds.source_type] || SOURCE_TYPE_STYLES.FILE_UPLOAD
                // Đếm số cột - hỗ trợ cả array và object format
                const columns = ds.file_config?.columns
                const columnsCount = columns 
                  ? (Array.isArray(columns) ? columns.length : Object.keys(columns).length)
                  : 0
                
                return (
                  <tr key={ds.id} className={ds.isNew ? 'bg-green-50' : ''}>
                    <td className="px-4 py-3">
                      <div className="flex items-center">
                        {ds.isNew && <span className="text-green-600 text-xs mr-2">[MỚI]</span>}
                        <span className="font-medium">{ds.source_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${typeStyle.bg} ${typeStyle.text}`}>
                        {typeStyle.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {ds.display_name || '-'}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {ds.source_type === 'FILE_UPLOAD' && (
                        <span>Row: {ds.file_config?.data_start_row || 2}, {columnsCount} cột</span>
                      )}
                      {ds.source_type === 'DATABASE' && (
                        <span>{ds.db_config?.db_connection || 'Chưa cấu hình'}</span>
                      )}
                      {ds.source_type === 'SFTP' && (
                        <span>{ds.sftp_config?.host || 'Chưa cấu hình'}</span>
                      )}
                      {ds.source_type === 'API' && (
                        <span>{ds.api_config?.method || 'GET'}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {ds.is_required ? (
                        <CheckIcon className="h-5 w-5 text-green-600" />
                      ) : (
                        <XMarkIcon className="h-5 w-5 text-gray-300" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => openEditor(index)}
                        className="text-blue-600 hover:text-blue-800 text-sm font-medium px-2 py-1 rounded hover:bg-blue-50"
                      >
                        Sửa
                      </button>
                      <button
                        onClick={() => removeDataSource(index)}
                        disabled={deleting === index}
                        className="text-red-600 hover:text-red-800 text-sm font-medium disabled:opacity-50"
                      >
                        {deleting === index ? 'Đang xóa...' : 'Xóa'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500 border-2 border-dashed rounded-lg">
          <p>Chưa có nguồn dữ liệu nào.</p>
          <p className="text-sm mt-2">Click "Thêm nguồn mới" để bắt đầu cấu hình.</p>
        </div>
      )}

      {/* Edit Modal */}
      {editingSource !== null && editForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col m-4">
            <div className="flex-shrink-0 bg-white border-b px-6 py-4 flex justify-between items-center rounded-t-xl">
              <h3 className="text-lg font-semibold">
                {editForm.isNew ? 'Thêm nguồn dữ liệu mới' : `Sửa nguồn: ${editForm.source_name}`}
              </h3>
              <button onClick={closeEditor} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Basic Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tên nguồn (ID) *</label>
                  <input
                    type="text"
                    value={editForm.source_name}
                    onChange={(e) => handleFormChange('source_name', e.target.value.toUpperCase())}
                    className="w-full px-3 py-2 border rounded-lg"
                    placeholder="VD: B1, B2, B3..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Loại nguồn *</label>
                  <select
                    value={editForm.source_type}
                    onChange={(e) => {
                      const newType = e.target.value
                      const resetConfigs = {
                        file_config: null,
                        db_config: null,
                        sftp_config: null,
                        api_config: null
                      }
                      if (newType === 'FILE_UPLOAD') {
                        resetConfigs.file_config = { header_row: 1, data_start_row: 2, sheet_name: '', columns: {} }
                      } else if (newType === 'DATABASE') {
                        resetConfigs.db_config = { db_connection: '', sql_file: '' }
                      } else if (newType === 'SFTP') {
                        resetConfigs.sftp_config = { host: '', path_pattern: '', username: '', columns: {} }
                      } else if (newType === 'API') {
                        resetConfigs.api_config = { url: '', method: 'GET', headers: {} }
                      }
                      setEditForm(prev => ({ ...prev, source_type: newType, ...resetConfigs }))
                    }}
                    className="w-full px-3 py-2 border rounded-lg"
                  >
                    <option value="FILE_UPLOAD">File Upload</option>
                    <option value="DATABASE">Database</option>
                    <option value="SFTP">SFTP</option>
                    <option value="API">API</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tên hiển thị</label>
                  <input
                    type="text"
                    value={editForm.display_name || ''}
                    onChange={(e) => handleFormChange('display_name', e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg"
                    placeholder="VD: Dữ liệu đối tác"
                  />
                </div>
                <div className="flex items-end">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={editForm.is_required || false}
                      onChange={(e) => handleFormChange('is_required', e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 mr-2"
                    />
                    <span className="text-sm font-medium text-gray-700">Bắt buộc phải upload</span>
                  </label>
                </div>
              </div>

              {/* FILE_UPLOAD Config */}
              {editForm.source_type === 'FILE_UPLOAD' && (
                <div className="border-t pt-4">
                  <h4 className="font-medium text-blue-800 mb-4">📄 Cấu hình File Upload</h4>
                  
                  <div className={`grid ${getColumnsArray().length > 0 ? 'grid-cols-2' : 'grid-cols-3'} gap-4 mb-4`}>
                    {/* Ẩn Dòng Header khi đã cấu hình Column Mapping — không cần thiết vì cột được xác định bằng vị trí Excel */}
                    {getColumnsArray().length === 0 && (
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Dòng Header</label>
                        <input
                          type="number"
                          value={editForm.file_config?.header_row || 1}
                          onChange={(e) => handleConfigChange('file_config', 'header_row', parseInt(e.target.value) || 1)}
                          className="w-full px-3 py-2 border rounded-lg"
                          min="1"
                        />
                      </div>
                    )}
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Dòng bắt đầu dữ liệu</label>
                      <input
                        type="number"
                        value={editForm.file_config?.data_start_row || 2}
                        onChange={(e) => handleConfigChange('file_config', 'data_start_row', parseInt(e.target.value) || 2)}
                        className="w-full px-3 py-2 border rounded-lg"
                        min="1"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Tên Sheet (Excel)</label>
                      <input
                        type="text"
                        value={editForm.file_config?.sheet_name || ''}
                        onChange={(e) => handleConfigChange('file_config', 'sheet_name', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="Để trống = sheet đầu tiên"
                      />
                    </div>
                  </div>

                  {/* Column Mapping */}
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="flex justify-between items-center mb-3">
                      <h5 className="text-sm font-medium text-blue-800">Ánh xạ cột (Column Mapping)</h5>
                      <button
                        onClick={addColumnMapping}
                        className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
                      >
                        <PlusIcon className="h-4 w-4 mr-1" />
                        Thêm cột
                      </button>
                    </div>
                    
                    {getColumnsArray().length > 0 ? (
                      <div className="space-y-2">
                        <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 font-medium">
                          <div className="col-span-5">Tên trường (alias)</div>
                          <div className="col-span-5">Cột trong file (A, B, C...)</div>
                          <div className="col-span-2"></div>
                        </div>
                        {getColumnsArray().map((col) => (
                          <div key={col.id} className="grid grid-cols-12 gap-2">
                            <input
                              type="text"
                              value={col.alias}
                              onChange={(e) => updateColumnMapping(col.id, 'alias', e.target.value)}
                              className="col-span-5 px-2 py-1 border rounded text-sm"
                              placeholder="VD: txn_id"
                            />
                            <input
                              type="text"
                              value={col.source}
                              onChange={(e) => updateColumnMapping(col.id, 'source', e.target.value)}
                              className="col-span-5 px-2 py-1 border rounded text-sm"
                              placeholder="VD: A hoặc tên cột"
                            />
                            <button
                              onClick={() => removeColumnMapping(col.id)}
                              className="col-span-2 text-red-500 hover:text-red-700 flex items-center justify-center"
                            >
                              <TrashIcon className="h-4 w-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500 text-center py-4">
                        Chưa có ánh xạ cột. Click "Thêm cột" để cấu hình.
                        <br />
                        <span className="text-xs">VD: txn_id → A, amount → C</span>
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* DATABASE Config */}
              {editForm.source_type === 'DATABASE' && (
                <div className="border-t pt-4">
                  <h4 className="font-medium text-green-800 mb-4">🗄️ Cấu hình Database</h4>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Kết nối Database *</label>
                      <select
                        value={editForm.db_config?.db_connection || ''}
                        onChange={(e) => handleConfigChange('db_config', 'db_connection', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                      >
                        <option value="">-- Chọn kết nối --</option>
                        <option value="vnptmoney_main">vnptmoney_main</option>
                        <option value="vnptmoney_report">vnptmoney_report</option>
                        <option value="partner_db">partner_db</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">File SQL *</label>
                      <input
                        type="text"
                        value={editForm.db_config?.sql_file || ''}
                        onChange={(e) => handleConfigChange('db_config', 'sql_file', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="shared/query_b4.sql"
                      />
                    </div>
                  </div>
                  
                  {/* Output Columns - danh sách các cột sẽ trả ra từ query */}
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="flex justify-between items-center mb-3">
                      <label className="font-medium text-green-800">Ánh xạ cột (Column Mapping)</label>
                      <button
                        type="button"
                        onClick={() => {
                          const cols = editForm.db_config?.output_columns || []
                          handleConfigChange('db_config', 'output_columns', [...cols, { source: '', alias: '' }])
                        }}
                        className="text-sm text-green-600 hover:text-green-800"
                      >
                        + Thêm cột
                      </button>
                    </div>
                    <p className="text-xs text-green-600 mb-3">
                      Tên trường SQL → Tên alias (dùng để chọn cột trong Workflow)
                    </p>
                    
                    {(editForm.db_config?.output_columns || []).length > 0 ? (
                      <div className="space-y-2">
                        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 px-2">
                          <div className="col-span-5">Tên trường SQL</div>
                          <div className="col-span-5">Tên alias</div>
                          <div className="col-span-2"></div>
                        </div>
                        {(editForm.db_config?.output_columns || []).map((col, colIdx) => (
                          <div key={colIdx} className="grid grid-cols-12 gap-2 items-center">
                            <input
                              type="text"
                              value={col.source || col.name || ''}
                              onChange={(e) => {
                                const cols = [...(editForm.db_config?.output_columns || [])]
                                cols[colIdx] = { ...cols[colIdx], source: e.target.value }
                                handleConfigChange('db_config', 'output_columns', cols)
                              }}
                              className="col-span-5 px-2 py-1.5 border rounded text-sm"
                              placeholder="VD: transaction_id"
                            />
                            <input
                              type="text"
                              value={col.alias || col.display_name || ''}
                              onChange={(e) => {
                                const cols = [...(editForm.db_config?.output_columns || [])]
                                cols[colIdx] = { ...cols[colIdx], alias: e.target.value }
                                handleConfigChange('db_config', 'output_columns', cols)
                              }}
                              className="col-span-5 px-2 py-1.5 border rounded text-sm"
                              placeholder="VD: txn_id"
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const cols = (editForm.db_config?.output_columns || []).filter((_, i) => i !== colIdx)
                                handleConfigChange('db_config', 'output_columns', cols)
                              }}
                              className="col-span-2 text-red-500 hover:text-red-700 text-center"
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500 italic">
                        Chưa có cột nào. Click "Thêm cột" để khai báo.
                        <br />
                        <span className="text-xs">VD: transaction_id → txn_id, total_amount → amount</span>
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* SFTP Config */}
              {editForm.source_type === 'SFTP' && (
                <div className="border-t pt-4">
                  <h4 className="font-medium text-purple-800 mb-4">📡 Cấu hình SFTP</h4>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">SFTP Host</label>
                      <input
                        type="text"
                        value={editForm.sftp_config?.host || ''}
                        onChange={(e) => handleConfigChange('sftp_config', 'host', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="sftp.partner.com"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Path Pattern</label>
                      <input
                        type="text"
                        value={editForm.sftp_config?.path_pattern || ''}
                        onChange={(e) => handleConfigChange('sftp_config', 'path_pattern', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="/data/{yyyyMMdd}/*.xlsx"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Username</label>
                      <input
                        type="text"
                        value={editForm.sftp_config?.username || ''}
                        onChange={(e) => handleConfigChange('sftp_config', 'username', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                      />
                    </div>
                  </div>
                  
                  {/* SFTP cũng có thể cần column mapping */}
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <p className="text-sm text-purple-700">
                      File từ SFTP sẽ được xử lý giống như File Upload. 
                      Cấu hình column mapping tương tự.
                    </p>
                  </div>
                </div>
              )}

              {/* API Config */}
              {editForm.source_type === 'API' && (
                <div className="border-t pt-4">
                  <h4 className="font-medium text-orange-800 mb-4">🔗 Cấu hình API</h4>
                  <div className="grid grid-cols-4 gap-4">
                    <div className="col-span-3">
                      <label className="block text-sm text-gray-600 mb-1">API URL</label>
                      <input
                        type="text"
                        value={editForm.api_config?.url || ''}
                        onChange={(e) => handleConfigChange('api_config', 'url', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                        placeholder="https://api.partner.com/transactions"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Method</label>
                      <select
                        value={editForm.api_config?.method || 'GET'}
                        onChange={(e) => handleConfigChange('api_config', 'method', e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg"
                      >
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex-shrink-0 bg-gray-50 border-t px-6 py-4 rounded-b-xl">
              {/* Error message */}
              {saveError && (
                <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                  ⚠️ {saveError}
                </div>
              )}
              
              {/* New config warning */}
              {isNewConfig && (
                <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-yellow-800 text-sm">
                  ⚠️ Vui lòng lưu thông tin cấu hình chính trước khi thêm nguồn dữ liệu.
                </div>
              )}
              
              <div className="flex justify-between items-center">
                <p className="text-xs text-gray-500">
                  💾 Dữ liệu sẽ được <strong>lưu ngay vào database</strong> khi bấm nút Lưu.
                </p>
                <div className="flex space-x-3">
                  <button
                    onClick={closeEditor}
                    disabled={saving}
                    className="px-4 py-2 border border-gray-300 bg-white rounded-lg hover:bg-gray-100 disabled:opacity-50"
                  >
                    Hủy
                  </button>
                  <button
                    onClick={saveSource}
                    disabled={saving || isNewConfig}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                  >
                    {saving ? (
                      <>
                        <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Đang lưu...
                      </>
                    ) : (
                      <>💾 LƯU VÀO DATABASE</>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================
// WORKFLOW TAB COMPONENT (với nút lưu riêng)
// ============================================
function WorkflowTab({ 
  workflowSteps, 
  setWorkflowSteps, 
  dataSources,
  configId, 
  isNewConfig,
  addWorkflowStep,
  updateWorkflowStep,
  updateWorkflowStepMulti,
  removeWorkflowStep,
  moveWorkflowStep,
  getAvailableSources,
  onReload
}) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [expandedStep, setExpandedStep] = useState(null) // Track which step is expanded
  
  const JOIN_TYPES = ['left', 'inner', 'right', 'outer']
  const OUTPUT_TYPES = [
    { value: 'intermediate', label: '🔄 Trung gian', desc: 'Dùng làm input cho bước tiếp theo' },
    { value: 'report', label: '📊 Xuất báo cáo', desc: 'Kết quả cuối cùng, xuất ra file báo cáo' },
  ]
  
  // LƯU TẤT CẢ WORKFLOW STEPS VÀO DB
  const saveAllWorkflows = async () => {
    if (isNewConfig) {
      setSaveError('Vui lòng lưu thông tin cấu hình chính trước.')
      return
    }
    
    // Validate output columns for all visible steps
    const visibleStepsForValidation = workflowSteps.filter(ws => !ws.isDeleted)
    const allOutputErrors = []
    visibleStepsForValidation.forEach((step, stepIdx) => {
      const cols = step.output_columns || []
      if (cols.length === 0) return
      
      const displayNames = []
      cols.forEach((col, colIdx) => {
        const rowNum = colIdx + 1
        const stepLabel = step.step_name || step.output_name || `Step ${stepIdx + 1}`
        if (!col.source) {
          allOutputErrors.push(`[${stepLabel}] Cột #${rowNum}: Chưa chọn Nguồn`)
        }
        if (!col.display_name) {
          allOutputErrors.push(`[${stepLabel}] Cột #${rowNum}: Chưa có Tên cột output`)
        }
        const dn = (col.display_name || '').trim()
        if (dn) displayNames.push({ colIdx, dn })
      })
      // Duplicate display_name within step
      const seen = {}
      displayNames.forEach(({ colIdx: ci, dn }) => {
        if (seen[dn] !== undefined) {
          const stepLabel = step.step_name || step.output_name || `Step ${stepIdx + 1}`
          if (!allOutputErrors.find(e => e.includes(`"${dn}" bị trùng`) && e.includes(`[${stepLabel}]`))) {
            allOutputErrors.push(`[${stepLabel}] Tên hiển thị "${dn}" bị trùng (cột #${seen[dn] + 1} và #${ci + 1})`)
          }
        } else {
          seen[dn] = ci
        }
      })
    })
    
    if (allOutputErrors.length > 0) {
      setSaveError('Output columns có lỗi:\n• ' + allOutputErrors.join('\n• '))
      return
    }
    
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    
    try {
      // BƯỚC 1: Xóa các step bị đánh dấu delete TRƯỚC
      // (để tránh conflict step_order khi update)
      const stepsToDelete = workflowSteps.filter(ws => ws.isDeleted && !String(ws.id).startsWith('new_'))
      for (const step of stepsToDelete) {
        await workflowsApiV2.delete(step.id)
        console.log('✅ Deleted workflow step:', step.id)
      }
      
      // BƯỚC 2: Update/Create các step còn lại
      const visibleSteps = workflowSteps.filter(ws => !ws.isDeleted)
      
      for (let i = 0; i < visibleSteps.length; i++) {
        const step = visibleSteps[i]
        const stepData = { 
          ...step, 
          step_order: i + 1,
          config_id: parseInt(configId)
        }
        // Xóa các field không cần gửi lên server
        delete stepData.isNew
        delete stepData.isModified
        delete stepData.isDeleted

        // Clean matching_rules: chỉ giữ data của mode đang dùng
        if (stepData.matching_rules) {
          const mr = { ...stepData.matching_rules }
          if (mr.mode === 'advanced') {
            // Advanced mode: chỉ giữ expression, xóa simple config
            if (mr.key_match) {
              const { left, right, ...restKey } = mr.key_match
              mr.key_match = restKey
            }
            if (mr.amount_match) {
              const { left_column, right_column, left, right, tolerance, tolerance_type, ...restAmt } = mr.amount_match
              mr.amount_match = restAmt
            }
          } else {
            // Simple mode: xóa expression field
            if (mr.key_match) {
              const { expression, ...restKey } = mr.key_match
              mr.key_match = restKey
            }
            if (mr.amount_match) {
              const { expression, ...restAmt } = mr.amount_match
              mr.amount_match = restAmt
            }
          }
          stepData.matching_rules = mr
        }
        
        if (step.isNew || String(step.id).startsWith('new_')) {
          // Create new
          delete stepData.id
          const response = await workflowsApiV2.create(stepData)
          console.log('✅ Created workflow step:', response.data)
        } else {
          // Update existing
          const response = await workflowsApiV2.update(step.id, stepData)
          console.log('✅ Updated workflow step:', response.data)
        }
      }
      
      // BƯỚC 3: Reload data từ server để đồng bộ state
      if (onReload) {
        await onReload()
      }
      
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (error) {
      console.error('❌ Failed to save workflow:', error)
      setSaveError(error.response?.data?.detail || error.message || 'Không thể lưu workflow')
    } finally {
      setSaving(false)
    }
  }
  
  const visibleSteps = workflowSteps.filter(ws => !ws.isDeleted)
  const hasUnsavedChanges = workflowSteps.some(ws => ws.isNew || ws.isModified || ws.isDeleted)
  
  // Toggle expand/collapse step
  const toggleStep = (stepId) => {
    setExpandedStep(prev => prev === stepId ? null : stepId)
  }
  
  // Get columns từ một source - hỗ trợ tất cả các loại source
  // Trả về danh sách alias (tên đã được map)
  // Hỗ trợ cả workflow output (kết quả trung gian)
  const getSourceColumns = (sourceName) => {
    // 1. Tìm trong dataSources trước
    const ds = dataSources.find(d => d.source_name === sourceName)
    if (ds) {
      // FILE_UPLOAD: lấy từ file_config.columns → alias
      if (ds.source_type === 'FILE_UPLOAD' && ds.file_config?.columns) {
        const cols = ds.file_config.columns
        if (Array.isArray(cols)) return cols.map(c => c.alias).filter(Boolean)
        return Object.keys(cols)
      }
      
      // DATABASE: lấy từ db_config.output_columns → alias (hoặc name nếu chưa migrate)
      if (ds.source_type === 'DATABASE' && ds.db_config?.output_columns) {
        return ds.db_config.output_columns.map(c => c.alias || c.name).filter(Boolean)
      }
      
      // API: lấy từ api_config.output_columns → alias
      if (ds.source_type === 'API' && ds.api_config?.output_columns) {
        return ds.api_config.output_columns.map(c => c.alias || c.name).filter(Boolean)
      }
      
      // SFTP: tương tự FILE_UPLOAD → alias
      if (ds.source_type === 'SFTP' && ds.sftp_config?.columns) {
        const cols = ds.sftp_config.columns
        if (Array.isArray(cols)) return cols.map(c => c.alias).filter(Boolean)
        return Object.keys(cols)
      }
      
      return []
    }
    
    // 2. Nếu không tìm thấy trong dataSources, tìm trong workflow step outputs
    // sourceName có thể là output_name của một step trước đó (VD: A1_1, A1_2)
    const previousStep = workflowSteps.find(ws => ws.output_name === sourceName && !ws.isDeleted)
    if (previousStep) {
      // Nếu step trước có output_columns đã cấu hình, lấy từ đó
      if (previousStep.output_columns && Array.isArray(previousStep.output_columns) && previousStep.output_columns.length > 0) {
        return previousStep.output_columns.map(c => c.column_name || c.display_name).filter(Boolean)
      }
      
      // Nếu chưa có output_columns, merge columns từ left_source và right_source của step đó
      const leftCols = getSourceColumns(previousStep.left_source)
      const rightCols = getSourceColumns(previousStep.right_source)
      const mergedCols = [...new Set([...leftCols, ...rightCols, 'match_status'])]
      return mergedCols
    }
    
    return []
  }
  
  return (
    <div className="space-y-4">
      {/* Header với nút lưu */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h3 className="font-medium text-gray-700">Workflow - Các cặp so sánh</h3>
          {hasUnsavedChanges && (
            <span className="text-sm text-amber-600 animate-pulse">● Có thay đổi chưa lưu</span>
          )}
          {saveSuccess && (
            <span className="text-sm text-green-600">✓ Đã lưu thành công!</span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={addWorkflowStep}
            className="inline-flex items-center px-4 py-2 bg-blue-700 text-white rounded-lg text-sm hover:bg-blue-800 font-semibold shadow-md border-2 border-blue-800"
          >
            <PlusIcon className="h-5 w-5 mr-1" />
            + Thêm cặp so sánh mới
          </button>
          <button
            onClick={saveAllWorkflows}
            disabled={saving || isNewConfig || !hasUnsavedChanges}
            className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Đang lưu...
              </>
            ) : (
              <>💾 LƯU WORKFLOW</>
            )}
          </button>
        </div>
      </div>
      
      {/* Error message */}
      {saveError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm whitespace-pre-wrap">
          ⚠️ {saveError}
        </div>
      )}
      
      {/* New config warning */}
      {isNewConfig && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          ⚠️ Vui lòng lưu thông tin cấu hình chính trước khi cấu hình workflow.
        </div>
      )}
      
      {/* Hướng dẫn */}
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-blue-800 text-sm">
        💡 Mỗi cặp so sánh sẽ ghép 2 nguồn dữ liệu và tạo ra 1 output. Output có thể dùng làm input cho cặp tiếp theo (trung gian) hoặc là kết quả cuối cùng để xuất báo cáo.
      </div>
      
      {/* Workflow Steps List - Redesigned */}
      {visibleSteps.map((step, index) => {
        const isExpanded = expandedStep === step.id
        const outputType = step.output_type || 'intermediate'
        const outputTypeInfo = OUTPUT_TYPES.find(t => t.value === outputType)
        const leftCols = getSourceColumns(step.left_source)
        const rightCols = getSourceColumns(step.right_source)
        
        return (
          <div 
            key={step.id} 
            className={`border-2 rounded-xl overflow-hidden transition-all ${
              outputType === 'report' ? 'border-purple-400' :
              (step.isNew || step.isModified) ? 'border-amber-300' : 'border-gray-200'
            }`}
          >
            {/* Step Header - Always visible */}
            <div 
              className={`p-4 cursor-pointer ${
                outputType === 'report' ? 'bg-purple-50' :
                (step.isNew || step.isModified) ? 'bg-amber-50' : 'bg-gray-50'
              }`}
              onClick={() => toggleStep(step.id)}
            >
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-white font-bold shadow-md ${
                    outputType === 'report' ? 'bg-purple-600' : 'bg-gray-700'
                  }`}>
                    {index + 1}
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      {step.isNew && <span className="text-green-600 text-xs font-medium">[MỚI]</span>}
                      {step.isModified && !step.isNew && <span className="text-amber-600 text-xs font-medium">[ĐÃ SỬA]</span>}
                      <h4 className="font-semibold text-gray-900">{step.step_name || 'Chưa đặt tên'}</h4>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600 mt-0.5">
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                        {step.left_source || '?'}
                      </span>
                      <span className="text-gray-400">⟷</span>
                      <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-medium">
                        {step.right_source || '?'}
                      </span>
                      <span className="text-gray-400">→</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        outputType === 'report' ? 'bg-purple-100 text-purple-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {step.output_name || '?'}
                      </span>
                      <span className="text-xs text-gray-500">({outputTypeInfo?.label})</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); moveWorkflowStep(step.id, -1) }}
                    disabled={index === 0}
                    className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-white rounded disabled:opacity-30"
                    title="Di chuyển lên"
                  >
                    <ChevronUpIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); moveWorkflowStep(step.id, 1) }}
                    disabled={index === visibleSteps.length - 1}
                    className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-white rounded disabled:opacity-30"
                    title="Di chuyển xuống"
                  >
                    <ChevronDownIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); removeWorkflowStep(step.id) }}
                    className="p-1.5 text-red-400 hover:text-red-600 hover:bg-white rounded"
                    title="Xóa"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                  <div className={`ml-2 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                    <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                  </div>
                </div>
              </div>
            </div>
            
            {/* Step Content - Expandable */}
            {isExpanded && (
              <div className="p-5 bg-white space-y-6">
                {/* ===== PHẦN 1: THÔNG TIN CƠ BẢN ===== */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Tên bước *</label>
                    <input
                      type="text"
                      value={step.step_name}
                      onChange={(e) => updateWorkflowStep(step.id, 'step_name', e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg"
                      placeholder="VD: So khớp B1-B4"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Nguồn bên trái *</label>
                    <select
                      value={step.left_source}
                      onChange={(e) => updateWorkflowStep(step.id, 'left_source', e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg bg-blue-50"
                    >
                      <option value="">-- Chọn nguồn --</option>
                      {getAvailableSources().map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Nguồn bên phải *</label>
                    <select
                      value={step.right_source}
                      onChange={(e) => updateWorkflowStep(step.id, 'right_source', e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg bg-orange-50"
                    >
                      <option value="">-- Chọn nguồn --</option>
                      {getAvailableSources().map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Join Type</label>
                    <select
                      value={step.join_type}
                      onChange={(e) => updateWorkflowStep(step.id, 'join_type', e.target.value)}
                      className="w-full px-3 py-2 border rounded-lg"
                    >
                      {JOIN_TYPES.map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>
                </div>
                
                {/* ===== PHẦN 2: MATCHING RULES (giống V1) ===== */}
                <div className="border-t pt-5">
                  <MatchingRulesEditorV2
                    step={step}
                    stepId={step.id}
                    updateWorkflowStep={updateWorkflowStep}
                    leftColumns={leftCols}
                    rightColumns={rightCols}
                    leftLabel={step.left_source || 'Trái'}
                    rightLabel={step.right_source || 'Phải'}
                  />
                </div>
                
                {/* ===== PHẦN 3: OUTPUT CONFIG ===== */}
                <div className="border-t pt-5">
                  <h5 className="font-medium text-gray-800 mb-4 flex items-center gap-2">
                    📤 Cấu hình Output
                  </h5>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Tên Output *</label>
                      <input
                        type="text"
                        value={step.output_name}
                        onChange={(e) => updateWorkflowStep(step.id, 'output_name', e.target.value.toUpperCase())}
                        className="w-full px-3 py-2 border rounded-lg font-mono"
                        placeholder="VD: A1, A2, RESULT..."
                      />
                      <p className="text-xs text-gray-500 mt-1">Có thể dùng làm input cho bước sau</p>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Loại Output</label>
                      <div className="grid grid-cols-2 gap-2">
                        {OUTPUT_TYPES.map(ot => (
                          <label 
                            key={ot.value}
                            className={`flex items-start gap-2 p-3 border rounded-lg cursor-pointer transition-all ${
                              step.output_type === ot.value 
                                ? (ot.value === 'report' ? 'border-purple-500 bg-purple-50' :
                                   'border-gray-500 bg-gray-50')
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <input
                              type="radio"
                              name={`output_type_${step.id}`}
                              checked={step.output_type === ot.value}
                              onChange={() => {
                                updateWorkflowStepMulti(step.id, {
                                  output_type: ot.value,
                                  is_final_output: ot.value === 'report'
                                })
                              }}
                              className="mt-0.5"
                            />
                            <div>
                              <div className="font-medium text-sm">{ot.label}</div>
                              <div className="text-xs text-gray-500">{ot.desc}</div>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                  
                  {/* Nếu là output report, hiển thị thêm options */}
                  {step.output_type === 'report' && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Tên hiển thị</label>
                          <input
                            type="text"
                            value={step.output_display_name || ''}
                            onChange={(e) => updateWorkflowStep(step.id, 'output_display_name', e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg"
                            placeholder="VD: Kết quả đối soát B1-B4"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Thứ tự hiển thị</label>
                          <input
                            type="number"
                            value={step.output_display_order || 1}
                            onChange={(e) => updateWorkflowStep(step.id, 'output_display_order', parseInt(e.target.value) || 1)}
                            className="w-full px-3 py-2 border rounded-lg"
                            min="1"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {/* ===== PHẦN 4: OUTPUT COLUMNS CONFIG ===== */}
                  <div className="border-t pt-5">
                    <WorkflowOutputColumnsEditor
                      step={step}
                      stepId={step.id}
                      updateWorkflowStep={updateWorkflowStep}
                      dataSources={dataSources}
                      workflowSteps={workflowSteps}
                    />
                  </div>
                  
                  {/* Nút Lưu ở cuối mỗi step */}
                  <div className="border-t mt-5 pt-4 flex justify-end">
                    <button
                      onClick={saveAllWorkflows}
                      disabled={saving || isNewConfig}
                      className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium flex items-center gap-2 shadow-sm"
                    >
                      {saving ? (
                        <>
                          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          Đang lưu...
                        </>
                      ) : (
                        <>💾 LƯU WORKFLOW</>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      })}

      {visibleSteps.length === 0 && (
        <div className="text-center py-12 text-gray-500 border-2 border-dashed rounded-xl">
          <div className="text-4xl mb-3">🔗</div>
          <p className="font-medium">Chưa có cặp so sánh nào</p>
          <p className="text-sm mt-1">Click "Thêm cặp so sánh" để bắt đầu cấu hình workflow đối soát.</p>
        </div>
      )}
    </div>
  )
}

// ============================================
// REPORT TEMPLATE TAB COMPONENT
// ============================================
function ReportTemplateTab({ config, handleConfigChange, configId, isNewConfig, workflowSteps = [] }) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  
  // Report cell mapping state - stored in config.report_cell_mapping
  const reportCellMapping = config.report_cell_mapping || { sheets: [] }
  const sheets = reportCellMapping.sheets || []
  const [activeSheetIdx, setActiveSheetIdx] = useState(0)
  
  // State riêng cho columns input để cho phép nhập dấu phẩy thoải mái
  const [columnsInputText, setColumnsInputText] = useState('')
  
  // Sync columnsInputText với dữ liệu từ sheets
  useEffect(() => {
    const currentSheet = sheets[activeSheetIdx]
    if (currentSheet) {
      setColumnsInputText((currentSheet.columns || []).join(', '))
    }
  }, [activeSheetIdx, sheets.length])
  
  // Ensure activeSheetIdx is valid
  useEffect(() => {
    if (sheets.length > 0 && activeSheetIdx >= sheets.length) {
      setActiveSheetIdx(sheets.length - 1)
    }
  }, [sheets.length, activeSheetIdx])
  
  const updateReportCellMapping = (newMapping) => {
    handleConfigChange('report_cell_mapping', newMapping)
  }
  
  const updateSheets = (newSheets) => {
    updateReportCellMapping({ ...reportCellMapping, sheets: newSheets })
  }
  
  // Sheet management
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
  
  // Save to database
  const saveReportTemplate = async () => {
    if (isNewConfig) {
      setSaveError('Vui lòng lưu thông tin cấu hình chính trước.')
      return
    }
    
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    
    try {
      // Update config với report_template_path và report_cell_mapping
      await configsApiV2.update(configId, {
        report_template_path: config.report_template_path,
        report_cell_mapping: reportCellMapping
      })
      console.log('✅ Saved report template config')
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (error) {
      console.error('❌ Failed to save report template:', error)
      setSaveError(error.response?.data?.detail || error.message || 'Không thể lưu cấu hình template')
    } finally {
      setSaving(false)
    }
  }
  
  // Get current sheet safely
  const currentSheet = activeSheetIdx < sheets.length ? sheets[activeSheetIdx] : null
  
  return (
    <div className="space-y-6">
      {/* Header với nút lưu */}
      <div className="flex justify-between items-center border-b pb-4">
        <div className="flex items-center gap-4">
          <h3 className="font-medium text-gray-700">📊 Cấu hình Report Template</h3>
          {saveSuccess && (
            <span className="text-sm text-green-600">✓ Đã lưu thành công!</span>
          )}
        </div>
        <button
          onClick={saveReportTemplate}
          disabled={saving || isNewConfig}
          className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
        >
          {saving ? (
            <>
              <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Đang lưu...
            </>
          ) : (
            <>💾 LƯU TEMPLATE</>
          )}
        </button>
      </div>
      
      {/* Error/Warning messages */}
      {saveError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠️ {saveError}
        </div>
      )}
      
      {isNewConfig && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          ⚠️ Vui lòng lưu thông tin cấu hình chính trước khi cấu hình template.
        </div>
      )}
      
      {/* Template File Path */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          📁 Đường dẫn file template (Excel)
        </label>
        <input
          type="text"
          value={config.report_template_path || ''}
          onChange={(e) => handleConfigChange('report_template_path', e.target.value || null)}
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
            className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 flex items-center"
          >
            <PlusIcon className="h-4 w-4 mr-1" />
            Thêm Sheet
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
                    <XMarkIcon className="h-4 w-4" />
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
            
            {/* SQL Cells */}
            <div className="bg-gray-50 p-4 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h5 className="font-medium text-gray-700">🔢 Các ô tổng hợp dữ liệu (SQL)</h5>
                  <p className="text-xs text-gray-500">Điền giá trị vào ô cụ thể trong sheet này bằng câu SQL</p>
                </div>
                <button
                  onClick={handleAddSqlCell}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center"
                >
                  <PlusIcon className="h-4 w-4 mr-1" />
                  Thêm SQL Cell
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
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                {(currentSheet.sql_cells || []).length === 0 && (
                  <div className="text-center py-4 text-gray-400 text-sm bg-white rounded border-2 border-dashed">
                    Chưa có SQL cell nào cho sheet này. Click "Thêm SQL Cell" để bắt đầu.
                  </div>
                )}
              </div>
            </div>
            
            {/* Data Table config (optional) */}
            <div className="bg-yellow-50 p-4 rounded-lg">
              <h5 className="font-medium text-gray-700 mb-3">📋 Bảng dữ liệu chi tiết (tùy chọn)</h5>
              <p className="text-xs text-gray-500 mb-3">
                Dùng để xuất danh sách các dòng từ kết quả đối soát ra sheet
              </p>
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
                    value={columnsInputText}
                    onChange={(e) => setColumnsInputText(e.target.value)}
                    onBlur={(e) => {
                      // Parse và lưu khi blur
                      const cols = e.target.value.split(',').map(c => c.trim()).filter(c => c)
                      handleUpdateDataTable('columns', cols)
                    }}
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
        
        {/* Available tables from workflow */}
        {(() => {
          const reportSteps = workflowSteps.filter(ws => ws.output_type === 'report' && !ws.isDeleted)
          const allOutputs = workflowSteps.filter(ws => !ws.isDeleted && ws.output_name)
          return (
            <div className="mt-4 space-y-3">
              {/* Bảng có thể dùng trong SQL */}
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm">
                <p className="font-medium text-green-800 mb-2">📊 Bảng dữ liệu có thể dùng trong SQL:</p>
                {reportSteps.length > 0 ? (
                  <div className="space-y-1">
                    {reportSteps.map(step => (
                      <div key={step.id} className="flex items-center gap-2">
                        <code className="px-2 py-1 bg-green-100 text-green-800 rounded font-mono text-xs">
                          {step.output_name}
                        </code>
                        <span className="text-green-700 text-xs">
                          ← {step.step_name} ({step.output_display_name || 'Xuất báo cáo'})
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-amber-600 text-xs">
                    ⚠️ Chưa có workflow step nào được chọn "Xuất báo cáo". 
                    Vui lòng vào tab Workflow và chọn output_type = "Xuất báo cáo" cho các bước cần xuất.
                  </p>
                )}
                {allOutputs.length > 0 && reportSteps.length < allOutputs.length && (
                  <details className="mt-2">
                    <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                      Xem tất cả outputs ({allOutputs.length})
                    </summary>
                    <div className="mt-1 pl-2 text-xs text-gray-500">
                      {allOutputs.map(step => (
                        <span key={step.id} className="mr-2">
                          <code className={`px-1 rounded ${step.output_type === 'report' ? 'bg-green-100' : 'bg-gray-100'}`}>
                            {step.output_name}
                          </code>
                          {step.output_type !== 'report' && ' (trung gian)'}
                        </span>
                      ))}
                    </div>
                  </details>
                )}
              </div>
              
              {/* Ví dụ SQL */}
              <div className="p-3 bg-blue-50 rounded-lg text-sm">
                <p className="font-medium text-blue-800 mb-2">💡 Ví dụ câu SQL:</p>
                <ul className="text-blue-700 space-y-1 text-xs font-mono">
                  {reportSteps.length > 0 ? (
                    <>
                      <li>• SELECT COUNT(*) FROM {reportSteps[0].output_name}</li>
                      <li>• SELECT COUNT(*) FROM {reportSteps[0].output_name} WHERE match_status = 'MATCHED'</li>
                      <li>• SELECT SUM(credit_amount) FROM {reportSteps[0].output_name}</li>
                    </>
                  ) : (
                    <>
                      <li>• SELECT COUNT(*) FROM [TÊnBẢNG]</li>
                      <li>• SELECT COUNT(*) FROM [TÊnBẢNG] WHERE match_status = 'MATCHED'</li>
                      <li>• SELECT SUM(amount) FROM [TÊnBẢNG]</li>
                    </>
                  )}
                </ul>
              </div>
            </div>
          )
        })()}
      </div>
    </div>
  )
}

// ============================================
// OUTPUTS TAB COMPONENT (với nút lưu riêng) - DEPRECATED, kept for reference
// ============================================
function OutputsTab({
  outputConfigs,
  setOutputConfigs,
  dataSources,
  workflowSteps,
  configId,
  isNewConfig,
  addOutputConfig,
  updateOutputConfig,
  removeOutputConfig
}) {
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  
  // LƯU TẤT CẢ OUTPUT CONFIGS VÀO DB
  const saveAllOutputs = async () => {
    if (isNewConfig) {
      setSaveError('Vui lòng lưu thông tin cấu hình chính trước.')
      return
    }
    
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    
    try {
      const visibleOutputs = outputConfigs.filter(oc => !oc.isDeleted)
      
      for (const output of visibleOutputs) {
        const outputData = { ...output, config_id: parseInt(configId) }
        delete outputData.isNew
        delete outputData.isModified
        delete outputData.isDeleted
        
        if (output.isNew || String(output.id).startsWith('new_')) {
          // Create new
          delete outputData.id
          const response = await outputsApiV2.create(outputData)
          console.log('✅ Created output config:', response.data)
        } else {
          // Update existing
          const response = await outputsApiV2.update(output.id, outputData)
          console.log('✅ Updated output config:', response.data)
        }
      }
      
      // Delete removed outputs
      for (const output of outputConfigs.filter(oc => oc.isDeleted && !String(oc.id).startsWith('new_'))) {
        await outputsApiV2.delete(output.id)
        console.log('✅ Deleted output config:', output.id)
      }
      
      // Clear deleted items from state
      setOutputConfigs(prev => prev.filter(oc => !oc.isDeleted).map(oc => ({
        ...oc,
        isNew: false,
        isModified: false
      })))
      
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (error) {
      console.error('❌ Failed to save outputs:', error)
      setSaveError(error.response?.data?.detail || error.message || 'Không thể lưu output config')
    } finally {
      setSaving(false)
    }
  }
  
  const visibleOutputs = outputConfigs.filter(oc => !oc.isDeleted)
  const hasUnsavedChanges = outputConfigs.some(oc => oc.isNew || oc.isModified || oc.isDeleted)
  
  return (
    <div className="space-y-4">
      {/* Header với nút lưu */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          {hasUnsavedChanges && (
            <span className="text-sm text-amber-600 animate-pulse">● Có thay đổi chưa lưu</span>
          )}
          {saveSuccess && (
            <span className="text-sm text-green-600">✓ Đã lưu thành công!</span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={addOutputConfig}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 shadow-md font-medium transition-colors"
          >
            <PlusIcon className="h-4 w-4 mr-1" />
            Thêm output
          </button>
          <button
            onClick={saveAllOutputs}
            disabled={saving || isNewConfig || !hasUnsavedChanges}
            className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? (
              <>
                <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Đang lưu...
              </>
            ) : (
              <>💾 LƯU OUTPUT</>
            )}
          </button>
        </div>
      </div>
      
      {/* Error message */}
      {saveError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          ⚠️ {saveError}
        </div>
      )}
      
      {/* New config warning */}
      {isNewConfig && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          ⚠️ Vui lòng lưu thông tin cấu hình chính trước khi cấu hình output.
        </div>
      )}
      
      {/* Output Configs List */}
      {visibleOutputs.map((output, index) => (
        <div key={output.id} className={`border rounded-lg p-4 space-y-4 ${
          (output.isNew || output.isModified) ? 'border-amber-300 bg-amber-50' : 'border-gray-200'
        }`}>
          <div className="flex justify-between items-center">
            <h4 className="font-medium">
              {output.isNew && <span className="text-green-600 text-xs mr-2">[MỚI]</span>}
              {output.isModified && !output.isNew && <span className="text-amber-600 text-xs mr-2">[ĐÃ SỬA]</span>}
              Output: {output.output_name}
            </h4>
            <button
              onClick={() => removeOutputConfig(index)}
              className="text-red-500 hover:text-red-700"
            >
              <TrashIcon className="h-5 w-5" />
            </button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Output Name</label>
              <input
                type="text"
                value={output.output_name}
                onChange={(e) => updateOutputConfig(index, 'output_name', e.target.value.toUpperCase())}
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Display Name</label>
              <input
                type="text"
                value={output.display_name || ''}
                onChange={(e) => updateOutputConfig(index, 'display_name', e.target.value)}
                className="w-full px-3 py-2 border rounded-lg text-sm"
                placeholder="VD: Kết quả đối soát"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={output.use_for_report}
                  onChange={(e) => updateOutputConfig(index, 'use_for_report', e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 mr-2"
                />
                <span className="text-sm">Dùng cho Report</span>
              </label>
            </div>
          </div>
          
          {/* Output Columns Config */}
          <OutputColumnsEditor
            output={output}
            index={index}
            updateOutputConfig={updateOutputConfig}
            dataSources={dataSources}
            workflowSteps={workflowSteps}
          />
        </div>
      ))}

      {visibleOutputs.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          Chưa có output config nào. Click "Thêm output" để bắt đầu.
        </div>
      )}
    </div>
  )
}

// ============================================
// MATCHING RULES EDITOR V2 (giống V1)
// ============================================
function MatchingRulesEditorV2({ 
  step, 
  stepId, 
  updateWorkflowStep, 
  leftColumns = [], 
  rightColumns = [],
  leftLabel = 'Trái',
  rightLabel = 'Phải'
}) {
  // Restore mode from saved matching_rules.mode ('advanced' | 'simple' | undefined)
  const [showAdvanced, setShowAdvanced] = useState((step.matching_rules || {}).mode === 'advanced')
  const [showJson, setShowJson] = useState(false)
  const [textInputs, setTextInputs] = useState({})
  const [expandedPanels, setExpandedPanels] = useState({})

  // Safe helpers
  const safeArray = (val) => Array.isArray(val) ? val : []
  const safeObj = (val) => (val && typeof val === 'object' && !Array.isArray(val)) ? val : {}
  
  // Extract config
  const matchingRules = step.matching_rules || {}
  const keyMatch = safeObj(matchingRules.key_match)
  const amountMatch = safeObj(matchingRules.amount_match)
  const statusLogic = matchingRules.status_logic || {
    all_match: 'MATCHED',
    key_match_amount_mismatch: 'MISMATCH',
    no_key_match: 'NOT_FOUND',
    no_key_match_right: 'RIGHT_ONLY'
  }
  
  const SIMPLE_TRANSFORMS = [
    { id: 'strip', label: 'Trim khoảng trắng' },
    { id: 'upper', label: 'Viết HOA' },
    { id: 'lower', label: 'Viết thường' },
    { id: 'trim_zero', label: 'Bỏ số 0 đầu' },
  ]
  
  // Update functions
  const updateMatchingRules = (updates) => {
    updateWorkflowStep(stepId, 'matching_rules', { ...matchingRules, ...updates })
  }
  
  const updateKeyMatch = (updates) => {
    updateMatchingRules({ key_match: { ...keyMatch, ...updates } })
  }
  
  const updateAmountMatch = (updates) => {
    updateMatchingRules({ amount_match: { ...amountMatch, ...updates } })
  }
  
  const updateSide = (matchType, side, updates) => {
    const match = matchType === 'key' ? keyMatch : amountMatch
    const currentSide = safeObj(match[side])
    const updateFn = matchType === 'key' ? updateKeyMatch : updateAmountMatch
    updateFn({ [side]: { ...currentSide, ...updates } })
  }
  
  // Parts management
  const getParts = (matchType, side) => {
    const match = matchType === 'key' ? keyMatch : amountMatch
    return safeArray(safeObj(match[side]).parts)
  }
  
  const getTransforms = (matchType, side) => {
    const match = matchType === 'key' ? keyMatch : amountMatch
    return safeArray(safeObj(match[side]).transforms)
  }
  
  const addPart = (matchType, side, type, value) => {
    if (!value) return
    const parts = getParts(matchType, side)
    updateSide(matchType, side, { parts: [...parts, { type, value }] })
  }
  
  const removePart = (matchType, side, idx) => {
    const parts = getParts(matchType, side)
    updateSide(matchType, side, { parts: parts.filter((_, i) => i !== idx) })
  }
  
  const movePart = (matchType, side, idx, direction) => {
    const parts = [...getParts(matchType, side)]
    const newIdx = direction === 'up' ? idx - 1 : idx + 1
    if (newIdx < 0 || newIdx >= parts.length) return
    ;[parts[idx], parts[newIdx]] = [parts[newIdx], parts[idx]]
    updateSide(matchType, side, { parts })
  }
  
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
  
  // Generate expression preview
  const generatePreview = (matchType, side) => {
    const parts = getParts(matchType, side)
    if (parts.length === 0) return ''
    return parts.map(p => p.type === 'column' ? `[${p.value}]` : `'${p.value}'`).join(' + ')
  }
  
  // Generate expression from side config (giống V1)
  const generateExprFromSide = (matchType, side, prefix) => {
    const parts = getParts(matchType, side)
    const transforms = getTransforms(matchType, side)
    const match = matchType === 'key' ? keyMatch : amountMatch
    const sideConfig = safeObj(match[side])
    
    if (parts.length === 0) return ''
    
    // Build parts expression
    const partsExpr = parts.map(p => {
      if (!p || !p.value) return "''"
      if (p.type === 'text') return `'${p.value}'`
      return `${prefix}['${p.value}'].astype(str)`
    }).join(' + ')
    
    let expr = parts.length > 1 ? `(${partsExpr})` : partsExpr
    
    // Apply basic transforms
    transforms.forEach(t => {
      if (t === 'strip') expr = `${expr}.str.strip()`
      if (t === 'upper') expr = `${expr}.str.upper()`
      if (t === 'lower') expr = `${expr}.str.lower()`
      if (t === 'trim_zero') expr = `${expr}.str.lstrip('0')`
    })
    
    // Apply advanced config: substring
    if (sideConfig.substring_start != null || sideConfig.substring_end != null) {
      const start = sideConfig.substring_start ?? ''
      const end = sideConfig.substring_end ?? ''
      expr = `${expr}.str[${start}:${end}]`
    }
    
    // Apply advanced config: replace
    if (sideConfig.replace_pattern) {
      const replaceWith = sideConfig.replace_with || ''
      expr = `${expr}.str.replace(r'${sideConfig.replace_pattern}', '${replaceWith}', regex=True)`
    }
    
    return expr
  }
  
  // Generate Key Expression (giống V1)
  const generateKeyExpression = () => {
    const leftParts = getParts('key', 'left')
    const rightParts = getParts('key', 'right')
    if (leftParts.length === 0 || rightParts.length === 0) return ''
    
    const leftExpr = generateExprFromSide('key', 'left', 'LEFT')
    const rightExpr = generateExprFromSide('key', 'right', 'RIGHT')
    return `${leftExpr} == ${rightExpr}`
  }
  
  // Generate Amount Expression (giống V1)
  const generateAmountExpression = () => {
    const leftCol = amountMatch.left_column
    const rightCol = amountMatch.right_column
    if (!leftCol || !rightCol) return ''
    
    const tolerance = amountMatch.tolerance ?? 0
    const toleranceType = amountMatch.tolerance_type || 'absolute'
    const leftTransforms = getTransforms('amount', 'left')
    const rightTransforms = getTransforms('amount', 'right')
    const leftConfig = safeObj(amountMatch.left)
    const rightConfig = safeObj(amountMatch.right)
    
    // Build left expression
    let leftExpr = `LEFT['${leftCol}']`
    leftTransforms.forEach(t => {
      if (t === 'strip') leftExpr = `${leftExpr}.str.strip()`
      if (t === 'upper') leftExpr = `${leftExpr}.str.upper()`
      if (t === 'lower') leftExpr = `${leftExpr}.str.lower()`
      if (t === 'trim_zero') leftExpr = `${leftExpr}.str.lstrip('0')`
    })
    if (leftConfig.substring_start != null || leftConfig.substring_end != null) {
      leftExpr = `${leftExpr}.str[${leftConfig.substring_start ?? ''}:${leftConfig.substring_end ?? ''}]`
    }
    if (leftConfig.regex_pattern) {
      leftExpr = `${leftExpr}.str.extract(r'${leftConfig.regex_pattern}', expand=False)`
    }
    if (leftConfig.replace_pattern) {
      leftExpr = `${leftExpr}.str.replace(r'${leftConfig.replace_pattern}', '${leftConfig.replace_with || ''}', regex=True)`
    }
    // Number Transform (giống V1)
    if (leftConfig.numberTransform?.enabled) {
      const ts = leftConfig.numberTransform.thousandSeparator ?? ''
      const ds = leftConfig.numberTransform.decimalSeparator ?? ''
      leftExpr = `normalize_number(${leftExpr}, '${ts}', '${ds}')`
    } else {
      leftExpr = `${leftExpr}.astype(float)`
    }
    
    // Build right expression
    let rightExpr = `RIGHT['${rightCol}']`
    rightTransforms.forEach(t => {
      if (t === 'strip') rightExpr = `${rightExpr}.str.strip()`
      if (t === 'upper') rightExpr = `${rightExpr}.str.upper()`
      if (t === 'lower') rightExpr = `${rightExpr}.str.lower()`
      if (t === 'trim_zero') rightExpr = `${rightExpr}.str.lstrip('0')`
    })
    if (rightConfig.substring_start != null || rightConfig.substring_end != null) {
      rightExpr = `${rightExpr}.str[${rightConfig.substring_start ?? ''}:${rightConfig.substring_end ?? ''}]`
    }
    if (rightConfig.regex_pattern) {
      rightExpr = `${rightExpr}.str.extract(r'${rightConfig.regex_pattern}', expand=False)`
    }
    if (rightConfig.replace_pattern) {
      rightExpr = `${rightExpr}.str.replace(r'${rightConfig.replace_pattern}', '${rightConfig.replace_with || ''}', regex=True)`
    }
    // Number Transform (giống V1)
    if (rightConfig.numberTransform?.enabled) {
      const ts = rightConfig.numberTransform.thousandSeparator ?? ''
      const ds = rightConfig.numberTransform.decimalSeparator ?? ''
      rightExpr = `normalize_number(${rightExpr}, '${ts}', '${ds}')`
    } else {
      rightExpr = `${rightExpr}.astype(float)`
    }
    
    // Build comparison
    if (tolerance === 0) {
      return `${leftExpr} == ${rightExpr}`
    }
    if (toleranceType === 'percent') {
      return `abs(${leftExpr} - ${rightExpr}) <= ${leftExpr} * ${tolerance / 100}`
    }
    return `abs(${leftExpr} - ${rightExpr}) <= ${tolerance}`
  }
  
  // Render side panel (giống V1)
  const renderSidePanel = (matchType, side, label, columns) => {
    const inputKey = `${matchType}_${side}`
    const advKey = `${matchType}_${side}_adv`
    const parts = getParts(matchType, side)
    const transforms = getTransforms(matchType, side)
    const textValue = getTextInput(inputKey)
    const isAdvExpanded = expandedPanels[advKey]
    const match = matchType === 'key' ? keyMatch : amountMatch
    const sideConfig = safeObj(match[side])
    
    return (
      <div className="bg-white p-4 rounded-lg border flex-1">
        <label className="block text-sm font-semibold text-gray-700 mb-2">{label}</label>
        
        {/* Parts list */}
        <div className="mb-3 space-y-1 min-h-[50px]">
          {parts.length === 0 && (
            <div className="text-gray-400 text-xs italic py-2 text-center border-2 border-dashed rounded">
              Chưa có thành phần nào
            </div>
          )}
          {parts.map((part, idx) => (
            <div key={idx} className="flex items-center gap-1 bg-gray-50 p-1.5 rounded text-sm">
              <span className="text-gray-400 w-5 text-center text-xs">{idx + 1}</span>
              {part.type === 'column' ? (
                <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded font-mono flex-1 truncate text-xs">
                  {part.value}
                </span>
              ) : (
                <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded font-mono flex-1 truncate text-xs">
                  '{part.value}'
                </span>
              )}
              <button type="button" onClick={() => movePart(matchType, side, idx, 'up')} 
                disabled={idx === 0}
                className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30">↑</button>
              <button type="button" onClick={() => movePart(matchType, side, idx, 'down')} 
                disabled={idx === parts.length - 1}
                className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30">↓</button>
              <button type="button" onClick={() => removePart(matchType, side, idx)}
                className="p-0.5 text-red-400 hover:text-red-600">×</button>
            </div>
          ))}
        </div>
        
        {/* Add column */}
        <div className="flex gap-1 mb-2">
          <select
            value=""
            onChange={(e) => { if (e.target.value) addPart(matchType, side, 'column', e.target.value) }}
            className="flex-1 px-2 py-1.5 border rounded text-sm"
          >
            <option value="">+ Thêm cột...</option>
            {columns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </div>
        
        {/* Add text */}
        <div className="flex gap-1 mb-3">
          <input
            type="text"
            value={textValue}
            onChange={(e) => setTextInput(inputKey, e.target.value)}
            className="flex-1 px-2 py-1.5 border rounded text-sm font-mono"
            placeholder="Text tĩnh (VD: BXL, -, &)"
          />
          <button
            type="button"
            onClick={() => { if (textValue) { addPart(matchType, side, 'text', textValue); setTextInput(inputKey, '') } }}
            className="px-3 py-1.5 text-sm bg-amber-500 text-white rounded hover:bg-amber-600"
          >
            + Text
          </button>
        </div>
        
        {/* Preview */}
        {parts.length > 0 && (
          <div className="text-xs bg-gray-100 p-2 rounded mb-3 font-mono text-gray-600 break-all">
            <span className="text-gray-400">Preview: </span>
            {generatePreview(matchType, side)}
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
                className="w-3 h-3 rounded"
              />
              {t.label}
            </label>
          ))}
        </div>
        
        {/* Advanced toggle */}
        <button
          type="button"
          onClick={() => setExpandedPanels(prev => ({ ...prev, [advKey]: !prev[advKey] }))}
          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          {isAdvExpanded ? '▼' : '▶'} Cấu hình nâng cao
        </button>
        
        {isAdvExpanded && (
          <div className="mt-2 p-3 bg-gray-50 rounded border text-xs space-y-2">
            <div className="flex items-center gap-2">
              <label className="w-20 text-gray-600">Substring:</label>
              <input type="number" value={sideConfig.substring_start ?? ''} 
                onChange={(e) => updateSide(matchType, side, { substring_start: e.target.value === '' ? null : parseInt(e.target.value) })}
                className="w-16 px-2 py-1 border rounded text-center" placeholder="start" />
              <span>→</span>
              <input type="number" value={sideConfig.substring_end ?? ''} 
                onChange={(e) => updateSide(matchType, side, { substring_end: e.target.value === '' ? null : parseInt(e.target.value) })}
                className="w-16 px-2 py-1 border rounded text-center" placeholder="end" />
            </div>
            <div className="flex items-center gap-2">
              <label className="w-20 text-gray-600">Regex:</label>
              <input type="text" value={sideConfig.regex_pattern || ''} 
                onChange={(e) => updateSide(matchType, side, { regex_pattern: e.target.value || null })}
                className="flex-1 px-2 py-1 border rounded font-mono" placeholder="VD: (\d{10,15})" />
            </div>
            <div className="flex items-center gap-2">
              <label className="w-20 text-gray-600">Replace:</label>
              <input type="text" value={sideConfig.replace_pattern || ''} 
                onChange={(e) => updateSide(matchType, side, { replace_pattern: e.target.value || null })}
                className="w-24 px-2 py-1 border rounded font-mono" placeholder="pattern" />
              <span>→</span>
              <input type="text" value={sideConfig.replace_with || ''} 
                onChange={(e) => updateSide(matchType, side, { replace_with: e.target.value || null })}
                className="w-24 px-2 py-1 border rounded font-mono" placeholder="thay bằng" />
            </div>
            
            {/* Number transform for amount */}
            {matchType === 'amount' && (
              <div className="pt-2 border-t mt-2">
                <label className="flex items-center gap-2 mb-2">
                  <input
                    type="checkbox"
                    checked={sideConfig.numberTransform?.enabled || false}
                    onChange={(e) => {
                      if (e.target.checked) {
                        updateSide(matchType, side, {
                          numberTransform: { enabled: true, thousandSeparator: ',', decimalSeparator: '.' }
                        })
                      } else {
                        updateSide(matchType, side, { numberTransform: null })
                      }
                    }}
                    className="w-3 h-3"
                  />
                  <span className="font-medium">🔢 Chuẩn hóa số</span>
                </label>
                
                {sideConfig.numberTransform?.enabled && (
                  <div className="ml-5 space-y-2">
                    <div className="flex items-center gap-2">
                      <label className="w-28">Dấu ngăn nghìn:</label>
                      <select
                        value={sideConfig.numberTransform.thousandSeparator || ','}
                        onChange={(e) => updateSide(matchType, side, {
                          numberTransform: { ...sideConfig.numberTransform, thousandSeparator: e.target.value }
                        })}
                        className="px-2 py-1 border rounded"
                      >
                        <option value=",">Dấu phẩy (,)</option>
                        <option value=".">Dấu chấm (.)</option>
                        <option value="">Không có</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="w-28">Dấu thập phân:</label>
                      <select
                        value={sideConfig.numberTransform.decimalSeparator || '.'}
                        onChange={(e) => updateSide(matchType, side, {
                          numberTransform: { ...sideConfig.numberTransform, decimalSeparator: e.target.value }
                        })}
                        className="px-2 py-1 border rounded"
                      >
                        <option value=".">Dấu chấm (.)</option>
                        <option value=",">Dấu phẩy (,)</option>
                        <option value="">Không có</option>
                      </select>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h5 className="font-semibold text-gray-800 flex items-center gap-2">
          🔗 Quy tắc Matching
        </h5>
        <label className="flex items-center text-xs text-gray-500">
          <input
            type="checkbox"
            checked={showAdvanced}
            onChange={(e) => {
              const isAdvanced = e.target.checked
              setShowAdvanced(isAdvanced)
              // Persist mode preference into matching_rules so it restores on reload
              updateMatchingRules({ mode: isAdvanced ? 'advanced' : 'simple' })
            }}
            className="rounded border-gray-300 text-blue-600 mr-1"
          />
          Mode nâng cao (raw expression)
        </label>
      </div>

      {/* KEY MATCH Section */}
      <div className="bg-blue-50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <span className="px-2 py-1 bg-blue-600 text-white rounded text-xs font-bold">KEY</span>
          <span className="font-medium text-blue-800">So khớp Key (Mã giao dịch)</span>
        </div>
        
        {showAdvanced ? (
          <div>
            <label className="block text-xs text-gray-600 mb-1">Expression (Pandas)</label>
            <textarea
              value={keyMatch.expression || ''}
              onChange={(e) => updateKeyMatch({ expression: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg text-sm font-mono h-20"
              placeholder="left['txn_id'].str.strip().str.upper() == right['ref'].str.strip().str.upper()"
            />
          </div>
        ) : (
          <div className="flex gap-4">
            {renderSidePanel('key', 'left', `${leftLabel} (Bên trái)`, leftColumns)}
            <div className="flex items-center text-2xl text-gray-400 font-bold">=</div>
            {renderSidePanel('key', 'right', `${rightLabel} (Bên phải)`, rightColumns)}
          </div>
        )}
      </div>
      
      {/* AMOUNT MATCH Section - Có transforms giống V1 */}
      <div className="bg-green-50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <span className="px-2 py-1 bg-green-600 text-white rounded text-xs font-bold">AMOUNT</span>
          <span className="font-medium text-green-800">So khớp Số tiền</span>
        </div>
        
        {showAdvanced ? (
          <div>
            <label className="block text-xs text-gray-600 mb-1">Expression (Pandas)</label>
            <textarea
              value={amountMatch.expression || ''}
              onChange={(e) => updateAmountMatch({ expression: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg text-sm font-mono h-20"
              placeholder="abs(left['amount'].astype(float) - right['amt'].astype(float)) <= 1"
            />
          </div>
        ) : (
          <>
            {/* Column selection with transforms */}
            <div className="grid grid-cols-[1fr_auto_1fr] gap-4 mb-4">
              {/* LEFT SIDE */}
              <div className="bg-white p-4 rounded-lg border">
                <label className="block text-sm font-semibold text-gray-700 mb-2">{leftLabel} (Bên trái)</label>
                <select
                  value={amountMatch.left_column || ''}
                  onChange={(e) => updateAmountMatch({ left_column: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg mb-3"
                >
                  <option value="">-- Chọn cột số tiền --</option>
                  {leftColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                
                {/* Transforms cho bên trái - luôn hiển thị */}
                <div className="mt-3">
                  <label className="block text-xs text-gray-500 mb-2">Xử lý trước khi so sánh:</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {SIMPLE_TRANSFORMS.map(t => (
                        <label key={t.id} className="flex items-center gap-1 text-xs cursor-pointer">
                          <input
                            type="checkbox"
                            checked={getTransforms('amount', 'left').includes(t.id)}
                            onChange={() => toggleTransform('amount', 'left', t.id)}
                            className="w-3 h-3"
                          />
                          {t.label}
                        </label>
                      ))}
                    </div>
                    
                    {/* Advanced transforms */}
                    <details className="text-xs">
                      <summary className="cursor-pointer text-green-600 hover:underline">Xử lý nâng cao...</summary>
                      <div className="mt-2 space-y-2 p-2 bg-green-50 rounded">
                        {/* Substring - giống Key Match */}
                        <div className="flex items-center gap-2">
                          <label className="w-20 text-gray-600">Substring:</label>
                          <input
                            type="number"
                            value={safeObj(amountMatch.left).substring_start ?? ''}
                            onChange={(e) => updateSide('amount', 'left', { substring_start: e.target.value === '' ? null : parseInt(e.target.value) })}
                            className="w-16 px-2 py-1 border rounded text-center"
                            placeholder="start"
                          />
                          <span>→</span>
                          <input
                            type="number"
                            value={safeObj(amountMatch.left).substring_end ?? ''}
                            onChange={(e) => updateSide('amount', 'left', { substring_end: e.target.value === '' ? null : parseInt(e.target.value) })}
                            className="w-16 px-2 py-1 border rounded text-center"
                            placeholder="end"
                          />
                        </div>
                        
                        {/* Regex - giống Key Match */}
                        <div className="flex items-center gap-2">
                          <label className="w-20 text-gray-600">Regex:</label>
                          <input
                            type="text"
                            value={safeObj(amountMatch.left).regex_pattern || ''}
                            onChange={(e) => updateSide('amount', 'left', { regex_pattern: e.target.value || null })}
                            className="flex-1 px-2 py-1 border rounded font-mono"
                            placeholder="VD: (\d+\.?\d*)"
                          />
                        </div>
                        
                        {/* Replace - giống Key Match */}
                        <div className="flex items-center gap-2">
                          <label className="w-20 text-gray-600">Replace:</label>
                          <input
                            type="text"
                            value={safeObj(amountMatch.left).replace_pattern || ''}
                            onChange={(e) => updateSide('amount', 'left', { replace_pattern: e.target.value })}
                            className="w-24 px-2 py-1 border rounded font-mono"
                            placeholder="pattern"
                          />
                          <span>→</span>
                          <input
                            type="text"
                            value={safeObj(amountMatch.left).replace_with || ''}
                            onChange={(e) => updateSide('amount', 'left', { replace_with: e.target.value })}
                            className="w-24 px-2 py-1 border rounded font-mono"
                            placeholder="thay bằng"
                          />
                        </div>
                        
                        {/* Number Transform */}
                        <div className="border-t pt-2 mt-2">
                          <div className="flex items-center gap-2 mb-2">
                            <input
                              type="checkbox"
                              id="amount-left-number-transform"
                              checked={safeObj(amountMatch.left).numberTransform?.enabled || false}
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
                          
                          {safeObj(amountMatch.left).numberTransform?.enabled && (() => {
                            const nt = safeObj(amountMatch.left).numberTransform
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
                                  }} className="px-2 py-0.5 border rounded text-xs">
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
                                  }} className="px-2 py-0.5 border rounded text-xs">
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
                    </details>
                </div>
              </div>
              
              <div className="flex items-center text-2xl text-gray-400 font-bold">≈</div>
              
              {/* RIGHT SIDE */}
              <div className="bg-white p-4 rounded-lg border">
                <label className="block text-sm font-semibold text-gray-700 mb-2">{rightLabel} (Bên phải)</label>
                <select
                  value={amountMatch.right_column || ''}
                  onChange={(e) => updateAmountMatch({ right_column: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg mb-3"
                >
                  <option value="">-- Chọn cột số tiền --</option>
                  {rightColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
                
                {/* Transforms cho bên phải - luôn hiển thị */}
                <div className="mt-3">
                  <label className="block text-xs text-gray-500 mb-2">Xử lý trước khi so sánh:</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {SIMPLE_TRANSFORMS.map(t => (
                        <label key={t.id} className="flex items-center gap-1 text-xs cursor-pointer">
                          <input
                            type="checkbox"
                            checked={getTransforms('amount', 'right').includes(t.id)}
                            onChange={() => toggleTransform('amount', 'right', t.id)}
                            className="w-3 h-3"
                          />
                          {t.label}
                        </label>
                      ))}
                    </div>
                    
                    {/* Advanced transforms */}
                    <details className="text-xs">
                      <summary className="cursor-pointer text-green-600 hover:underline">Xử lý nâng cao...</summary>
                      <div className="mt-2 space-y-2 p-2 bg-green-50 rounded">
                        {/* Substring - giống Key Match */}
                        <div className="flex items-center gap-2">
                          <label className="w-20 text-gray-600">Substring:</label>
                          <input
                            type="number"
                            value={safeObj(amountMatch.right).substring_start ?? ''}
                            onChange={(e) => updateSide('amount', 'right', { substring_start: e.target.value === '' ? null : parseInt(e.target.value) })}
                            className="w-16 px-2 py-1 border rounded text-center"
                            placeholder="start"
                          />
                          <span>→</span>
                          <input
                            type="number"
                            value={safeObj(amountMatch.right).substring_end ?? ''}
                            onChange={(e) => updateSide('amount', 'right', { substring_end: e.target.value === '' ? null : parseInt(e.target.value) })}
                            className="w-16 px-2 py-1 border rounded text-center"
                            placeholder="end"
                          />
                        </div>
                        
                        {/* Regex - giống Key Match */}
                        <div className="flex items-center gap-2">
                          <label className="w-20 text-gray-600">Regex:</label>
                          <input
                            type="text"
                            value={safeObj(amountMatch.right).regex_pattern || ''}
                            onChange={(e) => updateSide('amount', 'right', { regex_pattern: e.target.value || null })}
                            className="flex-1 px-2 py-1 border rounded font-mono"
                            placeholder="VD: (\d+\.?\d*)"
                          />
                        </div>
                        
                        {/* Replace - giống Key Match */}
                        <div className="flex items-center gap-2">
                          <label className="w-20 text-gray-600">Replace:</label>
                          <input
                            type="text"
                            value={safeObj(amountMatch.right).replace_pattern || ''}
                            onChange={(e) => updateSide('amount', 'right', { replace_pattern: e.target.value })}
                            className="w-24 px-2 py-1 border rounded font-mono"
                            placeholder="pattern"
                          />
                          <span>→</span>
                          <input
                            type="text"
                            value={safeObj(amountMatch.right).replace_with || ''}
                            onChange={(e) => updateSide('amount', 'right', { replace_with: e.target.value })}
                            className="w-24 px-2 py-1 border rounded font-mono"
                            placeholder="thay bằng"
                          />
                        </div>
                        
                        {/* Number Transform */}
                        <div className="border-t pt-2 mt-2">
                          <div className="flex items-center gap-2 mb-2">
                            <input
                              type="checkbox"
                              id="amount-right-number-transform"
                              checked={safeObj(amountMatch.right).numberTransform?.enabled || false}
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
                          
                          {safeObj(amountMatch.right).numberTransform?.enabled && (() => {
                            const nt = safeObj(amountMatch.right).numberTransform
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
                                  }} className="px-2 py-0.5 border rounded text-xs">
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
                                  }} className="px-2 py-0.5 border rounded text-xs">
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
                    </details>
                </div>
              </div>
            </div>
            
            {/* Tolerance config */}
            <div className="flex items-center gap-4 bg-white p-3 rounded-lg border">
              <label className="text-sm text-gray-600">Cho phép lệch:</label>
              <input
                type="number"
                value={amountMatch.tolerance ?? 0}
                onChange={(e) => updateAmountMatch({ tolerance: parseFloat(e.target.value) || 0 })}
                className="w-24 px-3 py-1.5 border rounded text-sm"
                min="0"
                step="0.01"
              />
              <select
                value={amountMatch.tolerance_type || 'absolute'}
                onChange={(e) => updateAmountMatch({ tolerance_type: e.target.value })}
                className="px-3 py-1.5 border rounded text-sm"
              >
                <option value="absolute">Số tuyệt đối</option>
                <option value="percent">Phần trăm (%)</option>
              </select>
            </div>
          </>
        )}
      </div>
      
      {/* STATUS LOGIC Section */}
      <div className="bg-purple-50 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <span className="px-2 py-1 bg-purple-600 text-white rounded text-xs font-bold">STATUS</span>
          <span className="font-medium text-purple-800">Logic gán trạng thái</span>
        </div>
        
        <div className="grid grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-600 mb-1">Key khớp + Amount khớp</label>
            <input
              type="text"
              value={statusLogic.all_match || 'MATCHED'}
              onChange={(e) => updateMatchingRules({ status_logic: { ...statusLogic, all_match: e.target.value } })}
              className="w-full px-3 py-1.5 border rounded text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Key khớp + Amount lệch</label>
            <input
              type="text"
              value={statusLogic.key_match_amount_mismatch || 'MISMATCH'}
              onChange={(e) => updateMatchingRules({ status_logic: { ...statusLogic, key_match_amount_mismatch: e.target.value } })}
              className="w-full px-3 py-1.5 border rounded text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Left không khớp</label>
            <input
              type="text"
              value={statusLogic.no_key_match || 'NOT_FOUND'}
              onChange={(e) => updateMatchingRules({ status_logic: { ...statusLogic, no_key_match: e.target.value } })}
              className="w-full px-3 py-1.5 border rounded text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">Right không khớp</label>
            <input
              type="text"
              value={statusLogic.no_key_match_right || 'RIGHT_ONLY'}
              onChange={(e) => updateMatchingRules({ status_logic: { ...statusLogic, no_key_match_right: e.target.value } })}
              className="w-full px-3 py-1.5 border rounded text-sm font-mono"
            />
          </div>
        </div>
      </div>
      
      {/* PREVIEW EXPRESSION Section - Giống V1 */}
      <div className="bg-gray-50 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-gray-600 text-white rounded text-xs font-bold">PREVIEW</span>
            <span className="font-medium text-gray-800">Biểu thức so sánh</span>
          </div>
          <button
            type="button"
            onClick={() => setShowJson(!showJson)}
            className="text-xs text-blue-600 hover:underline"
          >
            {showJson ? 'Ẩn JSON' : 'Xem JSON'}
          </button>
        </div>
        
        {/* Key Match Expression */}
        <div className="mb-3">
          <label className="block text-xs text-gray-500 mb-1">Key Match Expression:</label>
          <div className="bg-white p-2 rounded border font-mono text-xs break-all text-gray-700">
            {(showAdvanced ? keyMatch.expression : generateKeyExpression()) || <span className="text-gray-400 italic">Chưa cấu hình</span>}
          </div>
        </div>

        {/* Amount Match Expression */}
        <div className="mb-3">
          <label className="block text-xs text-gray-500 mb-1">Amount Match Expression:</label>
          <div className="bg-white p-2 rounded border font-mono text-xs break-all text-gray-700">
            {(showAdvanced ? amountMatch.expression : generateAmountExpression()) || <span className="text-gray-400 italic">Chưa cấu hình</span>}
          </div>
        </div>
        
        {/* JSON View */}
        {showJson && (
          <div className="mt-3">
            <label className="block text-xs text-gray-500 mb-1">JSON Config:</label>
            <pre className="bg-gray-800 text-green-400 p-3 rounded text-xs overflow-auto max-h-60">
              {JSON.stringify(matchingRules, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================
// EXPRESSION RULE BUILDER - inline rule editor for EXPRESSION columns
// New data structure:
//   when: [ [{column, value}, ...], [...] ]  → OR of AND-groups
//   then: "result_value"
// ============================================
// Operator definitions for EXPRESSION rule conditions
const EXPRESSION_OPERATORS = [
  { value: 'eq', label: '=', hint: 'Bằng' },
  { value: 'ne', label: '≠', hint: 'Khác' },
  { value: 'gt', label: '>', hint: 'Lớn hơn (số)' },
  { value: 'lt', label: '<', hint: 'Nhỏ hơn (số)' },
  { value: 'gte', label: '≥', hint: 'Lớn hơn hoặc bằng' },
  { value: 'lte', label: '≤', hint: 'Nhỏ hơn hoặc bằng' },
  { value: 'contains', label: 'Chứa', hint: 'Chuỗi chứa (ko phân biệt hoa thường)' },
  { value: 'is_not_empty', label: 'Có giá trị', hint: 'Không rỗng / không null' },
  { value: 'is_empty', label: 'Rỗng', hint: 'Rỗng hoặc null' },
  { value: 'func', label: 'Hàm', hint: 'Biểu thức Python (COL là cột hiện tại)' },
]

function ExpressionRuleBuilder({ expression, onChange, availableColumns }) {
  const rules = expression?.rules || []
  const defaultVal = expression?.default || ''

  const updateRules = (newRules) => {
    onChange({ ...expression, rules: newRules, default: defaultVal })
  }

  // --- Rule CRUD ---
  const addRule = () => {
    // New rule with one OR-group containing one empty condition
    const firstCol = availableColumns[0] || ''
    updateRules([...rules, {
      when: [[{ column: firstCol, op: 'eq', value: '' }]],
      then: ''
    }])
  }
  
  const removeRule = (ruleIdx) => {
    updateRules(rules.filter((_, i) => i !== ruleIdx))
  }
  
  const updateRuleThen = (ruleIdx, value) => {
    const newRules = [...rules]
    newRules[ruleIdx] = { ...newRules[ruleIdx], then: value }
    updateRules(newRules)
  }
  
  // --- OR group CRUD ---
  const addOrGroup = (ruleIdx) => {
    const newRules = [...rules]
    const when = [...(newRules[ruleIdx].when || [])]
    const firstCol = availableColumns[0] || ''
    when.push([{ column: firstCol, op: 'eq', value: '' }])
    newRules[ruleIdx] = { ...newRules[ruleIdx], when }
    updateRules(newRules)
  }
  
  const removeOrGroup = (ruleIdx, groupIdx) => {
    const newRules = [...rules]
    const when = [...(newRules[ruleIdx].when || [])]
    when.splice(groupIdx, 1)
    newRules[ruleIdx] = { ...newRules[ruleIdx], when }
    updateRules(newRules)
  }
  
  // --- AND condition CRUD within a group ---
  const addCondition = (ruleIdx, groupIdx) => {
    const newRules = [...rules]
    const when = [...(newRules[ruleIdx].when || [])]
    const group = [...(when[groupIdx] || [])]
    const firstCol = availableColumns[0] || ''
    group.push({ column: firstCol, op: 'eq', value: '' })
    when[groupIdx] = group
    newRules[ruleIdx] = { ...newRules[ruleIdx], when }
    updateRules(newRules)
  }
  
  const removeCondition = (ruleIdx, groupIdx, condIdx) => {
    const newRules = [...rules]
    const when = [...(newRules[ruleIdx].when || [])]
    const group = [...(when[groupIdx] || [])]
    group.splice(condIdx, 1)
    // If group is empty after removal, remove the whole group
    if (group.length === 0) {
      when.splice(groupIdx, 1)
    } else {
      when[groupIdx] = group
    }
    newRules[ruleIdx] = { ...newRules[ruleIdx], when }
    updateRules(newRules)
  }
  
  const updateCondition = (ruleIdx, groupIdx, condIdx, field, value) => {
    const newRules = [...rules]
    const when = [...(newRules[ruleIdx].when || [])]
    const group = [...(when[groupIdx] || [])]
    group[condIdx] = { ...group[condIdx], [field]: value }
    when[groupIdx] = group
    newRules[ruleIdx] = { ...newRules[ruleIdx], when }
    updateRules(newRules)
  }
  
  return (
    <div className="mt-2 ml-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-amber-800">
          🔧 Rules (đánh giá từ trên xuống, rule đầu tiên khớp sẽ được dùng)
        </span>
        <button
          onClick={addRule}
          className="text-xs text-amber-700 hover:text-amber-900 px-2 py-0.5 rounded border border-amber-300 hover:bg-amber-100"
        >
          + Thêm Rule
        </button>
      </div>
      
      {availableColumns.length === 0 && (
        <div className="text-xs text-red-500 bg-red-50 p-2 rounded mb-2">
          ⚠️ Chưa có cột nguồn nào được cấu hình. Thêm các cột output (không phải EXPRESSION) trước để dùng trong điều kiện.
        </div>
      )}
      
      {rules.length > 0 ? (
        <div className="space-y-2">
          {rules.map((rule, ruleIdx) => {
            const whenGroups = Array.isArray(rule.when) ? rule.when : []
            return (
              <div key={ruleIdx} className="bg-white rounded border p-2">
                <div className="flex items-start gap-2">
                  <span className="text-xs font-medium text-gray-500 mt-1 flex-shrink-0 w-6">
                    #{ruleIdx + 1}
                  </span>
                  <div className="flex-1 space-y-1">
                    <div className="text-xs text-gray-500 font-medium">KHI:</div>
                    
                    {/* OR groups */}
                    {whenGroups.map((group, groupIdx) => (
                      <div key={groupIdx}>
                        {groupIdx > 0 && (
                          <div className="flex items-center gap-2 my-1">
                            <div className="flex-1 border-t border-orange-200"></div>
                            <span className="text-xs font-bold text-orange-500 px-2">HOẶC</span>
                            <div className="flex-1 border-t border-orange-200"></div>
                          </div>
                        )}
                        <div className="ml-2 pl-2 border-l-2 border-blue-200 space-y-1">
                          {/* AND conditions within group */}
                          {(group || []).map((cond, condIdx) => {
                            const condOp = cond.op || 'eq'
                            const noValueOps = ['is_empty', 'is_not_empty']
                            const isFuncOp = condOp === 'func'
                            const needsValue = !noValueOps.includes(condOp)
                            return (
                              <div key={condIdx} className={`flex ${isFuncOp ? 'items-start' : 'items-center'} gap-1.5`}>
                                {condIdx > 0 && <span className="text-xs text-blue-600 font-semibold w-8 text-center mt-1">VÀ</span>}
                                {condIdx === 0 && <span className="w-8"></span>}
                                <select
                                  value={cond.column || ''}
                                  onChange={(e) => updateCondition(ruleIdx, groupIdx, condIdx, 'column', e.target.value)}
                                  className="px-1.5 py-1 border rounded text-xs bg-blue-50 min-w-[130px]"
                                >
                                  <option value="">-- Chọn cột --</option>
                                  {availableColumns.map(c => (
                                    <option key={c} value={c}>{c}</option>
                                  ))}
                                </select>
                                <select
                                  value={condOp}
                                  onChange={(e) => updateCondition(ruleIdx, groupIdx, condIdx, 'op', e.target.value)}
                                  className="px-1 py-1 border rounded text-xs bg-amber-50 font-medium min-w-[85px]"
                                  title={EXPRESSION_OPERATORS.find(o => o.value === condOp)?.hint || ''}
                                >
                                  {EXPRESSION_OPERATORS.map(op => (
                                    <option key={op.value} value={op.value} title={op.hint}>{op.label}</option>
                                  ))}
                                </select>
                                {needsValue && !isFuncOp && (
                                  <input
                                    type="text"
                                    value={cond.value || ''}
                                    onChange={(e) => updateCondition(ruleIdx, groupIdx, condIdx, 'value', e.target.value)}
                                    className="px-1.5 py-1 border rounded text-xs font-mono flex-1 min-w-[100px]"
                                    placeholder="giá trị"
                                  />
                                )}
                                {isFuncOp && (
                                  <textarea
                                    value={cond.value || ''}
                                    onChange={(e) => updateCondition(ruleIdx, groupIdx, condIdx, 'value', e.target.value)}
                                    className="px-1.5 py-1 border rounded text-xs font-mono flex-1 min-w-[200px] bg-purple-50 resize-y"
                                    placeholder="VD: COL.str.len() > 5 hoặc pd.to_numeric(COL, errors='coerce') > 1000"
                                    rows={2}
                                  />
                                )}
                                <button
                                  onClick={() => removeCondition(ruleIdx, groupIdx, condIdx)}
                                  className="text-red-300 hover:text-red-500 flex-shrink-0"
                                  title="Xóa điều kiện"
                                >
                                  <XMarkIcon className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            )
                          })}
                          <div className="flex items-center gap-2 ml-8">
                            <button
                              onClick={() => addCondition(ruleIdx, groupIdx)}
                              className="text-xs text-blue-500 hover:text-blue-700"
                            >
                              + Thêm điều kiện (VÀ)
                            </button>
                            {whenGroups.length > 1 && (
                              <button
                                onClick={() => removeOrGroup(ruleIdx, groupIdx)}
                                className="text-xs text-red-400 hover:text-red-600"
                              >
                                Xóa nhóm
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                    
                    {/* Add OR group button */}
                    <button
                      onClick={() => addOrGroup(ruleIdx)}
                      className="text-xs text-orange-500 hover:text-orange-700 ml-2 mt-1"
                    >
                      + Thêm nhóm điều kiện (HOẶC)
                    </button>
                    
                    {/* Then value */}
                    <div className="flex items-center gap-1.5 mt-1 pt-1 border-t">
                      <span className="text-xs font-medium text-green-700 w-6">→</span>
                      <span className="text-xs text-gray-500">THÌ:</span>
                      <input
                        type="text"
                        value={rule.then || ''}
                        onChange={(e) => updateRuleThen(ruleIdx, e.target.value)}
                        className="px-1.5 py-1 border rounded text-xs font-mono flex-1 bg-green-50"
                        placeholder="giá trị kết quả"
                      />
                    </div>
                  </div>
                  
                  <button
                    onClick={() => removeRule(ruleIdx)}
                    className="text-red-400 hover:text-red-600 flex-shrink-0 mt-1"
                    title="Xóa rule"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-xs text-gray-400 text-center py-2 bg-white rounded border border-dashed">
          Chưa có rule. Click "Thêm Rule" để bắt đầu.
        </div>
      )}
      
      {/* Default value */}
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-amber-200">
        <span className="text-xs font-medium text-gray-600">Giá trị mặc định:</span>
        <input
          type="text"
          value={defaultVal}
          onChange={(e) => onChange({ ...expression, rules, default: e.target.value })}
          className="px-2 py-1 border rounded text-xs font-mono flex-1 bg-gray-50"
          placeholder="Giá trị khi không khớp rule nào"
        />
      </div>
    </div>
  )
}

// ============================================
// WORKFLOW OUTPUT COLUMNS EDITOR (dành cho từng workflow step)
// ============================================
function WorkflowOutputColumnsEditor({ step, stepId, updateWorkflowStep, dataSources, workflowSteps }) {
  const outputColumns = step.output_columns || []
  
  const setOutputColumns = (newColumns) => {
    updateWorkflowStep(stepId, 'output_columns', newColumns)
  }
  
  // --- Validation ---
  const getValidationErrors = () => {
    const errors = []
    const displayNames = []
    
    outputColumns.forEach((col, idx) => {
      const rowNum = idx + 1
      if (!col.source) {
        errors.push({ idx, field: 'source', msg: `Cột #${rowNum}: Chưa chọn Nguồn` })
      }
      if (!col.display_name) {
        errors.push({ idx, field: 'display_name', msg: `Cột #${rowNum}: Chưa có Tên cột output` })
      }
      // Track display_names for duplicate check
      const dn = (col.display_name || '').trim()
      if (dn) {
        displayNames.push({ idx, dn })
      }
    })
    
    // Check duplicate display_name
    const seen = {}
    displayNames.forEach(({ idx, dn }) => {
      if (seen[dn] !== undefined) {
        // Mark both the first and current as duplicate
        if (!errors.find(e => e.idx === seen[dn] && e.field === 'display_name_dup')) {
          errors.push({ idx: seen[dn], field: 'display_name_dup', msg: `Cột #${seen[dn] + 1}: Tên hiển thị "${dn}" bị trùng` })
        }
        errors.push({ idx, field: 'display_name_dup', msg: `Cột #${idx + 1}: Tên hiển thị "${dn}" bị trùng` })
      } else {
        seen[dn] = idx
      }
    })
    
    return errors
  }
  
  const validationErrors = getValidationErrors()
  const hasError = (colIdx, field) => validationErrors.some(e => e.idx === colIdx && e.field === field)
  const hasDisplayNameError = (colIdx) => hasError(colIdx, 'display_name') || hasError(colIdx, 'display_name_dup')
  const errorBorder = 'border-red-400 ring-1 ring-red-300 bg-red-50'
  
  const addColumn = () => {
    setOutputColumns([
      ...outputColumns,
      { id: `col_${Date.now()}`, source: '', source_column: '', display_name: '' }
    ])
  }
  
  const updateColumn = (colIdx, field, value) => {
    const updated = [...outputColumns]
    updated[colIdx] = { ...updated[colIdx], [field]: value }
    // When switching to EXPRESSION, initialize expression config
    if (field === 'source' && value === 'EXPRESSION') {
      updated[colIdx] = {
        ...updated[colIdx],
        source_column: '',
        expression: updated[colIdx].expression || { rules: [], default: '' }
      }
    }
    // When switching away from EXPRESSION, clean up
    if (field === 'source' && value !== 'EXPRESSION') {
      const { expression, ...rest } = updated[colIdx]
      updated[colIdx] = rest
    }
    setOutputColumns(updated)
  }
  
  // Update expression config for EXPRESSION columns
  const updateExpression = (colIdx, exprConfig) => {
    const updated = [...outputColumns]
    updated[colIdx] = { ...updated[colIdx], expression: exprConfig }
    setOutputColumns(updated)
  }
  
  // Hàm đặc biệt khi chọn cột nguồn - tự động fill các trường khác
  const onSelectSourceColumn = (colIdx, columnName) => {
    const updated = [...outputColumns]
    const current = updated[colIdx]
    updated[colIdx] = {
      ...current,
      source_column: columnName,
      // Tự động fill tên cột output = tên cột chọn (nếu chưa có)
      display_name: current.display_name || columnName
    }
    setOutputColumns(updated)
  }
  
  const removeColumn = (colIdx) => {
    setOutputColumns(outputColumns.filter((_, i) => i !== colIdx))
  }
  
  // Chỉ cho chọn từ left_source và right_source của step này + MATCH_STATUS + EXPRESSION
  const availableSources = [
    step.left_source,
    step.right_source,
    'MATCH_STATUS',  // Trạng thái so khớp
    'EXPRESSION'     // Cột tính toán từ các cột khác (combine status)
  ].filter(Boolean)
  
  // Get display_names of all non-EXPRESSION columns (for EXPRESSION rule builder)
  const getNonExpressionColumnNames = () => {
    return outputColumns
      .filter(c => c.source !== 'EXPRESSION')
      .map(c => c.display_name)
      .filter(Boolean)
  }
  
  // Get columns from a source - trả về alias
  // Hỗ trợ cả workflow output (kết quả trung gian)
  const getSourceColumns = (sourceName) => {
    // Special case: MATCH_STATUS
    if (sourceName === 'MATCH_STATUS') {
      return ['match_status', 'match_detail', 'amount_difference', 'left_key', 'right_key', 'left_amount', 'right_amount']
    }
    
    // EXPRESSION has no source columns - uses rule builder instead
    if (sourceName === 'EXPRESSION') {
      return []
    }
    
    // 1. Tìm trong dataSources trước
    const ds = dataSources.find(d => d.source_name === sourceName)
    if (ds) {
      // FILE_UPLOAD: lấy từ file_config.columns → alias
      if (ds.source_type === 'FILE_UPLOAD' && ds.file_config?.columns) {
        const cols = ds.file_config.columns
        if (Array.isArray(cols)) return cols.map(c => c.alias || c.source).filter(Boolean)
        return Object.keys(cols)
      }
      
      // DATABASE: lấy từ db_config.output_columns → alias (hoặc name nếu chưa migrate)
      if (ds.source_type === 'DATABASE' && ds.db_config?.output_columns) {
        return ds.db_config.output_columns.map(c => c.alias || c.name).filter(Boolean)
      }
      
      // API: lấy từ api_config.output_columns → alias
      if (ds.source_type === 'API' && ds.api_config?.output_columns) {
        return ds.api_config.output_columns.map(c => c.alias || c.name).filter(Boolean)
      }
      
      // SFTP: tương tự FILE_UPLOAD → alias
      if (ds.source_type === 'SFTP' && ds.sftp_config?.columns) {
        const cols = ds.sftp_config.columns
        if (Array.isArray(cols)) return cols.map(c => c.alias || c.source).filter(Boolean)
        return Object.keys(cols)
      }
      
      return []
    }
    
    // 2. Nếu không tìm thấy trong dataSources, tìm trong workflow step outputs
    const previousStep = workflowSteps.find(ws => ws.output_name === sourceName && !ws.isDeleted)
    if (previousStep) {
      // Nếu step trước có output_columns đã cấu hình, lấy từ đó
      if (previousStep.output_columns && Array.isArray(previousStep.output_columns) && previousStep.output_columns.length > 0) {
        return previousStep.output_columns.map(c => c.display_name || c.column_name).filter(Boolean)
      }
      
      // Nếu chưa có output_columns, merge columns từ left_source và right_source của step đó
      const leftCols = getSourceColumns(previousStep.left_source)
      const rightCols = getSourceColumns(previousStep.right_source)
      const mergedCols = [...new Set([...leftCols, ...rightCols, 'match_status'])]
      return mergedCols
    }
    
    return []
  }
  
  return (
    <div className="bg-indigo-50 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h5 className="font-medium text-indigo-800 flex items-center gap-2">
          📊 Cấu hình các cột Output
          <span className="text-xs font-normal text-indigo-600">
            (Chọn các cột cần lấy ra từ kết quả đối soát)
          </span>
        </h5>
        <button
          onClick={addColumn}
          className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center px-3 py-1 rounded-lg border border-indigo-300 hover:bg-indigo-100"
        >
          <PlusIcon className="h-4 w-4 mr-1" />
          Thêm cột
        </button>
      </div>
      
      {/* Validation warnings */}
      {validationErrors.length > 0 && outputColumns.length > 0 && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-xs font-semibold text-red-700 mb-1">⚠️ Cảnh báo ({validationErrors.length}):</div>
          <ul className="text-xs text-red-600 space-y-0.5 list-disc list-inside">
            {validationErrors.map((err, i) => (
              <li key={i}>{err.msg}</li>
            ))}
          </ul>
        </div>
      )}
      
      {outputColumns.length > 0 ? (
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 font-medium px-1">
            <div className="col-span-2">1. Nguồn</div>
            <div className="col-span-3">2. Cột nguồn</div>
            <div className="col-span-4">3. Tên cột output</div>
            <div className="col-span-1 text-center" title="Cho phép lọc theo cột này trong kết quả">Lọc</div>
            <div className="col-span-1"></div>
          </div>
          
          {outputColumns.map((col, colIdx) => (
            <div key={col.id || colIdx} className="bg-white p-2 rounded-lg border">
              <div className="grid grid-cols-12 gap-2">
              {/* 1. Nguồn */}
              <select
                value={col.source || ''}
                onChange={(e) => updateColumn(colIdx, 'source', e.target.value)}
                className={`col-span-2 px-2 py-1.5 border rounded text-sm ${hasError(colIdx, 'source') ? errorBorder : 'bg-blue-50'}`}
              >
                <option value="">-- Chọn --</option>
                {availableSources.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              
              {col.source === 'EXPRESSION' ? (
                <>
                  {/* EXPRESSION: no source_column, just display_name */}
                  <div className="col-span-3 text-xs text-gray-400 flex items-center px-2">
                    ← Cấu hình rules bên dưới
                  </div>

                  {/* Tên cột output */}
                  <input
                    type="text"
                    value={col.display_name || ''}
                    onChange={(e) => updateColumn(colIdx, 'display_name', e.target.value)}
                    className={`col-span-4 px-2 py-1.5 border rounded text-sm font-mono ${hasDisplayNameError(colIdx) ? errorBorder : ''}`}
                    placeholder="vd: final_status"
                  />
                </>
              ) : (
                <>
                  {/* 2. Cột nguồn */}
                  <div className="col-span-3">
                    {col.source && getSourceColumns(col.source).length > 0 ? (
                      <select
                        value={col.source_column || ''}
                        onChange={(e) => onSelectSourceColumn(colIdx, e.target.value)}
                        className="w-full px-2 py-1.5 border rounded text-sm bg-green-50"
                      >
                        <option value="">-- Chọn cột --</option>
                        {getSourceColumns(col.source).map(c => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    ) : col.source ? (
                      <input
                        type="text"
                        value={col.source_column || ''}
                        onChange={(e) => onSelectSourceColumn(colIdx, e.target.value)}
                        className="w-full px-2 py-1.5 border rounded text-sm font-mono"
                        placeholder="Nhập tên cột"
                      />
                    ) : (
                      <span className="text-xs text-gray-400 px-2 py-1.5 block">← Chọn nguồn trước</span>
                    )}
                  </div>

                  {/* 3. Tên cột output (auto-filled from source_column) */}
                  <input
                    type="text"
                    value={col.display_name || ''}
                    onChange={(e) => updateColumn(colIdx, 'display_name', e.target.value)}
                    className={`col-span-4 px-2 py-1.5 border rounded text-sm font-mono ${hasDisplayNameError(colIdx) ? errorBorder : ''}`}
                    placeholder="(auto-fill)"
                  />
                </>
              )}

              {/* Filterable checkbox */}
              <div className="col-span-1 flex items-center justify-center">
                <input
                  type="checkbox"
                  checked={!!col.filterable}
                  onChange={(e) => updateColumn(colIdx, 'filterable', e.target.checked)}
                  className="h-4 w-4 text-indigo-600 border-gray-300 rounded cursor-pointer"
                  title="Cho phép lọc theo cột này"
                />
              </div>

              <button
                onClick={() => removeColumn(colIdx)}
                className="col-span-1 text-red-400 hover:text-red-600 flex items-center justify-center"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
              </div>
              
              {/* EXPRESSION Rule Builder - shown below the row */}
              {col.source === 'EXPRESSION' && (
                <ExpressionRuleBuilder
                  expression={col.expression || { rules: [], default: '' }}
                  onChange={(expr) => updateExpression(colIdx, expr)}
                  availableColumns={getNonExpressionColumnNames()}
                />
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-gray-500 text-center py-6 bg-white rounded-lg border-2 border-dashed">
          Chưa có cột output. Click "Thêm cột" để cấu hình các cột cần xuất ra từ kết quả đối soát.
        </div>
      )}
      
      {/* Quick add helper */}
      {outputColumns.length === 0 && (
        <div className="mt-3 flex items-center gap-2 text-xs text-indigo-600">
          <span>💡 Gợi ý:</span>
          <button
            onClick={() => {
              const leftSource = step.left_source
              const rightSource = step.right_source
              const baseCols = [
                { id: 'col_1', source: '', source_column: '', display_name: 'Trạng thái' },
                { id: 'col_2', source: leftSource, source_column: '', display_name: 'Mã GD (Trái)' },
                { id: 'col_3', source: rightSource, source_column: '', display_name: 'Mã GD (Phải)' },
              ]
              setOutputColumns(baseCols)
            }}
            className="hover:underline"
          >
            Thêm các cột cơ bản
          </button>
        </div>
      )}
    </div>
  )
}

// ============================================
// (Old) MATCHING RULES EDITOR COMPONENT - kept for reference
// ============================================
function MatchingRulesEditor({ step, index, updateWorkflowStep, dataSources }) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  
  const matchingRules = step.matching_rules || { match_type: 'expression', rules: [], status_logic: {} }
  const rules = matchingRules.rules || []
  
  const updateMatchingRules = (newRules) => {
    updateWorkflowStep(index, 'matching_rules', {
      ...matchingRules,
      rules: newRules
    })
  }
  
  const addRule = (type) => {
    const newRule = type === 'key_match' 
      ? {
          id: `rule_${Date.now()}`,
          rule_name: `key_match_${rules.length + 1}`,
          type: 'expression',
          expression: '',
          _ui_config: {
            mode: 'simple',
            ruleType: 'key_match',
            leftColumns: [],
            rightColumns: [],
            separator: '',
            transforms: ['strip', 'upper'],
            matchMode: 'exact'
          }
        }
      : {
          id: `rule_${Date.now()}`,
          rule_name: `amount_match_${rules.length + 1}`,
          type: 'expression',
          expression: '',
          _ui_config: {
            mode: 'simple',
            ruleType: 'amount_match',
            leftColumn: '',
            rightColumn: '',
            tolerance: 0,
            toleranceType: 'absolute'
          }
        }
    updateMatchingRules([...rules, newRule])
  }
  
  const updateRule = (ruleIdx, field, value) => {
    const newRules = [...rules]
    if (field.startsWith('_ui_config.')) {
      const uiField = field.replace('_ui_config.', '')
      newRules[ruleIdx] = {
        ...newRules[ruleIdx],
        _ui_config: { ...newRules[ruleIdx]._ui_config, [uiField]: value }
      }
    } else {
      newRules[ruleIdx] = { ...newRules[ruleIdx], [field]: value }
    }
    updateMatchingRules(newRules)
  }
  
  const removeRule = (ruleIdx) => {
    updateMatchingRules(rules.filter((_, i) => i !== ruleIdx))
  }
  
  // Get available columns from left and right sources
  const leftSource = dataSources.find(ds => ds.source_name === step.left_source)
  const rightSource = dataSources.find(ds => ds.source_name === step.right_source)
  
  const getColumnsForSource = (source) => {
    if (!source) return []
    
    // FILE_UPLOAD: lấy từ file_config.columns
    if (source.source_type === 'FILE_UPLOAD' && source.file_config?.columns) {
      const cols = source.file_config.columns
      if (Array.isArray(cols)) {
        return cols.map(c => c.alias).filter(Boolean)
      }
      return Object.keys(cols)
    }
    
    // DATABASE: lấy từ db_config.output_columns
    if (source.source_type === 'DATABASE' && source.db_config?.output_columns) {
      return source.db_config.output_columns.map(c => c.name).filter(Boolean)
    }
    
    // API: lấy từ api_config.output_columns
    if (source.source_type === 'API' && source.api_config?.output_columns) {
      return source.api_config.output_columns.map(c => c.name).filter(Boolean)
    }
    
    // SFTP: tương tự FILE_UPLOAD
    if (source.source_type === 'SFTP' && source.sftp_config?.columns) {
      const cols = source.sftp_config.columns
      if (Array.isArray(cols)) {
        return cols.map(c => c.alias).filter(Boolean)
      }
      return Object.keys(cols)
    }
    
    return []
  }
  
  const leftColumns = getColumnsForSource(leftSource)
  const rightColumns = getColumnsForSource(rightSource)
  
  return (
    <div className="bg-amber-50 rounded-lg p-4">
      <div className="flex justify-between items-center mb-3">
        <h5 className="font-medium text-amber-800">🔗 Matching Rules</h5>
        <div className="flex items-center gap-2">
          <label className="flex items-center text-xs text-gray-500">
            <input
              type="checkbox"
              checked={showAdvanced}
              onChange={(e) => setShowAdvanced(e.target.checked)}
              className="rounded border-gray-300 text-amber-600 mr-1"
            />
            Nâng cao
          </label>
        </div>
      </div>
      
      {/* Rules List */}
      <div className="space-y-3">
        {rules.map((rule, ruleIdx) => (
          <div key={rule.id || ruleIdx} className="bg-white rounded-lg p-3 border">
            <div className="flex justify-between items-center mb-2">
              <input
                type="text"
                value={rule.rule_name}
                onChange={(e) => updateRule(ruleIdx, 'rule_name', e.target.value)}
                className="font-medium text-sm border-b border-transparent hover:border-gray-300 focus:border-amber-500 outline-none px-1"
              />
              <button
                onClick={() => removeRule(ruleIdx)}
                className="text-red-400 hover:text-red-600"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
            
            {showAdvanced ? (
              /* Advanced Mode - Raw Expression */
              <div>
                <label className="block text-xs text-gray-500 mb-1">Expression (Pandas)</label>
                <textarea
                  value={rule.expression}
                  onChange={(e) => updateRule(ruleIdx, 'expression', e.target.value)}
                  className="w-full px-2 py-1 border rounded text-xs font-mono h-16"
                  placeholder="left['txn_id'].str.strip() == right['ref'].str.strip()"
                />
              </div>
            ) : (
              /* Simple Mode */
              <div className="space-y-2">
                {rule._ui_config?.ruleType === 'key_match' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Cột bên trái ({step.left_source})</label>
                      <select
                        value={rule._ui_config?.leftColumns?.[0] || ''}
                        onChange={(e) => updateRule(ruleIdx, '_ui_config.leftColumns', [e.target.value])}
                        className="w-full px-2 py-1 border rounded text-sm"
                      >
                        <option value="">-- Chọn cột --</option>
                        {leftColumns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Cột bên phải ({step.right_source})</label>
                      <select
                        value={rule._ui_config?.rightColumns?.[0] || ''}
                        onChange={(e) => updateRule(ruleIdx, '_ui_config.rightColumns', [e.target.value])}
                        className="w-full px-2 py-1 border rounded text-sm"
                      >
                        <option value="">-- Chọn cột --</option>
                        {rightColumns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs text-gray-500 mb-1">Transforms</label>
                      <div className="flex gap-3 text-xs">
                        {['strip', 'upper', 'lower'].map(t => (
                          <label key={t} className="flex items-center">
                            <input
                              type="checkbox"
                              checked={rule._ui_config?.transforms?.includes(t)}
                              onChange={(e) => {
                                const current = rule._ui_config?.transforms || []
                                const newTransforms = e.target.checked 
                                  ? [...current, t]
                                  : current.filter(x => x !== t)
                                updateRule(ruleIdx, '_ui_config.transforms', newTransforms)
                              }}
                              className="rounded border-gray-300 text-amber-600 mr-1"
                            />
                            {t}
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
                
                {rule._ui_config?.ruleType === 'amount_match' && (
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Cột tiền ({step.left_source})</label>
                      <select
                        value={rule._ui_config?.leftColumn || ''}
                        onChange={(e) => updateRule(ruleIdx, '_ui_config.leftColumn', e.target.value)}
                        className="w-full px-2 py-1 border rounded text-sm"
                      >
                        <option value="">-- Chọn --</option>
                        {leftColumns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Cột tiền ({step.right_source})</label>
                      <select
                        value={rule._ui_config?.rightColumn || ''}
                        onChange={(e) => updateRule(ruleIdx, '_ui_config.rightColumn', e.target.value)}
                        className="w-full px-2 py-1 border rounded text-sm"
                      >
                        <option value="">-- Chọn --</option>
                        {rightColumns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Cho phép lệch</label>
                      <input
                        type="number"
                        value={rule._ui_config?.tolerance || 0}
                        onChange={(e) => updateRule(ruleIdx, '_ui_config.tolerance', parseFloat(e.target.value) || 0)}
                        className="w-full px-2 py-1 border rounded text-sm"
                        min="0"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        
        {rules.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-2">
            Chưa có rule nào. Thêm rule để định nghĩa cách so khớp.
          </p>
        )}
      </div>
      
      {/* Add Rule Buttons */}
      <div className="flex gap-2 mt-3">
        <button
          onClick={() => addRule('key_match')}
          className="px-3 py-1 text-xs bg-amber-100 text-amber-700 rounded hover:bg-amber-200"
        >
          + Key Match
        </button>
        <button
          onClick={() => addRule('amount_match')}
          className="px-3 py-1 text-xs bg-amber-100 text-amber-700 rounded hover:bg-amber-200"
        >
          + Amount Match
        </button>
      </div>
    </div>
  )
}

// ============================================
// OUTPUT COLUMNS EDITOR COMPONENT
// ============================================
function OutputColumnsEditor({ output, index, updateOutputConfig, dataSources, workflowSteps }) {
  const columnsConfig = output.columns_config || []
  
  // Lấy columns config dưới dạng array
  const getColumnsArray = () => {
    if (!columnsConfig) return []
    if (Array.isArray(columnsConfig)) return columnsConfig
    // Convert từ object
    return Object.entries(columnsConfig).map(([name, config], idx) => ({
      id: `col_${idx}`,
      column_name: name,
      ...config
    }))
  }
  
  const setColumnsArray = (newArray) => {
    updateOutputConfig(index, 'columns_config', newArray)
  }
  
  const addColumn = () => {
    const current = getColumnsArray()
    setColumnsArray([
      ...current,
      { id: `col_${Date.now()}`, column_name: '', source: '', source_column: '', display_name: '' }
    ])
  }
  
  const updateColumn = (colIdx, field, value) => {
    const current = getColumnsArray()
    const updated = [...current]
    updated[colIdx] = { ...updated[colIdx], [field]: value }
    setColumnsArray(updated)
  }
  
  const removeColumn = (colIdx) => {
    const current = getColumnsArray()
    setColumnsArray(current.filter((_, i) => i !== colIdx))
  }
  
  // Get available sources (data sources + workflow outputs)
  const availableSources = [
    ...dataSources.filter(ds => !ds.isDeleted).map(ds => ds.source_name),
    ...workflowSteps.filter(ws => !ws.isDeleted).map(ws => ws.output_name)
  ]
  
  // Get columns from a source - trả về alias
  // Hỗ trợ cả workflow output (kết quả trung gian)
  const getSourceColumns = (sourceName) => {
    // 1. Tìm trong dataSources trước
    const ds = dataSources.find(d => d.source_name === sourceName)
    if (ds) {
      // FILE_UPLOAD: lấy từ file_config.columns → alias
      if (ds.source_type === 'FILE_UPLOAD' && ds.file_config?.columns) {
        const cols = ds.file_config.columns
        if (Array.isArray(cols)) return cols.map(c => c.alias).filter(Boolean)
        return Object.keys(cols)
      }
      
      // DATABASE: lấy từ db_config.output_columns → alias (hoặc name nếu chưa migrate)
      if (ds.source_type === 'DATABASE' && ds.db_config?.output_columns) {
        return ds.db_config.output_columns.map(c => c.alias || c.name).filter(Boolean)
      }
      
      // API: lấy từ api_config.output_columns → alias
      if (ds.source_type === 'API' && ds.api_config?.output_columns) {
        return ds.api_config.output_columns.map(c => c.alias || c.name).filter(Boolean)
      }
      
      // SFTP: tương tự FILE_UPLOAD → alias
      if (ds.source_type === 'SFTP' && ds.sftp_config?.columns) {
        const cols = ds.sftp_config.columns
        if (Array.isArray(cols)) return cols.map(c => c.alias).filter(Boolean)
        return Object.keys(cols)
      }
      
      return []
    }
    
    // 2. Nếu không tìm thấy trong dataSources, tìm trong workflow step outputs
    const previousStep = workflowSteps.find(ws => ws.output_name === sourceName && !ws.isDeleted)
    if (previousStep) {
      // Nếu step trước có output_columns đã cấu hình, lấy từ đó
      if (previousStep.output_columns && Array.isArray(previousStep.output_columns) && previousStep.output_columns.length > 0) {
        return previousStep.output_columns.map(c => c.column_name || c.display_name).filter(Boolean)
      }
      
      // Nếu chưa có output_columns, merge columns từ left_source và right_source của step đó
      const leftCols = getSourceColumns(previousStep.left_source)
      const rightCols = getSourceColumns(previousStep.right_source)
      const mergedCols = [...new Set([...leftCols, ...rightCols, 'match_status'])]
      return mergedCols
    }
    
    return []
  }
  
  const columns = getColumnsArray()
  
  return (
    <div className="bg-indigo-50 rounded-lg p-4 mt-3">
      <div className="flex justify-between items-center mb-3">
        <h5 className="font-medium text-indigo-800">📊 Output Columns</h5>
        <button
          onClick={addColumn}
          className="text-sm text-indigo-600 hover:text-indigo-800 flex items-center"
        >
          <PlusIcon className="h-4 w-4 mr-1" />
          Thêm cột
        </button>
      </div>
      
      {columns.length > 0 ? (
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 font-medium">
            <div className="col-span-3">Tên cột output</div>
            <div className="col-span-2">Nguồn</div>
            <div className="col-span-3">Cột nguồn</div>
            <div className="col-span-3">Tên hiển thị</div>
            <div className="col-span-1"></div>
          </div>
          
          {columns.map((col, colIdx) => (
            <div key={col.id} className="grid grid-cols-12 gap-2">
              <input
                type="text"
                value={col.column_name || ''}
                onChange={(e) => updateColumn(colIdx, 'column_name', e.target.value)}
                className="col-span-3 px-2 py-1 border rounded text-sm"
                placeholder="txn_id"
              />
              <select
                value={col.source || ''}
                onChange={(e) => updateColumn(colIdx, 'source', e.target.value)}
                className="col-span-2 px-2 py-1 border rounded text-sm"
              >
                <option value="">--</option>
                {availableSources.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <select
                value={col.source_column || ''}
                onChange={(e) => updateColumn(colIdx, 'source_column', e.target.value)}
                className="col-span-3 px-2 py-1 border rounded text-sm"
              >
                <option value="">-- Chọn cột --</option>
                {getSourceColumns(col.source).map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
                <option value="_custom">Nhập tay...</option>
              </select>
              <input
                type="text"
                value={col.display_name || ''}
                onChange={(e) => updateColumn(colIdx, 'display_name', e.target.value)}
                className="col-span-3 px-2 py-1 border rounded text-sm"
                placeholder="Mã GD"
              />
              <button
                onClick={() => removeColumn(colIdx)}
                className="col-span-1 text-red-400 hover:text-red-600 flex items-center justify-center"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-500 text-center py-4">
          Chưa có cột output. Click "Thêm cột" để cấu hình các cột xuất ra.
        </p>
      )}
    </div>
  )
}

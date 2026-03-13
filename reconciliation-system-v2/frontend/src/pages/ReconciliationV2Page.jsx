import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  ArrowPathIcon,
  CloudArrowUpIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  ArchiveBoxIcon,
  TableCellsIcon,
  DocumentArrowUpIcon
} from '@heroicons/react/24/outline'
import { configsApiV2, dataSourcesApiV2, reconciliationApiV2 } from '../services/api'
import { useAuthStore } from '../stores/authStore'

// Supported file extensions
const ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.xlsb', '.csv', '.zip']
const ACCEPT_STRING = '.xlsx,.xls,.xlsb,.csv,.zip'

function getFileIcon(filename) {
  const ext = filename.split('.').pop()?.toLowerCase()
  if (ext === 'zip') return ArchiveBoxIcon
  if (['xlsx', 'xls', 'xlsb'].includes(ext)) return TableCellsIcon
  if (ext === 'csv') return DocumentTextIcon
  return DocumentArrowUpIcon
}

function getFileTypeLabel(filename) {
  const ext = filename.split('.').pop()?.toLowerCase()
  if (ext === 'zip') return 'ZIP'
  if (['xlsx', 'xls', 'xlsb'].includes(ext)) return 'Excel'
  if (ext === 'csv') return 'CSV'
  return ext?.toUpperCase()
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function isValidFile(filename) {
  const ext = '.' + filename.split('.').pop()?.toLowerCase()
  return ALLOWED_EXTENSIONS.includes(ext)
}

export default function ReconciliationV2Page() {
  const navigate = useNavigate()
  const { user } = useAuthStore()

  // State
  const [step, setStep] = useState(1) // 1: Select config, 2: Upload files, 3: Run & Review
  const [configs, setConfigs] = useState([])
  const [selectedConfig, setSelectedConfig] = useState(null)
  const [dataSources, setDataSources] = useState([])
  const [uploadedFiles, setUploadedFiles] = useState({}) // source_name -> File[] (array of files)
  const [periodFrom, setPeriodFrom] = useState('')
  const [periodTo, setPeriodTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [errorLogs, setErrorLogs] = useState([]) // step_logs from failed execution
  const [batchFolder, setBatchFolder] = useState(null)
  const [result, setResult] = useState(null)
  const [dragOver, setDragOver] = useState({}) // source_name -> boolean
  const [duplicateWarning, setDuplicateWarning] = useState(null) // { duplicates, message }
  const [needForceReplace, setNeedForceReplace] = useState(false) // true if user confirmed replace at step 2

  // Load configs (re-run when user permissions change)
  useEffect(() => {
    loadConfigs()
  }, [user])

  // Load data sources when config selected
  useEffect(() => {
    if (selectedConfig) {
      loadDataSources(selectedConfig.id)
    }
  }, [selectedConfig])

  const loadConfigs = async () => {
    try {
      setLoading(true)
      const response = await configsApiV2.list({ page: 1, page_size: 100 })
      let activeConfigs = response.data.items.filter(c => c.is_active)

      // Filter configs by user's can_reconcile permission (admin sees all)
      if (!user?.is_admin) {
        const permissions = user?.permissions || []
        const allowedPairs = permissions
          .filter(p => p.can_reconcile)
          .map(p => `${p.partner_code}_${p.service_code}`)
        activeConfigs = activeConfigs.filter(c =>
          allowedPairs.includes(`${c.partner_code}_${c.service_code}`)
        )
      }

      setConfigs(activeConfigs)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách cấu hình')
    } finally {
      setLoading(false)
    }
  }

  const loadDataSources = async (configId) => {
    try {
      const response = await dataSourcesApiV2.getByConfig(configId)
      setDataSources(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải nguồn dữ liệu')
    }
  }

  const handleFileChange = (sourceName, fileList) => {
    const newFiles = Array.from(fileList)
    // Validate file types
    const validFiles = newFiles.filter(f => isValidFile(f.name))
    const invalidFiles = newFiles.filter(f => !isValidFile(f.name))
    
    if (invalidFiles.length > 0) {
      setError(`File không hỗ trợ: ${invalidFiles.map(f => f.name).join(', ')}. Chỉ chấp nhận: ${ALLOWED_EXTENSIONS.join(', ')}`)
      // Still add valid files
    }
    
    if (validFiles.length > 0) {
      setUploadedFiles(prev => ({
        ...prev,
        [sourceName]: [...(prev[sourceName] || []), ...validFiles]
      }))
    }
  }

  const handleRemoveFile = (sourceName, fileIndex) => {
    setUploadedFiles(prev => ({
      ...prev,
      [sourceName]: prev[sourceName].filter((_, idx) => idx !== fileIndex)
    }))
  }

  const handleClearSource = (sourceName) => {
    setUploadedFiles(prev => ({
      ...prev,
      [sourceName]: []
    }))
  }

  // Drag and drop handlers
  const handleDragOver = (e, sourceName) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(prev => ({ ...prev, [sourceName]: true }))
  }

  const handleDragLeave = (e, sourceName) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(prev => ({ ...prev, [sourceName]: false }))
  }

  const handleDrop = (e, sourceName) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(prev => ({ ...prev, [sourceName]: false }))
    
    const files = e.dataTransfer?.files
    if (files?.length > 0) {
      handleFileChange(sourceName, files)
    }
  }

  const fileUploadSources = dataSources.filter(ds => ds.source_type === 'FILE_UPLOAD')
  
  const requiredSources = fileUploadSources.filter(ds => ds.is_required)
  const allRequiredUploaded = requiredSources.every(ds => uploadedFiles[ds.source_name]?.length > 0)

  // Calculate total files info
  const totalFilesCount = Object.values(uploadedFiles).reduce((sum, files) => sum + files.length, 0)
  const totalFilesSize = Object.values(uploadedFiles).flat().reduce((sum, f) => sum + f.size, 0)
  const hasZipFiles = Object.values(uploadedFiles).flat().some(f => f.name.toLowerCase().endsWith('.zip'))

  const handleUploadFiles = async (forceReplace = false) => {
    if (!selectedConfig) return
    
    // Validate dates before uploading
    if (!periodFrom || !periodTo) {
      setError('Vui lòng chọn kỳ đối soát (Từ ngày - Đến ngày) trước khi upload.')
      return
    }
    
    // Validate files
    const allFiles = []
    const allSourceNames = []
    for (const [sourceName, files] of Object.entries(uploadedFiles)) {
      for (const file of files) {
        allFiles.push(file)
        allSourceNames.push(sourceName)
      }
    }
    
    if (allFiles.length === 0) {
      setError('Vui lòng chọn ít nhất 1 file để upload')
      return
    }
    
    // Check for duplicate batches BEFORE uploading (avoid wasting upload time)
    if (!forceReplace) {
      try {
        const checkResp = await reconciliationApiV2.checkDuplicate({
          config_id: selectedConfig.id,
          period_from: periodFrom,
          period_to: periodTo,
        })
        const checkData = checkResp.data
        
        if (checkData.has_duplicate) {
          if (checkData.approved_conflict) {
            const approvedBatch = checkData.duplicates.find(d => d.status === 'APPROVED')
            setError(
              `Không thể tạo batch mới! Đã tồn tại batch được phê duyệt (${approvedBatch?.batch_id}) ` +
              `cho khoảng thời gian ${approvedBatch?.period_from} đến ${approvedBatch?.period_to}.`
            )
            return
          }
          // Unapproved duplicates → show warning BEFORE upload
          setDuplicateWarning({
            duplicates: checkData.duplicates,
            message: `Đã tồn tại ${checkData.duplicates.length} batch chưa duyệt với khoảng thời gian trùng lặp.`
          })
          return
        }
      } catch (err) {
        console.warn('Duplicate check failed, proceeding with upload:', err)
      }
    }
    
    // Clear warnings
    setDuplicateWarning(null)
    
    try {
      setUploading(true)
      setUploadProgress(0)
      setError(null)
      
      const response = await reconciliationApiV2.uploadFiles(
        selectedConfig.id,
        allFiles,
        allSourceNames,
        (progress) => setUploadProgress(progress)
      )
      
      setBatchFolder(response.data.batch_folder)
      setUploadProgress(100)
      setStep(3)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        setError(detail.map(e => e.msg || JSON.stringify(e)).join('; '))
      } else {
        setError(typeof detail === 'string' ? detail : 'Không thể upload files')
      }
    } finally {
      setUploading(false)
    }
  }

  const handleRunReconciliation = async (forceReplace = false) => {
    if (!selectedConfig || !batchFolder) return
    
    // Validate dates
    if (!periodFrom || !periodTo) {
      setError('Vui lòng chọn kỳ đối soát (Từ ngày - Đến ngày) ở bước Upload files trước khi chạy.')
      return
    }
    
    // Duplicate check was already done before upload (step 2).
    // Just run with the forceReplace flag passed through.
    
    try {
      setRunning(true)
      setError(null)
      setErrorLogs([])
      
      const response = await reconciliationApiV2.run(
        {
          config_id: selectedConfig.id,
          period_from: periodFrom,
          period_to: periodTo,
          cycle_params: {
            date_from: periodFrom,
            date_to: periodTo
          }
        },
        batchFolder,
        forceReplace
      )
      
      // Backend now returns immediately with {batch_id, status: "PROCESSING"}
      // Redirect to BatchDetailPage where polling UI shows live progress
      const batchId = response.data.batch_id
      if (batchId) {
        navigate(`/v2/batches/${batchId}`)
      } else {
        setResult(response.data)
      }
    } catch (err) {
      // Handle error - detail can be string, object with step_logs, or array of validation errors
      const detail = err.response?.data?.detail
      if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
        if (detail.type === 'duplicate_warning') {
          // Fallback: backend returned duplicate warning (shouldn't happen if frontend checks first)
          setDuplicateWarning({
            duplicates: detail.duplicates || [],
            message: detail.message || 'Tồn tại batch trùng lặp'
          })
        } else {
          // Structured error with step_logs from backend
          setError(detail.message || 'Lỗi khi chạy đối soát')
          setErrorLogs(detail.step_logs || [])
        }
      } else if (Array.isArray(detail)) {
        // FastAPI 422 validation errors
        const messages = detail.map(e => e.msg || JSON.stringify(e)).join('; ')
        setError(`Lỗi dữ liệu: ${messages}`)
      } else if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Lỗi khi chạy đối soát')
      }
    } finally {
      setRunning(false)
    }
  }

  const handleConfirmReplace = () => {
    setDuplicateWarning(null)
    setNeedForceReplace(true)
    // User confirmed → proceed with upload (skip duplicate check) then auto-run
    handleUploadFiles(true)
  }

  const handleCancelReplace = () => {
    setDuplicateWarning(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Đối soát V2</h1>
        <p className="text-sm text-gray-500 mt-1">
          Hệ thống đối soát động với workflow linh hoạt
        </p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-center mb-8">
        {[
          { num: 1, label: 'Chọn cấu hình' },
          { num: 2, label: 'Upload files' },
          { num: 3, label: 'Chạy đối soát' }
        ].map((s, idx) => (
          <div key={s.num} className="flex items-center">
            <div className={`flex items-center justify-center w-10 h-10 rounded-full font-bold
              ${step >= s.num ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-500'}`}>
              {step > s.num ? <CheckCircleIcon className="h-6 w-6" /> : s.num}
            </div>
            <span className={`ml-2 ${step >= s.num ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>
              {s.label}
            </span>
            {idx < 2 && <div className="w-16 h-1 mx-4 bg-gray-200" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center text-red-600">
            <ExclamationTriangleIcon className="h-5 w-5 mr-2 flex-shrink-0" />
            <span className="font-medium">{error}</span>
          </div>
          
          {/* Step-by-step execution logs on error */}
          {errorLogs.length > 0 && (
            <div className="mt-3 border-t border-red-200 pt-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Chi tiết quá trình thực thi:</h4>
              <div className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs font-mono max-h-64 overflow-y-auto space-y-1">
                {errorLogs.map((log, idx) => {
                  const statusIcon = log.status === 'ok' ? '✅' 
                    : log.status === 'error' ? '❌' 
                    : log.status === 'warning' ? '⚠️' 
                    : '▶️'
                  const statusColor = log.status === 'ok' ? 'text-green-400' 
                    : log.status === 'error' ? 'text-red-400'
                    : log.status === 'warning' ? 'text-yellow-400'
                    : 'text-blue-400'
                  return (
                    <div key={idx} className={`flex items-start gap-2 ${log.status === 'error' ? 'bg-red-900/30 -mx-1 px-1 rounded' : ''}`}>
                      <span>{statusIcon}</span>
                      <span className="text-gray-500 whitespace-nowrap">{log.time?.split('T')[1]?.substring(0, 8) || ''}</span>
                      <span className={`font-semibold ${statusColor}`}>[{log.step}]</span>
                      <span className={log.status === 'error' ? 'text-red-300' : ''}>{log.message}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Step 1: Select Config */}
      {step === 1 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium mb-4">Chọn cấu hình đối soát</h2>
          
          {loading ? (
            <div className="flex justify-center py-8">
              <ArrowPathIcon className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {configs.map((config) => (
                <button
                  key={config.id}
                  onClick={() => {
                    setSelectedConfig(config)
                    setStep(2) // Tự động chuyển sang step 2
                  }}
                  className={`p-4 border-2 rounded-lg text-left transition-all
                    ${selectedConfig?.id === config.id 
                      ? 'border-primary-500 bg-primary-50' 
                      : 'border-gray-200 hover:border-primary-300'}`}
                >
                  <div className="font-bold text-lg">
                    {config.partner_code}/{config.service_code}
                  </div>
                  <div className="text-sm text-gray-600">{config.partner_name}</div>
                  <div className="text-xs text-gray-400 mt-2">
                    {config.data_sources?.length || 0} nguồn · 
                    {config.workflow_steps?.length || 0} bước
                  </div>
                </button>
              ))}
            </div>
          )}

          {selectedConfig && (
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setStep(2)}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
              >
                Tiếp tục →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 2: Upload Files */}
      {step === 2 && selectedConfig && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-medium">
              Upload files cho {selectedConfig.partner_code}/{selectedConfig.service_code}
            </h2>
            <button
              onClick={() => setStep(1)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              ← Chọn lại cấu hình
            </button>
          </div>

          {/* Period Selection */}
          <div className="grid grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Từ ngày
              </label>
              <input
                type="date"
                value={periodFrom}
                onChange={(e) => setPeriodFrom(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Đến ngày
              </label>
              <input
                type="date"
                value={periodTo}
                onChange={(e) => setPeriodTo(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
          </div>

          {/* File Upload Areas */}
          <div className="space-y-4">
            {fileUploadSources.map((ds) => {
              const files = uploadedFiles[ds.source_name] || []
              const hasFiles = files.length > 0
              const isDraggedOver = dragOver[ds.source_name]
              const sourceHasZip = files.some(f => f.name.toLowerCase().endsWith('.zip'))
              const sourceMultiFile = files.length > 1 || sourceHasZip
              
              return (
              <div 
                key={ds.source_name}
                className={`border-2 border-dashed rounded-lg p-4 transition-all ${
                  isDraggedOver
                    ? 'border-primary-500 bg-primary-50 scale-[1.01]'
                    : hasFiles 
                      ? 'border-green-400 bg-green-50' 
                      : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragOver={(e) => handleDragOver(e, ds.source_name)}
                onDragLeave={(e) => handleDragLeave(e, ds.source_name)}
                onDrop={(e) => handleDrop(e, ds.source_name)}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center">
                    <CloudArrowUpIcon className={`h-8 w-8 mr-3 ${
                      isDraggedOver ? 'text-primary-500 animate-bounce' :
                      hasFiles ? 'text-green-500' : 'text-gray-400'
                    }`} />
                    <div>
                      <div className="font-medium">
                        {ds.source_name}: {ds.display_name}
                        {ds.is_required && (
                          <span className="ml-2 text-xs text-red-500 font-normal">* Bắt buộc</span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        Kéo thả hoặc click để chọn file · Excel (.xlsx, .xls, .xlsb), CSV, ZIP · Có thể chọn nhiều file
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasFiles && (
                      <button
                        type="button"
                        onClick={() => handleClearSource(ds.source_name)}
                        className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                      >
                        Xóa tất cả
                      </button>
                    )}
                    <label className="cursor-pointer px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm transition-colors">
                      {hasFiles ? '+ Thêm file' : 'Chọn file'}
                      <input
                        type="file"
                        accept={ACCEPT_STRING}
                        multiple
                        className="hidden"
                        onChange={(e) => {
                          handleFileChange(ds.source_name, e.target.files)
                          e.target.value = '' // Reset to allow re-selecting same file
                        }}
                      />
                    </label>
                  </div>
                </div>
                
                {/* Drop zone overlay when dragging */}
                {isDraggedOver && !hasFiles && (
                  <div className="text-center py-4 text-primary-600">
                    <CloudArrowUpIcon className="h-10 w-10 mx-auto mb-2" />
                    <p className="text-sm font-medium">Thả file tại đây</p>
                  </div>
                )}
                
                {/* List of uploaded files */}
                {hasFiles && (
                  <div className="mt-3 space-y-1">
                    {files.map((file, idx) => {
                      const FileIcon = getFileIcon(file.name)
                      const fileType = getFileTypeLabel(file.name)
                      const isZip = file.name.toLowerCase().endsWith('.zip')
                      
                      return (
                        <div key={idx} className={`flex items-center justify-between px-3 py-2 rounded border ${
                          isZip ? 'bg-amber-50 border-amber-200' : 'bg-white border-gray-200'
                        }`}>
                          <div className="flex items-center min-w-0 flex-1">
                            <FileIcon className={`h-4 w-4 mr-2 flex-shrink-0 ${
                              isZip ? 'text-amber-600' : 'text-green-600'
                            }`} />
                            <span className="text-sm text-gray-700 truncate">{file.name}</span>
                            <span className={`text-xs ml-2 px-1.5 py-0.5 rounded flex-shrink-0 ${
                              isZip 
                                ? 'bg-amber-100 text-amber-700' 
                                : 'bg-gray-100 text-gray-500'
                            }`}>
                              {fileType}
                            </span>
                            <span className="text-xs text-gray-400 ml-2 flex-shrink-0">
                              {formatFileSize(file.size)}
                            </span>
                            {isZip && (
                              <span className="text-xs text-amber-600 ml-2 flex-shrink-0">
                                (tự giải nén khi xử lý)
                              </span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveFile(ds.source_name, idx)}
                            className="text-red-400 hover:text-red-600 p-1 ml-2 flex-shrink-0"
                            title="Xóa file"
                          >
                            <XCircleIcon className="h-5 w-5" />
                          </button>
                        </div>
                      )
                    })}
                    
                    {/* Source summary */}
                    <div className="flex items-center justify-between text-xs text-gray-500 mt-2 pt-2 border-t border-gray-100">
                      <span>
                        {files.length} file(s) · {formatFileSize(files.reduce((s, f) => s + f.size, 0))}
                      </span>
                      {sourceMultiFile && (
                        <span className="text-primary-600 font-medium">
                          ↳ Dữ liệu sẽ được ghép tự động khi chạy đối soát
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
              )
            })}
          </div>

          {/* Upload summary & info */}
          {totalFilesCount > 0 && (
            <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start">
                <div className="text-blue-600 text-sm">
                  <span className="font-medium">Tổng cộng:</span> {totalFilesCount} file(s) · {formatFileSize(totalFilesSize)}
                  {hasZipFiles && (
                    <span className="ml-2 text-amber-600">
                      · Có file ZIP (sẽ tự giải nén)
                    </span>
                  )}
                </div>
              </div>
              <p className="text-xs text-blue-500 mt-1">
                Hệ thống sẽ tự động đọc và ghép dữ liệu từ tất cả các file (bao gồm nội dung trong ZIP) cho mỗi nguồn trước khi thực hiện so khớp.
              </p>
            </div>
          )}

          <div className="mt-6 flex flex-col items-end gap-4">
            {/* Duplicate Warning Dialog - shown BEFORE upload */}
            {duplicateWarning && (
              <div className="w-full">
                <div className="bg-amber-50 border-2 border-amber-400 rounded-lg p-5 text-left">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-2xl">⚠️</span>
                    <h3 className="font-bold text-amber-800 text-base">Phát hiện batch trùng lặp</h3>
                  </div>
                  <p className="text-sm text-amber-700 mb-3">{duplicateWarning.message}</p>
                  <div className="bg-white rounded border border-amber-200 mb-4 overflow-hidden">
                    <table className="w-full text-xs">
                      <thead className="bg-amber-100">
                        <tr>
                          <th className="px-3 py-1.5 text-left font-semibold text-amber-800">Batch ID</th>
                          <th className="px-3 py-1.5 text-left font-semibold text-amber-800">Trạng thái</th>
                          <th className="px-3 py-1.5 text-left font-semibold text-amber-800">Kỳ đối soát</th>
                          <th className="px-3 py-1.5 text-left font-semibold text-amber-800">Ngày tạo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {duplicateWarning.duplicates.map((d, i) => (
                          <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-amber-50'}>
                            <td className="px-3 py-1.5 font-mono text-xs">{d.batch_id}</td>
                            <td className="px-3 py-1.5">
                              <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
                                d.status === 'COMPLETED' ? 'bg-green-100 text-green-700' :
                                d.status === 'FAILED' ? 'bg-red-100 text-red-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>{d.status}</span>
                            </td>
                            <td className="px-3 py-1.5">{d.period_from} → {d.period_to}</td>
                            <td className="px-3 py-1.5">{d.created_at ? new Date(d.created_at).toLocaleString('vi-VN') : '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="text-sm text-amber-800 font-medium mb-3">
                    Nếu tiếp tục, các batch cũ trùng lặp sẽ bị <span className="text-red-600 font-bold">XÓA TOÀN BỘ</span> (dữ liệu + file kết quả) và tạo batch mới thay thế.
                  </p>
                  <div className="flex gap-3 justify-end">
                    <button
                      onClick={handleCancelReplace}
                      className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium"
                    >
                      Hủy bỏ
                    </button>
                    <button
                      onClick={handleConfirmReplace}
                      disabled={uploading}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm font-medium"
                    >
                      {uploading ? 'Đang xử lý...' : 'Xóa batch cũ & Upload tiếp tục'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {!duplicateWarning && (
              <button
                onClick={() => handleUploadFiles(false)}
                disabled={!allRequiredUploaded || uploading}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
              >
                {uploading ? (
                  <>
                    <ArrowPathIcon className="h-5 w-5 animate-spin mr-2" />
                    Đang upload... {uploadProgress > 0 && `${uploadProgress}%`}
                  </>
                ) : (
                  <>
                    <CloudArrowUpIcon className="h-5 w-5 mr-2" />
                    Upload {totalFilesCount > 0 ? `${totalFilesCount} file(s)` : ''} & Tiếp tục →
                  </>
                )}
              </button>
            )}
          </div>

          {/* Upload progress bar */}
          {uploading && uploadProgress > 0 && (
            <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Step 3: Run Reconciliation */}
      {step === 3 && selectedConfig && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium mb-4">Chạy đối soát</h2>

          {!result ? (
            <div className="text-center py-8">
              <p className="text-gray-600 mb-4">
                Files đã được upload thành công. Nhấn nút bên dưới để bắt đầu đối soát.
              </p>

              <button
                onClick={() => handleRunReconciliation(needForceReplace)}
                disabled={running}
                className="px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center mx-auto"
              >
                {running ? (
                  <>
                    <ArrowPathIcon className="h-5 w-5 animate-spin mr-2" />
                    Đang xử lý...
                  </>
                ) : (
                  <>
                    <PlayIcon className="h-5 w-5 mr-2" />
                    Chạy đối soát
                  </>
                )}
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Success Message */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center">
                <CheckCircleIcon className="h-8 w-8 text-green-500 mr-3" />
                <div>
                  <div className="font-medium text-green-800">Đối soát hoàn thành!</div>
                  <div className="text-sm text-green-600">
                    Batch ID: {result.batch_id} · Thời gian: {result.total_time_seconds?.toFixed(2)}s
                  </div>
                </div>
              </div>

              {/* Output Results */}
              <div>
                <h3 className="font-medium mb-3">Kết quả Output:</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {result.outputs?.map((output) => (
                    <div key={output.output_name} className="border rounded-lg p-4">
                      <div className="font-bold">{output.output_name}</div>
                      <div className="text-sm text-gray-600">{output.display_name}</div>
                      <div className="mt-2 text-2xl font-bold text-primary-600">
                        {output.row_count} dòng
                      </div>
                      {output.status_counts && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(output.status_counts).map(([status, count]) => (
                            <span key={status} className="text-xs bg-gray-100 px-2 py-1 rounded">
                              {status}: {count}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-4 justify-center">
                <button
                  onClick={() => navigate(`/batches/${result.batch_id}`)}
                  className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                >
                  Xem chi tiết
                </button>
                <button
                  onClick={() => {
                    setStep(1)
                    setSelectedConfig(null)
                    setUploadedFiles({})
                    setBatchFolder(null)
                    setResult(null)
                    setErrorLogs([])
                  }}
                  className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Đối soát mới
                </button>
              </div>

              {/* Execution Step Logs (collapsible) */}
              {result.step_logs && result.step_logs.length > 0 && (
                <details className="border rounded-lg">
                  <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-gray-700 hover:bg-gray-50">
                    📋 Chi tiết quá trình thực thi ({result.step_logs.length} bước)
                  </summary>
                  <div className="bg-gray-900 text-gray-100 rounded-b-lg p-3 text-xs font-mono max-h-64 overflow-y-auto space-y-1">
                    {result.step_logs.map((log, idx) => {
                      const statusIcon = log.status === 'ok' ? '✅' 
                        : log.status === 'error' ? '❌' 
                        : log.status === 'warning' ? '⚠️' 
                        : '▶️'
                      const statusColor = log.status === 'ok' ? 'text-green-400' 
                        : log.status === 'error' ? 'text-red-400'
                        : log.status === 'warning' ? 'text-yellow-400'
                        : 'text-blue-400'
                      return (
                        <div key={idx} className="flex items-start gap-2">
                          <span>{statusIcon}</span>
                          <span className="text-gray-500 whitespace-nowrap">{log.time?.split('T')[1]?.substring(0, 8) || ''}</span>
                          <span className={`font-semibold ${statusColor}`}>[{log.step}]</span>
                          <span>{log.message}</span>
                        </div>
                      )
                    })}
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

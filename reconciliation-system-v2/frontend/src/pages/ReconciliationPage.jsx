import { useState, useCallback, useEffect, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { partnersApi, reconciliationApi } from '../services/api'

export default function ReconciliationPage() {
  const navigate = useNavigate()
  const [partnerCode, setPartnerCode] = useState('')
  const [serviceCode, setServiceCode] = useState('')
  const [dateFrom, setDateFrom] = useState(new Date().toISOString().split('T')[0])
  const [dateTo, setDateTo] = useState(new Date().toISOString().split('T')[0])
  const [filesB1, setFilesB1] = useState([])
  const [filesB2, setFilesB2] = useState([])
  const [filesB3, setFilesB3] = useState([])
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [duplicateBatch, setDuplicateBatch] = useState(null)
  const [pendingFormData, setPendingFormData] = useState(null)
  
  // Progress tracking
  const [showProgressModal, setShowProgressModal] = useState(false)
  const [processingBatchId, setProcessingBatchId] = useState(null)
  const [progressSteps, setProgressSteps] = useState([])
  const [progressStatus, setProgressStatus] = useState('PROCESSING')
  const [progressError, setProgressError] = useState(null)
  const pollingRef = useRef(null)
  
  // Fetch partners
  const { data: partnersData } = useQuery({
    queryKey: ['partners'],
    queryFn: () => partnersApi.getPartners(),
  })
  
  // Fetch services when partner selected
  const { data: servicesData } = useQuery({
    queryKey: ['services', partnerCode],
    queryFn: () => partnersApi.getServices(partnerCode),
    enabled: !!partnerCode,
  })
  
  const partners = partnersData?.data || []
  const services = servicesData?.data || []
  
  // Poll for progress updates
  const pollProgress = useCallback(async (batchId) => {
    try {
      const response = await reconciliationApi.getBatch(batchId)
      const batch = response.data
      
      setProgressSteps(batch.step_logs || [])
      setProgressStatus(batch.status)
      
      if (batch.status === 'ERROR') {
        setProgressError(batch.error_message)
        clearInterval(pollingRef.current)
      } else if (batch.status === 'COMPLETED' || batch.status === 'APPROVED') {
        clearInterval(pollingRef.current)
        // Auto navigate after 1.5s
        setTimeout(() => {
          setShowProgressModal(false)
          navigate(`/batches/${batchId}`)
        }, 1500)
      }
    } catch (err) {
      console.error('Poll error:', err)
    }
  }, [navigate])
  
  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])
  
  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (formData) => reconciliationApi.upload(formData),
    onMutate: () => {
      // Show progress modal immediately when starting
      setShowProgressModal(true)
      setProgressSteps([
        { step: 'UPLOAD', status: 'processing', message: 'Đang upload file...', time: new Date().toISOString() }
      ])
      setProgressStatus('PROCESSING')
      setProgressError(null)
      setProcessingBatchId(null)
    },
    onSuccess: (response) => {
      const batchId = response.data.batch_id
      setProcessingBatchId(batchId)
      setProgressStatus('COMPLETED')
      setProgressSteps(prev => [
        ...prev.filter(s => s.step !== 'UPLOAD'),
        { step: 'UPLOAD', status: 'ok', message: 'Upload thành công', time: new Date().toISOString() },
        { step: 'COMPLETE', status: 'ok', message: `Đối soát hoàn tất - Batch: ${batchId}`, time: new Date().toISOString() }
      ])
      
      // Auto navigate after 2s
      setTimeout(() => {
        setShowProgressModal(false)
        navigate(`/batches/${batchId}`)
      }, 2000)
    },
    onError: (error) => {
      const errorDetail = error.response?.data?.detail || error.response?.data?.error_message || 'Có lỗi xảy ra'
      setProgressStatus('ERROR')
      setProgressError(errorDetail)
      setProgressSteps(prev => [
        ...prev.filter(s => s.status !== 'processing'),
        { step: 'ERROR', status: 'error', message: errorDetail, time: new Date().toISOString() }
      ])
    },
  })
  
  // Delete batch mutation
  const deleteMutation = useMutation({
    mutationFn: (batchId) => reconciliationApi.deleteBatch(batchId),
  })
  
  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (filesB1.length === 0) {
      toast.error('Vui lòng chọn ít nhất 1 file B1 (sao kê ngân hàng)')
      return
    }
    
    const formData = new FormData()
    formData.append('partner_code', partnerCode)
    formData.append('service_code', serviceCode)
    formData.append('date_from', dateFrom)
    formData.append('date_to', dateTo)
    
    // Append multiple files for each type
    filesB1.forEach((file) => formData.append('files_b1', file))
    filesB2.forEach((file) => formData.append('files_b2', file))
    filesB3.forEach((file) => formData.append('files_b3', file))
    
    // Check for duplicate batch
    try {
      const checkResult = await reconciliationApi.checkDuplicate(partnerCode, serviceCode, dateFrom, dateTo)
      if (checkResult.data?.exists) {
        // Found duplicate batch, show confirmation dialog
        setDuplicateBatch(checkResult.data.batch)
        setPendingFormData(formData)
        setShowConfirmDialog(true)
        return
      }
    } catch (err) {
      // If check fails, proceed anyway
      console.warn('Check duplicate failed:', err)
    }
    
    // No duplicate, proceed with upload
    uploadMutation.mutate(formData)
  }
  
  const handleConfirmReplace = async () => {
    setShowConfirmDialog(false)
    
    // Delete old batch first
    if (duplicateBatch?.batch_id) {
      try {
        await deleteMutation.mutateAsync(duplicateBatch.batch_id)
        toast.success('Đã xóa batch cũ')
      } catch (err) {
        toast.error('Không thể xóa batch cũ: ' + (err.response?.data?.detail || err.message))
        return
      }
    }
    
    // Then upload new batch
    if (pendingFormData) {
      uploadMutation.mutate(pendingFormData)
    }
    
    setDuplicateBatch(null)
    setPendingFormData(null)
  }
  
  const handleCancelReplace = () => {
    setShowConfirmDialog(false)
    setDuplicateBatch(null)
    setPendingFormData(null)
  }
  
  // Dropzone component for multiple files
  const MultiFileDropzone = ({ label, files, setFiles, required }) => {
    const onDrop = useCallback((acceptedFiles) => {
      setFiles(prev => [...prev, ...acceptedFiles])
    }, [setFiles])
    
    const removeFile = (index) => {
      setFiles(prev => prev.filter((_, i) => i !== index))
    }
    
    const { getRootProps, getInputProps, isDragActive } = useDropzone({
      onDrop,
      accept: {
        'application/vnd.ms-excel': ['.xls'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
        'application/vnd.ms-excel.sheet.binary.macroEnabled.12': ['.xlsb'],
        'text/csv': ['.csv'],
        'application/zip': ['.zip'],
        'application/x-rar-compressed': ['.rar'],
        'application/vnd.rar': ['.rar'],
      },
      multiple: true,
    })
    
    return (
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          {label} {required && <span className="text-red-500">*</span>}
          {files.length > 0 && <span className="text-gray-400 ml-2">({files.length} file)</span>}
        </label>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition ${
            isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <input {...getInputProps()} />
          <p className="text-gray-500">Kéo thả file hoặc click để chọn (có thể chọn nhiều file)</p>
          <p className="text-xs text-gray-400 mt-1">.xlsx, .xls, .xlsb, .csv, .zip, .rar</p>
        </div>
        
        {/* List of selected files */}
        {files.length > 0 && (
          <div className="mt-2 space-y-1">
            {files.map((file, index) => (
              <div key={index} className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-green-600">✓</span>
                  <span className="text-sm text-gray-700">{file.name}</span>
                  <span className="text-xs text-gray-400">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }
  
  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-xl shadow-sm">
        <div className="p-6 border-b">
          <h1 className="text-xl font-semibold text-gray-800">Tạo đối soát mới</h1>
          <p className="text-gray-500 text-sm mt-1">
            Upload file sao kê và chạy đối soát với dữ liệu VNPT Money
          </p>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {/* Partner & Service */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Đối tác <span className="text-red-500">*</span>
              </label>
              <select
                value={partnerCode}
                onChange={(e) => { setPartnerCode(e.target.value); setServiceCode(''); }}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                required
              >
                <option value="">Chọn đối tác</option>
                {partners.map((p) => (
                  <option key={p.partner_code} value={p.partner_code}>
                    {p.partner_name}
                  </option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Dịch vụ <span className="text-red-500">*</span>
              </label>
              <select
                value={serviceCode}
                onChange={(e) => setServiceCode(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                required
                disabled={!partnerCode}
              >
                <option value="">Chọn dịch vụ</option>
                {services.map((s) => (
                  <option key={s.service_code} value={s.service_code}>
                    {s.service_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          
          {/* Date Range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kỳ đối soát <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Từ ngày</label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Đến ngày</label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  min={dateFrom}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                  required
                />
              </div>
            </div>
          </div>
          
          {/* File uploads - support multiple files */}
          <div className="space-y-4">
            <MultiFileDropzone
              label="File B1 - Sao kê ngân hàng"
              files={filesB1}
              setFiles={setFilesB1}
              required
            />
            
            <MultiFileDropzone
              label="File B2 - Hoàn tiền (nếu có)"
              files={filesB2}
              setFiles={setFilesB2}
            />
            
            <MultiFileDropzone
              label="File B3 - Chi tiết đối tác (nếu có)"
              files={filesB3}
              setFiles={setFilesB3}
            />
          </div>
          
          {/* Submit */}
          <div className="pt-4">
            <button
              type="submit"
              disabled={uploadMutation.isPending || deleteMutation.isPending}
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploadMutation.isPending ? 'Đang xử lý...' : 'Chạy đối soát'}
            </button>
          </div>
        </form>
      </div>
      
      {/* Progress Modal */}
      {showProgressModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {progressStatus === 'PROCESSING' && (
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                )}
                {progressStatus === 'COMPLETED' && <span className="text-2xl">✅</span>}
                {progressStatus === 'ERROR' && <span className="text-2xl">❌</span>}
                <h3 className="text-lg font-semibold text-gray-800">
                  {progressStatus === 'PROCESSING' && 'Đang xử lý đối soát...'}
                  {progressStatus === 'COMPLETED' && 'Đối soát hoàn thành!'}
                  {progressStatus === 'ERROR' && 'Đối soát thất bại'}
                </h3>
              </div>
              {(progressStatus === 'COMPLETED' || progressStatus === 'ERROR') && (
                <button
                  onClick={() => {
                    setShowProgressModal(false)
                    if (progressStatus === 'COMPLETED') {
                      navigate(`/batches/${processingBatchId}`)
                    }
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              )}
            </div>
            
            {/* Progress steps */}
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {progressSteps.length === 0 && progressStatus === 'PROCESSING' && (
                <div className="text-gray-500 text-sm py-2">Đang khởi tạo...</div>
              )}
              {progressSteps.map((step, idx) => (
                <div 
                  key={idx} 
                  className={`flex items-start gap-3 p-2 rounded ${
                    step.status === 'ok' ? 'bg-green-50' : 
                    step.status === 'error' ? 'bg-red-50' : 
                    step.status === 'processing' ? 'bg-blue-50' : 'bg-gray-50'
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {step.status === 'ok' && <span className="text-green-600">✓</span>}
                    {step.status === 'error' && <span className="text-red-600">✗</span>}
                    {step.status === 'processing' && (
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                    )}
                    {!['ok', 'error', 'processing'].includes(step.status) && <span className="text-gray-400">○</span>}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium ${
                      step.status === 'ok' ? 'text-green-700' : 
                      step.status === 'error' ? 'text-red-700' : 
                      step.status === 'processing' ? 'text-blue-700' : 'text-gray-600'
                    }`}>
                      {step.step}
                    </p>
                    <p className="text-xs text-gray-500 truncate">{step.message}</p>
                    {step.time && (
                      <p className="text-xs text-gray-400">{new Date(step.time).toLocaleTimeString('vi-VN')}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
            
            {/* Error message */}
            {progressError && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-700 text-sm font-medium mb-1">Chi tiết lỗi:</p>
                <pre className="text-red-600 text-xs whitespace-pre-wrap break-words">{progressError}</pre>
              </div>
            )}
            
            {/* Actions */}
            <div className="mt-4 flex gap-3">
              {progressStatus === 'COMPLETED' && (
                <button
                  onClick={() => {
                    setShowProgressModal(false)
                    navigate(`/batches/${processingBatchId}`)
                  }}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                >
                  Xem chi tiết batch
                </button>
              )}
              {progressStatus === 'ERROR' && (
                <>
                  <button
                    onClick={() => setShowProgressModal(false)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                  >
                    Đóng
                  </button>
                  {processingBatchId && (
                    <button
                      onClick={() => {
                        setShowProgressModal(false)
                        navigate(`/batches/${processingBatchId}`)
                      }}
                      className="flex-1 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
                    >
                      Xem batch lỗi
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Confirm Replace Dialog */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-3xl">⚠️</span>
              <h3 className="text-lg font-semibold text-gray-800">Batch đã tồn tại</h3>
            </div>
            
            <p className="text-gray-600 mb-4">
              Đã tồn tại batch có cùng khoảng thời gian đối soát:
            </p>
            
            {duplicateBatch && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4">
                <p className="text-sm"><strong>Batch ID:</strong> {duplicateBatch.batch_id}</p>
                <p className="text-sm"><strong>Trạng thái:</strong> {duplicateBatch.status}</p>
                <p className="text-sm"><strong>Kỳ đối soát:</strong> {duplicateBatch.period_from} - {duplicateBatch.period_to}</p>
                <p className="text-sm"><strong>Ngày tạo:</strong> {new Date(duplicateBatch.created_at).toLocaleString('vi-VN')}</p>
              </div>
            )}
            
            <p className="text-gray-600 mb-6">
              Bạn có muốn tạo lại? <strong className="text-red-600">Batch cũ sẽ bị xóa và thay thế.</strong>
            </p>
            
            <div className="flex gap-3">
              <button
                onClick={handleCancelReplace}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
              >
                Hủy
              </button>
              <button
                onClick={handleConfirmReplace}
                disabled={deleteMutation.isPending}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Đang xóa...' : 'Xóa và tạo mới'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

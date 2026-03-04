/**
 * MockDataPage - Quản lý dữ liệu mock B4 cho testing
 */

import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { mockDataApi } from '../../services/api'

export default function MockDataPage() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef(null)
  
  const [uploadModal, setUploadModal] = useState(false)
  const [previewModal, setPreviewModal] = useState(null)
  const [uploadForm, setUploadForm] = useState({
    partnerCode: '',
    serviceCode: '',
    file: null
  })
  
  // Fetch mock files list
  const { data: mockFilesData, isLoading } = useQuery({
    queryKey: ['mock-files'],
    queryFn: () => mockDataApi.list(),
  })
  
  const mockFiles = mockFilesData?.data?.files || []
  
  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: ({ partnerCode, serviceCode, file }) => 
      mockDataApi.upload(partnerCode, serviceCode, file),
    onSuccess: (res) => {
      toast.success(`Đã upload ${res.data.filename} (${res.data.row_count} dòng)`)
      queryClient.invalidateQueries(['mock-files'])
      setUploadModal(false)
      setUploadForm({ partnerCode: '', serviceCode: '', file: null })
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Lỗi upload file')
    }
  })
  
  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (filename) => mockDataApi.delete(filename),
    onSuccess: () => {
      toast.success('Đã xóa file')
      queryClient.invalidateQueries(['mock-files'])
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || 'Lỗi xóa file')
    }
  })
  
  // Preview query
  const { data: previewData, isLoading: previewLoading } = useQuery({
    queryKey: ['mock-preview', previewModal],
    queryFn: () => mockDataApi.preview(previewModal, 50),
    enabled: !!previewModal
  })
  
  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setUploadForm({ ...uploadForm, file })
      
      // Auto-extract partner/service from filename if possible
      const match = file.name.match(/^([A-Z]+)_([A-Z]+)_/)
      if (match) {
        setUploadForm(prev => ({
          ...prev,
          file,
          partnerCode: match[1],
          serviceCode: match[2]
        }))
      }
    }
  }
  
  const handleUpload = () => {
    if (!uploadForm.partnerCode || !uploadForm.serviceCode || !uploadForm.file) {
      toast.error('Vui lòng điền đầy đủ thông tin')
      return
    }
    uploadMutation.mutate(uploadForm)
  }
  
  const handleDelete = (filename) => {
    if (window.confirm(`Xóa file mock "${filename}"?`)) {
      deleteMutation.mutate(filename)
    }
  }
  
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Mock Data B4</h1>
          <p className="text-gray-500">
            Quản lý dữ liệu mock để test đối soát (thay thế query database)
          </p>
        </div>
        <button
          onClick={() => setUploadModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
        >
          <span>📤</span> Upload Mock File
        </button>
      </div>
      
      {/* Info box */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h3 className="font-medium text-blue-800 mb-2">💡 Hướng dẫn</h3>
        <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
          <li>File mock sẽ được đặt tên theo format: <code className="bg-blue-100 px-1 rounded">PARTNER_SERVICE_b4_mock.csv</code></li>
          <li>Khi chạy đối soát với <code className="bg-blue-100 px-1 rounded">mock_mode = true</code>, hệ thống sẽ đọc từ file này thay vì query database</li>
          <li>Đảm bảo file CSV có đầy đủ các cột cần thiết (transaction_ref, total_amount, ...)</li>
        </ul>
      </div>
      
      {/* Files table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Đang tải...</div>
        ) : mockFiles.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-gray-500 mb-4">Chưa có file mock nào</p>
            <button
              onClick={() => setUploadModal(true)}
              className="text-blue-600 hover:underline"
            >
              + Upload file đầu tiên
            </button>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">File</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Partner</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Service</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {mockFiles.map((file) => (
                <tr key={file.filename} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <p className="font-mono text-sm text-gray-800">{file.filename}</p>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                      {file.partner_code}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">
                      {file.service_code}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {formatFileSize(file.size)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => setPreviewModal(file.filename)}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        Xem
                      </button>
                      <a
                        href={mockDataApi.download(file.filename)}
                        className="text-green-600 hover:underline text-sm"
                        download
                      >
                        Tải
                      </a>
                      <button
                        onClick={() => handleDelete(file.filename)}
                        className="text-red-600 hover:underline text-sm"
                      >
                        Xóa
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      
      {/* Upload Modal */}
      {uploadModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Upload Mock File</h3>
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Partner Code
                  </label>
                  <input
                    type="text"
                    value={uploadForm.partnerCode}
                    onChange={(e) => setUploadForm({ ...uploadForm, partnerCode: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VD: SACOMBANK"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Service Code
                  </label>
                  <input
                    type="text"
                    value={uploadForm.serviceCode}
                    onChange={(e) => setUploadForm({ ...uploadForm, serviceCode: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VD: TOPUP"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  File CSV
                </label>
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition"
                >
                  {uploadForm.file ? (
                    <div>
                      <p className="font-medium text-gray-800">{uploadForm.file.name}</p>
                      <p className="text-sm text-gray-500">{formatFileSize(uploadForm.file.size)}</p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-gray-500">Nhấn để chọn file CSV</p>
                      <p className="text-xs text-gray-400 mt-1">hoặc kéo thả vào đây</p>
                    </div>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
              
              {uploadForm.partnerCode && uploadForm.serviceCode && (
                <p className="text-sm text-gray-500">
                  Sẽ lưu thành: <code className="bg-gray-100 px-1 rounded">
                    {uploadForm.partnerCode}_{uploadForm.serviceCode}_b4_mock.csv
                  </code>
                </p>
              )}
            </div>
            
            <div className="flex gap-2 mt-6">
              <button
                onClick={() => {
                  setUploadModal(false)
                  setUploadForm({ partnerCode: '', serviceCode: '', file: null })
                }}
                className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50 transition"
              >
                Hủy
              </button>
              <button
                onClick={handleUpload}
                disabled={uploadMutation.isPending || !uploadForm.file}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
              >
                {uploadMutation.isPending ? 'Đang upload...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Preview Modal */}
      {previewModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-5xl max-h-[80vh] flex flex-col">
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-800">
                Preview: {previewModal}
              </h3>
              <button
                onClick={() => setPreviewModal(null)}
                className="p-2 hover:bg-gray-100 rounded"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {previewLoading ? (
                <div className="text-center text-gray-500 py-8">Đang tải...</div>
              ) : previewData?.data ? (
                <div>
                  <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
                    <span>Tổng: <strong>{previewData.data.total_rows}</strong> dòng</span>
                    <span>Hiển thị: <strong>{previewData.data.preview_rows}</strong> dòng</span>
                    <span>Cột: <strong>{previewData.data.columns?.length}</strong></span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm border">
                      <thead className="bg-gray-100">
                        <tr>
                          <th className="px-3 py-2 border text-left">#</th>
                          {previewData.data.columns?.map(col => (
                            <th key={col} className="px-3 py-2 border text-left font-medium">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.data.data?.map((row, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-2 border text-gray-500">{idx + 1}</td>
                            {previewData.data.columns?.map(col => (
                              <td key={col} className="px-3 py-2 border">
                                {row[col]}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500">Không có dữ liệu</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

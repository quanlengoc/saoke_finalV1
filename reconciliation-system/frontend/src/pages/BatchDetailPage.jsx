import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { reconciliationApi, reportsApi, approvalsApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'

const statusColors = {
  'UPLOADING': 'bg-gray-100 text-gray-800',
  'PROCESSING': 'bg-yellow-100 text-yellow-800',
  'COMPLETED': 'bg-green-100 text-green-800',
  'APPROVED': 'bg-blue-100 text-blue-800',
  'REJECTED': 'bg-red-100 text-red-800',
  'ERROR': 'bg-red-100 text-red-800',
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

export default function BatchDetailPage() {
  const { batchId } = useParams()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [activeMainTab, setActiveMainTab] = useState('results') // results, report, history
  const [previewPageA1, setPreviewPageA1] = useState(0)
  const [previewPageA2, setPreviewPageA2] = useState(0)
  const [filterB1B4, setFilterB1B4] = useState('')
  const [filterB1B2, setFilterB1B2] = useState('')
  const [filterB3A1, setFilterB3A1] = useState('')
  const [filterFinalStatus, setFilterFinalStatus] = useState('')
  
  // Fetch batch details
  const { data: batchData, isLoading } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => reconciliationApi.getBatch(batchId),
  })
  
  // Fetch preview data for A1
  const { data: previewDataA1 } = useQuery({
    queryKey: ['preview', batchId, 'a1', previewPageA1, filterB1B4, filterB1B2, filterFinalStatus],
    queryFn: () => reportsApi.preview(batchId, 'a1', { 
      skip: previewPageA1 * 50, 
      limit: 50,
      status_b1b4: filterB1B4 || undefined,
      status_b1b2: filterB1B2 || undefined,
      final_status: filterFinalStatus || undefined
    }),
    enabled: !!batchData?.data && ['COMPLETED', 'APPROVED'].includes(batchData?.data?.status),
  })
  
  // Fetch preview data for A2
  const { data: previewDataA2 } = useQuery({
    queryKey: ['preview', batchId, 'a2', previewPageA2, filterB3A1],
    queryFn: () => reportsApi.preview(batchId, 'a2', { 
      skip: previewPageA2 * 50, 
      limit: 50,
      status_b3a1: filterB3A1 || undefined
    }),
    enabled: !!batchData?.data && ['COMPLETED', 'APPROVED'].includes(batchData?.data?.status),
  })
  
  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['stats', batchId],
    queryFn: () => reportsApi.getStats(batchId),
    enabled: !!batchData?.data,
  })
  
  const batch = batchData?.data
  const previewA1 = previewDataA1?.data
  const previewA2 = previewDataA2?.data
  const stats = statsData?.data
  
  // Mutations
  const rerunMutation = useMutation({
    mutationFn: () => reconciliationApi.rerunBatch(batchId),
    onSuccess: () => {
      toast.success('Đã chạy lại đối soát')
      queryClient.invalidateQueries(['batch', batchId])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })
  
  const submitMutation = useMutation({
    mutationFn: () => approvalsApi.submit(batchId),
    onSuccess: () => {
      toast.success('Đã gửi phê duyệt')
      queryClient.invalidateQueries(['batch', batchId])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
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
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[batch.status]}`}>
                {batch.status}
              </span>
              {batch.is_locked && (
                <span className="px-3 py-1 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                  🔒 Đã khóa
                </span>
              )}
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
            {batch.status === 'COMPLETED' && !batch.is_locked && (
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
            {['ERROR', 'UPLOADING'].includes(batch.status) && !batch.is_locked && (
              <button
                onClick={() => rerunMutation.mutate()}
                disabled={rerunMutation.isPending}
                className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition"
              >
                🔄 Chạy lại
              </button>
            )}
          </div>
        </div>
      </div>
      
      {/* Files Uploaded Section */}
      {batch.files_uploaded && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">📁 File đã upload</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* B1 Files */}
            <div className="border rounded-lg p-4">
              <h3 className="font-medium text-gray-700 mb-2">B1 - Dữ liệu đối tác</h3>
              {batch.files_uploaded.b1?.length > 0 ? (
                <ul className="space-y-1">
                  {batch.files_uploaded.b1.map((path, idx) => (
                    <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span className="truncate" title={path}>{path.split(/[/\\]/).pop()}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-400 italic">Không có file</p>
              )}
            </div>
            
            {/* B2 Files */}
            <div className="border rounded-lg p-4">
              <h3 className="font-medium text-gray-700 mb-2">B2 - Dữ liệu bổ sung</h3>
              {batch.files_uploaded.b2?.length > 0 ? (
                <ul className="space-y-1">
                  {batch.files_uploaded.b2.map((path, idx) => (
                    <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span className="truncate" title={path}>{path.split(/[/\\]/).pop()}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-400 italic">Không có file</p>
              )}
            </div>
            
            {/* B3 Files */}
            <div className="border rounded-lg p-4">
              <h3 className="font-medium text-gray-700 mb-2">B3 - Dữ liệu khác</h3>
              {batch.files_uploaded.b3?.length > 0 ? (
                <ul className="space-y-1">
                  {batch.files_uploaded.b3.map((path, idx) => (
                    <li key={idx} className="text-sm text-gray-600 flex items-center gap-2">
                      <span className="text-green-500">✓</span>
                      <span className="truncate" title={path}>{path.split(/[/\\]/).pop()}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-400 italic">Không có file</p>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* MAIN TABS: Kết quả | Báo cáo | Lịch sử */}
      {['COMPLETED', 'APPROVED'].includes(batch.status) && (
        <div className="bg-white rounded-xl shadow-sm">
          <div className="border-b flex">
            <button
              onClick={() => setActiveMainTab('results')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'results' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
            >
              📊 Kết quả
            </button>
            <button
              onClick={() => setActiveMainTab('report')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'report' ? 'border-b-2 border-green-600 text-green-600' : 'text-gray-500 hover:text-gray-700'}`}
            >
              📄 Báo cáo
            </button>
            <button
              onClick={() => setActiveMainTab('history')}
              className={`py-3 px-6 font-medium transition ${activeMainTab === 'history' ? 'border-b-2 border-purple-600 text-purple-600' : 'text-gray-500 hover:text-gray-700'}`}
            >
              📜 Lịch sử xử lý
            </button>
          </div>
          
          <div className="p-6">
            {/* ===== TAB: KẾT QUẢ ===== */}
            {activeMainTab === 'results' && (
              <div className="space-y-6">
                {/* 1. Khối số lượng bản ghi */}
                <div className="border rounded-lg p-4 bg-gray-50">
                  <h3 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <span className="text-blue-500">📁</span> Số lượng bản ghi
                  </h3>
                  <div className="grid grid-cols-5 gap-4">
                    <div className="bg-white rounded-lg p-3 border text-center">
                      <p className="text-xs text-gray-500 mb-1">B1 (Sao kê)</p>
                      <p className="text-xl font-bold text-blue-600">{stats?.basic_stats?.total_b1?.toLocaleString() || 0}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border text-center">
                      <p className="text-xs text-gray-500 mb-1">B2 (Bổ sung)</p>
                      <p className="text-xl font-bold text-purple-600">{stats?.basic_stats?.total_b2?.toLocaleString() || 0}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border text-center">
                      <p className="text-xs text-gray-500 mb-1">B3 (Khác)</p>
                      <p className="text-xl font-bold text-teal-600">{stats?.basic_stats?.total_b3?.toLocaleString() || 0}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border text-center">
                      <p className="text-xs text-gray-500 mb-1">B4 (Đối tác)</p>
                      <p className="text-xl font-bold text-orange-600">{stats?.basic_stats?.total_b4?.toLocaleString() || 0}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border text-center">
                      <p className="text-xs text-gray-500 mb-1">A1 (Kết quả)</p>
                      <p className="text-xl font-bold text-green-600">{stats?.a1_stats?.total?.toLocaleString() || 0}</p>
                    </div>
                  </div>
                  {/* A2 only if B3 matching is enabled */}
                  {stats?.basic_stats?.matching_stats?.b3_a1 && (
                    <div className="mt-3">
                      <div className="bg-white rounded-lg p-3 border text-center w-40">
                        <p className="text-xs text-gray-500 mb-1">A2 (Lệch B3↔A1)</p>
                        <p className="text-xl font-bold text-red-600">{stats?.a2_stats?.total?.toLocaleString() || 0}</p>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* 2. Khối kết quả so khớp */}
                <div className="border rounded-lg p-4 bg-gray-50">
                  <h3 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                    <span className="text-green-500">🔗</span> Kết quả so khớp
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* B1↔B4 */}
                    {stats?.basic_stats?.matching_stats?.b1_b4 && (
                      <div className="bg-white border rounded-lg p-4">
                        <h4 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                          <span className="text-blue-500">🔗</span> B1 ↔ B4
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between items-center">
                            <span className="text-gray-600">Tổng so sánh:</span>
                            <span className="font-semibold">{stats.basic_stats.matching_stats.b1_b4.total || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-green-600">✓ Khớp:</span>
                            <span className="font-semibold text-green-600">{stats.basic_stats.matching_stats.b1_b4.matched || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-red-600">✗ Không tìm thấy:</span>
                            <span className="font-semibold text-red-600">{stats.basic_stats.matching_stats.b1_b4.not_found || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-orange-600">⚠ Lệch:</span>
                            <span className="font-semibold text-orange-600">{stats.basic_stats.matching_stats.b1_b4.mismatch || 0}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* B1↔B2 */}
                    {stats?.basic_stats?.matching_stats?.b1_b2 && (
                      <div className="bg-white border rounded-lg p-4">
                        <h4 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                          <span className="text-purple-500">🔗</span> B1 ↔ B2
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between items-center">
                            <span className="text-gray-600">Tổng so sánh:</span>
                            <span className="font-semibold">{stats.basic_stats.matching_stats.b1_b2.total || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-green-600">✓ Khớp:</span>
                            <span className="font-semibold text-green-600">{stats.basic_stats.matching_stats.b1_b2.matched || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-red-600">✗ Không tìm thấy:</span>
                            <span className="font-semibold text-red-600">{stats.basic_stats.matching_stats.b1_b2.not_found || 0}</span>
                          </div>
                          {(stats.basic_stats.matching_stats.b1_b2.mismatch > 0) && (
                            <div className="flex justify-between items-center">
                              <span className="text-yellow-600">⚠ Lệch:</span>
                              <span className="font-semibold text-yellow-600">{stats.basic_stats.matching_stats.b1_b2.mismatch}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {/* B3↔A1 */}
                    {stats?.basic_stats?.matching_stats?.b3_a1 && (
                      <div className="bg-white border rounded-lg p-4">
                        <h4 className="font-medium text-gray-700 mb-3 flex items-center gap-2">
                          <span className="text-teal-500">🔗</span> B3 ↔ A1
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between items-center">
                            <span className="text-gray-600">Tổng so sánh:</span>
                            <span className="font-semibold">{stats.basic_stats.matching_stats.b3_a1.total || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-green-600">✓ Khớp:</span>
                            <span className="font-semibold text-green-600">{stats.basic_stats.matching_stats.b3_a1.matched || 0}</span>
                          </div>
                          <div className="flex justify-between items-center">
                            <span className="text-red-600">✗ Không tìm thấy:</span>
                            <span className="font-semibold text-red-600">{stats.basic_stats.matching_stats.b3_a1.not_found || 0}</span>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* No matching stats available */}
                    {!stats?.basic_stats?.matching_stats?.b1_b4 && !stats?.basic_stats?.matching_stats?.b1_b2 && !stats?.basic_stats?.matching_stats?.b3_a1 && (
                      <div className="col-span-3 text-center py-4 text-gray-500">
                        Chưa có dữ liệu thống kê so khớp.
                      </div>
                    )}
                  </div>
                </div>
                
                {/* 3. Khối chi tiết A1 */}
                <div className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-medium text-gray-700 flex items-center gap-2">
                      <span className="text-green-500">📄</span> Chi tiết kết quả A1 ({stats?.a1_stats?.total?.toLocaleString() || 0} bản ghi)
                    </h3>
                    <div className="flex gap-2">
                      <button
                        onClick={() => reportsApi.download(batchId, 'a1', 'csv').catch(e => toast.error('Lỗi tải file CSV'))}
                        className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
                      >
                        📥 CSV
                      </button>
                      <button
                        onClick={() => reportsApi.download(batchId, 'a1', 'xlsx').catch(e => toast.error('Lỗi tải file Excel'))}
                        className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
                      >
                        📥 Excel
                      </button>
                    </div>
                  </div>
                  
                  {/* A1 Status breakdown */}
                  {stats?.a1_stats?.by_final_status && (
                    <div className="mb-4 flex flex-wrap gap-2">
                      {Object.entries(stats.a1_stats.by_final_status).map(([status, count]) => (
                        <span key={status} className={`px-2 py-1 rounded text-xs ${
                          status.includes('MATCHED') || status.includes('OK') ? 'bg-green-100 text-green-700' :
                          status.includes('NOT') ? 'bg-red-100 text-red-700' :
                          status.includes('MISMATCH') || status.includes('ERROR') ? 'bg-orange-100 text-orange-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {status}: {count}
                        </span>
                      ))}
                    </div>
                  )}
                  
                  {/* A1 Filters */}
                  <div className="mb-4 flex items-center gap-4 flex-wrap bg-gray-50 p-3 rounded-lg">
                    <span className="text-sm font-medium text-gray-600">🔍 Lọc:</span>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-600">B1↔B4:</label>
                      <select 
                        value={filterB1B4} 
                        onChange={(e) => { setFilterB1B4(e.target.value); setPreviewPageA1(0); }}
                        className="px-2 py-1 border rounded text-xs"
                      >
                        <option value="">Tất cả</option>
                        <option value="MATCHED">✓ Khớp</option>
                        <option value="NOT_FOUND">✗ Không tìm thấy</option>
                        <option value="MISMATCH">⚠ Lệch</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-600">B1↔B2:</label>
                      <select 
                        value={filterB1B2} 
                        onChange={(e) => { setFilterB1B2(e.target.value); setPreviewPageA1(0); }}
                        className="px-2 py-1 border rounded text-xs"
                      >
                        <option value="">Tất cả</option>
                        <option value="MATCHED">✓ Khớp</option>
                        <option value="NOT_FOUND">✗ Không tìm thấy</option>
                        <option value="MISMATCH">⚠ Lệch</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="text-xs text-gray-600 font-semibold">Final Status:</label>
                      <select 
                        value={filterFinalStatus} 
                        onChange={(e) => { setFilterFinalStatus(e.target.value); setPreviewPageA1(0); }}
                        className="px-2 py-1 border rounded text-xs bg-blue-50"
                      >
                        <option value="">Tất cả</option>
                        {/* Lấy từ config status_combine_rules */}
                        {stats?.final_status_options?.map(st => (
                          <option key={st} value={st}>{st}</option>
                        ))}
                        {/* Fallback: lấy từ dữ liệu thực tế nếu config không có */}
                        {!stats?.final_status_options?.length && stats?.a1_stats?.by_final_status && Object.keys(stats.a1_stats.by_final_status).map(st => (
                          <option key={st} value={st}>{st}</option>
                        ))}
                      </select>
                    </div>
                    {(filterB1B4 || filterB1B2 || filterFinalStatus) && (
                      <button 
                        onClick={() => { setFilterB1B4(''); setFilterB1B2(''); setFilterFinalStatus(''); setPreviewPageA1(0); }}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Xóa bộ lọc
                      </button>
                    )}
                  </div>
                  
                  {/* A1 Data table */}
                  <div className="overflow-x-auto max-h-96 border rounded">
                    {previewA1 ? (
                      <>
                        <table className="w-full text-xs">
                          <thead className="bg-gray-100 sticky top-0">
                            <tr>
                              {previewA1.columns?.map((col) => (
                                <th key={col} className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap">
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y">
                            {previewA1.data?.map((row, idx) => (
                              <tr key={idx} className="hover:bg-gray-50">
                                {previewA1.columns?.map((col) => (
                                  <td key={col} className="px-3 py-2 whitespace-nowrap max-w-xs truncate">
                                    {row[col]}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {/* A1 Pagination */}
                        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t">
                          <p className="text-xs text-gray-500">
                            {previewPageA1 * 50 + 1} - {Math.min((previewPageA1 + 1) * 50, previewA1.total)} / {previewA1.total}
                          </p>
                          <div className="flex gap-1">
                            <button onClick={() => setPreviewPageA1(Math.max(0, previewPageA1 - 1))} disabled={previewPageA1 === 0} className="px-2 py-0.5 border rounded text-xs hover:bg-gray-100 disabled:opacity-50">←</button>
                            <button onClick={() => setPreviewPageA1(previewPageA1 + 1)} disabled={(previewPageA1 + 1) * 50 >= previewA1.total} className="px-2 py-0.5 border rounded text-xs hover:bg-gray-100 disabled:opacity-50">→</button>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="p-4 text-center text-gray-500 text-sm">Không có dữ liệu</div>
                    )}
                  </div>
                </div>
                
                {/* 4. Khối chi tiết A2 - Only show if B3 files were uploaded AND B3↔A1 matching is enabled */}
                {batch.files_uploaded?.b3?.length > 0 && stats?.basic_stats?.matching_stats?.b3_a1 && (
                  <div className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-medium text-gray-700 flex items-center gap-2">
                        <span className="text-red-500">⚠️</span> Chi tiết kết quả A2 - Lệch B3↔A1 ({stats?.a2_stats?.total?.toLocaleString() || 0} bản ghi)
                      </h3>
                      <div className="flex gap-2">
                        <button
                          onClick={() => reportsApi.download(batchId, 'a2', 'csv').catch(e => toast.error('Lỗi tải file CSV'))}
                          className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
                        >
                          📥 CSV
                        </button>
                        <button
                          onClick={() => reportsApi.download(batchId, 'a2', 'xlsx').catch(e => toast.error('Lỗi tải file Excel'))}
                          className="px-3 py-1 border rounded text-xs hover:bg-gray-50"
                        >
                          📥 Excel
                        </button>
                      </div>
                    </div>
                    
                    {/* A2 Status breakdown */}
                    {stats?.a2_stats?.by_status && (
                      <div className="mb-4 flex flex-wrap gap-2">
                        {Object.entries(stats.a2_stats.by_status).map(([status, count]) => (
                          <span key={status} className={`px-2 py-1 rounded text-xs ${
                            status.includes('MATCHED') ? 'bg-green-100 text-green-700' :
                            status.includes('NOT') ? 'bg-red-100 text-red-700' :
                            status.includes('MISMATCH') ? 'bg-orange-100 text-orange-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {status}: {count}
                          </span>
                        ))}
                      </div>
                    )}
                    
                    {/* A2 Filters */}
                    <div className="mb-4 flex items-center gap-4 flex-wrap bg-red-50 p-3 rounded-lg">
                      <span className="text-sm font-medium text-gray-600">🔍 Lọc B3↔A1:</span>
                      <select 
                        value={filterB3A1} 
                        onChange={(e) => { setFilterB3A1(e.target.value); setPreviewPageA2(0); }}
                        className="px-2 py-1 border rounded text-xs"
                      >
                        <option value="">Tất cả</option>
                        <option value="MATCHED">✓ Khớp</option>
                        <option value="NOT_FOUND">✗ Không tìm thấy</option>
                        <option value="MISMATCH">⚠ Lệch</option>
                      </select>
                      {filterB3A1 && (
                        <button 
                          onClick={() => { setFilterB3A1(''); setPreviewPageA2(0); }}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Xóa bộ lọc
                        </button>
                      )}
                    </div>
                    
                    {/* A2 Data table */}
                    <div className="overflow-x-auto max-h-96 border rounded">
                      {previewA2 ? (
                        <>
                          <table className="w-full text-xs">
                            <thead className="bg-red-50 sticky top-0">
                              <tr>
                                {previewA2.columns?.map((col) => (
                                  <th key={col} className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap">
                                    {col}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y">
                              {previewA2.data?.map((row, idx) => (
                                <tr key={idx} className="hover:bg-red-50">
                                  {previewA2.columns?.map((col) => (
                                    <td key={col} className="px-3 py-2 whitespace-nowrap max-w-xs truncate">
                                      {row[col]}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {/* A2 Pagination */}
                          <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t">
                            <p className="text-xs text-gray-500">
                              {previewPageA2 * 50 + 1} - {Math.min((previewPageA2 + 1) * 50, previewA2.total)} / {previewA2.total}
                            </p>
                            <div className="flex gap-1">
                              <button onClick={() => setPreviewPageA2(Math.max(0, previewPageA2 - 1))} disabled={previewPageA2 === 0} className="px-2 py-0.5 border rounded text-xs hover:bg-gray-100 disabled:opacity-50">←</button>
                              <button onClick={() => setPreviewPageA2(previewPageA2 + 1)} disabled={(previewPageA2 + 1) * 50 >= previewA2.total} className="px-2 py-0.5 border rounded text-xs hover:bg-gray-100 disabled:opacity-50">→</button>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="p-4 text-center text-gray-500 text-sm">Không có dữ liệu A2</div>
                      )}
                    </div>
                  </div>
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
                
                {/* Quick download buttons */}
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-gray-600 mb-3">📥 Tải nhanh dữ liệu</h4>
                  <div className="flex gap-3">
                    <button
                      onClick={() => reportsApi.download(batchId, 'a1', 'xlsx').catch(e => toast.error('Lỗi tải file'))}
                      className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                    >
                      📊 A1 Excel
                    </button>
                    <button
                      onClick={() => reportsApi.download(batchId, 'a1', 'csv').catch(e => toast.error('Lỗi tải file'))}
                      className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                    >
                      📄 A1 CSV
                    </button>
                    {stats?.basic_stats?.matching_stats?.b3_a1 && (
                      <>
                        <button
                          onClick={() => reportsApi.download(batchId, 'a2', 'xlsx').catch(e => toast.error('Lỗi tải file'))}
                          className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                        >
                          📊 A2 Excel
                        </button>
                        <button
                          onClick={() => reportsApi.download(batchId, 'a2', 'csv').catch(e => toast.error('Lỗi tải file'))}
                          className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm"
                        >
                          📄 A2 CSV
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            {/* ===== TAB: LỊCH SỬ XỬ LÝ ===== */}
            {activeMainTab === 'history' && (
              <div className="space-y-4">
                <h3 className="font-medium text-gray-700 flex items-center gap-2">
                  <span className="text-purple-500">📜</span> Lịch sử xử lý chi tiết
                </h3>
                
                {batch.step_logs && batch.step_logs.length > 0 ? (
                  <div className="space-y-2">
                    {batch.step_logs.map((log, idx) => (
                      <div key={idx} className={`flex items-start gap-4 p-3 rounded-lg ${
                        log.step?.includes('ERROR') || log.message?.includes('Lỗi') ? 'bg-red-50 border-l-4 border-red-500' :
                        log.step?.includes('COMPLETE') || log.message?.includes('thành công') ? 'bg-green-50 border-l-4 border-green-500' :
                        log.step?.includes('MATCHING') || log.step?.includes('LOAD') ? 'bg-blue-50 border-l-4 border-blue-500' :
                        'bg-gray-50 border-l-4 border-gray-300'
                      }`}>
                        <span className="text-xs text-gray-400 whitespace-nowrap font-mono min-w-[140px]">
                          {formatTimestamp(log.time || log.timestamp)}
                        </span>
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                          log.step?.includes('ERROR') ? 'bg-red-200 text-red-700' :
                          log.step?.includes('COMPLETE') ? 'bg-green-200 text-green-700' :
                          log.step?.includes('MATCHING') ? 'bg-purple-200 text-purple-700' :
                          log.step?.includes('LOAD') ? 'bg-blue-200 text-blue-700' :
                          log.step?.includes('REPORT') ? 'bg-yellow-200 text-yellow-700' :
                          'bg-gray-200 text-gray-700'
                        }`}>
                          {log.step}
                        </span>
                        <span className="text-sm text-gray-700 flex-1">{log.message}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <div className="text-4xl mb-3">📋</div>
                    <p>Chưa có lịch sử xử lý</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

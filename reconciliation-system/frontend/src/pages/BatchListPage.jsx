import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { reconciliationApi, partnersApi } from '../services/api'

const statusColors = {
  'UPLOADING': 'bg-gray-100 text-gray-800',
  'PROCESSING': 'bg-yellow-100 text-yellow-800',
  'COMPLETED': 'bg-green-100 text-green-800',
  'APPROVED': 'bg-blue-100 text-blue-800',
  'REJECTED': 'bg-red-100 text-red-800',
  'ERROR': 'bg-red-100 text-red-800',
}

export default function BatchListPage() {
  const queryClient = useQueryClient()
  const [expandedError, setExpandedError] = useState(null)
  const [filters, setFilters] = useState({
    partner_code: '',
    service_code: '',
    status: '',
    from_date: '',
    to_date: '',
  })
  
  // Rerun mutation
  const rerunMutation = useMutation({
    mutationFn: (batchId) => reconciliationApi.rerunBatch(batchId),
    onSuccess: () => {
      toast.success('Đã bắt đầu chạy lại đối soát')
      queryClient.invalidateQueries(['batches'])
    },
    onError: (err) => {
      const errorDetail = err.response?.data?.detail || err.response?.data?.error_message || err.message || 'Lỗi không xác định'
      toast.error(`Lỗi: ${errorDetail}`, { duration: 5000 })
      console.error('Rerun error:', err.response?.data)
    },
  })
  
  // Fetch partners for filter
  const { data: partnersData } = useQuery({
    queryKey: ['partners'],
    queryFn: () => partnersApi.getPartners(),
  })
  
  // Fetch batches
  const { data: batchesData, isLoading } = useQuery({
    queryKey: ['batches', filters],
    queryFn: () => reconciliationApi.listBatches(filters),
  })
  
  const partners = partnersData?.data || []
  const batches = batchesData?.data?.items || []
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Danh sách batch đối soát</h1>
        <Link
          to="/reconciliation"
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
        >
          + Tạo mới
        </Link>
      </div>
      
      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <select
            value={filters.partner_code}
            onChange={(e) => setFilters({ ...filters, partner_code: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value="">Tất cả đối tác</option>
            {partners.map((p) => (
              <option key={p.partner_code} value={p.partner_code}>{p.partner_name}</option>
            ))}
          </select>
          
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
          >
            <option value="">Tất cả trạng thái</option>
            <option value="PROCESSING">Đang xử lý</option>
            <option value="COMPLETED">Hoàn thành</option>
            <option value="APPROVED">Đã duyệt</option>
            <option value="REJECTED">Từ chối</option>
            <option value="ERROR">Lỗi</option>
          </select>
          
          <input
            type="date"
            value={filters.from_date}
            onChange={(e) => setFilters({ ...filters, from_date: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Từ ngày"
          />
          
          <input
            type="date"
            value={filters.to_date}
            onChange={(e) => setFilters({ ...filters, to_date: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Đến ngày"
          />
          
          <button
            onClick={() => setFilters({ partner_code: '', service_code: '', status: '', from_date: '', to_date: '' })}
            className="px-4 py-2 border rounded-lg hover:bg-gray-50 transition"
          >
            Xóa bộ lọc
          </button>
        </div>
      </div>
      
      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Đang tải...</div>
        ) : batches.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Không có dữ liệu</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Batch ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Đối tác / Dịch vụ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Kỳ đối soát</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cấu hình</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trạng thái</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Thời gian</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {batches.map((batch) => (
                <tr key={batch.batch_id} className={`hover:bg-gray-50 ${batch.status === 'ERROR' ? 'bg-red-50' : ''}`}>
                  <td className="px-6 py-4">
                    <div>
                      <span className="font-mono text-sm">{batch.batch_id}</span>
                      {batch.error_message && (
                        <button
                          onClick={() => setExpandedError(expandedError === batch.batch_id ? null : batch.batch_id)}
                          className="ml-2 text-red-500 hover:text-red-700 text-xs"
                          title="Xem lỗi"
                        >
                          ⚠️ Lỗi
                        </button>
                      )}
                    </div>
                    {expandedError === batch.batch_id && batch.error_message && (
                      <div className="mt-2 p-2 bg-red-100 border border-red-300 rounded text-xs text-red-800 max-w-md">
                        <pre className="whitespace-pre-wrap break-words">{batch.error_message}</pre>
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-gray-800">{batch.partner_code}</p>
                      <p className="text-sm text-gray-500">{batch.service_code}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {batch.period_from} - {batch.period_to}
                  </td>
                  <td className="px-6 py-4">
                    {batch.config_id ? (
                      <Link
                        to={`/admin/configs?edit=${batch.config_id}`}
                        className="text-blue-600 hover:underline text-sm"
                        title={`Config #${batch.config_id}`}
                      >
                        #{batch.config_id}
                      </Link>
                    ) : (
                      <span className="text-gray-400 text-sm">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[batch.status]}`}>
                      {batch.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(batch.created_at).toLocaleString('vi-VN')}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {['ERROR', 'UPLOADING'].includes(batch.status) && (
                        <button
                          onClick={() => rerunMutation.mutate(batch.batch_id)}
                          disabled={rerunMutation.isPending}
                          className="px-3 py-1 bg-orange-500 text-white rounded text-xs hover:bg-orange-600 transition disabled:opacity-50"
                        >
                          🔄 Chạy lại
                        </button>
                      )}
                      <Link
                        to={`/batches/${batch.batch_id}`}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        Chi tiết →
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

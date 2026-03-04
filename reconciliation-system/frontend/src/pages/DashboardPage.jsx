import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { reconciliationApi, approvalsApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'

export default function DashboardPage() {
  const { user } = useAuthStore()
  
  // Fetch recent batches
  const { data: batchesData } = useQuery({
    queryKey: ['recentBatches'],
    queryFn: () => reconciliationApi.listBatches({ limit: 5 }),
  })
  
  // Fetch approval stats
  const { data: statsData } = useQuery({
    queryKey: ['approvalStats'],
    queryFn: () => approvalsApi.getStats({}),
  })
  
  const recentBatches = batchesData?.data?.items || []
  const stats = statsData?.data || {}
  
  const statusColors = {
    'UPLOADING': 'bg-gray-100 text-gray-800',
    'PROCESSING': 'bg-yellow-100 text-yellow-800',
    'COMPLETED': 'bg-green-100 text-green-800',
    'APPROVED': 'bg-blue-100 text-blue-800',
    'REJECTED': 'bg-red-100 text-red-800',
    'ERROR': 'bg-red-100 text-red-800',
  }
  
  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h1 className="text-2xl font-bold text-gray-800">
          Xin chào, {user?.full_name}! 👋
        </h1>
        <p className="text-gray-500 mt-1">
          Chào mừng bạn đến với hệ thống đối soát giao dịch
        </p>
      </div>
      
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">📋</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Tổng batch</p>
              <p className="text-2xl font-bold text-gray-800">{stats.total || 0}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">⏳</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Chờ phê duyệt</p>
              <p className="text-2xl font-bold text-gray-800">{stats.pending_approval || 0}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">✅</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Đã duyệt</p>
              <p className="text-2xl font-bold text-gray-800">{stats.approved || 0}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
              <span className="text-2xl">❌</span>
            </div>
            <div>
              <p className="text-sm text-gray-500">Từ chối</p>
              <p className="text-2xl font-bold text-gray-800">{stats.rejected || 0}</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link
          to="/reconciliation"
          className="bg-blue-600 text-white rounded-xl p-6 hover:bg-blue-700 transition"
        >
          <div className="flex items-center gap-4">
            <span className="text-3xl">📤</span>
            <div>
              <h3 className="text-lg font-semibold">Tạo đối soát mới</h3>
              <p className="text-blue-100 text-sm">Upload file và chạy đối soát</p>
            </div>
          </div>
        </Link>
        
        <Link
          to="/approvals"
          className="bg-green-600 text-white rounded-xl p-6 hover:bg-green-700 transition"
        >
          <div className="flex items-center gap-4">
            <span className="text-3xl">✅</span>
            <div>
              <h3 className="text-lg font-semibold">Phê duyệt</h3>
              <p className="text-green-100 text-sm">{stats.pending_approval || 0} batch đang chờ duyệt</p>
            </div>
          </div>
        </Link>
      </div>
      
      {/* Recent Batches */}
      <div className="bg-white rounded-xl shadow-sm">
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">Batch gần đây</h2>
            <Link to="/batches" className="text-blue-600 hover:underline text-sm">
              Xem tất cả →
            </Link>
          </div>
        </div>
        
        <div className="divide-y">
          {recentBatches.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              Chưa có batch nào
            </div>
          ) : (
            recentBatches.map((batch) => (
              <Link
                key={batch.batch_id}
                to={`/batches/${batch.batch_id}`}
                className="flex items-center justify-between p-4 hover:bg-gray-50 transition"
              >
                <div>
                  <p className="font-medium text-gray-800">{batch.batch_id}</p>
                  <p className="text-sm text-gray-500">
                    {batch.partner_code} / {batch.service_code} • {batch.period_from} - {batch.period_to}
                  </p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[batch.status]}`}>
                  {batch.status}
                </span>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

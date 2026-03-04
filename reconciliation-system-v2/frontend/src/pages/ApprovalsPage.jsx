import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { approvalsApi } from '../services/api'

export default function ApprovalsPage() {
  const queryClient = useQueryClient()
  const [selectedBatch, setSelectedBatch] = useState(null)
  const [notes, setNotes] = useState('')
  const [action, setAction] = useState(null)
  
  // Fetch pending approvals
  const { data: pendingData, isLoading } = useQuery({
    queryKey: ['pendingApprovals'],
    queryFn: () => approvalsApi.listPending({}),
  })
  
  const pendingBatches = pendingData?.data || []
  
  // Mutations
  const approveMutation = useMutation({
    mutationFn: ({ batchId, notes }) => approvalsApi.approve(batchId, notes),
    onSuccess: () => {
      toast.success('Đã phê duyệt')
      queryClient.invalidateQueries(['pendingApprovals'])
      setSelectedBatch(null)
      setNotes('')
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })
  
  const rejectMutation = useMutation({
    mutationFn: ({ batchId, notes }) => approvalsApi.reject(batchId, notes),
    onSuccess: () => {
      toast.success('Đã từ chối')
      queryClient.invalidateQueries(['pendingApprovals'])
      setSelectedBatch(null)
      setNotes('')
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })
  
  const handleAction = () => {
    if (!selectedBatch) return
    
    if (action === 'approve') {
      approveMutation.mutate({ batchId: selectedBatch.batch_id, notes })
    } else if (action === 'reject') {
      if (!notes.trim()) {
        toast.error('Vui lòng nhập lý do từ chối')
        return
      }
      rejectMutation.mutate({ batchId: selectedBatch.batch_id, notes })
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Phê duyệt</h1>
        <p className="text-gray-500">Các batch đang chờ phê duyệt</p>
      </div>
      
      {/* Pending list */}
      <div className="bg-white rounded-xl shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Đang tải...</div>
        ) : pendingBatches.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p className="text-4xl mb-4">✅</p>
            <p>Không có batch nào đang chờ duyệt</p>
          </div>
        ) : (
          <div className="divide-y">
            {pendingBatches.map((batch) => (
              <div key={batch.batch_id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <Link
                        to={`/batches/${batch.batch_id}`}
                        className="font-medium text-blue-600 hover:underline"
                      >
                        {batch.batch_id}
                      </Link>
                      {batch.is_locked && (
                        <span className="px-2 py-0.5 rounded text-xs bg-orange-100 text-orange-800">
                          🔒 Đã gửi
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {batch.partner_code} / {batch.service_code} • {batch.reconcile_date}
                    </p>
                    {batch.stats && (
                      <p className="text-xs text-gray-400 mt-1">
                        A1: {batch.stats.total_a1} | A2: {batch.stats.total_a2}
                      </p>
                    )}
                  </div>
                  
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setSelectedBatch(batch); setAction('approve'); setNotes(''); }}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition text-sm"
                    >
                      ✓ Duyệt
                    </button>
                    <button
                      onClick={() => { setSelectedBatch(batch); setAction('reject'); setNotes(''); }}
                      className="px-4 py-2 border border-red-500 text-red-500 rounded-lg hover:bg-red-50 transition text-sm"
                    >
                      ✕ Từ chối
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Modal */}
      {selectedBatch && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              {action === 'approve' ? '✓ Phê duyệt' : '✕ Từ chối'} batch
            </h3>
            
            <div className="mb-4">
              <p className="text-sm text-gray-500 mb-2">Batch ID:</p>
              <p className="font-mono">{selectedBatch.batch_id}</p>
            </div>
            
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Ghi chú {action === 'reject' && <span className="text-red-500">*</span>}
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                rows={3}
                placeholder={action === 'reject' ? 'Nhập lý do từ chối...' : 'Ghi chú (không bắt buộc)'}
              />
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={() => { setSelectedBatch(null); setNotes(''); }}
                className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50 transition"
              >
                Hủy
              </button>
              <button
                onClick={handleAction}
                disabled={approveMutation.isPending || rejectMutation.isPending}
                className={`flex-1 px-4 py-2 rounded-lg text-white transition disabled:opacity-50 ${
                  action === 'approve' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
                }`}
              >
                {action === 'approve' ? 'Xác nhận duyệt' : 'Xác nhận từ chối'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

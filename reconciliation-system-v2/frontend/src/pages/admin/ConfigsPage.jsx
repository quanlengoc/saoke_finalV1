import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { configsApi } from '../../services/api'
import ConfigFormModal from '../../components/ConfigFormModal'

export default function ConfigsPage() {
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState({ partner_code: '', include_inactive: false })
  const [showModal, setShowModal] = useState(false)
  const [editConfig, setEditConfig] = useState(null)
  const [viewConfig, setViewConfig] = useState(null)
  
  // Fetch configs
  const { data: configsData, isLoading } = useQuery({
    queryKey: ['configs', filters],
    queryFn: () => configsApi.list(filters),
  })
  
  const configs = configsData?.data || []
  
  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => configsApi.delete(id, false),
    onSuccess: () => {
      toast.success('Đã vô hiệu hóa cấu hình')
      queryClient.invalidateQueries(['configs'])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })
  
  const handleDelete = (config) => {
    if (window.confirm(`Vô hiệu hóa cấu hình cho ${config.partner_code}/${config.service_code}?`)) {
      deleteMutation.mutate(config.id)
    }
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Quản lý cấu hình</h1>
          <p className="text-gray-500">Cấu hình đối soát cho từng đối tác/dịch vụ</p>
        </div>
        <button
          onClick={() => {
            setEditConfig(null)
            setShowModal(true)
          }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          + Thêm cấu hình
        </button>
      </div>
      
      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm p-4">
        <div className="flex items-center gap-4">
          <input
            type="text"
            value={filters.partner_code}
            onChange={(e) => setFilters({ ...filters, partner_code: e.target.value })}
            className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            placeholder="Tìm theo partner code..."
          />
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={filters.include_inactive}
              onChange={(e) => setFilters({ ...filters, include_inactive: e.target.checked })}
              className="w-4 h-4 rounded"
            />
            <span className="text-sm text-gray-600">Hiện cấu hình inactive</span>
          </label>
        </div>
      </div>
      
      {/* Configs table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Đang tải...</div>
        ) : configs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Chưa có cấu hình nào</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Đối tác</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Dịch vụ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Hiệu lực</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trạng thái</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {configs.map((config) => (
                <tr key={config.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-gray-600">{config.id}</td>
                  <td className="px-6 py-4">
                    <p className="font-medium text-gray-800">{config.partner_name}</p>
                    <p className="text-sm text-gray-500">{config.partner_code}</p>
                  </td>
                  <td className="px-6 py-4">
                    <p className="font-medium text-gray-800">{config.service_name}</p>
                    <p className="text-sm text-gray-500">{config.service_code}</p>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {config.valid_from} → {config.valid_to || '∞'}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      config.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {config.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => setViewConfig(config)}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        Xem
                      </button>
                      <button
                        onClick={() => {
                          setEditConfig(config)
                          setShowModal(true)
                        }}
                        className="text-green-600 hover:underline text-sm"
                      >
                        Sửa
                      </button>
                      <button
                        onClick={() => handleDelete(config)}
                        className="text-red-600 hover:underline text-sm"
                      >
                        Vô hiệu
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      
      {/* View Config Modal */}
      {viewConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-800">
                Chi tiết cấu hình: {viewConfig.partner_code}/{viewConfig.service_code}
              </h3>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setEditConfig(viewConfig)
                    setViewConfig(null)
                    setShowModal(true)
                  }}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Chỉnh sửa
                </button>
                <button
                  onClick={() => setViewConfig(null)}
                  className="p-2 hover:bg-gray-100 rounded"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
                {JSON.stringify(viewConfig, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
      
      {/* Config Form Modal */}
      <ConfigFormModal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false)
          setEditConfig(null)
        }}
        editConfig={editConfig}
      />
    </div>
  )
}

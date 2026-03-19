import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  PlusIcon, 
  EyeIcon, 
  PencilIcon, 
  TrashIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentDuplicateIcon,
  Cog6ToothIcon
} from '@heroicons/react/24/outline'
import { configsApiV2 } from '../../services/api'

export default function ConfigsV2Page() {
  const [configs, setConfigs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedConfig, setSelectedConfig] = useState(null)

  const pageSize = 20

  useEffect(() => {
    loadConfigs()
  }, [page])

  const loadConfigs = async () => {
    try {
      setLoading(true)
      const response = await configsApiV2.list({ page, page_size: pageSize })
      setConfigs(response.data.items)
      setTotal(response.data.total)
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể tải danh sách cấu hình')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (configId) => {
    if (!confirm('Bạn có chắc muốn xóa cấu hình này?')) return

    try {
      await configsApiV2.delete(configId)
      loadConfigs()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không thể xóa cấu hình')
    }
  }

  // Clone state
  const [cloneSource, setCloneSource] = useState(null)
  const [cloneForm, setCloneForm] = useState({
    partner_code: '', partner_name: '', service_code: '', service_name: '',
    valid_from: '', valid_to: '', is_active: true
  })
  const [cloneLoading, setCloneLoading] = useState(false)

  const openCloneModal = (config) => {
    setCloneSource(config)
    setCloneForm({
      partner_code: config.partner_code,
      partner_name: config.partner_name,
      service_code: config.service_code + '_COPY',
      service_name: config.service_name + ' (bản sao)',
      valid_from: config.valid_from || '',
      valid_to: config.valid_to || '',
      is_active: true,
    })
  }

  const handleClone = async () => {
    if (!cloneForm.partner_code || !cloneForm.service_code || !cloneForm.valid_from) {
      alert('Vui lòng điền đầy đủ thông tin bắt buộc')
      return
    }
    setCloneLoading(true)
    try {
      const payload = {
        ...cloneForm,
        valid_to: cloneForm.valid_to || null,
      }
      await configsApiV2.clone(cloneSource.id, payload)
      setCloneSource(null)
      loadConfigs()
    } catch (err) {
      alert(err.response?.data?.detail || 'Không thể clone cấu hình')
    } finally {
      setCloneLoading(false)
    }
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
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Quản lý Cấu hình V2</h1>
          <p className="text-sm text-gray-500 mt-1">
            Hệ thống đối soát động - Số nguồn dữ liệu và workflow không giới hạn
          </p>
        </div>
        <Link
          to="/admin/configs-v2/new"
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow-md font-medium transition-colors"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          Thêm cấu hình
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">{error}</div>
      )}

      {/* Configs Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Partner / Service
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Nguồn dữ liệu
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Workflow Steps
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Outputs
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Trạng thái
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Hiệu lực
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Thao tác
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {configs.map((config) => (
              <tr key={config.id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div className="font-medium text-gray-900">
                    {config.partner_code}/{config.service_code}
                  </div>
                  <div className="text-sm text-gray-500">{config.partner_name}</div>
                  <div className="text-xs text-gray-400">{config.service_name}</div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {config.data_sources?.map((ds) => (
                      <span
                        key={ds.source_name}
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                          ${ds.source_type === 'FILE_UPLOAD' ? 'bg-blue-100 text-blue-800' : ''}
                          ${ds.source_type === 'DATABASE' ? 'bg-green-100 text-green-800' : ''}
                          ${ds.source_type === 'SFTP' ? 'bg-purple-100 text-purple-800' : ''}
                          ${ds.source_type === 'API' ? 'bg-orange-100 text-orange-800' : ''}
                        `}
                      >
                        {ds.source_name}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm">
                    {config.workflow_steps?.length || 0} bước
                  </div>
                  <div className="text-xs text-gray-400">
                    {config.workflow_steps?.filter(ws => ws.is_final_output).length || 0} output cuối
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {config.output_configs?.map((oc) => (
                      <span
                        key={oc.output_name}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800"
                      >
                        {oc.output_name}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4">
                  {config.is_active ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <CheckCircleIcon className="h-4 w-4 mr-1" />
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      <XCircleIcon className="h-4 w-4 mr-1" />
                      Inactive
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  {config.valid_from} - {config.valid_to || '∞'}
                </td>
                <td className="px-6 py-4 text-right">
                  <div className="flex justify-end gap-2">
                    <Link
                      to={`/admin/configs-v2/${config.id}`}
                      className="text-blue-600 hover:text-blue-800 font-medium"
                      title="Xem chi tiết"
                    >
                      <EyeIcon className="h-5 w-5" />
                    </Link>
                    <Link
                      to={`/admin/configs-v2/${config.id}/edit`}
                      className="text-yellow-600 hover:text-yellow-900"
                      title="Chỉnh sửa"
                    >
                      <PencilIcon className="h-5 w-5" />
                    </Link>
                    <button
                      onClick={() => openCloneModal(config)}
                      className="text-green-600 hover:text-green-900"
                      title="Clone cấu hình"
                    >
                      <DocumentDuplicateIcon className="h-5 w-5" />
                    </button>
                    <button
                      onClick={() => handleDelete(config.id)}
                      className="text-red-600 hover:text-red-900"
                      title="Xóa"
                    >
                      <TrashIcon className="h-5 w-5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex justify-between items-center">
          <div className="text-sm text-gray-500">
            Hiển thị {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} / {total} cấu hình
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Trước
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page * pageSize >= total}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Sau
            </button>
          </div>
        </div>
      )}

      {/* Clone Modal */}
      {cloneSource && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg">
            <h3 className="text-lg font-bold mb-1">Clone cấu hình</h3>
            <p className="text-xs text-gray-500 mb-4">
              Sao chép từ: <strong>{cloneSource.partner_code} / {cloneSource.service_code}</strong> (ID: {cloneSource.id})
              <br />Toàn bộ nguồn dữ liệu, workflow, report template sẽ được clone.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Mã đối tác *</label>
                <input type="text" value={cloneForm.partner_code}
                  onChange={e => setCloneForm(f => ({ ...f, partner_code: e.target.value }))}
                  className="w-full px-3 py-2 border rounded text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Tên đối tác *</label>
                <input type="text" value={cloneForm.partner_name}
                  onChange={e => setCloneForm(f => ({ ...f, partner_name: e.target.value }))}
                  className="w-full px-3 py-2 border rounded text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Mã dịch vụ *</label>
                <input type="text" value={cloneForm.service_code}
                  onChange={e => setCloneForm(f => ({ ...f, service_code: e.target.value }))}
                  className="w-full px-3 py-2 border rounded text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Tên dịch vụ *</label>
                <input type="text" value={cloneForm.service_name}
                  onChange={e => setCloneForm(f => ({ ...f, service_name: e.target.value }))}
                  className="w-full px-3 py-2 border rounded text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Hiệu lực từ *</label>
                <input type="date" value={cloneForm.valid_from}
                  onChange={e => setCloneForm(f => ({ ...f, valid_from: e.target.value }))}
                  className="w-full px-3 py-2 border rounded text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Hiệu lực đến</label>
                <input type="date" value={cloneForm.valid_to}
                  onChange={e => setCloneForm(f => ({ ...f, valid_to: e.target.value }))}
                  className="w-full px-3 py-2 border rounded text-sm" />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setCloneSource(null)}
                className="px-4 py-2 text-sm text-gray-600 border rounded hover:bg-gray-50">
                Hủy
              </button>
              <button onClick={handleClone} disabled={cloneLoading}
                className="px-4 py-2 text-sm text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 flex items-center gap-2">
                {cloneLoading && <ArrowPathIcon className="h-4 w-4 animate-spin" />}
                <DocumentDuplicateIcon className="h-4 w-4" />
                Clone
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { usersApi, configsApi } from '../../services/api'

export default function UsersPage() {
  const queryClient = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    full_name: '',
    is_admin: false,
  })
  const [permissions, setPermissions] = useState([])
  const [showPassword, setShowPassword] = useState(false)

  // Fetch users
  const { data: usersData, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => usersApi.list(),
  })

  // Fetch configs to get partner/service list for permission assignment
  const { data: configsData } = useQuery({
    queryKey: ['configsForPermissions'],
    queryFn: () => configsApi.list({ include_inactive: false }),
  })

  // Fetch user detail with permissions when editing
  const { data: userDetailData } = useQuery({
    queryKey: ['userDetail', editingUser?.id],
    queryFn: () => usersApi.get(editingUser.id),
    enabled: !!editingUser,
  })

  const users = usersData?.data || []
  // Extract unique partner/service pairs from configs (memoized to avoid re-render loops)
  const allPartners = useMemo(() => {
    const configs = configsData?.data?.items || configsData?.data || []
    return configs.reduce((acc, config) => {
      const key = `${config.partner_code}_${config.service_code}`
      if (!acc.find(p => `${p.partner_code}_${p.service_code}` === key)) {
        acc.push({
          partner_code: config.partner_code,
          partner_name: config.partner_name,
          service_code: config.service_code,
          service_name: config.service_name
        })
      }
      return acc
    }, [])
  }, [configsData])

  // Load permissions when user detail is fetched — filter by active configs only
  // to remove orphaned permissions (partner/service no longer in any active config)
  useEffect(() => {
    if (userDetailData?.data?.permissions && allPartners.length > 0) {
      const activeKeys = new Set(allPartners.map(p => `${p.partner_code}_${p.service_code}`))
      setPermissions(
        userDetailData.data.permissions
          .filter(p => activeKeys.has(`${p.partner_code}_${p.service_code}`))
          .map(p => ({
            partner_code: p.partner_code,
            service_code: p.service_code,
            can_reconcile: p.can_reconcile,
            can_approve: p.can_approve,
          }))
      )
    }
  }, [userDetailData, allPartners])

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data) => usersApi.create(data),
    onSuccess: () => {
      toast.success('Tạo user thành công')
      queryClient.invalidateQueries(['users'])
      setShowModal(false)
      resetForm()
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => usersApi.update(id, data),
    onSuccess: () => {
      toast.success('Cập nhật thành công')
      queryClient.invalidateQueries(['users'])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })

  const permissionMutation = useMutation({
    mutationFn: ({ userId, permissions: perms }) => usersApi.bulkUpdatePermissions(userId, perms),
    onSuccess: () => {
      toast.success('Cập nhật quyền thành công')
      queryClient.invalidateQueries(['users'])
      queryClient.invalidateQueries(['userDetail'])
      setShowModal(false)
      resetForm()
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi cập nhật quyền'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => usersApi.delete(id),
    onSuccess: () => {
      toast.success('Xóa thành công')
      queryClient.invalidateQueries(['users'])
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Lỗi'),
  })

  const resetForm = () => {
    setFormData({ email: '', password: '', full_name: '', is_admin: false })
    setPermissions([])
    setEditingUser(null)
    setShowPassword(false)
  }

  const handleEdit = (user) => {
    setEditingUser(user)
    setFormData({
      email: user.email,
      password: '',
      full_name: user.full_name,
      is_admin: user.is_admin,
    })
    setPermissions([]) // will be loaded by useEffect when userDetailData arrives
    setShowModal(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (editingUser) {
      const data = { ...formData }
      if (!data.password) delete data.password
      // Update user info first, then permissions
      updateMutation.mutate({ id: editingUser.id, data }, {
        onSuccess: () => {
          // After user info saved, save permissions
          if (!formData.is_admin) {
            permissionMutation.mutate({ userId: editingUser.id, permissions })
          } else {
            // Admin doesn't need specific permissions
            queryClient.invalidateQueries(['userDetail'])
            setShowModal(false)
            resetForm()
          }
        }
      })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handleDelete = (user) => {
    if (window.confirm(`Xóa user ${user.email}?`)) {
      deleteMutation.mutate(user.id)
    }
  }

  const togglePermission = (partnerCode, serviceCode, field) => {
    setPermissions(prev => {
      const existing = prev.find(
        p => p.partner_code === partnerCode && p.service_code === serviceCode
      )
      if (existing) {
        const updated = { ...existing, [field]: !existing[field] }
        // Remove if both are false
        if (!updated.can_reconcile && !updated.can_approve) {
          return prev.filter(p => !(p.partner_code === partnerCode && p.service_code === serviceCode))
        }
        return prev.map(p =>
          p.partner_code === partnerCode && p.service_code === serviceCode ? updated : p
        )
      } else {
        return [...prev, {
          partner_code: partnerCode,
          service_code: serviceCode,
          can_reconcile: field === 'can_reconcile',
          can_approve: field === 'can_approve',
        }]
      }
    })
  }

  const getPermission = (partnerCode, serviceCode) => {
    return permissions.find(
      p => p.partner_code === partnerCode && p.service_code === serviceCode
    ) || { can_reconcile: false, can_approve: false }
  }

  const isAllChecked = (field) => {
    if (allPartners.length === 0) return false
    return allPartners.every(p => {
      const perm = getPermission(p.partner_code, p.service_code)
      return perm[field]
    })
  }

  const toggleAll = (field) => {
    const allChecked = isAllChecked(field)
    if (allChecked) {
      // Uncheck all for this field
      setPermissions(prev =>
        prev.map(p => ({ ...p, [field]: false })).filter(p => p.can_reconcile || p.can_approve)
      )
    } else {
      // Check all for this field
      setPermissions(prev => {
        const updated = [...prev]
        allPartners.forEach(partner => {
          const existing = updated.find(
            p => p.partner_code === partner.partner_code && p.service_code === partner.service_code
          )
          if (existing) {
            existing[field] = true
          } else {
            updated.push({
              partner_code: partner.partner_code,
              service_code: partner.service_code,
              can_reconcile: field === 'can_reconcile',
              can_approve: field === 'can_approve',
            })
          }
        })
        return updated
      })
    }
  }

  // Count permissions for display in table
  const getUserPermissionSummary = (user) => {
    if (user.is_admin) return null
    const perms = user.permissions || []
    if (perms.length === 0) return 'Chưa phân quyền'
    const reconcileCount = perms.filter(p => p.can_reconcile).length
    const approveCount = perms.filter(p => p.can_approve).length
    const parts = []
    if (reconcileCount > 0) parts.push(`${reconcileCount} đối soát`)
    if (approveCount > 0) parts.push(`${approveCount} phê duyệt`)
    return parts.join(', ')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Quản lý Users</h1>
          <p className="text-gray-500">Quản lý tài khoản và phân quyền người dùng</p>
        </div>
        <button
          onClick={() => { resetForm(); setShowModal(true); }}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          + Thêm user
        </button>
      </div>

      {/* Users table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Đang tải...</div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Họ tên</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Role</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trạng thái</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-gray-600">{user.id}</td>
                  <td className="px-6 py-4 font-medium text-gray-800">{user.email}</td>
                  <td className="px-6 py-4 text-gray-600">{user.full_name}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      user.is_admin ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {user.is_admin ? 'Admin' : 'User'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(user)}
                        className="text-blue-600 hover:underline text-sm"
                      >
                        Sửa
                      </button>
                      <button
                        onClick={() => handleDelete(user)}
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

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">
              {editingUser ? 'Sửa user' : 'Thêm user mới'}
            </h3>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Mật khẩu {editingUser && '(để trống nếu không đổi)'}
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      className="w-full px-4 py-2 pr-10 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                      required={!editingUser}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                      tabIndex={-1}
                    >
                      {showPassword ? (
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Họ tên</label>
                  <input
                    type="text"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  />
                </div>

                <div className="flex items-end pb-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_admin"
                      checked={formData.is_admin}
                      onChange={(e) => setFormData({ ...formData, is_admin: e.target.checked })}
                      className="w-4 h-4 rounded border-gray-300"
                    />
                    <label htmlFor="is_admin" className="text-sm text-gray-700">
                      Là Admin (toàn quyền)
                    </label>
                  </div>
                </div>
              </div>

              {/* Permissions section - only for non-admin users when editing */}
              {editingUser && !formData.is_admin && (
                <div className="border-t pt-4 mt-4">
                  <h4 className="text-sm font-semibold text-gray-800 mb-3">
                    Phân quyền theo Partner / Service
                  </h4>

                  {allPartners.length === 0 ? (
                    <p className="text-sm text-gray-500 italic">Chưa có cấu hình nào. Tạo cấu hình trước khi phân quyền.</p>
                  ) : (
                    <div className="border rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-2 text-left font-medium text-gray-600">Partner / Service</th>
                            <th className="px-4 py-2 text-center font-medium text-gray-600 w-32">
                              <div className="flex flex-col items-center gap-1">
                                <span>Đối soát</span>
                                <label className="flex items-center gap-1 text-xs text-gray-400 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={isAllChecked('can_reconcile')}
                                    onChange={() => toggleAll('can_reconcile')}
                                    className="w-3 h-3 rounded border-gray-300"
                                  />
                                  Tất cả
                                </label>
                              </div>
                            </th>
                            <th className="px-4 py-2 text-center font-medium text-gray-600 w-32">
                              <div className="flex flex-col items-center gap-1">
                                <span>Phê duyệt</span>
                                <label className="flex items-center gap-1 text-xs text-gray-400 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={isAllChecked('can_approve')}
                                    onChange={() => toggleAll('can_approve')}
                                    className="w-3 h-3 rounded border-gray-300"
                                  />
                                  Tất cả
                                </label>
                              </div>
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {allPartners.map((p) => {
                            const perm = getPermission(p.partner_code, p.service_code)
                            return (
                              <tr key={`${p.partner_code}_${p.service_code}`} className="hover:bg-gray-50">
                                <td className="px-4 py-2">
                                  <div className="font-medium text-gray-800">{p.partner_name || p.partner_code}</div>
                                  <div className="text-xs text-gray-500">{p.service_name || p.service_code}</div>
                                </td>
                                <td className="px-4 py-2 text-center">
                                  <input
                                    type="checkbox"
                                    checked={perm.can_reconcile}
                                    onChange={() => togglePermission(p.partner_code, p.service_code, 'can_reconcile')}
                                    className="w-4 h-4 rounded border-gray-300 text-blue-600"
                                  />
                                </td>
                                <td className="px-4 py-2 text-center">
                                  <input
                                    type="checkbox"
                                    checked={perm.can_approve}
                                    onChange={() => togglePermission(p.partner_code, p.service_code, 'can_approve')}
                                    className="w-4 h-4 rounded border-gray-300 text-orange-600"
                                  />
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {editingUser && formData.is_admin && (
                <div className="border-t pt-4 mt-4">
                  <p className="text-sm text-gray-500 italic">
                    Admin có toàn quyền trên tất cả partner/service, không cần phân quyền riêng.
                  </p>
                </div>
              )}

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowModal(false); resetForm(); }}
                  className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50 transition"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending || permissionMutation.isPending}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
                >
                  {editingUser ? 'Cập nhật' : 'Tạo mới'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

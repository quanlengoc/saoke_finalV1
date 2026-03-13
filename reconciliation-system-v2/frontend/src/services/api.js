import axios from 'axios'

// ============================================================================
// Single API instance - V2 only
// ============================================================================

const api = axios.create({
  baseURL: '/api/v2',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Helper function to get token from localStorage
const getToken = () => {
  try {
    const authStorage = localStorage.getItem('auth-storage')
    if (authStorage) {
      const parsed = JSON.parse(authStorage)
      return parsed?.state?.token || null
    }
  } catch (e) {
    console.error('[API] Error reading token from localStorage:', e)
  }
  return null
}

// Set token directly to axios defaults (call this after login)
export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
  } else {
    delete api.defaults.headers.common['Authorization']
  }
}

// Initialize token from localStorage on app load
const initToken = getToken()
if (initToken) {
  setAuthToken(initToken)
}

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    if (!config.headers.Authorization) {
      const token = getToken()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth-storage')
      setAuthToken(null)
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ============================================================================
// Auth API
// ============================================================================

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  getMe: () => api.get('/auth/me'),
  changePassword: (currentPassword, newPassword) =>
    api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
}

// ============================================================================
// Partners API
// ============================================================================

export const partnersApi = {
  list: () => api.get('/partners'),
  getPartners: () => api.get('/partners/partners'),
  getServices: (partnerCode) => api.get(`/partners/services/${partnerCode}`),
  getConfig: (partnerCode, serviceCode, date) =>
    api.get(`/partners/config/${partnerCode}/${serviceCode}`, { params: { target_date: date } }),
}

// ============================================================================
// Reconciliation API
// ============================================================================

export const reconciliationApi = {
  uploadFiles: (configId, files, sourceNames, onProgress) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    formData.append('source_names', sourceNames.join(','))
    return api.post(`/reconciliation/upload-files/${configId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      }
    })
  },
  run: (requestData, batchFolder, forceReplace = false) =>
    api.post('/reconciliation/run', requestData, {
      params: { batch_folder: batchFolder, force_replace: forceReplace }
    }),
  checkDuplicate: (requestData) =>
    api.post('/reconciliation/check-duplicate', requestData),
  deleteBatch: (batchId) =>
    api.delete(`/reconciliation/batches/${batchId}`),
  listBatches: (params) => {
    const cleanParams = Object.fromEntries(
      Object.entries(params || {}).filter(([_, v]) => v !== '' && v != null)
    )
    return api.get('/reconciliation/batches', { params: cleanParams })
  },
  getBatch: (batchId) => api.get(`/reconciliation/batches/${batchId}`),
  rerunBatch: (batchId) => api.post(`/reconciliation/batches/${batchId}/rerun`),
  stopBatch: (batchId) => api.post(`/reconciliation/batches/${batchId}/stop`),
  getRunLogs: (batchId, runNumber) => api.get(`/reconciliation/batches/${batchId}/runs/${runNumber}/logs`),
}

// ============================================================================
// Reports API
// ============================================================================

export const reportsApi = {
  preview: (batchId, fileType, params) =>
    api.get(`/reports/preview/${batchId}/${fileType}`, { params }),
  downloadUrl: (batchId, fileType, format = 'csv') =>
    `/api/v2/reports/download/${batchId}/${fileType}?format=${format}`,
  download: async (batchId, fileType, format = 'csv') => {
    const response = await api.get(`/reports/download/${batchId}/${fileType}`, {
      params: { format },
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${batchId}_${fileType}.${format}`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    return response
  },
  generateReport: (batchId) => api.post(`/reports/generate/${batchId}`),
  getStats: (batchId) => api.get(`/reports/stats/${batchId}`),
}

// ============================================================================
// Approvals API
// ============================================================================

export const approvalsApi = {
  listPending: (params) => api.get('/approvals/pending', { params }),
  submit: (batchId) => api.post(`/approvals/submit/${batchId}`),
  approve: (batchId, notes) => api.post(`/approvals/approve/${batchId}`, { notes }),
  reject: (batchId, notes) => api.post(`/approvals/reject/${batchId}`, { notes }),
  unlock: (batchId) => api.post(`/approvals/unlock/${batchId}`),
  getHistory: (batchId) => api.get(`/approvals/history/${batchId}`),
  getStats: (params) => api.get('/approvals/stats', { params }),
}

// ============================================================================
// Users API (Admin)
// ============================================================================

export const usersApi = {
  list: () => api.get('/users/'),
  get: (userId) => api.get(`/users/${userId}`),
  create: (data) => api.post('/users/', data),
  update: (userId, data) => api.put(`/users/${userId}`, data),
  delete: (userId) => api.delete(`/users/${userId}`),
  addPermission: (userId, permission) => api.post(`/users/${userId}/permissions`, permission),
  removePermission: (userId, permissionId) => api.delete(`/users/${userId}/permissions/${permissionId}`),
  bulkUpdatePermissions: (userId, permissions) => api.put(`/users/${userId}/permissions/bulk`, { permissions }),
}

// ============================================================================
// Configs API
// ============================================================================

export const configsApi = {
  list: (params) => api.get('/configs/', { params }),
  get: (configId) => api.get(`/configs/${configId}`),
  create: (data) => api.post('/configs/', data),
  update: (configId, data) => api.patch(`/configs/${configId}`, data),
  delete: (configId) => api.delete(`/configs/${configId}`),
}

// ============================================================================
// Data Sources API
// ============================================================================

export const dataSourcesApi = {
  getByConfig: (configId) => api.get(`/data-sources/by-config/${configId}`),
  get: (sourceId) => api.get(`/data-sources/${sourceId}`),
  create: (data) => api.post('/data-sources/', data),
  update: (sourceId, data) => api.patch(`/data-sources/${sourceId}`, data),
  delete: (sourceId) => api.delete(`/data-sources/${sourceId}`),
}

// ============================================================================
// Workflows API
// ============================================================================

export const workflowsApi = {
  getByConfig: (configId) => api.get(`/workflows/by-config/${configId}`),
  get: (stepId) => api.get(`/workflows/${stepId}`),
  create: (data) => api.post('/workflows/', data),
  update: (stepId, data) => api.patch(`/workflows/${stepId}`, data),
  delete: (stepId) => api.delete(`/workflows/${stepId}`),
}

// ============================================================================
// Outputs API
// ============================================================================

export const outputsApi = {
  getByConfig: (configId) => api.get(`/outputs/by-config/${configId}`),
  get: (outputId) => api.get(`/outputs/${outputId}`),
  create: (data) => api.post('/outputs/', data),
  update: (outputId, data) => api.patch(`/outputs/${outputId}`, data),
  delete: (outputId) => api.delete(`/outputs/${outputId}`),
}

// ============================================================================
// Mock Data API (Admin)
// ============================================================================

export const mockDataApi = {
  list: () => api.get('/mock-data'),
  upload: (partnerCode, serviceCode, file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/mock-data/upload', formData, {
      params: { partner_code: partnerCode, service_code: serviceCode },
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  preview: (filename, limit = 20) =>
    api.get(`/mock-data/preview/${filename}`, { params: { limit } }),
  download: (filename) => `/api/v2/mock-data/download/${filename}`,
  delete: (filename) => api.delete(`/mock-data/${filename}`),
  getColumns: (partnerCode, serviceCode) =>
    api.get(`/mock-data/columns/${partnerCode}/${serviceCode}`),
}

// ============================================================================
// Backward compatibility aliases (for pages still using old V2 names)
// ============================================================================

export const configsApiV2 = configsApi
export const dataSourcesApiV2 = dataSourcesApi
export const workflowsApiV2 = workflowsApi
export const outputsApiV2 = outputsApi
export const reconciliationApiV2 = reconciliationApi

export default api

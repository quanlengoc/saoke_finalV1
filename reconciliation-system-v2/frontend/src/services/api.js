import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Helper function to get token from localStorage (avoid circular import)
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

// Request interceptor - add auth token (backup method)
api.interceptors.request.use(
  (config) => {
    // Check if Authorization header is already set
    if (!config.headers.Authorization) {
      const token = getToken()
      console.log('[API Interceptor] Token from localStorage:', token ? 'exists' : 'null')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    console.log('[API Request]', config.method?.toUpperCase(), config.url, 'Auth:', config.headers.Authorization ? 'Yes' : 'No')
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle 401/403
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      // Clear auth storage and redirect to login
      localStorage.removeItem('auth-storage')
      setAuthToken(null)
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  getMe: () => api.get('/auth/me'),
  changePassword: (currentPassword, newPassword) => 
    api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword }),
}

// Partners API
export const partnersApi = {
  list: () => api.get('/partners'),
  getPartners: () => api.get('/partners/partners'),
  getServices: (partnerCode) => api.get(`/partners/services/${partnerCode}`),
  getConfig: (partnerCode, serviceCode, date) => 
    api.get(`/partners/config/${partnerCode}/${serviceCode}`, { params: { target_date: date } }),
}

// Reconciliation API
export const reconciliationApi = {
  upload: (formData) => api.post('/reconciliation/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  listBatches: (params) => {
    // Filter out empty string values to avoid 422 errors
    const cleanParams = Object.fromEntries(
      Object.entries(params || {}).filter(([_, v]) => v !== '' && v != null)
    )
    return api.get('/reconciliation/batches', { params: cleanParams })
  },
  getBatch: (batchId) => api.get(`/reconciliation/batches/${batchId}`),
  rerunBatch: (batchId) => api.post(`/reconciliation/batches/${batchId}/rerun`),
  checkDuplicate: (partnerCode, serviceCode, dateFrom, dateTo) => 
    api.get('/reconciliation/check-duplicate', { 
      params: { partner_code: partnerCode, service_code: serviceCode, date_from: dateFrom, date_to: dateTo } 
    }),
  deleteBatch: (batchId) => api.delete(`/reconciliation/batches/${batchId}`),
}

// Reports API
export const reportsApi = {
  preview: (batchId, fileType, params) => 
    api.get(`/reports/preview/${batchId}/${fileType}`, { params }),
  downloadUrl: (batchId, fileType, format = 'csv') => 
    `/api/v1/reports/download/${batchId}/${fileType}?format=${format}`,
  download: async (batchId, fileType, format = 'csv') => {
    const response = await api.get(`/reports/download/${batchId}/${fileType}`, {
      params: { format },
      responseType: 'blob'
    })
    // Create download link
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

// Approvals API
export const approvalsApi = {
  listPending: (params) => api.get('/approvals/pending', { params }),
  submit: (batchId) => api.post(`/approvals/submit/${batchId}`),
  approve: (batchId, notes) => api.post(`/approvals/approve/${batchId}`, { notes }),
  reject: (batchId, notes) => api.post(`/approvals/reject/${batchId}`, { notes }),
  unlock: (batchId) => api.post(`/approvals/unlock/${batchId}`),
  getHistory: (batchId) => api.get(`/approvals/history/${batchId}`),
  getStats: (params) => api.get('/approvals/stats', { params }),
}

// Users API (Admin)
export const usersApi = {
  list: () => {
    const token = getToken()
    return api.get('/users/', { headers: { Authorization: `Bearer ${token}` } })
  },
  get: (userId) => {
    const token = getToken()
    return api.get(`/users/${userId}`, { headers: { Authorization: `Bearer ${token}` } })
  },
  create: (data) => {
    const token = getToken()
    return api.post('/users/', data, { headers: { Authorization: `Bearer ${token}` } })
  },
  update: (userId, data) => {
    const token = getToken()
    return api.put(`/users/${userId}`, data, { headers: { Authorization: `Bearer ${token}` } })
  },
  delete: (userId) => {
    const token = getToken()
    return api.delete(`/users/${userId}`, { headers: { Authorization: `Bearer ${token}` } })
  },
  addPermission: (userId, permission) => {
    const token = getToken()
    return api.post(`/users/${userId}/permissions`, permission, { headers: { Authorization: `Bearer ${token}` } })
  },
  removePermission: (userId, permissionId) => {
    const token = getToken()
    return api.delete(`/users/${userId}/permissions/${permissionId}`, { headers: { Authorization: `Bearer ${token}` } })
  },
  bulkUpdatePermissions: (userId, permissions) => {
    const token = getToken()
    return api.put(`/users/${userId}/permissions/bulk`, { permissions }, { headers: { Authorization: `Bearer ${token}` } })
  },
}

// Configs API (Admin)
export const configsApi = {
  list: (params) => {
    const token = getToken()
    return api.get('/configs/', { headers: { Authorization: `Bearer ${token}` }, params })
  },
  get: (configId) => {
    const token = getToken()
    return api.get(`/configs/${configId}`, { headers: { Authorization: `Bearer ${token}` } })
  },
  create: (data) => {
    const token = getToken()
    return api.post('/configs/', data, { headers: { Authorization: `Bearer ${token}` } })
  },
  update: (configId, data) => {
    const token = getToken()
    return api.put(`/configs/${configId}`, data, { headers: { Authorization: `Bearer ${token}` } })
  },
  delete: (configId, hardDelete = false) => {
    const token = getToken()
    return api.delete(`/configs/${configId}`, { headers: { Authorization: `Bearer ${token}` }, params: { hard_delete: hardDelete } })
  },
  duplicate: (configId, validFrom, validTo) => {
    const token = getToken()
    return api.post(`/configs/${configId}/duplicate`, null, { 
      headers: { Authorization: `Bearer ${token}` },
      params: { new_valid_from: validFrom, new_valid_to: validTo } 
    })
  },
}

// Mock Data API (Admin)
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
  download: (filename) => `/api/v1/mock-data/download/${filename}`,
  delete: (filename) => api.delete(`/mock-data/${filename}`),
  getColumns: (partnerCode, serviceCode) => 
    api.get(`/mock-data/columns/${partnerCode}/${serviceCode}`),
}

// ============================================================================
// API V2 - Dynamic Reconciliation System
// ============================================================================

// Create separate axios instance for v2
const apiV2 = axios.create({
  baseURL: '/api/v2',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Use same interceptors as v1
apiV2.interceptors.request.use(
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

apiV2.interceptors.response.use(
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

// V2 Configs API
export const configsApiV2 = {
  list: (params) => apiV2.get('/configs/', { params }),
  get: (configId) => apiV2.get(`/configs/${configId}`),
  create: (data) => apiV2.post('/configs/', data),
  update: (configId, data) => apiV2.patch(`/configs/${configId}`, data),
  delete: (configId) => apiV2.delete(`/configs/${configId}`),
}

// V2 Data Sources API
export const dataSourcesApiV2 = {
  getByConfig: (configId) => apiV2.get(`/data-sources/by-config/${configId}`),
  get: (sourceId) => apiV2.get(`/data-sources/${sourceId}`),
  create: (data) => apiV2.post('/data-sources/', data),
  update: (sourceId, data) => apiV2.patch(`/data-sources/${sourceId}`, data),
  delete: (sourceId) => apiV2.delete(`/data-sources/${sourceId}`),
}

// V2 Workflows API
export const workflowsApiV2 = {
  getByConfig: (configId) => apiV2.get(`/workflows/by-config/${configId}`),
  get: (stepId) => apiV2.get(`/workflows/${stepId}`),
  create: (data) => apiV2.post('/workflows/', data),
  update: (stepId, data) => apiV2.patch(`/workflows/${stepId}`, data),
  delete: (stepId) => apiV2.delete(`/workflows/${stepId}`),
}

// V2 Outputs API
export const outputsApiV2 = {
  getByConfig: (configId) => apiV2.get(`/outputs/by-config/${configId}`),
  get: (outputId) => apiV2.get(`/outputs/${outputId}`),
  create: (data) => apiV2.post('/outputs/', data),
  update: (outputId, data) => apiV2.patch(`/outputs/${outputId}`, data),
  delete: (outputId) => apiV2.delete(`/outputs/${outputId}`),
}

// V2 Reconciliation API
export const reconciliationApiV2 = {
  uploadFiles: (configId, files, sourceNames, onProgress) => {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    formData.append('source_names', sourceNames.join(','))
    return apiV2.post(`/reconciliation/upload-files/${configId}`, formData, {
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
    apiV2.post('/reconciliation/run', requestData, { 
      params: { batch_folder: batchFolder, force_replace: forceReplace } 
    }),
  checkDuplicate: (requestData) =>
    apiV2.post('/reconciliation/check-duplicate', requestData),
  deleteBatch: (batchId) =>
    apiV2.delete(`/reconciliation/batches/${batchId}`),
  listBatches: (params) => {
    const cleanParams = Object.fromEntries(
      Object.entries(params || {}).filter(([_, v]) => v !== '' && v != null)
    )
    return apiV2.get('/reconciliation/batches', { params: cleanParams })
  },
  getBatch: (batchId) => apiV2.get(`/reconciliation/batches/${batchId}`),
  rerunBatch: (batchId) => apiV2.post(`/reconciliation/batches/${batchId}/rerun`),
  getRunLogs: (batchId, runNumber) => apiV2.get(`/reconciliation/batches/${batchId}/runs/${runNumber}/logs`),
}

export default api

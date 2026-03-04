import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import { setAuthToken } from './services/api'

// Layouts
import MainLayout from './layouts/MainLayout'
import AuthLayout from './layouts/AuthLayout'

// Pages
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ReconciliationPage from './pages/ReconciliationPage'
import BatchListPage from './pages/BatchListPage'
import BatchDetailPage from './pages/BatchDetailPage'
import ApprovalsPage from './pages/ApprovalsPage'
import UsersPage from './pages/admin/UsersPage'
import ConfigsPage from './pages/admin/ConfigsPage'
import MockDataPage from './pages/admin/MockDataPage'

// Protected Route Component
function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, user } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  if (adminOnly && !user?.is_admin) {
    return <Navigate to="/" replace />
  }
  
  return children
}

function App() {
  const token = useAuthStore((state) => state.token)
  
  // Sync token to axios when it changes
  useEffect(() => {
    setAuthToken(token)
  }, [token])
  
  return (
    <Routes>
      {/* Auth routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>
      
      {/* Protected routes */}
      <Route element={
        <ProtectedRoute>
          <MainLayout />
        </ProtectedRoute>
      }>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/reconciliation" element={<ReconciliationPage />} />
        <Route path="/batches" element={<BatchListPage />} />
        <Route path="/batches/:batchId" element={<BatchDetailPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        
        {/* Admin routes */}
        <Route path="/admin/users" element={
          <ProtectedRoute adminOnly>
            <UsersPage />
          </ProtectedRoute>
        } />
        <Route path="/admin/configs" element={
          <ProtectedRoute adminOnly>
            <ConfigsPage />
          </ProtectedRoute>
        } />
        <Route path="/admin/mock-data" element={
          <ProtectedRoute adminOnly>
            <MockDataPage />
          </ProtectedRoute>
        } />
      </Route>
      
      {/* 404 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

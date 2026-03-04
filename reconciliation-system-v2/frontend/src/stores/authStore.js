import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import axios from 'axios'

// Direct API calls without using the shared api instance to avoid circular deps
const authAxios = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      
      login: async (email, password) => {
        const response = await authAxios.post('/auth/login', { email, password })
        const { access_token } = response.data
        
        // Set token in state
        set({ token: access_token, isAuthenticated: true })
        
        // Fetch user info with new token
        const userResponse = await authAxios.get('/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` }
        })
        set({ user: userResponse.data })
        
        return userResponse.data
      },
      
      logout: () => {
        set({ user: null, token: null, isAuthenticated: false })
      },
      
      fetchUser: async () => {
        try {
          const token = get().token
          const response = await authAxios.get('/auth/me', {
            headers: { Authorization: `Bearer ${token}` }
          })
          set({ user: response.data })
          return response.data
        } catch (error) {
          get().logout()
          throw error
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        token: state.token, 
        isAuthenticated: state.isAuthenticated,
        user: state.user 
      }),
    }
  )
)

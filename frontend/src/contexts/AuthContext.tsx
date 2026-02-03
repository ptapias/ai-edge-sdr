import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi, User, LoginCredentials, RegisterCredentials } from '../services/authApi'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  register: (credentials: RegisterCredentials) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: React.ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Check for existing auth on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access_token')
      if (token) {
        try {
          const userData = await authApi.getCurrentUser()
          setUser(userData)
        } catch (error) {
          // Token expired or invalid, try to refresh
          const refreshToken = localStorage.getItem('refresh_token')
          if (refreshToken) {
            try {
              const tokens = await authApi.refreshToken(refreshToken)
              localStorage.setItem('access_token', tokens.access_token)
              localStorage.setItem('refresh_token', tokens.refresh_token)
              const userData = await authApi.getCurrentUser()
              setUser(userData)
            } catch {
              // Refresh failed, clear tokens
              localStorage.removeItem('access_token')
              localStorage.removeItem('refresh_token')
            }
          }
        }
      }
      setIsLoading(false)
    }

    initAuth()
  }, [])

  const login = useCallback(async (credentials: LoginCredentials) => {
    const tokens = await authApi.login(credentials)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    const userData = await authApi.getCurrentUser()
    setUser(userData)
  }, [])

  const register = useCallback(async (credentials: RegisterCredentials) => {
    const tokens = await authApi.register(credentials)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    const userData = await authApi.getCurrentUser()
    setUser(userData)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // Ignore logout errors
    }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const userData = await authApi.getCurrentUser()
      setUser(userData)
    } catch {
      // If refresh fails, logout
      await logout()
    }
  }, [logout])

  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export default AuthContext

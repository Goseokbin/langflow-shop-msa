import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { apiClient, User } from '@/lib/api'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is already logged in
    const checkAuth = async () => {
      try {
        if (typeof window !== 'undefined' && apiClient.getToken()) {
          const currentUser: User = await apiClient.getCurrentUser()
          setUser(currentUser)
        } else {
          setUser(null)
        }
      } catch (error) {
        // Not logged in or token expired
        setUser(null)
      } finally {
        setLoading(false)
      }
    }

    checkAuth()
  }, [])

  const login = async (email: string, password: string) => {
    try {
      const response = await apiClient.login(email, password)
      // Get user info after login
      const user = await apiClient.getCurrentUser()
      setUser(user)
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }

  const register = async (email: string, username: string, password: string) => {
    try {
      await apiClient.register(email, password, username)
      await apiClient.login(email, password)
      // Get user info after registration
      const user = await apiClient.getCurrentUser()
      setUser(user)
    } catch (error) {
      console.error('Register error:', error)
      throw error
    }
  }

  const logout = () => {
    apiClient.logout()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

// Made with Bob

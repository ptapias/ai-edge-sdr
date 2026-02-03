import axios from 'axios'

const authClient = axios.create({
  baseURL: '/api/auth',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth header to requests
authClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Types
export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_verified: boolean
  created_at: string
  updated_at: string
  has_linkedin_connected: boolean
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterCredentials {
  email: string
  password: string
  full_name?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LinkedInAccount {
  id: string
  account_name: string | null
  linkedin_profile_url: string | null
  linkedin_email: string | null
  is_connected: boolean
  connection_status: string | null
  connected_at: string | null
  last_sync_at: string | null
}

export interface LinkedInConnectRequest {
  username: string  // LinkedIn email
  password: string  // LinkedIn password
}

export interface LinkedInCheckpointRequest {
  code: string  // 2FA/OTP code
}

export interface LinkedInConnectResponse {
  success: boolean
  connected: boolean
  requires_checkpoint: boolean
  checkpoint_type: string | null
  message: string | null
  account: LinkedInAccount | null
}

// API functions
export const authApi = {
  register: async (credentials: RegisterCredentials): Promise<AuthTokens> => {
    const response = await authClient.post('/register', credentials)
    return response.data
  },

  login: async (credentials: LoginCredentials): Promise<AuthTokens> => {
    const response = await authClient.post('/login', credentials)
    return response.data
  },

  refreshToken: async (refreshToken: string): Promise<AuthTokens> => {
    const response = await authClient.post('/refresh', { refresh_token: refreshToken })
    return response.data
  },

  logout: async (): Promise<void> => {
    await authClient.post('/logout')
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await authClient.get('/me')
    return response.data
  },

  updateUser: async (data: { full_name?: string }): Promise<User> => {
    const response = await authClient.patch('/me', data)
    return response.data
  },

  // LinkedIn Account
  getLinkedInAccount: async (): Promise<LinkedInAccount | null> => {
    const response = await authClient.get('/linkedin')
    return response.data
  },

  connectLinkedIn: async (data: LinkedInConnectRequest): Promise<LinkedInConnectResponse> => {
    const response = await authClient.post('/linkedin/connect', data)
    return response.data
  },

  solveLinkedInCheckpoint: async (data: LinkedInCheckpointRequest): Promise<LinkedInConnectResponse> => {
    const response = await authClient.post('/linkedin/checkpoint', data)
    return response.data
  },

  disconnectLinkedIn: async (): Promise<void> => {
    await authClient.delete('/linkedin/disconnect')
  },
}

export default authApi

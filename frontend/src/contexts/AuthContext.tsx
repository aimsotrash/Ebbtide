import { createContext, useContext, useState, type ReactNode } from 'react'
import { config } from '@/lib/config'
import { storeTokens, clearTokens, getAccessToken, getRefreshToken } from '@/lib/tokens'

export interface User {
  email: string
  name: string
}

interface AuthCtx {
  user: User | null
  login: (email: string, password: string) => Promise<boolean>
  register: (name: string, email: string, password: string) => Promise<string | true>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  login: async () => false,
  register: async () => true,
  logout: async () => {},
})

interface AuthResponse {
  access_token: string
  refresh_token: string
  name: string
  email: string
  expires_in: number
}

function readStoredUser(): User | null {
  try { return JSON.parse(localStorage.getItem('dory-session') ?? 'null') } catch { return null }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser)

  function adoptSession(data: AuthResponse) {
    const session: User = { email: data.email, name: data.name }
    setUser(session)
    localStorage.setItem('dory-session', JSON.stringify(session))
    storeTokens(data.access_token, data.refresh_token)
  }

  async function login(email: string, password: string): Promise<boolean> {
    // Auth is strictly backend-driven. There is no offline/demo bypass that
    // fabricates a session — a "logged in" state must always be backed by a
    // real token (P0 demo-account security: no hidden bypass paths).
    try {
      const res = await fetch(`${config.apiBaseUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!res.ok) return false
      adoptSession(await res.json())
      return true
    } catch {
      return false
    }
  }

  async function register(name: string, email: string, password: string): Promise<string | true> {
    try {
      const res = await fetch(`${config.apiBaseUrl}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        return data.detail ?? 'Registration failed.'
      }
      adoptSession(await res.json())
      return true
    } catch {
      return 'Could not reach the server.'
    }
  }

  async function logout() {
    const refresh = getRefreshToken()
    const access = getAccessToken()
    if (refresh) {
      try {
        await fetch(`${config.apiBaseUrl}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(access ? { Authorization: `Bearer ${access}` } : {}),
          },
          body: JSON.stringify({ refresh_token: refresh }),
        })
      } catch {
        // best-effort; client state is the source of truth on logout
      }
    }
    setUser(null)
    localStorage.removeItem('dory-session')
    clearTokens()
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

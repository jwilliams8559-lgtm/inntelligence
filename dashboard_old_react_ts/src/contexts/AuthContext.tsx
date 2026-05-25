import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import type { FeatureGates, PlanTier } from '../hooks/usePlanFeatures'

interface AuthUser {
  email:         string
  tenant_id:     string
  plan_tier:     PlanTier
  property_name: string
  role:          string
}

interface AuthContextValue {
  user:        AuthUser | null
  features:    FeatureGates | null
  token:       string | null
  isLoading:   boolean
  login:       (email: string, password: string) => Promise<{ ok: boolean; error?: string }>
  logout:      () => void
}

const Ctx = createContext<AuthContextValue>({
  user: null, features: null, token: null, isLoading: true,
  login: async () => ({ ok: false }), logout: () => {},
})

const TOKEN_KEY = 'tgc.auth.token'

// Wrap fetch so every call attaches the Authorization header automatically
const _origFetch = window.fetch.bind(window)
function authFetch(token: string | null) {
  window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    if (token && url.startsWith('/api/') && !url.startsWith('/api/auth/')) {
      const headers = new Headers(init.headers)
      if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
      init = { ...init, headers }
    }
    return _origFetch(input as any, init)
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,     setUser]     = useState<AuthUser | null>(null)
  const [features, setFeatures] = useState<FeatureGates | null>(null)
  const [token,    setToken]    = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => { authFetch(token) }, [token])

  useEffect(() => {
    async function bootstrap() {
      // If we have a token, validate it via /api/auth/me. Otherwise stay loading=false logged-out.
      if (!token) { setIsLoading(false); return }
      try {
        const r = await fetch('/api/auth/me')
        if (!r.ok) { setUser(null); setFeatures(null); setToken(null); localStorage.removeItem(TOKEN_KEY); return }
        const j = await r.json()
        setUser({
          email: j.email, tenant_id: j.tenant_id, plan_tier: j.plan_tier,
          property_name: j.property_name, role: j.role,
        })
        setFeatures(j.features)
      } catch {
        setUser(null); setFeatures(null)
      } finally { setIsLoading(false) }
    }
    void bootstrap()
  }, [])

  async function login(email: string, password: string) {
    try {
      const r = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ error: 'Login failed' }))
        return { ok: false, error: err.error || 'Login failed' }
      }
      const j = await r.json()
      localStorage.setItem(TOKEN_KEY, j.token)
      setToken(j.token)
      setUser({
        email: j.email, tenant_id: j.tenant_id, plan_tier: j.plan_tier,
        property_name: j.property_name, role: j.role,
      })
      setFeatures(j.features)
      return { ok: true }
    } catch (e: any) {
      return { ok: false, error: e?.message || 'Network error' }
    }
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null); setUser(null); setFeatures(null)
  }

  return (
    <Ctx.Provider value={{ user, features, token, isLoading, login, logout }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() { return useContext(Ctx) }

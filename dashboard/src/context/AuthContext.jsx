import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authMe, authLogin, authLogout, authResetPassword, setToken } from '../api/client'

// Auth state for the JSX app. Talks only to the Flask /api/auth/* endpoints,
// which proxy Supabase Auth server-side. When Supabase isn't configured the
// server reports auth_configured:false and we run in "open mode" (local/demo)
// so the dashboard stays usable without a login wall.
const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [loading, setLoading] = useState(true)
  const [authConfigured, setAuthConfigured] = useState(true)
  const [user, setUser] = useState(null)

  const refresh = useCallback(async () => {
    const me = await authMe()
    if (me.auth_configured === false) {
      setAuthConfigured(false); setUser(null)
    } else if (me.authenticated) {
      setAuthConfigured(true); setUser(me)
    } else {
      setAuthConfigured(true); setUser(null)
    }
    setLoading(false)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const login = useCallback(async (email, password) => {
    const j = await authLogin(email, password)
    setToken(j.access_token)
    await refresh()
    return j
  }, [refresh])

  const logout = useCallback(async () => {
    await authLogout()
    setToken('')
    setUser(null)
  }, [])

  const openMode = !authConfigured            // no Supabase → no auth wall
  const role = user?.role || (openMode ? 'tgc_admin' : null)

  return (
    <AuthCtx.Provider value={{ loading, openMode, authConfigured, user, role, login, logout, resetPassword: authResetPassword, refresh }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)

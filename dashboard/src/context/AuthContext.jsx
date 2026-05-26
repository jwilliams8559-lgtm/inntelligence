import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { supabase, supabaseConfigured } from '../lib/supabase'
import { authMe, setToken } from '../api/client'

// Auth for the JSX app.
//  • Real mode (Supabase configured): supabase-js owns the session (persistence
//    + token auto-refresh). The access token carries the custom_access_token_hook
//    claims (app_metadata.app_role, app_metadata.tenant_id). We enrich with the
//    Flask /api/auth/me endpoint (joins tenants/properties, onboarding_complete).
//  • Open mode (no VITE_SUPABASE_* vars): no login wall — local/demo stays usable.
const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState(null)
  const openMode = !supabaseConfigured

  // Enrich the current session via Flask (role/tenant/property/onboarding).
  const loadContext = useCallback(async (accessToken) => {
    setToken(accessToken || '')
    if (!accessToken) { setUser(null); return }
    const me = await authMe()
    setUser(me.authenticated ? me : null)
  }, [])

  useEffect(() => {
    if (openMode) { setLoading(false); return }
    let active = true
    supabase.auth.getSession().then(async ({ data }) => {
      if (!active) return
      await loadContext(data.session?.access_token)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      loadContext(session?.access_token)
    })
    return () => { active = false; sub?.subscription?.unsubscribe() }
  }, [openMode, loadContext])

  const login = useCallback(async (email, password) => {
    if (openMode) return { role: 'tgc_admin' }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw new Error(error.message || 'Invalid email or password.')
    await loadContext(data.session?.access_token)
    const me = await authMe()
    return me.authenticated ? me : { role: 'inn_owner' }
  }, [openMode, loadContext])

  const logout = useCallback(async () => {
    if (!openMode) { try { await supabase.auth.signOut() } catch { /* ignore */ } }
    setToken(''); setUser(null)
  }, [openMode])

  const resetPassword = useCallback(async (email) => {
    if (openMode) return { ok: true }
    try { await supabase.auth.resetPasswordForEmail(email) } catch { /* never reveal */ }
    return { ok: true }
  }, [openMode])

  const role = user?.role || (openMode ? 'tgc_admin' : null)

  return (
    <AuthCtx.Provider value={{ loading, openMode, authConfigured: !openMode, user, role, login, logout, resetPassword }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)

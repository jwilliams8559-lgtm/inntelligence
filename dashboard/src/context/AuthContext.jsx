import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { supabase, supabaseConfigured } from '../lib/supabase'
import { authMe, setToken, demoSession } from '../api/client'

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
  const [demoUser, setDemoUser] = useState(null)
  const openMode = !supabaseConfigured

  // Public read-only demo: mint a signed server session (real token → real API,
  // full feature access, server-enforced read-only) and enter the live app.
  const startDemo = useCallback(async () => {
    try { sessionStorage.setItem('inn_demo', '1') } catch { /* ignore */ }
    try {
      const s = await demoSession()                 // POST /api/demo/session
      setToken(s.access_token || '')
      setDemoUser({ authenticated: true, ...s })
      return s
    } catch {
      // Fall back to a minimal demo identity so the app still opens.
      setToken('')
      const fallback = { authenticated: true, demo: true, read_only: true,
        role: 'demo_viewer', plan_tier: 'collection',
        property_name: 'The Bay Street Inn', owner_name: 'Live Demo' }
      setDemoUser(fallback)
      return fallback
    }
  }, [])
  const exitDemo = useCallback(() => {
    try { sessionStorage.removeItem('inn_demo') } catch { /* ignore */ }
    setToken('')
    setDemoUser(null)
  }, [])

  // Enrich the current session via Flask (role/tenant/property/onboarding).
  const loadContext = useCallback(async (accessToken) => {
    setToken(accessToken || '')
    if (!accessToken) { setUser(null); return }
    const me = await authMe()
    setUser(me.authenticated ? me : null)
  }, [])

  useEffect(() => {
    // A demo session (possibly from a pre-refresh deep link) takes precedence
    // and skips Supabase entirely.
    let isDemo = false
    try { isDemo = sessionStorage.getItem('inn_demo') === '1' } catch { /* ignore */ }
    if (isDemo) { startDemo().finally(() => setLoading(false)); return }
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
  }, [openMode, loadContext, startDemo])

  const login = useCallback(async (email, password) => {
    exitDemo()  // a real sign-in always supersedes a demo session
    if (openMode) return { role: 'tgc_admin' }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw new Error(error.message || 'Invalid email or password.')
    await loadContext(data.session?.access_token)
    const me = await authMe()
    return me.authenticated ? me : { role: 'inn_owner' }
  }, [openMode, loadContext, exitDemo])

  const logout = useCallback(async () => {
    exitDemo()
    if (!openMode) { try { await supabase.auth.signOut() } catch { /* ignore */ } }
    setToken(''); setUser(null)
  }, [openMode, exitDemo])

  const resetPassword = useCallback(async (email) => {
    if (openMode) return { ok: true }
    try { await supabase.auth.resetPasswordForEmail(email) } catch { /* never reveal */ }
    return { ok: true }
  }, [openMode])

  const effectiveUser = demoUser || user
  const role = effectiveUser?.role || (openMode ? 'tgc_admin' : null)

  return (
    <AuthCtx.Provider value={{
      loading, openMode, authConfigured: !openMode,
      user: effectiveUser, role, login, logout, resetPassword,
      demoMode: !!demoUser,
      demoReadOnly: !!(demoUser && (demoUser.read_only || demoUser.demo)),
      startDemo, exitDemo,
    }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)

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

// Synthetic read-only session for the public /demo experience. No Supabase
// login: clearing the API token makes the Flask backend serve the Bay Street
// Inn demo tenant (see modules/auth/auth.py get_current_user fallback), so every
// real screen renders real demo data. Survives refresh via sessionStorage.
const DEMO_USER = {
  authenticated: true, demo: true,
  email: 'demo@graciouscollection.com', owner_name: 'Demo Viewer',
  role: 'inn_owner', tenant_id: 'bay-street-inn-demo',
  plan_tier: 'professional', property_name: 'The Bay Street Inn',
  pending_onboarding: false,
}

export function AuthProvider({ children }) {
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState(null)
  const [demoUser, setDemoUser] = useState(null)
  const openMode = !supabaseConfigured

  const startDemo = useCallback(() => {
    try { sessionStorage.setItem('inn_demo', '1'); sessionStorage.setItem('inn_demo_tour', '1') } catch { /* ignore */ }
    setToken('')            // backend falls back to the Bay Street demo tenant
    setDemoUser(DEMO_USER)
  }, [])
  const exitDemo = useCallback(() => {
    try { sessionStorage.removeItem('inn_demo'); sessionStorage.removeItem('inn_demo_tour') } catch { /* ignore */ }
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
    if (isDemo) { setToken(''); setDemoUser(DEMO_USER); setLoading(false); return }
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
      demoMode: !!demoUser, startDemo, exitDemo,
    }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)

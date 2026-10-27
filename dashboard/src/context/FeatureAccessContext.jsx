import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useAuth } from './AuthContext'
import { getFeatureAccess, startFeatureTrial } from '../api/client'

// Holds the server's authoritative per-feature access + trial snapshot. The
// server is the source of truth; usePlanFeatures reads this and falls back to a
// tier-only computation while it loads (or when unauthenticated / demo mode).
const FeatureAccessContext = createContext(null)

export function FeatureAccessProvider({ children }) {
  const { user, openMode } = useAuth() || {}
  const [snapshot, setSnapshot] = useState(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    // No real backend session (demo / open mode) → skip; hook uses tier fallback.
    if (openMode || !user || user.demo) { setSnapshot(null); return }
    setLoading(true)
    try {
      setSnapshot(await getFeatureAccess())
    } catch {
      setSnapshot(null)
    } finally {
      setLoading(false)
    }
  }, [openMode, user])

  useEffect(() => { refresh() }, [refresh])

  // Start a trial, then refresh so locks/banners update immediately.
  const startTrial = useCallback(async (featureKey) => {
    const res = await startFeatureTrial(featureKey)
    await refresh()
    return res
  }, [refresh])

  return (
    <FeatureAccessContext.Provider value={{ snapshot, loading, refresh, startTrial }}>
      {children}
    </FeatureAccessContext.Provider>
  )
}

export function useFeatureAccess() {
  return useContext(FeatureAccessContext) || { snapshot: null, loading: false, refresh: () => {}, startTrial: async () => ({}) }
}

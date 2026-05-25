import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getDashboard } from '../api/client'

// ─────────────────────────────────────────────────────────────────────────────
//  PriceContext — the ONLY place pricing data is fetched and stored.
//  Every screen reads from here, so any two screens showing the same room rate
//  are reading the identical number from the identical API call. Auto-refreshes
//  every 5 minutes and tracks lastUpdated so no screen ever shows stale data
//  without saying so.
// ─────────────────────────────────────────────────────────────────────────────

const PriceContext = createContext(null)
export const usePrices = () => useContext(PriceContext)

const REFRESH_MS = 5 * 60 * 1000 // 5 minutes

export function PriceProvider({ children }) {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await getDashboard()
      setDashboard(d)
      setLastUpdated(new Date())
    } catch (e) {
      setError(e?.message || 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  const value = {
    dashboard,
    property: dashboard?.property ?? null,
    summary: dashboard?.summary ?? null,
    rates: dashboard?.today_rates ?? [],
    competitors: dashboard?.competitor_comparison ?? null,
    loading,
    error,
    lastUpdated,
    refresh: load,
  }

  return <PriceContext.Provider value={value}>{children}</PriceContext.Provider>
}

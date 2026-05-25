// ─────────────────────────────────────────────────────────────────────────────
//  Flask API client — SINGLE SOURCE OF TRUTH for data access.
//  No screen or component ever calls fetch() directly. They go through these
//  functions, which are in turn driven by PriceContext. All requests hit /api/*
//  which Vite proxies to the Flask backend on :5001 (see vite.config.js).
// ─────────────────────────────────────────────────────────────────────────────

async function _get(url) {
  const r = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!r.ok) throw new Error(`API ${url} → HTTP ${r.status}`)
  return r.json()
}

function _today() {
  return new Date().toISOString().slice(0, 10)
}

// ── Core endpoint ────────────────────────────────────────────────────────────
// The rich dashboard payload: property, summary, today_rates, competitor
// comparison, upcoming events, optimizations. PriceContext fetches this once.
export function getDashboard(date = _today()) {
  return _get(`/api/dashboard?date=${date}`)
}

// ── Derived from the single dashboard round-trip (keeps one source of truth) ──
export async function getRates(date = _today()) {
  return (await getDashboard(date)).today_rates
}
export async function getCompetitors(date = _today()) {
  return (await getDashboard(date)).competitor_comparison
}
export async function getEvents(date = _today()) {
  return (await getDashboard(date)).upcoming_events
}
export async function getGapNights(date = _today()) {
  return (await getDashboard(date)).optimizations
}

// ── Standalone endpoints that already exist on the Flask side ────────────────
export function getPackages() {
  return _get('/api/packages')
}
export function getMarketIntel() {
  return _get('/api/market-intelligence')
}
export function getFnB() {
  return _get('/api/fnb/summary')
}

// ── Endpoints not yet available on the backend ───────────────────────────────
// Stubbed so the contract exists in one place; wired when those screens are
// built. They reject clearly rather than silently returning fake data.
const _notReady = (name) => () =>
  Promise.reject(new Error(`${name}: Flask endpoint not yet available`))
export const getWeather = _notReady('getWeather')
export const getHistorical = _notReady('getHistorical')
export const getReputation = _notReady('getReputation')
export const getROI = _notReady('getROI')

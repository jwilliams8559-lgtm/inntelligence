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
export function togglePackage(id) {
  return fetch(`/api/packages/${encodeURIComponent(id)}/toggle`, { method: 'POST' })
    .then((r) => { if (!r.ok) throw new Error(`toggle failed: HTTP ${r.status}`); return r.json() })
}
export function getMarketIntel() {
  return _get('/api/market-intelligence')
}
export function getFnB() {
  return _get('/api/fnb/summary')
}
export function getROI() {
  return _get('/api/roi')
}
export function getWeather() {
  return _get('/api/weather')
}
export function getHistorical() {
  return _get('/api/historical')
}
export function getReputation() {
  return _get('/api/reputation')
}
export function getGapNight() {
  return _get('/api/gap-night')
}
export function getRevenueIntelligence() {
  return _get('/api/revenue-intelligence')
}
export function getGuests() {
  return _get('/api/guests')
}
export function getGuestProfile(id) {
  return _get(`/api/guests/${encodeURIComponent(id)}`)
}
export function getCrmMeta() {
  return _get('/api/crm/meta')
}
export function getCrmAnalytics() {
  return _get('/api/crm/analytics')
}
export function sendCampaign(payload) {
  return fetch('/api/crm/campaign', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}
export function getGiftShop() {
  return _get('/api/gift-shop')
}
function _send(url, method, body) {
  return fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  }).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
}
export const addGiftCategory  = (b) => _send('/api/gift-shop/category', 'POST', b)
export const updateGiftCategory = (id, b) => _send(`/api/gift-shop/category/${encodeURIComponent(id)}`, 'PUT', b)
export const deleteGiftCategory = (id) => _send(`/api/gift-shop/category/${encodeURIComponent(id)}`, 'DELETE')
export const addGiftItem    = (b) => _send('/api/gift-shop/item', 'POST', b)
export const updateGiftItem = (id, b) => _send(`/api/gift-shop/item/${encodeURIComponent(id)}`, 'PUT', b)
export const deleteGiftItem = (id) => _send(`/api/gift-shop/item/${encodeURIComponent(id)}`, 'DELETE')
export function getRoomRate(roomId, date = _today()) {
  return _get(`/api/room-rate?room_id=${encodeURIComponent(roomId)}&date=${date}`)
}
export function getRateCalendar(days = 30) {
  return _get(`/api/rate-calendar?days=${days}`)
}
export function getCompetitive(tier = 'average', days = 14) {
  return _get(`/api/competitive?tier=${encodeURIComponent(tier)}&days=${days}`)
}
export function getEventsDetail(days = 90) {
  return _get(`/api/events?days=${days}`)
}

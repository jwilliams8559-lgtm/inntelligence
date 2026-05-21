import { useEffect, useState, useCallback } from 'react'

interface Notification {
  id: string; title: string; body: string
  category: string; priority: 'critical' | 'high' | 'medium' | 'low'
  types: string[]
  action_url?: string | null
  data?: Record<string, any>
  created_at: string; expires_at: string
  read: boolean; dismissed: boolean; sound: boolean
}

interface ApiResponse {
  notifications: Notification[]
  badge_count: number
  has_critical: boolean
  has_modal: boolean
}

const DISMISSED_KEY    = 'inn.notif.dismissed'
const PREFS_KEY        = 'inn.notif.prefs'
const MODAL_SHOWN_KEY  = 'inn.notif.modalShown'   // session storage

interface NotifPrefs { push: boolean; modal: boolean; banner: boolean; sound: boolean; badge: boolean }
const DEFAULT_PREFS: NotifPrefs = { push: true, modal: true, banner: true, sound: false, badge: true }

function loadPrefs(): NotifPrefs {
  try { return { ...DEFAULT_PREFS, ...JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') } }
  catch { return DEFAULT_PREFS }
}

function loadDismissedIds(): Set<string> {
  try { return new Set<string>(JSON.parse(localStorage.getItem(DISMISSED_KEY) || '[]')) }
  catch { return new Set() }
}

function saveDismissed(ids: Set<string>) {
  localStorage.setItem(DISMISSED_KEY, JSON.stringify([...ids]))
}

function playChime() {
  try {
    const Ctx = (window.AudioContext || (window as any).webkitAudioContext)
    if (!Ctx) return
    const ctx  = new Ctx()
    const osc  = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.frequency.value = 440
    osc.type = 'sine'
    gain.gain.setValueAtTime(0.25, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.45)
  } catch { /* silent */ }
}

async function setPwaBadge(count: number) {
  try {
    const nav = navigator as any
    if (typeof nav.setAppBadge === 'function') {
      if (count > 0) await nav.setAppBadge(count)
      else           await nav.clearAppBadge()
    }
  } catch { /* unsupported browser */ }
}

export default function NotificationSystem() {
  const [data,    setData]    = useState<ApiResponse | null>(null)
  const [modal,   setModal]   = useState<Notification | null>(null)
  const [banner,  setBanner]  = useState<Notification | null>(null)
  const [prefs,   setPrefs]   = useState<NotifPrefs>(loadPrefs())

  const refresh = useCallback(async () => {
    try {
      const r = await fetch('/api/notifications')
      const j: ApiResponse = await r.json()
      setData(j)
      if (prefs.badge) setPwaBadge(j.badge_count)
    } catch { /* offline */ }
  }, [prefs.badge])

  // Initial fetch + 60s polling
  useEffect(() => {
    void refresh()
    const id = setInterval(refresh, 60_000)
    return () => clearInterval(id)
  }, [refresh])

  // Listen for pref changes (Settings panel writes localStorage)
  useEffect(() => {
    function onPrefs() { setPrefs(loadPrefs()) }
    window.addEventListener('storage', onPrefs)
    window.addEventListener('inn:notif-prefs', onPrefs)
    return () => {
      window.removeEventListener('storage', onPrefs)
      window.removeEventListener('inn:notif-prefs', onPrefs)
    }
  }, [])

  // Trigger modal for first un-dismissed CRITICAL notif this session
  useEffect(() => {
    if (!data || !prefs.modal) return
    const dismissed = loadDismissedIds()
    const sessionShown = sessionStorage.getItem(MODAL_SHOWN_KEY)
    const candidate = data.notifications.find(n =>
      n.priority === 'critical' && n.types.includes('modal') && !dismissed.has(n.id)
    )
    if (candidate && sessionShown !== candidate.category) {
      setModal(candidate)
      sessionStorage.setItem(MODAL_SHOWN_KEY, candidate.category)
      if (prefs.sound && candidate.sound) playChime()
    }
  }, [data, prefs.modal, prefs.sound])

  // Banner queue — show one high/medium banner at a time
  useEffect(() => {
    if (!data || !prefs.banner || banner) return
    const dismissed = loadDismissedIds()
    const candidate = data.notifications.find(n =>
      (n.priority === 'high' || n.priority === 'medium')
      && n.types.includes('banner')
      && !dismissed.has(n.id)
    )
    if (candidate) {
      setBanner(candidate)
      const timeout = candidate.priority === 'high' ? 15_000 : 8_000
      const t = setTimeout(() => setBanner(null), timeout)
      return () => clearTimeout(t)
    }
  }, [data, banner, prefs.banner])

  function dismiss(notif: Notification) {
    const dismissed = loadDismissedIds()
    dismissed.add(notif.id)
    saveDismissed(dismissed)
    fetch(`/api/notifications/${notif.id}/dismiss`, { method: 'POST' }).catch(() => {})
    setModal(null); setBanner(null)
  }

  function navigate(notif: Notification) {
    fetch(`/api/notifications/${notif.id}/read`, { method: 'POST' }).catch(() => {})
    if (notif.action_url) {
      const screenMap: Record<string, string> = {
        '/calendar': 'calendar', '/demand': 'demand', '/events': 'events',
        '/competitive': 'competitive', '/reputation': 'reputation',
        '/performance': 'performance',
      }
      const screen = screenMap[notif.action_url]
      if (screen) window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: screen }))
    }
    setModal(null); setBanner(null)
  }

  return (
    <>
      {modal && prefs.modal && <ModalView notif={modal} onAction={() => navigate(modal)} onDismiss={() => dismiss(modal)} />}
      {banner && prefs.banner && <BannerView notif={banner} onAction={() => navigate(banner)} onDismiss={() => dismiss(banner)} />}
    </>
  )
}

function ModalView({ notif, onAction, onDismiss }: { notif: Notification; onAction: () => void; onDismiss: () => void }) {
  return (
    <div className="fixed inset-0 z-[60] bg-navy/60 flex items-center justify-center p-4 animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="bg-navy text-white px-5 py-2.5 flex items-center justify-between">
          <div className="text-gold font-serif font-bold text-base" style={{ fontFamily: 'Georgia, serif' }}>INNtelligence</div>
          <button onClick={onDismiss} className="text-white/60 hover:text-white text-xl leading-none">×</button>
        </div>
        <div className="px-5 py-5">
          <h2 className="font-bold text-navy text-xl" style={{ fontFamily: 'Georgia, serif' }}>{notif.title}</h2>
          <p className="text-sm text-slate-700 mt-2 leading-relaxed">{notif.body}</p>
          <div className="mt-5 flex items-center justify-between">
            <button onClick={onDismiss} className="text-xs text-slate-400 hover:text-navy">Dismiss for now</button>
            <button onClick={onAction} className="bg-gold text-white text-sm font-bold px-4 py-2 rounded-lg hover:bg-gold-dark">
              Review Now →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function BannerView({ notif, onAction, onDismiss }: { notif: Notification; onAction: () => void; onDismiss: () => void }) {
  const isHigh = notif.priority === 'high'
  return (
    <div className={`fixed top-0 left-0 right-0 z-50 shadow-lg flex items-center px-4 py-2.5 gap-3 ${
      isHigh ? 'bg-navy text-white border-b-2 border-gold' : 'bg-navy-light text-white border-b border-navy'
    }`}>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-sm truncate"><span className="text-gold">{notif.title}</span></div>
        <div className="text-xs text-white/80 truncate">{notif.body}</div>
      </div>
      <button onClick={onAction} className="text-xs font-bold bg-gold text-white px-3 py-1.5 rounded whitespace-nowrap hover:bg-gold-dark">
        Review →
      </button>
      <button onClick={onDismiss} className="text-white/60 hover:text-white text-lg leading-none">×</button>
    </div>
  )
}

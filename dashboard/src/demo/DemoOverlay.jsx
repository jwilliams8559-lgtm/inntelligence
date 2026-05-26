import { useState, useEffect, useRef, useCallback, useLayoutEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { DEMO_STEPS, DEMO_CONTACT_EMAIL } from './demoSteps'

// ── Web Speech fallback (used only if the ElevenLabs MP3 can't load) ──────────
function speakFallback(text) {
  try {
    if (!('speechSynthesis' in window) || !text) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.rate = 0.95
    const v = (window.speechSynthesis.getVoices() || []).find((x) => /en[-_]US/i.test(x.lang))
    if (v) u.voice = v
    window.speechSynthesis.speak(u)
  } catch { /* ignore */ }
}
const stopSpeak = () => { try { window.speechSynthesis.cancel() } catch { /* ignore */ } }

const LAST = DEMO_STEPS.length - 1
const isMobile = () => typeof window !== 'undefined' && window.innerWidth < 768

// ─────────────────────────────────────────────────────────────────────────────
//  DemoOverlay — rides on top of the real dashboard during /demo.
//   • Guided mode: spotlight + coach-mark tooltip walking 7 steps.
//   • Free-explore mode (after finish/skip): a slim banner; tour can be replayed.
// ─────────────────────────────────────────────────────────────────────────────
export default function DemoOverlay() {
  const { demoMode, exitDemo } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [active, setActive] = useState(false)     // guided tour running
  const [idx, setIdx] = useState(0)
  const [rect, setRect] = useState(null)          // spotlight target rect
  const [auto, setAuto] = useState(false)
  const [muted, setMuted] = useState(false)

  const audioRef = useRef(null)
  const cleanupRef = useRef(null)
  const mutedRef = useRef(muted)
  const autoRef = useRef(auto)
  useEffect(() => { mutedRef.current = muted }, [muted])
  useEffect(() => { autoRef.current = auto }, [auto])

  // Start the guided tour once, if /demo flagged it.
  useEffect(() => {
    if (!demoMode) return
    let pending = false
    try { pending = sessionStorage.getItem('inn_demo_tour') === '1' } catch { /* ignore */ }
    if (pending) {
      try { sessionStorage.removeItem('inn_demo_tour') } catch { /* ignore */ }
      setActive(true); setIdx(0)
    }
  }, [demoMode])

  const step = DEMO_STEPS[idx]

  const goNext = useCallback(() => setIdx((i) => Math.min(i + 1, LAST)), [])
  const goPrev = useCallback(() => setIdx((i) => Math.max(i - 1, 0)), [])
  const skipToEnd = useCallback(() => setIdx(LAST), [])
  const finish = useCallback(() => { stopSpeak(); setActive(false); setRect(null) }, [])
  const replay = useCallback(() => { setIdx(0); setActive(true) }, [])

  // Navigate to the step's screen whenever the active step changes.
  useEffect(() => {
    if (!active) return
    const want = step.route
    const here = location.pathname + location.search
    if (here !== want) navigate(want)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx])

  // Locate + track the spotlight target after navigation/data-load settles.
  useEffect(() => {
    if (!active) { setRect(null); return undefined }
    if (!step.target) { setRect(null); return undefined }   // closing card
    let raf = 0, tries = 0, stop = false
    const measure = (el) => {
      const r = el.getBoundingClientRect()
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    }
    const find = () => {
      if (stop) return
      const el = document.querySelector(`[data-tour="${step.target}"]`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' })
        setTimeout(() => !stop && measure(el), 350)
        const onMove = () => { const e2 = document.querySelector(`[data-tour="${step.target}"]`); if (e2) measure(e2) }
        window.addEventListener('scroll', onMove, true)
        window.addEventListener('resize', onMove)
        cleanupRef.current = () => {
          window.removeEventListener('scroll', onMove, true)
          window.removeEventListener('resize', onMove)
        }
        return
      }
      if (tries++ > 50) { setRect(null); return }   // ~6s → graceful center
      raf = window.setTimeout(find, 120)
    }
    find()
    return () => { stop = true; clearTimeout(raf); cleanupRef.current?.(); cleanupRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx, location.pathname, location.search])

  // Narration audio per step (ElevenLabs MP3 with Web Speech fallback).
  useEffect(() => {
    if (!active) return undefined
    stopSpeak()
    const a = new Audio(`/api/tour/audio/${step.id}`)
    a.muted = mutedRef.current
    audioRef.current = a
    const onEnded = () => { if (autoRef.current) goNext() }
    a.addEventListener('ended', onEnded)
    a.play().catch(() => { if (!mutedRef.current) speakFallback(step.text) })
    return () => {
      a.removeEventListener('ended', onEnded)
      try { a.pause() } catch { /* ignore */ }
      audioRef.current = null
      stopSpeak()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx])

  useEffect(() => { if (audioRef.current) audioRef.current.muted = muted; if (muted) stopSpeak() }, [muted])

  if (!demoMode) return null

  // Free-explore banner (tour finished or skipped to explore).
  if (!active) {
    return (
      <div className="fixed bottom-0 inset-x-0 z-[60] bg-navy/95 backdrop-blur border-t border-gold/40 text-white px-4 py-2.5 flex items-center justify-between gap-3 text-sm">
        <div className="min-w-0">
          <span className="text-gold font-semibold">Demo Mode</span>
          <span className="text-white/70 hidden sm:inline"> — The Bay Street Inn, Beaufort SC · explore freely</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={replay} className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs">↺ Replay tour</button>
          <a href={`mailto:${DEMO_CONTACT_EMAIL}?subject=INNtelligence%20Founding%20Member%20Access`}
             className="px-3 py-1.5 rounded-lg bg-gold text-navy font-semibold text-xs hover:bg-gold-light">Request access</a>
          <Link to="/login" onClick={exitDemo} className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs">Sign in</Link>
        </div>
      </div>
    )
  }

  const onClosing = idx === LAST
  return (
    <>
      {!onClosing && <Spotlight rect={rect} />}
      {onClosing
        ? <ClosingCard onExplore={finish} onPrev={goPrev} exitDemo={exitDemo} />
        : <Coachmark
            step={step} idx={idx} rect={rect}
            auto={auto} muted={muted}
            onNext={goNext} onPrev={goPrev} onSkip={skipToEnd}
            onToggleAuto={() => setAuto((a) => !a)} onToggleMute={() => setMuted((m) => !m)} />}
    </>
  )
}

// ── Spotlight: dim the page, cut a glowing hole around the target ─────────────
function Spotlight({ rect }) {
  if (!rect) return <div className="fixed inset-0 z-[55] bg-black/55 pointer-events-none" />
  const pad = 6
  return (
    <div
      className="fixed z-[55] rounded-xl pointer-events-none transition-all duration-300"
      style={{
        top: rect.top - pad, left: rect.left - pad,
        width: rect.width + pad * 2, height: rect.height + pad * 2,
        boxShadow: '0 0 0 9999px rgba(0,0,0,0.55)',
        outline: '3px solid #c9a84c', outlineOffset: 2,
      }}
    />
  )
}

// ── Coachmark tooltip: floats near the target (desktop) or docks bottom (mobile)
function Coachmark({ step, idx, rect, auto, muted, onNext, onPrev, onSkip, onToggleAuto, onToggleMute }) {
  const ref = useRef(null)
  const [pos, setPos] = useState(null)
  const mobile = isMobile()

  useLayoutEffect(() => {
    if (mobile || !rect || !ref.current) { setPos(null); return }
    const vw = window.innerWidth, vh = window.innerHeight
    const w = ref.current.offsetWidth, h = ref.current.offsetHeight
    const gap = 14
    const clampTop = (t) => Math.min(Math.max(12, t), vh - h - 12)
    const clampLeft = (l) => Math.min(Math.max(12, l), vw - w - 12)
    if (rect.top + rect.height + gap + h < vh) {            // below
      setPos({ top: rect.top + rect.height + gap, left: clampLeft(rect.left) })
    } else if (rect.top - h - gap > 12) {                   // above
      setPos({ top: rect.top - h - gap, left: clampLeft(rect.left) })
    } else if (rect.left - w - gap > 12) {                  // left (tall targets)
      setPos({ top: clampTop(rect.top), left: rect.left - w - gap })
    } else if (rect.left + rect.width + w + gap < vw) {     // right
      setPos({ top: clampTop(rect.top), left: rect.left + rect.width + gap })
    } else {
      setPos(null)                                          // center fallback
    }
  }, [rect, mobile, idx])

  const baseCls = mobile
    ? 'fixed z-[60] inset-x-0 bottom-0 rounded-t-2xl'
    : 'fixed z-[60] w-[min(92vw,360px)] rounded-2xl'
  const style = mobile ? {} : (pos ? { top: pos.top, left: pos.left }
    : { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' })

  return (
    <div ref={ref} style={style}
         className={`${baseCls} bg-navy text-white shadow-2xl ring-1 ring-gold/50 p-5`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-gold-light text-[11px] uppercase tracking-wide font-semibold">Step {idx + 1} of {DEMO_STEPS.length}</span>
        <div className="flex items-center gap-1.5">
          {DEMO_STEPS.map((_, i) => (
            <span key={i} className={`h-1.5 rounded-full transition-all ${i === idx ? 'w-5 bg-gold' : 'w-1.5 bg-white/25'}`} />
          ))}
        </div>
      </div>
      <div className="text-gold font-bold text-base">{step.title}</div>
      <p className="text-white/85 text-sm leading-relaxed mt-1.5">{step.text}</p>

      <div className="flex items-center gap-2 mt-4">
        <button onClick={onPrev} disabled={idx === 0}
          className="px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm disabled:opacity-30 disabled:cursor-not-allowed">⏮ Prev</button>
        <button onClick={onNext}
          className="flex-1 px-3 py-2 rounded-lg bg-gold text-navy font-semibold text-sm hover:bg-gold-light">Next ⏭</button>
      </div>
      <div className="flex items-center justify-between mt-3 text-[11px] text-white/55">
        <div className="flex items-center gap-3">
          <button onClick={onToggleAuto} className={auto ? 'text-gold' : 'hover:text-white'}>{auto ? '⏸ Auto-play on' : '▶ Auto-play'}</button>
          <button onClick={onToggleMute} className="hover:text-white">{muted ? '🔇 Muted' : '🔊 Sound'}</button>
        </div>
        <button onClick={onSkip} className="hover:text-white underline">Skip tour</button>
      </div>
    </div>
  )
}

// ── Closing CTA (step 7) ──────────────────────────────────────────────────────
function ClosingCard({ onExplore, onPrev, exitDemo }) {
  const tiers = [
    { name: 'Starter', price: '$399' },
    { name: 'Professional', price: '$699', popular: true },
    { name: 'Enterprise', price: '$1,200' },
    { name: 'Premium', price: '$2,400' },
    { name: 'Founding Member', price: 'FREE', sub: '6 months, then $699/mo' },
  ]
  return (
    <div className="fixed inset-0 z-[60] overflow-y-auto"
         style={{ background: 'radial-gradient(circle at 50% 12%, #14385f, #061629)' }}>
      <div className="min-h-full flex flex-col items-center justify-center text-center px-6 py-12">
        <div className="text-gold font-extrabold tracking-tight text-3xl sm:text-4xl">INNtelligence</div>
        <div className="text-gold-light text-xs uppercase tracking-[0.3em] mt-2">by The Gracious Collection</div>
        <h1 className="text-white text-2xl sm:text-3xl font-bold mt-6 max-w-2xl">Real pricing intelligence for boutique inns.</h1>
        <p className="text-white/70 mt-3 max-w-xl">Starting at $399/month. A limited number of Founding Member slots are available — free for your first 6 months.</p>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 mt-8 w-full max-w-3xl">
          {tiers.map((t) => (
            <div key={t.name} className={`rounded-xl p-3 border ${t.popular ? 'border-gold bg-gold/10' : 'border-white/15 bg-navy/50'}`}>
              <div className="text-gold-light text-[11px] font-semibold uppercase tracking-wide">{t.name}</div>
              <div className="mt-1 text-white"><span className="text-xl font-extrabold">{t.price}</span>{t.price !== 'FREE' && <span className="text-white/40 text-xs">/mo</span>}</div>
              {t.sub && <div className="text-[10px] text-gold-light mt-0.5">{t.sub}</div>}
            </div>
          ))}
        </div>

        <a href={`mailto:${DEMO_CONTACT_EMAIL}?subject=INNtelligence%20Founding%20Member%20Access&body=I%20just%20viewed%20the%20INNtelligence%20demo%20and%20would%20like%20to%20request%20Founding%20Member%20access%20for%20my%20inn.`}
           className="mt-9 inline-block px-9 py-4 rounded-xl bg-gold text-navy font-bold text-lg hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">
          Request Founding Member Access
        </a>
        <div className="text-white/50 text-sm mt-3">{DEMO_CONTACT_EMAIL}</div>

        <div className="flex items-center justify-center gap-3 mt-8 flex-wrap">
          <button onClick={onPrev} className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm text-white/80">⏮ Back</button>
          <button onClick={onExplore} className="px-5 py-2 rounded-lg bg-white/15 hover:bg-white/25 text-sm text-white font-semibold">Explore the dashboard →</button>
          <Link to="/login" onClick={exitDemo} className="px-4 py-2 rounded-lg text-sm text-white/60 hover:text-white underline">Sign in</Link>
        </div>
      </div>
    </div>
  )
}

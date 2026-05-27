import { useState, useEffect, useRef, useCallback, useLayoutEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  DEMO_STEPS, DEMO_CONTACT, DEMO_MAILTO, LAST_INDEX, SCREEN_STEP_COUNT,
} from './demoSteps'

// ── Browser-speech fallback (used when an ElevenLabs MP3 can't load) ──────────
function speak(text) {
  try {
    if (!('speechSynthesis' in window) || !text) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.rate = 0.96
    const v = (window.speechSynthesis.getVoices() || []).find((x) => /en[-_]US/i.test(x.lang))
    if (v) u.voice = v
    window.speechSynthesis.speak(u)
  } catch { /* ignore */ }
}
const stopSpeak = () => { try { window.speechSynthesis.cancel() } catch { /* ignore */ } }
const isMobile = () => typeof window !== 'undefined' && window.innerWidth < 768

// screen-step index → "Step N of 11"
const screenNumber = (idx) => DEMO_STEPS.slice(0, idx + 1).filter((s) => s.kind === 'screen').length

// ─────────────────────────────────────────────────────────────────────────────
//  DemoOverlay — rides on top of the real dashboard for /demo.
// ─────────────────────────────────────────────────────────────────────────────
export default function DemoOverlay() {
  const { demoMode, exitDemo } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [active, setActive] = useState(false)
  const [idx, setIdx] = useState(0)
  const [rect, setRect] = useState(null)
  const [muted, setMuted] = useState(false)
  const [bannerOff, setBannerOff] = useState(false)
  const [openingFade, setOpeningFade] = useState(false)   // crossfade Step 0 → 1
  const [liveRate, setLiveRate] = useState('')            // dynamic rate read from the drawer
  const [subCaption, setSubCaption] = useState('')        // FIX 7: per-screen caption in a multi-screen step
  const [paused, setPaused] = useState(false)
  const [remaining, setRemaining] = useState(0)           // seconds left on this step
  const [stepSecs, setStepSecs] = useState(0)             // total seconds for this step
  const [barReady, setBarReady] = useState(false)         // bar appears 300ms after the step mounts

  const audioRef = useRef(null)
  const cleanupRef = useRef(null)
  const advancedRef = useRef(-1)
  const mutedRef = useRef(muted)
  const pausedRef = useRef(paused)
  useEffect(() => { mutedRef.current = muted }, [muted])
  useEffect(() => { pausedRef.current = paused }, [paused])

  const step = DEMO_STEPS[idx]

  const goNext = useCallback(() => setIdx((i) => Math.min(i + 1, LAST_INDEX)), [])
  const goPrev = useCallback(() => setIdx((i) => Math.max(i - 1, 0)), [])
  const clearStartFlag = () => { try { sessionStorage.removeItem('inn_demo_tour') } catch { /* ignore */ } }
  const skip = useCallback(() => { stopSpeak(); clearStartFlag(); setActive(false); setRect(null) }, [])
  const replay = useCallback(() => { setIdx(0); setActive(true) }, [])
  const advance = useCallback(() => {
    if (advancedRef.current === idx) return
    advancedRef.current = idx
    if (idx === 0) {                       // crossfade the opening out before Step 1
      clearStartFlag()                     // past the intro — don't re-trigger on remount
      setOpeningFade(true)
      setTimeout(() => { setOpeningFade(false); goNext() }, 500)
      return
    }
    goNext()
  }, [idx, goNext])

  // Auto-start the guided tour at Step 0 if /demo flagged it. We do NOT clear the
  // flag here — React.StrictMode double-invokes effects in dev, and consuming the
  // flag on the first pass made the second mount skip the intro (landing on Home).
  // The flag is cleared when the user leaves Step 0 (advance) or skips the tour.
  useEffect(() => {
    if (!demoMode) return
    let pending = false
    try { pending = sessionStorage.getItem('inn_demo_tour') === '1' } catch { /* ignore */ }
    if (pending) { setActive(true); setIdx(0) }
  }, [demoMode])

  // Navigate to the step's screen when the active step changes. Steps with a
  // `sequence` (FIX 7) walk through several screens on timers, updating the
  // caption for each.
  useEffect(() => {
    if (!active) return undefined
    setSubCaption('')
    if (step.sequence) {
      const timers = []
      step.sequence.forEach((seg) => {
        timers.push(window.setTimeout(() => {
          const here = location.pathname + location.search
          if (here !== seg.route) navigate(seg.route)
          setSubCaption(seg.caption || '')
        }, seg.at || 0))
      })
      return () => timers.forEach(clearTimeout)
    }
    if (step.route) {
      const here = location.pathname + location.search
      if (here !== step.route) navigate(step.route)
    }
    return undefined
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx])

  // Locate + track the spotlight target (data-tour id, then CSS selectors).
  useEffect(() => {
    cleanupRef.current?.(); cleanupRef.current = null
    if (!active || step.kind !== 'screen') { setRect(null); return undefined }
    let tries = 0, stop = false, timer = 0
    const queryEl = () => {
      if (step.target) {
        const el = document.querySelector(`[data-tour="${step.target}"]`)
        if (el) return el
      }
      for (const sel of (step.selectors || [])) {
        const el = document.querySelector(sel)
        if (el) return el
      }
      return null
    }
    const measure = (el) => {
      const r = el.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) return
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    }
    const find = () => {
      if (stop) return
      const el = queryEl()
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' })
        setTimeout(() => { if (!stop) measure(el) }, 320)
        const onMove = () => { const e2 = queryEl(); if (e2) measure(e2) }
        window.addEventListener('scroll', onMove, true)
        window.addEventListener('resize', onMove)
        cleanupRef.current = () => {
          window.removeEventListener('scroll', onMove, true)
          window.removeEventListener('resize', onMove)
        }
        return
      }
      if (tries++ > 45) { setRect(null); return }     // graceful: no spotlight
      timer = window.setTimeout(find, 130)
    }
    setRect(null)
    find()
    return () => { stop = true; clearTimeout(timer); cleanupRef.current?.(); cleanupRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx, location.pathname, location.search])

  // Narration audio + countdown auto-advance + progress (per step). A 250ms
  // ticker decrements `remaining` (skipped while paused); the bar fills from it.
  // The closing step does not auto-advance. Step 1 + the opening hold briefly so
  // their content is visible before the bar/narration begin (FIX 1 / FIX 9).
  useEffect(() => {
    if (!active || step.kind === 'closing') { setBarReady(false); return undefined }
    stopSpeak()
    advancedRef.current = -1
    setPaused(false)
    setBarReady(false)
    let secs = step.timer || 18
    setStepSecs(secs); setRemaining(secs)
    let ticker = 0
    let last = 0

    const startTicker = () => {
      last = Date.now()
      ticker = window.setInterval(() => {
        if (pausedRef.current) { last = Date.now(); return }
        const now = Date.now()
        const dt = (now - last) / 1000; last = now
        setRemaining((r) => {
          const nr = r - dt
          if (nr <= 0) { advance(); return 0 }
          return nr
        })
      }, 250)
    }

    const kickoff = () => {
      setBarReady(true)
      if (!mutedRef.current) {
        const a = new Audio(`/api/demo/audio/${step.id}`)
        audioRef.current = a
        a.muted = mutedRef.current
        a.addEventListener('loadedmetadata', () => {
          if (isFinite(a.duration) && a.duration > 1) {
            secs = a.duration + 0.6; setStepSecs(secs); setRemaining(secs)
          }
        })
        a.addEventListener('ended', advance)
        a.play().catch(() => {
          fetch(`/api/demo/narration/${step.id}`)
            .then((r) => r.json()).then((d) => { if (!mutedRef.current && !pausedRef.current) speak(d.text) })
            .catch(() => {})
        })
      }
      startTicker()
    }

    const startDelay = idx === 1 ? 600 : idx === 0 ? 300 : 200  // let content mount first
    const kickTimer = window.setTimeout(kickoff, startDelay)

    return () => {
      clearTimeout(kickTimer); clearInterval(ticker)
      const a = audioRef.current
      if (a) { try { a.pause() } catch { /* ignore */ } a.removeEventListener('ended', advance) }
      audioRef.current = null
      stopSpeak()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx])

  // Pause/resume the narration audio with the countdown.
  useEffect(() => {
    const a = audioRef.current
    if (!a) { if (paused) stopSpeak(); return }
    if (paused) { try { a.pause() } catch { /* ignore */ } }
    else if (!mutedRef.current) { a.play().catch(() => {}) }
  }, [paused])

  // FIX 3b: read the recommended rate live from the open drawer so the Step 3
  // tooltip always matches the screen (no hardcoded dollar amount).
  useEffect(() => {
    if (!active || !step.dynamicRate) { setLiveRate(''); return undefined }
    let stop = false, t = 0, tries = 0
    const poll = () => {
      if (stop) return
      const el = document.querySelector('[data-demo-rate]')
      const txt = el && el.textContent && el.textContent.trim()
      if (txt) { setLiveRate(txt); return }
      if (tries++ > 40) return
      t = window.setTimeout(poll, 200)
    }
    poll()
    return () => { stop = true; clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx])

  useEffect(() => {
    if (audioRef.current) audioRef.current.muted = muted
    if (muted) stopSpeak()
  }, [muted])

  // Step 11: auto-trigger the Approve All animation, then advance to closing
  // when it signals completion.
  useEffect(() => {
    if (!active || step.target !== 'approve-all') return undefined
    const onDone = () => advance()
    window.addEventListener('inn-demo-approve-done', onDone)
    const t = window.setTimeout(() => {
      const btn = document.querySelector('[data-tour="approve-all"]')
      if (btn) btn.click()
    }, 8000)
    return () => { window.removeEventListener('inn-demo-approve-done', onDone); clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, idx])

  if (!demoMode) return null

  const banner = !bannerOff && (
    <div className="fixed top-0 inset-x-0 z-[65] bg-gold text-navy px-4 py-2 flex items-center justify-between gap-3 text-sm font-medium shadow">
      <div className="min-w-0 truncate">
        <span className="font-bold">Demo Mode</span>
        <span className="hidden sm:inline"> — The Bay Street Inn, Beaufort SC — Request access to see YOUR property's data</span>
        <span className="sm:hidden"> — Bay Street Inn</span>
      </div>
      <button onClick={() => setBannerOff(true)} aria-label="Dismiss banner"
        className="shrink-0 w-6 h-6 rounded-full hover:bg-navy/10 flex items-center justify-center font-bold">✕</button>
    </div>
  )

  // Free exploration (tour finished or skipped).
  if (!active) {
    return (
      <>
        {banner}
        <a href={DEMO_MAILTO}
          className="fixed bottom-5 right-5 z-[60] px-5 py-3 rounded-xl bg-gold text-navy font-bold shadow-lg shadow-gold/30 hover:bg-gold-light text-sm">
          Request Founding Member Access
        </a>
        <button onClick={replay}
          className="fixed bottom-5 left-5 z-[60] px-4 py-2.5 rounded-xl bg-navy/90 text-white text-xs hover:bg-navy">↺ Replay tour</button>
      </>
    )
  }

  const pct = stepSecs > 0 ? Math.min(100, Math.max(0, (1 - remaining / stepSecs) * 100)) : 0
  const bottomBar = barReady && step.kind !== 'closing' && (
    <BottomBar pct={pct} remaining={remaining} paused={paused} onTogglePause={() => setPaused((p) => !p)} />
  )

  if (step.kind === 'opening') return <>{banner}<Opening fading={openingFade} onSkip={skip} onNext={advance} muted={muted} onMute={() => setMuted((m) => !m)} />{bottomBar}</>
  if (step.kind === 'closing') return <>{banner}<Closing onReplay={replay} onExplore={skip} exitDemo={exitDemo} /></>

  return (
    <>
      {banner}
      <Spotlight rect={rect} />
      <Coachmark
        step={step} idx={idx} rect={rect} muted={muted} liveRate={liveRate} caption={subCaption || step.caption}
        onNext={advance} onPrev={goPrev} onSkip={skip} onMute={() => setMuted((m) => !m)} />
      {bottomBar}
    </>
  )
}

// ── Bottom auto-advance bar (full width, gold, with countdown + pause) ────────
function BottomBar({ pct, remaining, paused, onTogglePause }) {
  return (
    <div className="fixed bottom-0 inset-x-0 z-[62]">
      <div className="h-1.5 bg-navy/30">
        <div className="h-full bg-gold" style={{ width: `${pct}%`, transition: 'width 0.25s linear' }} />
      </div>
      <div className="bg-navy/90 backdrop-blur text-white/90 px-4 py-1.5 flex items-center justify-center gap-3 text-xs">
        <span>{paused ? 'Paused — read at your own pace' : `Auto-advancing in ${Math.max(0, Math.ceil(remaining))}s`}</span>
        <button onClick={onTogglePause} className="px-3 py-1 rounded-md bg-white/15 hover:bg-white/25 font-semibold">
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
      </div>
    </div>
  )
}

// ── Spotlight ─────────────────────────────────────────────────────────────────
function Spotlight({ rect }) {
  if (!rect) return <div className="fixed inset-0 z-[55] bg-black/60 pointer-events-none" />
  const pad = 6
  return (
    <div className="fixed z-[55] rounded-xl pointer-events-none transition-all duration-300"
      style={{
        top: rect.top - pad, left: rect.left - pad,
        width: rect.width + pad * 2, height: rect.height + pad * 2,
        boxShadow: '0 0 0 9999px rgba(0,0,0,0.6)', outline: '3px solid #c9a84c', outlineOffset: 2,
      }} />
  )
}

// ── Coachmark tooltip (gold card, navy text) ──────────────────────────────────
function Coachmark({ step, idx, rect, muted, liveRate, caption, onNext, onPrev, onSkip, onMute }) {
  const ref = useRef(null)
  const [pos, setPos] = useState(null)
  const mobile = isMobile()

  useLayoutEffect(() => {
    if (mobile || !rect || !ref.current) { setPos(null); return }
    const vw = window.innerWidth, vh = window.innerHeight, gap = 14
    const w = ref.current.offsetWidth, h = ref.current.offsetHeight
    const cT = (t) => Math.min(Math.max(12, t), vh - h - 12)
    const cL = (l) => Math.min(Math.max(12, l), vw - w - 12)
    if (rect.top + rect.height + gap + h < vh) setPos({ top: rect.top + rect.height + gap, left: cL(rect.left) })          // below
    else if (rect.top - h - gap > 12) setPos({ top: rect.top - h - gap, left: cL(rect.left) })                            // above
    else if (rect.left + rect.width + w + gap < vw) setPos({ top: cT(rect.top), left: rect.left + rect.width + gap })     // right
    else if (rect.left - w - gap > 12) setPos({ top: cT(rect.top), left: rect.left - w - gap })                           // left
    else setPos(null)                                                                                                     // center
  }, [rect, mobile, idx])

  const base = mobile
    ? 'fixed z-[60] inset-x-0 bottom-0 rounded-t-2xl pb-6'
    : 'fixed z-[60] w-[min(94vw,380px)] rounded-2xl'
  const style = mobile ? {} : (pos ? { top: pos.top, left: pos.left } : { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' })

  return (
    <div ref={ref} style={style} className={`${base} bg-gold text-navy shadow-2xl ring-2 ring-navy/20`}>
      {mobile && <div className="mx-auto mt-2 h-1.5 w-10 rounded-full bg-navy/25" />}
      <div className="p-5">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] uppercase tracking-wide font-bold text-navy/70">Step {screenNumber(idx)} of {SCREEN_STEP_COUNT}</span>
          <button onClick={onSkip} className="text-[11px] font-semibold text-navy/70 hover:text-navy underline">Skip Tour</button>
        </div>
        <div className="font-extrabold text-lg leading-tight">{step.title}</div>
        {/* dark scrim behind text for guaranteed contrast */}
        <div className="mt-2 rounded-lg bg-navy text-white/95 p-3 text-[15px] sm:text-sm leading-relaxed" style={{ fontSize: mobile ? 16 : undefined }}>
          {step.dynamicRate && liveRate && (
            <span className="block font-bold text-gold mb-1">INNtelligence is recommending {liveRate}</span>
          )}
          {caption}
          {step.badge && (
            <span className="block mt-2 text-gold italic text-[13px]" style={{ fontSize: mobile ? 14 : undefined }}>{step.badge}</span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-3">
          <button onClick={onPrev} disabled={idx === 0}
            className="px-3 py-2 rounded-lg bg-navy/10 hover:bg-navy/20 text-sm font-semibold disabled:opacity-30">⏮ Prev</button>
          <button onClick={onNext} className="flex-1 px-3 py-2 rounded-lg bg-navy text-white font-semibold text-sm hover:bg-navy-light">Next ⏭</button>
          <button onClick={onMute} aria-label="Mute" className="px-3 py-2 rounded-lg bg-navy/10 hover:bg-navy/20 text-sm">{muted ? '🔇' : '🔊'}</button>
        </div>
      </div>
    </div>
  )
}

// ── Step 0 — Opening (founder intro) ──────────────────────────────────────────
function Opening({ fading, onSkip, onNext, muted, onMute }) {
  return (
    <div className={`fixed inset-0 z-[60] overflow-y-auto transition-opacity duration-500 ${fading ? 'opacity-0' : 'opacity-100'}`}
      style={{ background: 'radial-gradient(circle at 50% 15%, #14385f, #061629)' }}>
      <button onClick={onSkip} className="absolute top-3 right-4 z-10 text-white/70 hover:text-white text-sm underline">Skip Tour →</button>
      <div className="min-h-full flex flex-col items-center justify-center px-6 py-14 text-center">
        <div className="text-gold font-extrabold tracking-tight text-3xl sm:text-4xl">INNtelligence</div>
        <div className="grid sm:grid-cols-[auto_1fr] items-center gap-6 mt-10 max-w-2xl text-left">
          <div className="w-28 h-28 rounded-full bg-gold text-navy flex items-center justify-center text-4xl font-extrabold mx-auto shadow-lg shadow-gold/30">JW</div>
          <div>
            <div className="text-white text-2xl font-bold">Jim Williams</div>
            <div className="text-gold mt-0.5">Director of Pricing, Cox Communications</div>
            <div className="text-white/60 text-sm mt-2">11 Years Enterprise Pricing Strategy</div>
            <div className="text-white/60 text-sm">MBA, University of South Florida</div>
            <div className="text-white/60 text-sm">BA Economics, Duke University</div>
          </div>
        </div>
        <div className="w-40 h-px bg-gold/60 my-9" />
        <div className="text-white/90 text-lg font-semibold">Demonstrating with The Bay Street Inn</div>
        <div className="text-gold-light text-sm mt-1">Beaufort, South Carolina — Waterfront Boutique Inn</div>

        <div className="flex items-center justify-center gap-3 mt-10">
          <button onClick={onMute} className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm text-white">{muted ? '🔇 Muted' : '🔊 Sound'}</button>
          <button onClick={onNext} className="px-6 py-2 rounded-lg bg-gold text-navy font-bold text-sm hover:bg-gold-light">Begin →</button>
        </div>
      </div>
    </div>
  )
}

// ── Closing — full screen CTA ─────────────────────────────────────────────────
function Closing({ onReplay, onExplore, exitDemo }) {
  const cards = [
    { t: 'Founding Member Program', lines: ['3–5 Founding Member Slots Available', 'Professional Tier — FREE for 6 months', '$699/month after founding period', 'You shape what INNtelligence becomes'] },
    { t: 'The ROI Math', lines: ['$93,500 total annual revenue lift', '$8,388 annual subscription', '11.1x total return on investment', 'Across rooms, direct bookings, CRM, packages, and F&B'] },
    { t: 'What We Ask', lines: ['Connect your PMS', 'Monthly 30-minute feedback calls', 'Honest testimonial at 90 days', 'Help shape the product roadmap'] },
    { t: 'Ready to Connect — Right Now', lines: [
      'Already integrated with your existing systems',
      'PMS: ResNexus · Cloudbeds · ThinkReservations',
      'Guesty · WebRezPro · Little Hotelier',
      'OTAs: Booking.com · Expedia · Airbnb · VRBO',
      'Hotels.com · Trip.com · Agoda',
      'Connect in minutes. Go live today.',
    ], goldLast: true },
    { t: `Contact ${DEMO_CONTACT.name}`, lines: ['Jim Williams — Founder', DEMO_CONTACT.phone, DEMO_CONTACT.email, 'I personally respond within 24 hours'], bigIndex: 1 },
  ]
  return (
    <div className="fixed inset-0 z-[60] overflow-y-auto" style={{ background: 'radial-gradient(circle at 50% 10%, #14385f, #061629)' }}>
      <div className="min-h-full flex flex-col items-center px-6 py-12 text-center">
        <div className="text-gold font-extrabold tracking-tight text-3xl sm:text-4xl">INNtelligence</div>
        <div className="text-gold-light text-sm mt-1">Boutique Hospitality Intelligence</div>
        <div className="text-white/50 text-xs">by The Gracious Collection</div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-8 w-full max-w-5xl text-left">
          {cards.map((c) => (
            <div key={c.t} className="rounded-2xl border border-gold/30 bg-navy/50 p-4">
              <div className="text-gold-light text-xs font-bold uppercase tracking-wide">{c.t}</div>
              <div className="mt-2 space-y-1">
                {c.lines.map((l, i) => {
                  const isBig = c.bigIndex === i
                  const isGold = c.goldLast && i === c.lines.length - 1
                  const cls = isBig ? 'text-white text-2xl font-extrabold'
                    : isGold ? 'text-gold font-bold text-[13px] pt-1'
                    : 'text-white/75 text-[13px]'
                  return <div key={i} className={cls}>{l}</div>
                })}
              </div>
            </div>
          ))}
        </div>

        <a href={DEMO_MAILTO}
          className="mt-9 inline-block px-9 py-4 rounded-xl bg-gold text-navy font-bold text-lg hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">
          Request Founding Member Access
        </a>
        <div className="text-white/50 text-sm mt-3">I personally respond to every request within 24 hours — Jim Williams</div>

        <div className="flex items-center justify-center gap-3 mt-8 flex-wrap">
          <button onClick={onExplore} className="px-5 py-2 rounded-lg bg-white/15 hover:bg-white/25 text-sm text-white font-semibold">Explore the dashboard →</button>
          <button onClick={onReplay} className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm text-white/80">↺ Replay tour</button>
          <Link to="/login" onClick={exitDemo} className="px-4 py-2 rounded-lg text-sm text-white/60 hover:text-white underline">Sign in</Link>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { AuthProvider } from '../contexts/AuthContext'
import AppInner from './AppShell'
import { DEMO_STEPS } from './demoScript'
import SpotlightOverlay from './SpotlightOverlay'
import DemoControls from './DemoControls'
import { NarrationEngine } from './NarrationEngine'
import AnimatedCursor from './AnimatedCursor'

type Phase = 'entry' | 'running' | 'finished'

const DEMO_EMAIL    = 'demo@graciouscollection.com'
const DEMO_PASSWORD = 'demo2026'
const TOKEN_KEY     = 'tgc.auth.token'

/** Top-level demo route. Three phases:
 *    entry    full-screen splash with [Start Demo]
 *    running  AuthProvider+AppInner renders the actual app underneath
 *             a SpotlightOverlay; controls + narration drive the tour.
 *             On action steps, an AnimatedCursor self-drives the click —
 *             the viewer just watches.
 *    finished completion CTA modal
 */
export default function DemoMode() {
  const [phase,   setPhase]   = useState<Phase>('entry')
  const [stepIdx, setStepIdx] = useState(0)
  const [muted,   setMuted]   = useState(false)
  const [paused,  setPaused]  = useState(false)
  const narrationRef = useRef(new NarrationEngine())

  // Auto-login as the demo professional user so the app renders the
  // Bay Street Inn dashboard under the spotlight.
  useEffect(() => {
    if (phase !== 'running') return
    const existing = localStorage.getItem(TOKEN_KEY)
    if (!existing) {
      fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
      }).then(r => r.json()).then(j => {
        if (j.token) {
          localStorage.setItem(TOKEN_KEY, j.token)
          window.dispatchEvent(new Event('inn:auth-refresh'))
        }
      }).catch(() => {})
    }
  }, [phase])

  const step = DEMO_STEPS[stepIdx]

  // On Rate Calendar steps (1 & 2), scroll the calendar grid so the
  // gold Water Festival cells (July 17-26) are immediately visible.
  // The festival header carries data-tour="rate-cell-festival"; we
  // smooth-scroll its column into view inside the calendar's overflow
  // container. Retries because the grid takes a moment to mount.
  useEffect(() => {
    if (phase !== 'running' || !step) return
    if (stepIdx !== 0 && stepIdx !== 1) return
    if (step.screen !== 'calendar') return

    let cancelled = false
    function scrollToFestival(attempt = 0) {
      if (cancelled) return
      const cell = document.querySelector('[data-tour="rate-cell-festival"]') as HTMLElement | null
      if (cell) {
        cell.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
        return
      }
      if (attempt < 25) setTimeout(() => scrollToFestival(attempt + 1), 200)
    }
    const t = setTimeout(() => scrollToFestival(), 800)
    return () => { cancelled = true; clearTimeout(t) }
  }, [stepIdx, phase, step?.screen])

  // Drive screen navigation + narration when step changes. Every step
  // auto-advances when audio ends — the AnimatedCursor handles the
  // simulated click partway through, but does not control advance.
  useEffect(() => {
    if (phase !== 'running' || !step) return
    window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: step.screen }))
    if (paused) return
    if (muted) return
    const t = setTimeout(() => {
      narrationRef.current.speak({
        stepId: step.id,
        text:   step.narration,
        onEnd:  () => {
          if (paused || muted) return
          advance()
        },
      })
    }, 600)
    return () => {
      clearTimeout(t)
      narrationRef.current.cancel()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIdx, phase, paused, muted])

  function start() { setPhase('running'); setStepIdx(0); setPaused(false) }
  function advance() {
    narrationRef.current.cancel()
    if (stepIdx < DEMO_STEPS.length - 1) setStepIdx(stepIdx + 1)
    else                                 setPhase('finished')
  }
  function back() {
    narrationRef.current.cancel()
    if (stepIdx > 0) setStepIdx(stepIdx - 1)
  }
  function togglePause() {
    setPaused(p => {
      if (!p) narrationRef.current.cancel()
      return !p
    })
  }
  function toggleMute() {
    setMuted(m => {
      if (!m) narrationRef.current.cancel()
      return !m
    })
  }
  function exit() {
    narrationRef.current.cancel()
    window.location.href = '/'
  }

  if (phase === 'entry') return <EntryScreen onStart={start} />

  if (phase === 'finished') return <FinishedScreen onRestart={start} />

  return (
    <AuthProvider>
      <AppInner />

      {/* Top gold demo banner */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9002,
        background: '#A07830', color: '#1A3A5C',
        padding: '6px 16px', fontSize: 13, fontWeight: 700,
        textAlign: 'center', fontFamily: 'Inter, system-ui, sans-serif',
        letterSpacing: '0.5px',
      }}>
        DEMO MODE — Bay Street Inn, Beaufort SC
        <button onClick={exit} style={{
          position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
          background: 'rgba(26,58,92,0.15)', border: '1px solid rgba(26,58,92,0.4)',
          color: '#1A3A5C', padding: '2px 10px', borderRadius: 4, fontSize: 12,
          cursor: 'pointer',
        }}>Exit Demo</button>
      </div>

      <SpotlightOverlay
        selector={step?.spotlightSelector || ''}
        active={phase === 'running'}
      />

      {muted && step && (
        <div style={{
          position: 'fixed', bottom: 88, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.85)', color: 'white',
          padding: '12px 24px', borderRadius: 8, maxWidth: 760,
          fontSize: 14, lineHeight: 1.55, zIndex: 9003, textAlign: 'center',
          fontFamily: 'Inter, system-ui',
        }}>{step.narration}</div>
      )}

      {/* Self-driving gold cursor. Remounts per step via key so the
          animation restarts from screen center each time. */}
      {step?.action && !paused && (
        <AnimatedCursor
          key={`cursor-${stepIdx}`}
          active={phase === 'running'}
          targetSelector={step.action.targetSelector}
          delayMs={step.action.delayMs}
        />
      )}

      <DemoControls
        currentStep={stepIdx}
        totalSteps={DEMO_STEPS.length}
        paused={paused}
        muted={muted}
        title={step?.title || ''}
        onPrev={back}
        onNext={advance}
        onTogglePause={togglePause}
        onToggleMute={toggleMute}
        onExit={exit}
      />
    </AuthProvider>
  )
}

function EntryScreen({ onStart }: { onStart: () => void }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 10000,
      background: 'linear-gradient(135deg, #1A3A5C 0%, #0F2744 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Inter, system-ui, sans-serif', padding: 24,
    }}>
      <div style={{ textAlign: 'center', maxWidth: 560 }}>
        <div style={{
          fontFamily: 'Playfair Display, Georgia, serif',
          fontSize: 64, fontWeight: 700, color: '#A07830', marginBottom: 8, lineHeight: 1.1,
        }}>INNtelligence</div>
        <div style={{ color: '#9CA3AF', fontSize: 14, marginBottom: 40 }}>by The Gracious Collection</div>
        <div style={{ fontSize: 22, color: 'white', fontWeight: 600, marginBottom: 12 }}>
          22-Minute Guided Demo
        </div>
        <div style={{ fontSize: 16, color: '#9CA3AF', marginBottom: 48, lineHeight: 1.5 }}>
          See how Bay Street Inn — a 19-room historic boutique property on
          Beaufort's Bay Street — manages pricing, restaurant yield, guest
          relationships, and revenue with INNtelligence.
        </div>
        <button onClick={onStart} style={{
          background: '#A07830', color: '#1A3A5C', border: 'none',
          padding: '18px 48px', borderRadius: 8, fontSize: 18,
          fontWeight: 700, cursor: 'pointer', display: 'block', width: '100%',
          fontFamily: 'Playfair Display, Georgia, serif', marginBottom: 12,
        }}>▶ Start Demo</button>
        <a href="/" style={{ display: 'block', color: '#9CA3AF', fontSize: 14, textDecoration: 'none', padding: 12 }}>
          Skip — show me the app
        </a>
        <div style={{ marginTop: 24, fontSize: 12, color: '#6B7280' }}>
          Enable sound for the best experience. Works with captions when muted.
        </div>
      </div>
    </div>
  )
}

function FinishedScreen({ onRestart }: { onRestart: () => void }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 10000,
      background: 'rgba(0,0,0,0.85)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <div style={{ background: 'white', borderRadius: 16, padding: 40, maxWidth: 520, width: '100%', textAlign: 'center' }}>
        <div style={{ fontFamily: 'Playfair Display, Georgia, serif', fontSize: 28, color: '#1A3A5C', marginBottom: 12, fontWeight: 700 }}>
          Ready to see INNtelligence on your property?
        </div>
        <p style={{ color: '#6B7280', marginBottom: 28 }}>14-day free trial. No credit card. Cancel anytime.</p>
        <a href="/pricing" style={{
          display: 'block', background: '#A07830', color: 'white', textDecoration: 'none',
          padding: 16, borderRadius: 8, fontWeight: 700, fontSize: 18, marginBottom: 10,
          fontFamily: 'Playfair Display, Georgia, serif',
        }}>Start My Free Trial</a>
        <a href="mailto:jim@graciouscollection.com?subject=INNtelligence Demo - I want to learn more"
           style={{ display: 'block', color: '#1A3A5C', fontSize: 14, textDecoration: 'none', padding: 12, border: '1px solid #E8E4DC', borderRadius: 8 }}>
          Schedule a Call with Jim
        </a>
        <button onClick={onRestart} style={{ background: 'none', border: 'none', color: '#9CA3AF', fontSize: 13, cursor: 'pointer', marginTop: 16 }}>
          Watch demo again
        </button>
      </div>
    </div>
  )
}

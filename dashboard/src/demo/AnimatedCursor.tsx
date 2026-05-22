import { useEffect, useRef, useState } from 'react'

interface Props {
  /** True when this cursor should run. Re-mounting via key={stepIdx} restarts the animation. */
  active: boolean
  /** CSS selector for the element to click. The cursor animates to the element's center. */
  targetSelector: string
  /** Delay (ms) from mount before the cursor begins moving from screen center. */
  delayMs: number
}

type Phase = 'idle' | 'visible' | 'moving' | 'pausing' | 'clicking' | 'done'

const MOVE_MS  = 1200
const PAUSE_MS = 800
const FADE_MS  = 350

/**
 * Self-driving gold cursor. Mounts at screen center, waits `delayMs`,
 * animates to the target element, pauses, dispatches a click, then fades.
 * Uses element.click() (DOM API) so the React handler on the element fires
 * exactly as if a real user had clicked it.
 *
 * State machine:
 *   idle      → not rendered
 *   visible   → rendered at center, no transition (one frame, primes the move)
 *   moving    → transform → target with 1.2s ease-out transition
 *   pausing   → at target, pulse ring visible
 *   clicking  → element.click() fired, opacity fading
 *   done      → not rendered
 */
export default function AnimatedCursor({ active, targetSelector, delayMs }: Props) {
  const [phase, setPhase] = useState<Phase>('idle')
  const center = useRef({
    x: typeof window !== 'undefined' ? window.innerWidth  / 2 : 720,
    y: typeof window !== 'undefined' ? window.innerHeight / 2 : 450,
  })
  const [pos, setPos] = useState(center.current)

  useEffect(() => {
    if (!active) return
    let cancelled = false
    const timers: number[] = []

    function tryStart(attempts = 0) {
      if (cancelled) return
      const el = document.querySelector(targetSelector) as HTMLElement | null
      if (!el) {
        if (attempts < 25) {
          timers.push(window.setTimeout(() => tryStart(attempts + 1), 200))
        } else {
          setPhase('done')
        }
        return
      }

      // 1. Become visible at screen center (no transition on this paint).
      setPos(center.current)
      setPhase('visible')

      // 2. Double-RAF so the browser commits the centered paint, then
      //    transition transform to the target's center.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (cancelled) return
        const rect = el.getBoundingClientRect()
        setPos({
          x: rect.left + rect.width  / 2,
          y: rect.top  + rect.height / 2,
        })
        setPhase('moving')

        timers.push(window.setTimeout(() => {
          if (cancelled) return
          setPhase('pausing')
        }, MOVE_MS))

        timers.push(window.setTimeout(() => {
          if (cancelled) return
          try { el.click() } catch { /* unmounted */ }
          setPhase('clicking')
        }, MOVE_MS + PAUSE_MS))

        timers.push(window.setTimeout(() => {
          if (cancelled) return
          setPhase('done')
        }, MOVE_MS + PAUSE_MS + FADE_MS))
      }))
    }

    timers.push(window.setTimeout(() => tryStart(0), delayMs))
    return () => {
      cancelled = true
      timers.forEach(clearTimeout)
    }
  }, [active, targetSelector, delayMs])

  if (!active || phase === 'idle' || phase === 'done') return null

  const transition =
    phase === 'visible'
      ? 'none'
      : phase === 'moving'
        ? `transform ${MOVE_MS}ms cubic-bezier(0.4, 0.0, 0.2, 1)`
        : phase === 'clicking'
          ? `opacity ${FADE_MS}ms ease-out`
          : 'none'

  return (
    <div
      aria-hidden
      style={{
        position: 'fixed',
        left: 0, top: 0,
        transform: `translate(${pos.x - 12}px, ${pos.y - 12}px)`,
        transition,
        opacity: phase === 'clicking' ? 0 : 1,
        pointerEvents: 'none',
        zIndex: 9999,
        willChange: 'transform, opacity',
      }}
    >
      <div style={{
        width: 24, height: 24, borderRadius: '50%',
        background: '#A07830',
        boxShadow: '0 4px 14px rgba(160,120,48,0.55), 0 0 0 3px rgba(255,255,255,0.85)',
        position: 'relative',
      }}>
        <svg width="14" height="14" viewBox="0 0 14 14" style={{
          position: 'absolute', right: -7, bottom: -7,
          filter: 'drop-shadow(0 2px 3px rgba(0,0,0,0.25))',
        }}>
          <polygon points="0,0 12,4 4,12" fill="#A07830" />
        </svg>
        {phase === 'pausing' && (
          <div style={{
            position: 'absolute', inset: -6,
            border: '2px solid #A07830',
            borderRadius: '50%',
            opacity: 0.7,
            animation: 'inn-cursor-ring 0.8s ease-out',
            pointerEvents: 'none',
          }} />
        )}
      </div>
    </div>
  )
}

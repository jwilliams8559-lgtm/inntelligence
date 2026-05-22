import { useEffect, useState, useRef } from 'react'

interface Props {
  selector: string
  active: boolean
  padding?: number
}

interface Rect { top: number; left: number; width: number; height: number }

/**
 * Renders a dark overlay covering the viewport EXCEPT a soft-edged
 * rectangular cutout over the element matching `selector`. Gold glow
 * border highlights the cutout. The overlay is purely visual — it
 * does not steal pointer events so the underlying app is still usable.
 */
export default function SpotlightOverlay({ selector, active, padding = 16 }: Props) {
  const [rect,    setRect]    = useState<Rect | null>(null)
  const [size,    setSize]    = useState({ w: window.innerWidth, h: window.innerHeight })
  const retryRef = useRef<number | null>(null)

  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (!active || !selector) { setRect(null); return }
    if (retryRef.current) clearTimeout(retryRef.current)

    function find(attempt = 0) {
      const el = document.querySelector(selector) as HTMLElement | null
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        // Allow scroll to settle, then measure
        retryRef.current = window.setTimeout(() => {
          const r = el.getBoundingClientRect()
          setRect({
            top:    r.top    - padding,
            left:   r.left   - padding,
            width:  r.width  + padding * 2,
            height: r.height + padding * 2,
          })
        }, 350) as unknown as number
      } else if (attempt < 20) {
        retryRef.current = window.setTimeout(() => find(attempt + 1), 150) as unknown as number
      } else {
        setRect(null)
      }
    }
    // Brief delay so navigation completes and DOM settles
    retryRef.current = window.setTimeout(() => find(0), 300) as unknown as number

    return () => { if (retryRef.current) clearTimeout(retryRef.current) }
  }, [selector, active, padding, size.w, size.h])

  if (!active) return null

  // No element found — full dark wash
  if (!rect) {
    return (
      <div style={{
        position: 'fixed', inset: 0, zIndex: 9000,
        background: 'rgba(0,0,0,0.6)', pointerEvents: 'none',
        transition: 'all 0.4s ease',
      }} />
    )
  }

  const { top, left, width, height } = rect
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9000, pointerEvents: 'none' }}>
      <svg width={size.w} height={size.h} style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <mask id="spotlight-cutout">
            <rect width={size.w} height={size.h} fill="white" />
            <rect x={left} y={top} width={width} height={height} rx={10} fill="black" />
          </mask>
        </defs>
        <rect width={size.w} height={size.h} fill="rgba(0,0,0,0.7)" mask="url(#spotlight-cutout)" style={{ transition: 'all 0.4s ease' }} />
        {/* Gold inner border */}
        <rect x={left - 2} y={top - 2} width={width + 4} height={height + 4} rx={12}
              fill="none" stroke="#A07830" strokeWidth={3}
              style={{ filter: 'drop-shadow(0 0 14px rgba(160,120,48,0.85))', transition: 'all 0.4s ease' }} />
        {/* Outer glow ring */}
        <rect x={left - 8} y={top - 8} width={width + 16} height={height + 16} rx={16}
              fill="none" stroke="#C9A84C" strokeWidth={1.5} opacity={0.45}
              style={{ transition: 'all 0.4s ease' }} />
      </svg>
    </div>
  )
}

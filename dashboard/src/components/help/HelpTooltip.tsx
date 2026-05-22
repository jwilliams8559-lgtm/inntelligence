import { useState, useRef, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  title: string
  body: string
  learnMoreUrl?: string
  delay?: number
}

/**
 * Help-context tooltip. Wraps any element. Hovers for ≥1.5s to display.
 * Styled like a boutique product, not a developer popover.
 */
export default function HelpTooltip({ children, title, body, learnMoreUrl, delay = 1500 }: Props) {
  const [open, setOpen] = useState(false)
  const t = useRef<number | null>(null)

  function start() {
    if (t.current) window.clearTimeout(t.current)
    t.current = window.setTimeout(() => setOpen(true), delay)
  }
  function stop() {
    if (t.current) { window.clearTimeout(t.current); t.current = null }
    setOpen(false)
  }

  return (
    <span className="relative inline-block" onMouseEnter={start} onMouseLeave={stop}>
      {children}
      {open && (
        <span className="absolute z-50 left-1/2 -translate-x-1/2 mt-2 w-72 animate-fade-in" style={{ top: '100%' }}>
          <span className="block bg-white rounded-lg shadow-2xl border border-warm overflow-hidden">
            <span className="block bg-navy text-white text-xs font-semibold px-3 py-1.5">{title}</span>
            <span className="block text-xs text-slate-700 px-3 py-2 leading-snug font-sans">{body}</span>
            {learnMoreUrl && (
              <span className="block px-3 pb-2">
                <a href={learnMoreUrl} target="_blank" rel="noopener" className="text-[11px] text-gold-dark font-bold hover:underline">Learn more →</a>
              </span>
            )}
          </span>
        </span>
      )}
    </span>
  )
}

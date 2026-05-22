import { useEffect, useState } from 'react'

interface Props { selector?: string }

export default function SpotlightOverlay({ selector }: Props) {
  const [rect, setRect] = useState<DOMRect | null>(null)

  useEffect(() => {
    function compute() {
      if (!selector) { setRect(null); return }
      const t = setTimeout(() => {
        const el = document.querySelector(selector)
        if (el) {
          const r = (el as HTMLElement).getBoundingClientRect()
          setRect(r)
          ;(el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' })
        } else {
          setRect(null)
        }
      }, 350)
      return () => clearTimeout(t)
    }
    const cleanup = compute()
    return cleanup
  }, [selector])

  return (
    <div className="fixed inset-0 z-40 pointer-events-none" aria-hidden>
      {rect ? (
        <svg className="w-full h-full">
          <defs>
            <mask id="demo-mask">
              <rect width="100%" height="100%" fill="white" />
              <rect x={rect.left - 12} y={rect.top - 12}
                    width={rect.width + 24} height={rect.height + 24}
                    rx={12} fill="black" />
            </mask>
          </defs>
          <rect width="100%" height="100%" fill="rgba(0,0,0,0.65)" mask="url(#demo-mask)" />
          <rect x={rect.left - 12} y={rect.top - 12}
                width={rect.width + 24} height={rect.height + 24}
                rx={12} fill="none" stroke="#A07830" strokeWidth={3}
                style={{ filter: 'drop-shadow(0 0 16px rgba(160,120,48,0.9))' }} />
        </svg>
      ) : (
        <div className="absolute inset-0 bg-black/55" />
      )}
    </div>
  )
}

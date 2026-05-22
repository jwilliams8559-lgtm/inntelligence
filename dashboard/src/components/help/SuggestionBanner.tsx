import { useEffect, useState, type ReactNode } from 'react'

interface Props {
  id: string                // unique key for dismiss persistence
  icon?: string
  children: ReactNode       // banner body
  cta?: { label: string; onClick: () => void }
  dismissForHours?: number  // default 24h
}

const KEY_PREFIX = 'inn_suggestion_'

/**
 * Sage-green dismissable banner that re-appears after N hours.
 * Honors the "inn_suggestions_disabled" localStorage flag.
 */
export default function SuggestionBanner({ id, icon = '💡', children, cta, dismissForHours = 24 }: Props) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (localStorage.getItem('inn_suggestions_disabled') === 'true') return
    const key = KEY_PREFIX + id
    const dismissedAt = Number(localStorage.getItem(key) || 0)
    const cutoff = Date.now() - dismissForHours * 3600 * 1000
    if (!dismissedAt || dismissedAt < cutoff) setOpen(true)
  }, [id, dismissForHours])

  function dismiss() {
    localStorage.setItem(KEY_PREFIX + id, String(Date.now()))
    setOpen(false)
  }

  if (!open) return null
  return (
    <div className="bg-sage/10 border border-sage/30 text-sage-dark rounded-lg px-4 py-2.5 flex items-center justify-between gap-3 text-sm animate-fade-in">
      <div className="flex items-baseline gap-2 flex-1 min-w-0">
        <span>{icon}</span>
        <span className="leading-snug">{children}</span>
      </div>
      <div className="flex items-center gap-2 whitespace-nowrap">
        {cta && (
          <button onClick={cta.onClick} className="bg-sage text-white text-xs font-bold px-3 py-1.5 rounded hover:bg-sage-dark">
            {cta.label}
          </button>
        )}
        <button onClick={dismiss} className="text-sage/60 hover:text-sage-dark text-base leading-none">×</button>
      </div>
    </div>
  )
}

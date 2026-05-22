import { useEffect, useState } from 'react'

const SEEN_KEY = 'inn_seen_screens'

function getSeen(): string[] {
  try { return JSON.parse(localStorage.getItem(SEEN_KEY) || '[]') }
  catch { return [] }
}
function markSeen(id: string) {
  const seen = getSeen()
  if (!seen.includes(id)) {
    seen.push(id)
    localStorage.setItem(SEEN_KEY, JSON.stringify(seen))
  }
}

interface Props {
  id: string                 // unique key per screen
  title: string
  bullets: string[]
  ctaLabel?: string
}

/**
 * First-visit screen intro modal. Shows once per browser, opt-out via
 * Settings → Guided Mode.
 */
export default function ScreenIntro({ id, title, bullets, ctaLabel = 'Got it' }: Props) {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const seen = getSeen().includes(id)
    const disabled = localStorage.getItem('inn_intros_disabled') === 'true'
    if (!seen && !disabled) setOpen(true)
  }, [id])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 bg-navy/50 flex items-center justify-center p-4 animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        <div className="bg-navy text-white px-5 py-3">
          <div className="text-[10px] uppercase tracking-[3px] text-gold font-bold">Quick orientation</div>
          <div className="font-display text-xl mt-0.5">{title}</div>
        </div>
        <ul className="px-5 py-4 space-y-2 text-sm text-slate-700">
          {bullets.map((b, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-gold">•</span>
              <span>{b}</span>
            </li>
          ))}
        </ul>
        <div className="px-5 pb-4 flex items-center justify-between">
          <a href="#settings" onClick={(e) => { e.preventDefault(); localStorage.setItem('inn_intros_disabled', 'true'); markSeen(id); setOpen(false); window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: 'settings' })) }}
             className="text-[11px] text-slate-400 hover:text-navy">Don't show these</a>
          <button onClick={() => { markSeen(id); setOpen(false) }}
                  className="bg-gold text-white text-sm font-bold px-4 py-2 rounded-lg hover:bg-gold-dark">{ctaLabel}</button>
        </div>
      </div>
    </div>
  )
}

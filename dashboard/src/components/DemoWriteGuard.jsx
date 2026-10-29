import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'

// In the read-only demo, neutralize save/edit/delete/create controls so visitors
// can't attempt mutations. This is UX polish — the SERVER is authoritative and
// returns 403 on every write for the demo principal regardless of the UI.
//
// Navigation stays fully live: links, NavLinks, tabs, filters, pagination,
// expand/collapse and anything whose label isn't a write verb are untouched.
const WRITE_VERB = /\b(save|add|create|new|edit|update|delete|remove|discard|send|approve|reject|publish|toggle|activate|deactivate|enable|disable|turn on|turn off|apply|confirm|submit|connect|invite|provision|generate|import|export|upload|reset|accept|decline|book|reserve|charge|pay|cancel subscription|upgrade|checkout|subscribe)\b/i

// Controls that are navigation/safe even if they match a verb (allowlist by testid/aria).
function isWriteControl(el) {
  if (!el) return false
  if (el.closest('[data-demo-allow]')) return false         // explicit opt-out
  if (el.closest('a[href]')) return false                    // links = navigation
  const role = el.getAttribute?.('role')
  if (role === 'tab' || role === 'menuitem') return false
  const label = (el.getAttribute?.('aria-label') || el.textContent || '').trim()
  return WRITE_VERB.test(label)
}

export default function DemoWriteGuard() {
  const { demoReadOnly } = useAuth() || {}
  const [toast, setToast] = useState(false)

  useEffect(() => {
    if (!demoReadOnly) return
    let t
    const flash = () => { setToast(true); clearTimeout(t); t = setTimeout(() => setToast(false), 2600) }

    const onClick = (e) => {
      const btn = e.target.closest?.('button, input[type="submit"], [role="button"]')
      if (btn && isWriteControl(btn)) {
        e.preventDefault(); e.stopPropagation()
        flash()
      }
    }
    const onSubmit = (e) => { e.preventDefault(); e.stopPropagation(); flash() }

    // Capture phase so we intercept before the app's own handlers run.
    document.addEventListener('click', onClick, true)
    document.addEventListener('submit', onSubmit, true)
    return () => {
      document.removeEventListener('click', onClick, true)
      document.removeEventListener('submit', onSubmit, true)
      clearTimeout(t)
    }
  }, [demoReadOnly])

  if (!demoReadOnly || !toast) return null
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[90] px-4 py-2.5 rounded-lg bg-navy text-white text-sm shadow-2xl border border-gold/40">
      🔒 Read-only demo — <span className="text-gold font-semibold">start a free trial</span> to make changes.
    </div>
  )
}

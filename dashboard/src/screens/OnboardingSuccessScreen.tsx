import { useEffect, useState } from 'react'

interface SessionInfo { session_id: string; plan_tier: string; email?: string | null; demo?: boolean }

export default function OnboardingSuccessScreen() {
  const [info, setInfo] = useState<SessionInfo | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sid = params.get('session_id')
    if (!sid) { setErr('Missing session ID'); return }
    fetch(`/api/billing/session/${sid}`).then(r => r.json()).then(j => {
      if (j.error) setErr(j.error); else setInfo(j)
    })
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-8"
         style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #07172B 100%)' }}>
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl p-8 text-center">
        <div className="w-16 h-16 bg-sage rounded-full mx-auto flex items-center justify-center text-white text-4xl">✓</div>
        <h1 className="text-navy font-bold text-2xl mt-3">Payment confirmed.</h1>
        <p className="text-slate-600 text-sm mt-1">Let's set up your property.</p>

        {err && <div className="mt-4 bg-coral/10 border border-coral/30 text-coral text-sm rounded p-3">{err}</div>}

        {info && (
          <div className="mt-5 bg-cream rounded-xl p-4 text-left text-sm">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Plan selected</div>
            <div className="text-navy font-bold text-lg capitalize mt-1">{info.plan_tier}</div>
            {info.email && <div className="text-slate-600 text-xs mt-1">Confirmation sent to {info.email}</div>}
            {info.demo && (
              <div className="mt-3 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
                ★ Demo mode — Stripe is not yet configured in this environment.
                In production this page launches a 5-step property setup wizard.
              </div>
            )}
          </div>
        )}

        <div className="mt-6 space-y-2">
          <a href="mailto:jwilliams8559@gmail.com?subject=I%20just%20signed%20up"
             className="block w-full bg-gold text-white font-bold py-2.5 rounded-lg hover:bg-gold-dark">
            Email Jim to schedule onboarding
          </a>
          <a href="/" className="block w-full bg-white border border-navy text-navy font-bold py-2.5 rounded-lg hover:bg-navy/5">
            Sign in to your dashboard
          </a>
        </div>

        <p className="text-[10px] text-slate-400 mt-6">INNtelligence by The Gracious Collection · 404-909-5818 · jwilliams8559@gmail.com</p>
      </div>
    </div>
  )
}

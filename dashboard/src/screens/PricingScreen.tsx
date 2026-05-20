import { useEffect, useState } from 'react'

interface Plan {
  id: string; name: string; price_monthly: number; trial_days: number
  highlight: boolean; cta: string; badge?: string
  tagline: string; features: string[]
}

export default function PricingScreen() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/billing/plans').then(r => r.json()).then(setPlans)
  }, [])

  async function selectPlan(p: Plan) {
    if (p.id === 'enterprise') {
      window.location.href = 'mailto:jwilliams8559@gmail.com?subject=Enterprise%20plan%20enquiry'
      return
    }
    setLoading(true)
    const r = await fetch('/api/billing/create-checkout', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_tier: p.id, success_root: window.location.origin }),
    })
    const j = await r.json()
    if (j.checkout_url) window.location.href = j.checkout_url
    else { alert(j.error || 'Checkout failed'); setLoading(false) }
  }

  return (
    <div className="min-h-screen py-12 px-4"
         style={{ background: 'linear-gradient(135deg, #FAF7F0 0%, #F5EFE0 100%)' }}>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-10">
          <div className="text-gold text-[10px] uppercase tracking-[4px] font-bold">The Gracious Collection</div>
          <h1 className="font-bold text-navy text-4xl mt-1" style={{ fontFamily: 'Georgia, serif' }}>Pricing for boutique inns</h1>
          <p className="text-slate-600 mt-2 text-sm">14-day free trial on every plan. No credit card required.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map(p => (
            <div key={p.id}
              className={`relative bg-white rounded-2xl p-6 flex flex-col ${
                p.highlight ? 'border-2 border-gold shadow-xl' : 'border border-slate-200 shadow-sm'
              }`}>
              {p.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gold text-white text-[10px] uppercase font-bold tracking-wide px-3 py-1 rounded-full">
                  {p.badge}
                </span>
              )}
              <div className="font-bold text-navy text-xl">{p.name}</div>
              <div className="text-xs text-slate-500 mt-0.5">{p.tagline}</div>
              <div className="mt-4 flex items-baseline">
                <span className="text-4xl font-bold text-navy">${p.price_monthly.toLocaleString()}</span>
                <span className="text-slate-500 text-sm ml-1">/mo</span>
              </div>
              {p.trial_days > 0 && (
                <div className="text-[11px] text-sage-dark font-semibold mt-1">{p.trial_days}-day free trial</div>
              )}
              <ul className="mt-4 space-y-1.5 text-xs text-slate-700 flex-1">
                {p.features.map((f, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-sage">✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <button onClick={() => selectPlan(p)} disabled={loading}
                className={`mt-5 w-full font-bold py-2.5 rounded-lg transition-colors ${
                  p.highlight ? 'bg-gold text-white hover:bg-gold-dark' : 'bg-navy text-white hover:bg-navy-light'
                } disabled:opacity-50`}>
                {loading ? 'Loading…' : p.cta}
              </button>
            </div>
          ))}
        </div>

        {/* Founding Member band */}
        <div className="mt-10 bg-gradient-to-br from-gold/15 to-gold/5 border-2 border-gold rounded-2xl p-6 flex items-center justify-between flex-wrap gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[3px] text-gold-dark font-bold">⭐ Founding Member</div>
            <h2 className="font-bold text-navy text-xl mt-1">Free for 6 months, then 25% off Professional forever</h2>
            <p className="text-sm text-slate-600 mt-1 max-w-xl">
              In exchange: PMS connection, monthly calls, testimonial, case study. We're looking for 3–5 founding members by Q3 2026.
            </p>
          </div>
          <a href="mailto:jwilliams8559@gmail.com?subject=Founding%20Member%20Application"
             className="bg-gold text-white font-bold px-6 py-3 rounded-lg hover:bg-gold-dark whitespace-nowrap">
            Apply Now →
          </a>
        </div>

        <div className="text-center text-[10px] text-slate-400 mt-10">
          The Gracious Collection © 2026 · graciouscollection.com · jwilliams8559@gmail.com
        </div>
      </div>
    </div>
  )
}

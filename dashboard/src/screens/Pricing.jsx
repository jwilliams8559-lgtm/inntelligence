import { Link } from 'react-router-dom'

// Correct tier pricing — matches engine/billing.py plan catalog.
const TIERS = [
  { id: 'starter', name: 'Starter', price: '$399', tagline: '5–10 rooms · first-time revenue management',
    feats: ['90-day rate calendar', 'AI recommendations', '5 competitors monitored', 'Manual rate approval', '1 PMS integration', 'Email support'] },
  { id: 'professional', name: 'Professional', price: '$699', popular: true, tagline: '10–20 rooms · serious revenue growth',
    feats: ['Everything in Starter', 'Autopilot rate publishing', 'OTA publishing (7 channels)', 'Guest CRM + campaigns', 'Packages & gift shop', 'Monthly strategy call'] },
  { id: 'enterprise', name: 'Enterprise', price: '$1,200', tagline: '20+ rooms · multi-property',
    feats: ['Everything in Professional', 'Multi-property console', '2 advisory hours / month', 'Custom integrations'] },
  { id: 'premium', name: 'Premium', price: '$2,400', tagline: 'Portfolio operators',
    feats: ['Everything in Enterprise', 'Unlimited properties', 'White-label option', 'Dedicated account manager'] },
]

export default function Pricing() {
  return (
    <div className="min-h-screen py-12 px-4" style={{ background: 'linear-gradient(135deg, #FAF7F0 0%, #F2ECDD 100%)' }}>
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-10">
          <div className="text-gold-dark text-[10px] uppercase tracking-[4px] font-bold">INNtelligence by The Gracious Collection</div>
          <h1 className="font-bold text-navy text-4xl mt-1" style={{ fontFamily: 'Georgia, serif' }}>Pricing for boutique inns</h1>
          <p className="text-gray-600 mt-2 text-sm">Boutique Hospitality Intelligence · 14-day free trial on every plan · no credit card required.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {TIERS.map((t) => (
            <div key={t.id} className={`relative bg-white rounded-2xl p-6 flex flex-col ${t.popular ? 'border-2 border-gold shadow-xl' : 'border border-gray-200 shadow-sm'}`}>
              {t.popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gold text-navy text-[10px] uppercase font-bold tracking-wide px-3 py-1 rounded-full">Most Popular</span>}
              <div className="font-bold text-navy text-xl">{t.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">{t.tagline}</div>
              <div className="mt-4 flex items-baseline">
                <span className="text-4xl font-extrabold text-navy">{t.price}</span>
                <span className="text-gray-500 text-sm ml-1">/mo</span>
              </div>
              <ul className="mt-4 space-y-1.5 text-xs text-gray-700 flex-1">
                {t.feats.map((f, i) => <li key={i} className="flex gap-2"><span className="text-gold">✓</span><span>{f}</span></li>)}
              </ul>
              <Link to="/onboarding" className={`mt-5 w-full text-center font-bold py-2.5 rounded-lg transition-colors ${t.popular ? 'bg-gold text-navy hover:bg-gold-light' : 'bg-navy text-white hover:bg-navy-light'}`}>
                Start free trial
              </Link>
            </div>
          ))}
        </div>

        {/* Founding Member band */}
        <div className="mt-10 rounded-2xl p-6 flex items-center justify-between flex-wrap gap-4 border-2 border-gold" style={{ background: 'linear-gradient(135deg, rgba(201,168,76,0.15), rgba(201,168,76,0.05))' }}>
          <div>
            <div className="text-[10px] uppercase tracking-[3px] text-gold-dark font-bold">⭐ Founding Member</div>
            <h2 className="font-bold text-navy text-xl mt-1">Free for 6 months, then $699/month (Professional)</h2>
            <p className="text-sm text-gray-600 mt-1 max-w-xl">In exchange: PMS connection, monthly calls, a testimonial, and a case study. We're looking for 3–5 founding members.</p>
          </div>
          <a href="mailto:hello@inntelligence.app?subject=Founding%20Member%20Application" className="bg-gold text-navy font-bold px-6 py-3 rounded-lg hover:bg-gold-light whitespace-nowrap">Apply Now →</a>
        </div>

        <div className="text-center text-[10px] text-gray-400 mt-10">
          INNtelligence by The Gracious Collection © 2026 · hello@inntelligence.app · <Link to="/" className="underline hover:text-gold">Back to dashboard</Link>
        </div>
      </div>
    </div>
  )
}

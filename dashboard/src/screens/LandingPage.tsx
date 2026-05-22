/**
 * INNtelligence public landing page at /.
 * Un-authed root visitors land here; authed users get the dashboard.
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cream text-navy">
      {/* HERO */}
      <section className="px-4 py-20 text-white" style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #0F2744 100%)' }}>
        <div className="max-w-5xl mx-auto text-center">
          <div className="text-gold font-display font-bold tracking-wide text-6xl md:text-7xl">INNtelligence</div>
          <div className="text-white/60 mt-2 text-sm tracking-wide">by The Gracious Collection</div>
          <h1 className="font-display text-3xl md:text-4xl mt-6">Revenue intelligence built for innkeepers</h1>
          <p className="text-white/85 mt-4 max-w-2xl mx-auto text-base">
            The only AI pricing platform that manages rooms, restaurant, bar, packages,
            and gift shop — built by a boutique inn owner, for boutique inn owners.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3 justify-center">
            <a href="/pricing" className="bg-gold text-white font-bold px-8 py-3.5 rounded-lg hover:bg-gold-dark text-lg">
              Start Free Trial — 14 Days Free
            </a>
            <a href="/demo" className="border border-white text-white font-bold px-6 py-3.5 rounded-lg hover:bg-white/10 text-lg">
              Watch 12-Minute Demo →
            </a>
          </div>
          <div className="text-white/40 text-xs mt-3">No credit card required. Cancel anytime.</div>
        </div>
      </section>

      {/* SOCIAL PROOF BAR */}
      <section className="bg-navy-light text-white/85 text-xs text-center px-4 py-3 tracking-wide">
        8.7× average ROI · 39 competitors monitored · 7 OTA channels · Built for Select Registry properties · TakeUp AI replacement
      </section>

      {/* FEATURE GRID */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <h2 className="font-display text-3xl text-center mb-10">Everything you need to price like a pro</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            { icon: '📅', title: 'Rate Intelligence', body: '90-day calendar with demand-driven recommendations. One-click approve to 7 OTAs in under 3 seconds.' },
            { icon: '🏆', title: 'Competitive Intelligence', body: 'Real-time monitoring of boutique peers and STRs. Boutique-anchored pricing — never priced below Cuthbert.' },
            { icon: '🍽️', title: 'F&B Yield', body: 'Restaurant and bar revenue tracked alongside rooms. Prix fixe and happy hour recommendations on slow nights.' },
            { icon: '📊', title: 'Plain-English Reasoning', body: 'Every rate explains itself: demand score, comp position, event impact, amenity premium. No black box.' },
            { icon: '💌', title: 'Guest CRM', body: 'Lifetime value, recency, anniversary tracking. Demand-triggered email campaigns drafted automatically.' },
            { icon: '📈', title: 'Documented ROI', body: 'Monthly performance report shows exact revenue lift vs subscription cost. Average 8.7× return.' },
          ].map((f, i) => (
            <div key={i} className="bg-white rounded-xl border border-warm shadow-sm p-5">
              <div className="text-3xl mb-2">{f.icon}</div>
              <div className="font-display text-lg text-navy">{f.title}</div>
              <p className="text-sm text-slate-600 mt-1.5 leading-snug">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* TAKEUP DISPLACEMENT */}
      <section className="bg-amber-600 text-white py-8 px-4">
        <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <div className="text-sm uppercase tracking-widest opacity-80">For former TakeUp AI customers</div>
            <div className="font-display text-2xl mt-1">More features. Lower cost. 60 days free, no credit card.</div>
            <div className="text-white/80 text-sm mt-1">We built the direct replacement — and added everything TakeUp did not have.</div>
          </div>
          <a href="/pricing?source=takeup" className="bg-white text-amber-700 font-bold px-6 py-3 rounded-lg hover:bg-amber-50 whitespace-nowrap">
            Claim 60-Day Free Trial →
          </a>
        </div>
      </section>

      {/* PRICING TEASER */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <h2 className="font-display text-3xl text-center mb-10">Pricing built for boutique inns</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {[
            { name: 'Essentials',   price: 399 },
            { name: 'Professional', price: 699, highlight: true },
            { name: 'Portfolio',    price: 1199 },
            { name: 'Enterprise',   price: 2400 },
          ].map(p => (
            <div key={p.name} className={`bg-white rounded-xl p-5 text-center ${p.highlight ? 'border-2 border-gold shadow-lg' : 'border border-warm'}`}>
              {p.highlight && <div className="bg-gold text-white text-[10px] uppercase font-bold tracking-wide py-1 -mx-5 -mt-5 mb-3 rounded-t-xl">Most Popular</div>}
              <div className="font-display text-xl text-navy">{p.name}</div>
              <div className="text-3xl font-bold mt-2 text-navy">${p.price.toLocaleString()}<span className="text-sm text-slate-400">/mo</span></div>
              <a href="/pricing" className={`block mt-4 py-2 rounded font-bold text-sm ${p.highlight ? 'bg-gold text-white hover:bg-gold-dark' : 'bg-navy text-white hover:bg-navy-light'}`}>Start Free Trial</a>
            </div>
          ))}
        </div>
        <div className="text-center mt-6">
          <a href="/pricing" className="text-gold-dark font-semibold hover:underline">See full plan comparison →</a>
        </div>
      </section>

      {/* CTA / DEMO */}
      <section className="bg-navy text-white px-4 py-16 text-center">
        <h2 className="font-display text-3xl">See it running on a real property</h2>
        <p className="text-white/80 mt-3">12 narrated steps. Anchorage 1770 Inn, Beaufort SC. No login required.</p>
        <a href="/demo" className="inline-block mt-6 bg-gold text-white font-bold px-8 py-3 rounded-lg hover:bg-gold-dark text-lg">
          ▶ Watch 12-Minute Demo
        </a>
      </section>

      {/* FOOTER */}
      <footer className="py-8 px-4 text-center text-xs text-slate-500">
        <div>INNtelligence by The Gracious Collection</div>
        <div className="mt-1">
          <a href="mailto:jwilliams8559@gmail.com" className="hover:text-navy">jwilliams8559@gmail.com</a>
          <span className="mx-2">·</span>
          <a href="tel:404-909-5818" className="hover:text-navy">404-909-5818</a>
          <span className="mx-2">·</span>
          <a href="/login" className="hover:text-navy">Sign in →</a>
        </div>
      </footer>
    </div>
  )
}

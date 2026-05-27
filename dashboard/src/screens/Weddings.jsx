import { useState, useEffect } from 'react'
import { usePrices } from '../context/PriceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const PACKAGES = [
  {
    name: 'Intimate Elopement', guests: 'Up to 10 guests · 1 night minimum', price: '$2,500 – $4,500',
    blurb: 'Just the two of you (and your dearest few). Exchange vows in our garden, toast with champagne, and wake to breakfast in bed with the morning light off the river.',
    inclusions: ['Private ceremony space', 'Bridal suite upgrade', 'Champagne toast', 'Breakfast for two', 'Late checkout'],
    addons: 'Add-ons: photographer referral · fresh florals · custom cake',
  },
  {
    name: 'Garden Ceremony', guests: 'Up to 30 guests · 2 night minimum · 10+ rooms', price: '$12,000 – $18,000',
    blurb: 'An intimate celebration beneath the live oaks. Your closest family and friends gather for a rehearsal dinner at The Parlor and an unforgettable garden ceremony.',
    inclusions: ['Outdoor garden ceremony space', 'Rehearsal dinner at The Parlor', 'Wedding night suite', 'Breakfast for all guests'],
  },
  {
    name: 'Classic Wedding', guests: 'Up to 50 guests · 2 night minimum · full buyout', price: '$18,000 – $28,000',
    blurb: 'The whole inn, entirely yours. A full Parlor reception, golden-hour cocktails on the rooftop, and a dedicated coordinator orchestrating every detail.',
    inclusions: ['Everything in Garden Ceremony', 'Full Parlor reception', 'Rooftop cocktail hour', 'Dedicated event coordinator'],
  },
  {
    name: 'Grand Celebration', guests: 'Up to 75 guests · 3 night minimum · full buyout', price: '$28,000 – $45,000',
    blurb: 'A three-day affair worthy of the moment. Welcome your guests with a riverside dinner, celebrate in grand style, and send everyone home with a farewell brunch.',
    inclusions: ['Everything in Classic', 'Welcome dinner (night 1)', 'Farewell brunch', 'Suite upgrades for the wedding party'],
  },
]

const HIGHLIGHTS = [
  { icon: '🏛️', title: 'Historic Setting', text: "Built in the heart of Beaufort's Historic District." },
  { icon: '🌅', title: 'Waterfront Views', text: 'Stunning Beaufort River views from our rooftop.' },
  { icon: '🍽️', title: 'The Parlor', text: 'Award-winning restaurant for rehearsal dinners and receptions.' },
  { icon: '🔑', title: 'Exclusive Buyout', text: 'Your guests have the entire inn to themselves.' },
  { icon: '🌿', title: 'Lowcountry Charm', text: 'Authentic Southern hospitality and cuisine.' },
  { icon: '💍', title: 'Expert Coordination', text: 'A dedicated wedding coordinator for every event.' },
]

const TESTIMONIALS = [
  { quote: 'The Bay Street Inn made our dream wedding a reality. The Parlor was stunning for our rehearsal dinner and waking up to Beaufort River views on our wedding morning was magical. The staff treated every one of our 40 guests like family.', who: 'Amanda & Christopher Hartley', when: 'married October 2025' },
  { quote: 'We chose The Bay Street Inn for its intimacy and exclusivity. Having the entire property to ourselves for the weekend made our celebration feel truly special. The rooftop at sunset was absolutely breathtaking.', who: 'Jennifer & Michael Torres', when: 'married September 2025' },
  { quote: 'From our first inquiry to the last goodbye, the team at Bay Street Inn exceeded every expectation. The food at The Parlor was exceptional and our guests are still talking about it six months later.', who: 'Sarah & David Kim', when: 'married March 2026' },
]

const FAQS = [
  ['How many guests can The Bay Street Inn accommodate?', 'We can host intimate elopements of 2 guests up to grand celebrations of 75 guests for a full property buyout.'],
  ['Do you require a minimum stay for wedding bookings?', 'Yes — wedding packages require a minimum 2-night stay for the full property, ensuring your celebration is never rushed.'],
  ['What is included in the F&B minimum?', 'Our food and beverage minimum covers catering through The Parlor at Bay Street Inn, including rehearsal dinners, cocktail hours, wedding receptions, and farewell brunches.'],
  ['Can we bring our own caterer?', "We proudly feature The Parlor's award-winning Lowcountry cuisine exclusively. Outside catering is not permitted."],
  ['What is your deposit and payment schedule?', 'We require 25% to hold your date, 50% at 90 days prior, and the remaining 25% at 30 days prior to your event.'],
  ['What is your cancellation policy?', 'Cancellations 90+ days prior receive a full refund. 60–89 days prior, 50% is refunded. Under 60 days, deposits are non-refundable.'],
  ['Is The Bay Street Inn pet friendly for weddings?', 'Yes — well-behaved pets are welcome in our pet-friendly garden rooms. Please inform us when booking.'],
  ['How far in advance should we book?', "We recommend booking 12–18 months in advance for peak season weekends, particularly during Beaufort's Water Festival and Gullah Festival periods."],
]

export default function Weddings() {
  const { property, loading, error } = usePrices()
  const name = property?.name || 'The Bay Street Inn'
  const [openFaq, setOpenFaq] = useState(0)
  const isDemo = (() => { try { return sessionStorage.getItem('inn_demo') === '1' } catch { return false } })()

  if (error) return <ErrorBanner message={error} />
  if (loading && !property) return <LoadingSpinner label="Loading…" />

  return (
    <div className="-m-6">
      {isDemo && (
        <div className="px-6 pt-6 max-w-6xl mx-auto"><DemoWeddingCalc /></div>
      )}
      {/* HERO */}
      <section className="relative text-center text-white px-6 py-20 overflow-hidden"
               style={{ background: 'radial-gradient(circle at 50% 20%, #14385f 0%, #0a2342 55%, #061629 100%)' }}>
        <div className="absolute inset-0 opacity-20 pointer-events-none"
             style={{ background: 'radial-gradient(circle at 50% 100%, rgba(201,168,76,0.5), transparent 60%)' }} />
        <div className="relative max-w-3xl mx-auto">
          <div className="text-gold-light text-xs uppercase tracking-[0.35em] mb-4">{name} · Beaufort, SC</div>
          <h1 className="text-4xl sm:text-5xl font-extrabold leading-tight" style={{ fontFamily: 'Georgia, serif' }}>
            Celebrate Your Perfect Day at {name}
          </h1>
          <p className="text-gold-light text-lg sm:text-xl mt-5 italic">
            Historic luxury on the Beaufort River — where Southern charm meets timeless elegance
          </p>
          <p className="text-white/70 mt-6 leading-relaxed">
            Nestled in the heart of Beaufort's Historic District, {name} offers an intimate and exclusive setting
            for your wedding celebration. With 19 beautifully appointed rooms, The Parlor restaurant, and our stunning
            rooftop overlooking the Beaufort River, every detail of your special day is thoughtfully curated.
          </p>
          <a href="#inquiry" className="inline-block mt-8 px-8 py-3 rounded-xl bg-gold text-navy font-bold hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">
            Begin Your Inquiry
          </a>
        </div>
      </section>

      <div className="px-6 py-12 max-w-6xl mx-auto space-y-16">
        {/* PACKAGES */}
        <section>
          <SectionTitle eyebrow="Curated for you" title="Wedding Packages" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {PACKAGES.map((p) => (
              <div key={p.name} className="rounded-2xl overflow-hidden border border-gold/30 bg-white shadow-sm">
                <div className="bg-navy text-white px-6 py-5">
                  <div className="flex items-baseline justify-between flex-wrap gap-2">
                    <h3 className="text-2xl font-bold" style={{ fontFamily: 'Georgia, serif' }}>{p.name}</h3>
                    <span className="text-gold font-extrabold text-lg">{p.price}</span>
                  </div>
                  <div className="text-gold-light text-xs mt-1">{p.guests}</div>
                </div>
                <div className="p-6">
                  <p className="text-gray-600 italic leading-relaxed">{p.blurb}</p>
                  <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-sm text-gray-700">
                    {p.inclusions.map((i) => <li key={i} className="flex gap-2"><span className="text-gold">✦</span>{i}</li>)}
                  </ul>
                  {p.addons && <div className="text-[11px] text-gray-400 mt-3 italic">{p.addons}</div>}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* VENUE HIGHLIGHTS */}
        <section>
          <SectionTitle eyebrow="Why couples choose us" title="Venue Highlights" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {HIGHLIGHTS.map((h) => (
              <div key={h.title} className="rounded-2xl border border-gray-200 bg-white p-6 text-center shadow-sm hover:shadow-md transition-shadow">
                <div className="text-4xl">{h.icon}</div>
                <div className="font-bold text-navy mt-3">{h.title}</div>
                <div className="text-sm text-gray-500 mt-1">{h.text}</div>
              </div>
            ))}
          </div>
        </section>

        {/* INQUIRY FORM */}
        <section id="inquiry">
          <SectionTitle eyebrow="Let's begin" title="Wedding Inquiry" />
          <InquiryForm />
        </section>

        {/* PHOTO GALLERY PLACEHOLDER */}
        <section>
          <SectionTitle eyebrow="A glimpse of your day" title="Photo Gallery" />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="aspect-[4/3] rounded-2xl flex flex-col items-center justify-center border border-gold/30"
                   style={{ background: 'linear-gradient(135deg, rgba(201,168,76,0.12), rgba(232,213,163,0.18))' }}>
                <div className="text-3xl text-gold/70">📷</div>
                <div className="text-xs text-gold-dark/70 mt-1">Your wedding photos here</div>
              </div>
            ))}
          </div>
          <p className="text-center text-sm text-gray-500 mt-4">Contact us to schedule a venue tour and photo session.</p>
        </section>

        {/* TESTIMONIALS */}
        <section>
          <SectionTitle eyebrow="Love stories" title="What Couples Say" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {TESTIMONIALS.map((t) => (
              <div key={t.who} className="rounded-2xl bg-navy text-white p-6 relative">
                <div className="text-gold text-5xl leading-none absolute top-3 left-4 opacity-40">“</div>
                <p className="text-white/85 text-sm leading-relaxed relative mt-4 italic">{t.quote}</p>
                <div className="mt-4 text-gold font-semibold text-sm">— {t.who}</div>
                <div className="text-white/50 text-xs">{t.when}</div>
              </div>
            ))}
          </div>
        </section>

        {/* FAQ */}
        <section>
          <SectionTitle eyebrow="Good to know" title="Frequently Asked Questions" />
          <div className="space-y-2 max-w-3xl mx-auto">
            {FAQS.map(([q, a], i) => (
              <div key={q} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <button onClick={() => setOpenFaq(openFaq === i ? -1 : i)}
                        className="w-full flex items-center justify-between text-left px-5 py-3.5 hover:bg-gray-50">
                  <span className="font-semibold text-navy text-sm">{q}</span>
                  <span className="text-gold ml-3">{openFaq === i ? '−' : '+'}</span>
                </button>
                {openFaq === i && <div className="px-5 pb-4 text-sm text-gray-600 leading-relaxed">{a}</div>}
              </div>
            ))}
          </div>
        </section>

        {/* CONTACT */}
        <section className="rounded-2xl text-center text-white px-6 py-12"
                 style={{ background: 'radial-gradient(circle at 50% 0%, #14385f, #0a2342)' }}>
          <h2 className="text-3xl font-extrabold" style={{ fontFamily: 'Georgia, serif' }}>Ready to Begin Planning?</h2>
          <div className="mt-4 text-gold-light">
            <div>Wedding Coordinator: <span className="text-gold font-semibold">weddings@baystreetinn.com</span></div>
            <div className="mt-1">Phone: <span className="text-gold font-semibold">(843) 555-0177</span></div>
          </div>
          <div className="flex items-center justify-center gap-4 mt-8 flex-wrap">
            <a href="mailto:weddings@baystreetinn.com?subject=Schedule%20a%20venue%20tour"
               className="px-7 py-3 rounded-xl bg-gold text-navy font-bold hover:bg-gold-light transition-colors">Schedule a Tour</a>
            <button className="px-7 py-3 rounded-xl border border-gold/60 text-gold font-semibold hover:bg-gold/10 transition-colors">Download Wedding Guide</button>
          </div>
        </section>
      </div>
    </div>
  )
}

// Demo-only automated wedding quote: pre-populated inquiry with instant
// results, then a Water Festival date conflict fires after 8 seconds (FIX 6).
function DemoWeddingCalc() {
  const [conflict, setConflict] = useState(false)
  const [dateLabel, setDateLabel] = useState('September 13, 2026')
  useEffect(() => {
    const t = setTimeout(() => {
      setDateLabel('July 19, 2026 — Water Festival'); setConflict(true)
      try { window.dispatchEvent(new CustomEvent('inn-demo-wedding-conflict')) } catch { /* ignore */ }
    }, 12000)
    return () => clearTimeout(t)
  }, [])

  const lines = [
    ['Room block — 19 rooms × 2 nights', 22800],
    ['Event space rental', 3500],
    ['Food & beverage — 40 guests', 7200],
    ['Setup & breakdown', 1200],
    ['Exclusivity premium', 2600],
  ]
  const total = 37300, individual = 16800, premium = total - individual
  const usd = (n) => '$' + n.toLocaleString('en-US')

  return (
    <section data-tour="wedding-calc" className="rounded-2xl border border-gold/40 bg-white shadow-sm overflow-hidden">
      <style>{`@keyframes wedSlide{from{opacity:0;transform:translateY(-14px)}to{opacity:1;transform:none}}`}</style>
      {conflict && (
        <div style={{ animation: 'wedSlide .4s ease-out' }}
          className="bg-rose-600 text-white px-5 py-3 font-semibold flex items-center gap-2">
          <span className="text-lg">⚠</span>
          CONFLICT: Water Festival rates exceed wedding buyout value — Recommend declining or negotiating
        </div>
      )}
      <div className="bg-navy text-white px-6 py-4">
        <div className="text-gold-light text-[11px] uppercase tracking-wide">Wedding Inquiry · Auto-calculated</div>
        <div className="flex items-baseline justify-between flex-wrap gap-2 mt-1">
          <div className="text-xl font-bold">Margaret &amp; Thomas</div>
          <div className={`text-sm font-semibold ${conflict ? 'text-rose-300' : 'text-gold'}`}>{dateLabel}</div>
        </div>
        <div className="text-white/60 text-xs mt-0.5">40 guests · full property buyout · 2 nights</div>
      </div>
      <div className="p-6">
        <div className="space-y-1.5">
          {lines.map(([label, val]) => (
            <div key={label} className="flex justify-between text-sm border-b border-gray-100 py-1.5">
              <span className="text-gray-600">{label}</span>
              <span className="font-semibold text-navy">{usd(val)}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between mt-3">
          <span className="font-bold text-navy">Total wedding package</span>
          <span className="text-2xl font-extrabold text-gold">{usd(total)}</span>
        </div>
        {!conflict ? (
          <div className="mt-4 rounded-lg bg-emerald-50 border border-emerald-200 p-3 flex items-center justify-between">
            <span className="text-sm text-emerald-800">vs individual bookings {usd(individual)} · wedding premium <span className="font-bold">+{usd(premium)}</span></span>
            <span className="text-xs font-bold bg-emerald-600 text-white px-3 py-1 rounded-full">ACCEPT</span>
          </div>
        ) : (
          <div className="mt-4 rounded-lg bg-rose-50 border border-rose-200 p-3 flex items-center justify-between">
            <span className="text-sm text-rose-800">Water Festival individual pricing exceeds this buyout on these dates.</span>
            <span className="text-xs font-bold bg-rose-600 text-white px-3 py-1 rounded-full">DECLINE / NEGOTIATE</span>
          </div>
        )}
      </div>
    </section>
  )
}

function SectionTitle({ eyebrow, title }) {
  return (
    <div className="text-center mb-7">
      <div className="text-gold-dark text-xs uppercase tracking-[0.3em]">{eyebrow}</div>
      <h2 className="text-3xl font-extrabold text-navy mt-1" style={{ fontFamily: 'Georgia, serif' }}>{title}</h2>
      <div className="w-16 h-0.5 bg-gold mx-auto mt-3" />
    </div>
  )
}

function InquiryForm() {
  const [f, setF] = useState({ p1: '', p2: '', date: '', guests: '', budget: '', referral: '', requests: '' })
  const [sent, setSent] = useState(false)
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }))
  const cls = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold'

  if (sent) {
    return (
      <div className="max-w-xl mx-auto rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
        <div className="text-4xl">💌</div>
        <div className="text-xl font-bold text-navy mt-3">Thank you!</div>
        <p className="text-gray-600 mt-1">Our wedding coordinator will contact you within 24 hours.</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Labeled label="Partner 1 Name"><input value={f.p1} onChange={set('p1')} className={cls} /></Labeled>
        <Labeled label="Partner 2 Name"><input value={f.p2} onChange={set('p2')} className={cls} /></Labeled>
        <Labeled label="Wedding Date"><input type="date" value={f.date} onChange={set('date')} className={cls} /></Labeled>
        <Labeled label="Guest Count"><input type="number" value={f.guests} onChange={set('guests')} className={cls} /></Labeled>
        <Labeled label="Budget Range">
          <select value={f.budget} onChange={set('budget')} className={cls}>
            <option value="">Select…</option>
            {['Under $15k', '$15k – $25k', '$25k – $40k', '$40k+'].map((b) => <option key={b}>{b}</option>)}
          </select>
        </Labeled>
        <Labeled label="How did you hear about us?"><input value={f.referral} onChange={set('referral')} className={cls} /></Labeled>
      </div>
      <div className="mt-4">
        <Labeled label="Special Requests"><textarea value={f.requests} onChange={set('requests')} rows={3} className={cls} /></Labeled>
      </div>
      <button onClick={() => setSent(true)} disabled={!f.p1 || !f.p2}
              className="mt-5 w-full bg-gold text-navy font-bold py-3 rounded-xl hover:bg-gold-light transition-colors disabled:opacity-50">
        Send Wedding Inquiry
      </button>
    </div>
  )
}

const Labeled = ({ label, children }) => (
  <div><label className="block text-xs font-semibold text-gray-500 mb-1">{label}</label>{children}</div>
)

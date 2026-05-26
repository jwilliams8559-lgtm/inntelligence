import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'

// ─────────────────────────────────────────────────────────────────────────────
//  INNtelligence — Product Tour. Narration via ElevenLabs (Will), generated
//  server-side and cached, with a Web Speech API fallback. Two-panel layout
//  (60% simulated screen / 40% narration + metrics) and a working auto-play
//  timer (useRef so it survives re-renders).
// ─────────────────────────────────────────────────────────────────────────────

const TOTAL_SECONDS = 1320 // 22 minutes (progress-bar denominator)
const usd = (n) => '$' + Math.round(n).toLocaleString('en-US')

// Test mode: /tour?test=400 → skip prep + audio, use 400ms steps so headless
// can verify auto-advance without spending credits or waiting minutes.
const TEST_MS = (() => {
  try { const v = new URLSearchParams(window.location.search).get('test'); return v ? Number(v) : null }
  catch { return null }
})()

// ── Shared bits ──────────────────────────────────────────────────────────────
const Bar = ({ v, max, color = '#c9a84c' }) => (
  <div className="flex-1 h-3.5 bg-white/10 rounded overflow-hidden">
    <div className="h-full rounded" style={{ width: `${Math.min(100, (v / max) * 100)}%`, background: color }} />
  </div>
)
const Tag = ({ children, tone = 'gold' }) => {
  const t = { gold: 'bg-gold/20 text-gold border-gold/40', rose: 'bg-rose-500/20 text-rose-300 border-rose-400/40', emerald: 'bg-emerald-500/20 text-emerald-300 border-emerald-400/40', amber: 'bg-amber-500/20 text-amber-200 border-amber-400/40', gray: 'bg-white/10 text-white/60 border-white/20' }
  return <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${t[tone]}`}>{children}</span>
}
const SimTitle = ({ children }) => <div className="text-gold-light text-xs font-semibold uppercase tracking-wide mb-3">{children}</div>

// ── 14 simulated screens ─────────────────────────────────────────────────────
function S1() {
  const m = [['Avg Rate', '$487'], ['RevPAR', '$365'], ['Market Pressure', '7/10'], ['Active Events', '4']]
  return (
    <div><SimTitle>Good Morning · Today at The Bay Street Inn</SimTitle>
      <div className="grid grid-cols-2 gap-3">
        {m.map((x) => <div key={x[0]} className="rounded-xl bg-white/5 border border-white/10 p-4"><div className="text-gold text-2xl font-extrabold">{x[1]}</div><div className="text-white/50 text-xs mt-1">{x[0]}</div></div>)}
      </div>
      <div className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/10 p-3 text-sm text-rose-200">⚠ Alert: a competitor dropped rates overnight.</div>
    </div>
  )
}
function S2() {
  const rows = [['Rhett House Inn', '↓ $40 overnight', 'rose'], ['Cuthbert House Inn', '$455 · holding', 'gray'], ['Anchorage 1770', '$445', 'gray'], ['★ Bay Street Inn', '$445 · hold', 'gold']]
  return (
    <div><SimTitle>Competitive Intel · Waterfront</SimTitle>
      <div className="space-y-1.5">
        {rows.map((r) => (
          <div key={r[0]} className={`flex justify-between items-center rounded-lg px-3 py-2 ${r[2] === 'gold' ? 'bg-gold/15' : 'bg-white/5'} ${r[2] === 'rose' ? 'ring-1 ring-rose-400/50' : ''}`}>
            <span className={r[2] === 'gold' ? 'text-gold font-bold' : 'text-white/80'}>{r[0]}</span>
            <span className={`text-sm ${r[2] === 'rose' ? 'text-rose-300 font-semibold' : 'text-white/60'}`}>{r[1]}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 text-xs text-white/50">Comp average tonight: <span className="text-white font-semibold">$412</span> · your premium <span className="text-emerald-300 font-semibold">+8% justified</span></div>
    </div>
  )
}
function S3() {
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2"><SimTitle>Rate Calendar · Water Festival weekend</SimTitle>
        <div className="space-y-1.5 text-sm">
          {[['Fri Jul 17 · WF Room 1', 502], ['Sat Jul 18 · WF Room 1', 547], ['Fri Jul 17 · Grand Parlor', 721]].map((r) => (
            <div key={r[0]} className="flex justify-between rounded-lg bg-white/5 px-3 py-2"><span className="text-white/70">{r[0]}</span><span className="text-gold font-bold">{usd(r[1])}</span></div>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-gold/40 bg-navy-dark/60 p-3 text-xs text-white/70">
        <div className="text-gold font-bold mb-1">Why $502?</div>
        Seasonal ×1.30 · Festival ×1.35 · 9 days out · 3 rooms left · comp avg $412.
        <div className="mt-2 text-emerald-300">+29% above rack — justified</div>
      </div>
    </div>
  )
}
function S4() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div><SimTitle>Gap Night Detector</SimTitle>
        <div className="rounded-lg border border-rose-400 bg-rose-500/10 p-3 text-sm"><div className="text-rose-300 font-bold">Tue Jun 2 · Garden Room 3</div><div className="text-white/60 text-xs mt-1">Orphan between two booked nights</div></div>
        <ul className="mt-2 text-xs text-white/70 space-y-1"><li>① Lower rate $22</li><li>② Targeted email · 150-mi garden guests</li></ul>
      </div>
      <div><SimTitle>Fri / Sat Solver</SimTitle>
        <div className="text-sm text-white/70">6 Saturdays booked · Fridays open</div>
        <div className="mt-1 text-xs text-white/60">4 → add 2-night minimum · 2 → Friday discount</div>
        <div className="mt-3 rounded-lg bg-gold/10 border border-gold/30 p-3 text-gold font-bold">Est. recovery today: $840</div>
      </div>
    </div>
  )
}
function S5() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div><SimTitle>Lapsed VIP Guests · 12</SimTitle>
        {['Catherine Beaumont — Charlotte', 'Thomas Reed — DC', 'Sarah Donnelly — Columbia'].map((g, i) => (
          <div key={g} className={`rounded-lg px-3 py-2 mt-1.5 text-sm ${i === 0 ? 'bg-gold/15 text-gold font-semibold' : 'bg-white/5 text-white/70'}`}>{g}</div>
        ))}
      </div>
      <div className="rounded-xl border border-gold/40 bg-navy-dark/60 p-4">
        <div className="text-gold font-bold">Catherine Beaumont</div>
        <div className="text-xs text-white/50">4 stays · {usd(3840)} lifetime · waterfront · 7 mo ago</div>
        <div className="mt-3 rounded-lg bg-white/5 p-3 text-xs text-white/70">Win-Back email · 10% loyalty rate · personalized → 12 guests</div>
        <div className="mt-2 text-emerald-300 font-bold text-sm">Win-back potential: $5,400</div>
      </div>
    </div>
  )
}
function S6() {
  return (
    <div className="grid grid-cols-3 gap-4 items-center">
      <div className="text-center rounded-xl bg-navy-dark/60 border border-gold/40 p-5"><div className="text-gold-light text-xs uppercase">90-day ROI</div><div className="text-5xl font-extrabold text-gold mt-1">8.7×</div></div>
      <div className="col-span-2 grid grid-cols-2 gap-2 text-sm">
        {[['Water Festival lift', '+$4,200'], ['Win-back revenue', '+$2,100'], ['RevPAR vs comp', '+23%'], ['ADR YoY', '+18%']].map((x) => (
          <div key={x[0]} className="rounded-lg bg-white/5 p-3"><div className="text-emerald-300 font-bold">{x[1]}</div><div className="text-white/50 text-xs">{x[0]}</div></div>
        ))}
      </div>
    </div>
  )
}
function S7() {
  const parlor = [['Mon', 1200], ['Tue', 980], ['Wed', 1100], ['Thu', 1100], ['Fri', 3200], ['Sat', 3800], ['Sun', 2100]]
  return (
    <div><SimTitle>The Parlor · revenue by day</SimTitle>
      <div className="space-y-1.5">{parlor.map((d) => (
        <div key={d[0]} className="flex items-center gap-2 text-[11px]"><span className="w-8 text-white/50">{d[0]}</span><Bar v={d[1]} max={4000} color={d[0] === 'Thu' ? '#f59e0b' : '#c9a84c'} /><span className="w-12 text-right text-white/70">{usd(d[1])}</span></div>
      ))}</div>
      <div className="mt-3 rounded-lg bg-gold/10 border border-gold/30 p-3 text-xs text-white/80"><span className="text-gold font-semibold">Recommendation:</span> Thursday Lowcountry Sunset Supper → +$1,400/mo</div>
    </div>
  )
}
function S8() {
  const lines = [['Room block (19×2×$420)', 15960], ['Event space', 1500], ['F&B (45 guests)', 5625], ['Setup & coordination', 800], ['Exclusivity premium', 4777]]
  return (
    <div><SimTitle>Private Events · Hartley Wedding</SimTitle>
      {lines.map((l) => <div key={l[0]} className="flex justify-between text-xs py-1 border-b border-white/5"><span className="text-white/70">{l[0]}</span><span className="text-white">{usd(l[1])}</span></div>)}
      <div className="flex justify-between mt-2 text-gold font-extrabold text-lg"><span>Total package</span><span>$28,662</span></div>
      <div className="mt-2 flex items-center justify-between"><span className="text-xs text-white/60">vs individual $15,960 → +$12,702</span><Tag tone="emerald">ACCEPT</Tag></div>
    </div>
  )
}
function S9() {
  return (
    <div><SimTitle>Events · Next 6 months</SimTitle>
      <div className="rounded-xl border border-gold/50 bg-gold/10 p-4 text-center"><div className="text-gold text-4xl font-extrabold">9 days</div><div className="text-white/60 text-xs">until Beaufort Water Festival · 13 days</div></div>
      <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
        <div className="rounded-lg bg-white/5 p-3"><div className="text-white font-bold">85%</div><div className="text-white/50">waterfront booked</div></div>
        <div className="rounded-lg bg-white/5 p-3"><div className="text-white font-bold">+35–40%</div><div className="text-white/50">expected premium</div></div>
      </div>
      <div className="mt-2 text-xs text-emerald-300">Recommendation: hold rates — demand surges in final 7 days</div>
    </div>
  )
}
function S10() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="rounded-xl border border-gold/40 bg-navy-dark/60 p-4"><div className="text-gold font-bold">💑 Romance Package</div><div className="text-emerald-300 font-bold text-lg mt-1">$4,781/mo</div><div className="text-white/50 text-xs">active · 20% take · +$85</div></div>
      <div className="rounded-xl border border-white/15 bg-white/5 p-4"><div className="flex items-center justify-between"><span className="text-white font-semibold">💍 Proposal Package</span><span className="text-xs bg-navy ring-1 ring-gold text-white px-2 py-0.5 rounded animate-pulse">Activate</span></div><div className="text-white/50 text-xs mt-1">only 12% of inns offer · +$195</div><div className="text-gold font-bold mt-1">$3,200/mo potential</div></div>
    </div>
  )
}
function S11() {
  const ms = [42, 38, 44, 51, 58, 62, 68, 64, 55, 49, 41, 46, 48, 44, 50, 57, 64]
  return (
    <div><SimTitle>Historical · 24 months</SimTitle>
      <div className="flex items-end gap-1 h-32">{ms.map((m, i) => <div key={i} className="flex-1 rounded-t" style={{ height: `${(m / 68) * 100}%`, background: i === 6 ? '#c9a84c' : 'rgba(255,255,255,0.2)' }} />)}</div>
      <div className="flex justify-between text-xs mt-2"><span className="text-gold font-bold">Best: Jul 2025 · $68,400</span><span className="text-emerald-300">+23% vs last May</span></div>
    </div>
  )
}
function S12() {
  return (
    <div className="grid grid-cols-2 gap-4 items-center">
      <div className="text-center rounded-xl bg-navy-dark/60 border border-gold/40 p-5"><div className="text-gold-light text-xs uppercase">Pricing Power</div><div className="text-5xl font-extrabold text-gold mt-1">84<span className="text-xl text-white/30">/100</span></div></div>
      <div className="space-y-2">{[['TripAdvisor', 4.7], ['Google', 4.8], ['Booking.com', 4.6]].map((p) => <div key={p[0]} className="flex items-center gap-2 text-sm"><span className="w-24 text-white/60">{p[0]}</span><Bar v={p[1]} max={5} /><span className="text-gold font-bold w-10 text-right">{p[1]}★</span></div>)}<div className="text-xs text-white/50 mt-1">Top: location, views, breakfast, staff</div></div>
    </div>
  )
}
function S14() {
  const cats = [['🛏️ Comphy Bedding', 1920], ['🍷 Murano Glass · Mazzuccato', 1240], ['🫙 Lowcountry Pantry', 612]]
  return (
    <div><SimTitle>Gift Shop · $3,160 this month</SimTitle>
      {cats.map((c) => <div key={c[0]} className="flex justify-between rounded-lg bg-white/5 px-3 py-2 mt-1.5 text-sm"><span className="text-white/80">{c[0]}</span><span className="text-emerald-300 font-bold">{usd(c[1])}</span></div>)}
      <div className="mt-2 text-xs text-white/50">Pure margin · zero additional staff</div>
    </div>
  )
}

function SWED() {
  const pk = [['Intimate Elopement', '$2,500–$4,500'], ['Garden Ceremony', '$12,000–$18,000'], ['Classic Wedding', '$18,000–$28,000'], ['Grand Celebration', '$28,000–$45,000']]
  return (
    <div><SimTitle>Weddings · shareable with couples</SimTitle>
      <div className="grid grid-cols-2 gap-2">
        {pk.map((p, i) => (
          <div key={p[0]} className={`rounded-lg p-3 border ${i === 3 ? 'border-gold/50 bg-gold/10' : 'border-white/10 bg-white/5'}`}>
            <div className="text-white text-sm font-semibold">{p[0]}</div>
            <div className="text-gold text-xs font-bold mt-1">{p[1]}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-lg bg-white/5 border border-white/10 p-3 text-xs text-white/60">
        Inquiry form qualifies the lead and routes to your event coordinator · every date checked against your revenue calendar.
      </div>
    </div>
  )
}

// ── Step definitions ─────────────────────────────────────────────────────────
const N = {
  s1: "It's 7:02 on a Friday morning in Beaufort, South Carolina. You open INNtelligence. In ten seconds you know everything you need to know about today. Average rate across all 19 rooms: $487. RevPAR: $365. Market pressure score seven out of ten — the market is strong. Four active events in the next thirty days. And one alert: a competitor dropped rates overnight. Let's see which one.",
  s2: "Rhett House Inn. Down forty dollars on standard rooms since yesterday. They have availability for Water Festival opening weekend — which means they're getting nervous. Here's what that means for you. Switch to Waterfront rooms. Your direct comp set average tonight is $412. INNtelligence is recommending you hold at $445 — an eight percent premium — because your waterfront rooms have a higher reputation score and Cuthbert House, your strongest direct competitor, hasn't moved. But if Cuthbert drops by Friday you'll get an alert immediately. You're not flying blind anymore.",
  s3: "Now let's look at Water Festival weekend specifically. Friday July seventeenth. INNtelligence is recommending Waterfront Room 1 at five hundred and two dollars. That's twenty-nine percent above rack rate. Here's the reasoning: seasonal index one point three, Water Festival multiplier one point three five, nine days out with three rooms still available, competitor average four hundred and twelve — your premium is fully justified. Click accept and that rate is set. Saturday July eighteenth — five hundred and forty-seven. Grand Parlor Suite — seven hundred and twenty-one. All nineteen rooms priced individually for that weekend in under sixty seconds. Compare that to what it used to take.",
  s4: "Three gap nights flagged this week. Tuesday June second — Garden Room 3 is the only unbooked room between two booked dates. Classic orphan gap. INNtelligence recommends lowering the rate twenty-two dollars and sending a targeted offer to guests within a hundred and fifty miles who've stayed in garden rooms before. That one room at a discounted rate is worth more than that room empty at full price. The Friday-Saturday problem: you have six Saturday bookings this week with their adjacent Fridays open. INNtelligence recommends adding a two-night minimum to four of them where demand is strong enough, and offering a modest Friday discount on the other two where it isn't. Estimated additional revenue from acting on these recommendations today: eight hundred and forty dollars.",
  s5: "Forty-seven guests haven't visited Bay Street Inn in over six months. INNtelligence has identified twelve of them as high-value win-back targets — people who stayed multiple times, spent over six hundred dollars per visit, and whose last stay was more than a hundred and eighty days ago. Margaret Chen from Charlotte is at the top of the list. Four stays. Three thousand eight hundred and forty dollars in lifetime spend. Waterfront room every time. Last visit seven months ago. One personalized email with a ten percent loyalty rate for her next waterfront booking. INNtelligence writes the email, personalizes it with her name and her preferred room type, and sends it. If three of those twelve guests book — conservative estimate — that's five thousand four hundred dollars in recovered revenue from fifteen minutes of your morning.",
  s6: "Is INNtelligence worth it? Let's look at the numbers. Ninety days in. Bay Street Inn's RevPAR is running twenty-three percent above the competitive set. ADR is up eighteen percent year over year. The subscription cost for those ninety days: eight hundred and ninety-seven dollars. The additional revenue attributable to INNtelligence recommendations: seven thousand eight hundred and three dollars. That's an eight point seven times return. The Water Festival weekend alone — priced dynamically instead of at last year's flat rate — generated four thousand two hundred dollars in additional revenue. One weekend paid for the subscription nine times over.",
  s7: "The Parlor at Bay Street Inn. Thursday evening is underperforming — eleven hundred in revenue compared to thirty-two hundred on Friday. INNtelligence recommendation: launch a Thursday Lowcountry Sunset Supper — a fixed price three-course menu at sixty-five dollars per person paired with a rooftop cocktail hour at sunset. Similar inns that have added a Thursday evening special see a twenty to twenty-five percent lift. At Bay Street Inn's average cover count that's fourteen hundred dollars in additional monthly food and beverage revenue. One menu change. One night a week.",
  s8: "A wedding inquiry came in last night. Sarah and James Thompson. August twenty-third. Forty-five guests. They want a full buyout. Let's run the calculator. Nineteen rooms times two nights at four hundred and twenty average: fifteen thousand nine hundred and sixty. Event space: fifteen hundred. Food and beverage for forty-five guests: five thousand six hundred and twenty-five. Setup and coordination: eight hundred. Exclusivity premium: four thousand seven hundred and seventy-seven. Total package: twenty-eight thousand six hundred and sixty-two dollars. Compare that to selling those rooms individually on a late August weekend: fifteen thousand nine hundred and sixty. The wedding generates twelve thousand seven hundred and two dollars more than individual bookings. Recommendation: Accept.",
  s9: "Nine days until the Water Festival. Thirteen days of the biggest demand event in Beaufort. INNtelligence has been adjusting rates for this window since ninety days out. Right now all waterfront and water view rooms are eighty-five percent booked for the festival period. Garden rooms are at sixty percent. INNtelligence recommendation: hold rates, do not discount. Demand typically surges in the final seven days as last-minute bookers fill those rooms. Trust the model.",
  s10: "The Romance Package is generating four thousand seven hundred and eighty-one dollars per month at Bay Street Inn. Twenty percent of guests are adding it at eighty-five dollars above rack rate. But INNtelligence has identified a gap in your package lineup. The Proposal Package — a room upgrade, champagne, personalized note, and photographer referral — is offered by only twelve percent of comparable inns in your market. Recommended premium: one hundred and ninety-five dollars. Estimated monthly revenue at fifteen percent take rate: three thousand two hundred dollars. One package activation. Potentially thirty-eight thousand four hundred in additional annual revenue.",
  s11: "Twenty-four months of performance data. Your best month ever: July twenty twenty-five at sixty-eight thousand four hundred dollars. This May is running twenty-three percent ahead of last year. INNtelligence uses this history to make smarter forward-looking recommendations — because the best predictor of future demand is what actually happened before.",
  s12: "Pricing Power Score: eighty-four out of one hundred. That means your reputation gives you the right to charge a premium. Guests consistently cite location, breakfast, staff, and river views. One area to watch: value mentions have dropped slightly in the last thirty days. INNtelligence recommendation: add a complimentary Lowcountry welcome amenity to check-ins this month — local jam, pralines, a handwritten note. Cost: under eight dollars per room. Impact on perceived value: significant.",
  s13: "Rain forecasted for this Saturday. INNtelligence automatically flags this for food and beverage: push The Parlor's indoor dinner reservations, promote the rooftop bar's covered section, consider a rainy day package for guests already booked. Weather isn't something you can control. How you respond to it is.",
  s14: "Finally — the Gift Shop. Guests who fall in love with their experience want to bring it home. Bay Street Inn sells Comphy bedding — the exact sheets from the rooms — and authentic Murano glass by Gino Mazzuccato, sourced directly from Venice, Italy. This month: three thousand one hundred and sixty dollars in gift shop revenue with zero additional staff. That is pure margin on top of room revenue.",
}

const STEPS = [
  { id: 'step_01', title: 'Good Morning', duration: 90, Sim: S1, narration: N.s1, callouts: [["Today's Avg Rate", '$487'], ['RevPAR', '$365'], ['Market Pressure', '7/10'], ['Alert', 'Competitor rate drop']] },
  { id: 'step_02', title: 'Competitive Intel', duration: 150, Sim: S2, narration: N.s2, callouts: [['Rhett House', 'Down $40 overnight'], ['Your Rate', '$445 (hold)'], ['Comp Average', '$412'], ['Your Premium', '+8% justified']] },
  { id: 'step_03', title: 'Rate Calendar', duration: 180, Sim: S3, narration: N.s3, callouts: [['WF Room 1 · Fri', '$502'], ['WF Room 1 · Sat', '$547'], ['Grand Parlor Suite', '$721'], ['Festival Premium', '+29% above rack']] },
  { id: 'step_04', title: 'Revenue Intelligence', duration: 120, Sim: S4, narration: N.s4, callouts: [['Gap Nights Found', '3'], ['Estimated Recovery', '$840'], ['Friday Orphans', '6'], ['Top Action', 'Lower rate $22 + email']] },
  { id: 'step_05', title: 'Guest CRM', duration: 120, Sim: S5, narration: N.s5, callouts: [['Lapsed VIP Guests', '12'], ['Margaret Chen', '4 stays · $3,840'], ['Last Visit', '7 months ago'], ['Win-back Potential', '$5,400']] },
  { id: 'step_06', title: 'ROI Performance', duration: 90, Sim: S6, narration: N.s6, callouts: [['ROI', '8.7× in 90 days'], ['Water Festival Lift', '+$4,200'], ['Win-back Revenue', '+$2,100'], ['ADR vs Last Year', '+18%']] },
  { id: 'step_07', title: 'F&B Yield', duration: 90, Sim: S7, narration: N.s7, callouts: [['Monthly F&B Revenue', '$21,800'], ['Thursday Gap', '−$2,100 vs Fri'], ['Recommendation', 'Thursday Supper'], ['Projected Lift', '+$1,400/mo']] },
  { id: 'step_08', title: 'Private Events', duration: 120, Sim: S8, narration: N.s8, callouts: [['Thompson Wedding', '$28,662'], ['Individual Bookings', '$15,960'], ['Event Premium', '$12,702'], ['Recommendation', 'ACCEPT']] },
  { id: 'step_09', title: 'Events Calendar', duration: 60, Sim: S9, narration: N.s9, callouts: [['Days to Water Festival', '9'], ['Festival Duration', '13 days'], ['Waterfront Occupancy', '85%'], ['Expected Premium', '+35–40%']] },
  { id: 'step_10', title: 'Packages', duration: 60, Sim: S10, narration: N.s10, callouts: [['Romance Package', '$4,781/mo'], ['Proposal Potential', '$3,200/mo'], ['Inns Offering Proposal', '12%'], ['Action', 'One-click activate']] },
  { id: 'step_11', title: 'Historical Performance', duration: 45, Sim: S11, narration: N.s11, callouts: [['Best Month Ever', 'Jul 2025 · $68,400'], ['Current vs LY', '+23%'], ['12-Month Trend', 'Consistently up'], ['YoY Growth', '18%']] },
  { id: 'step_12', title: 'Reputation', duration: 45, Sim: S12, narration: N.s12, callouts: [['Pricing Power Score', '84/100'], ['TripAdvisor', '4.7 ★'], ['Google', '4.8 ★'], ['Top Keywords', 'Location, Views']] },
  { id: 'step_13', title: 'Weather', duration: 45, Sim: S13, narration: N.s13, callouts: [['Saturday', 'Rain forecasted'], ['F&B Action', 'Push indoor dining'], ['Rooftop', 'Promote covered section'], ['Guest Alert', 'Rainy-day package']] },
  { id: 'step_14', title: 'Gift Shop', duration: 45, Sim: S14, narration: N.s14, callouts: [['Monthly Gift Revenue', '$3,160'], ['Top Item', 'Comphy $1,920'], ['Murano Glass', '$1,240'], ['Margin', 'No extra staff']] },
]

// ── Web Speech fallback ──────────────────────────────────────────────────────
function speakFallback(text) {
  try {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.rate = 0.92; u.pitch = 1.0
    const voices = window.speechSynthesis.getVoices() || []
    const v = voices.find((x) => /en[-_]US/i.test(x.lang))
    if (v) u.voice = v
    window.speechSynthesis.speak(u)
  } catch { /* ignore */ }
}
function stopSpeak() { try { window.speechSynthesis.cancel() } catch { /* ignore */ } }

// ── Main component ───────────────────────────────────────────────────────────
export default function Tour() {
  const [phase, setPhase] = useState(TEST_MS ? 'opening' : 'prep')
  const [prep, setPrep] = useState({ done: 0, total: STEPS.length, label: 'Preparing your tour…' })
  const [step, setStep] = useState(0)
  const [mode, setMode] = useState('manual')
  const [paused, setPaused] = useState(false)
  const [muted, setMuted] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [usingFallback, setUsingFallback] = useState(false)

  const audioRef = useRef(null)
  const advancedRef = useRef(-1)   // guards against double-advance per step
  const mutedRef = useRef(muted)
  const modeRef = useRef(mode)
  useEffect(() => { mutedRef.current = muted }, [muted])
  useEffect(() => { modeRef.current = mode }, [mode])

  // ── Prep: generate all audio sequentially (skipped in test mode) ───────────
  useEffect(() => {
    if (TEST_MS) return
    let cancelled = false
    async function run() {
      try {
        const status = await fetch('/api/tour/audio-status').then((r) => r.json())
        if (!status.configured) { setUsingFallback(true); setPhase('opening'); return }
        if (status.all_ready) { setPrep((p) => ({ ...p, done: STEPS.length })); setPhase('opening'); return }
        const have = new Set(status.generated || [])
        let done = have.size
        setPrep({ done, total: STEPS.length, label: `Generating narration… ${done}/${STEPS.length}` })
        for (let i = 0; i < STEPS.length; i++) {
          if (cancelled) return
          const s = STEPS[i]
          if (have.has(s.id)) continue
          setPrep({ done, total: STEPS.length, label: `Step ${i + 1} of ${STEPS.length} — generating audio…` })
          const res = await fetch('/api/tour/generate-audio', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_id: s.id, narration_text: s.narration }),
          }).then((r) => r.json()).catch(() => ({ ok: false }))
          if (!res.ok) setUsingFallback(true)
          done += 1
          setPrep({ done, total: STEPS.length, label: `Step ${i + 1} of ${STEPS.length} — ready` })
        }
        if (!cancelled) setPhase('opening')
      } catch {
        if (!cancelled) { setUsingFallback(true); setPhase('opening') }
      }
    }
    run()
    return () => { cancelled = true }
  }, [])

  const cur = STEPS[step]
  const stepMs = TEST_MS || cur.duration * 1000

  const goNext = () => {
    if (advancedRef.current === step) return // already advanced for this step
    advancedRef.current = step
    if (step < STEPS.length - 1) setStep(step + 1)
    else setPhase('closing')
  }
  const goPrev = () => {
    advancedRef.current = -1
    if (phase === 'closing') { setPhase('running'); setStep(STEPS.length - 1); return }
    if (step > 0) setStep(step - 1)
  }

  // reset per-step state + advance guard whenever the step changes
  useEffect(() => { advancedRef.current = -1; setElapsed(0) }, [step, phase])

  // ── Audio playback per step ────────────────────────────────────────────────
  useEffect(() => {
    if (phase !== 'running') return undefined
    stopSpeak()
    if (TEST_MS) return undefined // no audio in test mode
    const a = new Audio(`/api/tour/audio/${cur.id}`)
    a.muted = mutedRef.current
    audioRef.current = a
    a.addEventListener('ended', () => { if (modeRef.current === 'auto') goNext() })
    a.play().catch(() => {
      // ElevenLabs/file unavailable → browser voice
      setUsingFallback(true)
      if (!mutedRef.current) speakFallback(cur.narration)
    })
    return () => {
      try { a.pause() } catch { /* ignore */ }
      audioRef.current = null
      stopSpeak()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, step])

  // keep audio muted state in sync
  useEffect(() => {
    if (audioRef.current) audioRef.current.muted = muted
    if (muted) stopSpeak()
  }, [muted])

  // ── Auto-advance timer (useRef so it survives re-renders) ──────────────────
  useEffect(() => {
    if (phase !== 'running' || mode !== 'auto' || paused) return undefined
    const id = setTimeout(goNext, stepMs)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, step, mode, paused])

  // progress ticker (visual only)
  useEffect(() => {
    if (phase !== 'running' || paused) return undefined
    const id = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(id)
  }, [phase, step, paused])

  const completed = STEPS.slice(0, step).reduce((a, s) => a + s.duration, 0)
  const progress = phase === 'closing' ? 100 : phase !== 'running' ? 0
    : Math.min(100, ((completed + Math.min(elapsed, cur.duration)) / TOTAL_SECONDS) * 100)

  const begin = (m) => { setMode(m); setPaused(false); setStep(0); advancedRef.current = -1; setPhase('running') }
  const restart = () => { stopSpeak(); setPhase('opening'); setStep(0); setPaused(false) }

  return (
    <div data-tour-steps={STEPS.length} data-tour-total={TOTAL_SECONDS}
         className="relative -m-6 h-[calc(100vh-56px)] bg-navy text-white overflow-hidden flex flex-col">
      <style>{`@keyframes tourFloat{0%{transform:translateY(0);opacity:.5}50%{opacity:1}100%{transform:translateY(-28px);opacity:.35}}`}</style>

      {phase === 'prep' && <Prep prep={prep} />}
      {phase === 'opening' && <Opening usingFallback={usingFallback} onBegin={() => begin('manual')} onAuto={() => begin('auto')} />}
      {phase === 'running' && (
        <Running cur={cur} step={step} progress={progress} mode={mode} paused={paused} muted={muted} usingFallback={usingFallback}
          onNext={goNext} onPrev={goPrev} onPause={() => setPaused((p) => !p)} onMute={() => setMuted((m) => !m)} onRestart={restart} />
      )}
      {phase === 'closing' && <Closing onRestart={restart} />}
    </div>
  )
}

// ── Prep screen ──────────────────────────────────────────────────────────────
function Prep({ prep }) {
  const pct = Math.round((prep.done / prep.total) * 100)
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
      <div className="text-gold font-extrabold text-3xl tracking-tight">INNtelligence</div>
      <div className="text-white/70 mt-4 text-lg">Preparing your tour…</div>
      <div className="text-gold-light/70 text-sm mt-1">{prep.label}</div>
      <div className="w-72 h-2 bg-white/10 rounded-full overflow-hidden mt-5"><div className="h-full bg-gold transition-all" style={{ width: `${pct}%` }} /></div>
      <div className="text-white/40 text-xs mt-2">Generating studio narration with ElevenLabs · cached after first visit</div>
    </div>
  )
}

// ── Opening screen ───────────────────────────────────────────────────────────
function Opening({ onBegin, onAuto, usingFallback }) {
  return (
    <div className="relative flex-1 flex flex-col items-center justify-center text-center px-6"
         style={{ background: 'radial-gradient(circle at 50% 20%, #14385f 0%, #0a2342 60%, #061629 100%)' }}>
      <div className="absolute inset-0 pointer-events-none">
        {Array.from({ length: 16 }).map((_, i) => (
          <span key={i} className="absolute rounded-full bg-gold" style={{ width: 3 + (i % 3), height: 3 + (i % 3), left: `${(i * 53) % 100}%`, top: `${(i * 37) % 100}%`, opacity: 0.4, animation: `tourFloat ${6 + (i % 5)}s ease-in-out ${i * 0.4}s infinite` }} />
        ))}
      </div>
      <div className="relative z-10">
        <div className="text-gold font-extrabold tracking-tight text-5xl sm:text-6xl">INNtelligence</div>
        <p className="text-white text-2xl sm:text-3xl mt-8 font-semibold">19 rooms. One goal: maximum revenue.</p>
        <p className="text-gold-light text-lg mt-2">See how The Bay Street Inn does it.</p>
        <div className="flex items-center justify-center gap-4 mt-10">
          <button onClick={onBegin} aria-label="Begin Tour" className="px-8 py-3 rounded-xl border border-gold/60 text-gold font-semibold hover:bg-gold/10 transition-colors">▷ Begin Tour</button>
          <button onClick={onAuto} aria-label="Auto-Play Tour" className="px-8 py-3 rounded-xl bg-gold text-navy font-bold hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">⏵ Auto-Play Tour</button>
        </div>
        <div className="text-white/40 text-xs mt-4">No signup required · 22 minutes · Sound on for best experience</div>
        {usingFallback && <div className="text-amber-300/80 text-xs mt-2">Studio narration unavailable — using browser voice.</div>}
      </div>
    </div>
  )
}

// ── Running (two-panel) ──────────────────────────────────────────────────────
function Running({ cur, step, progress, mode, paused, muted, usingFallback, onNext, onPrev, onPause, onMute, onRestart }) {
  const Sim = cur.Sim
  return (
    <>
      <div className="flex-1 flex min-h-0">
        {/* LEFT 60% — simulated screen */}
        <div className="w-3/5 p-6 overflow-y-auto" style={{ background: 'radial-gradient(circle at 40% 30%, #0d2b4e 0%, #061629 75%)' }}>
          <div className="rounded-2xl bg-navy/70 backdrop-blur p-6 ring-2 ring-gold/60 shadow-[0_0_50px_rgba(201,168,76,0.25)] min-h-full">
            <Sim />
          </div>
        </div>
        {/* RIGHT 40% — narration + metrics + nav */}
        <div className="w-2/5 border-l border-white/10 bg-navy-dark/40 flex flex-col min-h-0">
          <div className="p-5 overflow-y-auto flex-1">
            <div className="text-gold-light text-xs uppercase tracking-wide">Step {step + 1} of {STEPS.length} · {cur.title}</div>
            <p className="text-white text-lg leading-relaxed mt-3">{cur.narration}</p>
            {usingFallback && <div className="text-amber-300/70 text-[11px] mt-2">Using browser voice</div>}
          </div>
          <div className="p-5 border-t border-white/10 grid grid-cols-2 gap-2">
            {cur.callouts.map((c) => (
              <div key={c[0]} className="rounded-lg bg-gold/10 border border-gold/25 p-3">
                <div className="text-gold font-bold text-sm leading-tight">{c[1]}</div>
                <div className="text-white/50 text-[10px] mt-0.5">{c[0]}</div>
              </div>
            ))}
          </div>
          <div className="p-4 border-t border-white/10 flex items-center gap-2">
            <button onClick={onPrev} aria-label="Previous step" className="flex-1 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm">⏮ Prev</button>
            {mode === 'auto' && <button onClick={onPause} aria-label="Play/Pause" className="flex-1 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm">{paused ? '⏵' : '⏸'}</button>}
            <button onClick={onNext} aria-label="Next step" className="flex-1 py-2 rounded-lg bg-gold text-navy font-semibold text-sm hover:bg-gold-light">Next ⏭</button>
          </div>
        </div>
      </div>

      {/* CONTROLS BAR — full width bottom */}
      <div className="border-t border-white/10 bg-navy-dark/60 px-6 py-3">
        <div className="h-2 bg-white/10 rounded-full overflow-hidden mb-2"><div className="h-full bg-gold transition-all duration-500" style={{ width: `${progress}%` }} /></div>
        <div className="flex items-center justify-between text-sm">
          <div className="text-white/50 text-xs">Step {step + 1} of {STEPS.length} · {Math.round(progress)}% of 22 min</div>
          <div className="flex items-center gap-2">
            <button onClick={onMute} aria-label="Mute" className={`px-3 py-1.5 rounded-lg text-xs ${muted ? 'bg-rose-500/30 text-rose-200' : 'bg-white/10 hover:bg-white/20'}`}>{muted ? '🔇 Muted' : '🔊 Sound'}</button>
            <button onClick={onRestart} aria-label="Restart" className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs">↺ Restart</button>
            <Link to="/" className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs">✕ Exit Tour</Link>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Closing screen ───────────────────────────────────────────────────────────
function Closing({ onRestart }) {
  const stats = [['8.7×', 'ROI in first 90 days'], ['23%', 'RevPAR above comp set'], ['$28,662', 'private event identified'], ['$840', 'gap night recovery this week']]
  const tiers = [
    { name: 'Starter', price: '$149', feats: ['1 property, up to 20 rooms', '5 competitors monitored', 'Rate Calendar & Competitive Intel', 'Email support'] },
    { name: 'Professional', price: '$299', popular: true, feats: ['1 property, unlimited rooms', '9 competitors w/ tier intelligence', 'All 14 screens incl. F&B & CRM', 'Private Events calculator', 'Live competitor scraping', 'Priority support'] },
    { name: 'Multi-Property', price: '$499', feats: ['Up to 5 properties', 'Everything in Professional', 'White-label option', 'Dedicated account manager'] },
  ]
  return (
    <div className="flex-1 overflow-y-auto text-center px-6 py-10" style={{ background: 'radial-gradient(circle at 50% 15%, #14385f, #061629)' }}>
      <div className="text-gold font-extrabold tracking-tight text-3xl">INNtelligence</div>
      <h1 className="text-white text-3xl sm:text-4xl font-extrabold mt-3">Your revenue. Maximized. Every morning.</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8 max-w-4xl mx-auto">
        {stats.map((s) => <div key={s[1]} className="rounded-xl bg-navy/60 border border-gold/30 p-5"><div className="text-gold text-3xl font-extrabold">{s[0]}</div><div className="text-white/60 text-xs mt-2">{s[1]}</div></div>)}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-10 max-w-4xl mx-auto text-left">
        {tiers.map((t) => (
          <div key={t.name} className={`rounded-2xl p-5 border relative ${t.popular ? 'border-gold bg-gold/10 sm:scale-105' : 'border-white/15 bg-navy/50'}`}>
            {t.popular && <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gold text-navy text-[10px] font-bold px-3 py-0.5 rounded-full">MOST POPULAR</div>}
            <div className="text-gold-light text-sm font-semibold uppercase tracking-wide">{t.name}</div>
            <div className="mt-2"><span className="text-3xl font-extrabold text-white">{t.price}</span><span className="text-white/40 text-sm">/month</span></div>
            <ul className="mt-3 space-y-1 text-sm text-white/70">{t.feats.map((f) => <li key={f}>✓ {f}</li>)}</ul>
          </div>
        ))}
      </div>
      <a href="mailto:hello@inntelligence.app?subject=Start%20my%20free%2030-day%20trial" className="mt-10 inline-block px-10 py-4 rounded-xl bg-gold text-navy font-bold text-lg hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">Start Your Free 30-Day Trial</a>
      <div className="text-white/40 text-sm mt-3">No credit card required. Cancel anytime. Setup in under 10 minutes.</div>
      <div className="text-white/50 text-sm mt-1">Questions? <span className="text-gold">hello@inntelligence.app</span></div>
      <button onClick={onRestart} className="mt-6 text-white/40 text-xs underline hover:text-white/70">↺ Replay the tour</button>
    </div>
  )
}

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
// Narration text uses the hyphenated "Inn-telligence" so the ElevenLabs TTS
// pronounces it "Inn-telligence". Captions render "INNtelligence" via display().
const OPENING_NARRATION = "Inn-telligence was built by a pricing professional with eleven years of experience building revenue optimization systems for one of America's largest telecommunications companies. Systems that are now enterprise standard. Systems that generate hundreds of millions of dollars in optimized revenue. He looked at the boutique inn industry and saw the same problem he had solved in telecom: owners making pricing decisions based on gut feel, leaving significant revenue on the table every single night. So he built Inn-telligence. The same institutional-grade pricing intelligence that Fortune 500 companies pay millions for — built specifically for boutique inns, starting at a hundred and forty-nine dollars a month. This is The Bay Street Inn in Beaufort, South Carolina. Nineteen rooms. Let's show you what Inn-telligence does for an inn like this every single morning."
const CLOSING_NARRATION = "Eleven years building pricing systems for Fortune 500 companies. The same methodology. The same rigor. Now available to every boutique inn owner who has ever wondered if they are charging the right rate. Inn-telligence combines artificial intelligence with real-world pricing expertise built by someone who has spent over a decade doing this professionally — and who now owns a boutique inn himself. Every recommendation is AI-generated and expert-validated. Not just an algorithm. Not just data. Pricing intelligence with the judgment to know what the data means. Bay Street Inn. Nineteen rooms. Maximum revenue. Every single day. Your inn deserves the same. Start your free thirty-day trial today. No credit card required."

const N = {
  s1: "It's seven oh two on a Friday morning in Beaufort, South Carolina. The owner of Bay Street Inn opens Inn-telligence. Before the first cup of coffee is finished, she knows everything she needs to know about today. Average rate across all nineteen rooms: four hundred and eighty-seven dollars. RevPAR: three hundred and sixty-five dollars. Market pressure score seven out of ten — demand is building. Four active events in the next thirty days. And one alert at the top of the screen: a competitor dropped rates overnight. This is what running an inn looks like with Inn-telligence. Every morning starts with clarity instead of guesswork. Let's walk through exactly what she does next.",
  s2: "The first screen every morning is Competitive Intelligence. Here is something most inn owners do not know: your competitors are adjusting their rates constantly — sometimes daily, sometimes overnight while you sleep. Without a system monitoring them around the clock, you are always reacting instead of leading. Inn-telligence monitors nine properties in the Beaufort market twenty-four hours a day, updating rates every morning at six AM. The AI identifies patterns in how each competitor prices — when they discount, how aggressively, and what triggers it. Over time it learns their behavior and predicts their next move before they make it. Your competitors are organized into three tiers based on how directly they compete for your guests. Direct competitors — Rhett House Inn, Cuthbert House Inn, Anchorage 1770, and 607 Bay Inn — these four properties drive your rate recommendations with the highest weight. Now filter to Waterfront rooms specifically. Rhett House and City Loft Hotel immediately gray out. They do not have true waterfront rooms. Inn-telligence never compares you to a property that is not actually competing for the same guest on the same product. This is the kind of nuance that comes from real hospitality expertise baked into the system — not just an algorithm pulling rates off a website. Your direct comp set average for waterfront rooms tonight is four hundred and twelve dollars. Inn-telligence recommends holding at four hundred and forty-five dollars — an eight percent premium. Why is that premium justified? Your TripAdvisor score is higher. Your waterfront views are rated better by guests who have stayed at both properties. And the market pressure score of seven out of ten means demand is strong enough to support it. The rate drop alert: Rhett House dropped forty dollars overnight. They have availability for Water Festival weekend — they are nervous. Cuthbert House has not moved. Inn-telligence recommendation: hold your rates. Your strongest competitor is confident. You should be too. That recommendation comes from eleven years of pricing experience encoded into every decision the AI makes. It does not just show you data — it tells you what to do with it.",
  s3: "The Rate Calendar is where Inn-telligence's pricing expertise becomes real money. Every inn owner knows they should be charging more during peak season and less during slow periods. But knowing that and actually doing it — room by room, night by night, accounting for events, competitor moves, lead time, and demand signals — is a full-time job. It is what a professional revenue manager does. Inn-telligence does it automatically, for every room, every night. Select Waterfront rooms and look at Water Festival weekend — Friday July seventeenth through Sunday July nineteenth. Waterfront Room 1 on Friday: five hundred and two dollars. Twenty-nine percent above rack rate. Here is the exact reasoning. Seasonal index: one point three for peak July. Water Festival demand multiplier: one point three five — thirteen consecutive days of the biggest event in Beaufort. Lead time urgency: nine days out, demand is building. Competitor average for comparable waterfront rooms: four hundred and twelve dollars. Reputation premium: eight percent above comp set, justified. Confidence level: HIGH. Every number in that calculation comes from a methodology developed over eleven years of professional pricing practice. The same approach used to optimize hundreds of millions of dollars in revenue — now running automatically for your nineteen rooms. Click accept. Rate is set. One click. Done. Saturday: five hundred and forty-seven. Grand Parlor Suite: seven hundred and twenty-one. All nineteen rooms, Water Festival weekend, individually priced in under sixty seconds. Now look at Tuesday July twenty-first — mid-week after the festival peak. Garden Room 3: two hundred and forty-nine dollars. Below rack rate. The engine knows demand drops sharply mid-week after the festival and recommends a strategic discount to fill the room rather than hold a rate you will not achieve. That balance — charging premium when you can, being strategic when you should — is exactly what separates professional revenue management from guesswork. And now every inn owner has access to it.",
  s4: "This is one of the screens I am most proud of, because it solves a problem I saw inn owners struggling with long before Inn-telligence existed. The orphan gap problem. You have a Saturday booking for Waterfront Room 1. Friday before it: empty. Sunday after it: empty. Those nights are almost impossible to fill at full price because most guests want a minimum two-night stay. Without a system watching your calendar, those nights just go empty. You never even think about them until checkout day when it is too late. Inn-telligence finds every orphan gap automatically and gives you specific actions to take right now — not generic suggestions, but calculated recommendations based on your actual guest data and current market conditions. For this Friday gap: contact the Saturday guest and offer Friday at a fifteen percent discount. They are already coming — the incremental cost to you is almost nothing and the revenue is pure upside. If that does not work by Wednesday: send a targeted email to past guests within a hundred and fifty miles who have stayed in waterfront rooms before. Frame it as an exclusive offer for past guests. This week alone: three orphan gaps, eight hundred and forty dollars in recoverable revenue that would have gone empty without this screen. The ten AI recommendations below are generated fresh every morning from your booking data, competitor rates, and the local events calendar. Human pricing expertise, encoded into an algorithm, running while you sleep. That is Inn-telligence.",
  s5: "The best revenue you will ever generate comes from guests who already love you. Win-back marketing — reaching out to past guests who have not returned — consistently outperforms acquiring new guests by three to five times in both conversion rate and lifetime value. Every major hotel chain has known this for decades and built entire CRM systems around it. Boutique inn owners have had no equivalent tool. Until now. Inn-telligence builds a complete intelligence profile on every guest who has ever stayed with you. Look at Catherine Beaumont from Charlotte, North Carolina. Four stays. Lifetime spend: three thousand eight hundred and forty dollars. Always books waterfront. Last visit: seven months ago. Catherine is a Lapsed VIP. She loved Bay Street Inn enough to come back three times. Something got in the way. Maybe she just needed someone to reach out. Campaign Manager. Lapsed VIP segment. Win-Back template. The email personalizes itself — her name, her preferred room, a ten percent loyalty rate for her next waterfront stay. Twelve guests match this profile right now. If three of them book a two-night waterfront stay — conservative estimate based on industry win-back conversion rates — that is five thousand four hundred dollars in recovered revenue. From fifteen minutes of a Friday morning. From guests who already chose you once.",
  s6: "I built Inn-telligence to be accountable. Not just to show you data — to show you what that data is worth in actual dollars. The ROI Performance screen is the most transparent thing in hospitality software. It shows you exactly what Inn-telligence has generated and exactly what it missed. Both. Bay Street Inn. Ninety days. Eight point seven times return. Water Festival dynamic pricing: four thousand two hundred dollars above what flat-rate pricing would have generated. Gullah Festival surge: eighteen hundred and fifty. Win-back campaigns: two thousand one hundred. And the misses — because I show you those too. Two Thursday nights in April went unbooked when a modest rate reduction would likely have filled them. Six hundred and eighty dollars in missed revenue. Inn-telligence shows you the misses because that transparency is how the recommendations get smarter over time. The AI learns from every empty room, not just the ones it filled. RevPAR twenty-three percent above comp set. ADR up eighteen percent year over year. Subscription cost for the quarter: eight hundred and ninety-seven dollars. Return: seven thousand eight hundred and three dollars. One Water Festival weekend paid for the year.",
  s7: "For inns with a restaurant or bar, food and beverage is a revenue center that most owners dramatically underanalyze. I know this from experience. The same yield management principles that work for room pricing work for restaurant seats and bar tops. Day of week. Time of day. Event influence. Guest mix. All of it matters. Inn-telligence applies those principles to The Parlor and The Rooftop at Bay Street Inn automatically. Thursday Rooftop: eight hundred and ninety dollars. Friday: two thousand one hundred. That gap tells a story. Guests arriving Thursday have dinner plans elsewhere. The Rooftop has empty seats on the most beautiful sunset evening of the week. Recommendation: Thursday Lowcountry Sunset Supper. Fixed price, three courses, sixty-five dollars per person, rooftop cocktail hour included. Inns that introduce a Thursday evening special see twenty to twenty-five percent revenue lift. At Bay Street Inn's cover count: fourteen hundred additional dollars per month. Sixteen thousand eight hundred dollars per year. One menu decision.",
  s8: "This is the screen that surprises people most when they first see Inn-telligence. Because nobody else has built it. Every revenue management system in hospitality is built around transactional nightly bookings. None of them help you price a wedding. None of them tell you whether to accept a corporate buyout on a festival weekend. None of them calculate the exact premium you should charge for exclusivity. I built this screen because I know from personal experience that group events are where boutique inns leave the most money on the table. Elizabeth and William Hartley. Wedding inquiry. August twenty-third. Forty-five guests. Full buyout. The calculator runs in seconds. Room block: fifteen thousand nine hundred and sixty. Event space: fifteen hundred. Food and beverage: five thousand six hundred and twenty-five. Setup: eight hundred. Exclusivity premium: four thousand seven hundred and seventy-seven. Total: twenty-eight thousand six hundred and sixty-two dollars. Compare to individual bookings that weekend: fifteen thousand nine hundred and sixty. Wedding premium: twelve thousand seven hundred and two dollars. Accept. Now change the date to July nineteenth — Water Festival opening weekend. The conflict alert fires immediately. Festival individual pricing: nineteen thousand two hundred. The wedding offer is below that threshold. Recommendation: Decline or negotiate above festival pricing. That one calculation, on that one date change, protects thousands of dollars that most inn owners would never have thought to calculate.",
  s9: "The Weddings screen is designed to be shared directly with couples who are considering Bay Street Inn for their celebration. Four packages, from intimate elopements at twenty-five hundred to forty-five hundred dollars, all the way to Grand Celebrations for seventy-five guests at twenty-eight to forty-five thousand. Every package includes the full inclusions list, deposit schedule, and cancellation terms — everything a couple needs to make a confident decision. The inquiry form captures everything you need to qualify a wedding lead and routes it to your event coordinator immediately. Your wedding business runs through Inn-telligence from first contact to confirmed booking. No spreadsheets. No pricing uncertainty. Every date checked against your revenue calendar before you say yes.",
  s10: "Inn-telligence tracks every event in the Beaufort market — from the Original Gullah Festival on Memorial Day weekend to Parris Island Marine Corps graduations that fill rooms eight times a year. Understanding your local events calendar is not optional for a boutique inn in an event-driven market like Beaufort. It is the foundation of everything else. Switch to Next Six Months and every revenue opportunity is laid out in front of you, with pricing impact and recommended action for each. The Beaufort Water Festival: thirty to forty percent premium, rooms selling out sixty days in advance. Inn-telligence started adjusting your rates ninety days ago. Penn Center Heritage Days in November: historically underpriced by most Bay Street properties. Twenty percent premium opportunity. You are planning months ahead now, not reacting the week of.",
  s11: "The Romance Package generates four thousand seven hundred and eighty-one dollars per month at Bay Street Inn. Nearly fifty-eight thousand dollars a year. From one package offering at eighty-five dollars above rack rate. The Available Packages tab shows what comparable inns offer that Bay Street Inn does not — yet. The Proposal Package is offered by only twelve percent of comparable boutique inns. Low competition. High perceived value. One hundred and ninety-five dollar premium. Estimated monthly revenue: three thousand two hundred dollars. Thirty-eight thousand four hundred dollars a year from one toggle switch. Inn-telligence monitors what packages the market offers and identifies the gaps specific to your property and guest profile. The opportunities are always there. Now you can see them.",
  s12: "Twenty-four months of performance data so you always know where you have been and where you are going. Best month ever: July twenty twenty-five, sixty-eight thousand four hundred dollars. This May running twenty-three percent ahead of last year. The seasonal pattern becomes visible over time — July and October your peaks, January and February your valleys. Inn-telligence uses this history to build smarter forward recommendations. It knows your property. It learns your patterns. Every month the model gets more accurate.",
  s13: "Pricing power comes from reputation. You cannot charge a premium if guests do not believe you are worth it. And you cannot know what guests think if you are not systematically listening. Pricing Power Score: eighty-four out of one hundred. That number means Bay Street Inn has earned the right to price above the market average. Top guest keywords: location, breakfast, staff, views. One trend to watch: value mentions dropping slightly. Recommendation: add a Lowcountry welcome amenity to all check-ins. Local jam, pralines, handwritten note. Under eight dollars per room. The kind of gesture that turns a four-star review into a five-star review and a five-star review into a repeat guest.",
  s14: "The final revenue stream — and one of the most satisfying to build into Inn-telligence, because it turns a guest's love for their experience into ongoing revenue long after checkout. Comphy bedding — the exact sheets on every bed at Bay Street Inn. Eight sets sold this month. Nineteen hundred and twenty dollars. Pure margin. Murano glass by Gino Mazzuccato — authentic hand-blown glass from the island of Murano in Venice, Italy, displayed throughout the inn, available to purchase and ship anywhere in the United States. Three pieces this month. Twelve hundred and forty dollars. Three thousand one hundred and sixty dollars in gift shop revenue. Zero additional staff. Guests take home a piece of Bay Street Inn and a reason to come back.",
}

const STEPS = [
  { id: 'step_01', title: 'Good Morning', duration: 90, Sim: S1, narration: N.s1, callouts: [["Today's Avg Rate", '$487'], ['RevPAR', '$365'], ['Market Pressure', '7/10'], ['Alert', 'Competitor rate drop']] },
  { id: 'step_02', title: 'Competitive Intel', duration: 150, Sim: S2, narration: N.s2, callouts: [['Rhett House', 'Down $40 overnight'], ['Your Rate', '$445 (hold)'], ['Comp Average', '$412'], ['Your Premium', '+8% justified']] },
  { id: 'step_03', title: 'Rate Calendar', duration: 180, Sim: S3, narration: N.s3, callouts: [['WF Room 1 · Fri', '$502'], ['WF Room 1 · Sat', '$547'], ['Grand Parlor Suite', '$721'], ['Festival Premium', '+29% above rack']] },
  { id: 'step_04', title: 'Revenue Intelligence', duration: 120, Sim: S4, narration: N.s4, callouts: [['Gap Nights Found', '3'], ['Estimated Recovery', '$840'], ['Friday Orphans', '6'], ['Top Action', 'Lower rate $22 + email']] },
  { id: 'step_05', title: 'Guest CRM', duration: 120, Sim: S5, narration: N.s5, callouts: [['Lapsed VIP Guests', '12'], ['Catherine Beaumont', '4 stays · $3,840'], ['Last Visit', '7 months ago'], ['Win-back Potential', '$5,400']] },
  { id: 'step_06', title: 'ROI Performance', duration: 90, Sim: S6, narration: N.s6, callouts: [['ROI', '8.7× in 90 days'], ['Water Festival Lift', '+$4,200'], ['Win-back Revenue', '+$2,100'], ['ADR vs Last Year', '+18%']] },
  { id: 'step_07', title: 'F&B Yield', duration: 90, Sim: S7, narration: N.s7, callouts: [['Monthly F&B Revenue', '$21,800'], ['Thursday Rooftop', '$890 vs $2,100 Fri'], ['Recommendation', 'Thursday Sunset Supper'], ['Projected Lift', '+$1,400/mo']] },
  { id: 'step_08', title: 'Private Events', duration: 120, Sim: S8, narration: N.s8, callouts: [['Hartley Wedding', '$28,662'], ['Individual Bookings', '$15,960'], ['Wedding Premium', '$12,702'], ['Festival-date conflict', 'Decline/negotiate']] },
  { id: 'step_09', title: 'Weddings', duration: 60, Sim: SWED, narration: N.s9, callouts: [['Packages', '4 tiers'], ['From', '$2,500 elopement'], ['Up to', '$45,000 grand'], ['Leads', 'Routed to coordinator']] },
  { id: 'step_10', title: 'Events Calendar', duration: 60, Sim: S9, narration: N.s10, callouts: [['Water Festival', '+30–40% premium'], ['Penn Center Heritage', '+20% opportunity'], ['Rates adjusted', '90 days ahead'], ['Parris Island', '8× per year']] },
  { id: 'step_11', title: 'Packages', duration: 60, Sim: S10, narration: N.s11, callouts: [['Romance Package', '$4,781/mo'], ['Annual', '~$58,000'], ['Proposal Potential', '$3,200/mo'], ['Inns Offering Proposal', '12%']] },
  { id: 'step_12', title: 'Historical Performance', duration: 45, Sim: S11, narration: N.s12, callouts: [['Best Month Ever', 'Jul 2025 · $68,400'], ['Current vs LY', '+23%'], ['Peaks', 'July & October'], ['Valleys', 'Jan & Feb']] },
  { id: 'step_13', title: 'Reputation', duration: 45, Sim: S12, narration: N.s13, callouts: [['Pricing Power Score', '84/100'], ['TripAdvisor', '4.7 ★'], ['Google', '4.8 ★'], ['Watch', 'Value mentions dipping']] },
  { id: 'step_14', title: 'Gift Shop', duration: 45, Sim: S14, narration: N.s14, callouts: [['Monthly Gift Revenue', '$3,160'], ['Comphy Bedding', '$1,920'], ['Murano Glass', '$1,240'], ['Margin', 'No extra staff']] },
]

// Captions show the brand as "INNtelligence" while TTS receives "Inn-telligence".
const display = (text) => text.replace(/Inn-telligence/g, 'INNtelligence')

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
  const [prep, setPrep] = useState({ done: 0, total: STEPS.length + 2, label: 'Preparing your tour…' })
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

  // Opening + 14 steps + closing narration, generated/cached in this order.
  const PREP_ITEMS = [
    { id: 'opening', narration: OPENING_NARRATION },
    ...STEPS.map((s) => ({ id: s.id, narration: s.narration })),
    { id: 'closing', narration: CLOSING_NARRATION },
  ]

  // ── Prep: generate all audio sequentially (skipped in test mode) ───────────
  useEffect(() => {
    if (TEST_MS) return
    let cancelled = false
    const total = PREP_ITEMS.length
    async function run() {
      try {
        const status = await fetch('/api/tour/audio-status').then((r) => r.json())
        if (!status.configured) { setUsingFallback(true); setPhase('opening'); return }
        if (status.all_ready) { setPrep({ done: total, total, label: 'Ready' }); setPhase('opening'); return }
        const have = new Set(status.generated || [])
        let done = have.size
        setPrep({ done, total, label: `Generating narration… ${done}/${total}` })
        for (let i = 0; i < total; i++) {
          if (cancelled) return
          const item = PREP_ITEMS[i]
          if (have.has(item.id)) continue
          setPrep({ done, total, label: `Generating audio… ${i + 1} of ${total}` })
          const res = await fetch('/api/tour/generate-audio', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ step_id: item.id, narration_text: item.narration }),
          }).then((r) => r.json()).catch(() => ({ ok: false }))
          if (!res.ok) setUsingFallback(true)
          done += 1
          setPrep({ done, total, label: `Generated ${i + 1} of ${total}` })
        }
        if (!cancelled) setPhase('opening')
      } catch {
        if (!cancelled) { setUsingFallback(true); setPhase('opening') }
      }
    }
    run()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // ── Opening (intro) + closing narration playback ──────────────────────────
  useEffect(() => {
    if (TEST_MS) return undefined
    if (phase !== 'intro' && phase !== 'closing') return undefined
    stopSpeak()
    const id = phase === 'intro' ? 'opening' : 'closing'
    const text = phase === 'intro' ? OPENING_NARRATION : CLOSING_NARRATION
    const a = new Audio(`/api/tour/audio/${id}`)
    a.muted = mutedRef.current
    audioRef.current = a
    let fallbackTimer = null
    if (phase === 'intro') {
      a.addEventListener('ended', () => begin('auto'))
      fallbackTimer = setTimeout(() => begin('auto'), 75000) // proceed even if audio stalls
    }
    a.play().catch(() => { setUsingFallback(true); if (!mutedRef.current) speakFallback(text) })
    return () => {
      try { a.pause() } catch { /* ignore */ }
      audioRef.current = null
      if (fallbackTimer) clearTimeout(fallbackTimer)
      stopSpeak()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase])

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
  const beginAuto = () => { if (TEST_MS) { begin('auto'); return } setMode('auto'); setPhase('intro') }
  const restart = () => { stopSpeak(); setPhase('opening'); setStep(0); setPaused(false) }

  return (
    <div data-tour-steps={STEPS.length} data-tour-total={TOTAL_SECONDS}
         className="relative -m-6 h-[calc(100vh-56px)] bg-navy text-white overflow-hidden flex flex-col">
      <style>{`@keyframes tourFloat{0%{transform:translateY(0);opacity:.5}50%{opacity:1}100%{transform:translateY(-28px);opacity:.35}}`}</style>

      {phase === 'prep' && <Prep prep={prep} />}
      {phase === 'opening' && <Opening usingFallback={usingFallback} onBegin={() => begin('manual')} onAuto={beginAuto} />}
      {phase === 'intro' && <Intro muted={muted} onMute={() => setMuted((m) => !m)} onSkip={() => begin('auto')} />}
      {phase === 'running' && (
        <Running cur={cur} step={step} progress={progress} mode={mode} paused={paused} muted={muted} usingFallback={usingFallback}
          onNext={goNext} onPrev={goPrev} onPause={() => setPaused((p) => !p)} onMute={() => setMuted((m) => !m)} onRestart={restart} />
      )}
      {phase === 'closing' && <Closing onRestart={restart} muted={muted} onMute={() => setMuted((m) => !m)} />}
    </div>
  )
}

// ── Intro screen (plays opening narration before Step 1 in Auto-Play) ────────
function Intro({ muted, onMute, onSkip }) {
  return (
    <div className="relative flex-1 flex flex-col items-center justify-center text-center px-6"
         style={{ background: 'radial-gradient(circle at 50% 20%, #14385f 0%, #0a2342 60%, #061629 100%)' }}>
      <div className="absolute inset-0 pointer-events-none">
        {Array.from({ length: 16 }).map((_, i) => (
          <span key={i} className="absolute rounded-full bg-gold" style={{ width: 3 + (i % 3), height: 3 + (i % 3), left: `${(i * 53) % 100}%`, top: `${(i * 37) % 100}%`, opacity: 0.4, animation: `tourFloat ${6 + (i % 5)}s ease-in-out ${i * 0.4}s infinite` }} />
        ))}
      </div>
      <div className="relative z-10 max-w-3xl">
        <div className="text-gold font-extrabold tracking-tight text-4xl">INNtelligence</div>
        <div className="text-gold-light text-xs uppercase tracking-[0.3em] mt-2">A note before we begin</div>
        <p className="text-white/90 text-lg leading-relaxed mt-6">{display(OPENING_NARRATION)}</p>
        <div className="flex items-center justify-center gap-3 mt-8">
          <button onClick={onMute} className={`px-4 py-2 rounded-lg text-sm ${muted ? 'bg-rose-500/30 text-rose-200' : 'bg-white/10 hover:bg-white/20'}`}>{muted ? '🔇 Muted' : '🔊 Sound'}</button>
          <button onClick={onSkip} aria-label="Skip intro" className="px-5 py-2 rounded-lg bg-gold text-navy font-semibold text-sm hover:bg-gold-light">Skip intro → Step 1</button>
        </div>
      </div>
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
            <p className="text-white text-lg leading-relaxed mt-3">{display(cur.narration)}</p>
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
function Closing({ onRestart, muted, onMute }) {
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
      <div className="flex items-center justify-center gap-3 mt-6">
        <button onClick={onMute} className={`text-xs px-3 py-1.5 rounded-lg ${muted ? 'bg-rose-500/30 text-rose-200' : 'bg-white/10 hover:bg-white/20'}`}>{muted ? '🔇 Muted' : '🔊 Sound'}</button>
        <button onClick={onRestart} className="text-white/40 text-xs underline hover:text-white/70">↺ Replay the tour</button>
      </div>
    </div>
  )
}

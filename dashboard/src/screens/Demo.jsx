import { useState, useEffect, useRef } from 'react'

// ─────────────────────────────────────────────────────────────────────────────
//  INNtelligence — 22-minute self-running interactive demo for The Bay Street Inn.
//  All data here is HARDCODED — the demo never calls the Flask API, so it runs
//  even if the backend is down. Voice via Web Speech API; captions always visible.
// ─────────────────────────────────────────────────────────────────────────────

const TOTAL_SECONDS = 1320 // 22 minutes

const usd = (n) => '$' + Math.round(n).toLocaleString('en-US')

// ── Small presentational helpers ─────────────────────────────────────────────
const Bar = ({ value, max, color = '#c9a84c' }) => (
  <div className="flex-1 h-4 bg-white/10 rounded overflow-hidden">
    <div className="h-full rounded" style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: color }} />
  </div>
)
const Tag = ({ children, tone = 'gold' }) => {
  const tones = {
    gold: 'bg-gold/20 text-gold border-gold/40',
    rose: 'bg-rose-500/20 text-rose-300 border-rose-400/40',
    emerald: 'bg-emerald-500/20 text-emerald-300 border-emerald-400/40',
    gray: 'bg-white/10 text-white/60 border-white/20',
    amber: 'bg-amber-500/20 text-amber-200 border-amber-400/40',
  }
  return <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${tones[tone]}`}>{children}</span>
}
const Panel = ({ title, children }) => (
  <div className="w-full">
    {title && <div className="text-gold-light text-sm font-semibold uppercase tracking-wide mb-3">{title}</div>}
    {children}
  </div>
)

// ── 12 simulated screens (static Bay Street Inn data) ────────────────────────

function SimRateCalendar() {
  const rooms = ['WF Room 1', 'WF Room 2', 'WF Room 3', 'Water View 1', 'Garden 2', 'Signature Suite']
  const days = ['Tonight', 'Fri', 'Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  // deterministic rate grid; a few exact callouts per the script
  const rate = (ri, di) => {
    if (ri === 0 && di === 0) return { v: 445, s: 'premium' }
    if (ri === 2 && di === 2) return { v: 502, s: 'premium' }
    if (ri === 0 && di === 5) return { v: 355, s: 'discount' }
    const base = [389, 379, 369, 309, 249, 519][ri]
    const wk = di === 2 || di === 8 ? 1.18 : di === 5 ? 0.92 : 1.0
    const v = Math.round((base * wk) / 5) * 5
    return { v, s: v > base * 1.05 ? 'premium' : v < base * 0.99 ? 'discount' : 'hold' }
  }
  const tone = (s) => s === 'premium' ? 'bg-emerald-500/15 text-emerald-300'
    : s === 'discount' ? 'bg-rose-500/15 text-rose-300' : 'text-white/80'
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <div className="lg:col-span-2 overflow-x-auto">
        <Panel title="Rate Calendar · Waterfront · Next 30 days">
          <table className="text-xs w-full">
            <thead><tr className="text-white/40">
              <th className="text-left py-1 pr-2">Room</th>
              {days.map((d, di) => <th key={di} className="px-1 text-center">{d}</th>)}
            </tr></thead>
            <tbody>
              {rooms.map((rm, ri) => (
                <tr key={rm} className="border-t border-white/5">
                  <td className="py-1.5 pr-2 text-white/70 whitespace-nowrap">{rm}</td>
                  {days.map((_, di) => {
                    const { v, s } = rate(ri, di)
                    const hot = ri === 0 && di === 0
                    return (
                      <td key={di} className={`px-1 py-1 text-center rounded font-semibold ${tone(s)} ${hot ? 'ring-2 ring-gold' : ''}`}>{usd(v)}</td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
      <div className="rounded-xl border border-gold/40 bg-navy-dark/60 p-4">
        <div className="text-gold font-bold">WF Room 1 · Tonight</div>
        <div className="text-4xl font-extrabold text-gold mt-1">$445</div>
        <div className="text-[11px] text-white/50">rack $389 · +14% premium</div>
        <div className="mt-3 space-y-1 text-xs text-white/70">
          <div className="flex justify-between"><span>Demand score</span><span className="text-gold font-bold">7.2 / 10</span></div>
          <div className="flex justify-between"><span>Confidence</span><Tag tone="emerald">HIGH</Tag></div>
          <div className="flex justify-between"><span>Comp avg (WF)</span><span>$378</span></div>
        </div>
        <div className="mt-3 text-[11px] text-white/60 leading-snug border-t border-white/10 pt-2">
          Original Gullah Festival begins tomorrow · weekend arrival · demand climbing. Recommend holding premium.
        </div>
        <button className="mt-3 w-full bg-gold text-navy font-semibold py-1.5 rounded text-sm">✓ Accept $445</button>
      </div>
    </div>
  )
}

function SimCompetitiveIntel() {
  const tiers = [
    { label: 'Your Direct Competitors', rows: [
      { name: 'Rhett House Inn', na: true },
      { name: 'Cuthbert House Inn', rate: 450 },
      { name: 'Anchorage 1770', rate: 445 },
      { name: '607 Bay Inn', na: true },
    ]},
    { label: 'Market Reference', rows: [
      { name: 'Beaufort Inn', na: true },
      { name: 'City Loft Hotel', na: true },
    ]},
    { label: 'Market Anchors', rows: [
      { name: 'Airbnb Near Bay St', partial: true, rate: 250 },
      { name: 'Hampton Inn Beaufort', na: true, ref: 'Budget Reference' },
      { name: 'Montage Palmetto Bluff', rate: 1385, ref: 'Luxury Reference' },
    ]},
  ]
  return (
    <Panel title="Competitive Intelligence · Waterfront filter active">
      <div className="flex gap-2 mb-3">
        {['All', 'Waterfront', 'Water View', 'Garden', 'Suites'].map((t) => (
          <span key={t} className={`text-xs px-3 py-1 rounded-md ${t === 'Waterfront' ? 'bg-navy text-white font-semibold ring-1 ring-gold' : 'bg-white/10 text-white/50'}`}>{t}</span>
        ))}
      </div>
      <table className="w-full text-xs">
        <tbody>
          <tr className="bg-gold/15 text-gold font-bold">
            <td className="py-2 pl-2">★ The Bay Street Inn</td>
            <td className="text-right pr-2">$445</td>
            <td className="text-right pr-2 text-gold/70">recommended</td>
          </tr>
          <tr className="bg-navy/40 text-white font-semibold border-y border-white/10">
            <td className="py-1.5 pl-2">Comp-set average</td>
            <td className="text-right pr-2">$378</td>
            <td className="text-right pr-2 text-[10px] text-white/40 italic">3 comparable</td>
          </tr>
          {tiers.map((g) => (
            <FragmentRows key={g.label} g={g} />
          ))}
        </tbody>
      </table>
    </Panel>
  )
}
function FragmentRows({ g }) {
  return (
    <>
      <tr><td colSpan={3} className="text-[10px] uppercase tracking-wide text-white/30 pt-3 pb-1 pl-2">{g.label}</td></tr>
      {g.rows.map((r) => (
        <tr key={r.name} className={`border-t border-white/5 ${r.na ? 'text-white/25' : 'text-white/80'}`}>
          <td className="py-1.5 pl-2 whitespace-nowrap">
            {r.name}
            {r.ref && <span className={`ml-2 text-[9px] px-1.5 py-0.5 rounded-full border ${r.ref.includes('Luxury') ? 'bg-gold/15 text-gold border-gold/40' : 'bg-white/10 text-white/40 border-white/20'}`}>{r.ref}</span>}
            {r.partial && <span className="ml-2 text-[9px] text-amber-300">⚠ Varies</span>}
          </td>
          <td className={`text-right pr-2 ${r.partial ? 'italic text-amber-300' : ''}`}>{r.na ? 'N/A' : usd(r.rate) + (r.partial ? '*' : '')}</td>
          <td className="text-right pr-2 text-[10px] text-white/30">{r.na ? 'no comparable room' : ''}</td>
        </tr>
      ))}
    </>
  )
}

function SimRevenueIntel() {
  const recs = [
    'Lower Garden Room 3 by $18 for next Mon–Tue — competitor dropped, 3 guests comparison shopping',
    'Add 2-night minimum to Saturday Jun 14 waterfront bookings',
    'Launch win-back email to 8 lapsed guests within 100 miles',
    'Raise Signature Suite $25 for Water Festival weekend',
    'Fill Friday orphan Jun 13 — offer extension to Saturday guest',
    'Activate Proposal Package — only 12% of comps offer it',
    'Promote rooftop happy hour Thursday — demand soft',
    'Hold Grand Parlor at ceiling for Gullah Festival',
    'Send anniversary upgrade offer to 3 arriving couples',
    'Set 3-night minimum for July 4th weekend',
  ]
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Panel title="Gap Night Detector">
        <div className="flex gap-2 items-stretch">
          {['Thu', 'Fri', 'Sat', 'Sun'].map((d) => {
            const orphan = d === 'Fri'
            const booked = d === 'Sat'
            return (
              <div key={d} className={`flex-1 rounded-lg p-3 text-center border ${orphan ? 'border-rose-400 bg-rose-500/10' : booked ? 'border-emerald-400/50 bg-emerald-500/10' : 'border-white/15 bg-white/5'}`}>
                <div className="text-white/60 text-xs">{d}</div>
                <div className="text-lg mt-1">{booked ? '🛏️' : orphan ? '⚠️' : '·'}</div>
                <div className={`text-[10px] mt-1 ${orphan ? 'text-rose-300 font-bold' : 'text-white/40'}`}>{booked ? 'Booked' : orphan ? 'ORPHAN' : 'Open'}</div>
              </div>
            )
          })}
        </div>
        <div className="mt-3 text-xs text-white/70 space-y-1">
          <div className="text-gold-light font-semibold">Recommended actions for Friday orphan:</div>
          <div>① Add 2-night minimum to the Saturday booking</div>
          <div>② Offer Friday at 12% discount as an extension</div>
          <div>③ Targeted email to past guests within 100 miles</div>
        </div>
      </Panel>
      <Panel title="AI Revenue Recommendations · 10 active">
        <div className="space-y-1.5 max-h-72 overflow-hidden">
          {recs.map((r, i) => (
            <div key={i} className={`text-[11px] rounded px-2 py-1.5 border-l-2 ${i === 0 ? 'border-gold bg-gold/10 text-white' : 'border-white/20 bg-white/5 text-white/70'}`}>
              {i === 0 && <span className="text-gold font-bold mr-1">TOP →</span>}{r}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

function SimGuestCRM() {
  const guests = [
    ['Margaret Chen', 'Charlotte, NC', 4, 3840, 'VIP Lapsed'],
    ['James Whitfield', 'Atlanta, GA', 2, 1290, 'Regular'],
    ['Sarah Donnelly', 'Columbia, SC', 6, 5210, 'VIP'],
    ['Robert Hayes', 'Raleigh, NC', 1, 410, 'New'],
    ['Linda Park', 'Charleston, SC', 3, 2180, 'Regular'],
    ['Thomas Reed', 'Washington, DC', 5, 4620, 'VIP'],
    ['Emily Carter', 'New York, NY', 2, 1740, 'Lapsed'],
    ['David Nguyen', 'Beaufort, SC', 8, 6890, 'VIP'],
  ]
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Panel title="Guest List · 68 guests">
        <table className="w-full text-xs">
          <tbody>
            {guests.map((g) => (
              <tr key={g[0]} className={`border-t border-white/5 ${g[0] === 'Margaret Chen' ? 'bg-gold/10 text-white' : 'text-white/70'}`}>
                <td className="py-1.5 font-medium">{g[0]}</td>
                <td className="text-white/50">{g[1]}</td>
                <td className="text-center">{g[2]}×</td>
                <td className="text-right">{usd(g[3])}</td>
                <td className="text-right"><Tag tone={g[4].includes('VIP') ? 'gold' : g[4].includes('Lapsed') ? 'rose' : 'gray'}>{g[4]}</Tag></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <div className="rounded-xl border border-gold/40 bg-navy-dark/60 p-4">
        <div className="text-gold font-bold text-lg">Margaret Chen</div>
        <div className="text-white/50 text-xs">Charlotte, NC · 230 mi away</div>
        <div className="grid grid-cols-3 gap-2 mt-3 text-center">
          {[['4', 'stays'], [usd(3840), 'lifetime'], ['7mo', 'since visit']].map((m) => (
            <div key={m[1]} className="bg-white/5 rounded py-2"><div className="text-gold font-bold text-sm">{m[0]}</div><div className="text-[10px] text-white/40">{m[1]}</div></div>
          ))}
        </div>
        <div className="mt-3 text-xs"><Tag tone="rose">VIP Lapsed</Tag> <span className="text-white/50 ml-2">Prefers Waterfront</span></div>
        <div className="mt-4 rounded-lg bg-white/5 border border-white/10 p-3">
          <div className="text-[10px] uppercase tracking-wide text-white/40">Campaign · Win-Back template</div>
          <div className="text-sm text-white mt-1 font-semibold">"Margaret, your river view is waiting"</div>
          <div className="text-[11px] text-white/60 mt-1">Personalized · references her favorite waterfront room · 10% loyalty rate → Lapsed VIP segment (12 guests)</div>
          <button className="mt-2 w-full bg-gold text-navy font-semibold py-1.5 rounded text-sm">✉ Send Campaign</button>
        </div>
      </div>
    </div>
  )
}

function SimROI() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
      <div className="rounded-xl bg-navy-dark/60 border border-gold/40 p-5 text-center">
        <div className="text-gold-light text-xs uppercase tracking-wide">Return on subscription · 90 days</div>
        <div className="text-6xl font-extrabold text-gold mt-2">8.7×</div>
        <div className="text-white/50 text-xs mt-1">pays for itself in one festival weekend</div>
        <div className="grid grid-cols-2 gap-2 mt-4 text-center">
          <div className="bg-emerald-500/10 rounded py-2"><div className="text-emerald-300 font-bold">+23%</div><div className="text-[10px] text-white/40">RevPAR vs comp</div></div>
          <div className="bg-emerald-500/10 rounded py-2"><div className="text-emerald-300 font-bold">+18%</div><div className="text-[10px] text-white/40">ADR YoY</div></div>
        </div>
      </div>
      <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Panel title="Top 5 Wins This Month">
          {[['Water Festival pricing', 4200], ['Gullah Festival surge', 1850], ['Win-back campaigns', 2100], ['Weekend min-stay', 1120], ['Suite premium hold', 760]].map((w) => (
            <div key={w[0]} className="flex justify-between text-xs py-1.5 border-b border-white/5"><span className="text-white/70">{w[0]}</span><span className="text-emerald-300 font-bold">+{usd(w[1])}</span></div>
          ))}
        </Panel>
        <Panel title="Missed Opportunities">
          {[['2 Thursday nights, April', 680], ['Garden Rm late discount', 240]].map((w) => (
            <div key={w[0]} className="flex justify-between text-xs py-1.5 border-b border-white/5"><span className="text-white/70">{w[0]}</span><span className="text-rose-300 font-bold">−{usd(w[1])}</span></div>
          ))}
          <div className="text-[11px] text-white/40 mt-2 italic">Shown intentionally — learn from every empty room.</div>
        </Panel>
      </div>
    </div>
  )
}

function SimPrivateEvents() {
  const lines = [['Room block (19 × $420 × 2)', 15960], ['Event space fee', 1500], ['F&B minimum (30 guests)', 3750], ['Setup & coordination', 800], ['Exclusivity premium', 4402]]
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Panel title="Private Event Calculator · Wedding inquiry">
        <div className="grid grid-cols-2 gap-2 text-xs mb-3">
          {[['Event', 'Wedding'], ['Date', 'Oct 11, 2026'], ['Guests', '30'], ['Rooms', '19'], ['Nights', '2'], ['F&B', 'Yes']].map((f) => (
            <div key={f[0]} className="bg-white/5 rounded px-2 py-1.5"><span className="text-white/40">{f[0]}: </span><span className="text-white font-semibold">{f[1]}</span></div>
          ))}
        </div>
        {lines.map((l) => (
          <div key={l[0]} className="flex justify-between text-xs py-1 border-b border-white/5"><span className="text-white/70">{l[0]}</span><span className="text-white">{usd(l[1])}</span></div>
        ))}
        <div className="flex justify-between mt-2 text-gold font-extrabold text-lg"><span>Total package value</span><span>$26,412</span></div>
      </Panel>
      <Panel title="Conflict Detection">
        <div className="rounded-lg border border-amber-400/50 bg-amber-500/10 p-3">
          <div className="text-amber-200 font-semibold text-sm">⚠ Beaufort Shrimp Festival weekend</div>
          <div className="text-xs text-white/70 mt-1">Selling rooms individually at event pricing would generate <span className="text-white font-bold">$19,200</span>.</div>
        </div>
        <div className="rounded-lg border border-gold/40 bg-gold/10 p-3 mt-3">
          <div className="text-gold font-semibold text-sm">Recommendation</div>
          <div className="text-xs text-white/80 mt-1">Negotiate the wedding package <span className="font-bold text-white">above $20,000</span> — or decline and sell individually. Wedding premium over individual sale: <span className="text-emerald-300 font-bold">+$10,452</span>.</div>
        </div>
      </Panel>
    </div>
  )
}

function SimFnB() {
  const parlor = [['Mon', 1200], ['Tue', 980], ['Wed', 1100], ['Thu', 1850], ['Fri', 3200], ['Sat', 3800], ['Sun', 2100]]
  const rooftop = [['Mon', 400], ['Tue', 350], ['Wed', 420], ['Thu', 890], ['Fri', 2100], ['Sat', 2400], ['Sun', 1200]]
  const Chart = ({ title, data, color }) => (
    <Panel title={title}>
      <div className="space-y-1.5">
        {data.map((d) => (
          <div key={d[0]} className="flex items-center gap-2 text-[11px]"><span className="w-8 text-white/50">{d[0]}</span><Bar value={d[1]} max={4000} color={color} /><span className="w-12 text-right text-white/70">{usd(d[1])}</span></div>
        ))}
      </div>
    </Panel>
  )
  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Chart title="The Parlor at Bay Street · by day" data={parlor} color="#c9a84c" />
        <Chart title="The Rooftop at Bay Street · by day" data={rooftop} color="#5b8fb0" />
      </div>
      <div className="mt-4 rounded-lg border border-gold/40 bg-gold/10 p-3 text-xs text-white/80">
        <span className="text-gold font-semibold">Top recommendation:</span> Launch a Thursday sunset happy hour at The Rooftop — comparable inns see a <span className="font-bold text-white">22% lift</span> (~$1,700/mo).
      </div>
    </div>
  )
}

function SimPackages() {
  const active = ['Romance', 'Anniversary', 'Adventure', 'Spa', 'Breakfast', 'Sunset Cruise', 'Pet']
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <Panel title="Active Packages · 7">
        <div className="flex flex-wrap gap-2">{active.map((p) => <Tag key={p} tone="gold">{p}</Tag>)}</div>
        <div className="mt-4 rounded-lg border border-gold/40 bg-navy-dark/60 p-3">
          <div className="text-gold font-bold">💑 Romance Package</div>
          <div className="text-xs text-white/60 mt-1">Offered by 78% of comparable inns · +$85 premium · 20% take rate</div>
          <div className="text-emerald-300 font-bold text-lg mt-1">$4,781 / mo</div>
        </div>
      </Panel>
      <Panel title="Available Packages · 18 more">
        <div className="rounded-lg border border-white/15 bg-white/5 p-3">
          <div className="flex items-center justify-between">
            <div className="text-white font-semibold">💍 Proposal Package</div>
            <button className="bg-navy text-white text-xs font-semibold px-3 py-1 rounded ring-1 ring-gold animate-pulse">+ Activate</button>
          </div>
          <div className="text-xs text-white/60 mt-1">Only 12% of inns offer it · low competition, high value</div>
          <div className="text-[11px] text-white/50 mt-1">Recommended +$195 · est. $3,200/mo at 15% take</div>
        </div>
      </Panel>
    </div>
  )
}

function SimEvents() {
  const events = [
    ['Original Gullah Festival', 'May 24–26', '+35%', 'high'],
    ['Beaufort Water Festival', 'Jul 17–27', '+30–40%', 'peak'],
    ['Parris Island Graduation', 'Monthly', '+12%', 'recurring'],
    ['Shrimp Festival', 'Oct 3–5', '+28%', 'high'],
    ['First Friday Art Walk', 'Monthly', '+8%', 'recurring'],
  ]
  return (
    <Panel title="Beaufort Events · Next 6 months">
      <div className="space-y-2">
        {events.map((e) => (
          <div key={e[0]} className={`flex items-center justify-between rounded-lg p-3 border ${e[3] === 'peak' ? 'border-gold/50 bg-gold/10' : 'border-white/10 bg-white/5'}`}>
            <div><div className="text-white font-semibold text-sm">{e[0]}</div><div className="text-[11px] text-white/50">{e[1]}</div></div>
            <div className="text-right"><div className="text-gold font-bold">{e[2]}</div>{e[3] === 'peak' && <div className="text-[10px] text-gold-light">largest revenue event</div>}</div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function SimHistorical() {
  const months = [42, 38, 44, 51, 58, 62, 68, 64, 55, 49, 41, 46, 48, 44, 50, 57, 64]
  return (
    <Panel title="Historical Performance · 24 months">
      <div className="flex items-end gap-1 h-40">
        {months.map((m, i) => (
          <div key={i} className="flex-1 rounded-t" style={{ height: `${(m / 68) * 100}%`, background: i === 6 ? '#c9a84c' : 'rgba(255,255,255,0.2)' }} title={`${m}k`} />
        ))}
      </div>
      <div className="flex justify-between text-xs mt-3">
        <div><span className="text-gold font-bold">Best month:</span> <span className="text-white">July 2025 · $68,400</span></div>
        <div><span className="text-emerald-300 font-bold">+23%</span> <span className="text-white/60">May 2026 vs May 2025</span></div>
      </div>
    </Panel>
  )
}

function SimReputation() {
  const platforms = [['TripAdvisor', 4.7], ['Booking.com', 4.6], ['Google', 4.8]]
  const kw = ['location', 'breakfast', 'staff', 'views', 'value']
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-center">
      <div className="text-center rounded-xl bg-navy-dark/60 border border-gold/40 p-5">
        <div className="text-gold-light text-xs uppercase tracking-wide">Pricing Power Score</div>
        <div className="text-6xl font-extrabold text-gold mt-1">84<span className="text-2xl text-white/30">/100</span></div>
        <div className="text-white/50 text-xs mt-1">above 80 — you've earned premium pricing</div>
      </div>
      <div>
        <div className="space-y-2">
          {platforms.map((p) => (
            <div key={p[0]} className="flex items-center gap-2 text-sm"><span className="w-28 text-white/60">{p[0]}</span><Bar value={p[1]} max={5} /><span className="text-gold font-bold w-10 text-right">{p[1]}★</span></div>
          ))}
        </div>
        <div className="mt-4"><div className="text-[11px] text-white/40 uppercase tracking-wide mb-1">Guests love</div><div className="flex flex-wrap gap-2">{kw.map((k) => <Tag key={k} tone="gold">{k}</Tag>)}</div></div>
      </div>
    </div>
  )
}

function SimGiftShop() {
  const cats = [['🛏️ Comphy Bedding', 8, 1920, 48], ['🍷 Murano Glass · Gino Mazzuccato', 3, 1240, 52], ['🎨 Local Beaufort Artists', 5, 880, 45], ['🫙 Lowcountry Pantry', 34, 612, 55], ['🧢 Bay Street Branded', 12, 408, 60], ['🎁 Experience Kits', 6, 540, 50]]
  return (
    <Panel title="Gift Shop · This month $3,160 revenue">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {cats.map((c) => (
          <div key={c[0]} className={`rounded-lg p-3 border ${c[0].includes('Murano') || c[0].includes('Comphy') ? 'border-gold/40 bg-gold/10' : 'border-white/10 bg-white/5'}`}>
            <div className="text-white text-sm font-semibold">{c[0]}</div>
            <div className="flex justify-between text-[11px] text-white/60 mt-1"><span>{c[1]} sold</span><span className="text-emerald-300 font-bold">{usd(c[2])}</span><span>{c[3]}% margin</span></div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

// ── Steps ────────────────────────────────────────────────────────────────────
const STEPS = [
  { title: 'Rate Calendar', duration: 210, Sim: SimRateCalendar, narration: "Welcome to INNtelligence. This is The Bay Street Inn's Rate Calendar — the command center for every pricing decision you'll make. Right now, without INNtelligence, most inn owners set their rates once a season and hope for the best. INNtelligence prices every room, every night, based on what's actually happening in your market. Watch what happens when we select Waterfront rooms for the next 30 days. You can see Waterfront Room 1 is recommended at $445 tonight — that's above our rack rate of $389, because the Original Gullah Festival starts tomorrow and demand is already climbing. Room 3 next Saturday? $502. That's our weekend premium plus the festival multiplier working together. But look at next Tuesday — $355. Below rack rate. The engine sees low demand and recommends a modest discount to fill the room rather than leave it empty at a higher rate. Click any cell and you get the full reasoning. Competitor rates on comparable rooms. Demand score. Confidence level. And a one-click accept button. This is dynamic pricing that thinks like a revenue manager — available to every inn owner, not just the big hotel chains." },
  { title: 'Competitive Intel', duration: 180, Sim: SimCompetitiveIntel, narration: "Now let's look at what your competition is doing. INNtelligence monitors 9 properties in the Beaufort market, organized into three tiers. Your direct competitors — the properties guests are comparing you to right now — are Rhett House Inn, Cuthbert House Inn, Anchorage 1770, and 607 Bay Inn. Watch what happens when we filter to Waterfront rooms. Notice that Rhett House and City Loft immediately gray out — they don't have true waterfront rooms. We're not going to compare apples to oranges. The comp-set average for waterfront rooms tonight is $378 — and The Bay Street Inn is recommending $445. That's a 17% premium over the market average. Is that justified? Absolutely. Bay Street Inn has newer renovations, superior amenities, and a stronger reputation score. And see Montage Palmetto Bluff at the bottom — $1,385 a night. That's your luxury reference point. It tells you there are guests in this market willing to spend serious money for the right experience. INNtelligence updates these competitor rates every morning at 6am. You wake up knowing exactly where you stand before your first cup of coffee." },
  { title: 'Revenue Intelligence', duration: 150, Sim: SimRevenueIntel, narration: "This screen solves a problem every inn owner knows intimately. It's Thursday. Someone books your best waterfront room for Saturday night. Great. But now Friday sits empty next to a booked Saturday, and Sunday is also open. That's called an orphan gap — and it costs inn owners thousands of dollars every year. INNtelligence finds every gap in your calendar and tells you exactly what to do about it. For that Friday orphan, it recommends three specific actions: Add a two-night minimum to the Saturday booking, offer the Friday room at a 12% discount to the Saturday guest as an extension, or launch a targeted email to guests within 100 miles who've stayed with you before. Below that, you'll see ten specific AI recommendations active right now for Bay Street Inn. These aren't generic suggestions — they're calculated from your actual booking data, your competitor rates, and the local events calendar. This week's top recommendation: Lower Garden Room 3 by $18 for next Monday and Tuesday. A competitor dropped their rate yesterday and three guests are currently comparison shopping. That one insight, acted on today, could be the difference between a filled room and an empty one." },
  { title: 'Guest CRM', duration: 150, Sim: SimGuestCRM, narration: "Your guests are your most valuable asset — and most inn owners know almost nothing about them beyond a name and a reservation date. INNtelligence changes that completely. Here you can see every guest who has ever stayed at Bay Street Inn. Searchable. Filterable by visit frequency, lifetime spend, home location, and how long since their last stay. Let's look at Margaret Chen from Charlotte. Four stays. Lifetime spend of $3,840. Always books a waterfront room. Last visited seven months ago. Margaret is a lapsed VIP — and she's exactly who you should be reaching out to right now. Switch to Campaign Manager. Select the Lapsed VIP segment. Choose the Win-Back template. Preview the email — it's personalized with Margaret's name, references her favorite waterfront room, and offers a 10% loyalty rate. Hit send and that campaign goes to every guest who matches that profile. One campaign. Fifteen minutes of your time. Potentially thousands of dollars in recovered bookings from guests who already love you." },
  { title: 'ROI Performance', duration: 120, Sim: SimROI, narration: "Every subscription has to justify itself. This screen does that. Bay Street Inn has been running INNtelligence for 90 days. The result: an 8.7 times return on the subscription cost. Top wins this month: Water Festival weekend pricing captured $4,200 in additional revenue compared to last year's flat rate strategy. The Gullah Festival rate surge added $1,850. Three win-back campaigns converted to bookings worth $2,100. And missed opportunities — because we show you those too: Two Thursday nights in April went unbooked when a modest rate reduction would likely have filled them. Estimated missed revenue: $680. That transparency is intentional. INNtelligence doesn't just celebrate wins — it helps you learn from every empty room. Your RevPAR is running 23% above the competitive set. Your ADR is up 18% year over year. The subscription pays for itself in the first weekend of Water Festival alone." },
  { title: 'Private Events', duration: 120, Sim: SimPrivateEvents, narration: "Here's a screen you won't find in any other revenue management system for boutique inns. Weddings. Corporate retreats. Anniversary buyouts. These are the events that can transform a slow weekend into your highest-revenue days of the year — if you price them correctly. Let's say a wedding inquiry comes in for the second weekend in October. 30 guests, two nights, full buyout with catering. Watch what happens when we run the calculator. Room block revenue: 19 rooms times $420 average times two nights — $15,960. Event space fee: $1,500. Food and beverage minimum for 30 guests: $3,750. Setup and coordination: $800. Exclusivity premium: $4,402. Total package value: $26,412. Compare that to selling those rooms individually that weekend: $15,960. The wedding premium is $10,452. But here's where it gets interesting. October second weekend is during the Beaufort Shrimp Festival. INNtelligence flags this immediately — individual bookings at event pricing would generate $19,200. The recommendation: negotiate the wedding package above $20,000 or decline and sell individually. That's the kind of decision that used to require years of experience. Now it takes 30 seconds." },
  { title: 'F&B Yield', duration: 90, Sim: SimFnB, narration: "The Bay Street Inn's food and beverage operation is a major revenue center — and most inns leave significant money on the table by not analyzing it properly. The Parlor at Bay Street Inn generates over $14,000 in a typical month. The Rooftop adds another $7,800. INNtelligence breaks down performance by day of week so you can see exactly where the opportunities are. Thursday is underperforming at The Rooftop compared to Friday and Saturday. The recommendation: launch a Thursday sunset happy hour with passed appetizers. Similar inns that have done this see a 20 to 25 percent lift on Thursday evenings. That's potentially $1,700 in additional monthly revenue from one simple change." },
  { title: 'Packages', duration: 60, Sim: SimPackages, narration: "The Bay Street Inn currently offers 7 guest packages. But INNtelligence knows that comparable inns in your market offer up to 25 different packages — and some of them are generating serious revenue. The Romance Package is already active — and for good reason. 78% of comparable boutique inns offer it, and at $85 above rack rate with a 20% take rate, it's generating an estimated $4,781 per month. But look at the Proposal Package in Available. Only 12% of inns offer it, which means low competition and high perceived value. Recommended premium: $195. Estimated monthly revenue at 15% take rate: $3,200. One click to activate." },
  { title: 'Events', duration: 60, Sim: SimEvents, narration: "INNtelligence tracks every event in the Beaufort market — from the Original Gullah Festival on Memorial Day weekend to the monthly Parris Island Marine Corps graduations. Each event comes with a pricing impact recommendation based on historical demand data. The Beaufort Water Festival in July is your single largest revenue opportunity of the year — 13 days, 30 to 40 percent rate premium, and rooms that typically sell out 60 days in advance. INNtelligence starts adjusting your rates 90 days before the festival begins. By the time the festival arrives, you're already maximizing every room." },
  { title: 'Historical Performance', duration: 30, Sim: SimHistorical, narration: "Historical Performance gives you 24 months of data to understand your property's patterns. Your best month ever was July 2025 at $68,400. This May is running 23% ahead of last year. INNtelligence uses this history to make smarter forward-looking recommendations — because the best predictor of future demand is what actually happened before." },
  { title: 'Reputation', duration: 30, Sim: SimReputation, narration: "Your reputation directly affects how much you can charge. INNtelligence tracks your scores across every major platform and calculates a Pricing Power Score — currently 84 out of 100 for Bay Street Inn. A score above 80 means you have earned the right to price at a premium. Guests are telling you exactly what they love: location, breakfast, staff, views. These are your selling points — and INNtelligence factors them into every rate recommendation." },
  { title: 'Gift Shop', duration: 30, Sim: SimGiftShop, narration: "Finally — the Gift Shop. Guests who fall in love with their experience want to bring it home. Bay Street Inn sells Comphy bedding — the exact sheets from the rooms — and authentic Murano glass by Gino Mazzuccato, sourced directly from Venice. This month: $3,160 in gift shop revenue with zero additional staff. That's pure margin on top of room revenue." },
]

// ── Voice narration ──────────────────────────────────────────────────────────
function useNarration(text, active, muted) {
  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    try { window.speechSynthesis.cancel() } catch { /* ignore */ }
    if (!active || muted || !text) return
    let cancelled = false
    const speak = () => {
      if (cancelled) return
      try {
        const u = new SpeechSynthesisUtterance(text)
        u.rate = 0.88; u.pitch = 1.0
        const voices = window.speechSynthesis.getVoices() || []
        const v = voices.find((x) => x.name === 'Samantha')
          || voices.find((x) => x.name === 'Google US English')
          || voices.find((x) => /en[-_]US/i.test(x.lang))
        if (v) u.voice = v
        window.speechSynthesis.speak(u)
      } catch { /* speech unavailable — captions still show */ }
    }
    const voices = window.speechSynthesis.getVoices() || []
    if (voices.length) speak()
    else {
      window.speechSynthesis.onvoiceschanged = speak
      speak()
    }
    return () => { cancelled = true; try { window.speechSynthesis.cancel() } catch { /* ignore */ } }
  }, [text, active, muted])
}

// ── Main component ───────────────────────────────────────────────────────────
export default function Demo() {
  const [phase, setPhase] = useState('opening')   // opening | running | closing
  const [step, setStep] = useState(0)
  const [mode, setMode] = useState('manual')       // manual | auto
  const [paused, setPaused] = useState(false)
  const [muted, setMuted] = useState(false)
  const [stepElapsed, setStepElapsed] = useState(0)
  const stepRef = useRef(step)
  useEffect(() => { stepRef.current = step }, [step])

  const cur = STEPS[step]
  useNarration(cur.narration, phase === 'running', muted)

  // Auto-advance ticker
  useEffect(() => {
    if (phase !== 'running' || mode !== 'auto' || paused) return
    const id = setInterval(() => setStepElapsed((e) => e + 1), 1000)
    return () => clearInterval(id)
  }, [phase, mode, paused, step])

  // Advance when a step's time is up (auto mode)
  useEffect(() => {
    if (phase !== 'running' || mode !== 'auto') return
    if (stepElapsed >= STEPS[step].duration) {
      if (step < STEPS.length - 1) { setStep(step + 1); setStepElapsed(0) }
      else setPhase('closing')
    }
  }, [stepElapsed, phase, mode, step])

  const completedSecs = STEPS.slice(0, step).reduce((a, s) => a + s.duration, 0)
  const progress = phase === 'closing' ? 100
    : phase === 'opening' ? 0
      : Math.min(100, ((completedSecs + stepElapsed) / TOTAL_SECONDS) * 100)

  const begin = (m) => { setMode(m); setPhase('running'); setStep(0); setStepElapsed(0); setPaused(false) }
  const next = () => {
    if (step < STEPS.length - 1) { setStep(step + 1); setStepElapsed(0) }
    else setPhase('closing')
  }
  const prev = () => {
    if (phase === 'closing') { setPhase('running'); setStep(STEPS.length - 1); setStepElapsed(0); return }
    if (step > 0) { setStep(step - 1); setStepElapsed(0) }
  }
  const restart = () => { setPhase('opening'); setStep(0); setStepElapsed(0); setPaused(false) }

  return (
    <div data-demo-steps={STEPS.length} data-demo-total={TOTAL_SECONDS}
         className="relative -m-6 min-h-[calc(100vh-56px)] bg-navy text-white overflow-hidden">
      <style>{`
        @keyframes demoWave { 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        @keyframes demoFloat { 0%{transform:translateY(0);opacity:.5} 50%{opacity:1} 100%{transform:translateY(-30px);opacity:.4} }
      `}</style>

      {phase === 'opening' && <Opening onBegin={() => begin('manual')} onAuto={() => begin('auto')} />}

      {phase === 'running' && (
        <RunningStage
          step={step} cur={cur} progress={progress} mode={mode} paused={paused} muted={muted}
          onNext={next} onPrev={prev} onTogglePause={() => setPaused((p) => !p)}
          onToggleMute={() => setMuted((m) => !m)} onRestart={restart}
        />
      )}

      {phase === 'closing' && <Closing onRestart={restart} progress={progress} />}
    </div>
  )
}

// ── Opening screen ───────────────────────────────────────────────────────────
function Opening({ onBegin, onAuto }) {
  return (
    <div className="relative h-[calc(100vh-56px)] flex flex-col items-center justify-center text-center px-6">
      {/* animated water waves */}
      <div className="absolute inset-x-0 bottom-0 h-1/2 overflow-hidden pointer-events-none">
        {[0, 1, 2].map((i) => (
          <div key={i} className="absolute bottom-0 left-0 w-[200%] h-32"
               style={{
                 background: `radial-gradient(ellipse at center, rgba(201,168,76,${0.06 - i * 0.015}) 0%, transparent 70%)`,
                 bottom: `${i * 24}px`,
                 animation: `demoWave ${14 + i * 6}s linear infinite`,
               }} />
        ))}
      </div>
      {/* floating gold particles */}
      <div className="absolute inset-0 pointer-events-none">
        {Array.from({ length: 18 }).map((_, i) => (
          <span key={i} className="absolute rounded-full bg-gold"
                style={{
                  width: 3 + (i % 3), height: 3 + (i % 3),
                  left: `${(i * 53) % 100}%`, top: `${(i * 37) % 100}%`,
                  opacity: 0.4, animation: `demoFloat ${6 + (i % 5)}s ease-in-out ${i * 0.4}s infinite`,
                }} />
        ))}
      </div>

      <div className="relative z-10">
        <div className="text-gold font-extrabold tracking-tight text-5xl sm:text-6xl">INNtelligence</div>
        <div className="text-gold-light/70 text-sm mt-2 uppercase tracking-[0.3em]">Revenue Intelligence</div>
        <p className="text-white/90 text-xl sm:text-2xl mt-8 max-w-2xl mx-auto leading-relaxed">
          19 rooms. One goal: maximum revenue.<br />This is how INNtelligence does it.
        </p>
        <div className="text-white/40 text-sm mt-3">The Bay Street Inn · Beaufort, SC · a 22-minute guided tour</div>
        <div className="flex items-center justify-center gap-4 mt-10">
          <button onClick={onBegin} aria-label="Begin Demo"
                  className="px-8 py-3 rounded-xl border border-gold/60 text-gold font-semibold hover:bg-gold/10 transition-colors">
            ▷ Begin Demo
          </button>
          <button onClick={onAuto} aria-label="Auto-Play"
                  className="px-8 py-3 rounded-xl bg-gold text-navy font-bold hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">
            ⏵ Auto-Play
          </button>
        </div>
        <div className="text-white/30 text-xs mt-4">Begin Demo = you control · Auto-Play = self-running with narration</div>
      </div>
    </div>
  )
}

// ── Running stage (controls + spotlight + captions) ──────────────────────────
function RunningStage({ step, cur, progress, mode, paused, muted, onNext, onPrev, onTogglePause, onToggleMute, onRestart }) {
  const Sim = cur.Sim
  return (
    <div className="flex flex-col h-[calc(100vh-56px)]">
      {/* header / controls */}
      <div className="px-6 pt-4 pb-3 border-b border-white/10 bg-navy-dark/40">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-gold font-extrabold tracking-tight">INNtelligence</div>
            <div className="text-white/50 text-xs">Step {step + 1} of {STEPS.length} · {cur.title}</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onPrev} aria-label="Previous step" className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm">⏮ Prev</button>
            {mode === 'auto' && (
              <button onClick={onTogglePause} aria-label="Play/Pause" className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm">{paused ? '⏵ Resume' : '⏸ Pause'}</button>
            )}
            <button onClick={onNext} aria-label="Next step" className="px-3 py-1.5 rounded-lg bg-gold text-navy font-semibold text-sm hover:bg-gold-light">Next ⏭</button>
            <button onClick={onToggleMute} aria-label="Mute" className={`px-3 py-1.5 rounded-lg text-sm ${muted ? 'bg-rose-500/30 text-rose-200' : 'bg-white/10 hover:bg-white/20'}`}>{muted ? '🔇 Muted' : '🔊'}</button>
            <button onClick={onRestart} aria-label="Restart" className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm">↺</button>
          </div>
        </div>
        {/* progress bar */}
        <div className="mt-3 h-2 bg-white/10 rounded-full overflow-hidden">
          <div className="h-full bg-gold transition-all duration-700" style={{ width: `${progress}%` }} />
        </div>
        <div className="text-right text-[10px] text-white/40 mt-1">{Math.round(progress)}% of 22 minutes</div>
      </div>

      {/* spotlight stage */}
      <div className="flex-1 relative overflow-y-auto p-6" style={{ background: 'radial-gradient(circle at 50% 35%, #0d2b4e 0%, #061629 70%)' }}>
        <div className="max-w-5xl mx-auto rounded-2xl bg-navy/70 backdrop-blur p-6 ring-2 ring-gold/60 shadow-[0_0_60px_rgba(201,168,76,0.25)]">
          <Sim />
        </div>
        <div className="h-32" />
      </div>

      {/* captions — always visible */}
      <div className="absolute inset-x-0 bottom-0 px-6 pb-5 pointer-events-none">
        <div className="max-w-4xl mx-auto bg-navy-dark/85 backdrop-blur rounded-xl px-6 py-4 border border-gold/20">
          <p className="text-white text-lg leading-snug" style={{ fontSize: '18px' }}>{cur.narration}</p>
        </div>
      </div>
    </div>
  )
}

// ── Closing screen ───────────────────────────────────────────────────────────
function Closing({ onRestart }) {
  const stats = [
    ['8.7×', 'average ROI in first 90 days'],
    ['23%', 'RevPAR improvement above comp set'],
    ['$26,412', 'private event value identified'],
    ['68', 'guests in CRM ready for win-back'],
  ]
  const tiers = [
    { name: 'Starter', price: '$149', per: '/month', feats: ['1 property', 'Up to 20 rooms', '5 competitors'] },
    { name: 'Professional', price: '$299', per: '/month', feats: ['Unlimited rooms', 'Live scraping', 'All screens'], featured: true },
    { name: 'Multi-Property', price: '$499', per: '/month', feats: ['Up to 5 properties', 'White label', 'Priority support'] },
  ]
  return (
    <div className="min-h-[calc(100vh-56px)] flex flex-col items-center justify-center text-center px-6 py-10"
         style={{ background: 'radial-gradient(circle at 50% 20%, #0d2b4e 0%, #061629 70%)' }}>
      <div className="text-gold font-extrabold tracking-tight text-4xl">The results speak for themselves</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5 mt-8 max-w-4xl">
        {stats.map((s) => (
          <div key={s[1]} className="rounded-xl bg-navy/60 border border-gold/30 p-5">
            <div className="text-gold text-3xl sm:text-4xl font-extrabold">{s[0]}</div>
            <div className="text-white/60 text-xs mt-2">{s[1]}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-10 max-w-4xl w-full">
        {tiers.map((t) => (
          <div key={t.name} className={`rounded-2xl p-5 border ${t.featured ? 'border-gold bg-gold/10 scale-105' : 'border-white/15 bg-navy/50'}`}>
            <div className="text-gold-light text-sm font-semibold uppercase tracking-wide">{t.name}</div>
            <div className="mt-2"><span className="text-3xl font-extrabold text-white">{t.price}</span><span className="text-white/40 text-sm">{t.per}</span></div>
            <ul className="mt-3 space-y-1 text-sm text-white/70">
              {t.feats.map((f) => <li key={f}>✓ {f}</li>)}
            </ul>
          </div>
        ))}
      </div>

      <a href="mailto:demo@inntelligence.app?subject=Start%20my%20free%2030-day%20trial"
         className="mt-10 inline-block px-10 py-4 rounded-xl bg-gold text-navy font-bold text-lg hover:bg-gold-light transition-colors shadow-lg shadow-gold/20">
        Start Your Free 30-Day Trial
      </a>
      <div className="text-white/40 text-sm mt-3">No credit card required. Cancel anytime.</div>
      <div className="text-white/50 text-sm mt-1">Questions? Email <span className="text-gold">demo@inntelligence.app</span></div>
      <button onClick={onRestart} className="mt-6 text-white/40 text-xs underline hover:text-white/70">↺ Replay the demo</button>
    </div>
  )
}

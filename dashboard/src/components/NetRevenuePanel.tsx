/**
 * NetRevenuePanel — CPP pocket-price waterfall + channel segmentation + EVE.
 * Mounts inside the Rate Calendar drawer (one panel, sections collapse).
 *
 * Fetches:
 *   GET /api/waterfall?rate={rate}&nights={los}
 *   GET /api/waterfall/parity?rate={rate}
 *   GET /api/waterfall/blended?rate={rate}
 *   GET /api/eve?rate={rate}&room_name={name}&room_category={cat}
 */
import { useEffect, useState } from 'react'

interface Props {
  rate: number
  roomName: string
  roomCategory: string   // waterfront | waterview | garden | cottage
  nights?: number
  eventContext?: string
}

interface WaterfallLine {
  label: string; amount: number; cumulative: number
  pct_of_rack: number; is_deduction: boolean; color: string
}
interface ChannelWf {
  channel_id: string; channel_label: string; channel_icon: string
  rack_rate: number; lines: WaterfallLine[]
  gross_revenue: number; contribution_margin: number
  contribution_margin_pct: number; vs_direct_delta: number
  recommendation: string
}
interface ParityResp {
  direct_rate: number; target_contribution_margin: number
  parity_rates: Record<string, {
    channel: string; icon: string; rate_for_parity: number
    premium_vs_direct?: number; premium_pct?: number; note: string
  }>
}
interface BlendedResp {
  rack_rate: number; blended_gross_revenue: number
  blended_contribution_margin: number; blended_cm_pct: number
  channel_breakdown: { channel: string; icon: string; mix_pct: number;
    cm_per_booking: number; weighted_cm: number }[]
  insight: string
}
interface EveResp {
  next_best_alternative: { name: string; avg_rate: number; type: string }
  value_drivers: { id: string; name: string; description: string;
    value_estimate: number; evidence: string }[]
  total_value_premium: number
  justified_rate: number
  premium_vs_nba_pct: number
  summary: string
  guest_facing_justification: string
}

export default function NetRevenuePanel({ rate, roomName, roomCategory, nights = 1, eventContext }: Props) {
  const [waterfall, setWaterfall] = useState<Record<string, ChannelWf> | null>(null)
  const [parity, setParity]     = useState<ParityResp | null>(null)
  const [blended, setBlended]   = useState<BlendedResp | null>(null)
  const [eve, setEve]           = useState<EveResp | null>(null)
  const [openSection, setOpenSection] = useState<'waterfall'|'parity'|'blended'|'eve'>('waterfall')
  const [copyState, setCopyState] = useState<string | null>(null)

  useEffect(() => {
    const ev = eventContext ? `&event=${encodeURIComponent(eventContext)}` : ''
    Promise.all([
      fetch(`/api/waterfall?rate=${rate}&nights=${nights}`).then(r => r.json()),
      fetch(`/api/waterfall/parity?rate=${rate}&nights=${nights}`).then(r => r.json()),
      fetch(`/api/waterfall/blended?rate=${rate}&nights=${nights}`).then(r => r.json()),
      fetch(`/api/eve?rate=${rate}&room_name=${encodeURIComponent(roomName)}&room_category=${roomCategory}${ev}`).then(r => r.json()),
    ]).then(([w, p, b, e]) => {
      setWaterfall(w); setParity(p); setBlended(b); setEve(e)
    }).catch(() => {})
  }, [rate, roomName, roomCategory, nights, eventContext])

  if (!waterfall) return <div className="text-xs text-slate-400 px-4 py-3">Loading net revenue analysis…</div>

  // sort channels: direct first, then by CM descending
  const ordered = Object.values(waterfall).sort((a, b) =>
    a.channel_id.startsWith('direct') === b.channel_id.startsWith('direct')
      ? b.contribution_margin - a.contribution_margin
      : a.channel_id.startsWith('direct') ? -1 : 1
  )
  const rackTotal = rate * nights
  const direct = waterfall['direct_web']

  function copy(s: string, key: string) {
    navigator.clipboard?.writeText(s).then(() => {
      setCopyState(key); setTimeout(() => setCopyState(null), 1500)
    })
  }

  return (
    <div className="space-y-2 text-sm">
      {/* ── Section 1: Waterfall by channel ── */}
      <Section title="Pocket Price Waterfall" emoji="💧"
        open={openSection === 'waterfall'} onToggle={() => setOpenSection('waterfall')}>
        <div className="text-[11px] text-slate-500 mb-2">
          What you actually keep after each channel's deductions.
        </div>
        <div className="space-y-2">
          {ordered.map(ch => {
            const cmShare = (ch.contribution_margin / rackTotal) * 100
            const isDirect = ch.channel_id.startsWith('direct')
            return (
              <div key={ch.channel_id} className="bg-white border border-slate-100 rounded-lg p-2">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs font-semibold text-navy flex items-center gap-1.5">
                    <span>{ch.channel_icon}</span>
                    <span>{ch.channel_label}</span>
                  </div>
                  <div className="text-xs">
                    <span className="font-bold text-sage">${ch.contribution_margin.toFixed(0)}</span>
                    <span className="text-slate-400"> · {ch.contribution_margin_pct.toFixed(0)}%</span>
                    {!isDirect && (
                      <span className="ml-1 text-[10px] text-coral">
                        ({ch.vs_direct_delta >= 0 ? '+' : ''}{ch.vs_direct_delta.toFixed(0)} vs direct)
                      </span>
                    )}
                  </div>
                </div>
                {/* horizontal bar split into deductions */}
                <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
                  {(() => {
                    const segs: { w: number; color: string; label: string }[] = []
                    let prev = 100
                    ch.lines.slice(1).forEach(ln => {
                      const w = ((prev - ln.pct_of_rack))
                      segs.push({ w, color: ln.color, label: ln.label })
                      prev = ln.pct_of_rack
                    })
                    segs.push({ w: prev, color: '#1d9e75', label: 'Net contribution margin' })
                    return segs.map((s, i) => (
                      <div key={i} style={{ width: `${s.w}%`, background: s.color }}
                        title={`${s.label} — ${s.w.toFixed(1)}% of rack`} />
                    ))
                  })()}
                </div>
                <div className="text-[10px] text-slate-500 italic mt-1">{ch.recommendation}</div>
              </div>
            )
          })}
        </div>
        {/* Detailed line table for the focused channel (direct_web) */}
        {direct && (
          <div className="mt-3 bg-cream rounded p-2">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1">
              Direct line items for ${rate}/night × {nights}
            </div>
            <table className="w-full text-[11px]">
              <tbody>
                {direct.lines.map((ln, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="py-0.5">{ln.label}</td>
                    <td className={`py-0.5 text-right ${ln.is_deduction ? 'text-coral' : 'text-navy font-semibold'}`}>
                      {ln.is_deduction ? '-' : ''}${Math.abs(ln.amount).toFixed(2)}
                    </td>
                    <td className="py-0.5 text-right text-slate-400 w-12">{ln.pct_of_rack.toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {/* ── Section 2: Rate parity ── */}
      {parity && (
        <Section title="Rate Parity by Net Revenue" emoji="⚖️"
          open={openSection === 'parity'} onToggle={() => setOpenSection('parity')}>
          <div className="text-[11px] text-slate-500 mb-2">
            To earn the same as <strong className="text-navy">${parity.direct_rate}</strong> direct,
            charge these rates on each channel:
          </div>
          <div className="space-y-1">
            {Object.entries(parity.parity_rates).map(([id, r]) => {
              const isDirect = id.startsWith('direct')
              return (
                <div key={id} className="flex items-center gap-2 text-xs">
                  <span className="text-base">{r.icon}</span>
                  <span className="flex-1">{r.channel}</span>
                  <span className={`font-bold ${isDirect ? 'text-navy' : 'text-gold'}`}>
                    ${r.rate_for_parity}
                  </span>
                  {r.premium_vs_direct != null && r.premium_vs_direct > 0 && (
                    <span className="text-[10px] text-slate-500 w-20 text-right">
                      +${r.premium_vs_direct.toFixed(0)} ({r.premium_pct?.toFixed(0)}%)
                    </span>
                  )}
                </div>
              )
            })}
          </div>
          <div className="text-[10px] text-slate-400 italic mt-2">
            Target net contribution per booking: ${parity.target_contribution_margin}
          </div>
        </Section>
      )}

      {/* ── Section 3: Blended channel analysis ── */}
      {blended && (
        <Section title="Blended Revenue Across Channel Mix" emoji="🥧"
          open={openSection === 'blended'} onToggle={() => setOpenSection('blended')}>
          <div className="text-[11px] text-slate-500 mb-2">
            At ${blended.rack_rate} rack, your current channel mix earns:
          </div>
          <div className="bg-navy text-white rounded-lg p-3 mb-2 flex items-baseline justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-gold">Avg net per booking</div>
              <div className="text-2xl font-bold">${blended.blended_contribution_margin.toFixed(0)}</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-wider text-white/60">Blended CM</div>
              <div className="text-lg font-bold text-gold">{blended.blended_cm_pct.toFixed(0)}%</div>
            </div>
          </div>
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-[9px] uppercase tracking-wider text-slate-500 border-b border-slate-200">
                <th className="py-1">Channel</th>
                <th className="py-1 text-right">Mix</th>
                <th className="py-1 text-right">CM/Booking</th>
                <th className="py-1 text-right">Weighted</th>
              </tr>
            </thead>
            <tbody>
              {blended.channel_breakdown.map(c => (
                <tr key={c.channel} className="border-b border-slate-100">
                  <td className="py-1">{c.icon} {c.channel}</td>
                  <td className="py-1 text-right">{c.mix_pct}%</td>
                  <td className="py-1 text-right">${c.cm_per_booking.toFixed(0)}</td>
                  <td className="py-1 text-right text-sage font-semibold">${c.weighted_cm.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[11px] text-gold italic mt-2 bg-gold/5 rounded p-2 border-l-2 border-gold">
            💡 {blended.insight}
          </div>
        </Section>
      )}

      {/* ── Section 4: Economic Value Estimation ── */}
      {eve && (
        <Section title="Economic Value Estimation (EVE)" emoji="💎"
          open={openSection === 'eve'} onToggle={() => setOpenSection('eve')}>
          <div className="text-[11px] text-slate-500 mb-2">Why this rate is defensible vs the next best alternative.</div>
          <div className="bg-cream rounded-lg p-2 mb-2 text-xs">
            <div className="flex justify-between items-baseline">
              <span className="text-slate-500">Next-best alternative</span>
              <span className="font-semibold text-navy">{eve.next_best_alternative.name} — ${eve.next_best_alternative.avg_rate}</span>
            </div>
            <div className="flex justify-between items-baseline mt-1">
              <span className="text-slate-500">Total value premium</span>
              <span className="font-bold text-gold">+${eve.total_value_premium} ({eve.premium_vs_nba_pct.toFixed(0)}%)</span>
            </div>
            <div className="flex justify-between items-baseline mt-1 pt-1 border-t border-slate-200">
              <span className="text-navy font-bold">Justified rate</span>
              <span className="text-xl font-bold text-sage">${eve.justified_rate}</span>
            </div>
          </div>

          {/* Stacked value driver bars */}
          <div className="space-y-1">
            {eve.value_drivers.sort((a, b) => b.value_estimate - a.value_estimate).map(d => (
              <div key={d.id}>
                <div className="flex items-baseline justify-between text-[11px]">
                  <span className="text-slate-700">{d.name}</span>
                  <span className="text-gold font-bold">+${d.value_estimate}</span>
                </div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-gold rounded-full"
                       style={{ width: `${(d.value_estimate / Math.max(...eve.value_drivers.map(x => x.value_estimate))) * 100}%` }} />
                </div>
                <div className="text-[9px] text-slate-400 italic mt-0.5">{d.evidence}</div>
              </div>
            ))}
          </div>

          <div className="mt-3 bg-navy/5 border-l-2 border-navy rounded p-2 text-[11px] italic text-slate-700">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-navy not-italic mb-0.5">Guest-facing script:</div>
                <div>{eve.guest_facing_justification}</div>
              </div>
              <button onClick={() => copy(eve.guest_facing_justification, 'eve')}
                className="text-[10px] font-bold text-navy hover:text-gold whitespace-nowrap">
                {copyState === 'eve' ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          </div>
        </Section>
      )}
    </div>
  )
}

function Section({ title, emoji, open, onToggle, children }:
  { title: string; emoji: string; open: boolean; onToggle: () => void; children: any }) {
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
      <button onClick={onToggle}
        className="w-full px-3 py-2 flex items-center gap-2 bg-cream hover:bg-cream/60 text-left">
        <span>{emoji}</span>
        <span className="text-xs font-bold uppercase tracking-wider text-navy flex-1">{title}</span>
        <span className="text-slate-400">{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  )
}

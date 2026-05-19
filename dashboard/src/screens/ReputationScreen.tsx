import { useEffect, useState } from 'react'
import { format, parseISO } from 'date-fns'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

interface PlatformScore {
  current: number; trend_3mo: number; review_count: number
  history?: { date: string; score: number }[]
}
interface RepData {
  your_scores: Record<string, PlatformScore>
  competitor_scores: Record<string, Record<string, number>>
  pricing_power_score: number
  rate_premium_justified_pct: number
  monthly_history: { date: string; platform: string; score: number; review_count: number }[]
  alerts: { severity: string; message: string }[]
  keywords: { positive: string[]; negative: string[]; competitor_gaps: string[] }
}

const PLATFORM_META: Record<string, { label: string; icon: string; maxScore: number }> = {
  tripadvisor: { label: 'TripAdvisor',  icon: '🦉', maxScore: 5  },
  google:      { label: 'Google',       icon: '🔵', maxScore: 5  },
  booking_com: { label: 'Booking.com',  icon: '🟦', maxScore: 10 },
  expedia:     { label: 'Expedia',      icon: '🟡', maxScore: 5  },
}

function TrendArrow({ v }: { v: number }) {
  if (v > 0.05) return <span className="text-sage">↑ {v.toFixed(2)}</span>
  if (v < -0.05) return <span className="text-coral">↓ {Math.abs(v).toFixed(2)}</span>
  return <span className="text-slate-400">→ flat</span>
}

export default function ReputationScreen({ }: Props) {
  return (
    <LockedFeature featureName="Reputation & Review Intelligence" featureKey="reputation"
      description="Monitor TripAdvisor, Google, Booking.com, and Expedia reviews for your property AND competitors. Surface pricing power score, sentiment trends, and competitive gaps."
    >
      <Body />
    </LockedFeature>
  )
}

function Body() {
  const [data, setData] = useState<RepData | null>(null)
  useEffect(() => {
    fetch('/api/reputation').then(r => r.json()).then(setData).catch(() => setData(null))
  }, [])
  if (!data) return <div className="flex-1 bg-cream flex items-center justify-center text-slate-400">Loading reviews…</div>

  // Build comp trend chart: pick months and assemble {date, you, comp1, comp2}
  const taHistory = data.your_scores.tripadvisor?.history ?? []
  const chartData = taHistory.map(point => {
    const row: any = { date: format(parseISO(point.date), 'MMM yy'), you: point.score }
    // Use static competitor baselines synthesized for the chart
    Object.entries(data.competitor_scores).slice(0, 4).forEach(([name, scores]) => {
      row[name] = scores.tripadvisor
    })
    return row
  })

  return (
    <div className="flex-1 overflow-y-auto bg-cream p-5 pb-20">
      <h1 className="text-navy font-bold text-xl">Reputation &amp; Review Intelligence</h1>
      <p className="text-slate-500 text-sm mb-4">How your ratings affect your pricing power.</p>

      {/* Pricing Power Card */}
      <div data-tour="pricing-power" className="bg-white rounded-xl shadow-sm border-2 border-gold/30 p-5 mb-4">
        <div className="flex items-baseline justify-between flex-wrap gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[2px] text-gold font-bold">Pricing Power Score</div>
            <div className="text-5xl font-bold text-navy mt-1">{data.pricing_power_score}<span className="text-slate-300 text-2xl">/100</span></div>
          </div>
          <div className="flex-1 min-w-[280px]">
            <div className="text-sm text-slate-700">
              Your <strong className="text-navy">{data.your_scores.tripadvisor?.current ?? '—'}</strong> TripAdvisor rating justifies a{' '}
              <strong className="text-gold">{data.rate_premium_justified_pct}%</strong> rate premium above the average competitor.
            </div>
            <div className="text-xs text-slate-500 mt-1">
              At Anchorage's ~$380 base rate, that's worth approximately <strong>${Math.round(380 * data.rate_premium_justified_pct / 100)}/booking</strong>.
            </div>
          </div>
        </div>
      </div>

      {/* Platform scores */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        {Object.entries(data.your_scores).map(([key, score]) => {
          const meta = PLATFORM_META[key] ?? { label: key, icon: '⭐', maxScore: 5 }
          return (
            <div key={key} className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
              <div className="text-2xl">{meta.icon}</div>
              <div className="font-bold text-navy mt-1">{meta.label}</div>
              <div className="text-3xl font-bold text-navy mt-1">{score.current}<span className="text-slate-400 text-sm">/{meta.maxScore}</span></div>
              <div className="text-[11px] mt-1"><TrendArrow v={score.trend_3mo} /> <span className="text-slate-400">vs 3 mo ago</span></div>
              <div className="text-[10px] text-slate-400 mt-0.5">{score.review_count.toLocaleString()} reviews</div>
            </div>
          )
        })}
      </div>

      {/* Competitor trend chart */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 mb-4">
          <h2 className="font-bold text-navy mb-1">TripAdvisor Rating Trend — You vs Competitors</h2>
          <p className="text-xs text-slate-500 mb-3">12-month trailing window. Gold = your rating.</p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 5, right: 15, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis domain={[3.5, 5]} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend iconType="line" iconSize={10} wrapperStyle={{ fontSize: 10 }} />
              <Line type="monotone" dataKey="you" stroke="#A07830" strokeWidth={3} dot={{ r: 3 }} name="Anchorage 1770" />
              {Object.keys(data.competitor_scores).slice(0, 4).map((name, i) => (
                <Line key={name} type="monotone" dataKey={name}
                  stroke={['#94A3B8', '#64748B', '#475569', '#334155'][i % 4]}
                  strokeWidth={1.5} strokeDasharray="4 3" dot={false} name={name} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Keywords */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
          <div className="text-[10px] uppercase tracking-wider text-sage font-bold mb-2">What guests love</div>
          <div className="flex flex-wrap gap-1.5">
            {data.keywords.positive.map(k => (
              <span key={k} className="text-xs bg-sage/15 text-sage-dark px-2 py-0.5 rounded-full">{k}</span>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
          <div className="text-[10px] uppercase tracking-wider text-coral font-bold mb-2">Improvement opportunities</div>
          <div className="flex flex-wrap gap-1.5">
            {data.keywords.negative.map(k => (
              <span key={k} className="text-xs bg-coral/10 text-coral px-2 py-0.5 rounded-full">{k}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Competitor gaps */}
      <div className="bg-white rounded-xl shadow-sm border border-gold/30 p-4 mb-4">
        <div className="text-[10px] uppercase tracking-wider text-gold-dark font-bold mb-2">★ Competitor weaknesses to exploit</div>
        <ul className="text-sm text-slate-700 space-y-1">
          {data.keywords.competitor_gaps.map((g, i) => (
            <li key={i}>— {g}</li>
          ))}
        </ul>
      </div>

      {/* Alerts */}
      {data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((a, i) => (
            <div key={i} className={`rounded-xl p-3 border ${
              a.severity === 'warning' ? 'bg-amber-50 border-amber-200 text-amber-800'
              : a.severity === 'positive' ? 'bg-sage/10 border-sage/30 text-sage-dark'
                                            : 'bg-navy/5 border-navy/20 text-navy'}`}>
              <div className="text-sm font-semibold">{a.severity === 'positive' ? '↑' : '⚠'} {a.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

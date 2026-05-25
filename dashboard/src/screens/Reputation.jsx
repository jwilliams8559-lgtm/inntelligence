import { useState, useEffect } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { getReputation } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const PLATFORM_LABEL = {
  tripadvisor: 'TripAdvisor', google: 'Google', booking_com: 'Booking.com', expedia: 'Expedia',
}

export default function Reputation() {
  const [r, setR] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getReputation().then(setR).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!r) return <LoadingSpinner label="Loading reputation…" />

  const ta = r.your_scores?.tripadvisor
  const chart = (ta?.history || []).map((h) => ({ date: h.date.slice(0, 7), score: h.score }))

  return (
    <div>
      <ScreenHeader title="Reputation Intelligence" subtitle="Review scores across platforms · how reputation justifies your rate premium" />

      <div className="rounded-2xl bg-navy text-white p-6 mb-6 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div>
          <div className="text-gold-light text-sm uppercase tracking-wide font-semibold">Pricing power score</div>
          <div className="text-6xl font-extrabold text-gold mt-1">{r.pricing_power_score}</div>
          <div className="text-white/70 text-sm mt-1">Reputation justifies a <span className="text-gold-light font-semibold">+{r.rate_premium_justified_pct}%</span> rate premium</div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {Object.entries(r.your_scores).map(([plat, s]) => (
            <div key={plat} className="text-center">
              <div className="text-2xl font-bold">{s.current}</div>
              <div className="text-[11px] text-gold-light">{PLATFORM_LABEL[plat] || plat}</div>
              <div className={`text-[10px] ${s.trend_3mo >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {s.trend_3mo >= 0 ? '▲' : '▼'} {Math.abs(s.trend_3mo)} 3mo
              </div>
            </div>
          ))}
        </div>
      </div>

      {r.alerts.length > 0 && (
        <div className="space-y-2 mb-6">
          {r.alerts.map((a, i) => (
            <div key={i} className={`rounded-lg border p-3 text-sm ${a.severity === 'positive' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}`}>
              {a.message}
            </div>
          ))}
        </div>
      )}

      {chart.length > 0 && (
        <Card title="TripAdvisor Score Trend" className="mb-6">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chart} margin={{ top: 6, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} stroke="#94a3b8" />
              <YAxis domain={[4, 5]} tick={{ fontSize: 10 }} stroke="#94a3b8" />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#c9a84c" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="What Guests Love">
          <div className="flex flex-wrap gap-2 mb-4">
            {r.keywords.positive.map((k, i) => <Pill key={i} tone="gold">{k}</Pill>)}
          </div>
          <div className="text-xs font-semibold text-gray-500 mb-1">Watch areas</div>
          <div className="flex flex-wrap gap-2">
            {r.keywords.negative.map((k, i) => <Pill key={i} tone="rose">{k}</Pill>)}
          </div>
        </Card>
        <Card title="Competitor Gaps to Exploit">
          <ul className="space-y-2">
            {r.keywords.competitor_gaps.map((g, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-gold">◆</span>{g}</li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

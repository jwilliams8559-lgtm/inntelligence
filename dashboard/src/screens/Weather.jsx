import { useState, useEffect } from 'react'
import { getWeather } from '../api/client'
import { ScreenHeader, Card, StatCard, Pill } from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

function demandLabel(blend) {
  if (blend > 0) return { tone: 'gold', text: `+${Math.round(blend * 100)}% demand` }
  if (blend < 0) return { tone: 'rose', text: `${Math.round(blend * 100)}% demand` }
  return { tone: 'gray', text: 'neutral' }
}

export default function Weather() {
  const [w, setW] = useState(null)
  const [err, setErr] = useState(null)
  useEffect(() => { getWeather().then(setW).catch((e) => setErr(e.message)) }, [])

  if (err) return <ErrorBanner message={err} />
  if (!w) return <LoadingSpinner label="Loading forecast…" />
  if (w.error) return <ErrorBanner message={w.error} />

  const fc = w.forecast || []
  const temps = fc.map((d) => d.temp)
  const tHi = temps.length ? Math.max(...temps) : null
  const tLo = temps.length ? Math.min(...temps) : null
  const loc = w.location?.city ? `${w.location.city}, ${w.location.state}` : 'Beaufort, SC'

  return (
    <div>
      <ScreenHeader title="Weather Intelligence" subtitle={`${loc} · live NWS forecast feeding demand signals`} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatCard label="Good Weather Days" value={`${w.good_day_pct}%`} sub={`${w.good_day_count} of ${fc.length} days`} accent />
        <StatCard label="High / Low" value={tHi != null ? `${tHi}° / ${tLo}°` : '—'} sub="next 7 days" />
        <StatCard label="Forecast Days" value={fc.length} sub="daytime periods" />
        <StatCard label="Data Source" value="NWS" sub={w.data_source} />
      </div>

      <Card title="7-Day Forecast & Demand Impact">
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {fc.map((d, i) => {
            const dl = demandLabel(d.demand_blend)
            return (
              <div key={i} className={`rounded-xl border p-3 text-center ${d.good_weather ? 'border-gold/50 bg-gold/5' : 'border-gray-200 bg-white'}`}>
                <div className="text-[11px] font-semibold text-navy">{d.name}</div>
                <div className="text-3xl my-1">{d.icon}</div>
                <div className="text-xl font-extrabold text-navy">{d.temp}°{d.temp_unit}</div>
                <div className="text-[10px] text-gray-500 mt-1 leading-tight h-7 overflow-hidden">{d.short}</div>
                <div className="text-[10px] text-gray-400 mt-1">{d.wind}</div>
                <div className="mt-2 flex justify-center"><Pill tone={dl.tone}>{dl.text}</Pill></div>
              </div>
            )
          })}
          {fc.length === 0 && <p className="text-sm text-gray-400">No forecast available.</p>}
        </div>
      </Card>
    </div>
  )
}

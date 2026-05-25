import { useState, useEffect, Fragment } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { usePrices } from '../context/PriceContext'
import { getMarketIntel, getCompetitive } from '../api/client'
import {
  ScreenHeader, Card, Segmented, YoYToggle, ExportButton, LastUpdated, exportToCsv, usd,
} from '../components/ui'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const TIERS = [
  { value: 'average', label: 'Average' },
  { value: 'waterfront', label: 'Waterfront' },
  { value: 'water_view', label: 'Water View' },
  { value: 'garden', label: 'Garden' },
  { value: 'carriage_house', label: 'Carriage House' },
  { value: 'signature_suite', label: 'Signature' },
  { value: 'grand_parlor', label: 'Grand Parlor' },
]
const RANGES = [
  { value: 7, label: 'Week' }, { value: 14, label: '2 Weeks' },
  { value: 30, label: 'Month' }, { value: 90, label: '90 Days' },
]
const fmtDay = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

export default function CompetitiveIntel() {
  const { lastUpdated } = usePrices()
  const [tier, setTier] = useState('average')
  const [days, setDays] = useState(14)
  const [yoy, setYoy] = useState(false)
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [mi, setMi] = useState(null)
  const [miErr, setMiErr] = useState(null)

  useEffect(() => { getMarketIntel().then(setMi).catch((e) => setMiErr(e.message)) }, [])
  useEffect(() => {
    let live = true; setData(null); setErr(null)
    getCompetitive(tier, days).then((d) => live && setData(d)).catch((e) => live && setErr(e.message))
    return () => { live = false }
  }, [tier, days])

  if (err) return <ErrorBanner message={err} />
  if (!data) return <LoadingSpinner label="Loading competitive intelligence…" />

  const chartData = data.dates.map((dt, i) => ({
    label: fmtDay(dt), you: data.you[i], market: data.comp_avg[i], lastYear: data.you_last_year[i],
  }))
  const propName = data.property_name
  const grouped = {}
  data.competitors.forEach((c) => { (grouped[c.tier] ||= []).push(c) })

  const onExport = () => {
    const rows = data.dates.map((dt, i) => {
      const row = { date: dt, you: data.you[i], comp_avg: data.comp_avg[i], you_last_year: data.you_last_year[i] }
      data.competitors.forEach((c) => { row[c.name] = c.rates[i] })
      return row
    })
    exportToCsv(`competitive-${tier}-${days}d`, rows)
  }

  return (
    <div>
      <ScreenHeader
        title="Competitive Intelligence"
        subtitle={`${propName} vs Beaufort comp set · like-for-like by room category`}
        right={<div className="flex items-center gap-2 flex-wrap"><YoYToggle on={yoy} onChange={setYoy} /><ExportButton onClick={onExport} /><LastUpdated at={lastUpdated} /></div>}
      />

      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <Segmented options={TIERS} value={tier} onChange={setTier} />
        <Segmented options={RANGES} value={days} onChange={setDays} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card title="Market Pressure">
          {!mi ? <LoadingSpinner label="…" /> : (
            <div className="text-center py-2">
              <div className="text-6xl font-extrabold" style={{ color: mi.pressure_color }}>{mi.pressure_score}<span className="text-2xl text-gray-300">/10</span></div>
              <div className="font-semibold mt-1" style={{ color: mi.pressure_color }}>{mi.pressure_label}</div>
              <p className="text-xs text-gray-500 mt-3 leading-snug">{mi.recommendation}</p>
            </div>
          )}
        </Card>

        <Card title={`Rate Compression — ${TIERS.find((t) => t.value === tier).label}`} className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={210}>
            <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef1f4" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} stroke="#94a3b8" interval={Math.max(0, Math.floor(chartData.length / 10))} />
              <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" tickFormatter={(v) => `$${v}`} domain={['dataMin - 20', 'dataMax + 20']} />
              <Tooltip formatter={(v, n) => [usd(v), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="you" name={propName} stroke="#c9a84c" strokeWidth={2.5} dot={false} />
              <Line type="monotone" dataKey="market" name="Comp avg" stroke="#0a2342" strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              {yoy && <Line type="monotone" dataKey="lastYear" name="You (last year)" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="2 3" dot={false} />}
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title={`Competitor Rates — ${TIERS.find((t) => t.value === tier).label} · ${days} days`}>
        <div className="overflow-x-auto">
          <table className="text-xs border-separate" style={{ borderSpacing: 0 }}>
            <thead>
              <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                <th className="sticky left-0 z-10 bg-white text-left py-2 pr-3">Property</th>
                {data.dates.map((d) => <th key={d} className="text-right px-2 whitespace-nowrap">{fmtDay(d)}</th>)}
              </tr>
            </thead>
            <tbody>
              <tr className="bg-gold/10 font-bold text-navy">
                <td className="sticky left-0 z-10 bg-gold/10 text-left py-2 pr-3 whitespace-nowrap">★ {propName}</td>
                {data.you.map((r, i) => <td key={i} className="text-right px-2">{usd(r)}</td>)}
              </tr>
              {yoy && (
                <tr className="text-gray-400 italic">
                  <td className="sticky left-0 z-10 bg-white text-left py-1 pr-3 whitespace-nowrap">↳ last year</td>
                  {data.you_last_year.map((r, i) => <td key={i} className="text-right px-2">{usd(r)}</td>)}
                </tr>
              )}
              <tr className="bg-navy/5 font-semibold text-navy border-y border-navy/10">
                <td className="sticky left-0 z-10 bg-navy/5 text-left py-2 pr-3 whitespace-nowrap">Comp-set average</td>
                {data.comp_avg.map((r, i) => <td key={i} className="text-right px-2">{usd(r)}</td>)}
              </tr>
              <tr>
                <td colSpan={data.dates.length + 1} className="text-[10px] text-gray-400 italic pl-3 pt-0.5 pb-1.5">
                  Based on {data.comparable_count} comparable propert{data.comparable_count === 1 ? 'y' : 'ies'} — excludes N/A, luxury &amp; budget references
                </td>
              </tr>
              {Object.entries(grouped).map(([t, comps]) => (
                <Fragment key={t}>
                  <tr>
                    <td colSpan={data.dates.length + 1} className="bg-navy-light/10 text-navy font-bold uppercase text-[10px] tracking-wide py-1.5 px-1">
                      {data.tier_labels[t] || `Tier ${t}`}
                    </td>
                  </tr>
                  {comps.map((c) => {
                    const refBadge = c.reference ? (
                      <span title={c.reference_tooltip}
                        className={`ml-1 text-[9px] not-italic font-semibold px-1.5 py-0.5 rounded-full border ${
                          c.reference === 'luxury' ? 'bg-gold/15 text-gold-dark border-gold/40' : 'bg-gray-100 text-gray-500 border-gray-300'}`}>
                        {c.reference_label}
                      </span>
                    ) : null
                    if (!c.available) {
                      return (
                        <tr key={c.name} className="border-b border-gray-100 bg-gray-50 text-gray-300"
                            title="This property does not offer a comparable room type">
                          <td className="sticky left-0 z-10 bg-gray-50 text-left py-2 pr-3 whitespace-nowrap italic">{c.name}{refBadge}</td>
                          {data.dates.map((_, i) => <td key={i} className="text-right px-2 italic">N/A</td>)}
                        </tr>
                      )
                    }
                    if (c.reference) {
                      return (
                        <tr key={c.name} className="border-b border-gray-100 hover:bg-gray-50" title={c.reference_tooltip}>
                          <td className="sticky left-0 z-10 bg-white text-left py-2 pr-3 text-gray-500 whitespace-nowrap">{c.name}{refBadge}</td>
                          {c.rates.map((r, i) => <td key={i} className="text-right px-2 text-gray-400 italic">{usd(r)}</td>)}
                        </tr>
                      )
                    }
                    if (c.partial) {
                      const tip = `Limited availability — not all units offer this view type${c.label ? ` (${c.label})` : ''}`
                      return (
                        <tr key={c.name} className="border-b border-gray-100 hover:bg-amber-50/40" title={tip}>
                          <td className="sticky left-0 z-10 bg-white text-left py-2 pr-3 text-navy whitespace-nowrap">
                            {c.name} <span className="text-amber-600 text-[10px] not-italic">⚠ {c.label}</span>
                          </td>
                          {c.rates.map((r, i) => (
                            <td key={i} className="text-right px-2 italic text-amber-600" title={tip}>{usd(r)}*</td>
                          ))}
                        </tr>
                      )
                    }
                    return (
                      <tr key={c.name} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="sticky left-0 z-10 bg-white text-left py-2 pr-3 text-navy whitespace-nowrap">{c.name}</td>
                        {c.rates.map((r, i) => <td key={i} className="text-right px-2 text-gray-600">{usd(r)}</td>)}
                      </tr>
                    )
                  })}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {miErr && <div className="mt-4"><ErrorBanner message={`Market intel: ${miErr}`} /></div>}
    </div>
  )
}

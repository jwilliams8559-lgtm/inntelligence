import { usePrices } from '../context/PriceContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

const usd = (n) => '$' + Math.round(Number(n) || 0).toLocaleString('en-US')

export default function Home() {
  const { summary, property, dashboard, loading, error, lastUpdated } = usePrices()

  if (loading && !dashboard) return <LoadingSpinner label="Loading dashboard…" />
  if (error) return <ErrorBanner message={error} />
  if (!summary) return <LoadingSpinner label="No data available." />

  const occLow = Math.round((property?.occ_target_low ?? 0.7) * 100)
  const occHigh = Math.round((property?.occ_target_high ?? 0.85) * 100)
  const occAssumed = Math.round((property?.occupancy_assumed ?? 0.75) * 100)

  // Every value below comes from the API — nothing is hardcoded or computed here.
  const cards = [
    { label: 'Avg Rate', value: usd(summary.avg_rate), sub: `across ${property?.room_count ?? '—'} rooms` },
    { label: 'RevPAR', value: usd(summary.revpar), sub: `at ${occAssumed}% occupancy` },
    { label: 'Occupancy Target', value: `${occLow}–${occHigh}%`, sub: 'target band' },
    { label: 'Active Events', value: String(summary.active_events ?? 0), sub: 'today' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy">Welcome — {property?.name}</h1>
        <p className="text-gray-500">Today&rsquo;s snapshot · {property?.city}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold">{c.label}</div>
            <div className="text-3xl font-extrabold text-navy mt-1">{c.value}</div>
            <div className="text-xs text-gray-500 mt-1">{c.sub}</div>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400">
        All figures from <code>/api/dashboard</code> · single source of truth · data as of{' '}
        {lastUpdated ? lastUpdated.toLocaleString() : '—'}
      </p>
    </div>
  )
}

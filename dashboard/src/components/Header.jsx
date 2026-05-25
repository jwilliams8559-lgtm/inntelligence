import { usePrices } from '../context/PriceContext'

export default function Header() {
  const { property, lastUpdated, loading, refresh } = usePrices()

  // Property name + city only — never a street address.
  const name = property?.name || 'The Bay Street Inn'
  const city = property?.city || 'Beaufort, SC'
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  })
  const stamp = lastUpdated
    ? lastUpdated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : '—'

  return (
    <header className="bg-navy text-white px-6 py-3 flex items-center justify-between gap-4 flex-wrap">
      <div className="min-w-0">
        <span className="font-bold text-lg">{name}</span>
        <span className="text-gold-light"> — {city}</span>
      </div>
      <div className="flex items-center gap-4 text-sm flex-wrap">
        <span className="text-white/70">{today}</span>
        <span className="text-gold-light">Data as of {stamp}</span>
        <button
          onClick={refresh}
          disabled={loading}
          className="bg-gold text-navy font-semibold px-3 py-1.5 rounded-md hover:bg-gold-light disabled:opacity-60 transition-colors"
        >
          {loading ? 'Refreshing…' : '⟳ Refresh'}
        </button>
      </div>
    </header>
  )
}

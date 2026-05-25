// Shared presentational primitives — navy #0a2342 / gold #c9a84c, reused by
// every screen so styling stays consistent. No data logic lives here.

export const usd = (n) => '$' + Math.round(Number(n) || 0).toLocaleString('en-US')
export const usd2 = (n) => '$' + (Number(n) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const pct = (n) => `${Number(n) || 0}%`

export function ScreenHeader({ title, subtitle, right }) {
  return (
    <div className="flex items-end justify-between gap-4 flex-wrap mb-5">
      <div>
        <h1 className="text-2xl font-bold text-navy">{title}</h1>
        {subtitle && <p className="text-gray-500 text-sm mt-0.5">{subtitle}</p>}
      </div>
      {right}
    </div>
  )
}

export function Card({ title, right, children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 shadow-sm ${className}`}>
      {(title || right) && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          {title && <h2 className="font-semibold text-navy text-sm">{title}</h2>}
          {right}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  )
}

export function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-gray-400 font-semibold">{label}</div>
      <div className={`text-3xl font-extrabold mt-1 ${accent ? 'text-gold' : 'text-navy'}`}>{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

const STATUS_STYLES = {
  premium:  'bg-emerald-100 text-emerald-800',
  hold:     'bg-amber-100 text-amber-800',
  discount: 'bg-rose-100 text-rose-800',
}
export function StatusPill({ status, label }) {
  const cls = STATUS_STYLES[status] || 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-block text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${cls}`}>
      {label || status}
    </span>
  )
}

export function Pill({ children, tone = 'gold' }) {
  const tones = {
    gold: 'bg-gold/15 text-gold-dark border-gold/30',
    navy: 'bg-navy/10 text-navy border-navy/20',
    gray: 'bg-gray-100 text-gray-600 border-gray-200',
    rose: 'bg-rose-100 text-rose-700 border-rose-200',
    emerald: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  }
  return (
    <span className={`inline-block text-[11px] font-semibold px-2 py-0.5 rounded-full border ${tones[tone] || tones.gold}`}>
      {children}
    </span>
  )
}

// ── Reusable controls (shared across upgraded screens) ───────────────────────

// Segmented tab/selector control. options = [{value,label}] or [string].
export function Segmented({ options, value, onChange, size = 'sm' }) {
  const opts = options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o))
  const pad = size === 'sm' ? 'px-3 py-1 text-xs' : 'px-4 py-1.5 text-sm'
  return (
    <div className="inline-flex flex-wrap rounded-lg border border-gray-200 bg-gray-50 p-0.5 gap-0.5">
      {opts.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`${pad} font-semibold rounded-md transition-colors ${
            value === o.value ? 'bg-navy text-white shadow-sm' : 'text-gray-600 hover:text-navy'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// YoY comparison toggle.
export function YoYToggle({ on, onChange }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg border transition-colors ${
        on ? 'bg-gold text-navy border-gold' : 'bg-white text-gray-500 border-gray-200 hover:border-gold/50'
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${on ? 'bg-navy' : 'bg-gray-300'}`} />
      vs Last Year
    </button>
  )
}

// Confidence indicator.
export function ConfidencePill({ level }) {
  const map = {
    High:   'emerald',
    Medium: 'gold',
    Low:    'rose',
  }
  return <Pill tone={map[level] || 'gray'}>{level} confidence</Pill>
}

// Last-updated timestamp (expects a Date or ISO string; falls back to now).
export function LastUpdated({ at }) {
  const d = at ? new Date(at) : new Date()
  const txt = isNaN(d) ? '—' : d.toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  })
  return <span className="text-[11px] text-gray-400">Updated {txt}</span>
}

// CSV export: rows = array of objects, columns = [{key,label}] (optional).
export function exportToCsv(filename, rows, columns) {
  if (!rows || rows.length === 0) return
  const cols = columns || Object.keys(rows[0]).map((k) => ({ key: k, label: k }))
  const esc = (v) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const header = cols.map((c) => esc(c.label)).join(',')
  const body = rows.map((r) => cols.map((c) => esc(r[c.key])).join(',')).join('\n')
  const blob = new Blob([header + '\n' + body], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function ExportButton({ onClick, label = 'Export CSV' }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg border border-gray-200 bg-white text-gray-600 hover:border-navy hover:text-navy transition-colors"
    >
      ↓ {label}
    </button>
  )
}

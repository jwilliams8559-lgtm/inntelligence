import { useState } from 'react'

export type RangeKey = '7d' | '30d' | '90d' | '6m' | '12m' | '24m' | 'custom'

interface Props {
  value: RangeKey
  onChange: (range: RangeKey, custom?: { from: string; to: string }) => void
  options?: RangeKey[]
}

const LABELS: Record<RangeKey, string> = {
  '7d':   '7 Days',
  '30d':  '30 Days',
  '90d':  '90 Days',
  '6m':   '6 Months',
  '12m':  '12 Months',
  '24m':  '24 Months',
  custom: 'Custom',
}

const DEFAULT_OPTIONS: RangeKey[] = ['30d', '90d', '6m', '12m', '24m', 'custom']

export default function DateRangePicker({ value, onChange, options = DEFAULT_OPTIONS }: Props) {
  const [customFrom, setCustomFrom] = useState('')
  const [customTo,   setCustomTo]   = useState('')
  const [openCustom, setOpenCustom] = useState(false)

  return (
    <div className="flex items-center gap-1 text-xs relative">
      {options.map(opt => (
        <button key={opt}
          onClick={() => {
            if (opt === 'custom') { setOpenCustom(true); return }
            onChange(opt)
          }}
          className={`px-2.5 py-1 rounded font-semibold transition-colors ${
            value === opt ? 'bg-gold text-white' : 'bg-white border border-slate-200 text-slate-600 hover:border-navy/30'
          }`}>
          {LABELS[opt]}
        </button>
      ))}

      {openCustom && (
        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-slate-200 p-3 z-40 w-72">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold mb-2">Custom date range</div>
          <div className="flex items-center gap-2">
            <label className="flex-1 text-[11px]">
              <div className="text-slate-500">From</div>
              <input type="date" className="w-full border border-slate-200 rounded px-2 py-1" value={customFrom} onChange={e => setCustomFrom(e.target.value)} />
            </label>
            <label className="flex-1 text-[11px]">
              <div className="text-slate-500">To</div>
              <input type="date" className="w-full border border-slate-200 rounded px-2 py-1" value={customTo} onChange={e => setCustomTo(e.target.value)} />
            </label>
          </div>
          <div className="flex justify-end gap-2 mt-2">
            <button onClick={() => setOpenCustom(false)} className="text-[11px] text-slate-500">Cancel</button>
            <button onClick={() => {
              if (customFrom && customTo) {
                onChange('custom', { from: customFrom, to: customTo })
                setOpenCustom(false)
              }
            }} className="bg-navy text-white text-[11px] font-bold px-3 py-1 rounded">Apply</button>
          </div>
        </div>
      )}
    </div>
  )
}

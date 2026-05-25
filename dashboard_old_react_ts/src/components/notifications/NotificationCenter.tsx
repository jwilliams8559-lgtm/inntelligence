import { useEffect, useState } from 'react'

interface Notification {
  id: string; title: string; body: string
  category: string; priority: 'critical' | 'high' | 'medium' | 'low'
  types: string[]; action_url?: string | null
  created_at: string; read: boolean; dismissed: boolean
}

interface Props { open: boolean; onClose: () => void }

type Filter = 'all' | 'unread' | 'rate_surge' | 'competitor_event' | 'system'

const FILTER_LABELS: Record<Filter, string> = {
  all: 'All', unread: 'Unread',
  rate_surge: 'Rate Alerts', competitor_event: 'Competitive', system: 'System',
}

const PRIORITY_BORDER: Record<string, string> = {
  critical: 'border-coral', high: 'border-gold',
  medium:   'border-navy',  low:  'border-slate-300',
}

export default function NotificationCenter({ open, onClose }: Props) {
  const [items, setItems]   = useState<Notification[]>([])
  const [filter, setFilter] = useState<Filter>('all')

  useEffect(() => {
    if (!open) return
    fetch('/api/notifications').then(r => r.json()).then(j => setItems(j.notifications || []))
  }, [open])

  if (!open) return null

  const filtered = items.filter(n => {
    if (filter === 'all')    return true
    if (filter === 'unread') return !n.read
    return n.category === filter
  })

  async function markRead(id: string) {
    await fetch(`/api/notifications/${id}/read`, { method: 'POST' })
    setItems(items.map(n => n.id === id ? { ...n, read: true } : n))
  }
  async function markAllRead() {
    await Promise.all(items.filter(n => !n.read).map(n =>
      fetch(`/api/notifications/${n.id}/read`, { method: 'POST' })))
    setItems(items.map(n => ({ ...n, read: true })))
  }

  return (
    <div className="fixed inset-0 z-50 bg-navy/40 flex items-start justify-end p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[80vh] flex flex-col mt-12 mr-4" onClick={e => e.stopPropagation()}>
        <header className="bg-navy text-white px-4 py-3 flex items-center justify-between rounded-t-2xl">
          <div className="font-bold">Notifications</div>
          <button onClick={onClose} className="text-white/70 hover:text-white text-2xl leading-none">×</button>
        </header>
        <div className="border-b border-slate-200 px-3 py-2 flex items-center justify-between flex-wrap gap-2">
          <div className="flex flex-wrap gap-1">
            {(Object.keys(FILTER_LABELS) as Filter[]).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`text-[11px] px-2 py-1 rounded font-semibold ${
                  filter === f ? 'bg-navy text-white' : 'bg-white text-slate-500 hover:text-navy'
                }`}>{FILTER_LABELS[f]}</button>
            ))}
          </div>
          <button onClick={markAllRead} className="text-[11px] text-gold-dark hover:underline">Mark all read</button>
        </div>
        <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
          {filtered.length === 0 && (
            <div className="text-center text-slate-400 text-sm py-10">No notifications</div>
          )}
          {filtered.map(n => (
            <div key={n.id} className={`p-3 border-l-4 ${PRIORITY_BORDER[n.priority] || 'border-slate-300'} ${!n.read ? 'bg-cream/40' : ''}`}>
              <div className="flex items-baseline justify-between gap-2">
                <div className="font-semibold text-navy text-sm">{n.title}</div>
                <span className="text-[10px] uppercase text-slate-400">{n.priority}</span>
              </div>
              <div className="text-xs text-slate-600 mt-1 leading-snug">{n.body}</div>
              <div className="flex items-baseline justify-between mt-2">
                <span className="text-[10px] text-slate-400">{n.category.replace('_', ' ')}</span>
                {!n.read && <button onClick={() => markRead(n.id)} className="text-[11px] text-navy hover:underline">Mark read</button>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

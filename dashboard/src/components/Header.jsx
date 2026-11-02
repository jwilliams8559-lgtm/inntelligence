import { useState } from 'react'
import { usePrices } from '../context/PriceContext'
import { useAuth } from '../context/AuthContext'
import { createPortalSession } from '../api/client'

export default function Header() {
  const { property, lastUpdated, loading, refresh } = usePrices()
  const { user, role, demoMode, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [billingBusy, setBillingBusy] = useState(false)
  const [billingMsg, setBillingMsg] = useState(null)

  // Property name + city only — never a street address.
  const name = property?.name || 'The Bay Street Inn'
  const city = property?.city || 'Beaufort, SC'
  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  })
  const stamp = lastUpdated
    ? lastUpdated.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : '—'

  const owner = user?.owner_name || user?.email || 'Account'
  const canBill = !!user && !demoMode && role !== 'tgc_admin'

  async function manageBilling() {
    setBillingBusy(true); setBillingMsg(null)
    try {
      const res = await createPortalSession({ return_url: window.location.href })
      if (res && res.url) { window.location.href = res.url; return }
      setBillingMsg('Billing isn’t set up on this account yet.')
    } catch {
      setBillingMsg('Could not open billing just now. Please try again in a moment.')
    }
    setBillingBusy(false)
  }

  return (
    <header className="bg-navy text-white px-6 py-3 flex items-center justify-between gap-4 flex-wrap relative">
      <div className="min-w-0">
        <span className="font-bold text-lg">{name}</span>
        <span className="text-gold-light"> — {city}</span>
      </div>
      <div className="flex items-center gap-4 text-sm flex-wrap">
        <span className="text-white/70 hidden md:inline">{today}</span>
        <span className="text-gold-light hidden sm:inline">Data as of {stamp}</span>
        <button onClick={refresh} disabled={loading}
          className="bg-gold text-navy font-semibold px-3 py-1.5 rounded-md hover:bg-gold-light disabled:opacity-60 transition-colors">
          {loading ? 'Refreshing…' : '⟳ Refresh'}
        </button>

        {user && !demoMode && (
          <div className="relative">
            <button onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-1.5 bg-white/10 hover:bg-white/20 border border-white/15 rounded-md px-3 py-1.5 font-semibold">
              <span className="truncate max-w-[12ch]">{owner}</span>
              <span className="text-[10px]">▾</span>
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 mt-2 w-60 bg-white text-navy rounded-xl shadow-2xl border border-gray-100 z-20 overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-100">
                    <div className="text-xs text-gray-500">Signed in as</div>
                    <div className="text-sm font-semibold truncate">{user?.email || owner}</div>
                  </div>
                  {canBill && (
                    <button onClick={manageBilling} disabled={billingBusy}
                      className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 disabled:opacity-60">
                      {billingBusy ? 'Opening…' : '💳 Manage billing & subscription'}
                      <div className="text-[11px] text-gray-400">Update your card, view invoices, or cancel</div>
                    </button>
                  )}
                  {billingMsg && <div className="px-4 py-2 text-[11px] text-rose-600 bg-rose-50">{billingMsg}</div>}
                  <button onClick={() => { setMenuOpen(false); logout() }}
                    className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 border-t border-gray-100">
                    Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </header>
  )
}

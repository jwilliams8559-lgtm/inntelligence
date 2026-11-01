import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import DemoOverlay from '../demo/DemoOverlay'
import FoundingMemberBanner from './FoundingMemberBanner'
import TrialBanner from './TrialBanner'
import DemoBanner from './DemoBanner'
import DemoWriteGuard from './DemoWriteGuard'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { demoReadOnly } = useAuth() || {}
  // Explicit guided-tour mode: the narrated walkthrough can be launched over the
  // read-only demo via ?tour=1 (the "Play the guided tour" button, or a direct
  // link such as /demo?tour=1). The free-navigation demo is unchanged when the
  // flag is absent.
  const guidedTour = typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('tour') === '1'
  return (
    <div className="flex h-screen bg-gray-50 text-navy">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <DemoBanner />
        <FoundingMemberBanner />
        <TrialBanner />
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
      {/* The public read-only demo is free-navigation (no auto-playing tour).
          The narrated DemoOverlay runs for a normal demo session, or on demand
          over the read-only demo when guided-tour mode is requested (?tour=1). */}
      {(!demoReadOnly || guidedTour) && <DemoOverlay />}
      <DemoWriteGuard />
    </div>
  )
}

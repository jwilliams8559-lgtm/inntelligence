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
          The narrated DemoOverlay is reserved for an explicit guided-tour mode. */}
      {!demoReadOnly && <DemoOverlay />}
      <DemoWriteGuard />
    </div>
  )
}

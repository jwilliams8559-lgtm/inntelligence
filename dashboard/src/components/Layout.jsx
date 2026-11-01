import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import DemoOverlay from '../demo/DemoOverlay'
import FoundingMemberBanner from './FoundingMemberBanner'
import TrialBanner from './TrialBanner'
import DemoBanner from './DemoBanner'
import DemoWriteGuard from './DemoWriteGuard'

export default function Layout() {
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
      {/* /demo opens with the narrated guided tour. DemoOverlay self-guards
          (it renders only inside a demo session, via `if (!demoMode) return null`),
          so this is inert for signed-in users. The tour can be skipped from its
          opening screen ("Explore the dashboard →") to free-navigate the
          read-only demo. */}
      <DemoOverlay />
      <DemoWriteGuard />
    </div>
  )
}

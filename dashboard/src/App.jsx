import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { PriceProvider } from './context/PriceContext'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Home from './screens/Home'
import ScreenPlaceholder from './screens/ScreenPlaceholder'
import { SCREENS } from './routes'

import RateCalendar from './screens/RateCalendar'
import CompetitiveIntel from './screens/CompetitiveIntel'
import FnBYield from './screens/FnBYield'
import ROIPerformance from './screens/ROIPerformance'
import Packages from './screens/Packages'
import Events from './screens/Events'
import Weather from './screens/Weather'
import Historical from './screens/Historical'
import Reputation from './screens/Reputation'
import RevenueIntelligence from './screens/RevenueIntelligence'
import GuestCRM from './screens/GuestCRM'
import GiftShop from './screens/GiftShop'
import PrivateEvents from './screens/PrivateEvents'
import Weddings from './screens/Weddings'
import ManagementConsole from './screens/ManagementConsole'
import AdminAnalytics from './screens/AdminAnalytics'
import Login from './screens/Login'
import Onboarding from './screens/Onboarding'
import Pricing from './screens/Pricing'

function DemoEntry() {
  const { startDemo } = useAuth()
  useEffect(() => {
    startDemo()
    // Log this /demo visit once; store visit_id so the overlay can mark
    // completion when the closing screen renders.
    try {
      if (!sessionStorage.getItem('inn_demo_visit')) {
        fetch('/api/demo/log', { method: 'POST' })
          .then((r) => r.json()).then((d) => {
            if (d && d.visit_id) {
              try { sessionStorage.setItem('inn_demo_visit', d.visit_id) } catch { /* ignore */ }
            }
          }).catch(() => {})
      }
    } catch { /* ignore */ }
  }, [startDemo])
  return <Navigate to="/" replace />
}

const BUILT = {
  '/rate-calendar': RateCalendar,
  '/competitive-intel': CompetitiveIntel,
  '/fnb-yield': FnBYield,
  '/roi-performance': ROIPerformance,
  '/packages': Packages,
  '/events': Events,
  '/weather': Weather,
  '/historical': Historical,
  '/reputation': Reputation,
  '/gap-night': RevenueIntelligence,
  '/guest-crm': GuestCRM,
  '/gift-shop': GiftShop,
  '/private-events': PrivateEvents,
  '/weddings': Weddings,
  '/management-console': ManagementConsole,
  '/admin/analytics': AdminAnalytics,
}
// Screens only tgc_admin may see.
const ADMIN_ONLY = new Set(['/management-console', '/admin/analytics'])

function FullScreenSpinner() {
  return (
    <div className="h-screen flex items-center justify-center bg-navy text-gold">
      <div className="w-10 h-10 border-4 border-gold border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// Gate for the authenticated dashboard. Open mode (no Supabase) lets everything
// through so local/demo stays usable.
function RequireAuth({ children }) {
  const { loading, openMode, user } = useAuth()
  if (loading) return <FullScreenSpinner />
  if (openMode) return children
  if (!user) return <Navigate to="/login" replace />
  if (user.pending_onboarding) return <Navigate to="/onboarding" replace />
  return children
}

function AdminRoute({ children }) {
  const { openMode, role } = useAuth()
  if (!openMode && role !== 'tgc_admin') return <Navigate to="/" replace />
  return children
}

function OnboardingRoute() {
  const { loading, openMode, user } = useAuth()
  if (loading) return <FullScreenSpinner />
  if (!openMode && !user) return <Navigate to="/login" replace />
  return <Onboarding />
}

function AppRoutes() {
  const { role, openMode } = useAuth()
  const isAdmin = openMode || role === 'tgc_admin'
  return (
    <Routes>
      {/* Public — no auth, no dashboard chrome */}
      <Route path="/login" element={<Login />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/demo" element={<DemoEntry />} />
      <Route path="/tour" element={<Navigate to="/demo" replace />} />
      <Route path="/onboarding" element={<OnboardingRoute />} />

      {/* Authenticated dashboard */}
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Home />} />
        {SCREENS.filter((s) => s.path !== '/tour').map((s) => {
          const Comp = BUILT[s.path]
          let el = Comp ? <Comp /> : <ScreenPlaceholder name={s.name} />
          if (ADMIN_ONLY.has(s.path)) el = <AdminRoute>{el}</AdminRoute>
          // Hide admin routes for non-admins by redirecting.
          if (ADMIN_ONLY.has(s.path) && !isAdmin) el = <Navigate to="/" replace />
          return <Route key={s.path} path={s.path} element={el} />
        })}
        <Route path="*" element={<ScreenPlaceholder name="Not Found" />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <PriceProvider>
        <AppRoutes />
      </PriceProvider>
    </AuthProvider>
  )
}

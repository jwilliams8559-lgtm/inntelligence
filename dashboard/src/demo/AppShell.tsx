/** Re-export the authenticated app shell from App.tsx so DemoMode can
 * mount the same dashboard the real users see, without re-implementing
 * the screen-router. Keeps a single source of truth for which screen
 * renders for each `tgc:navigate` event. */
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import type { Tenant, Property, Screen, AppRole } from '../lib/types'
import { PlanFeaturesProvider } from '../hooks/usePlanFeatures'
import { useAuth } from '../contexts/AuthContext'
import Layout from '../components/Layout'
import RateCalendar from '../screens/RateCalendar'
import DemandDashboard from '../screens/DemandDashboard'
import EventsScreen from '../screens/EventsScreen'
import CompetitiveIntel from '../screens/CompetitiveIntel'
import ReputationScreen from '../screens/ReputationScreen'
import FnBScreen from '../screens/FnBScreen'
import PerformanceScreen from '../screens/PerformanceScreen'
import HistoricalScreen from '../screens/HistoricalScreen'
import GuestCRM from '../screens/GuestCRM'
import BehaviorScreen from '../screens/BehaviorScreen'
import Packages from '../screens/Packages'
import ManagementConsole from '../screens/ManagementConsole'
import Settings from '../screens/Settings'

const SLUG = import.meta.env.VITE_TENANT_SLUG || 'anchorage-1770-demo'
const APP_ROLE: AppRole = (import.meta.env.VITE_APP_ROLE as AppRole) || 'shg_admin'

/** Same render tree as App.tsx → AppInner, but exported so DemoMode
 * can wrap it in its own AuthProvider. */
export default function AppShell() {
  const { user, isLoading: authLoading } = useAuth()
  if (authLoading || !user) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#F8F6F0' }}>
        <div style={{ color: '#1A3A5C', fontFamily: 'Inter, sans-serif' }}>Loading demo…</div>
      </div>
    )
  }
  return <Authenticated />
}

function Authenticated() {
  const [screen, setScreen] = useState<Screen>('calendar')
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [property, setProperty] = useState<Property | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const onNav = (e: any) => { if (e?.detail) setScreen(e.detail as Screen) }
    window.addEventListener('tgc:navigate', onNav)
    return () => window.removeEventListener('tgc:navigate', onNav)
  }, [])

  useEffect(() => {
    async function load() {
      try {
        const { data: t } = await supabase.from('tenants').select('id,name,slug').eq('slug', SLUG).single()
        if (!t) { setLoading(false); return }
        setTenant(t)
        const { data: p } = await supabase.from('properties').select('id,tenant_id,name,city,state,timezone').eq('tenant_id', t.id).single()
        if (p) setProperty(p)
        const { count } = await supabase.from('rate_recommendations').select('id', { count: 'exact', head: true }).eq('tenant_id', t.id).eq('status', 'pending')
        setPendingCount(count ?? 0)
      } catch { /* offline / Supabase unavailable */ }
      setLoading(false)
    }
    load()
  }, [])

  if (loading || !tenant || !property) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: '#F8F6F0' }}>
        <div style={{ color: '#1A3A5C', fontFamily: 'Inter, sans-serif' }}>Loading Anchorage 1770…</div>
      </div>
    )
  }

  const screenProps = { tenant, property, pendingCount, setPendingCount }

  return (
    <PlanFeaturesProvider>
      <Layout screen={screen} setScreen={setScreen} pendingCount={pendingCount}
              propertyName={property.name} propertyId={property.id} appRole={APP_ROLE}>
        {screen === 'calendar'     && <RateCalendar     {...screenProps} />}
        {screen === 'demand'       && <DemandDashboard  {...screenProps} />}
        {screen === 'events'       && <EventsScreen     {...screenProps} />}
        {screen === 'competitive'  && <CompetitiveIntel {...screenProps} />}
        {screen === 'reputation'   && <ReputationScreen {...screenProps} />}
        {screen === 'fnb'          && <FnBScreen        {...screenProps} />}
        {screen === 'crm'          && <GuestCRM         {...screenProps} />}
        {screen === 'behavior'     && <BehaviorScreen   {...screenProps} />}
        {screen === 'packages'     && <Packages         {...screenProps} />}
        {screen === 'performance'  && <PerformanceScreen />}
        {screen === 'historical'   && <HistoricalScreen   {...screenProps} />}
        {screen === 'management'   && APP_ROLE === 'shg_admin' && <ManagementConsole {...screenProps} />}
        {screen === 'settings'     && <Settings         {...screenProps} />}
      </Layout>
    </PlanFeaturesProvider>
  )
}

import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import type { Tenant, Property, Screen, AppRole } from './lib/types'
import { PlanFeaturesProvider } from './hooks/usePlanFeatures'
import Layout from './components/Layout'
import RateCalendar from './screens/RateCalendar'
import DemandDashboard from './screens/DemandDashboard'
import EventsScreen from './screens/EventsScreen'
import CompetitiveIntel from './screens/CompetitiveIntel'
import GuestCRM from './screens/GuestCRM'
import Packages from './screens/Packages'
import ManagementConsole from './screens/ManagementConsole'
import Settings from './screens/Settings'

const SLUG = import.meta.env.VITE_TENANT_SLUG || 'anchorage-1770-demo'
// In production the role is read from JWT app_role claim. For the demo we
// expose VITE_APP_ROLE so the management console can be toggled off when
// hosting at a tenant-facing URL. Default = shg_admin for Jim's deployment.
const APP_ROLE: AppRole = (import.meta.env.VITE_APP_ROLE as AppRole) || 'shg_admin'

export default function App() {
  const [screen, setScreen] = useState<Screen>('calendar')
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [property, setProperty] = useState<Property | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [loading, setLoading] = useState(true)

  // Allow any component to fire a custom event to navigate
  useEffect(() => {
    const onNav = (e: any) => { if (e?.detail) setScreen(e.detail as Screen) }
    window.addEventListener('tgc:navigate', onNav)
    return () => window.removeEventListener('tgc:navigate', onNav)
  }, [])

  useEffect(() => {
    async function load() {
      const { data: t } = await supabase
        .from('tenants')
        .select('id,name,slug')
        .eq('slug', SLUG)
        .single()
      if (!t) { setLoading(false); return }
      setTenant(t)

      const { data: p } = await supabase
        .from('properties')
        .select('id,tenant_id,name,city,state,timezone')
        .eq('tenant_id', t.id)
        .single()
      if (p) setProperty(p)

      const { count } = await supabase
        .from('rate_recommendations')
        .select('id', { count: 'exact', head: true })
        .eq('tenant_id', t.id)
        .eq('status', 'pending')
      setPendingCount(count ?? 0)
      setLoading(false)
    }
    load()
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center min-h-screen bg-cream">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-navy border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-navy font-medium">Loading Rate Intelligence Center…</p>
      </div>
    </div>
  )

  if (!tenant || !property) return (
    <div className="flex items-center justify-center min-h-screen bg-cream">
      <p className="text-coral font-medium">Could not load tenant data. Check Supabase connection.</p>
    </div>
  )

  const screenProps = { tenant, property, pendingCount, setPendingCount }

  return (
    <PlanFeaturesProvider>
      <Layout screen={screen} setScreen={setScreen} pendingCount={pendingCount}
              propertyName={property.name} propertyId={property.id} appRole={APP_ROLE}>
        {screen === 'calendar'     && <RateCalendar     {...screenProps} />}
        {screen === 'demand'       && <DemandDashboard  {...screenProps} />}
        {screen === 'events'       && <EventsScreen     {...screenProps} />}
        {screen === 'competitive'  && <CompetitiveIntel {...screenProps} />}
        {screen === 'crm'          && <GuestCRM         {...screenProps} />}
        {screen === 'packages'     && <Packages         {...screenProps} />}
        {screen === 'management'   && APP_ROLE === 'shg_admin' && <ManagementConsole {...screenProps} />}
        {screen === 'settings'     && <Settings         {...screenProps} />}
      </Layout>
    </PlanFeaturesProvider>
  )
}

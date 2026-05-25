import { useState } from 'react'
import type { Tenant, Property } from '../lib/types'
import LockedFeature from '../components/LockedFeature'
import PackageDiscovery from '../components/PackageIntelligence/PackageDiscovery'
import PackageCompetitiveTable from '../components/PackageIntelligence/PackageCompetitiveTable'

interface Props { tenant: Tenant; property: Property; pendingCount: number; setPendingCount: (n: number) => void }

type Tab = 'discovery' | 'competitive'

export default function Packages({ }: Props) {
  const [tab, setTab] = useState<Tab>('discovery')

  return (
    <LockedFeature
      featureName="Package & Enhancement Intelligence"
      featureKey="packages_module"
      description="Analyze the 20 most-offered packages across 200+ boutique inns nationally, benchmark against your local competitors, and get AI-recommended pricing for your market. Generates an estimated $13,000+/mo for a typical 14-room boutique inn."
    >
      <div className="flex flex-col h-full overflow-hidden">
        <div className="bg-white border-b border-slate-200 px-5 py-2 flex items-center gap-1">
          {([
            { key: 'discovery'   as Tab, label: 'Package Discovery' },
            { key: 'competitive' as Tab, label: 'Competitive Analysis' },
          ]).map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${
                tab === t.key
                  ? 'bg-navy text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-100'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'discovery'   && <PackageDiscovery />}
        {tab === 'competitive' && <PackageCompetitiveTable />}
      </div>
    </LockedFeature>
  )
}

import { Routes, Route } from 'react-router-dom'
import { PriceProvider } from './context/PriceContext'
import Layout from './components/Layout'
import Home from './screens/Home'
import ScreenPlaceholder from './screens/ScreenPlaceholder'
import { SCREENS } from './routes'

// Built screens (extended as each is implemented). Any path not here renders
// the generic placeholder.
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
}

export default function App() {
  return (
    <PriceProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          {SCREENS.map((s) => {
            const Comp = BUILT[s.path]
            return (
              <Route
                key={s.path}
                path={s.path}
                element={Comp ? <Comp /> : <ScreenPlaceholder name={s.name} />}
              />
            )
          })}
          <Route path="*" element={<ScreenPlaceholder name="Not Found" />} />
        </Route>
      </Routes>
    </PriceProvider>
  )
}

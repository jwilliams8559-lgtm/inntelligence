import { Routes, Route } from 'react-router-dom'
import { PriceProvider } from './context/PriceContext'
import Layout from './components/Layout'
import Home from './screens/Home'
import ScreenPlaceholder from './screens/ScreenPlaceholder'
import { SCREENS } from './routes'

export default function App() {
  return (
    <PriceProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          {SCREENS.map((s) => (
            <Route key={s.path} path={s.path} element={<ScreenPlaceholder name={s.name} />} />
          ))}
          <Route path="*" element={<ScreenPlaceholder name="Not Found" />} />
        </Route>
      </Routes>
    </PriceProvider>
  )
}

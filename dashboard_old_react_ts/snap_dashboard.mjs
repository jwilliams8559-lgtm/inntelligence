import { chromium } from 'playwright'

const URL = 'http://localhost:5174'
const VIEWPORT = { width: 1024, height: 768 }
const OUT = '/tmp/dashboard-shots'

const SCREENS = [
  { tab: 'calendar',    name: '1-rate-calendar' },
  { tab: 'competitive', name: '2-competitive-intel' },
  { tab: 'demand',      name: '3-demand-dashboard' },
  { tab: 'settings',    name: '4-settings' },
]

async function clickNav(page, label) {
  // Each sidebar button contains a label span. Use role + name.
  await page.getByRole('button', { name: label }).first().click()
  await page.waitForTimeout(900)
}

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 })
const page = await ctx.newPage()
page.on('console', m => { if (m.type() === 'error') console.error('PAGE-ERR:', m.text()) })

console.log(`Loading ${URL}`)
await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 })
await page.waitForTimeout(1500)

// Wait for either loaded state or error
try {
  await page.waitForSelector('aside', { timeout: 10000 })
} catch (e) {
  console.log('Sidebar not found; capturing whatever is on screen')
}

const fs = await import('node:fs')
fs.mkdirSync(OUT, { recursive: true })

// Default landing — Rate Calendar with Water Festival banner visible
console.log(`Capturing default landing (Rate Calendar)…`)
await page.screenshot({ path: `${OUT}/0-landing.png`, fullPage: false })

// Click each tab and capture
const labels = {
  calendar:    'Rate Calendar',
  competitive: 'Competitive Intel',
  demand:      'Demand Dashboard',
  settings:    'Settings',
}
for (const s of SCREENS) {
  console.log(`Capturing ${s.name}…`)
  try {
    await clickNav(page, labels[s.tab])
    await page.waitForTimeout(1200)
    await page.screenshot({ path: `${OUT}/${s.name}.png`, fullPage: false })
  } catch (e) {
    console.error(`  failed: ${e.message}`)
  }
}

// Special: open the July 20 drawer on Rate Calendar
console.log('Capturing July 20 drawer open…')
try {
  await clickNav(page, 'Rate Calendar')
  await page.waitForTimeout(800)
  // Click the gold Water Festival banner — it opens the peak rec drawer
  const banner = page.locator('.bg-gold.cursor-pointer').first()
  await banner.click()
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${OUT}/5-jul20-drawer.png`, fullPage: false })
} catch (e) {
  console.error(`  drawer screenshot failed: ${e.message}`)
}

await browser.close()
console.log('Done. Screenshots in', OUT)

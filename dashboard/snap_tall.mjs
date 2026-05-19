import { chromium } from 'playwright'

const browser = await chromium.launch()
// Tall viewport to capture entire page content
const ctx = await browser.newContext({ viewport: { width: 1024, height: 2200 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()

await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 30000 })
await page.waitForTimeout(1500)
await page.waitForSelector('aside', { timeout: 10000 })

const screens = [
  { tab: 'Rate Calendar',    file: 'rate-calendar-tall' },
  { tab: 'Competitive Intel', file: 'competitive-tall' },
  { tab: 'Demand Dashboard', file: 'demand-tall' },
  { tab: 'Settings',         file: 'settings-tall' },
]

for (const s of screens) {
  console.log(`Capturing ${s.file}…`)
  await page.getByRole('button', { name: s.tab }).first().click()
  await page.waitForTimeout(1800)
  await page.screenshot({ path: `/tmp/dashboard-shots/${s.file}.png`, fullPage: false })
}

await browser.close()
console.log('Done')

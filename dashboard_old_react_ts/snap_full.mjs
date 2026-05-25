import { chromium } from 'playwright'

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1024, height: 768 }, deviceScaleFactor: 2 })
const page = await ctx.newPage()

await page.goto('http://localhost:5174', { waitUntil: 'networkidle', timeout: 30000 })
await page.waitForTimeout(1500)
await page.waitForSelector('aside', { timeout: 10000 })

// Click Competitive Intel
await page.getByRole('button', { name: 'Competitive Intel' }).first().click()
await page.waitForTimeout(2000)

// Full-page screenshot
await page.screenshot({ path: '/tmp/dashboard-shots/2b-competitive-intel-full.png', fullPage: true })

// Also scroll to bottom and capture viewport
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
await page.waitForTimeout(500)
await page.screenshot({ path: '/tmp/dashboard-shots/2c-competitive-intel-bottom.png', fullPage: false })

await browser.close()
console.log('Done')

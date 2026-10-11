// Real-browser end-to-end check (headless Microsoft Edge via playwright-core; no browser download).
// Requires the backend on :8000 and `npm run dev` on :5173. Usage: node e2e/run.mjs
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const URL_ = process.env.E2E_URL ?? 'http://localhost:5173'
const API = process.env.E2E_API ?? 'http://127.0.0.1:8000'
const SHOTS = path.join(ROOT, 'data', 'e2e')
const LEAF = path.join(ROOT, 'data', 'plantdoc_samples', 'late_blight', '18c.jpg')
const MULTI = path.join(ROOT, 'data', 'plantdoc_samples', 'late_blight', 'late_blight_tomato_leaf_spore1x1200.jpg')
const BLURRY = path.join(ROOT, 'data', 'e2e', 'blurry_leaf_test.jpg')  // generated: PlantDoc photo + Gaussian blur
mkdirSync(SHOTS, { recursive: true })

const results = []
const check = async (name, fn) => {
  try { const note = await fn(); results.push({ name, ok: true, note: note ?? '' }) }
  catch (e) { results.push({ name, ok: false, note: String(e.message ?? e).split('\n')[0] }) }
}
const assert = (c, msg) => { if (!c) throw new Error(msg) }

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const consoleErrors = []
const watch = (page) => {
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })
  page.on('pageerror', (e) => consoleErrors.push(String(e)))
}

// ---------- desktop, geolocation NOT granted ----------
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } })
await ctx.addInitScript(() => {
  window.__geoCalls = 0
  const real = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation)
  navigator.geolocation.getCurrentPosition = (...a) => { window.__geoCalls++; return real(...a) }
})
const page = await ctx.newPage()
watch(page)
await page.goto(URL_)

await check('loads with live OpenWeatherMap data for the selected farm', async () => {
  await page.getByText('LIVE DATA').first().waitFor({ timeout: 20000 })
  const temp = await page.locator('text=Temperature').first().locator('xpath=..').innerText()
  return temp.replace(/\s+/g, ' ')
})
await check('location is NOT requested on page load', async () => {
  const n = await page.evaluate(() => window.__geoCalls)
  assert(n === 0, `getCurrentPosition called ${n} times on load`)
})
await check('desktop hides the mobile menu button', async () => { assert(!(await page.getByRole('button', { name: 'Open menu' }).isVisible()), 'menu button visible on desktop') })
await check('model status shows ready', async () => { await page.getByText('ready (38 classes)').waitFor({ timeout: 5000 }) })
await page.screenshot({ path: path.join(SHOTS, 'overview-desktop.png'), fullPage: true })

await check('weather outlook: 5-day live forecast table populated', async () => {
  await page.getByRole('button', { name: 'Weather Outlook' }).first().click()
  await page.getByText('5-day forecast (3-hour steps)').waitFor()
  const rows = await page.locator('table tbody tr').count()
  assert(rows >= 30, `only ${rows} forecast rows`)
  return `${rows} rows`
})
await page.screenshot({ path: path.join(SHOTS, 'weather-desktop.png'), fullPage: true })

await check('farm switch updates location shown and weather', async () => {
  const before = await page.locator('h1 + p').first().innerText()
  await page.getByLabel('Farm or location').selectOption('3')
  await page.getByText(/Kolar Tomato Farm, Kolar/).first().waitFor({ timeout: 20000 })
  const after = await page.locator('h1 + p').first().innerText()
  assert(before !== after, 'header did not change')
  return after
})

await check('denied/unanswered permission shows an error and keeps manual selection', async () => {
  await page.getByRole('button', { name: /Use my location/ }).click()
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByText(/permission was denied|took too long|could not be determined/).waitFor({ timeout: 20000 })
  assert(await page.evaluate(() => window.__geoCalls) === 1, 'expected exactly one request')
  assert(await page.getByLabel('Farm or location').inputValue() === '3', 'selection changed')
  return await page.getByText(/permission was denied|took too long|could not be determined/).innerText()
})

await check('real image inference on a PlantDoc tomato late-blight photo', async () => {
  await page.getByLabel('Farm or location').selectOption('1')
  await page.getByRole('button', { name: 'Crop Monitoring' }).first().click()
  await page.getByTestId('file-input').setInputFiles(LEAF)
  await page.getByText('Tomato — Late blight').first().waitFor({ timeout: 30000 })
  return await page.getByText(/Model score \d+%/).first().innerText()
})
await check('crop selector lists all 14 crops from the model', async () => {
  const opts = await page.getByLabel('Crop', { exact: true }).locator('option').allInnerTexts()
  assert(opts.length === 14, `got ${opts.length}`)
  return opts.join(', ')
})
await check('photo guide is visible next to the uploader', async () => {
  await page.getByText('How to take a good photo').waitFor()
  assert(await page.getByRole('img', { name: /whole plant far away/ }).isVisible(), 'guide illustration missing')
})
await check('mark one leaf by dragging on the real photo; only that area is analysed', async () => {
  await page.getByRole('button', { name: /Mark one leaf/ }).click()
  const box = await page.getByAltText('Leaf preview').boundingBox()
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.8, { steps: 8 })
  await page.mouse.up()
  const resp = page.waitForResponse((r) => r.url().includes('/diagnose-image'))
  await page.getByRole('button', { name: 'Check marked leaf' }).click()
  const region = (await (await resp).json()).region  // backend echoes the area it actually analysed
  assert(region && Math.abs(region.x - 0.2) < 0.03 && Math.abs(region.w - 0.6) < 0.03, `region ${JSON.stringify(region)}`)
  await page.getByText(/Checked: the marked leaf only/).waitFor({ timeout: 30000 })
  return `region ${JSON.stringify(region)} · ${await page.getByText(/Model score \d+%/).first().innerText()}`
})
await page.screenshot({ path: path.join(SHOTS, 'monitoring-desktop.png'), fullPage: true })
await check('blurry photo is blocked with a clear message; "analyse anyway" works and is marked unreliable', async () => {
  await page.getByTestId('file-input').setInputFiles(BLURRY)
  await page.getByText('This photo could not be checked reliably').waitFor({ timeout: 30000 })
  const msg = await page.getByText(/The photo is blurry/).innerText()
  await page.getByRole('button', { name: /Analyse anyway/ }).click()
  await page.getByText('Analysed anyway — result not reliable').waitFor({ timeout: 30000 })
  await page.getByText('Uncertain').first().waitFor()
  return msg
})
await check('multi-leaf field photo is accepted and analysed', async () => {
  await page.getByTestId('file-input').setInputFiles(MULTI)
  await page.getByText(/Model score \d+%/).first().waitFor({ timeout: 30000 })
  assert(!(await page.getByText('This photo could not be checked reliably').isVisible()), 'multi-leaf photo rejected')
})
await page.getByTestId('file-input').setInputFiles(LEAF)
await page.getByText('Tomato — Late blight').first().waitFor({ timeout: 30000 })

await check('weather tab: live crop health risk, why-factors and day-by-day risk shown', async () => {
  await page.getByRole('button', { name: 'Weather Outlook' }).first().click()
  await page.getByRole('heading', { name: 'Crop health risk' }).waitFor({ timeout: 20000 })
  const sec = page.locator('section', { has: page.getByRole('heading', { name: 'Crop health risk' }) })
  const level = await sec.locator('span.rounded-full').first().innerText()
  await page.getByText('Why is my crop at risk?').waitFor()
  const days = await page.locator('text=Day-by-day risk').locator('xpath=ancestor::section[1]').locator('li').count()
  assert(days >= 3, `only ${days} days`)
  await page.getByText('What should I do?').waitFor()
  await page.getByText('Current conditions').waitFor()  // existing weather view preserved
  return `${level}, ${days} forecast days, basis: ${(await sec.innerText()).match(/Current weather and forecast|Forecast weather/)?.[0]}`
})
await page.screenshot({ path: path.join(SHOTS, 'weather-risk-desktop.png'), fullPage: true })

await check('disease-conducive demo changes risk and advisory; save assessment goes to history', async () => {
  await page.getByRole('button', { name: 'Demo: disease-conducive' }).click()
  await page.getByRole('button', { name: 'Overview' }).first().click()
  await page.getByText('SIMULATED DEMO DATA').first().waitFor()
  await page.getByText(/inspect today|scout your crop/).first().waitFor({ timeout: 15000 })
  await page.getByRole('button', { name: 'Save assessment' }).click()
  await page.getByText('Assessment saved to history.').waitFor()
  await page.getByRole('button', { name: 'Assessment History' }).first().click()
  await page.getByText(/Tomato – Late blight/).first().waitFor()
  return 'saved + listed'
})
await check('Ask AgriSentry: disclosure + context; not-configured state OR a real Groq answer', async () => {
  await page.getByRole('button', { name: /^Ask AgriSentry/ }).first().click()
  await page.getByRole('heading', { name: 'Ask AgriSentry', level: 1 }).waitFor()
  await page.getByText(/AI-generated answers/).waitFor()
  await page.getByTestId('chat-context').getByText(/Based on:/).waitFor()
  const configured = (await (await fetch('' + API + '/api/health')).json()).chat.configured
  if (!configured) {
    await page.getByText('The chat helper is not set up on this server.').waitFor()
    assert(await page.getByLabel('Your question').isDisabled(), 'input should be disabled')
    return 'not configured (no GROQ_API_KEY): disabled with setup instructions'
  }
  await page.getByRole('button', { name: 'Why is my crop at risk?' }).click()
  await page.getByText('AI answer').waitFor({ timeout: 40000 })
  return 'real Groq answer: ' + (await page.getByText('AI answer').locator('xpath=..').innerText()).replace(/\s+/g, ' ').slice(0, 160)
})
await check('alerts page lists simulated alert and acknowledgement works', async () => {
  await page.getByRole('button', { name: /^Alerts/ }).first().click()
  await page.getByText('simulated').first().waitFor()
  const before = await page.getByRole('button', { name: /Acknowledge/ }).count()
  await page.getByRole('button', { name: /Acknowledge/ }).first().click()
  await page.waitForFunction((n) => document.querySelectorAll('button').length && [...document.querySelectorAll('button')].filter((b) => /Acknowledge/.test(b.textContent)).length === n - 1, before)
  return `${before} -> ${before - 1} open`
})
await ctx.close()

// ---------- granted geolocation (real browser Geolocation API with a fixed position) ----------
const gctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, permissions: ['geolocation'], geolocation: { latitude: 18.5204, longitude: 73.8567 } })
const gpage = await gctx.newPage()
watch(gpage)
await gpage.goto(URL_)
await gpage.getByText('LIVE DATA').first().waitFor({ timeout: 20000 })
await check('granted permission: weather for current location (rounded), not saved as farm', async () => {
  const farmsBefore = await (await fetch('' + API + '/api/v1/farms')).json()
  await gpage.getByRole('button', { name: /Use my location/ }).click()
  await gpage.getByRole('button', { name: 'Continue' }).click()
  await gpage.getByText(/Showing weather for your current location/).waitFor({ timeout: 20000 })
  await gpage.getByText('LIVE DATA').first().waitFor({ timeout: 20000 })
  const banner = await gpage.getByText(/Showing weather for your current location/).innerText()
  const farmsAfter = await (await fetch('' + API + '/api/v1/farms')).json()
  assert(farmsAfter.length === farmsBefore.length, 'a farm was saved without consent')
  return banner
})
await gpage.screenshot({ path: path.join(SHOTS, 'current-location-desktop.png'), fullPage: true })
await gctx.close()

// ---------- mobile layout ----------
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
const mpage = await mctx.newPage()
watch(mpage)
await mpage.goto(URL_)
await mpage.getByText('LIVE DATA').first().waitFor({ timeout: 20000 })
for (const view of ['Overview', 'Weather Outlook', 'Crop Monitoring', 'Alerts', 'Ask AgriSentry', 'Assessment History']) {
  await check(`mobile 390px: ${view} has no horizontal page scroll`, async () => {
    await mpage.getByRole('button', { name: 'Open menu' }).click()
    await mpage.getByRole('button', { name: new RegExp(`^${view}`) }).last().click()
    await mpage.waitForTimeout(400)
    const [sw, iw] = await mpage.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth])
    assert(sw <= iw + 1, `scrollWidth ${sw} > ${iw}`)
  })
}
await mpage.getByRole('button', { name: 'Open menu' }).click()
await mpage.getByRole('button', { name: /^Overview/ }).last().click()
await mpage.screenshot({ path: path.join(SHOTS, 'overview-mobile.png'), fullPage: true })
await mctx.close()
await browser.close()

const relevant = consoleErrors.filter((e) => !/favicon|openweathermap\.org\/img/.test(e))
results.push({ name: 'no browser console errors', ok: relevant.length === 0, note: relevant.slice(0, 3).join(' | ') })
for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.note ? `  — ${r.note}` : ''}`)
const failed = results.filter((r) => !r.ok).length
console.log(`\n${results.length - failed}/${results.length} passed · screenshots in data/e2e/`)
process.exit(failed ? 1 : 0)

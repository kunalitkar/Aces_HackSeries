import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'

vi.mock('recharts', async () => {
  const React = await import('react')
  const Stub = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children)
  return { ResponsiveContainer: Stub, AreaChart: Stub, Area: Stub, ComposedChart: Stub, Bar: Stub, Line: Stub, CartesianGrid: Stub, XAxis: Stub, YAxis: Stub, Tooltip: Stub, Legend: Stub, ReferenceLine: Stub }
})

const farms = [
  { id: 1, name: 'Farm A', location: 'Nashik', lat: 20, lon: 73, crop: 'Tomato' },
  { id: 2, name: 'Farm B', location: 'Kolar', lat: 13, lon: 78, crop: 'Tomato' },
]
// MOCKED payload shaped like /api/v1/risk/forecast — not real OpenWeatherMap data
const live = (farm: (typeof farms)[number], temp: number, name: string) => ({
  farm,
  weather: {
    status: 'live', label: 'Live: OpenWeatherMap', source: 'OpenWeatherMap', fetched_at: '2026-10-11T10:00:00+05:30', observed_at: '2026-10-11T09:55:00+05:30',
    utc_offset_seconds: 19800, location: { name, country: 'IN', lat: farm.lat, lon: farm.lon },
    current: { time: '2026-10-11T09:55:00+05:30', temp_c: temp, feels_like_c: temp + 2, rh: 61, pressure_hpa: 1009, wind_ms: null, rain_mm: 0, icon: '03d', description: 'scattered clouds', condition: 'Clouds' },
    series: [{ time: '2026-10-11T09:55:00+05:30', temp_c: temp, rh: 61, rain_mm: 0, pop: null, wind_ms: null, description: 'scattered clouds' },
             { time: '2026-10-11T12:30:00+05:30', temp_c: temp - 1, rh: 65, rain_mm: 0.8, pop: 0.4, wind_ms: 2, description: 'light rain' }],
  },
  risk: { status: 'unavailable', reason: 'n/a' },
  advisory: { level: 'info', headline: 'Routine monitoring', what_is_happening: 'w', why: 'y', inspect: ['i'], actions: ['a'], reassess: 'r', consult: 'c', severity: 's' },
})

let release: (() => void) | null = null
beforeEach(() => {
  release = null
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (b: unknown) => ({ ok: true, status: 200, json: async () => b })
    if (url.includes('/api/health')) return ok({ status: 'ok', model: { available: true }, weather: { live_configured: true }, database: { mode: 'demo', configured: false, connected: false } })
    if (url.includes('/farms')) return ok(farms)
    if (url.includes('/risk/forecast')) {
      const body = JSON.parse(init!.body as string)
      if (body.farm_id === 2) await new Promise<void>((r) => { release = r })  // hold farm B's response
      return ok(body.farm_id === 1 ? live(farms[0], 27.3, 'Nashik') : live(farms[1], 31.1, 'Kolar'))
    }
    return ok({})
  }))
})

test('weather outlook shows live values, last-updated and local time zone', async () => {
  const user = userEvent.setup()
  render(<App />)
  await user.click((await screen.findAllByRole('button', { name: 'Weather Outlook' }))[0])
  expect(await screen.findByText('LIVE DATA')).toBeInTheDocument()
  expect(screen.getAllByText(/27.3°C/).length).toBeGreaterThan(0)
  expect(screen.getByText('1009 hPa')).toBeInTheDocument()
  expect(screen.getByText('Wind').closest('div')).toHaveTextContent('n/a') // missing wind stays unavailable, not 0
  expect(screen.getByText(/last updated/)).toBeInTheDocument()
  expect(screen.getByText(/UTC\+05:30/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Refresh weather' })).toBeInTheDocument()
})

test('changing farm does not show the previous location weather', async () => {
  const user = userEvent.setup()
  render(<App />)
  await user.click((await screen.findAllByRole('button', { name: 'Weather Outlook' }))[0])
  await screen.findByText(/Nashik, IN/)
  await user.selectOptions(screen.getByLabelText('Farm'), '2')
  expect(await screen.findByText(/Loading weather for Kolar/)).toBeInTheDocument()
  expect(screen.queryByText(/Nashik, IN/)).not.toBeInTheDocument()
  expect(screen.queryByText(/27.3°C/)).not.toBeInTheDocument()
  release!()
  expect(await screen.findByText(/Kolar, IN/)).toBeInTheDocument()
})

test('unavailable weather shows the actual error and hint', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const ok = (b: unknown) => ({ ok: true, status: 200, json: async () => b })
    if (url.includes('/api/health')) return ok({ status: 'ok', model: { available: true }, weather: { live_configured: true }, database: { mode: 'x', configured: false, connected: false } })
    if (url.includes('/farms')) return ok(farms)
    return ok({ farm: farms[0], weather: { status: 'unavailable', label: 'x', error: 'OpenWeatherMap rejected the API key (HTTP 401).', hint: 'new keys can take up to 2 hours to activate' },
      risk: { status: 'unavailable', reason: 'n/a' }, advisory: { level: 'info', headline: 'Weather risk unavailable', what_is_happening: 'w', why: 'y', inspect: [], actions: [], reassess: 'r', consult: 'c', severity: 's' } })
  }))
  const user = userEvent.setup()
  render(<App />)
  await user.click((await screen.findAllByRole('button', { name: 'Weather Outlook' }))[0])
  expect(await screen.findByText(/rejected the API key/)).toBeInTheDocument()
  expect(screen.getByText(/2 hours to activate/)).toBeInTheDocument()
  expect(screen.getByText('WEATHER UNAVAILABLE')).toBeInTheDocument()
})

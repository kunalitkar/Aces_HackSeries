import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'

vi.mock('recharts', async () => {
  const React = await import('react')
  const Stub = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children)
  return { ResponsiveContainer: Stub, AreaChart: Stub, Area: Stub, ComposedChart: Stub, Bar: Stub, Line: Stub, CartesianGrid: Stub, XAxis: Stub, YAxis: Stub, Tooltip: Stub, Legend: Stub, ReferenceLine: Stub }
})

const farm = { id: 1, name: 'Test Farm', location: 'Nashik', lat: 1, lon: 1, crop: 'Tomato' }
const mk = (mode: string) => {
  const hi = mode === 'conducive'
  return {
    farm,
    weather: { status: 'demo', label: hi ? 'Simulated: disease-conducive' : 'Simulated: normal', fetched_at: '2026-10-11T10:00:00+05:30',
      current: { time: '2026-10-11T10:00:00+05:30', temp_c: hi ? 19 : 29, rh: hi ? 93 : 50, rain_mm: 0 },
      series: [{ time: '2026-10-11T10:00:00+05:30', temp_c: 20, rh: 90, rain_mm: 0 }] },
    risk: { status: 'ok', index: hi ? 88 : 4, category: hi ? 'Very High' : 'Low', explanation: 'x',
      factors: [{ key: 'duration', label: 'Favourable-hours run', points: hi ? 50 : 0, max_points: 50, detail: 'd', available: true }], trend: [], peak: null },
    advisory: { level: hi ? 'watch' : 'info', headline: hi ? 'High blight-favourability weather – scout your crop' : 'Routine monitoring',
      what_is_happening: 'w', why: 'y', inspect: ['look'], actions: ['act'], reassess: 'r', consult: 'c', severity: 's' },
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (b: unknown) => ({ ok: true, status: 200, json: async () => b })
    if (url.includes('/api/health')) return ok({ status: 'ok', model: { available: true }, weather: { live_configured: false }, database: { mode: 'demo', configured: false, connected: false } })
    if (url.includes('/farms')) return ok([farm])
    if (url.includes('/risk/forecast')) return ok(mk(JSON.parse(init!.body as string).mode))
    if (url.includes('/risk/history')) return ok({ source: 'synthetic', persistent: false, entries: [{ id: 's', type: 'risk', created_at: '2026-10-10T10:00:00Z', title: 'Example entry', detail: 'Synthetic', synthetic: true, data_mode: 'synthetic' }] })
    return ok({})
  }))
  URL.createObjectURL = vi.fn(() => 'blob:x'); URL.revokeObjectURL = vi.fn()
})

test('navigation reaches every destination', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  for (const [nav, heading] of [['Crop Monitoring', 'Crop monitoring'], ['Weather Outlook', 'Weather outlook'], ['Field Advisories', 'Field advisories'], ['Assessment History', 'Assessment history'], ['Overview', 'Test Farm']] as const) {
    await user.click(screen.getAllByRole('button', { name: nav })[0])
    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  }
})

test('switching to disease-conducive demo updates risk, label and advisory', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  expect(screen.getByLabelText(/Risk favourability index 4 out of 100/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Demo: disease-conducive' }))
  await screen.findByText(/scout your crop/)
  expect(screen.getByLabelText(/index 88 out of 100, Very High/)).toBeInTheDocument()
  expect(screen.getAllByText('SIMULATED DEMO DATA').length).toBeGreaterThan(0)
})

test('rejects unsupported upload type client-side', async () => {
  const user = userEvent.setup({ applyAccept: false })
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.click(screen.getAllByRole('button', { name: 'Crop Monitoring' })[0])
  const input = await screen.findByTestId('file-input')
  await user.upload(input, new File(['hi'], 'a.txt', { type: 'text/plain' }))
  await waitFor(() => expect(screen.getAllByRole('alert')[0]).toHaveTextContent(/Unsupported file type/))
})

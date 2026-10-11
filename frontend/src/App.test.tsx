import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { alertsState, installFetch, lastForecastBodies } from './test/fixtures'

vi.mock('recharts', async () => (await import('./test/fixtures')).rechartsStub())

beforeEach(() => { alertsState.alerts = []; installFetch() })

test('navigation reaches every destination', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  for (const [nav, heading] of [['Crop Monitoring', 'Crop monitoring'], ['Weather Outlook', 'Weather outlook'], ['Field Advisories', 'Field advisories'],
    ['Alerts', 'Alerts'], ['Assessment History', 'Assessment history'], ['Overview', 'Farm A']] as const) {
    await user.click(screen.getAllByRole('button', { name: new RegExp(`^${nav}`) })[0])
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
  await user.upload(await screen.findByTestId('file-input'), new File(['hi'], 'a.txt', { type: 'text/plain' }))
  await waitFor(() => expect(screen.getAllByRole('alert')[0]).toHaveTextContent(/Unsupported file type/))
})

test('crop selector comes from the model catalogue and re-runs the photo for the new crop', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.click(screen.getAllByRole('button', { name: 'Crop Monitoring' })[0])
  const select = await screen.findByLabelText('Crop')
  expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['Tomato', 'Grape', 'Soybean'])
  expect(within(screen.getByLabelText('Supported classes')).getAllByRole('listitem')).toHaveLength(3)
  await user.upload(screen.getByTestId('file-input'), new File(['x'], 'leaf.jpg', { type: 'image/jpeg' }))
  expect(await screen.findByText('Tomato — healthy')).toBeInTheDocument()
  await user.selectOptions(select, 'Grape')
  expect(await screen.findByText('Grape — healthy')).toBeInTheDocument()
  await waitFor(() => expect(lastForecastBodies.at(-1)).toMatchObject({ crop: 'Grape' }))
  expect(await screen.findByText(/Weather-based forecasting: not available for this crop/)).toBeInTheDocument()
  await user.selectOptions(select, 'Soybean')
  expect(await screen.findByText(/Only one class exists for Soybean/)).toBeInTheDocument()
})

test('changing farm clears the previous photo and uses the new farm crop', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.click(screen.getAllByRole('button', { name: 'Crop Monitoring' })[0])
  await user.upload(await screen.findByTestId('file-input'), new File(['x'], 'leaf.jpg', { type: 'image/jpeg' }))
  await screen.findByText('Tomato — healthy')
  await user.selectOptions(screen.getByLabelText('Farm or location'), '2')
  await waitFor(() => expect(screen.queryByAltText('Leaf preview')).not.toBeInTheDocument())
  expect(screen.getByLabelText('Crop')).toHaveValue('Grape')
  await waitFor(() => expect(lastForecastBodies.at(-1)).toMatchObject({ farm_id: 2, crop: 'Grape', image: null }))
})

test('alerts can be acknowledged and simulated alerts are labelled', async () => {
  alertsState.alerts = [
    { id: 1, farm_id: 1, created_at: '2026-10-11T10:00:00Z', level: 'alert', message: 'Late-blight favourability is Very High now – Farm A', kind: 'weather', explanation: 'e', location_label: 'Farm A', category: 'Very High', simulated: true, acknowledged: false, acknowledged_at: null },
    { id: 2, farm_id: 1, created_at: '2026-10-11T09:00:00Z', level: 'warning', message: 'Real alert', kind: 'weather', explanation: 'e', location_label: 'Farm A', category: 'High', simulated: false, acknowledged: false, acknowledged_at: null },
  ]
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  expect(within(screen.getByRole('button', { name: 'Notifications' })).getByText('2')).toBeInTheDocument()
  await user.click(screen.getAllByRole('button', { name: /^Alerts/ })[0])
  expect(await screen.findByText('simulated')).toBeInTheDocument()
  expect(screen.getByText('live weather')).toBeInTheDocument()
  await user.click(screen.getAllByRole('button', { name: /Acknowledge/ })[0])
  await waitFor(() => expect(screen.queryByText(/Very High now/)).not.toBeInTheDocument())  // hidden from "Open"
  expect(within(screen.getByRole('button', { name: 'Notifications' })).getByText('1')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'All' }))
  expect(await screen.findByText(/Very High now/)).toBeInTheDocument()
})

test('report builder includes limitations and simulated label', async () => {
  const { reportHtml } = await import('./report')
  const { forecastFor } = await import('./test/fixtures')
  const f = forecastFor({ farm_id: 1, mode: 'conducive' }, {}) as never
  const html = reportHtml({ image: { result: null } } as never, f)
  expect(html).toContain('88/100')
  expect(html).toContain('SIMULATED weather')
  expect(html).toContain('Visual severity is not estimated')
  expect(html).not.toMatch(/<script/i)
})

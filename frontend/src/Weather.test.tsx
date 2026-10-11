import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { alertsState, installFetch, release } from './test/fixtures'

vi.mock('recharts', async () => (await import('./test/fixtures')).rechartsStub())
beforeEach(() => { alertsState.alerts = [] })

const openWeather = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click((await screen.findAllByRole('button', { name: 'Weather Outlook' }))[0])

test('weather outlook shows live values, last-updated, local time zone and the rules', async () => {
  installFetch({ live: true })
  const user = userEvent.setup()
  render(<App />)
  await openWeather(user)
  expect(await screen.findByText('LIVE DATA')).toBeInTheDocument()
  expect(screen.getAllByText(/27.3°C/).length).toBeGreaterThan(0)
  expect(screen.getByText('1009 hPa')).toBeInTheDocument()
  expect(screen.getByText('Wind').closest('div')).toHaveTextContent('n/a') // missing wind stays unavailable, not 0
  expect(screen.getByText(/last updated/)).toBeInTheDocument()
  expect(screen.getByText(/UTC\+05:30/)).toBeInTheDocument()
  expect(screen.getByText('How this score is calculated')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /favourable hours in the next 48 hours/ })).toBeInTheDocument()
})

test('changing farm does not show the previous location weather', async () => {
  installFetch({ live: true, holdFarm2: true })
  const user = userEvent.setup()
  render(<App />)
  await openWeather(user)
  await screen.findByText(/Farm A, Nashik/)
  await user.selectOptions(screen.getByLabelText('Farm or location'), '2')
  expect(await screen.findByText(/Loading weather/)).toBeInTheDocument()
  expect(screen.queryByText(/27.3°C/)).not.toBeInTheDocument()
  release!()
  expect(await screen.findByText(/Farm B, Kolar/)).toBeInTheDocument()
  expect(screen.getAllByText(/31.1°C/).length).toBeGreaterThan(0)
})

test('unavailable weather shows the actual error, hint and a retry', async () => {
  installFetch({ live: true, weatherError: true })
  const user = userEvent.setup()
  render(<App />)
  await openWeather(user)
  expect(await screen.findByText(/rejected the API key/)).toBeInTheDocument()
  expect(screen.getByText(/2 hours to activate/)).toBeInTheDocument()
  expect(screen.getByText('WEATHER UNAVAILABLE')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Retry/ })).toBeInTheDocument()
})

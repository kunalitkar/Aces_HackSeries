import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { alertsState, installFetch, lastForecastBodies } from './test/fixtures'

vi.mock('recharts', async () => (await import('./test/fixtures')).rechartsStub())

let getCurrentPosition: ReturnType<typeof vi.fn>
const setGeo = (impl: (ok: PositionCallback, err: PositionErrorCallback) => void) => {
  getCurrentPosition = vi.fn((ok, err) => impl(ok, err))
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: { getCurrentPosition } })
}
beforeEach(() => { alertsState.alerts = []; installFetch() })

const consent = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /Use my location/ }))
  expect(screen.getByRole('dialog', { name: 'Use your current location?' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Continue' }))
}

test('never asks for location on load; asks only after click + consent; granted updates weather', async () => {
  setGeo((ok) => ok({ coords: { latitude: 18.520431, longitude: 73.856744 } } as GeolocationPosition))
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  expect(getCurrentPosition).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: /Use my location/ }))
  await user.click(screen.getByRole('button', { name: 'Not now' }))
  expect(getCurrentPosition).not.toHaveBeenCalled()  // declining the explanation does not prompt
  await consent(user)
  expect(getCurrentPosition).toHaveBeenCalledTimes(1)
  await waitFor(() => expect(lastForecastBodies.at(-1)).toMatchObject({ location: { lat: 18.52, lon: 73.86 } }))  // rounded ~1 km
  expect(await screen.findByText(/Showing weather for your current location — Near Pune/)).toBeInTheDocument()
  expect(screen.getByLabelText('Farm or location')).toHaveDisplayValue('Current location (approx.)')
  // back to saved farms
  await user.click(screen.getByRole('button', { name: 'Back to saved farms' }))
  await waitFor(() => expect(lastForecastBodies.at(-1)).toMatchObject({ farm_id: 1 }))
})

test('denied permission explains, keeps manual selection and offers retry', async () => {
  setGeo((_ok, err) => err({ code: 1, message: 'denied' } as GeolocationPositionError))
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await consent(user)
  expect(await screen.findByText(/Location permission was denied/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  expect(screen.getByLabelText('Farm or location')).toHaveValue('1')  // still on the saved farm
  await user.selectOptions(screen.getByLabelText('Farm or location'), '2')
  await waitFor(() => expect(lastForecastBodies.at(-1)).toMatchObject({ farm_id: 2 }))
})

test('timeout and unavailable position are reported', async () => {
  setGeo((_ok, err) => err({ code: 3, message: 'timeout' } as GeolocationPositionError))
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await consent(user)
  expect(await screen.findByText(/took too long/)).toBeInTheDocument()
  setGeo((_ok, err) => err({ code: 2, message: 'unavailable' } as GeolocationPositionError))
  await user.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText(/could not be determined/)).toBeInTheDocument()
})

test('unsupported browser is handled', async () => {
  // @ts-expect-error removing the API to simulate an old browser
  delete (navigator as Navigator & { geolocation?: unknown }).geolocation
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined })
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await consent(user)
  expect(await screen.findByText(/does not support location access/)).toBeInTheDocument()
})

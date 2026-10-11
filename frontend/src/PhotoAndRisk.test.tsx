import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { alertsState, installFetch, lastDiagnoseForms } from './test/fixtures'

vi.mock('recharts', async () => (await import('./test/fixtures')).rechartsStub())

// jsdom has no PointerEvent / pointer capture; provide minimal versions so the leaf picker can be exercised.
class FakePointerEvent extends MouseEvent { pointerId = 1 }
beforeAll(() => {
  Object.assign(window, { PointerEvent: FakePointerEvent })
  Element.prototype.setPointerCapture = () => undefined
})
beforeEach(() => { alertsState.alerts = [] })

const leaf = () => new File(['x'], 'leaf.jpg', { type: 'image/jpeg' })
const openMonitoring = async (user: ReturnType<typeof userEvent.setup>) => {
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.click(screen.getAllByRole('button', { name: 'Crop Monitoring' })[0])
}

test('photo guide is shown next to the uploader with good and less suitable examples', async () => {
  installFetch()
  const user = userEvent.setup()
  await openMonitoring(user)
  expect(screen.getByText('How to take a good photo')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /close-up of a leaf with clear spots/ })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /whole plant far away/ })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /blurry leaf/ })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: /very dark photo/ })).toBeInTheDocument()
  expect(screen.getByText(/not photos of real diagnosed plants/)).toBeInTheDocument()
})

test('failed quality check: actionable message, retake, and analyse-anyway marks result unreliable', async () => {
  installFetch({ qualityFail: true })
  const user = userEvent.setup()
  await openMonitoring(user)
  await user.upload(screen.getByTestId('file-input'), leaf())
  expect(await screen.findByText('This photo could not be checked reliably')).toBeInTheDocument()
  expect(screen.getByText(/The photo is blurry/)).toBeInTheDocument()
  expect(screen.queryByText('Tomato — healthy')).not.toBeInTheDocument()  // no prediction shown
  expect(screen.getByRole('button', { name: /Take or choose another photo/ })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Analyse anyway/ }))
  expect(await screen.findByText('Tomato — healthy')).toBeInTheDocument()
  expect(lastDiagnoseForms.at(-1)!.get('force')).toBe('true')
  expect(screen.getByText('Analysed anyway — result not reliable')).toBeInTheDocument()
  expect(screen.getByText('Uncertain')).toBeInTheDocument()
})

test('farmer can mark one leaf; only that area is analysed and whole photo can be restored', async () => {
  installFetch()
  const user = userEvent.setup()
  await openMonitoring(user)
  await user.upload(screen.getByTestId('file-input'), leaf())
  await screen.findByText('Tomato — healthy')
  expect(screen.getByText('Checked: the whole photo.')).toBeInTheDocument()
  const img = screen.getByAltText('Leaf preview')
  img.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100, x: 0, y: 0, toJSON: () => ({}) })
  await user.click(screen.getByRole('button', { name: /Mark one leaf/ }))
  const picker = screen.getByTestId('leaf-picker')
  fireEvent.pointerDown(picker, { clientX: 20, clientY: 10 })
  fireEvent.pointerMove(picker, { clientX: 120, clientY: 60 })
  fireEvent.pointerUp(picker)
  await user.click(screen.getByRole('button', { name: 'Check marked leaf' }))
  await waitFor(() => expect(lastDiagnoseForms.at(-1)!.get('region')).toBe('0.1000,0.1000,0.5000,0.5000'))
  expect(await screen.findByText(/Checked: the marked leaf only/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Check whole photo' }))
  await waitFor(() => expect(lastDiagnoseForms.at(-1)!.get('region')).toBeNull())
})

test('weather tab: crop health risk, why factors, day-by-day and what-to-do come from the backend', async () => {
  installFetch()
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.click(screen.getByRole('button', { name: 'Demo: disease-conducive' }))
  await user.click(screen.getAllByRole('button', { name: 'Weather Outlook' })[0])
  const chr = (await screen.findByRole('heading', { name: 'Crop health risk' })).closest('section')!
  expect(within(chr).getByText('VERY HIGH')).toBeInTheDocument()
  expect(within(chr).getByRole('meter', { name: 'Weather risk score' })).toHaveAttribute('aria-valuenow', '88')
  expect(within(chr).getByText(/strongly favourable/)).toBeInTheDocument()
  expect(within(chr).getByText(/not the chance that your crop is infected/)).toBeInTheDocument()
  expect(within(chr).getByText(/Simulated demo weather/)).toBeInTheDocument()
  expect(screen.getByText('Why is my crop at risk?')).toBeInTheDocument()
  expect(screen.getByText('12 h')).toBeInTheDocument()
  expect(screen.getByText('Data unavailable', { selector: 'p.tabular-nums' })).toBeInTheDocument()  // missing rain, not 0
  expect(screen.getByText('Day-by-day risk')).toBeInTheDocument()
  expect(screen.getByText('MODERATE')).toBeInTheDocument()  // second day differs from the first
  expect(screen.getByText(/partial day/)).toBeInTheDocument()
  expect(screen.getByText('What should I do?')).toBeInTheDocument()
})

test('unsupported crop: forecast stays, no misleading score', async () => {
  installFetch()
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.selectOptions(screen.getByLabelText('Farm or location'), '2')  // Grape farm
  await user.click(screen.getAllByRole('button', { name: 'Weather Outlook' })[0])
  expect(await screen.findByText(/A validated weather-based risk assessment is not available for Grape/)).toBeInTheDocument()
  expect(screen.queryByRole('meter')).not.toBeInTheDocument()
  expect(screen.queryByText('Day-by-day risk')).not.toBeInTheDocument()
  expect(screen.getByText('Current conditions')).toBeInTheDocument()
})

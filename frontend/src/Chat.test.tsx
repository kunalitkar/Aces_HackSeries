import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from './App'
import { alertsState, installFetch, lastChatBodies } from './test/fixtures'

vi.mock('recharts', async () => (await import('./test/fixtures')).rechartsStub())
beforeEach(() => { alertsState.alerts = [] })

const openChat = async (user: ReturnType<typeof userEvent.setup>) => {
  render(<App />)
  await screen.findByText('Routine monitoring')
  await user.click(screen.getAllByRole('button', { name: /^Ask AgriSentry/ })[0])
  await screen.findByRole('heading', { level: 1, name: 'Ask AgriSentry' })
}

test('disclosure is shown, context chip reflects the selection and a question gets an AI-labelled answer', async () => {
  installFetch()
  const user = userEvent.setup()
  await openChat(user)
  expect(screen.getByText(/AI-generated answers/)).toBeInTheDocument()
  expect(screen.getByText(/never recommend chemicals, doses or spray times/)).toBeInTheDocument()
  expect(screen.getByText(/no exact location, no photo/)).toBeInTheDocument()
  await waitFor(() => expect(screen.getByTestId('chat-context')).toHaveTextContent('Farm A, Nashik'))
  expect(screen.getByTestId('chat-context')).toHaveTextContent(/Tomato · weather risk Low \(4\/100\) · simulated weather · no photo analysed/)
  await user.type(screen.getByLabelText('Your question'), 'किसान प्रश्न: मेरी फसल सुरक्षित है?')
  await user.click(screen.getByRole('button', { name: /Ask$/ }))
  expect(await screen.findByText('Answer 1: check lower leaves.')).toBeInTheDocument()
  expect(screen.getByText('AI answer')).toBeInTheDocument()
  expect(lastChatBodies[0]).toMatchObject({ farm_id: 1, crop: 'Tomato', mode: 'normal', image: null })
  expect(lastChatBodies[0].messages).toEqual([{ role: 'user', content: 'किसान प्रश्न: मेरी फसल सुरक्षित है?' }])
  expect(JSON.stringify(lastChatBodies[0])).not.toMatch(/lat|lon/)  // saved farm: only the id is sent
})

test('conversation history is sent, suggestions work, and a different farm starts a fresh conversation', async () => {
  installFetch()
  const user = userEvent.setup()
  await openChat(user)
  await user.click(screen.getByRole('button', { name: 'Why is my crop at risk?' }))
  expect(await screen.findByText('Answer 1: check lower leaves.')).toBeInTheDocument()
  await user.type(screen.getByLabelText('Your question'), 'And tomorrow?')
  await user.click(screen.getByRole('button', { name: /Ask$/ }))
  expect(await screen.findByText('Answer 3: check lower leaves.')).toBeInTheDocument()  // 3 messages sent = history included
  await user.selectOptions(screen.getByLabelText('Farm or location'), '2')
  await waitFor(() => expect(screen.queryByText('Answer 3: check lower leaves.')).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: 'Why is my crop at risk?' })).toBeInTheDocument()
})

test('not configured: explains exactly what to do and disables asking', async () => {
  installFetch({ chat: 'off' })
  const user = userEvent.setup()
  await openChat(user)
  expect(await screen.findByText('The chat helper is not set up on this server.')).toBeInTheDocument()
  expect(screen.getByText(/GROQ_API_KEY=your key/)).toBeInTheDocument()
  expect(screen.getByLabelText('Your question')).toBeDisabled()
  expect(screen.getByRole('button', { name: /Ask$/ })).toBeDisabled()
})

test('service errors are shown with their hint and the user can try again', async () => {
  installFetch({ chat: 'error' })
  const user = userEvent.setup()
  await openChat(user)
  await user.type(screen.getByLabelText('Your question'), 'hello')
  await user.click(screen.getByRole('button', { name: /Ask$/ }))
  expect(await screen.findByText(/Groq rate limit reached/)).toBeInTheDocument()
  expect(screen.getByText('Wait a minute and ask again.')).toBeInTheDocument()
  expect(screen.getByLabelText('Your question')).not.toBeDisabled()
})

test('a guarded reply is labelled', async () => {
  installFetch({ chat: 'guarded' })
  const user = userEvent.setup()
  await openChat(user)
  await user.type(screen.getByLabelText('Your question'), 'which spray?')
  await user.click(screen.getByRole('button', { name: /Ask$/ }))
  expect(await screen.findByText(/can't recommend chemicals/)).toBeInTheDocument()
  expect(screen.getByText(/chemical or dose suggestion was removed/)).toBeInTheDocument()
})

test('clear conversation works', async () => {
  installFetch()
  const user = userEvent.setup()
  await openChat(user)
  await user.click(screen.getByRole('button', { name: 'What does the weather score mean?' }))
  await screen.findByText('Answer 1: check lower leaves.')
  await user.click(screen.getByRole('button', { name: 'Clear conversation' }))
  expect(screen.queryByText('Answer 1: check lower leaves.')).not.toBeInTheDocument()
})

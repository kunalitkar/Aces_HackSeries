import { useEffect, useRef, useState } from 'react'
import { Bot, Send, ShieldAlert, Trash2 } from 'lucide-react'
import { api, type ChatMessage } from './api'
import type { Agri } from './useAgri'
import { Card, Notice } from './ui'

const SUGGESTIONS = ['Why is my crop at risk?', 'What should I check in my field today?', 'What does the weather score mean?', 'What does my photo result mean?']
type Turn = ChatMessage & { error?: boolean; blocked?: boolean }

export function AskAgriSentry({ a }: { a: Agri }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [unavailable, setUnavailable] = useState<{ error: string; hint?: string | null } | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const configured = a.health?.chat?.configured
  const f = a.forecast
  const contextKey = JSON.stringify([a.selection, a.crop, a.mode])

  // A different farm/location/crop/data source means different facts: start a fresh conversation.
  useEffect(() => { setTurns([]); setUnavailable(null) }, [contextKey])
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'nearest' }) }, [turns, busy])

  const send = async (q: string) => {
    const question = q.trim()
    if (!question || busy || !a.selection) return
    const next: Turn[] = [...turns, { role: 'user', content: question }]
    setTurns(next); setText(''); setBusy(true); setUnavailable(null)
    try {
      const history = next.filter((t) => !t.error).map(({ role, content }) => ({ role, content }))
      const r = await api.chat(history, a.selection, a.crop, a.mode, a.image.result)
      if (r.status === 'ok') setTurns([...next, { role: 'assistant', content: r.reply!, blocked: r.guard_blocked }])
      else setUnavailable({ error: r.error ?? 'The chat helper is unavailable.', hint: r.hint })
    } catch (e) {
      setUnavailable({ error: (e as Error).message })
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-3xl text-forest">Ask AgriSentry</h1>
        <p className="text-muted">Ask simple questions about your crop's weather risk and leaf photo. You can write in English, Hindi or Marathi.</p>
      </div>
      <Notice tone="info">
        <p className="flex items-start gap-2"><ShieldAlert size={16} className="mt-0.5 shrink-0" />
          <span><strong>AI-generated answers.</strong> They only explain AgriSentry's own results for the selection below and can be wrong. They never recommend chemicals, doses or spray times — ask your local KVK or agriculture officer. Your question and a summary of these results (no exact location, no photo) are sent to Groq to write the answer.</span></p>
      </Notice>
      <Card>
        <p className="mb-3 text-xs text-muted" data-testid="chat-context">
          Based on: <strong>{f?.place.kind === 'farm' ? f.place.label : f ? 'your chosen location' : 'loading…'}</strong> · {a.crop}
          {f?.risk.status === 'ok' ? ` · weather risk ${f.risk.category} (${Math.round(f.risk.index!)}/100)` : ' · no weather risk for this crop/data'}
          {a.mode !== 'live' ? ' · simulated weather' : ''}
          {a.image.result?.status === 'ok' ? ` · photo: ${a.image.result.condition}` : ' · no photo analysed'}
        </p>
        {configured === false && (
          <Notice tone="warn">
            <p className="font-semibold">The chat helper is not set up on this server.</p>
            <p className="mt-1">Add <code>GROQ_API_KEY=your key</code> to <code>backend/.env</code> and restart the backend. The rest of AgriSentry works without it.</p>
          </Notice>
        )}
        <div className="mt-3 max-h-[28rem] min-h-40 space-y-3 overflow-y-auto" role="log" aria-live="polite" aria-label="Conversation">
          {turns.length === 0 && configured !== false && (
            <div>
              <p className="text-sm text-muted">Try a question:</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => <button key={s} className="btn btn-ghost" onClick={() => send(s)} disabled={busy || !f}>{s}</button>)}
              </div>
            </div>
          )}
          {turns.map((t, i) => (
            <div key={i} className={`flex ${t.role === 'user' ? 'justify-end' : ''}`}>
              <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${t.role === 'user' ? 'bg-forest text-white' : 'bg-sage-50'}`}>
                {t.role === 'assistant' && <span className="mb-1 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-muted"><Bot size={12} /> AI answer</span>}
                {t.content}
                {t.blocked && <span className="mt-1 block text-[11px] text-muted">(A chemical or dose suggestion was removed.)</span>}
              </div>
            </div>
          ))}
          {busy && <p className="text-sm text-muted">Thinking…</p>}
          <div ref={end} />
        </div>
        {unavailable && (
          <div className="mt-3"><Notice tone="error"><p>{unavailable.error}</p>{unavailable.hint && <p className="mt-1">{unavailable.hint}</p>}</Notice></div>
        )}
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text) }}>
          <input aria-label="Your question" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} disabled={configured === false}
            placeholder="Type your question…" className="min-w-0 flex-1 rounded-lg border border-line bg-paper p-2 text-sm" />
          <button className="btn btn-primary" disabled={busy || !text.trim() || configured === false || !f}><Send size={15} /> Ask</button>
          {turns.length > 0 && <button type="button" className="btn btn-ghost" aria-label="Clear conversation" onClick={() => { setTurns([]); setUnavailable(null) }}><Trash2 size={15} /></button>}
        </form>
      </Card>
    </div>
  )
}

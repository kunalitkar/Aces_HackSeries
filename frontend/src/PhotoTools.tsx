import { useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from 'react'
import { Camera, CheckCircle2, Crop, Maximize, RotateCcw, Sun, XCircle, ZoomIn } from 'lucide-react'
import type { ImageResult, Region } from './api'
import { Notice } from './ui'

/* ---------- Photo guide (simple illustrations, not real diagnosed cases) ---------- */
const Leaf = ({ cx, cy, s = 1, spots = true }: { cx: number; cy: number; s?: number; spots?: boolean }) => (
  <g transform={`translate(${cx} ${cy}) scale(${s})`}>
    <path d="M0 -38 C 26 -30 30 6 0 38 C -30 6 -26 -30 0 -38 Z" fill="#5f9a5b" stroke="#2f5f35" strokeWidth="2" />
    <path d="M0 -34 L0 34" stroke="#2f5f35" strokeWidth="1.5" />
    {spots && <><circle cx="-9" cy="-6" r="5" fill="#5b3a1e" /><circle cx="10" cy="8" r="6" fill="#5b3a1e" /><circle cx="-6" cy="16" r="3.5" fill="#5b3a1e" /></>}
  </g>
)
const Frame = ({ children, label }: { children: ReactNode; label: string }) => (
  <svg viewBox="0 0 120 90" role="img" aria-label={label} className="h-auto w-full rounded-lg border border-line bg-sage-50">{children}</svg>
)

const GOOD = [
  { label: 'Close-up of one affected leaf', icon: <ZoomIn size={14} />, art: <Frame label="Illustration: close-up of a leaf with clear spots"><Leaf cx={60} cy={45} s={1.05} /></Frame> },
  { label: 'Several leaves, spots clearly visible', icon: <CheckCircle2 size={14} />, art: <Frame label="Illustration: a few leaves filling the photo, spots visible"><Leaf cx={38} cy={45} s={0.8} /><Leaf cx={82} cy={47} s={0.8} /></Frame> },
]
const BAD = [
  { label: 'Whole plant from far away', icon: <Maximize size={14} />, art: (
    <Frame label="Illustration: a whole plant far away, leaves too small">
      <path d="M60 82 L60 30" stroke="#2f5f35" strokeWidth="2" />
      {[[48, 34], [72, 40], [50, 52], [70, 60], [56, 22], [64, 70]].map(([x, y], i) => <Leaf key={i} cx={x} cy={y} s={0.18} spots={false} />)}
    </Frame>) },
  { label: 'Blurry photo', icon: <Camera size={14} />, art: (
    <Frame label="Illustration: blurry leaf"><defs><filter id="pg-blur"><feGaussianBlur stdDeviation="4" /></filter></defs><g filter="url(#pg-blur)"><Leaf cx={60} cy={45} /></g></Frame>) },
  { label: 'Too dark', icon: <Sun size={14} />, art: (
    <Frame label="Illustration: leaf in a very dark photo"><Leaf cx={60} cy={45} /><rect width="120" height="90" fill="#000" opacity="0.72" /></Frame>) },
]

export function PhotoGuide() {
  return (
    <details className="rounded-xl border border-line bg-paper p-3" open>
      <summary className="cursor-pointer text-sm font-semibold text-forest">How to take a good photo</summary>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        <li>Go close to an <strong>affected leaf</strong> so the spots and colour changes are easy to see.</li>
        <li>Hold the phone steady so the leaf is <strong>sharp, not blurry</strong>.</li>
        <li>Use <strong>daylight</strong>; avoid very dark shade and strong glare.</li>
        <li>Several leaves in one photo are fine if the affected ones are clearly visible. You can then mark one leaf to check.</li>
        <li>A whole-plant photo gives context, but the leaves are usually too small to check. Take a separate close-up too.</li>
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {GOOD.map((g) => (
          <figure key={g.label} className="text-xs">
            {g.art}<figcaption className="mt-1 flex items-start gap-1 text-forest"><CheckCircle2 size={14} className="mt-px shrink-0" />{g.label}</figcaption>
          </figure>
        ))}
        {BAD.map((b) => (
          <figure key={b.label} className="text-xs">
            {b.art}<figcaption className="mt-1 flex items-start gap-1 text-alert"><XCircle size={14} className="mt-px shrink-0" />{b.label}</figcaption>
          </figure>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted">Drawings for guidance only — not photos of real diagnosed plants.</p>
    </details>
  )
}

/* ---------- Quality feedback ---------- */
export function QualityPanel({ result, onRetake, onAnyway }: { result: ImageResult | null; onRetake: () => void; onAnyway: () => void }) {
  const q = result?.quality
  if (!q || q.status === 'ok') return null
  if (result!.status === 'quality_failed') {
    return (
      <Notice tone="error">
        <p className="font-semibold">This photo could not be checked reliably</p>
        <ul className="mt-1 list-disc pl-5">{q.checks.map((c) => <li key={c.key}>{c.message}</li>)}</ul>
        <div className="mt-2 flex flex-wrap gap-2">
          <button className="btn btn-primary" onClick={onRetake}><RotateCcw size={14} /> Take or choose another photo</button>
          <button className="btn btn-ghost" onClick={onAnyway}>Analyse anyway (less reliable)</button>
        </div>
      </Notice>
    )
  }
  return (
    <Notice tone="warn">
      <p className="font-semibold">{result!.quality_override ? 'Analysed anyway — result not reliable' : 'Photo quality could be better'}</p>
      <ul className="mt-1 list-disc pl-5">{q.checks.map((c) => <li key={c.key}>{c.message}</li>)}</ul>
      <button className="btn btn-ghost mt-2" onClick={onRetake}><RotateCcw size={14} /> Retake photo</button>
    </Notice>
  )
}

/* ---------- Preview with optional leaf selection (the farmer marks the leaf; nothing is auto-detected) ---------- */
const clamp = (v: number) => Math.min(1, Math.max(0, v))

export function LeafPicker({ src, analysed, busy, onAnalyse }: {
  src: string; analysed: Region | null; busy: boolean; onAnalyse: (r: Region | null) => void
}) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [selecting, setSelecting] = useState(false)
  const [box, setBox] = useState<Region | null>(null)
  const start = useRef<{ x: number; y: number } | null>(null)

  const point = (e: RPointerEvent) => {
    const r = imgRef.current!.getBoundingClientRect()
    return { x: clamp((e.clientX - r.left) / r.width), y: clamp((e.clientY - r.top) / r.height) }
  }
  const down = (e: RPointerEvent) => {
    if (!selecting) return
    e.currentTarget.setPointerCapture(e.pointerId)
    start.current = point(e)
    setBox({ ...start.current, w: 0, h: 0 })
  }
  const move = (e: RPointerEvent) => {
    if (!selecting || !start.current) return
    const p = point(e), s = start.current
    setBox({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) })
  }
  const up = () => { start.current = null }
  const shown = selecting ? box : analysed
  const valid = !!box && box.w > 0.05 && box.h > 0.05

  return (
    <div>
      <div className="flex justify-center rounded-xl bg-sage-50 p-1">
        <div className={`relative inline-block touch-none select-none ${selecting ? 'cursor-crosshair' : ''}`}
          onPointerDown={down} onPointerMove={move} onPointerUp={up} data-testid="leaf-picker">
          <img ref={imgRef} src={src} alt="Leaf preview" draggable={false} className="block max-h-80 max-w-full rounded-lg" />
          {shown && shown.w > 0 && (
            <div className="pointer-events-none absolute border-2 border-amber-warn bg-amber-warn/10"
              style={{ left: `${shown.x * 100}%`, top: `${shown.y * 100}%`, width: `${shown.w * 100}%`, height: `${shown.h * 100}%` }} />
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted" aria-live="polite">
        {selecting ? 'Drag a box around the one leaf you want checked.'
          : analysed ? 'Checked: the marked leaf only. Your original photo is kept unchanged.' : 'Checked: the whole photo.'}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {!selecting ? (
          <button className="btn btn-ghost" onClick={() => { setSelecting(true); setBox(null) }} disabled={busy}><Crop size={15} /> Mark one leaf</button>
        ) : (<>
          <button className="btn btn-primary" disabled={!valid || busy} onClick={() => { setSelecting(false); onAnalyse(box) }}>Check marked leaf</button>
          <button className="btn btn-ghost" onClick={() => { setSelecting(false); setBox(null) }}>Cancel</button>
        </>)}
        {analysed && !selecting && <button className="btn btn-ghost" onClick={() => onAnalyse(null)} disabled={busy}>Check whole photo</button>}
      </div>
    </div>
  )
}

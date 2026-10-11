import { useState, type ReactNode } from 'react'
import { LocateFixed, MapPin, Save, Search, Settings, Trash2, X } from 'lucide-react'
import { api, type GeoResult } from './api'
import type { Agri } from './useAgri'
import { Notice } from './ui'

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="card relative max-h-[90vh] w-full max-w-lg overflow-auto p-5">
        <div className="mb-3 flex items-center justify-between"><h2 className="font-serif text-xl text-forest">{title}</h2>
          <button aria-label="Close" className="p-1" onClick={onClose}><X size={18} /></button></div>
        {children}
      </div>
    </div>
  )
}

function CropSelect({ a, value, onChange }: { a: Agri; value: string; onChange: (c: string) => void }) {
  const crops = a.catalog?.crops.map((c) => c.crop) ?? ['Tomato']
  return (
    <select aria-label="Crop for this farm" value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-line bg-paper p-2 text-sm">
      {crops.map((c) => <option key={c}>{c}</option>)}
    </select>
  )
}

export function LocationSelector({ a, onManage }: { a: Agri; onManage: () => void }) {
  const [consent, setConsent] = useState(false)
  const sel = a.selection
  const value = sel?.kind === 'farm' ? String(sel.farmId) : 'adhoc'
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="flex items-center gap-2 text-sm"><MapPin size={16} className="text-forest" />
        <select aria-label="Farm or location" value={value} className="max-w-[17rem] rounded-lg border border-line bg-paper px-2 py-1.5"
          onChange={(e) => { if (e.target.value !== 'adhoc') a.setSelection({ kind: 'farm', farmId: Number(e.target.value) }) }}>
          {sel?.kind === 'location' && (
            <option value="adhoc">{sel.source === 'gps' ? 'Current location (approx.)' : `Searched: ${sel.label ?? 'place'}`}</option>
          )}
          {a.farms.map((x) => <option key={x.id} value={x.id}>{x.name} — {x.location}</option>)}
        </select></label>
      <button className="btn btn-ghost" onClick={() => setConsent(true)} disabled={a.geo.status === 'locating'}>
        <LocateFixed size={16} /> {a.geo.status === 'locating' ? 'Locating…' : 'Use my location'}
      </button>
      <button className="btn btn-ghost" onClick={onManage} aria-label="Manage farms and locations"><Settings size={16} /><span className="hidden sm:inline">Farms</span></button>
      {consent && (
        <Modal title="Use your current location?" onClose={() => setConsent(false)}>
          <p className="text-sm">AgriSentry will ask your browser for your position to fetch weather for where you are now.</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
            <li>Coordinates are rounded to about 1 km before they are sent to the AgriSentry server, which uses them only to request weather.</li>
            <li>They are not saved unless you choose “Save as farm”.</li>
            <li>Your browser will show its own permission prompt; you can decline.</li>
          </ul>
          <div className="mt-4 flex justify-end gap-2">
            <button className="btn btn-ghost" onClick={() => setConsent(false)}>Not now</button>
            <button className="btn btn-primary" onClick={() => { setConsent(false); a.requestLocation() }}><LocateFixed size={15} /> Continue</button>
          </div>
        </Modal>
      )}
    </div>
  )
}

export function GeoBanner({ a, onManage }: { a: Agri; onManage: () => void }) {
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('My field')
  const [crop, setCrop] = useState(a.crop)
  const [err, setErr] = useState<string | null>(null)
  const sel = a.selection
  if (a.geo.status === 'error') {
    return (
      <Notice tone="warn">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>{a.geo.error}</span>
          <span className="flex gap-2">
            <button className="btn btn-ghost" onClick={a.requestLocation}>Try again</button>
            <button className="btn btn-ghost" onClick={() => { a.dismissGeoError(); onManage() }}>Search a place</button>
            <button className="btn btn-ghost" onClick={a.dismissGeoError} aria-label="Dismiss"><X size={14} /></button>
          </span>
        </div>
      </Notice>
    )
  }
  if (sel?.kind !== 'location') return null
  const place = a.forecast?.place.label
  return (
    <Notice tone="info">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>{sel.source === 'gps' ? 'Showing weather for your current location' : 'Showing weather for a searched place'}{place ? ` — ${place}` : ''}. Not saved.</span>
        <span className="flex gap-2">
          <button className="btn btn-ghost" onClick={() => { setSaving(true); setCrop(a.crop) }}><Save size={14} /> Save as farm</button>
          {a.farms[0] && <button className="btn btn-ghost" onClick={() => a.setSelection({ kind: 'farm', farmId: a.farms[0].id })}>Back to saved farms</button>}
        </span>
      </div>
      {saving && (
        <Modal title="Save this location as a farm" onClose={() => setSaving(false)}>
          <p className="text-sm text-muted">This stores the approximate coordinates (about 1 km) with the farm so you can monitor it later.</p>
          <label className="mt-3 block text-sm">Farm name<input className="mt-1 w-full rounded-lg border border-line bg-paper p-2" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></label>
          <label className="mt-3 block text-sm">Crop<CropSelect a={a} value={crop} onChange={setCrop} /></label>
          {err && <div className="mt-3"><Notice tone="error">{err}</Notice></div>}
          <div className="mt-4 flex justify-end gap-2">
            <button className="btn btn-ghost" onClick={() => setSaving(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={!name.trim()} onClick={async () => {
              try { await a.saveLocationAsFarm(name.trim(), crop, place ?? sel.label ?? 'Saved location'); setSaving(false) } catch (e) { setErr((e as Error).message) }
            }}><Save size={15} /> Save farm</button>
          </div>
        </Modal>
      )}
    </Notice>
  )
}

export function FarmManager({ a, onClose }: { a: Agri; onClose: () => void }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<GeoResult[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [picked, setPicked] = useState<GeoResult | null>(null)
  const [name, setName] = useState('')
  const [crop, setCrop] = useState('Tomato')
  const placeName = (r: GeoResult) => [r.name, r.state, r.country].filter(Boolean).join(', ')

  const search = async () => {
    setBusy(true); setMsg(null); setPicked(null)
    try { const r = await api.geocode(q); setResults(r.results); setMsg(r.error) } catch (e) { setMsg((e as Error).message) } finally { setBusy(false) }
  }
  const save = async () => {
    if (!picked) return
    try {
      const f = await api.createFarm({ name: name.trim(), location: placeName(picked), lat: picked.lat, lon: picked.lon, crop })
      await a.refreshFarms(); a.setSelection({ kind: 'farm', farmId: f.id }); onClose()
    } catch (e) { setMsg((e as Error).message) }
  }
  const remove = async (id: number) => {
    try {
      await api.deleteFarm(id)
      const list = await a.refreshFarms()
      if (a.selection?.kind === 'farm' && a.selection.farmId === id && list[0]) a.setSelection({ kind: 'farm', farmId: list[0].id })
    } catch (e) { setMsg((e as Error).message) }
  }
  return (
    <Modal title="Farms & locations" onClose={onClose}>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Saved farms</h3>
      <ul className="mt-2 divide-y divide-line text-sm">
        {a.farms.map((f) => (
          <li key={f.id} className="flex items-center justify-between gap-2 py-2">
            <button className="text-left hover:underline" onClick={() => { a.setSelection({ kind: 'farm', farmId: f.id }); onClose() }}>
              <span className="font-medium">{f.name}</span> <span className="text-muted">· {f.location} · {f.crop}</span></button>
            {f.is_seed ? <span className="text-xs text-muted">demo farm</span>
              : <button className="btn btn-ghost" aria-label={`Delete ${f.name}`} onClick={() => remove(f.id)}><Trash2 size={14} /></button>}
          </li>
        ))}
      </ul>
      <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-muted">Find a place</h3>
      <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); search() }}>
        <input aria-label="Search for a village, town or city" placeholder="e.g. Narayangaon, Maharashtra" value={q} onChange={(e) => setQ(e.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-line bg-paper p-2 text-sm" />
        <button className="btn btn-primary" disabled={busy || q.trim().length < 2}><Search size={15} /> {busy ? 'Searching…' : 'Search'}</button>
      </form>
      {msg && <div className="mt-2"><Notice tone="warn">{msg}</Notice></div>}
      <ul className="mt-2 space-y-1 text-sm">
        {results.map((r) => (
          <li key={`${r.lat},${r.lon}`} className={`flex flex-wrap items-center justify-between gap-2 rounded-lg p-2 ${picked === r ? 'bg-sage-50' : ''}`}>
            <span>{placeName(r)}</span>
            <span className="flex gap-2">
              <button className="btn btn-ghost" onClick={() => { a.setSelection({ kind: 'location', lat: r.lat, lon: r.lon, label: placeName(r), source: 'search' }); onClose() }}>View weather</button>
              <button className="btn btn-ghost" onClick={() => { setPicked(r); setName(r.name) }}>Save as farm…</button>
            </span>
          </li>
        ))}
      </ul>
      {picked && (
        <div className="mt-3 space-y-2 rounded-xl border border-line p-3 text-sm">
          <p className="font-medium">New farm at {placeName(picked)}</p>
          <label className="block">Name<input className="mt-1 w-full rounded-lg border border-line bg-paper p-2" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></label>
          <label className="block">Crop<CropSelect a={a} value={crop} onChange={setCrop} /></label>
          <div className="flex justify-end"><button className="btn btn-primary" disabled={!name.trim()} onClick={save}><Save size={15} /> Save farm</button></div>
        </div>
      )}
    </Modal>
  )
}

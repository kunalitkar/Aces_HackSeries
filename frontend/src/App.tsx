import { useState } from 'react'
import { Bell, CalendarClock, ClipboardList, CloudSun, LayoutDashboard, Leaf, MapPin, Menu, ScanSearch, User, X } from 'lucide-react'
import { useAgri, type View } from './useAgri'
import type { Mode } from './api'
import { Advisories, History, Monitoring, Overview, WeatherOutlook } from './pages'

const NAV: { id: View; label: string; icon: typeof Leaf }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'monitoring', label: 'Crop Monitoring', icon: ScanSearch },
  { id: 'weather', label: 'Weather Outlook', icon: CloudSun },
  { id: 'advisories', label: 'Field Advisories', icon: ClipboardList },
  { id: 'history', label: 'Assessment History', icon: CalendarClock },
]
const MODES: { id: Mode; label: string }[] = [
  { id: 'live', label: 'Live weather' },
  { id: 'normal', label: 'Demo: normal' },
  { id: 'conducive', label: 'Demo: disease-conducive' },
]

export default function App() {
  const a = useAgri()
  const [menu, setMenu] = useState(false)
  const [panel, setPanel] = useState<'notif' | 'profile' | null>(null)
  const f = a.forecast

  const notifications: { text: string; tone: string }[] = []
  if (f && f.advisory.level !== 'info') notifications.push({ text: f.advisory.headline, tone: f.advisory.level })
  if (f?.weather.status === 'unavailable') notifications.push({ text: 'Live weather unavailable — choose a demo scenario.', tone: 'warning' })
  if (a.health && !a.health.model.available) notifications.push({ text: 'Image model unavailable — classification disabled.', tone: 'warning' })
  if (f?.risk.peak && f.risk.index != null && f.risk.peak.index > f.risk.index + 5) notifications.push({ text: `Favourability expected to peak at ${Math.round(f.risk.peak.index)}/100 (${f.risk.peak.category}).`, tone: 'watch' })

  const go = (v: View) => { a.setView(v); setMenu(false); setPanel(null) }
  const sidebar = (
    <nav className="flex h-full flex-col gap-1 p-4" aria-label="Main">
      <div className="mb-4 flex items-center gap-2 px-2">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-forest text-white"><Leaf size={20} /></span>
        <div><p className="font-serif text-lg leading-none text-forest">AgriSentry</p><p className="text-[11px] text-muted">See the risk. Act before it spreads.</p></div>
      </div>
      {NAV.map(({ id, label, icon: Icon }) => (
        <button key={id} onClick={() => go(id)} aria-current={a.view === id ? 'page' : undefined}
          className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium ${a.view === id ? 'bg-forest text-white' : 'text-ink hover:bg-sage-50'}`}>
          <Icon size={18} />{label}
        </button>
      ))}
      <div className="mt-auto rounded-xl bg-sage-50 p-3 text-xs text-muted">
        <p className="font-semibold text-forest">System status</p>
        <p>Image model: {a.health ? (a.health.model.available ? 'ready' : 'unavailable') : 'backend offline'}</p>
        <p>Live weather: {a.health?.weather.live_configured ? 'configured' : 'not configured'}</p>
        <p>Database: {a.health?.database.mode ?? '—'}</p>
      </div>
    </nav>
  )

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="sticky top-0 hidden h-screen border-r border-line bg-paper lg:block">{sidebar}</aside>
      {menu && (
        <div className="fixed inset-0 z-40 lg:hidden"><div className="absolute inset-0 bg-black/30" onClick={() => setMenu(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-paper shadow-xl"><button aria-label="Close menu" className="absolute right-3 top-3 p-1" onClick={() => setMenu(false)}><X size={20} /></button>{sidebar}</aside></div>
      )}
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex flex-wrap items-center gap-3 border-b border-line bg-cream/95 px-4 py-3 backdrop-blur md:px-8">
          <button className="btn btn-ghost lg:hidden" aria-label="Open menu" onClick={() => setMenu(true)}><Menu size={18} /></button>
          <label className="flex items-center gap-2 text-sm"><MapPin size={16} className="text-forest" />
            <select aria-label="Farm" value={a.farmId ?? ''} onChange={(e) => a.setFarmId(Number(e.target.value))} className="rounded-lg border border-line bg-paper px-2 py-1.5">
              {a.farms.map((x) => <option key={x.id} value={x.id}>{x.name} — {x.location}</option>)}
            </select></label>
          <div role="group" aria-label="Weather data source" className="flex overflow-hidden rounded-lg border border-line bg-paper text-xs font-medium">
            {MODES.map((m) => (
              <button key={m.id} onClick={() => a.setMode(m.id)} aria-pressed={a.mode === m.id}
                className={`px-3 py-2 ${a.mode === m.id ? 'bg-forest text-white' : 'hover:bg-sage-50'}`}>{m.label}</button>
            ))}
          </div>
          <div className="relative ml-auto flex items-center gap-2">
            <button className="btn btn-ghost relative" aria-label="Notifications" onClick={() => setPanel(panel === 'notif' ? null : 'notif')}>
              <Bell size={17} />{notifications.length > 0 && <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-alert px-1 text-[10px] text-white">{notifications.length}</span>}
            </button>
            <button className="btn btn-ghost" aria-label="Profile" onClick={() => setPanel(panel === 'profile' ? null : 'profile')}><User size={17} /></button>
            {panel && (
              <div className="card absolute right-0 top-12 z-50 w-80 p-4 text-sm">
                {panel === 'notif' ? (<>
                  <p className="mb-2 font-semibold">Notifications</p>
                  {notifications.length ? <ul className="space-y-2">{notifications.map((n) => <li key={n.text} className="rounded-lg bg-amber-50 p-2">{n.text}</li>)}</ul> : <p className="text-muted">No active alerts. Conditions are routine.</p>}
                </>) : (<>
                  <p className="font-semibold">Demo farmer</p><p className="text-xs text-muted">Prototype account, no sign-in</p>
                  <div className="mt-3 flex flex-col gap-2">
                    <button className="btn btn-ghost" onClick={() => { a.removeImage(); a.setMode('normal'); go('overview') }}>Reset demo state</button>
                    <button className="btn btn-ghost" onClick={() => { a.setMode('live'); go('weather') }}>Switch to live weather</button>
                  </div>
                </>)}
              </div>
            )}
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-4 md:p-8">
          {a.loading && !f && <p className="text-muted">Loading assessment…</p>}
          {a.view === 'overview' && <Overview a={a} />}
          {a.view === 'monitoring' && <Monitoring a={a} />}
          {a.view === 'weather' && <WeatherOutlook a={a} />}
          {a.view === 'advisories' && <Advisories a={a} />}
          {a.view === 'history' && <History a={a} />}
          <p className="mt-10 text-center text-xs text-muted">AgriSentry is a decision-support prototype. Weather favourability and AI image output do not confirm infection — verify in the field and consult local agricultural guidance.</p>
        </main>
      </div>
    </div>
  )
}

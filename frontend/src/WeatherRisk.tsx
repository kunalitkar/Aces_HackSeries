/* Farmer-facing weather-risk views. Every number and sentence comes from the backend risk engine/advisory;
   nothing is recalculated here. */
import { CloudRain, Droplets, Thermometer, Timer, type LucideIcon } from 'lucide-react'
import { fmtDateTime, type Advisory, type DailyRisk, type Factor, type Risk } from './api'
import { CAT_COLOR, Card, Notice } from './ui'

const ICON: Record<string, LucideIcon> = { duration: Timer, temperature: Thermometer, humidity: Droplets, rain: CloudRain }
const BASIS: Record<string, string> = {
  'current observation + forecast': 'Current weather and forecast',
  forecast: 'Forecast weather',
  simulated: 'Simulated demo weather (not real)',
}
const dayLabel = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString('en-IN', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short' })

export function CropHealthRisk({ risk, crop, disease, updated, offset }: { risk: Risk | undefined; crop: string; disease?: string; updated?: string; offset?: number }) {
  if (!risk) return null
  if (risk.status !== 'ok') {
    return (
      <Card title="Crop health risk">
        <p className="text-lg font-semibold">{crop}</p>
        <Notice tone={risk.status === 'not_applicable' ? 'info' : 'warn'}>
          {risk.status === 'not_applicable'
            ? `A validated weather-based risk assessment is not available for ${crop}. The forecast below is still accurate; use leaf photos and regular field checks to watch for disease.`
            : `Weather risk is unavailable right now: ${risk.reason ?? 'no weather data'}.`}
        </Notice>
      </Card>
    )
  }
  const color = CAT_COLOR[risk.category!]
  return (
    <section className="card p-5" aria-labelledby="chr-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="chr-title" className="text-sm font-semibold uppercase tracking-wide text-muted">Crop health risk</h2>
          <p className="mt-1 text-sm">{crop} · {disease ?? 'Late blight'} · weather-based (experimental)</p>
        </div>
        <span className="rounded-full px-3 py-1 text-sm font-bold tracking-wide text-white" style={{ background: color }}>{risk.category!.toUpperCase()}</span>
      </div>
      <div className="mt-4">
        <div className="flex items-baseline gap-2"><span className="text-3xl font-bold tabular-nums">{Math.round(risk.index!)}</span><span className="text-muted">/ 100 weather score</span></div>
        <div className="mt-2 h-3 overflow-hidden rounded-full bg-sage-50" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(risk.index!)} aria-label="Weather risk score">
          <div className="h-3 rounded-full" style={{ width: `${risk.index}%`, background: color }} />
        </div>
        <div className="mt-1 flex justify-between text-[11px] text-muted"><span>Low</span><span>Moderate</span><span>High</span><span>Very high</span></div>
      </div>
      <p className="mt-3 text-base">{risk.level_text}</p>
      <p className="mt-2 text-xs text-muted">
        {risk.period && <>Period: next 12 h from {fmtDateTime(risk.period.start, offset)} · {BASIS[risk.period.basis] ?? risk.period.basis}</>}
        {updated && <> · updated {fmtDateTime(updated, offset)}</>}
      </p>
      <p className="mt-1 text-xs text-muted">The score shows how much the weather favours the disease. It is not the chance that your crop is infected.</p>
    </section>
  )
}

function FactorRow({ f }: { f: Factor }) {
  const Icon = ICON[f.key] ?? Thermometer
  const has = f.value != null
  return (
    <li className="flex gap-3 py-3">
      <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-sage-50 text-forest"><Icon size={18} /></span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-medium">{f.name ?? f.label}</p>
          <p className="tabular-nums">{has ? `${f.value} ${f.unit}` : 'Data unavailable'}</p>
        </div>
        <p className="text-sm">{f.interpretation}</p>
        <p className="text-xs text-muted">Why it matters: {f.why}</p>
        <div className="mt-1 flex items-center gap-2 text-[11px] text-muted">
          <div className="h-1.5 w-24 rounded-full bg-sage-50"><div className="h-1.5 rounded-full bg-forest" style={{ width: `${(f.points / f.max_points) * 100}%` }} /></div>
          adds {f.points.toFixed(1)} of {f.max_points} points
        </div>
      </div>
    </li>
  )
}

export function WhyAtRisk({ risk }: { risk: Risk }) {
  const factors = [...risk.factors!].sort((x, y) => y.points / y.max_points - x.points / x.max_points)
  return (
    <Card title="Why is my crop at risk?">
      <p className="text-xs text-muted">Weather in the assessment period ({risk.period ? (BASIS[risk.period.basis] ?? risk.period.basis).toLowerCase() : 'forecast'}), most important first.</p>
      <ul className="divide-y divide-line">{factors.map((f) => <FactorRow key={f.key} f={f} />)}</ul>
      <p className="text-xs text-muted">These weather conditions can favour the disease; they do not prove that plants are infected.</p>
    </Card>
  )
}

export function DailyRiskList({ risk }: { risk: Risk }) {
  const days = risk.daily ?? []
  return (
    <Card title="Day-by-day risk">
      {days.length === 0 ? <p className="text-sm text-muted">Forecast risk by day is unavailable for this data.</p> : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {days.map((d: DailyRisk) => (
            <li key={d.date} className="rounded-xl border border-line p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{dayLabel(d.date)}</p>
                <span className="rounded-full px-2 py-0.5 text-xs font-bold text-white" style={{ background: CAT_COLOR[d.category] }}>{d.category.toUpperCase()}</span>
              </div>
              <p className="mt-1 text-sm"><span className="capitalize">{d.weather.description ?? 'Weather summary'}</span>{' · '}
                {d.weather.temp_min != null ? `${Math.round(d.weather.temp_min)}–${Math.round(d.weather.temp_max!)} °C` : 'temp n/a'}
                {' · '}{d.weather.rh_mean != null ? `RH ${d.weather.rh_mean}%` : 'RH n/a'}
                {' · '}{d.weather.rain_mm != null ? `${d.weather.rain_mm} mm rain` : 'rain n/a'}</p>
              <p className="mt-1 text-xs"><span className="text-muted">Main factor:</span> {d.main_factor ?? 'none'}</p>
              <p className="text-xs"><span className="text-muted">What to do:</span> {d.action}</p>
              <p className="mt-1 text-[11px] text-muted">{d.basis === 'simulated' ? 'Simulated' : d.basis === 'forecast' ? 'Forecast' : 'Current + forecast'}{d.partial ? ' · partial day (limited data)' : ''} · score {Math.round(d.index)}/100</p>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted">Each day shows the highest 12-hour weather score starting that day. Days without enough forecast data are left out.</p>
    </Card>
  )
}

export function WhatShouldIDo({ advisory }: { advisory: Advisory }) {
  const steps = [...new Set([...advisory.inspect, ...advisory.actions])].slice(0, 5)
  return (
    <Card title="What should I do?">
      <p className="mb-2 font-medium">{advisory.headline}</p>
      <p className="mb-2 text-xs text-muted">Based on today’s weather risk{advisory.evidence[0]?.text.startsWith('No leaf image') ? '' : ' and your latest leaf photo'}.</p>
      <ol className="list-decimal space-y-1 pl-5 text-sm">{steps.map((s) => <li key={s}>{s}</li>)}</ol>
      <p className="mt-2 text-sm"><strong>Check again:</strong> {advisory.reassess}</p>
      <p className="mt-2 text-xs text-muted">If you see symptoms, ask your local Krishi Vigyan Kendra (KVK) or agriculture officer before using any pesticide. AgriSentry does not recommend sprays or doses.</p>
    </Card>
  )
}

import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Check, Download, Droplets, Gauge as GaugeIcon, ImagePlus, Printer, RefreshCw, Replace, Save, Thermometer, Trash2, Upload, Wind } from 'lucide-react'
import { api, fmtDateTime, fmtTime, prettyLabel, tzLabel, type Assessment, type ImageResult, type Risk, type WeatherPoint } from './api'
import type { Agri } from './useAgri'
import { AdvisoryBanner, CAT_COLOR, Card, CurrentStats, DataBadge, Factors, Gauge, Notice, RiskTrend, WeatherChart } from './ui'
import { downloadReport, printReport } from './report'

const pct = (n: number) => `${Math.round(n * 100)}%`

function WeatherUnavailable({ a }: { a: Agri }) {
  const w = a.forecast?.weather
  return (
    <Notice tone="error">
      <p className="font-semibold">Weather data unavailable</p>
      <p className="mt-1">{w?.error ?? a.forecast?.risk.reason ?? 'The weather service did not respond.'}</p>
      {w?.hint && <p className="mt-1">{w.hint}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <button className="btn btn-ghost" onClick={() => a.reload(false, true)}><RefreshCw size={14} /> Retry</button>
        <span>Image analysis still works. Use the data-source switch for a clearly labelled demo scenario.</span>
      </div>
    </Notice>
  )
}

function RiskUnavailable({ risk }: { risk: Risk | undefined }) {
  if (risk?.status === 'not_applicable') return <Notice tone="info">{risk.reason}</Notice>
  return <p className="text-sm text-muted">{risk?.reason ?? 'Risk unavailable — no weather data.'}</p>
}

export function HealthBadge({ r }: { r: ImageResult }) {
  const [cls, text] = r.uncertain ? ['bg-amber-50 text-amber-warn', 'Uncertain'] : r.healthy ? ['bg-sage-50 text-forest', 'Healthy pattern'] : ['bg-alert-50 text-alert', 'Disease pattern']
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>{text}</span>
}

export function ImageSummary({ result, error, loading }: { result: ImageResult | null; error: string | null; loading: boolean }) {
  if (loading) return <p className="text-sm text-muted">Analysing leaf image…</p>
  if (error) return <Notice tone="error">{error}</Notice>
  if (!result) return <p className="text-sm text-muted">No leaf image analysed yet.</p>
  if (result.status !== 'ok') return <Notice tone="warn">Image classification unavailable: {result.error}</Notice>
  const alt = result.unrestricted_top3?.[0]
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2"><p className="text-lg font-semibold">{result.crop} — {result.condition}</p><HealthBadge r={result} /></div>
      <p className="text-sm text-muted">Model score {pct(result.score!)} · {result.latency_ms} ms</p>
      {result.single_class_crop && <Notice tone="warn">The model has only one class for {result.crop}, so it cannot separate healthy from diseased leaves for this crop. Inspect the plant in the field.</Notice>}
      {result.crop_mismatch && alt && <Notice tone="warn">This photo does not look like {result.selected_crop} to the model (only {pct(result.crop_mass ?? 0)} of its score went to {result.selected_crop}; closest overall: {alt.crop} – {alt.condition}). Check the crop selection or retake the photo.</Notice>}
      {!result.crop_mismatch && !result.single_class_crop && result.low_confidence && <Notice tone="warn">Low model score — retake a sharp, well-lit close-up of one leaf on a plain background.</Notice>}
    </div>
  )
}

function RecentAlerts({ a }: { a: Agri }) {
  const open = a.alerts.filter((x) => !x.acknowledged).slice(0, 3)
  if (!open.length) return null
  return (
    <Card title="Open alerts" action={<button className="btn btn-ghost" onClick={() => a.setView('alerts')}>All alerts <ArrowRight size={14} /></button>}>
      <ul className="space-y-2 text-sm">{open.map((x) => (
        <li key={x.id} className="flex flex-wrap items-center justify-between gap-2">
          <span>{x.message} {x.simulated && <SimTag />}</span>
          <span className="text-xs text-muted">{fmtDateTime(x.created_at)}</span>
        </li>))}</ul>
    </Card>
  )
}
const SimTag = () => <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-warn">simulated</span>

export function Overview({ a }: { a: Agri }) {
  const f = a.forecast
  const risk = f?.risk
  const ok = risk?.status === 'ok'
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-forest">{a.farm?.name ?? f?.place.label ?? 'AgriSentry'}</h1>
          <p className="text-muted">{a.farm ? `${a.farm.location} · ` : ''}{a.crop}{a.catalog?.weather_model[a.crop] ? ` · ${a.catalog.weather_model[a.crop].toLowerCase()} watch` : ''}</p>
        </div>
        <button className="btn btn-primary" onClick={() => a.reload(true)} disabled={!f}><Save size={16} /> Save assessment</button>
      </div>
      {a.saveMsg && <Notice tone="info">{a.saveMsg}</Notice>}
      {a.error && <Notice tone="error">{a.error}</Notice>}
      {f && <AdvisoryBanner advisory={f.advisory} />}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Current weather" action={<DataBadge weather={f?.weather} />}>
          {f?.weather.current ? (<>
            <CurrentStats p={f.weather.current} />
            <p className="mt-3 text-xs text-muted">{f.place.label} · {f.weather.label}{f.weather.fetched_at && ` · updated ${fmtDateTime(f.weather.fetched_at, f.weather.utc_offset_seconds)}`}</p>
            {risk?.stale && <p className="mt-1 text-xs text-alert">Observation is {risk.data_age_hours} h old — refresh.</p>}
          </>) : f ? <WeatherUnavailable a={a} /> : <p className="text-sm text-muted">Loading…</p>}
        </Card>
        <Card title="Late-blight weather favourability">
          {ok ? (<>
            <Gauge index={risk!.index!} category={risk!.category!} />
            <p className="mt-3 text-xs text-muted">Next 12 h, experimental index. Not a probability of infection.</p>
          </>) : <RiskUnavailable risk={risk} />}
        </Card>
        <Card title="Leaf image result" action={<button className="btn btn-ghost" onClick={() => a.setView('monitoring')}>{a.image.previewUrl ? 'Details' : 'Upload'} <ArrowRight size={14} /></button>}>
          <div className="flex gap-3">
            {a.image.previewUrl && <img src={a.image.previewUrl} alt="Uploaded leaf" className="h-20 w-20 rounded-lg object-cover" />}
            <ImageSummary result={a.image.result} error={a.image.error} loading={a.image.loading} />
          </div>
          <p className="mt-3 text-xs text-muted">Image prediction is separate from the weather index. Severity: not estimated.</p>
        </Card>
      </div>
      <div className="grid gap-5 lg:grid-cols-5">
        <Card title="Forecast favourability trend" className="lg:col-span-3" action={<button className="btn btn-ghost" onClick={() => a.setView('weather')}>Weather outlook <ArrowRight size={14} /></button>}>
          {ok ? <RiskTrend risk={risk!} offset={f?.weather.utc_offset_seconds} /> : <RiskUnavailable risk={risk} />}
        </Card>
        <Card title="Main risk contributors" className="lg:col-span-2">
          {ok ? <Factors factors={risk!.factors!} /> : <p className="text-sm text-muted">No weather factors for this selection.</p>}
        </Card>
      </div>
      {f && (
        <Card title="Recommended next action" action={<button className="btn btn-ghost" onClick={() => a.setView('advisories')}>Full advisory <ArrowRight size={14} /></button>}>
          <ul className="list-disc space-y-1 pl-5 text-sm">{[...f.advisory.inspect, ...f.advisory.actions].slice(0, 3).map((t) => <li key={t}>{t}</li>)}</ul>
        </Card>
      )}
      <RecentAlerts a={a} />
    </div>
  )
}

export function Monitoring({ a }: { a: Agri }) {
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const r = a.image.result
  const crops = a.catalog?.crops ?? []
  const info = crops.find((c) => c.crop === a.crop)
  const pick = (files: FileList | null) => { if (files?.[0]) a.setFile(files[0]) }
  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-3xl text-forest">Crop monitoring</h1>
        <p className="text-muted">AI visual screening of a single leaf photo with EfficientNetV2-S (38 PlantVillage classes, 14 crops).</p>
      </div>
      {a.catalog && !a.catalog.available && <Notice tone="error">Image model unavailable: {a.catalog.error}</Notice>}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Crop & supported classes">
          <label className="block text-sm"><span className="text-muted">Crop</span>
            <select aria-label="Crop" value={a.crop} onChange={(e) => a.setCrop(e.target.value)} className="mt-1 w-full rounded-lg border border-line bg-paper p-2">
              {(crops.length ? crops.map((c) => c.crop) : [a.crop]).map((c) => <option key={c}>{c}</option>)}
            </select></label>
          {info && (
            <div className="mt-3">
              <p className="text-xs text-muted">The model can recognise these {info.crop.toLowerCase()} classes:</p>
              <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Supported classes">
                {info.classes.map((c) => <li key={c.label} className={`rounded-full px-2.5 py-1 text-xs ${c.healthy ? 'bg-sage-50 text-forest' : 'bg-amber-50 text-amber-warn'}`}>{c.condition}</li>)}
              </ul>
              {info.classes.length === 1 && <p className="mt-2 text-xs text-alert">Only one class exists for {info.crop}; the model cannot separate healthy from diseased leaves for this crop.</p>}
              {!info.has_healthy_class && info.classes.length > 1 && <p className="mt-2 text-xs text-alert">No healthy class exists for {info.crop}.</p>}
              <p className="mt-2 text-xs text-muted">Diseases not listed cannot be recognised. Weather-based forecasting: {a.catalog?.weather_model[info.crop] ? `${a.catalog.weather_model[info.crop]} (experimental)` : 'not available for this crop'}.</p>
            </div>
          )}
          <div className="mt-4">
            <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" data-testid="file-input" onChange={(e) => { pick(e.target.files); e.target.value = '' }} />
            {!a.image.previewUrl ? (
              <button type="button" onClick={() => input.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files) }}
                className={`flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed p-10 text-muted ${drag ? 'border-forest bg-sage-50' : 'border-line'}`}>
                <ImagePlus size={32} /><span className="font-medium text-ink">Drop a {a.crop.toLowerCase()} leaf photo or click to upload</span><span className="text-xs">JPEG, PNG or WebP · up to 8 MB</span>
              </button>
            ) : (
              <div>
                <img src={a.image.previewUrl} alt="Leaf preview" className="max-h-80 w-full rounded-xl bg-sage-50 object-contain" />
                <div className="mt-3 flex gap-2">
                  <button className="btn btn-ghost" onClick={() => input.current?.click()}><Replace size={15} /> Replace</button>
                  <button className="btn btn-ghost" onClick={a.removeImage}><Trash2 size={15} /> Remove</button>
                </div>
              </div>
            )}
          </div>
        </Card>
        <div className="space-y-5">
          <Card title="Model result">
            {!a.image.previewUrl && <p className="text-sm text-muted"><Upload className="mb-1 inline" size={16} /> Upload a photo to run inference.</p>}
            <ImageSummary result={r} error={a.image.error} loading={a.image.loading} />
            {r?.status === 'ok' && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{r.single_class_crop ? 'Raw score' : `Top candidates within ${r.selected_crop}`}</p>
                <ul className="space-y-2">
                  {r.top3!.map((t) => (
                    <li key={t.label} className="text-sm">
                      <div className="flex justify-between"><span>{t.condition}</span><span className="tabular-nums text-muted">{pct(t.score)}</span></div>
                      <div className="mt-1 h-1.5 rounded-full bg-sage-50"><div className="h-1.5 rounded-full bg-forest" style={{ width: pct(t.score) }} /></div>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-xs text-muted">Scores are renormalised over the selected crop's classes. Share of the full 38-class score given to {r.selected_crop}: {pct(r.crop_mass ?? 0)}. {r.score_note}</p>
                <p className="mt-1 text-xs text-muted">Model: {r.model_version}</p>
              </div>
            )}
            <div className="mt-4"><Notice tone="info">Trained on lab-style PlantVillage images. On 204 real field photos (PlantDoc test set, crops with several classes) it picked the right class 39% of the time when the crop was stated, so treat results as screening only and confirm in the field.</Notice></div>
          </Card>
          <Card title="Visual severity">
            <p className="text-sm">{a.forecast?.advisory.severity.text ?? 'Not estimated.'}</p>
            <p className="mt-2 text-sm text-muted">{a.forecast?.advisory.severity.manual}</p>
          </Card>
        </div>
      </div>
      {a.forecast && <Card title="Combined advisory"><AdvisoryBanner advisory={a.forecast.advisory} /></Card>}
    </div>
  )
}

const iconUrl = (icon: string) => `https://openweathermap.org/img/wn/${icon}@2x.png`
const val = (v: number | null | undefined, unit = '', digits = 1) => (v == null ? 'n/a' : `${Number(v.toFixed(digits))}${unit}`)

function CurrentConditions({ p }: { p: WeatherPoint }) {
  const stats = [
    { icon: <Thermometer size={16} />, l: 'Temperature', v: val(p.temp_c, '°C') },
    { icon: <Thermometer size={16} />, l: 'Feels like', v: val(p.feels_like_c, '°C') },
    { icon: <Droplets size={16} />, l: 'Humidity', v: val(p.rh, '%', 0) },
    { icon: <GaugeIcon size={16} />, l: 'Pressure', v: val(p.pressure_hpa, ' hPa', 0) },
    { icon: <Wind size={16} />, l: 'Wind', v: val(p.wind_ms, ' m/s') },
    { icon: <Droplets size={16} />, l: 'Rain (last hour)', v: val(p.rain_mm, ' mm') },
  ]
  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="flex items-center gap-2">
        {p.icon && <img src={iconUrl(p.icon)} alt={p.description ?? 'weather icon'} className="h-16 w-16" />}
        <p className="text-lg font-semibold capitalize">{p.description ?? p.condition ?? 'Conditions n/a'}</p>
      </div>
      <dl className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-3">
        {stats.map((x) => (
          <div key={x.l} className="rounded-xl bg-sage-50 p-3">
            <dt className="flex items-center gap-1 text-xs text-muted">{x.icon}{x.l}</dt>
            <dd className="text-lg font-semibold tabular-nums">{x.v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function IntervalStrip({ risk, offset }: { risk: Risk; offset?: number }) {
  const start = risk.intervals?.[0] ? new Date(risk.intervals[0].time).getTime() : 0
  const items = (risk.intervals ?? []).filter((i) => new Date(i.time).getTime() < start + 48 * 3600e3)
  const total = items.reduce((s, i) => s + i.hours, 0) || 1
  return (
    <div>
      <div className="flex h-6 overflow-hidden rounded-md border border-line" role="img" aria-label={`${risk.favourable_hours_48h} favourable hours in the next 48 hours`}>
        {items.map((i) => (
          <div key={i.time} title={`${fmtTime(i.time, offset)} · ${i.kind} · ${i.favourable == null ? 'missing data' : i.favourable ? 'favourable' : 'not favourable'}`}
            style={{ width: `${(i.hours / total) * 100}%` }} className={i.favourable == null ? 'bg-line' : i.favourable ? 'bg-alert/70' : 'bg-sage-50'} />
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted"><span>{items[0] && fmtTime(items[0].time, offset)}</span><span>{items.at(-1) && fmtTime(items.at(-1)!.time, offset)}</span></div>
      <p className="mt-2 text-xs text-muted"><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-alert/70" />favourable for late blight · <span className="mx-1 inline-block h-2.5 w-2.5 rounded-sm border border-line bg-sage-50" />not favourable · <span className="mx-1 inline-block h-2.5 w-2.5 rounded-sm bg-line" />missing data. First interval is {items[0]?.kind === 'observed' ? 'the current observation; the rest are forecasts' : items[0]?.kind === 'simulated' ? 'simulated' : 'a forecast'}.</p>
    </div>
  )
}

function RulesCard({ risk }: { risk: Risk }) {
  const r = risk.rules!
  return (
    <Card title="How this score is calculated">
      <p className="text-sm"><strong>{r.disease}.</strong> {r.status}.</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        <li>Favourable interval: {r.favourable_interval}; leaf-wetness proxy: {r.leaf_wetness_proxy}.</li>
        {r.components.map((c) => <li key={c.key}><span className="capitalize">{c.key}</span> (0–{c.max}): {c.rule}</li>)}
        <li>Window: {r.window}. Categories: {r.categories}.</li>
        <li>Missing data: {r.missing_data}.</li>
      </ul>
    </Card>
  )
}

export function WeatherOutlook({ a }: { a: Agri }) {
  const f = a.forecast
  const w = f?.weather
  const off = w?.utc_offset_seconds
  const series = w?.series ?? []
  const where = f ? (f.place.kind === 'farm' ? `${f.place.label} (${f.place.lat.toFixed(3)}, ${f.place.lon.toFixed(3)})` : `${f.place.label} · approximate`) : a.farm?.location
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-forest">Weather outlook</h1>
          <p className="text-muted">{where}{w?.location?.name && f?.place.kind === 'farm' ? ` · station: ${w.location.name}` : ''} · local time {tzLabel(off)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DataBadge weather={w} />
          <button className="btn btn-ghost" onClick={() => a.reload(false, true)} disabled={a.loading} aria-label="Refresh weather">
            <RefreshCw size={15} className={a.loading ? 'animate-spin' : ''} /> {a.loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>
      {w && w.status !== 'unavailable' && (
        <p className="text-xs text-muted">
          {w.label} · {w.source}
          {w.observed_at && ` · observed ${fmtDateTime(w.observed_at, off)}`}
          {w.fetched_at && ` · last updated ${fmtDateTime(w.fetched_at, off)}`}
          {w.cached && ' (cached up to 5 min; press Refresh to request fresh data)'}
        </p>
      )}
      {f?.risk.stale && <Notice tone="warn">The latest observation is {f.risk.data_age_hours} h old. Press Refresh before relying on the risk estimate.</Notice>}
      {a.error && <Notice tone="error">{a.error}</Notice>}
      {!f && a.loading && <Card><p className="text-sm text-muted">Loading weather…</p></Card>}
      {!f && !a.loading && !a.error && <Card><p className="text-sm text-muted">No weather data yet.</p></Card>}
      {f && w!.status === 'unavailable' && <WeatherUnavailable a={a} />}
      {f && w!.current && (<>
        <Card title="Current conditions">
          <CurrentConditions p={w!.current} />
          {w!.status === 'demo' && <p className="mt-3 text-xs text-amber-warn">Simulated values, not real measurements. Demo scenarios only carry temperature, humidity and rain.</p>}
        </Card>
        <Card title={w!.status === 'live' ? '5-day forecast (3-hour steps)' : 'Simulated forecast'}>
          <WeatherChart series={series} offset={off} />
          <p className="mt-2 text-xs text-muted">{series.length} time points · rain bars show mm per step.</p>
        </Card>
        {f.risk.status === 'ok' ? <>
          <Card title="Late-blight favourability trend (experimental)">
            <RiskTrend risk={f.risk} height={260} offset={off} />
            <p className="mt-2 text-sm">{f.risk.explanation}</p>
          </Card>
          <Card title={`Favourable intervals, next 48 h: ${f.risk.favourable_hours_48h} h`}><IntervalStrip risk={f.risk} offset={off} /></Card>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card title="Why this score"><Factors factors={f.risk.factors!} /></Card>
            <RulesCard risk={f.risk} />
          </div>
        </> : <Card title="Disease-risk forecast"><RiskUnavailable risk={f.risk} /></Card>}
        <Card title="Forecast table">
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-paper text-left text-muted"><tr><th className="py-1">Local time</th><th>Type</th><th>Conditions</th><th>Temp °C</th><th>RH %</th><th>Rain mm</th><th>Rain prob.</th><th>Wind m/s</th></tr></thead>
              <tbody>{series.map((p) => (
                <tr key={p.time} className="border-t border-line tabular-nums">
                  <td className="py-1">{fmtTime(p.time, off)}</td><td className="text-xs text-muted">{p.kind ?? '—'}</td>
                  <td className="capitalize">{p.description ?? '—'}</td><td>{val(p.temp_c)}</td><td>{val(p.rh, '', 0)}</td><td>{val(p.rain_mm)}</td>
                  <td>{p.pop == null ? '—' : `${Math.round(p.pop * 100)}%`}</td><td>{val(p.wind_ms)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      </>)}
    </div>
  )
}

export function Advisories({ a }: { a: Agri }) {
  const f = a.forecast
  const label = { image: 'Leaf image', weather: 'Weather', severity: 'Severity' }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="font-serif text-3xl text-forest">Field advisories</h1><p className="text-muted">{f?.place.label ?? a.farm?.name} · {a.crop}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <DataBadge weather={f?.weather} />
          <button className="btn btn-ghost" onClick={() => f && printReport(a, f)} disabled={!f}><Printer size={15} /> Print / PDF</button>
          <button className="btn btn-primary" onClick={() => f && downloadReport(a, f)} disabled={!f}><Download size={15} /> Download report</button>
        </div>
      </div>
      {a.error && <Notice tone="error">{a.error}</Notice>}
      {f && (<>
        <AdvisoryBanner advisory={f.advisory} />
        <Card title="Evidence">
          <ul className="space-y-2 text-sm">{f.advisory.evidence.map((e) => <li key={e.source}><strong>{label[e.source]}:</strong> {e.text}</li>)}</ul>
        </Card>
        <div className="grid gap-5 md:grid-cols-2">
          <Card title="What to inspect"><ul className="list-disc space-y-1 pl-5 text-sm">{f.advisory.inspect.map((t) => <li key={t}>{t}</li>)}</ul></Card>
          <Card title="Preventive steps"><ul className="list-disc space-y-1 pl-5 text-sm">{f.advisory.actions.map((t) => <li key={t}>{t}</li>)}</ul></Card>
          <Card title="When to reassess"><p className="text-sm">{f.advisory.reassess}</p><p className="mt-3 text-sm text-muted">{f.advisory.severity.manual}</p></Card>
          <Card title="Why we are saying this"><p className="text-sm">{f.advisory.why}</p></Card>
        </div>
        <Notice tone="warn"><strong>Consult local guidance. </strong>{f.advisory.consult}
          <ul className="mt-1 list-disc pl-5">{f.advisory.references.map((r) => <li key={r}>{r}</li>)}</ul></Notice>
      </>)}
    </div>
  )
}

export function Alerts({ a }: { a: Agri }) {
  const [filter, setFilter] = useState<'open' | 'all'>('open')
  useEffect(() => { a.refreshAlerts() }, [a.refreshAlerts])
  const list = a.alerts.filter((x) => filter === 'all' || !x.acknowledged)
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="font-serif text-3xl text-forest">Alerts</h1><p className="text-muted">Raised when late-blight favourability is High or forecast to become High within 48 h, and for saved assessments with a confident disease prediction. Unchanged conditions do not repeat within 24 h.</p></div>
        <div role="group" aria-label="Alert filter" className="flex overflow-hidden rounded-lg border border-line bg-paper text-xs font-medium">
          {(['open', 'all'] as const).map((k) => <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)} className={`px-3 py-2 ${filter === k ? 'bg-forest text-white' : 'hover:bg-sage-50'}`}>{k === 'open' ? 'Open' : 'All'}</button>)}
        </div>
      </div>
      {a.health && !a.health.database.persistent && <Notice tone="warn">Database not configured: alerts are kept in memory and lost when the backend restarts.</Notice>}
      <Card>
        {list.length === 0 ? <p className="text-sm text-muted">{filter === 'open' ? 'No open alerts.' : 'No alerts yet.'}</p> : (
          <ul className="divide-y divide-line">{list.map((x) => (
            <li key={x.id} className="flex flex-wrap items-start gap-3 py-3">
              <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: x.level === 'alert' ? '#9f1239' : '#b7791f' }} />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{x.message} {x.simulated ? <SimTag /> : <span className="rounded bg-sage-50 px-1.5 py-0.5 text-xs text-forest">{x.kind === 'image' ? 'image' : 'live weather'}</span>}</p>
                <p className="text-sm text-muted">{x.explanation}</p>
                <p className="text-xs text-muted">{fmtDateTime(x.created_at)} IST{x.acknowledged_at && ` · acknowledged ${fmtDateTime(x.acknowledged_at)}`}</p>
              </div>
              {!x.acknowledged && <button className="btn btn-ghost" onClick={() => a.acknowledge(x.id)}><Check size={14} /> Acknowledge</button>}
            </li>))}</ul>
        )}
      </Card>
    </div>
  )
}

export function History({ a }: { a: Agri }) {
  const [data, setData] = useState<{ persistent: boolean; backend: string | null; entries: Assessment[] } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [scope, setScope] = useState<'farm' | 'all'>('all')
  const farmFilter = scope === 'farm' ? a.farmId : null
  useEffect(() => { api.history(farmFilter).then(setData).catch((e) => setErr(e.message)) }, [farmFilter, a.saveMsg])
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="font-serif text-3xl text-forest">Assessment history</h1><p className="text-muted">Assessments you saved with “Save assessment”.</p></div>
        {a.farmId && <div role="group" aria-label="History scope" className="flex overflow-hidden rounded-lg border border-line bg-paper text-xs font-medium">
          {(['all', 'farm'] as const).map((k) => <button key={k} aria-pressed={scope === k} onClick={() => setScope(k)} className={`px-3 py-2 ${scope === k ? 'bg-forest text-white' : 'hover:bg-sage-50'}`}>{k === 'all' ? 'All' : 'This farm'}</button>)}
        </div>}
      </div>
      {err && <Notice tone="error">{err}</Notice>}
      {data && !data.persistent && <Notice tone="warn">Database not configured: history is kept in memory and lost when the backend restarts.</Notice>}
      <Card>
        {data && data.entries.length === 0 ? <p className="text-sm text-muted">No saved assessments yet. Use “Save assessment” on the Overview.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="text-left text-muted"><tr><th className="py-2">When</th><th>Place · crop</th><th>Image prediction</th><th>Weather risk</th><th>Advisory</th></tr></thead>
              <tbody>{data?.entries.map((e) => (
                <tr key={e.id} className="border-t border-line align-top">
                  <td className="py-2 pr-2 text-xs">{fmtDateTime(e.created_at)}</td>
                  <td className="pr-2">{e.location_label}<br /><span className="text-xs text-muted">{e.crop}</span></td>
                  <td className="pr-2">{e.predicted_label ? <>{prettyLabel(e.predicted_label)}<br /><span className="text-xs text-muted">score {pct(e.confidence!)}{e.image_uncertain ? ' · uncertain' : ''}</span></> : <span className="text-muted">—</span>}</td>
                  <td className="pr-2">{e.risk_index != null ? <span style={{ color: CAT_COLOR[e.risk_category!] }}>{Math.round(e.risk_index)}/100 {e.risk_category}</span> : <span className="text-muted">{e.risk_status.replace('_', ' ')}</span>}
                    <br />{e.simulated ? <SimTag /> : <span className="text-xs text-muted">live</span>}</td>
                  <td>{e.advisory_headline}<br /><span className="text-xs text-muted">{e.model_version ? `model ${e.model_version.split('@')[0]}` : ''}</span></td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Download, Droplets, Gauge as GaugeIcon, Thermometer, Wind, ImagePlus, Leaf, RefreshCw, Replace, Save, Trash2, Upload } from 'lucide-react'
import { api, fmtDateTime, fmtTime, tzLabel, type HistoryEntry, type ImageResult, type WeatherPoint } from './api'
import type { Agri } from './useAgri'
import { AdvisoryBanner, Card, CurrentStats, DataBadge, Factors, Gauge, Notice, RiskTrend, WeatherChart } from './ui'

const pct = (n: number) => `${Math.round(n * 100)}%`

function WeatherUnavailable({ a }: { a: Agri }) {
  const w = a.forecast?.weather
  return (
    <Notice tone="error">
      <p className="font-semibold">Weather data unavailable</p>
      <p className="mt-1">{w?.error ?? a.forecast?.risk.reason ?? 'The weather service did not respond.'}</p>
      {w?.hint && <p className="mt-1">{w.hint}</p>}
      <p className="mt-1">Image analysis still works. Use the data-source switch above to choose a clearly labelled demo scenario.</p>
    </Notice>
  )
}

export function ImageSummary({ result, error, loading }: { result: ImageResult | null; error: string | null; loading: boolean }) {
  if (loading) return <p className="text-sm text-muted">Analysing leaf image…</p>
  if (error) return <Notice tone="error">{error}</Notice>
  if (!result) return <p className="text-sm text-muted">No leaf image analysed yet.</p>
  if (result.status !== 'ok') return <Notice tone="warn">Image classification unavailable: {result.error}</Notice>
  return (
    <div>
      <p className="text-lg font-semibold">{result.crop} — {result.condition}</p>
      <p className="text-sm text-muted">Model softmax score {pct(result.score!)} · {result.latency_ms} ms</p>
      {!result.is_tomato && <div className="mt-2"><Notice tone="warn">This looks like a non-tomato class. AgriSentry currently supports tomato only; treat this result as unreliable.</Notice></div>}
      {result.is_tomato && result.low_confidence && <div className="mt-2"><Notice tone="warn">Low model score — retake a sharper, well-lit close-up of a single leaf.</Notice></div>}
    </div>
  )
}

export function Overview({ a }: { a: Agri }) {
  const f = a.forecast
  const risk = f?.risk
  const ok = risk?.status === 'ok'
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-forest">{a.farm?.name ?? 'AgriSentry'}</h1>
          <p className="text-muted">{a.farm?.location} · {a.farm?.crop} · late blight watch</p>
        </div>
        <button className="btn btn-primary" onClick={() => a.reload(true)} disabled={!ok}><Save size={16} /> Save assessment</button>
      </div>
      {a.saveMsg && <Notice tone="info">{a.saveMsg}</Notice>}
      {a.error && <Notice tone="error">{a.error}</Notice>}
      {f && <AdvisoryBanner advisory={f.advisory} />}
      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Current weather" action={<DataBadge weather={f?.weather} />}>
          {f?.weather.current ? (<>
            <CurrentStats p={f.weather.current} />
            <p className="mt-3 text-xs text-muted">{f.weather.label}{f.weather.fetched_at && ` · updated ${fmtDateTime(f.weather.fetched_at, f.weather.utc_offset_seconds)}`}</p>
          </>) : f ? <WeatherUnavailable a={a} /> : <p className="text-sm text-muted">Loading…</p>}
        </Card>
        <Card title="Environmental favourability">
          {ok ? (<>
            <Gauge index={risk!.index!} category={risk!.category!} />
            <p className="mt-3 text-xs text-muted">Weather-driven index for the next 12 h. Not a probability of infection.</p>
          </>) : <p className="text-sm text-muted">{risk?.reason ?? 'Risk unavailable — no weather data.'}</p>}
        </Card>
        <Card title="Leaf image result" action={<button className="btn btn-ghost" onClick={() => a.setView('monitoring')}>{a.image.previewUrl ? 'Details' : 'Upload'} <ArrowRight size={14} /></button>}>
          <div className="flex gap-3">
            {a.image.previewUrl && <img src={a.image.previewUrl} alt="Uploaded leaf" className="h-20 w-20 rounded-lg object-cover" />}
            <ImageSummary result={a.image.result} error={a.image.error} loading={a.image.loading} />
          </div>
          <p className="mt-3 text-xs text-muted">Image prediction is separate from the weather index.</p>
        </Card>
      </div>
      <div className="grid gap-5 lg:grid-cols-5">
        <Card title="Forecast favourability trend" className="lg:col-span-3" action={<button className="btn btn-ghost" onClick={() => a.setView('weather')}>Weather outlook <ArrowRight size={14} /></button>}>
          {ok ? <RiskTrend risk={risk!} offset={f?.weather.utc_offset_seconds} /> : <p className="text-sm text-muted">No forecast available.</p>}
        </Card>
        <Card title="Main risk contributors" className="lg:col-span-2">
          {ok ? <Factors factors={risk!.factors!} /> : <p className="text-sm text-muted">No factors — weather data unavailable.</p>}
        </Card>
      </div>
      {f && (
        <Card title="Recommended next action" action={<button className="btn btn-ghost" onClick={() => a.setView('advisories')}>Full advisory <ArrowRight size={14} /></button>}>
          <ul className="list-disc space-y-1 pl-5 text-sm">{[...f.advisory.inspect, ...f.advisory.actions].slice(0, 3).map((t) => <li key={t}>{t}</li>)}</ul>
        </Card>
      )}
    </div>
  )
}

export function Monitoring({ a }: { a: Agri }) {
  const input = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const r = a.image.result
  const pick = (files: FileList | null) => { if (files?.[0]) a.setFile(files[0]) }
  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-3xl text-forest">Crop monitoring</h1>
        <p className="text-muted">Upload a tomato leaf photo for an AI visual screening.</p>
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Crop & disease focus">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <label className="block"><span className="text-muted">Crop</span>
              <select className="mt-1 w-full rounded-lg border border-line bg-paper p-2" defaultValue="Tomato" aria-label="Crop"><option>Tomato</option></select></label>
            <label className="block"><span className="text-muted">Disease focus</span>
              <select className="mt-1 w-full rounded-lg border border-line bg-paper p-2" defaultValue="Late blight" aria-label="Disease focus"><option>Late blight</option></select></label>
          </div>
          <p className="mt-2 text-xs text-muted">Additional crops are planned. The image model screens 38 classes; non-tomato results are flagged as out of scope.</p>
          <div className="mt-4">
            <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" data-testid="file-input" onChange={(e) => { pick(e.target.files); e.target.value = '' }} />
            {!a.image.previewUrl ? (
              <button type="button" onClick={() => input.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files) }}
                className={`flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed p-10 text-muted ${drag ? 'border-forest bg-sage-50' : 'border-line'}`}>
                <ImagePlus size={32} /><span className="font-medium text-ink">Drop a leaf photo or click to upload</span><span className="text-xs">JPEG, PNG or WebP · up to 8 MB</span>
              </button>
            ) : (
              <div>
                <img src={a.image.previewUrl} alt="Leaf preview" className="max-h-80 w-full rounded-xl object-contain bg-sage-50" />
                <div className="mt-3 flex gap-2">
                  <button className="btn btn-ghost" onClick={() => input.current?.click()}><Replace size={15} /> Replace</button>
                  <button className="btn btn-ghost" onClick={a.removeImage}><Trash2 size={15} /> Remove</button>
                </div>
              </div>
            )}
          </div>
        </Card>
        <Card title="Model result">
          {!a.image.previewUrl && <p className="text-sm text-muted"><Upload className="mb-1 inline" size={16} /> Upload a photo to run EfficientNetV2-S inference.</p>}
          <ImageSummary result={r} error={a.image.error} loading={a.image.loading} />
          {r?.status === 'ok' && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Top 3 predictions</p>
              <ul className="space-y-2">
                {r.top3!.map((t) => (
                  <li key={t.label} className="text-sm">
                    <div className="flex justify-between"><span>{t.crop} — {t.condition}</span><span className="tabular-nums text-muted">{pct(t.score)}</span></div>
                    <div className="mt-1 h-1.5 rounded-full bg-sage-50"><div className="h-1.5 rounded-full bg-forest" style={{ width: pct(t.score) }} /></div>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted">{r.score_note}</p>
            </div>
          )}
          <div className="mt-4 space-y-2">
            <Notice tone="info">The model was trained on clean, lab-style leaf images. Field photos (cluttered backgrounds, uneven light) can be misclassified, so treat results as screening only and confirm in the field.</Notice>
            <p className="text-xs text-muted">Visual severity is not estimated — severity requires field inspection.</p>
          </div>
        </Card>
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

export function WeatherOutlook({ a }: { a: Agri }) {
  const f = a.forecast
  const w = f?.weather
  const off = w?.utc_offset_seconds
  const series = w?.series ?? []
  const place = w?.location?.name ? `${w.location.name}${w.location.country ? `, ${w.location.country}` : ''}` : a.farm?.location
  const coords = w?.location ? `${w.location.lat.toFixed(3)}, ${w.location.lon.toFixed(3)}` : a.farm ? `${a.farm.lat.toFixed(3)}, ${a.farm.lon.toFixed(3)}` : ''
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-forest">Weather outlook</h1>
          <p className="text-muted">{a.farm?.name} · {place} ({coords}) · local time {tzLabel(off)}</p>
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
      {a.error && <Notice tone="error">{a.error}</Notice>}
      {!f && a.loading && <Card><p className="text-sm text-muted">Loading weather for {a.farm?.location}…</p></Card>}
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
        {f.risk.status === 'ok' && <>
          <Card title="Environmental disease-risk trend">
            <RiskTrend risk={f.risk} height={260} offset={off} />
            <p className="mt-2 text-sm">{f.risk.explanation}</p>
            <p className="mt-1 text-xs text-muted">{f.risk.method} The risk method is unchanged in this phase; only the weather source is now real.</p>
          </Card>
          <Card title="Why this score"><Factors factors={f.risk.factors!} /></Card>
        </>}
        <Card title="Forecast table">
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-paper text-left text-muted"><tr><th className="py-1">Local time</th><th>Conditions</th><th>Temp °C</th><th>RH %</th><th>Rain mm</th><th>Rain prob.</th><th>Wind m/s</th></tr></thead>
              <tbody>{series.map((p) => (
                <tr key={p.time} className="border-t border-line tabular-nums">
                  <td className="py-1">{fmtTime(p.time, off)}</td>
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

function report(a: Agri): string {
  const f = a.forecast!
  const r = f.risk, i = a.image.result
  return [
    'AGRISENTRY RISK REPORT', `Generated: ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST`,
    `Farm: ${f.farm.name} (${f.farm.location})`, `Weather data: ${f.weather.label}`, '',
    r.status === 'ok' ? `Environmental favourability: ${r.index}/100 (${r.category})` : 'Environmental favourability: unavailable',
    ...(r.status === 'ok' ? r.factors!.map((x) => `  - ${x.label}: ${x.points}/${x.max_points} — ${x.detail}`) : []),
    '', i?.status === 'ok' ? `Image prediction: ${i.crop} — ${i.condition} (softmax score ${pct(i.score!)}; not a calibrated probability)` : 'Image prediction: none',
    '', `ADVISORY: ${f.advisory.headline}`, f.advisory.what_is_happening, `Why: ${f.advisory.why}`,
    'Inspect:', ...f.advisory.inspect.map((x) => `  - ${x}`), 'Actions:', ...f.advisory.actions.map((x) => `  - ${x}`),
    `Reassess: ${f.advisory.reassess}`, `Consult: ${f.advisory.consult}`, '', f.advisory.severity,
    'Favourable weather does not confirm infection; AI image output is a screening aid, not a diagnosis.',
  ].join('\n')
}

export function Advisories({ a }: { a: Agri }) {
  const f = a.forecast
  const download = () => {
    const url = URL.createObjectURL(new Blob([report(a)], { type: 'text/plain' }))
    const l = document.createElement('a'); l.href = url; l.download = 'agrisentry-report.txt'; l.click(); URL.revokeObjectURL(url)
  }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="font-serif text-3xl text-forest">Field advisories</h1><p className="text-muted">{a.farm?.name} · {a.farm?.location}</p></div>
        <div className="flex items-center gap-2"><DataBadge weather={f?.weather} /><button className="btn btn-primary" onClick={download} disabled={!f}><Download size={15} /> Download report</button></div>
      </div>
      {a.error && <Notice tone="error">{a.error}</Notice>}
      {f && (<>
        <AdvisoryBanner advisory={f.advisory} />
        <div className="grid gap-5 md:grid-cols-2">
          <Card title="Why we are saying this"><p className="text-sm">{f.advisory.why}</p></Card>
          <Card title="What to inspect"><ul className="list-disc space-y-1 pl-5 text-sm">{f.advisory.inspect.map((t) => <li key={t}>{t}</li>)}</ul></Card>
          <Card title="Preventative actions"><ul className="list-disc space-y-1 pl-5 text-sm">{f.advisory.actions.map((t) => <li key={t}>{t}</li>)}</ul></Card>
          <Card title="When to reassess"><p className="text-sm">{f.advisory.reassess}</p><p className="mt-3 text-xs text-muted">{f.advisory.severity}</p></Card>
        </div>
        <Notice tone="warn"><strong>Consult local guidance. </strong>{f.advisory.consult}</Notice>
      </>)}
    </div>
  )
}

export function History({ a }: { a: Agri }) {
  const [data, setData] = useState<{ source: string; persistent: boolean; entries: HistoryEntry[] } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { api.history(a.farmId).then(setData).catch((e) => setErr(e.message)) }, [a.farmId, a.saveMsg, a.image.result])
  return (
    <div className="space-y-5">
      <div><h1 className="font-serif text-3xl text-forest">Assessment history</h1><p className="text-muted">Previous weather-risk assessments and leaf-image checks.</p></div>
      {err && <Notice tone="error">{err}</Notice>}
      {data && data.source === 'synthetic' && <Notice tone="warn">No assessments saved yet. The entries below are <strong>synthetic examples</strong> for demonstration. Use “Save assessment” on the Overview to add real ones.</Notice>}
      {data && data.source === 'session' && <Notice tone="warn">Database not configured — showing this server session's entries only; they are lost on restart.</Notice>}
      <Card>
        <ul className="divide-y divide-line">
          {data?.entries.map((e) => (
            <li key={e.id} className="flex items-start gap-3 py-3">
              <Leaf size={18} className="mt-0.5 text-sage" />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{e.title} {e.synthetic && <span className="ml-1 rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-warn">{e.data_mode === 'synthetic' ? 'synthetic' : 'simulated weather'}</span>}</p>
                <p className="text-sm text-muted">{e.detail}</p>
              </div>
              <span className="shrink-0 text-xs text-muted">{fmtDateTime(e.created_at)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

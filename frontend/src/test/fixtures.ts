/* MOCKED backend responses for component tests — shaped like the real API, not real data. */
import { vi } from 'vitest'

export const farms = [
  { id: 1, name: 'Farm A', location: 'Nashik', lat: 20, lon: 73, crop: 'Tomato', is_seed: true },
  { id: 2, name: 'Farm B', location: 'Kolar', lat: 13, lon: 78, crop: 'Grape', is_seed: true },
]
export const catalog = {
  available: true, version: 'test-model', error: null, weather_model: { Tomato: 'Late blight', Potato: 'Late blight' },
  crops: [
    { crop: 'Tomato', has_healthy_class: true, disease_classes: 2, classes: [
      { index: 30, label: 'Tomato___Late_blight', condition: 'Late blight', healthy: false },
      { index: 29, label: 'Tomato___Early_blight', condition: 'Early blight', healthy: false },
      { index: 37, label: 'Tomato___healthy', condition: 'healthy', healthy: true }] },
    { crop: 'Grape', has_healthy_class: true, disease_classes: 1, classes: [
      { index: 11, label: 'Grape___Black_rot', condition: 'Black rot', healthy: false },
      { index: 14, label: 'Grape___healthy', condition: 'healthy', healthy: true }] },
    { crop: 'Soybean', has_healthy_class: true, disease_classes: 0, classes: [{ index: 24, label: 'Soybean___healthy', condition: 'healthy', healthy: true }] },
  ],
}
const advisory = (headline: string, level = 'info') => ({
  level, headline, crop: 'Tomato', what_is_happening: 'w', why: 'y', inspect: ['look'], actions: ['act'], reassess: 'r', consult: 'c',
  evidence: [{ source: 'image', text: 'No leaf image has been analysed yet.' }, { source: 'weather', text: 'weather text' }, { source: 'severity', text: 'Visual severity is not estimated.' }],
  severity: { available: false, text: 'Visual severity is not estimated.', manual: 'Check 20 plants.' }, references: ['KVK'],
})
export const weatherLive = (name: string, temp: number) => ({
  status: 'live', label: 'Live: OpenWeatherMap', source: 'OpenWeatherMap', fetched_at: '2026-10-11T10:00:00+05:30', observed_at: '2026-10-11T09:55:00+05:30',
  utc_offset_seconds: 19800, location: { name, country: 'IN', lat: 20, lon: 73 },
  current: { time: '2026-10-11T09:55:00+05:30', temp_c: temp, feels_like_c: temp + 2, rh: 61, pressure_hpa: 1009, wind_ms: null, rain_mm: 0, icon: '03d', description: 'scattered clouds', kind: 'observed' },
  series: [{ time: '2026-10-11T09:55:00+05:30', temp_c: temp, rh: 61, rain_mm: 0, pop: null, wind_ms: null, description: 'scattered clouds', kind: 'observed' },
           { time: '2026-10-11T12:30:00+05:30', temp_c: temp - 1, rh: 65, rain_mm: 0.8, pop: 0.4, wind_ms: 2, description: 'light rain', kind: 'forecast' }],
})
const riskOk = (index: number, category: string) => ({
  status: 'ok', index, category, explanation: `scores ${index}/100`, trend: [], peak: null, peak_48h: null, stale: false, favourable_hours_48h: 3,
  intervals: [{ time: '2026-10-11T09:55:00+05:30', hours: 3, favourable: true, kind: 'observed' }],
  factors: [{ key: 'duration', label: 'Favourable-hours run', points: index > 50 ? 50 : 0, max_points: 50, detail: 'd', available: true }],
  rules: { disease: 'Late blight', status: 'Experimental', favourable_interval: '10–27 °C', leaf_wetness_proxy: 'RH ≥ 90 %', window: 'next 12 h', components: [{ key: 'duration', max: 50, rule: 'run' }], categories: 'Low < 25', missing_data: 'skipped' },
})

export interface MockOpts { live?: boolean; holdFarm2?: boolean; weatherError?: boolean }
export let lastForecastBodies: Record<string, unknown>[] = []
export let release: (() => void) | null = null
export const alertsState: { alerts: Record<string, unknown>[] } = { alerts: [] }

export function forecastFor(body: Record<string, unknown>, opts: MockOpts) {
  const farm = farms.find((f) => f.id === body.farm_id) ?? null
  const loc = body.location as { lat: number; lon: number } | undefined
  const crop = (body.crop as string) ?? farm?.crop ?? 'Tomato'
  const hi = body.mode === 'conducive'
  const name = loc ? 'Pune' : farm?.id === 2 ? 'Kolar' : 'Nashik'
  const weather = opts.weatherError
    ? { status: 'unavailable', label: 'x', error: 'OpenWeatherMap rejected the API key (HTTP 401).', hint: 'new keys can take up to 2 hours to activate' }
    : body.mode === 'live' ? weatherLive(name, farm?.id === 2 ? 31.1 : 27.3)
    : { status: 'demo', label: hi ? 'Simulated: disease-conducive' : 'Simulated: normal', fetched_at: '2026-10-11T10:00:00+05:30', utc_offset_seconds: 19800,
        current: { time: '2026-10-11T10:00:00+05:30', temp_c: hi ? 19 : 29, rh: hi ? 93 : 50, rain_mm: 0, kind: 'simulated' },
        series: [{ time: '2026-10-11T10:00:00+05:30', temp_c: 20, rh: 90, rain_mm: 0, kind: 'simulated' }] }
  const risk = crop !== 'Tomato' ? { status: 'not_applicable', reason: `AgriSentry has no validated weather-risk model for ${crop}.` }
    : opts.weatherError ? { status: 'unavailable', reason: 'n/a' } : riskOk(hi ? 88 : 4, hi ? 'Very High' : 'Low')
  return {
    farm, crop, weather, risk, new_alerts: [], saved: null, image_ignored: false,
    place: loc ? { kind: 'location', label: 'Near Pune (current location)', farm_id: null, lat: loc.lat, lon: loc.lon }
      : { kind: 'farm', label: `${farm!.name}, ${farm!.location}`, farm_id: farm!.id, lat: farm!.lat, lon: farm!.lon },
    advisory: advisory(hi ? 'Weather favours late blight – scout your crop' : opts.weatherError ? 'Weather risk unavailable' : 'Routine monitoring', hi ? 'watch' : 'info'),
  }
}

export function installFetch(opts: MockOpts = {}) {
  lastForecastBodies = []
  release = null
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (b: unknown) => ({ ok: true, status: 200, json: async () => b })
    if (url.includes('/api/health')) return ok({ status: 'ok', model: { available: true }, weather: { live_configured: !!opts.live }, database: { mode: 'demo', configured: false, connected: true, persistent: false, backend: 'sqlite' } })
    if (url.includes('/model/classes')) return ok(catalog)
    if (url.includes('/acknowledge')) {
      const id = Number(url.split('/').at(-2))
      const a = alertsState.alerts.find((x) => x.id === id)!
      Object.assign(a, { acknowledged: true, acknowledged_at: '2026-10-11T11:00:00Z' })
      return ok(a)
    }
    if (url.includes('/alerts')) return ok({ persistent: false, unacknowledged: alertsState.alerts.filter((a) => !a.acknowledged).length, alerts: alertsState.alerts })
    if (url.includes('/farms')) return ok(farms)
    if (url.includes('/risk/history')) return ok({ persistent: false, backend: 'sqlite', entries: [] })
    if (url.includes('/diagnose-image')) {
      const crop = (init!.body as FormData).get('crop')
      return ok({ status: 'ok', label: `${crop}___healthy`, crop, condition: 'healthy', healthy: true, score: 0.8, selected_crop: crop, crop_mass: 0.9,
        top3: [{ label: `${crop}___healthy`, crop, condition: 'healthy', healthy: true, score: 0.8 }], unrestricted_top3: [], uncertain: false, latency_ms: 50, model_version: 'test' })
    }
    if (url.includes('/risk/forecast')) {
      const body = JSON.parse(init!.body as string)
      lastForecastBodies.push(body)
      if (opts.holdFarm2 && body.farm_id === 2) await new Promise<void>((r) => { release = r })
      return ok(forecastFor(body, opts))
    }
    return ok({})
  }))
  URL.createObjectURL = vi.fn(() => 'blob:x'); URL.revokeObjectURL = vi.fn()
}

export const rechartsStub = async () => {
  const React = await import('react')
  const Stub = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children)
  return { ResponsiveContainer: Stub, AreaChart: Stub, Area: Stub, ComposedChart: Stub, Bar: Stub, Line: Stub, CartesianGrid: Stub, XAxis: Stub, YAxis: Stub, Tooltip: Stub, Legend: Stub, ReferenceLine: Stub }
}

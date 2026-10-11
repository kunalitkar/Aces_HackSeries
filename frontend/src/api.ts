export type Mode = 'live' | 'normal' | 'conducive'

export interface Farm { id: number; name: string; location: string; lat: number; lon: number; crop: string; is_seed?: boolean }
export interface WeatherPoint {
  time: string
  temp_c: number | null
  rh: number | null
  rain_mm: number | null
  feels_like_c?: number | null
  pressure_hpa?: number | null
  wind_ms?: number | null
  condition?: string | null
  description?: string | null
  icon?: string | null
  pop?: number | null
  kind?: 'observed' | 'forecast' | 'simulated'
}
export interface Weather {
  status: 'live' | 'demo' | 'unavailable'
  label: string
  source?: string
  error?: string
  hint?: string | null
  fetched_at?: string
  observed_at?: string
  utc_offset_seconds?: number
  cached?: boolean
  location?: { name: string | null; country?: string | null; lat: number; lon: number }
  series?: WeatherPoint[]
  current?: WeatherPoint
}
export interface Factor {
  key: string; label: string; points: number; max_points: number; detail: string; available: boolean
  name?: string; value?: number | null; unit?: string; interpretation?: string; why?: string
}
export interface DailyRisk {
  date: string; index: number; category: 'Low' | 'Moderate' | 'High' | 'Very High'; peak_time: string
  main_factor: string | null; main_factor_reading: string; action: string; basis: string; partial: boolean; windows: number
  weather: { temp_min: number | null; temp_max: number | null; rh_mean: number | null; rain_mm: number | null; description: string | null }
}
export interface QualityCheck { key: string; status: 'warn' | 'fail'; value: number; message: string }
export interface Quality { status: 'ok' | 'warn' | 'fail'; checks: QualityCheck[]; note: string; metrics: Record<string, number> }
export interface Region { x: number; y: number; w: number; h: number }
export interface TrendPoint { time: string; index: number; category: string; temp_c: number | null; rh: number | null; rain_mm: number | null }
export interface RiskRules {
  disease: string; status: string; favourable_interval: string; leaf_wetness_proxy: string; window: string
  components: { key: string; max: number; rule: string }[]; categories: string; missing_data: string
}
export interface Risk {
  status: 'ok' | 'unavailable' | 'not_applicable'
  reason?: string
  index?: number
  category?: 'Low' | 'Moderate' | 'High' | 'Very High'
  factors?: Factor[]
  trend?: TrendPoint[]
  peak?: TrendPoint | null
  peak_48h?: TrendPoint | null
  intervals?: { time: string; hours: number; favourable: boolean | null; kind: string }[]
  favourable_hours_48h?: number
  stale?: boolean
  data_age_hours?: number | null
  rules?: RiskRules
  explanation?: string
  method?: string
  coverage?: number
  level_text?: string
  period?: { start: string; end: string; basis: string }
  daily?: DailyRisk[]
}
export interface Advisory {
  level: 'info' | 'watch' | 'warning' | 'alert'
  headline: string
  crop: string
  evidence: { source: 'image' | 'weather' | 'severity'; text: string }[]
  what_is_happening: string
  why: string
  inspect: string[]
  actions: string[]
  reassess: string
  consult: string
  severity: { available: boolean; text: string; manual: string }
  references: string[]
}
export interface Candidate { label: string; crop: string; condition: string; healthy: boolean; score: number }
export interface ImageResult {
  status: 'ok' | 'unavailable' | 'quality_failed'
  quality?: Quality
  region?: Region | null
  quality_override?: boolean
  quality_limited?: boolean
  error?: string
  label?: string
  crop?: string
  condition?: string
  healthy?: boolean
  score?: number
  top3?: Candidate[]
  unrestricted_top3?: Candidate[]
  selected_crop?: string | null
  crop_mass?: number | null
  crop_mismatch?: boolean
  single_class_crop?: boolean
  low_confidence?: boolean
  uncertain?: boolean
  latency_ms?: number
  model_version?: string
  image_ref?: string
  score_note?: string
}
export interface Place { kind: 'farm' | 'location'; label: string; farm_id: number | null; lat: number; lon: number }
export interface Alert {
  id: number; farm_id: number | null; created_at: string; level: 'info' | 'watch' | 'warning' | 'alert'; message: string
  kind: 'weather' | 'image'; explanation: string; location_label: string; category: string | null
  simulated: boolean; acknowledged: boolean; acknowledged_at: string | null
}
export interface Forecast {
  farm: Farm | null; place: Place; crop: string; weather: Weather; risk: Risk; advisory: Advisory
  new_alerts: Alert[]; saved: Assessment | null; image_ignored: boolean
}
export interface Assessment {
  id: number; created_at: string; farm_id: number | null; location_label: string; crop: string; data_mode: string
  simulated: boolean; predicted_label: string | null; confidence: number | null; image_uncertain: boolean | null
  risk_status: string; risk_index: number | null; risk_category: string | null; advisory_level: string
  advisory_headline: string; recommendation: string | null; model_version: string | null
}
export interface CropInfo {
  crop: string; has_healthy_class: boolean; disease_classes: number
  classes: { index: number; label: string; condition: string; healthy: boolean }[]
}
export interface ModelCatalog { available: boolean; version: string; error: string | null; crops: CropInfo[]; weather_model: Record<string, string> }
export interface GeoResult { name: string; state?: string | null; country?: string | null; lat: number; lon: number }
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface ChatReply {
  status: 'ok' | 'unavailable'; reply?: string; error?: string; hint?: string | null; guard_blocked?: boolean
  grounding?: { place: string; crop: string; weather_status: string; risk_level: string | null; image: string | null }
}
export interface Health {
  status: string
  chat?: { configured: boolean; model: string | null }
  model: { available: boolean; error?: string | null; version?: string }
  weather: { live_configured: boolean }
  database: { mode: string; configured: boolean; connected: boolean; persistent: boolean; backend: string | null; error?: string | null }
}

/** A saved farm, or an ad-hoc location (consent-based current position, or a searched place). */
export type Selection =
  | { kind: 'farm'; farmId: number }
  | { kind: 'location'; lat: number; lon: number; label?: string; source: 'gps' | 'search' }

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, init)
  } catch {
    throw new Error('Cannot reach the AgriSentry backend. Is it running on port 8000?')
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const j = await res.json()
      if (j.detail) detail = typeof j.detail === 'string' ? j.detail : j.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const json = (method: string, body: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  health: () => req<Health>('/api/health'),
  farms: () => req<Farm[]>('/api/v1/farms'),
  createFarm: (f: { name: string; location: string; lat: number; lon: number; crop: string }) => req<Farm>('/api/v1/farms', json('POST', f)),
  deleteFarm: (id: number) => req<{ deleted: number }>(`/api/v1/farms/${id}`, { method: 'DELETE' }),
  geocode: (q: string) => req<{ status: string; error: string | null; results: GeoResult[] }>(`/api/v1/geocode?q=${encodeURIComponent(q)}`),
  classes: () => req<ModelCatalog>('/api/v1/model/classes'),
  forecast: (sel: Selection, crop: string | null, mode: Mode, image: ImageResult | null, record = false, refresh = false) =>
    req<Forecast>('/api/v1/risk/forecast', json('POST', {
      ...(sel.kind === 'farm' ? { farm_id: sel.farmId } : { location: { lat: sel.lat, lon: sel.lon, label: sel.label ?? null } }),
      crop, mode, image, record, refresh,
    })),
  diagnose: (file: File, farm_id: number | null, crop: string | null, region: Region | null = null, force = false) => {
    const fd = new FormData()
    fd.append('file', file)
    if (farm_id != null) fd.append('farm_id', String(farm_id))
    if (crop) fd.append('crop', crop)
    if (region) fd.append('region', [region.x, region.y, region.w, region.h].map((v) => v.toFixed(4)).join(','))
    if (force) fd.append('force', 'true')
    return req<ImageResult>('/api/v1/diagnose-image', { method: 'POST', body: fd })
  },
  history: (farm_id: number | null) =>
    req<{ persistent: boolean; backend: string | null; entries: Assessment[] }>(`/api/v1/risk/history${farm_id ? `?farm_id=${farm_id}` : ''}`),
  chat: (messages: ChatMessage[], sel: Selection, crop: string | null, mode: Mode, image: ImageResult | null) =>
    req<ChatReply>('/api/v1/chat', json('POST', {
      messages, crop, mode, image,
      ...(sel.kind === 'farm' ? { farm_id: sel.farmId } : { location: { lat: sel.lat, lon: sel.lon, label: null } }),
    })),
  alerts: () => req<{ persistent: boolean; unacknowledged: number; alerts: Alert[] }>('/api/v1/alerts'),
  acknowledge: (id: number) => req<Alert>(`/api/v1/alerts/${id}/acknowledge`, { method: 'POST' }),
}

// Format an ISO instant in the location's own clock (offset in seconds from the weather payload; default IST).
const DEFAULT_OFFSET = 19800
const shifted = (iso: string, off = DEFAULT_OFFSET) => new Date(new Date(iso).getTime() + off * 1000)
const base: Intl.DateTimeFormatOptions = { timeZone: 'UTC', hour12: false }
export const fmtTime = (iso: string, off?: number) => shifted(iso, off).toLocaleString('en-IN', { ...base, weekday: 'short', hour: '2-digit', minute: '2-digit' })
export const fmtHour = (iso: string, off?: number) => shifted(iso, off).toLocaleTimeString('en-IN', { ...base, hour: '2-digit', minute: '2-digit' })
export const fmtDateTime = (iso: string, off?: number) => shifted(iso, off).toLocaleString('en-IN', { ...base, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
export const tzLabel = (off = DEFAULT_OFFSET) => { const m = Math.abs(off) / 60; return `UTC${off < 0 ? '-' : '+'}${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}` }
export const prettyLabel = (label: string) => label.replace('___', ' – ').replace(/_/g, ' ').replace(',', '').replace(' (including sour)', '').replace(' (maize)', '')

export type Mode = 'live' | 'normal' | 'conducive'

export interface Farm { id: number; name: string; location: string; lat: number; lon: number; crop: string }
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
export interface Factor { key: string; label: string; points: number; max_points: number; detail: string; available: boolean }
export interface TrendPoint { time: string; index: number; category: string; temp_c: number | null; rh: number | null; rain_mm: number | null }
export interface Risk {
  status: 'ok' | 'unavailable'
  reason?: string
  index?: number
  category?: 'Low' | 'Moderate' | 'High' | 'Very High'
  factors?: Factor[]
  trend?: TrendPoint[]
  peak?: TrendPoint | null
  explanation?: string
  method?: string
  coverage?: number
}
export interface Advisory {
  level: 'info' | 'watch' | 'warning' | 'alert'
  headline: string
  what_is_happening: string
  why: string
  inspect: string[]
  actions: string[]
  reassess: string
  consult: string
  severity: string
}
export interface ImageResult {
  status: 'ok' | 'unavailable'
  error?: string
  label?: string
  crop?: string
  condition?: string
  score?: number
  top3?: { label: string; crop: string; condition: string; score: number }[]
  latency_ms?: number
  is_tomato?: boolean
  low_confidence?: boolean
  score_note?: string
}
export interface Forecast { farm: Farm; weather: Weather; risk: Risk; advisory: Advisory }
export interface HistoryEntry { id: string; type: string; created_at: string; title: string; detail: string; synthetic: boolean; data_mode: string }
export interface Health { status: string; model: { available: boolean; error?: string | null }; weather: { live_configured: boolean }; database: { mode: string; configured: boolean; connected: boolean } }

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, init)
  } catch {
    throw new Error('Cannot reach the AgriSentry backend. Is it running on port 8000?')
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try { const j = await res.json(); if (j.detail) detail = String(j.detail) } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => req<Health>('/api/health'),
  farms: () => req<Farm[]>('/api/v1/farms'),
  forecast: (farm_id: number, mode: Mode, image: ImageResult | null, record = false, refresh = false) =>
    req<Forecast>('/api/v1/risk/forecast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ farm_id, mode, image, record, refresh }),
    }),
  diagnose: (file: File, farm_id: number | null) => {
    const fd = new FormData()
    fd.append('file', file)
    if (farm_id != null) fd.append('farm_id', String(farm_id))
    return req<ImageResult>('/api/v1/diagnose-image', { method: 'POST', body: fd })
  },
  history: (farm_id: number | null) =>
    req<{ source: string; persistent: boolean; entries: HistoryEntry[] }>(`/api/v1/risk/history${farm_id ? `?farm_id=${farm_id}` : ''}`),
}

// Format an ISO instant in the location's own clock (offset in seconds from the weather payload; default IST).
const DEFAULT_OFFSET = 19800
const shifted = (iso: string, off = DEFAULT_OFFSET) => new Date(new Date(iso).getTime() + off * 1000)
const base: Intl.DateTimeFormatOptions = { timeZone: 'UTC', hour12: false }
export const fmtTime = (iso: string, off?: number) => shifted(iso, off).toLocaleString('en-IN', { ...base, weekday: 'short', hour: '2-digit', minute: '2-digit' })
export const fmtHour = (iso: string, off?: number) => shifted(iso, off).toLocaleTimeString('en-IN', { ...base, hour: '2-digit', minute: '2-digit' })
export const fmtDateTime = (iso: string, off?: number) => shifted(iso, off).toLocaleString('en-IN', { ...base, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
export const tzLabel = (off = DEFAULT_OFFSET) => { const m = Math.abs(off) / 60; return `UTC${off < 0 ? '-' : '+'}${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}` }

import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Alert, type Farm, type Forecast, type Health, type ImageResult, type Mode, type ModelCatalog, type Region, type Selection } from './api'

export type View = 'overview' | 'monitoring' | 'weather' | 'advisories' | 'history' | 'alerts' | 'chat'
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024

export interface ImageState {
  file: File | null
  previewUrl: string | null
  result: ImageResult | null
  loading: boolean
  error: string | null
  region: Region | null  // user-selected leaf area of the current analysis (null = whole photo)
}
export type GeoState = { status: 'idle' | 'locating' | 'error'; error: string | null }
const emptyImage: ImageState = { file: null, previewUrl: null, result: null, loading: false, error: null, region: null }
const round2 = (n: number) => Math.round(n * 100) / 100

export const geoErrorMessage = (code: number | 'unsupported') => ({
  1: 'Location permission was denied. You can keep using a saved farm or search for a place instead. To allow it later, use the site settings in your browser’s address bar.',
  2: 'Your position could not be determined (no GPS/network location). Choose a farm or search for a place instead.',
  3: 'Finding your location took too long. Try again, or choose a farm or search for a place.',
  unsupported: 'This browser does not support location access. Choose a farm or search for a place instead.',
} as Record<number | string, string>)[code] ?? 'Could not get your location.'

export function useAgri() {
  const [view, setView] = useState<View>('overview')
  const [farms, setFarms] = useState<Farm[]>([])
  const [selection, setSelectionState] = useState<Selection | null>(null)
  const [crop, setCropState] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>('normal')
  const [health, setHealth] = useState<Health | null>(null)
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null)
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [image, setImage] = useState<ImageState>(emptyImage)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [geo, setGeo] = useState<GeoState>({ status: 'idle', error: null })
  const reqId = useRef(0)
  const lastKey = useRef('')
  const imgReq = useRef(0)

  const refreshAlerts = useCallback(() => { api.alerts().then((r) => setAlerts(r.alerts)).catch(() => undefined) }, [])
  const refreshFarms = useCallback(() => api.farms().then((f) => { setFarms(f); return f }), [])

  useEffect(() => {
    refreshFarms().then((f) => { if (f[0]) setSelectionState({ kind: 'farm', farmId: f[0].id }) }).catch((e) => setError(e.message))
    api.health().then((h) => { setHealth(h); if (h.weather.live_configured) setMode('live') }).catch(() => setHealth(null))
    api.classes().then(setCatalog).catch(() => setCatalog(null))
    refreshAlerts()
  }, [refreshFarms, refreshAlerts])

  const farm = selection?.kind === 'farm' ? farms.find((f) => f.id === selection.farmId) ?? null : null
  const activeCrop = crop ?? farm?.crop ?? 'Tomato'

  const clearImage = useCallback(() => {
    imgReq.current++
    setImage((s) => { if (s.previewUrl) URL.revokeObjectURL(s.previewUrl); return emptyImage })
  }, [])

  /** Changing the place always clears the previous place's photo, crop override and weather. */
  const setSelection = useCallback((s: Selection) => {
    setSelectionState(s); setCropState(null); clearImage()
  }, [clearImage])

  const load = useCallback(async (record = false, refresh = false) => {
    if (!selection) return
    const id = ++reqId.current
    const key = JSON.stringify([selection, mode, activeCrop])
    if (key !== lastKey.current) { lastKey.current = key; setForecast(null) }  // never show the previous selection's data
    setLoading(true)
    try {
      const f = await api.forecast(selection, activeCrop, mode, image.result, record, refresh)
      if (id !== reqId.current) return
      setForecast(f); setError(null)
      if (record) setSaveMsg('Assessment saved to history.')
      if (f.new_alerts.length) refreshAlerts()
    } catch (e) {
      if (id === reqId.current) { setError((e as Error).message); setForecast(null) }
    } finally {
      if (id === reqId.current) setLoading(false)
    }
  }, [selection, mode, activeCrop, image.result, refreshAlerts])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (saveMsg) { const t = setTimeout(() => setSaveMsg(null), 3000); return () => clearTimeout(t) } }, [saveMsg])

  const diagnose = useCallback(async (file: File, forCrop: string, region: Region | null = null, force = false) => {
    const id = ++imgReq.current
    setImage((s) => ({ ...s, result: null, error: null, loading: true, region }))
    try {
      const result = await api.diagnose(file, farm?.id ?? null, forCrop, region, force)
      if (id === imgReq.current) setImage((s) => ({ ...s, result, loading: false }))
    } catch (e) {
      if (id === imgReq.current) setImage((s) => ({ ...s, loading: false, error: (e as Error).message }))
    }
  }, [farm?.id])

  const setFile = useCallback((file: File) => {
    const previewUrl = URL.createObjectURL(file)
    setImage((s) => { if (s.previewUrl) URL.revokeObjectURL(s.previewUrl); return { ...emptyImage, file, previewUrl } })
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      imgReq.current++
      setImage((s) => ({ ...s, error: 'Unsupported file type. Please upload a JPEG, PNG or WebP photo.' })); return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      imgReq.current++
      setImage((s) => ({ ...s, error: 'Image is larger than 8 MB. Please upload a smaller photo.' })); return
    }
    diagnose(file, activeCrop)
  }, [activeCrop, diagnose])

  /** Changing crop re-runs the same photo (and selected leaf area) against the new crop's classes. */
  const setCrop = useCallback((c: string) => {
    setCropState(c)
    if (image.file && !image.error) diagnose(image.file, c, image.region)
  }, [image.file, image.error, image.region, diagnose])

  /** Analyse only the leaf area the farmer selected (null = whole photo). The original photo is unchanged. */
  const analyseRegion = useCallback((region: Region | null) => {
    if (image.file) diagnose(image.file, activeCrop, region)
  }, [image.file, activeCrop, diagnose])

  /** Classify a photo that failed the quality check; the result is marked unreliable by the backend. */
  const analyseAnyway = useCallback(() => {
    if (image.file) diagnose(image.file, activeCrop, image.region, true)
  }, [image.file, image.region, activeCrop, diagnose])

  /** Only ever called from an explicit user action after the consent explanation. */
  const requestLocation = useCallback(() => {
    if (!navigator.geolocation) { setGeo({ status: 'error', error: geoErrorMessage('unsupported') }); return }
    setGeo({ status: 'locating', error: null })
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeo({ status: 'idle', error: null })
        setSelection({ kind: 'location', lat: round2(pos.coords.latitude), lon: round2(pos.coords.longitude), source: 'gps' })
      },
      (err) => setGeo({ status: 'error', error: geoErrorMessage(err.code) }),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 },
    )
  }, [setSelection])
  const dismissGeoError = useCallback(() => setGeo({ status: 'idle', error: null }), [])

  const saveLocationAsFarm = useCallback(async (name: string, saveCrop: string, location: string) => {
    if (selection?.kind !== 'location') return
    const f = await api.createFarm({ name, location, lat: selection.lat, lon: selection.lon, crop: saveCrop })
    await refreshFarms()
    setSelection({ kind: 'farm', farmId: f.id })
  }, [selection, refreshFarms, setSelection])

  const acknowledge = useCallback(async (id: number) => {
    const a = await api.acknowledge(id)
    setAlerts((list) => list.map((x) => (x.id === id ? a : x)))
  }, [])

  const selKey = selection ? JSON.stringify([selection, mode, activeCrop]) : ''
  const current = forecast && JSON.stringify([selection, mode, forecast.crop]) === selKey ? forecast : null
  return {
    view, setView, farms, farm, selection, setSelection, refreshFarms, crop: activeCrop, setCrop, mode, setMode, health, catalog,
    forecast: current, loading, error, image, setFile, removeImage: clearImage, reload: load, saveMsg, analyseRegion, analyseAnyway,
    alerts, refreshAlerts, acknowledge, geo, requestLocation, dismissGeoError, saveLocationAsFarm,
    farmId: farm?.id ?? null,
  }
}
export type Agri = ReturnType<typeof useAgri>

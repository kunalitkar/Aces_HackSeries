import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Farm, type Forecast, type Health, type ImageResult, type Mode } from './api'

export type View = 'overview' | 'monitoring' | 'weather' | 'advisories' | 'history'
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024

export interface ImageState {
  file: File | null
  previewUrl: string | null
  result: ImageResult | null
  loading: boolean
  error: string | null
}
const emptyImage: ImageState = { file: null, previewUrl: null, result: null, loading: false, error: null }

export function useAgri() {
  const [view, setView] = useState<View>('overview')
  const [farms, setFarms] = useState<Farm[]>([])
  const [farmId, setFarmId] = useState<number | null>(null)
  const [mode, setMode] = useState<Mode>('normal')
  const [health, setHealth] = useState<Health | null>(null)
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [image, setImage] = useState<ImageState>(emptyImage)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const reqId = useRef(0)
  const lastKey = useRef('')
  const imgReq = useRef(0)

  useEffect(() => {
    api.farms().then((f) => { setFarms(f); setFarmId(f[0]?.id ?? null) }).catch((e) => setError(e.message))
    api.health().then((h) => { setHealth(h); if (h.weather.live_configured) setMode('live') }).catch(() => setHealth(null))
  }, [])

  const load = useCallback(async (record = false, refresh = false) => {
    if (farmId == null) return
    const id = ++reqId.current
    const key = `${farmId}|${mode}`
    if (key !== lastKey.current) { lastKey.current = key; setForecast(null) }  // never show the previous location's weather
    setLoading(true)
    try {
      const f = await api.forecast(farmId, mode, image.result, record, refresh)
      if (id !== reqId.current) return
      setForecast(f); setError(null)
      if (record) setSaveMsg('Assessment saved to history.')
    } catch (e) {
      if (id === reqId.current) { setError((e as Error).message); setForecast(null) }
    } finally {
      if (id === reqId.current) setLoading(false)
    }
  }, [farmId, mode, image.result])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (saveMsg) { const t = setTimeout(() => setSaveMsg(null), 3000); return () => clearTimeout(t) } }, [saveMsg])

  const setFile = useCallback(async (file: File) => {
    if (image.previewUrl) URL.revokeObjectURL(image.previewUrl)
    const previewUrl = URL.createObjectURL(file)
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setImage({ ...emptyImage, file, previewUrl, error: 'Unsupported file type. Please upload a JPEG, PNG or WebP photo.' }); return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImage({ ...emptyImage, file, previewUrl, error: 'Image is larger than 8 MB. Please upload a smaller photo.' }); return
    }
    const id = ++imgReq.current
    setImage({ ...emptyImage, file, previewUrl, loading: true })
    try {
      const result = await api.diagnose(file, farmId)
      if (id === imgReq.current) setImage((s) => ({ ...s, result, loading: false }))
    } catch (e) {
      if (id === imgReq.current) setImage((s) => ({ ...s, loading: false, error: (e as Error).message }))
    }
  }, [farmId, image.previewUrl])

  const removeImage = useCallback(() => {
    imgReq.current++
    if (image.previewUrl) URL.revokeObjectURL(image.previewUrl)
    setImage(emptyImage)
  }, [image.previewUrl])

  const farm = farms.find((f) => f.id === farmId) ?? null
  const current = forecast && forecast.farm.id === farmId ? forecast : null
  return { view, setView, farms, farm, farmId, setFarmId, mode, setMode, health, forecast: current, loading, error, image, setFile, removeImage, reload: load, saveMsg }
}
export type Agri = ReturnType<typeof useAgri>

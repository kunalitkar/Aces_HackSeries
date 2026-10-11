import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, CloudOff, FlaskConical, Radio, ShieldAlert, Info } from 'lucide-react'
import { Area, AreaChart, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { fmtHour, fmtTime, type Advisory, type Factor, type Risk, type Weather, type WeatherPoint } from './api'

export const CAT_COLOR: Record<string, string> = { Low: '#3f7d52', Moderate: '#b7791f', High: '#c2410c', 'Very High': '#9f1239' }
const LEVEL_STYLE: Record<Advisory['level'], { bg: string; fg: string; icon: ReactNode }> = {
  info: { bg: 'bg-sage-50', fg: 'text-forest', icon: <CheckCircle2 size={18} /> },
  watch: { bg: 'bg-amber-50', fg: 'text-amber-warn', icon: <Info size={18} /> },
  warning: { bg: 'bg-amber-50', fg: 'text-amber-warn', icon: <AlertTriangle size={18} /> },
  alert: { bg: 'bg-alert-50', fg: 'text-alert', icon: <ShieldAlert size={18} /> },
}

export function Card({ title, action, children, className = '' }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function DataBadge({ weather }: { weather: Weather | null | undefined }) {
  if (!weather) return null
  const m = {
    live: { cls: 'bg-sage-50 text-forest', icon: <Radio size={13} />, t: 'LIVE DATA' },
    demo: { cls: 'bg-amber-50 text-amber-warn', icon: <FlaskConical size={13} />, t: 'SIMULATED DEMO DATA' },
    unavailable: { cls: 'bg-alert-50 text-alert', icon: <CloudOff size={13} />, t: 'WEATHER UNAVAILABLE' },
  }[weather.status]
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${m.cls}`}>{m.icon}{m.t}</span>
}

export function Gauge({ index, category }: { index: number; category: string }) {
  const color = CAT_COLOR[category]
  const r = 62, c = Math.PI * r
  return (
    <div className="flex flex-col items-center" role="img" aria-label={`Risk favourability index ${index} out of 100, ${category}`}>
      <svg viewBox="0 0 150 90" className="w-56">
        <path d="M13 80 A62 62 0 0 1 137 80" fill="none" stroke="#e6e0d2" strokeWidth="13" strokeLinecap="round" />
        <path d="M13 80 A62 62 0 0 1 137 80" fill="none" stroke={color} strokeWidth="13" strokeLinecap="round" strokeDasharray={`${(index / 100) * c} ${c}`} />
        <text x="75" y="68" textAnchor="middle" fontSize="30" fontWeight="700" fill="#1f2a24">{Math.round(index)}</text>
        <text x="75" y="84" textAnchor="middle" fontSize="9" fill="#66705f">/ 100</text>
      </svg>
      <span className="-mt-1 rounded-full px-3 py-1 text-sm font-semibold text-white" style={{ background: color }}>{category}</span>
    </div>
  )
}

export function Factors({ factors }: { factors: Factor[] }) {
  return (
    <ul className="space-y-3">
      {factors.map((f) => (
        <li key={f.key}>
          <div className="flex justify-between text-sm">
            <span className="font-medium">{f.label}{!f.available && <span className="ml-2 text-xs text-alert">(data missing)</span>}</span>
            <span className="tabular-nums text-muted">{f.points.toFixed(1)} / {f.max_points}</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-sage-50"><div className="h-2 rounded-full bg-forest" style={{ width: `${(f.points / f.max_points) * 100}%` }} /></div>
          <p className="mt-1 text-xs text-muted">{f.detail}</p>
        </li>
      ))}
    </ul>
  )
}

export function RiskTrend({ risk, height = 240, offset }: { risk: Risk; height?: number; offset?: number }) {
  const data = (risk.trend ?? []).map((t) => ({ ...t, label: fmtTime(t.time, offset) }))
  return (
    <div style={{ height }} aria-label="Forecast favourability trend chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <defs><linearGradient id="rg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#1f4d3a" stopOpacity={0.35} /><stop offset="100%" stopColor="#1f4d3a" stopOpacity={0.03} /></linearGradient></defs>
          <CartesianGrid stroke="#e6e0d2" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#66705f' }} interval="preserveStartEnd" minTickGap={40} />
          <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fontSize: 11, fill: '#66705f' }} />
          <ReferenceLine y={25} stroke="#b7791f" strokeDasharray="3 3" /><ReferenceLine y={50} stroke="#c2410c" strokeDasharray="3 3" /><ReferenceLine y={75} stroke="#9f1239" strokeDasharray="3 3" />
          <Tooltip formatter={(v) => [`${Number(v).toFixed(0)} / 100`, 'Favourability']} />
          <Area type="monotone" dataKey="index" stroke="#1f4d3a" strokeWidth={2} fill="url(#rg)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function WeatherChart({ series, height = 280, offset }: { series: WeatherPoint[]; height?: number; offset?: number }) {
  const data = series.map((p) => ({ ...p, label: fmtTime(p.time, offset) }))
  return (
    <div style={{ height }} aria-label="Weather forecast chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 0, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="#e6e0d2" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#66705f' }} interval="preserveStartEnd" minTickGap={40} />
          <YAxis yAxisId="l" tick={{ fontSize: 11, fill: '#66705f' }} />
          <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11, fill: '#66705f' }} />
          <Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar yAxisId="r" dataKey="rain_mm" name="Rain (mm)" fill="#8fae8b" barSize={6} isAnimationActive={false} />
          <Line yAxisId="l" type="monotone" dataKey="temp_c" name="Temp (°C)" stroke="#b7791f" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line yAxisId="l" type="monotone" dataKey="rh" name="Humidity (%)" stroke="#1f4d3a" strokeWidth={2} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export function AdvisoryBanner({ advisory }: { advisory: Advisory }) {
  const s = LEVEL_STYLE[advisory.level]
  return (
    <div className={`flex items-start gap-3 rounded-xl p-4 ${s.bg}`}>
      <span className={`mt-0.5 ${s.fg}`}>{s.icon}</span>
      <div>
        <p className={`font-semibold ${s.fg}`}>{advisory.headline}</p>
        <p className="mt-1 text-sm text-ink">{advisory.what_is_happening}</p>
      </div>
    </div>
  )
}

export function Notice({ tone = 'warn', children }: { tone?: 'warn' | 'error' | 'info'; children: ReactNode }) {
  const cls = { warn: 'bg-amber-50 text-amber-warn', error: 'bg-alert-50 text-alert', info: 'bg-sage-50 text-forest' }[tone]
  return <div role={tone === 'error' ? 'alert' : undefined} className={`rounded-xl px-4 py-3 text-sm ${cls}`}>{children}</div>
}

export const CurrentStats = ({ p }: { p: WeatherPoint }) => (
  <div className="grid grid-cols-3 gap-3 text-center">
    {[['Temperature', p.temp_c, '°C'], ['Humidity', p.rh, '%'], ['Rain', p.rain_mm, ' mm']].map(([l, v, u]) => (
      <div key={l as string} className="rounded-xl bg-sage-50 p-3">
        <p className="text-xs text-muted">{l}</p>
        <p className="text-xl font-semibold tabular-nums">{v == null ? '—' : `${Math.round(Number(v) * 10) / 10}${u}`}</p>
      </div>
    ))}
  </div>
)

export { fmtHour }

import { fmtDateTime, type Forecast } from './api'
import type { Agri } from './useAgri'

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)
const list = (items: string[]) => `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join('')}</ul>`

/** Self-contained printable crop-health report built only from the current assessment. */
export function reportHtml(a: Agri, f: Forecast): string {
  const r = f.risk, w = f.weather, i = a.image.result, adv = f.advisory
  const now = new Date().toISOString()
  const cur = w.current
  const weather = cur
    ? `${esc(w.label)}. Now: ${cur.temp_c ?? 'n/a'} °C, RH ${cur.rh ?? 'n/a'} %, rain ${cur.rain_mm ?? 'n/a'} mm${w.observed_at ? ` (observed ${fmtDateTime(w.observed_at, w.utc_offset_seconds)})` : ''}.`
    : `Unavailable: ${esc(w.error ?? '')}`
  const risk = r.status === 'ok'
    ? `<p><strong>${r.index}/100 — ${r.category}</strong> (late blight, next 12 h; experimental, not a probability of infection)</p>
       <table><tr><th>Factor</th><th>Points</th><th>Detail</th></tr>${r.factors!.map((x) => `<tr><td>${esc(x.label)}</td><td>${x.points}/${x.max_points}</td><td>${esc(x.detail)}</td></tr>`).join('')}</table>
       <p>${esc(r.explanation ?? '')}</p>`
    : `<p>${esc(r.reason ?? 'Unavailable')}</p>`
  const image = i?.status === 'ok'
    ? `<p><strong>${esc(i.crop!)} — ${esc(i.condition!)}</strong>, model score ${Math.round(i.score! * 100)}%${i.uncertain ? ' (uncertain)' : ''}. ${esc(i.score_note ?? '')}</p><p class="m">Model: ${esc(i.model_version ?? '')}</p>`
    : '<p>No leaf image analysed.</p>'
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>AgriSentry report — ${esc(f.place.label)}</title>
<style>body{font:14px/1.5 system-ui,sans-serif;color:#1f2a24;max-width:760px;margin:24px auto;padding:0 16px}h1{color:#1f4d3a;font-family:Georgia,serif;margin-bottom:0}
h2{font-size:15px;text-transform:uppercase;letter-spacing:.04em;color:#66705f;border-bottom:1px solid #e6e0d2;padding-bottom:4px;margin-top:22px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #e6e0d2;padding:4px 6px;text-align:left;vertical-align:top}.m{color:#66705f;font-size:12px}
.b{padding:10px 12px;border-radius:8px;background:#fbf1dc}</style></head><body>
<h1>AgriSentry crop-health report</h1><p class="m">Generated ${esc(now)} · ${esc(f.place.label)} · crop: ${esc(f.crop)} · data: ${esc(w.status)}</p>
<div class="b"><strong>${esc(adv.headline)}</strong><br>${esc(adv.what_is_happening)}</div>
<h2>Weather</h2><p>${weather}</p>
<h2>Environmental risk</h2>${risk}
<h2>Leaf image</h2>${image}
<h2>Severity</h2><p>${esc(adv.severity.text)} ${esc(adv.severity.manual)}</p>
<h2>Advisory</h2><p><strong>Inspect:</strong></p>${list(adv.inspect)}<p><strong>Preventive steps:</strong></p>${list(adv.actions)}
<p><strong>Reassess:</strong> ${esc(adv.reassess)}</p><p><strong>Consult:</strong> ${esc(adv.consult)}</p>${list(adv.references)}
<h2>Limitations</h2><p class="m">AgriSentry is a decision-support prototype. Weather favourability does not confirm infection. The image model was trained on lab images and is less accurate on field photos; its score is not a calibrated probability. Visual severity is not measured.${w.status === 'demo' ? ' <strong>This report uses SIMULATED weather.</strong>' : ''}</p>
</body></html>`
}

export function printReport(a: Agri, f: Forecast) {
  const win = window.open('', '_blank')
  if (!win) { downloadReport(a, f); return }  // popup blocked: fall back to a file
  win.document.write(reportHtml(a, f))
  win.document.close()
  win.focus()
  win.print()
}

export function downloadReport(a: Agri, f: Forecast) {
  const url = URL.createObjectURL(new Blob([reportHtml(a, f)], { type: 'text/html' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `agrisentry-report-${new Date().toISOString().slice(0, 10)}.html`
  link.click()
  URL.revokeObjectURL(url)
}

"""Write the series review page from pool.py's output: python series_page.py POOL.json OUT.html

One block per series of the real panel (original coordinates): the source's own daily count, dollars and ticket
size over its whole history; one strip per detector showing the days it flagged; the verdicts already in
reviewed.yaml; and the pooled candidates with a suggested verdict. The reviewer confirms or changes candidates, marks
any other stretch on the chart (click: last day, shift-click: first day), and ticks the series off as fully reviewed:
on a reviewed series every unmarked day counts as confirmed fine, which is what lets the grader score misses.

Verdicts go to the artifact's database: `spans` (one document per marked stretch: ticker, source_id, start, end,
verdict real / change / not_real / recurring / unsure, note; a change runs from start, and returns after end unless
end == start, when it lasts) and `series` (ticker-source: reviewed). Publish with
capabilities {db: {}}; read them back with ArtifactData into reviewed.yaml.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import yaml

HERE = pathlib.Path(__file__).resolve().parent
SMALL_K = 6.0
THIN_CT = 20      # build.THIN_CT: thinner stretches are not scored, so not reviewed


def suggest(c: dict, s: dict) -> tuple[str, str]:
    """A suggested verdict from the reviewer's standing rules (feedback log #11-12)."""
    a, b = pd.Timestamp(c['start']), pd.Timestamp(c['end'])
    if (b - a).days + 1 > 7:
        return 'review', 'a sustained move: judge it on the chart'
    for yrs in (1, 2):
        lo, hi = a - pd.DateOffset(years=yrs) - pd.Timedelta(days=7), b - pd.DateOffset(years=yrs) + pd.Timedelta(days=7)
        past = [x for x in s.get('_flag_dates', []) if lo <= x <= hi]
        if past:
            return 'recurring', f'flagged at the same time {yrs} year{"s" if yrs > 1 else ""} earlier ({past[0].date()})'
    if c['own_z'] < SMALL_K and len(c['detectors']) <= 1:
        return 'not_real', f'one detector only, and {c["own_z"]}x the source\'s own noise (under {SMALL_K:g}x)'
    if c['own_z'] < SMALL_K and (c.get('peer_z') or 0) < SMALL_K:
        return 'not_real', 'within the source\'s own noise and close to the other sources'
    return 'review', f'{len(c["detectors"])} detector{"s" if len(c["detectors"]) > 1 else ""}, {c["own_z"]}x own noise'


def main():
    pool = json.loads(pathlib.Path(sys.argv[1]).read_text())
    rev = (yaml.safe_load((HERE / 'reviewed.yaml').read_text()) or {}).get('reviewed') or []
    by = {(s['ticker'], s['source_id']): s for s in pool['series']}
    for s in pool['series']:
        idx = sorted({i for k in ('own_point', 'peer_point') for i in s['flags'].get(k, [])})   # strong one-day moves only
        s['_flag_dates'] = [pd.Timestamp(s['dates'][i]) for i in idx]
    for s in pool['series']:                       # thin stretches (28-day median count under THIN_CT): not scored
        ct = pd.Series(s['ct'], dtype=float)
        thin = (ct.rolling(28, min_periods=1, center=True).median() < THIN_CT).to_numpy()
        s['thin'] = [i for i, t in enumerate(thin) if t]
    thin_days = {(s['ticker'], s['source_id']): {s['dates'][i] for i in s['thin']} for s in pool['series']}
    dropped = [c for c in pool['candidates'] if all(
        d in thin_days[(c['ticker'], c['source_id'])] for d in pd.date_range(c['start'], c['end']).strftime('%Y-%m-%d'))]
    pool['candidates'] = [c for c in pool['candidates'] if c not in dropped]
    print(len(dropped), 'candidates dropped: entirely on thin stretches')
    for c in pool['candidates']:
        c['suggest'], c['why'] = suggest(c, by[(c['ticker'], c['source_id'])])
    for s in pool['series']:
        s.pop('_flag_dates')
    known = [dict(ticker=r['ticker'], source_id=int(r['source_id']), start=str(r['start']), end=str(r['end']),
                  verdict=r['verdict']) for r in rev]
    data = dict(detectors=pool['detectors'], series=pool['series'], candidates=pool['candidates'], known=known)
    blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    pathlib.Path(sys.argv[2]).write_text(PAGE.replace('__DATA__', blob))
    n = pd.Series([c['suggest'] for c in pool['candidates']]).value_counts().to_dict()
    print(len(pool['series']), 'series,', len(pool['candidates']), 'candidates; suggested:', n)


PAGE = r"""<title>Series Review</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: a sticky series picker, then one series at a time: its chart with detector strips, then its candidates */
:root {
  --bg: #f6f7f5; --panel: #ffffff; --ink: #1b1f1d; --muted: #5d6762; --line: #dfe3e0;
  --count: #2a6fb8; --ticket: #b0601f; --flag: #c23b3b; --bad: rgba(194, 59, 59, .16); --fine: rgba(93, 103, 98, .14);
  --rec: rgba(42, 111, 184, .14); --sel: #2f7a50; --focus: #2a6fb8; --thin: rgba(93, 103, 98, .22);
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121513; --panel: #1a1e1c; --ink: #e6ebe8; --muted: #9aa49f; --line: #2c322f;
  --count: #6aa6e6; --ticket: #e0965a; --flag: #ef7171; --bad: rgba(239, 113, 113, .2); --fine: rgba(154, 164, 159, .16);
  --rec: rgba(106, 166, 230, .18); --sel: #7fd0a2; --focus: #6aa6e6; --thin: rgba(154, 164, 159, .2); color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121513; --panel: #1a1e1c; --ink: #e6ebe8; --muted: #9aa49f; --line: #2c322f;
  --count: #6aa6e6; --ticket: #e0965a; --flag: #ef7171; --bad: rgba(239, 113, 113, .2); --fine: rgba(154, 164, 159, .16);
  --rec: rgba(106, 166, 230, .18); --sel: #7fd0a2; --focus: #6aa6e6; --thin: rgba(154, 164, 159, .2); color-scheme: dark }
body { background: var(--bg); color: var(--ink); font: 15px/1.5 var(--sans); }
.wrap { max-width: 980px; margin: 0 auto; padding-block: 24px 64px; padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 16px; }
h1 { font-size: 26px; margin: 0; font-weight: 600; }
.lede { color: var(--muted); margin: 0; max-width: 72ch; }
.picker { display: flex; flex-wrap: wrap; gap: 6px; position: sticky; top: env(safe-area-inset-top, 0px); background: var(--bg); padding-block: 8px; z-index: 5; }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); background: var(--bg); z-index: 10; }
.picker button, .btn { font: 500 13px var(--sans); border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 6px; padding: 5px 10px; cursor: pointer; }
.picker button[aria-pressed="true"] { border-color: var(--ink); }
.picker button.done::after { content: " ✓"; color: var(--sel); }
button:focus-visible, textarea:focus-visible, input:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; display: grid; gap: 12px; min-width: 0; }
.row { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; }
.meta { font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
svg { width: 100%; height: auto; display: block; cursor: crosshair; }
svg text { font: 11px var(--mono); fill: var(--muted); }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--muted); }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { text-align: left; padding: 6px 6px; border-top: 1px solid var(--line); vertical-align: top; }
th { font-weight: 600; color: var(--muted); font-size: 12px; }
td.num { font: 12px var(--mono); white-space: nowrap; }
.tbl { overflow-x: auto; }
.vbtn { font: 500 12px var(--sans); border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 5px; padding: 3px 7px; cursor: pointer; margin: 1px; }
.vbtn[aria-pressed="true"] { background: var(--ink); color: var(--panel); border-color: var(--ink); }
.sugg { color: var(--muted); font-size: 12px; }
.status { font-size: 13px; color: var(--muted); min-height: 1.4em; }
.selbox { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 14px; }
.selbox input { font: 13px var(--mono); color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 3px 6px; }
.hint { font-size: 12px; color: var(--muted); }
</style>

<div class="wrap">
  <header style="display:grid;gap:6px">
    <h1>Series Review</h1>
    <p class="lede">Label the real data once. Every task is built from these 20 series, so a verdict here applies to all
    of them. Each series shows its own history, the days each detector flagged, and the candidates they raised with a
    suggestion from your rules. Confirm or change the suggestions, mark anything else on the chart, then tick the series
    as reviewed: on a reviewed series every unmarked day counts as fine, so the grader can score what a model missed.</p>
  </header>
  <div class="picker" id="picker" role="group" aria-label="Series"></div>
  <div class="status" id="status" role="status">Connecting to saved verdicts…</div>
  <div id="view"></div>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const NS = 'http://www.w3.org/2000/svg';
const $ = (s, e = document) => e.querySelector(s);
const V = { real: 'Bad', change: 'Level change', not_real: 'Fine', recurring: 'Recurs yearly', unsure: 'Unsure' };
const st = { cur: 0, spans: {}, series: {}, sel: null, zoom: 'all', db: null, lastYear: true };
function minus364(d) { const t = new Date(d + 'T00:00:00Z'); t.setUTCDate(t.getUTCDate() - 364); return t.toISOString().slice(0, 10); }
const key = s => `${s.ticker}-${s.source_id}`;
function el(t, a = {}, p) { const e = document.createElementNS(NS, t); for (const [k, v] of Object.entries(a)) e.setAttribute(k, v); if (p) p.appendChild(e); return e; }
function setStatus(t) { $('#status').textContent = t; }

function spansFor(s) {
  const out = D.known.filter(k => k.ticker === s.ticker && k.source_id === s.source_id).map(k => ({ ...k, saved: 'reviewed.yaml' }));
  for (const [id, v] of Object.entries(st.spans)) if (v.ticker === s.ticker && v.source_id === s.source_id && v.verdict) out.push({ ...v, id });
  return out;
}

function chart(s, wrap) {
  const W = 940, L = 78, R = 8, PH = 70, GAP = 10, STRIP = 11;
  let i0 = 0, i1 = s.dates.length - 1;
  if (st.zoom !== 'all') { const y = st.zoom; i0 = s.dates.findIndex(d => d.startsWith(y)); i1 = s.dates.length - 1 - [...s.dates].reverse().findIndex(d => d.startsWith(y)); }
  const n = i1 - i0 + 1, x = i => L + (W - L - R) * (i - i0) / Math.max(1, n - 1);
  const dets = D.detectors, top3 = 4, H = top3 + 3 * (PH + GAP) + dets.length * STRIP + 26;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `${s.ticker} source ${s.source_id}: count, dollars and ticket size, with detector flags` });
  const tkt = s.ct.map((c, i) => (c && s.amt[i]) ? s.amt[i] / c : null);
  const bands = spansFor(s);
  const panels = [['Count', s.ct, 'var(--count)'], ['Dollars', s.amt, 'var(--ticket)'], ['Ticket size ($)', tkt, 'var(--ticket)']];
  const yOf = i => s.dates[i];
  const idxOf = d => { let i = s.dates.indexOf(d); if (i < 0) i = s.dates.findIndex(z => z >= d); return i < 0 ? s.dates.length - 1 : i; };
  panels.forEach(([title, v, col], k) => {
    const top = top3 + k * (PH + GAP) + 14, ph = PH - 14;
    for (const b of bands) {
      const a = Math.max(idxOf(b.start), i0), e = Math.min(idxOf(b.end), i1); if (e < i0 || a > i1) continue;
      if (b.verdict === 'change') { el('line', { x1: x(a), x2: x(a), y1: top, y2: top + ph, stroke: 'var(--flag)', 'stroke-width': 2 }, svg);
        if (b.end !== b.start) el('line', { x1: x(e), x2: x(e), y1: top, y2: top + ph, stroke: 'var(--flag)', 'stroke-width': 2, 'stroke-dasharray': '3 2' }, svg); continue; }
      el('rect', { x: x(a) - 1, y: top, width: Math.max(2, x(e) - x(a) + 2), height: ph, fill: b.verdict === 'real' ? 'var(--bad)' : b.verdict === 'recurring' ? 'var(--rec)' : 'var(--fine)' }, svg);
    }
    for (const i of s.thin) if (i >= i0 && i <= i1) el('rect', { x: x(i) - 0.6, y: top, width: Math.max(1.2, (W - L - R) / n + 0.2), height: ph, fill: 'var(--thin)' }, svg);
    if (st.sel) { const a = Math.max(idxOf(st.sel[0]), i0), e = Math.min(idxOf(st.sel[1]), i1);
      if (e >= i0 && a <= i1) el('rect', { x: x(a) - 1, y: top, width: Math.max(2, x(e) - x(a) + 2), height: ph, fill: 'none', stroke: 'var(--sel)', 'stroke-width': 1.5, 'stroke-dasharray': '4 2' }, svg); }
    // last year, shifted 364 days so weekdays line up: the value the same source reported 52 weeks earlier
    const di = s._di || (s._di = new Map(s.dates.map((d, i) => [d, i])));
    const prev = st.lastYear ? s.dates.map(d => { const j = di.get(minus364(d)); return j === undefined ? null : v[j]; }) : null;
    const vals = v.slice(i0, i1 + 1).concat(prev ? prev.slice(i0, i1 + 1) : []).filter(z => z !== null);
    const lo = Math.max(0, Math.min(...vals)), hi = Math.max(...vals);
    const y = z => top + ph - (z - lo) / ((hi - lo) || 1) * ph;
    let d = ''; for (let i = i0; i <= i1; i++) { const z = v[i]; if (z === null) continue; d += (d && v[i - 1] !== null ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(z).toFixed(1); }
    if (prev) { let pd = ''; for (let i = i0; i <= i1; i++) { const z = prev[i]; if (z === null) { continue; } pd += (pd && prev[i - 1] !== null ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(z).toFixed(1); }
      el('path', { d: pd, fill: 'none', stroke: 'var(--muted)', 'stroke-width': 1, 'stroke-dasharray': '2 2', opacity: 0.8 }, svg); }
    el('path', { d, fill: 'none', stroke: col, 'stroke-width': 1, 'stroke-linejoin': 'round' }, svg);
    const t = el('text', { x: L, y: top - 3 }, svg); t.textContent = title;
    const fmt = z => z >= 1e6 ? (z / 1e6).toFixed(1) + 'M' : z >= 1e3 ? (z / 1e3).toFixed(1) + 'k' : z.toFixed(0);
    [[hi, top + 9], [lo, top + ph]].forEach(([z, yy]) => { const tt = el('text', { x: L - 5, y: yy, 'text-anchor': 'end' }, svg); tt.textContent = fmt(z); });
  });
  const sTop = top3 + 3 * (PH + GAP);
  dets.forEach((dn, k) => {
    const yy = sTop + k * STRIP;
    const t = el('text', { x: L - 5, y: yy + 8, 'text-anchor': 'end', style: 'font-size:10px' }, svg); t.textContent = dn.replace('_', ' ');
    el('line', { x1: L, x2: W - R, y1: yy + 4, y2: yy + 4, stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    for (const i of s.flags[dn]) if (i >= i0 && i <= i1) el('rect', { x: x(i) - 0.8, y: yy, width: 1.6, height: 7, fill: 'var(--flag)' }, svg);
  });
  const ax = H - 4; const ticks = [i0]; for (let i = i0 + 1; i <= i1; i++) if (s.dates[i].slice(0, 7) !== s.dates[i - 1].slice(0, 7) && (st.zoom !== 'all' || s.dates[i].slice(5, 7) === '01')) ticks.push(i);
  let lx = -99; for (const i of ticks) { if (x(i) - lx < 48) continue; lx = x(i); const t = el('text', { x: x(i), y: ax, 'text-anchor': 'middle' }, svg); t.textContent = st.zoom === 'all' ? s.dates[i].slice(0, 4) : s.dates[i].slice(0, 7); }
  svg.addEventListener('click', e => {
    const r = svg.getBoundingClientRect(), vx = (e.clientX - r.left) / r.width * W;
    const d = yOf(Math.max(i0, Math.min(i1, Math.round(i0 + (vx - L) / (W - L - R) * (n - 1)))));
    const [a, b] = st.sel || [d, d];
    st.sel = e.shiftKey ? (d <= b ? [d, b] : [b, d]) : (d >= a ? [a, d] : [d, a]);
    if (!st.selStarted) { st.sel = [d, d]; st.selStarted = true; }
    show();
  });
  wrap.appendChild(svg);
}

async function saveSpan(id, doc) {
  st.spans[id] = { ...(st.spans[id] || {}), ...doc, updated_at: new Date().toISOString() }; show();
  if (!st.db) { setStatus('Not saved: open the page on claude.ai while signed in.'); return; }
  try { await st.db.collection('spans').doc(id).set(st.spans[id]); setStatus('Saved.'); } catch (e) { setStatus('Not saved. Try again in a moment.'); }
}
async function saveSeries(k, reviewed) {
  st.series[k] = { reviewed, updated_at: new Date().toISOString() }; show();
  if (!st.db) return;
  try { await st.db.collection('series').doc(k).set(st.series[k]); setStatus('Saved.'); } catch (e) { setStatus('Not saved. Try again in a moment.'); }
}

function render() { show(); }
function show() {
  const pk = $('#picker'); pk.textContent = '';
  D.series.forEach((s, i) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = `${s.ticker}·${s.source_id}`;
    b.setAttribute('aria-pressed', String(i === st.cur)); if ((st.series[key(s)] || {}).reviewed) b.className = 'done';
    b.addEventListener('click', () => { st.cur = i; st.sel = null; st.selStarted = false; st.zoom = 'all'; show(); window.scrollTo(0, 0); }); pk.appendChild(b); });
  const s = D.series[st.cur], v = $('#view'); v.textContent = '';
  const p = document.createElement('section'); p.className = 'panel';
  const cands = D.candidates.filter(c => c.ticker === s.ticker && c.source_id === s.source_id);
  const head = document.createElement('div'); head.className = 'row';
  head.innerHTML = '<h2 style="margin:0;font-size:19px"></h2><span class="meta"></span>';
  $('h2', head).textContent = `${s.ticker} · source ${s.source_id}`;
  $('.meta', head).textContent = `${s.industry} · ${s.dates[0]} to ${s.dates[s.dates.length - 1]} · ${cands.length} candidates`;
  p.appendChild(head);
  const z = document.createElement('div'); z.className = 'row';
  const years = [...new Set(s.dates.map(d => d.slice(0, 4)))];
  const ly = document.createElement('button'); ly.type = 'button'; ly.className = 'btn'; ly.textContent = st.lastYear ? 'Hide last year' : 'Show last year';
  ly.addEventListener('click', () => { st.lastYear = !st.lastYear; show(); });
  for (const y of ['all', ...years]) { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = y === 'all' ? 'All years' : y;
    b.setAttribute('aria-pressed', String(st.zoom === y)); if (st.zoom === y) b.style.borderColor = 'var(--ink)';
    b.addEventListener('click', () => { st.zoom = y; show(); }); z.appendChild(b); }
  z.appendChild(ly);
  p.appendChild(z);
  const cw = document.createElement('div'); chart(s, cw); p.appendChild(cw);
  const lg = document.createElement('div'); lg.className = 'legend';
  lg.innerHTML = `<span><i class="sw" style="background:var(--count)"></i>count</span><span><i class="sw" style="background:var(--ticket)"></i>dollars, ticket size</span><span><i class="sw" style="background:transparent;border-top:2px dotted var(--muted);height:0"></i>same source 364 days earlier</span><span><i class="sw" style="background:var(--flag)"></i>a detector flagged that day</span><span><i class="sw" style="background:var(--bad)"></i>marked bad</span><span><i class="sw" style="background:var(--fine)"></i>marked fine</span><span><i class="sw" style="background:var(--rec)"></i>recurs yearly</span><span><i class="sw" style="background:var(--thin)"></i>too thin to trust (under 20 a day): not scored</span><span><i class="sw" style="background:transparent;border-left:2px solid var(--flag)"></i>level change starts (dashed: returns)</span><span><i class="sw" style="outline:1.5px dashed var(--sel);outline-offset:-2px"></i>your selection</span>`;
  p.appendChild(lg);
  const sb = document.createElement('div'); sb.className = 'selbox';
  if (st.sel) {
    sb.innerHTML = '<span>Selected</span><input type="date" id="sa"><span>to</span><input type="date" id="sb2">';
    $('#sa', sb).value = st.sel[0]; $('#sb2', sb).value = st.sel[1];
    $('#sa', sb).addEventListener('change', e => { st.sel = [e.target.value, st.sel[1]].sort(); show(); });
    $('#sb2', sb).addEventListener('change', e => { st.sel = [st.sel[0], e.target.value].sort(); show(); });
    for (const k of ['real', 'change', 'not_real', 'recurring', 'unsure']) { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = k === 'change' ? 'Level change: starts on the first day, returns after the last (same day: lasts)' : `Mark ${V[k].toLowerCase()}`;
      b.addEventListener('click', () => { saveSpan(`${key(s)}-${st.sel[0]}-${st.sel[1]}`, { ticker: s.ticker, source_id: s.source_id, start: st.sel[0], end: st.sel[1], verdict: k }); st.sel = null; st.selStarted = false; }); sb.appendChild(b); }
    const c = document.createElement('button'); c.type = 'button'; c.className = 'btn'; c.textContent = 'Clear selection'; c.addEventListener('click', () => { st.sel = null; st.selStarted = false; show(); }); sb.appendChild(c);
  } else sb.innerHTML = '<span class="hint">Click the chart to start a selection, click again to set its end (shift-click sets the start), then mark it. Use it for anything no detector caught.</span>';
  p.appendChild(sb);
  // candidates
  const tw = document.createElement('div'); tw.className = 'tbl';
  const tb = document.createElement('table');
  tb.innerHTML = '<thead><tr><th>Dates</th><th>Detectors</th><th>Size</th><th>Suggested</th><th>Your verdict</th></tr></thead><tbody></tbody>';
  const order = { review: 0, recurring: 1, not_real: 2 };
  for (const c of [...cands].sort((a, b) => order[a.suggest] - order[b.suggest] || b.own_z - a.own_z)) {
    const tr = document.createElement('tr'); const sv = (st.spans[c.id] || {}).verdict;
    tr.innerHTML = '<td class="num"></td><td></td><td class="num"></td><td class="sugg"></td><td></td>';
    tr.children[0].textContent = c.start === c.end ? c.start : `${c.start} → ${c.end}`;
    tr.children[1].textContent = Object.entries(c.detectors).map(([k, n]) => `${k.replace('_', ' ')}${n > 1 ? ' ×' + n : ''}`).join(', ');
    tr.children[2].textContent = `${c.own_move_pct > 0 ? '+' : ''}${c.own_move_pct}% · ${c.own_z}× own` + (c.peer_z != null ? ` · ${c.peer_z}× vs others` : '');
    tr.children[3].textContent = (c.suggest === 'review' ? 'Look: ' : V[c.suggest] + ': ') + c.why;
    for (const k of ['real', 'change', 'not_real', 'recurring', 'unsure']) { const b = document.createElement('button'); b.type = 'button'; b.className = 'vbtn'; b.textContent = V[k];
      b.setAttribute('aria-pressed', String(sv === k));
      if (k === 'change') b.title = 'A lasting change from the first day (the detectors\' last day is kept as when it settled). To mark a return, select the stretch on the chart.';
      b.addEventListener('click', () => saveSpan(c.id, { ticker: c.ticker, source_id: c.source_id, start: c.start, end: c.end, verdict: sv === k ? null : k, candidate: true })); tr.children[4].appendChild(b); }
    const go = document.createElement('button'); go.type = 'button'; go.className = 'vbtn'; go.textContent = 'Show';
    go.addEventListener('click', () => { st.zoom = c.start.slice(0, 4); st.sel = [c.start, c.end]; st.selStarted = true; show(); });
    tr.children[4].appendChild(go);
    tb.tBodies[0].appendChild(tr);
  }
  tw.appendChild(tb); p.appendChild(tw);
  // every stretch you have marked on this series (from the table or the chart), each with an undo
  const mine = Object.entries(st.spans).filter(([, m]) => m.ticker === s.ticker && m.source_id === s.source_id && m.verdict)
    .sort((a, b) => a[1].start.localeCompare(b[1].start));
  const saved = D.known.filter(k => k.ticker === s.ticker && k.source_id === s.source_id);
  if (mine.length || saved.length) {
    const box = document.createElement('div'); box.className = 'tbl';
    const t2 = document.createElement('table');
    t2.innerHTML = '<thead><tr><th>Your marks on this series</th><th>Verdict</th><th></th></tr></thead><tbody></tbody>';
    for (const [id, m] of mine) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td class="num"></td><td></td><td></td>';
      tr.children[0].textContent = m.start === m.end ? m.start : `${m.start} → ${m.end}`;
      tr.children[1].textContent = V[m.verdict] + (m.candidate ? '' : ' (marked on the chart)');
      const show = document.createElement('button'); show.type = 'button'; show.className = 'vbtn'; show.textContent = 'Show';
      show.addEventListener('click', () => { st.zoom = m.start.slice(0, 4); st.sel = [m.start, m.end]; st.selStarted = true; window.scrollTo(0, 0); render(); });
      const undo = document.createElement('button'); undo.type = 'button'; undo.className = 'vbtn'; undo.textContent = 'Undo';
      undo.addEventListener('click', () => saveSpan(id, { verdict: null, undone: true }));
      tr.children[2].append(show, undo);
      t2.tBodies[0].appendChild(tr);
    }
    for (const k of saved) {
      const tr = document.createElement('tr'); tr.innerHTML = '<td class="num"></td><td></td><td class="sugg"></td>';
      tr.children[0].textContent = k.start === k.end ? k.start : `${k.start} → ${k.end}`;
      tr.children[1].textContent = (V[k.verdict] || k.verdict);
      tr.children[2].textContent = 'already in the grader (an earlier review): to undo it, mark the same days again here, or ask Claude';
      t2.tBodies[0].appendChild(tr);
    }
    box.appendChild(t2); p.appendChild(box);
  }
  const fin = document.createElement('div'); fin.className = 'row';
  const sugOpen = cands.filter(c => c.suggest !== 'review' && !(st.spans[c.id] || {}).verdict);
  if (sugOpen.length) { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn';
    b.textContent = `Accept the ${sugOpen.length} suggested verdict${sugOpen.length > 1 ? 's' : ''}`;
    b.addEventListener('click', async () => { for (const c of sugOpen) await saveSpan(c.id, { ticker: c.ticker, source_id: c.source_id, start: c.start, end: c.end, verdict: c.suggest, candidate: true, accepted_suggestion: true }); });
    fin.appendChild(b); }
  const lab = document.createElement('label'); lab.className = 'row'; const cb = document.createElement('input'); cb.type = 'checkbox'; cb.id = 'rev-' + key(s);
  cb.checked = !!(st.series[key(s)] || {}).reviewed; cb.addEventListener('change', () => saveSeries(key(s), cb.checked));
  lab.append(cb, ' I have reviewed this whole series: every unmarked day is fine'); fin.appendChild(lab);
  p.appendChild(fin);
  v.appendChild(p);
}

show();
(async () => {
  const db = window.claude && await window.claude.use('db');
  if (!db) { setStatus('Verdicts can be chosen but not saved here: open the page on claude.ai while signed in.'); return; }
  st.db = db;
  const timer = setTimeout(() => setStatus('Saved verdicts can\'t be reached yet.'), 10000);
  db.collection('spans').onSnapshot(sn => { clearTimeout(timer); if (!sn.metadata.fromCache) setStatus(''); const o = {}; sn.docs.forEach(d => o[d.id] = d.data()); st.spans = o; show(); },
    e => { clearTimeout(timer); setStatus('Saved verdicts are unavailable.'); });
  db.collection('series').onSnapshot(sn => { const o = {}; sn.docs.forEach(d => o[d.id] = d.data()); st.series = o; show(); }, () => {});
})();
</script>
"""


if __name__ == '__main__':
    main()

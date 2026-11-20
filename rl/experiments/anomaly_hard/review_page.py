"""Write the review page for review_items.py's output: python review_page.py ITEMS.json OUT.html

The page shows each unexplained alert against its company's other sources and takes a verdict (real: data is bad on
the days marked; too_long: worth flagging but flagged too long, with the days that were bad; not_real; unsure), the
bad days as bad_start/bad_end, and a note, kept in the artifact's database (collection `verdicts`, one document per item id), plus one
note on anything missed (`notes/missed`). Publish OUT.html with capabilities {db: {}}; read the verdicts back with
ArtifactData and write them to reviewed.yaml.
"""
from __future__ import annotations

import json
import pathlib
import sys

PAGE = r"""<title>Flag Review</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: one review column; each alert is a card with its chart and a verdict row */
:root {
  --bg: #f6f7f5; --panel: #ffffff; --ink: #1b1f1d; --muted: #5d6762; --line: #dfe3e0;
  --count: #2a6fb8; --ticket: #b0601f; --flag: #c23b3b; --span: rgba(194, 59, 59, .10);
  --known: rgba(60, 130, 90, .16); --known-ink: #2f7a50;
  --real: #2f7a50; --toolong: #2b6f86; --notreal: #8a3b3b; --unsure: #8a6d1f; --focus: #2a6fb8; --badspan: #2f7a50;
  --clean: #7a4fc4; --run: rgba(176, 120, 20, .14); --acc: #2f7a50;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121513; --panel: #1a1e1c; --ink: #e6ebe8; --muted: #9aa49f; --line: #2c322f;
  --count: #6aa6e6; --ticket: #e0965a; --flag: #ef7171; --span: rgba(239, 113, 113, .14);
  --known: rgba(110, 200, 150, .16); --known-ink: #7fd0a2;
  --real: #7fd0a2; --toolong: #7cc6dd; --notreal: #ef8f8f; --unsure: #e3c06a; --focus: #6aa6e6; --badspan: #7fd0a2;
  --clean: #b79bf0; --run: rgba(227, 192, 106, .16); --acc: #7fd0a2; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121513; --panel: #1a1e1c; --ink: #e6ebe8; --muted: #9aa49f; --line: #2c322f;
  --count: #6aa6e6; --ticket: #e0965a; --flag: #ef7171; --span: rgba(239, 113, 113, .14);
  --known: rgba(110, 200, 150, .16); --known-ink: #7fd0a2;
  --real: #7fd0a2; --toolong: #7cc6dd; --notreal: #ef8f8f; --unsure: #e3c06a; --focus: #6aa6e6; --badspan: #7fd0a2;
  --clean: #b79bf0; --run: rgba(227, 192, 106, .16); --acc: #7fd0a2; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font: 15px/1.5 var(--sans); }
.wrap { max-width: 920px; margin: 0 auto; padding-block: 28px 64px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 20px; }
h1 { font-size: 26px; font-weight: 600; margin: 0; text-wrap: balance; }
.lede { color: var(--muted); margin: 0; max-width: 68ch; }
.bar { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
.counts { font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.filters { display: flex; flex-wrap: wrap; gap: 6px; }
.filters button, .verdict button { font: 500 13px var(--sans); border: 1px solid var(--line); background: var(--panel);
  color: var(--ink); border-radius: 6px; padding: 6px 12px; cursor: pointer; }
.filters button[aria-pressed="true"] { border-color: var(--ink); }
button:focus-visible, textarea:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.status { font-size: 13px; color: var(--muted); min-height: 1.5em; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; display: grid; gap: 10px; min-width: 0; }
.card.done { border-left: 4px solid var(--muted); }
.card[data-v="real"] { border-left-color: var(--real); }
.card[data-v="not_real"] { border-left-color: var(--notreal); }
.card[data-v="unsure"] { border-left-color: var(--unsure); }
.card[data-v="too_long"] { border-left-color: var(--toolong); }
.verdict button[aria-pressed="true"][data-v="too_long"] { background: var(--toolong); border-color: var(--toolong); color: var(--panel); }
.span { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; font-size: 14px; }
.span input { font: 14px var(--mono); color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 4px 6px; }
.span .hint { font-size: 12px; color: var(--muted); }
.chart svg.pick { cursor: crosshair; }
.span[hidden] { display: none; }
.zoom { display: flex; gap: 6px; align-items: center; font-size: 13px; color: var(--muted); }
.zoom button { font: 500 12px var(--sans); border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 6px; padding: 3px 9px; cursor: pointer; }
.zoom button[aria-pressed="true"] { border-color: var(--ink); }
.head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; align-items: baseline; }
.head h2 { font-size: 17px; margin: 0; font-weight: 600; }
.meta { font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.known { font-size: 13px; color: var(--known-ink); }
.why { margin: 0; padding: 10px 12px; background: var(--bg); border-radius: 6px; display: grid; gap: 6px; list-style: none; }
.why li { font-size: 14px; line-height: 1.45; max-width: 80ch; }
.why .who { font: 12px var(--mono); color: var(--muted); display: block; }
svg { width: 100%; height: auto; display: block; }
svg text { font: 11px var(--mono); fill: var(--muted); }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--muted); }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
.verdict { display: flex; flex-wrap: wrap; gap: 6px; }
.verdict button[aria-pressed="true"][data-v="real"] { background: var(--real); border-color: var(--real); color: var(--panel); }
.verdict button[aria-pressed="true"][data-v="not_real"] { background: var(--notreal); border-color: var(--notreal); color: var(--panel); }
.verdict button[aria-pressed="true"][data-v="unsure"] { background: var(--unsure); border-color: var(--unsure); color: var(--panel); }
textarea { width: 100%; box-sizing: border-box; font: 14px var(--sans); color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 6px; padding: 8px; resize: vertical; min-height: 2.6em; }
.missed { display: grid; gap: 6px; }
.missed label { font-weight: 600; }
.saved { font-size: 12px; color: var(--muted); }
</style>

<div class="wrap">
  <header style="display:grid;gap:8px">
    <h1>Flag Review</h1>
    <p class="lede">Each card is a run of flagged days that the grader does not count as bad data, with why the scorer
    flagged it. Decide whether the source data is really off there. <b>Data is bad</b> and <b>Worth flagging, but
    flagged too long</b> both ask for the days that really were bad: only those become bad data in every task, and flags
    outside them stay false alarms. <b>Data is fine</b> keeps the whole run a false alarm; <b>Unsure</b> leaves it
    unscored.</p>
    <p class="lede">A change that lasts is graded as a time series monitor sees it: the first two weeks of a change, and
    of the return to normal, are bad data; after about six weeks the new level is the normal level, so flags there are
    false alarms. Top panels: the source against the median of the company's other sources (log units). Bottom
    panels: this source's own daily count and dollars, on an axis fitted to its range.</p>
  </header>
  <div class="bar">
    <div class="filters" role="group" aria-label="Show">
      <button type="button" data-f="todo" aria-pressed="true">To review</button>
      <button type="button" data-f="all" aria-pressed="false">All</button>
      <button type="button" data-f="real" aria-pressed="false">Data is bad</button>
      <button type="button" data-f="too_long" aria-pressed="false">Flagged too long</button>
      <button type="button" data-f="not_real" aria-pressed="false">False alarm</button>
      <button type="button" data-f="unsure" aria-pressed="false">Unsure</button>
    </div>
    <span class="counts" id="counts"></span>
  </div>
  <div class="status" id="status" role="status">Connecting to the saved verdicts…</div>
  <section class="missed card">
    <label for="missed-note">Anything the scorer missed</label>
    <span class="saved">Problems you can see in these charts (or know of) that were not flagged: ticker, source, dates.</span>
    <textarea id="missed-note" rows="3" placeholder="e.g. DAL source 2, 2016-03-01 to 2016-04-15, count drops but no flags"></textarea>
    <span class="saved" id="missed-saved"></span>
  </section>
  <div id="list" style="display:grid;gap:16px"></div>
</div>

<script type="application/json" id="items">__ITEMS__</script>
<script>
const ITEMS = JSON.parse(document.getElementById('items').textContent);
const state = { verdicts: {}, filter: 'todo', db: null };
const $ = (s, el = document) => el.querySelector(s);
const NS = 'http://www.w3.org/2000/svg';
const LABEL = { real: 'Data is bad on these days', too_long: 'Worth flagging, but flagged too long',
  not_real: 'Data is fine (false alarm)', unsure: 'Unsure' };
const SPAN = new Set(['real', 'too_long']);

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

function chart(it, v) {
  const c = it.chart, W = 720, L = 52, R = 8, panelH = 104, gap = 18, T = 4, HEAD = 18;
  const panels = [
    { title: 'Count vs other sources (log ratio)', lines: [[c.count, 'var(--count)', 1.5]], flags: c.count },
    { title: 'Ticket size vs other sources (log ratio)', lines: [[c.ticket, 'var(--ticket)', 1.5]], flags: c.ticket },
    { title: 'Daily count, this source alone', plain: true, raw: c.raw.ct, color: 'var(--count)' },
    { title: 'Daily dollars, this source alone', plain: true, raw: c.raw.amt, color: 'var(--ticket)' },
  ];
  for (const p of panels) if (p.raw) {
    p.lines = [[p.raw[c.source], p.color, 1.6, 1]];
    p.flags = p.raw[c.source];
  }
  const H = T + panels.length * (panelH + gap) + 6;
  const n = c.dates.length, x = i => L + (W - L - R) * (n <= 1 ? 0 : i / (n - 1));
  const idx = d => { let i = c.dates.indexOf(d); if (i < 0) i = c.dates.findIndex(z => z >= d); return i < 0 ? n - 1 : i; };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': `${it.ticker} source ${it.source_id}: count and ticket size against other sources, and the daily count and dollars of every source, ${c.dates[0]} to ${c.dates[n - 1]}` });
  const fmt = v => Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : Math.abs(v) >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : v.toFixed(v < 10 ? 2 : 0);
  panels.forEach((p, k) => {
    const top0 = T + k * (panelH + gap), top = top0 + HEAD, ph = panelH - HEAD, tf = v => p.log ? Math.log10(Math.max(v, 0.01)) : v;
    const vals = p.lines.flatMap(([v]) => v.filter(z => z !== null).map(tf));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (!p.log && !p.plain) { lo = Math.min(lo, -0.2); hi = Math.max(hi, 0.2); }
    if (p.plain) { const pad = (hi - lo) * 0.05; lo -= pad; hi += pad; }
    if (hi - lo < 1e-9) { hi += 0.5; lo -= 0.5; }
    const y = v => top + ph - (tf(v) - lo) / (hi - lo) * ph;
    for (const kn of c.known) {
      const a = x(idx(kn.start)), b = x(idx(kn.end));
      el('rect', { x: a - 2, y: top, width: Math.max(4, b - a + 4), height: ph, fill: 'var(--known)' }, svg);
    }
    const a = x(idx(it.start)), b = x(idx(it.end));
    el('rect', { x: a - 2, y: top, width: Math.max(4, b - a + 4), height: ph, fill: 'var(--span)' }, svg);
    if (v && SPAN.has(v.verdict) && v.bad_start && v.bad_end) {
      const p0 = x(idx(v.bad_start)), p1 = x(idx(v.bad_end));
      el('rect', { x: p0 - 2, y: top + 1, width: Math.max(4, p1 - p0 + 4), height: ph - 2, fill: 'none',
        stroke: 'var(--badspan)', 'stroke-width': 2, 'stroke-dasharray': '5 3' }, svg);
    }
    if (!p.log && !p.plain) el('line', { x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    for (const v of [lo, hi]) {
      const t = el('text', { x: L - 6, y: top + ph - (v - lo) / (hi - lo) * ph + (v === hi ? 9 : -2), 'text-anchor': 'end' }, svg);
      t.textContent = p.log ? fmt(10 ** v) : p.plain ? fmt(v) : v.toFixed(2);
    }
    const tt = el('text', { x: L, y: top0 + 12 }, svg); tt.textContent = p.title;
    for (const [v, color, w, op] of p.lines) {
      let d = '';
      v.forEach((z, i) => { if (z === null) return; d += (d && v[i - 1] !== null ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(z).toFixed(1); });
      el('path', { d, fill: 'none', stroke: color, 'stroke-width': w, 'stroke-opacity': op ?? 1, 'stroke-linejoin': 'round' }, svg);
    }
    c.flags.forEach((f, i) => { if (f && p.flags[i] !== null) el('circle', { cx: x(i), cy: y(p.flags[i]), r: 2.6, fill: 'var(--flag)' }, svg); });
  });
  svg.dateAt = clientX => {
    const r = svg.getBoundingClientRect(), vx = (clientX - r.left) / r.width * W;
    return c.dates[Math.max(0, Math.min(n - 1, Math.round((vx - L) / (W - L - R) * (n - 1))))];
  };
  const base = H - 2;
  [0, Math.floor((n - 1) / 2), n - 1].forEach((i, j) => {
    const t = el('text', { x: x(i), y: base, 'text-anchor': ['start', 'middle', 'end'][j] }, svg); t.textContent = c.dates[i];
  });
  return svg;
}

const ZOOM = new Set();   // cards shown at the last 120 days (per viewer, not saved)
function zoomed(it) {
  const c = it.chart;
  if (!ZOOM.has(it.id) || c.dates.length <= 120) return c;
  const i0 = c.dates.length - 120, cut = a => a.slice(i0);
  return { ...c, dates: cut(c.dates), flags: cut(c.flags), panels: c.panels.map(p => ({ ...p,
    lines: p.lines.map(l => ({ ...l, v: cut(l.v) })), runs: p.runs && cut(p.runs), accepted: p.accepted && cut(p.accepted) })) };
}

const COLOR = { count: 'var(--count)', ticket: 'var(--ticket)', muted: 'var(--muted)', clean: 'var(--clean)', ink: 'var(--ink)' };

// The scorer's own workings over the full history it had seen when it set the alert (trace_scorer.py)
function algoChart(it, v) {
  const c = zoomed(it), W = 720, L = 52, R = 8, panelH = 96, gap = 14, T = 4, HEAD = 18, AX = 16;
  const n = c.dates.length, x = i => L + (W - L - R) * (n <= 1 ? 0 : i / (n - 1));
  const idx = d => { let i = c.dates.indexOf(d); if (i < 0) i = c.dates.findIndex(z => z >= d); return i < 0 ? n - 1 : i; };
  const H = T + c.panels.length * (panelH + gap) + AX;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': `${it.ticker} source ${it.source_id}: the scorer's count and ticket-size model, residuals, drift evidence and confidence, ${c.dates[0]} to ${c.dates[n - 1]}` });
  const fmt = v => Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : Math.abs(v) >= 1e3 ? (v / 1e3).toFixed(1) + 'k' : Math.abs(v) >= 10 ? v.toFixed(0) : v.toFixed(2);
  c.panels.forEach((p, k) => {
    const top0 = T + k * (panelH + gap), top = top0 + HEAD, ph = panelH - HEAD;
    const clip = z => (z === null ? null : p.clip ? Math.max(-p.clip, Math.min(p.clip, z)) : z);
    const vals = p.lines.flatMap(l => l.v.filter(z => z !== null).map(clip)).concat(p.hlines || []);
    let lo = p.lo ?? Math.min(...vals), hi = p.hi ?? Math.max(...vals);
    if (p.floor !== undefined) lo = Math.min(lo, p.floor);
    if (p.lo === undefined) { const pad = (hi - lo) * 0.05 || 0.5; lo -= pad; hi += pad; }
    if (p.positive) lo = Math.max(lo, 0);
    const y = z => top + ph - (clip(z) - lo) / (hi - lo) * ph;
    if (p.runs) p.runs.forEach((r, i) => { if (r) el('rect', { x: x(i) - 0.6, y: top, width: Math.max(1.2, (W - L - R) / n + 0.2), height: ph, fill: 'var(--run)' }, svg); });
    for (const kn of c.known) {
      if (kn.marker) { const a = x(idx(kn.start)); el('line', { x1: a, x2: a, y1: top, y2: top + ph, stroke: 'var(--known-ink)', 'stroke-width': 1, 'stroke-dasharray': '2 2' }, svg); continue; }
      const a = x(idx(kn.start)), b = x(idx(kn.end));
      el('rect', { x: a - 1, y: top, width: Math.max(2, b - a + 2), height: ph, fill: 'var(--known)' }, svg);
    }
    const a = x(idx(it.start)), b = x(idx(it.end));
    el('rect', { x: a - 2, y: top, width: Math.max(4, b - a + 4), height: ph, fill: 'var(--span)' }, svg);
    if (v && SPAN.has(v.verdict) && v.bad_start && v.bad_end) {
      const p0 = x(idx(v.bad_start)), p1 = x(idx(v.bad_end));
      el('rect', { x: p0 - 2, y: top + 1, width: Math.max(4, p1 - p0 + 4), height: ph - 2, fill: 'none', stroke: 'var(--badspan)', 'stroke-width': 2, 'stroke-dasharray': '5 3' }, svg);
    }
    if (p.zero && lo < 0 && hi > 0) el('line', { x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    for (const hl of p.hlines || []) el('line', { x1: L, x2: W - R, y1: y(hl), y2: y(hl), stroke: 'var(--flag)', 'stroke-width': 1, 'stroke-dasharray': '4 3', opacity: 0.7 }, svg);
    for (const val of [lo, hi]) {
      const t = el('text', { x: L - 6, y: top + ph - (val - lo) / (hi - lo) * ph + (val === hi ? 9 : -2), 'text-anchor': 'end' }, svg);
      t.textContent = fmt(val);
    }
    const tt = el('text', { x: L, y: top0 + 12 }, svg); tt.textContent = p.title;
    for (const l of p.lines) {
      let d = '';
      l.v.forEach((z, i) => { if (z === null) return; d += (d && l.v[i - 1] !== null ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(z).toFixed(1); });
      const at = { d, fill: 'none', stroke: COLOR[l.color] || l.color, 'stroke-width': l.w, 'stroke-linejoin': 'round' };
      if (l.dash) at['stroke-dasharray'] = '3 2';
      el('path', at, svg);
    }
    if (p.accepted) p.accepted.forEach((acc, i) => { if (acc && (i === 0 || !p.accepted[i - 1])) {
      el('line', { x1: x(i), x2: x(i), y1: top, y2: top + ph, stroke: 'var(--acc)', 'stroke-width': 1.5 }, svg);
      const t = el('text', { x: x(i) + 3, y: top + 9 }, svg); t.textContent = 'new normal accepted'; } });
    const first = p.lines[0].v;
    c.flags.forEach((f, i) => { if (f && first[i] !== null) el('circle', { cx: x(i), cy: y(first[i]), r: 1.9, fill: 'var(--flag)' }, svg); });
  });
  // date axis: first day, each 1 January, last day
  const ticks = [0];
  c.dates.forEach((d, i) => { if (i > 0 && d.slice(0, 4) !== c.dates[i - 1].slice(0, 4)) ticks.push(i); });
  ticks.push(n - 1);
  let lastX = -99;
  ticks.forEach((i, j) => {
    const xx = x(i); if (xx - lastX < 52 && j !== ticks.length - 1) return; lastX = xx;
    const t = el('text', { x: xx, y: H - 3, 'text-anchor': j === 0 ? 'start' : j === ticks.length - 1 ? 'end' : 'middle' }, svg);
    t.textContent = j === 0 || j === ticks.length - 1 ? c.dates[i] : c.dates[i].slice(0, 4);
  });
  svg.dateAt = clientX => {
    const r = svg.getBoundingClientRect(), vx = (clientX - r.left) / r.width * W;
    return c.dates[Math.max(0, Math.min(n - 1, Math.round((vx - L) / (W - L - R) * (n - 1))))];
  };
  return svg;
}

function card(it) {
  const v = state.verdicts[it.id] || {};
  const div = document.createElement('article');
  div.className = 'card' + (v.verdict ? ' done' : ''); if (v.verdict) div.dataset.v = v.verdict;
  const days = it.start === it.end ? it.start : `${it.start} to ${it.end}`;
  div.innerHTML = `<div class="head"><h2></h2><span class="meta"></span></div>
    <div class="meta days"></div><div class="known"></div><ul class="why" aria-label="Why it was flagged"></ul><div class="chart"></div>
    <div class="legend"><span><i class="sw" style="background:var(--count)"></i>count</span>
      <span><i class="sw" style="background:var(--ticket)"></i>ticket size, dollars</span>
      <span><i class="sw" style="background:var(--flag)"></i>flagged day</span>
      <span><i class="sw" style="background:var(--span)"></i>this alert</span>
      <span><i class="sw" style="background:var(--known)"></i>planted problem or real event in the window</span>
      <span><i class="sw" style="background:transparent;outline:2px dashed var(--badspan);outline-offset:-2px"></i>days you marked bad</span></div>
    <div class="verdict" role="group"></div>
    <div class="span" hidden><span>Bad from</span><input type="date" class="s0" aria-label="First bad day"><span>to</span>
      <input type="date" class="s1" aria-label="Last bad day"><span class="hint">Click the chart to set the last bad day; shift-click sets the first. Flags outside these days count as false alarms.</span></div>
    <textarea rows="2" placeholder="Note (optional): what you see, or the dates if the real problem spans different days"></textarea>
    <span class="saved"></span>`;
  $('h2', div).textContent = `${it.ticker} · source ${it.source_id}`;
  $('.head .meta', div).textContent = `${it.flagged_days} flagged day${it.flagged_days === 1 ? '' : 's'} · in ${it.tasks.length} of 4 tasks` + (it.by && it.by.filter(Boolean).length ? ` · flagged by ${it.by.filter(Boolean).join(' and ')}` : '');
  $('.days', div).textContent = days + (it.chart.algo ? `  ·  history shown: ${it.chart.dates[0]} to ${it.chart.dates[it.chart.dates.length - 1]}, everything the scorer had seen when it set this alert` : `  ·  ${it.chart.sources} sources`);
  $('.known', div).textContent = it.chart.known.length ? 'In this window: ' + it.chart.known.map(k => `${k.kind.replace('decoy:', 'real event (decoy): ')} ${k.start}`).join('; ') : '';
  const why = $('.why', div);
  for (const p of it.parts || []) {
    if (!p.why) continue;
    const li = document.createElement('li'), who = document.createElement('span');
    who.className = 'who';
    who.textContent = `${p.by.replace('-run', ' run')} · task ${p.task.replace('anomhard-', '')} · ${p.start === p.end ? p.start : p.start + ' to ' + p.end}`;
    li.append(who, document.createTextNode(p.why));
    why.appendChild(li);
  }
  if (!why.children.length) why.remove();
  const svg = it.chart.algo ? algoChart(it, v) : chart(it, v);
  if (it.chart.algo) {
    const z = document.createElement('div'); z.className = 'zoom';
    z.append('Show: ');
    for (const [lab, on] of [['Full history', false], ['Last 120 days', true]]) {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = lab;
      b.setAttribute('aria-pressed', String(ZOOM.has(it.id) === on));
      b.addEventListener('click', () => { on ? ZOOM.add(it.id) : ZOOM.delete(it.id); render(); });
      z.append(b);
    }
    $('.chart', div).before(z);
  }
  if (it.chart.algo) div.querySelector('.legend').innerHTML = `<span><i class="sw" style="background:var(--count)"></i>count</span>
      <span><i class="sw" style="background:var(--ticket)"></i>dollars, ticket size</span>
      <span><i class="sw" style="background:transparent;border-top:2px dashed var(--muted);height:0"></i>model's expected value</span>
      <span><i class="sw" style="background:var(--clean)"></i>cleaned value (where it differs)</span>
      <span><i class="sw" style="background:var(--flag)"></i>distrusted day / a threshold</span>
      <span><i class="sw" style="background:var(--span)"></i>this alert</span>
      <span><i class="sw" style="background:var(--run)"></i>in a shift run</span>
      <span><i class="sw" style="background:var(--known)"></i>planted problem (dashed line: company-wide real event)</span>
      <span><i class="sw" style="background:transparent;outline:2px dashed var(--badspan);outline-offset:-2px"></i>days you marked bad</span>`;
  $('.chart', div).appendChild(svg);
  const vb = $('.verdict', div); vb.setAttribute('aria-label', `Verdict for ${it.ticker} source ${it.source_id}`);
  for (const key of ['real', 'too_long', 'not_real', 'unsure']) {
    const b = document.createElement('button'); b.type = 'button'; b.dataset.v = key; b.textContent = LABEL[key];
    b.setAttribute('aria-pressed', String(v.verdict === key));
    b.addEventListener('click', () => {
      if (v.verdict === key) return save(it, { verdict: null });
      const patch = { verdict: key };
      if (SPAN.has(key) && !(v.bad_start && v.bad_end)) {
        patch.bad_start = it.start;
        patch.bad_end = key === 'real' ? it.end : it.start;   // too long: start from the first day, then widen
      }
      save(it, patch);
    });
    vb.appendChild(b);
  }
  if (SPAN.has(v.verdict)) {
    const row = $('.span', div), s0 = $('.s0', row), s1 = $('.s1', row);
    row.hidden = false;
    const lo = it.chart.dates[0], hi = it.chart.dates[it.chart.dates.length - 1];
    for (const inp of [s0, s1]) { inp.min = lo; inp.max = hi; }
    s0.id = 's0-' + it.id; s1.id = 's1-' + it.id;
    s0.value = v.bad_start || it.start; s1.value = v.bad_end || it.end;
    const fix = (a, b) => a <= b ? [a, b] : [b, a];
    s0.addEventListener('change', () => { const [a, b] = fix(s0.value, s1.value); save(it, { bad_start: a, bad_end: b }); });
    s1.addEventListener('change', () => { const [a, b] = fix(s0.value, s1.value); save(it, { bad_start: a, bad_end: b }); });
    svg.classList.add('pick');
    svg.addEventListener('click', e => {
      const d = svg.dateAt(e.clientX), cur0 = v.bad_start || it.start, cur1 = v.bad_end || it.end;
      const [a, b] = e.shiftKey ? fix(d, cur1) : fix(cur0, d);
      save(it, { bad_start: a, bad_end: b });
    });
  }
  const ta = $('textarea', div); ta.id = 'note-' + it.id; ta.value = v.note || '';
  ta.addEventListener('change', () => save(it, { note: ta.value.trim() }));
  return div;
}

async function save(it, patch) {
  const cur = state.verdicts[it.id] || {};
  const next = { ...cur, ...patch, ticker: it.ticker, source_id: it.source_id, start: it.start, end: it.end, updated_at: new Date().toISOString() };
  state.verdicts[it.id] = next; render();
  if (!state.db) { setStatus('Not saved: the saved-verdicts store is not available in this view.'); return; }
  try { await state.db.collection('verdicts').doc(it.id).set(next); setStatus('Saved.'); }
  catch (e) { setStatus('Not saved: ' + (e && e.message || 'the store refused the write') + '. Try again in a moment.'); }
}

function setStatus(t) { $('#status').textContent = t; }

function render() {
  const list = $('#list'); list.textContent = '';
  const shown = ITEMS.filter(it => {
    const v = (state.verdicts[it.id] || {}).verdict;
    return state.filter === 'all' || (state.filter === 'todo' ? !v : v === state.filter);
  });
  for (const it of shown) list.appendChild(card(it));
  if (!shown.length) { const p = document.createElement('p'); p.className = 'lede';
    p.textContent = state.filter === 'todo' ? 'Everything has a verdict. Use All to look back over them.' : 'Nothing here yet.'; list.appendChild(p); }
  const vs = ITEMS.map(it => (state.verdicts[it.id] || {}).verdict).filter(Boolean);
  const n = k => vs.filter(v => v === k).length;
  $('#counts').textContent = `${vs.length} of ${ITEMS.length} reviewed · ${n('real')} bad · ${n('too_long')} flagged too long · ${n('not_real')} false alarm · ${n('unsure')} unsure`;
}

document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {
  state.filter = b.dataset.f;
  document.querySelectorAll('.filters button').forEach(o => o.setAttribute('aria-pressed', String(o === b)));
  render();
}));

render();
(async () => {
  const db = window.claude && await window.claude.use('db');
  if (!db) { setStatus('Verdicts can be chosen but not saved in this view: open the page on claude.ai while signed in.'); return; }
  state.db = db;
  const timer = setTimeout(() => setStatus('Saved verdicts can\'t be reached yet; anything you choose is kept once they load.'), 10000);
  db.collection('verdicts').onSnapshot(snap => {
    if (!snap.metadata.fromCache) { clearTimeout(timer); setStatus(''); }
    const fresh = {}; snap.docs.forEach(d => { fresh[d.id] = d.data(); });
    state.verdicts = fresh; render();
  }, e => { clearTimeout(timer); setStatus('Saved verdicts are unavailable: ' + (e && e.message || 'error') + '.'); });
  const missed = $('#missed-note'), mdoc = db.doc('notes/missed');
  mdoc.onSnapshot(s => { if (s.exists && document.activeElement !== missed) missed.value = (s.data().text || ''); }, () => {});
  missed.addEventListener('change', async () => {
    try { await mdoc.set({ text: missed.value.trim(), updated_at: new Date().toISOString() }); $('#missed-saved').textContent = 'Saved.'; }
    catch (e) { $('#missed-saved').textContent = 'Not saved. Try again in a moment.'; }
  });
})();
</script>
"""


def main():
    items = json.loads(pathlib.Path(sys.argv[1]).read_text())
    blob = json.dumps(items, separators=(',', ':')).replace('</', '<\\/')
    pathlib.Path(sys.argv[2]).write_text(PAGE.replace('__ITEMS__', blob))
    print(len(items), 'items ->', sys.argv[2])


if __name__ == '__main__':
    main()

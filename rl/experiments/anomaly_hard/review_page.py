"""Write the review page for review_items.py's output: python review_page.py ITEMS.json OUT.html

The page shows each unexplained alert against its company's other sources and takes a verdict (real, not real,
unsure) and a note, kept in the artifact's database (collection `verdicts`, one document per item id), plus one
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
  --real: #2f7a50; --notreal: #8a3b3b; --unsure: #8a6d1f; --focus: #2a6fb8;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121513; --panel: #1a1e1c; --ink: #e6ebe8; --muted: #9aa49f; --line: #2c322f;
  --count: #6aa6e6; --ticket: #e0965a; --flag: #ef7171; --span: rgba(239, 113, 113, .14);
  --known: rgba(110, 200, 150, .16); --known-ink: #7fd0a2;
  --real: #7fd0a2; --notreal: #ef8f8f; --unsure: #e3c06a; --focus: #6aa6e6; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121513; --panel: #1a1e1c; --ink: #e6ebe8; --muted: #9aa49f; --line: #2c322f;
  --count: #6aa6e6; --ticket: #e0965a; --flag: #ef7171; --span: rgba(239, 113, 113, .14);
  --known: rgba(110, 200, 150, .16); --known-ink: #7fd0a2;
  --real: #7fd0a2; --notreal: #ef8f8f; --unsure: #e3c06a; --focus: #6aa6e6; color-scheme: dark }
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
.head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; align-items: baseline; }
.head h2 { font-size: 17px; margin: 0; font-weight: 600; }
.meta { font: 13px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.known { font-size: 13px; color: var(--known-ink); }
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
    <p class="lede">Each card is a run of flags the scorer raised that touches no planted problem. Decide whether the
    source data is really off there. <b>Real</b> makes it labelled bad data in every task, <b>Not real</b> keeps it a
    false alarm, <b>Unsure</b> leaves it unscored. Lines are the source minus the median of the company's other
    sources, in log units, centred on the window.</p>
  </header>
  <div class="bar">
    <div class="filters" role="group" aria-label="Show">
      <button type="button" data-f="todo" aria-pressed="true">To review</button>
      <button type="button" data-f="all" aria-pressed="false">All</button>
      <button type="button" data-f="real" aria-pressed="false">Real</button>
      <button type="button" data-f="not_real" aria-pressed="false">Not real</button>
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
const LABEL = { real: 'Real', not_real: 'Not real', unsure: 'Unsure' };

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

function chart(it) {
  const c = it.chart, W = 720, H = 230, L = 44, R = 8, panelH = 92, gap = 22, T = 8;
  const n = c.dates.length, x = i => L + (W - L - R) * (n <= 1 ? 0 : i / (n - 1));
  const idx = d => { let i = c.dates.indexOf(d); if (i < 0) i = c.dates.findIndex(z => z >= d); return i < 0 ? n - 1 : i; };
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
    'aria-label': `${it.ticker} source ${it.source_id}: count and ticket size against other sources, ${c.dates[0]} to ${c.dates[n - 1]}` });
  const panels = [['count', 'Count vs others', 'var(--count)'], ['ticket', 'Ticket size vs others', 'var(--ticket)']];
  panels.forEach(([key, title, color], p) => {
    const top = T + p * (panelH + gap), vals = c[key].filter(v => v !== null);
    let lo = Math.min(...vals, -0.2), hi = Math.max(...vals, 0.2);
    const y = v => top + panelH - (v - lo) / (hi - lo) * panelH;
    for (const k of c.known) {
      const a = x(idx(k.start)), b = x(idx(k.end));
      el('rect', { x: a - 2, y: top, width: Math.max(4, b - a + 4), height: panelH, fill: 'var(--known)' }, svg);
    }
    const a = x(idx(it.start)), b = x(idx(it.end));
    el('rect', { x: a - 2, y: top, width: Math.max(4, b - a + 4), height: panelH, fill: 'var(--span)' }, svg);
    el('line', { x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: 'var(--line)', 'stroke-width': 1 }, svg);
    for (const v of [lo, hi]) {
      const t = el('text', { x: L - 6, y: y(v) + (v === hi ? 9 : -2), 'text-anchor': 'end' }, svg); t.textContent = v.toFixed(2);
    }
    const tt = el('text', { x: L + 4, y: top + 11 }, svg); tt.textContent = title;
    let d = '';
    c[key].forEach((v, i) => { if (v === null) return; d += (d && c[key][i - 1] !== null ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1); });
    el('path', { d, fill: 'none', stroke: color, 'stroke-width': 1.5, 'stroke-linejoin': 'round' }, svg);
    c.flags.forEach((f, i) => { if (f && c[key][i] !== null) el('circle', { cx: x(i), cy: y(c[key][i]), r: 2.6, fill: 'var(--flag)' }, svg); });
  });
  const base = T + 2 * panelH + gap + 16;
  [0, Math.floor((n - 1) / 2), n - 1].forEach((i, j) => {
    const t = el('text', { x: x(i), y: base, 'text-anchor': ['start', 'middle', 'end'][j] }, svg); t.textContent = c.dates[i];
  });
  return svg;
}

function card(it) {
  const v = state.verdicts[it.id] || {};
  const div = document.createElement('article');
  div.className = 'card' + (v.verdict ? ' done' : ''); if (v.verdict) div.dataset.v = v.verdict;
  const days = it.start === it.end ? it.start : `${it.start} to ${it.end}`;
  div.innerHTML = `<div class="head"><h2></h2><span class="meta"></span></div>
    <div class="meta days"></div><div class="known"></div><div class="chart"></div>
    <div class="legend"><span><i class="sw" style="background:var(--count)"></i>count</span>
      <span><i class="sw" style="background:var(--ticket)"></i>ticket size</span>
      <span><i class="sw" style="background:var(--flag)"></i>flagged day</span>
      <span><i class="sw" style="background:var(--span)"></i>this alert</span>
      <span><i class="sw" style="background:var(--known)"></i>planted problem or real event in the window</span></div>
    <div class="verdict" role="group"></div>
    <textarea rows="2" placeholder="Note (optional): what you see, or the dates if the real problem spans different days"></textarea>
    <span class="saved"></span>`;
  $('h2', div).textContent = `${it.ticker} · source ${it.source_id}`;
  $('.head .meta', div).textContent = `${it.flagged_days} flagged day${it.flagged_days === 1 ? '' : 's'} · in ${it.tasks.length} of 4 tasks`;
  $('.days', div).textContent = days + `  ·  ${it.chart.sources} sources`;
  $('.known', div).textContent = it.chart.known.length ? 'In this window: ' + it.chart.known.map(k => `${k.kind.replace('decoy:', 'real event (decoy): ')} ${k.start}`).join('; ') : '';
  $('.chart', div).appendChild(chart(it));
  const vb = $('.verdict', div); vb.setAttribute('aria-label', `Verdict for ${it.ticker} source ${it.source_id}`);
  for (const key of ['real', 'not_real', 'unsure']) {
    const b = document.createElement('button'); b.type = 'button'; b.dataset.v = key; b.textContent = LABEL[key];
    b.setAttribute('aria-pressed', String(v.verdict === key));
    b.addEventListener('click', () => save(it, { verdict: v.verdict === key ? null : key }, div));
    vb.appendChild(b);
  }
  const ta = $('textarea', div); ta.id = 'note-' + it.id; ta.value = v.note || '';
  ta.addEventListener('change', () => save(it, { note: ta.value.trim() }, div));
  return div;
}

async function save(it, patch, div) {
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
  const vs = Object.values(state.verdicts).map(v => v.verdict).filter(Boolean);
  const n = k => vs.filter(v => v === k).length;
  $('#counts').textContent = `${vs.length} of ${ITEMS.length} reviewed · ${n('real')} real · ${n('not_real')} not real · ${n('unsure')} unsure`;
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

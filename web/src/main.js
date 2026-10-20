import './ui.css';
import { COURSE_META, latest, proofSet, PROOF, LAB, PAPER_TEST, HOW_SURE, howSure } from './data.js';
import { initAuth, signInWithGoogle, signOut, hasClerk } from './auth.js';
import { drawTrade, destroy as destroyTrade, etTime } from './tradeChart.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const root = document.documentElement;
const qs = new URLSearchParams(location.search);
const STILL = qs.has('still') && qs.get('still') !== '0';
const REDUCE = !STILL && matchMedia('(prefers-reduced-motion: reduce)').matches;
const QUIET = STILL || REDUCE;
if (STILL) root.classList.add('still');
if (REDUCE) root.classList.add('reduce');
const DESK = matchMedia('(min-width: 960px)');
const store = {
  get(k, d) { try { const v = localStorage.getItem('dta-' + k); return v === null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem('dta-' + k, JSON.stringify(v)); } catch (_) {} }
};

/* ---------- icons: one stroke weight ---------- */
const ICON = {
  chevL: '<path d="M14.5 5.5 8 12l6.5 6.5"/>',
  chevR: '<path d="M9.5 5.5 16 12l-6.5 6.5"/>',
  x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  arrowR: '<path d="M4.5 12h15M13.5 6l6 6-6 6"/>',
  logout: '<path d="M9.5 4.5H6.5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h3"/><path d="M15.5 16.5 20 12l-4.5-4.5M20 12H9.5"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.1"/>',
  play: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10.2 9.4v5.2l4.4-2.6z"/>',
  chat: '<path d="M5.5 5h13a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H11l-4.5 3.5V16h-1A1.5 1.5 0 0 1 4 14.5v-8A1.5 1.5 0 0 1 5.5 5z"/>',
  help: '<circle cx="12" cy="12" r="8.5"/><path d="M9.7 9.6a2.4 2.4 0 0 1 4.6.9c0 1.7-2.3 2-2.3 3.5M12 16.9v.1"/>',
  trend: '<path d="M4 17l5.5-5.5 3.5 3.5L20 8"/><path d="M14.5 8H20v5.5"/>',
  doc: '<path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V7.5z"/><path d="M14 3.5v4h4M9 12h6M9 15.5h6"/>',
  wrench: '<path d="M14.5 5.5a4 4 0 0 0 4.9 4.9l-8.6 8.6a2.1 2.1 0 0 1-3-3l8.6-8.6"/>',
  ext: '<path d="M13.5 5.5H18.5V10.5M18.5 5.5 11 13"/><path d="M16.5 13.5v4a1.5 1.5 0 0 1-1.5 1.5H7a1.5 1.5 0 0 1-1.5-1.5V9.5A1.5 1.5 0 0 1 7 8h4"/>',
  grid: '<rect x="4.5" y="4.5" width="6" height="6" rx="1.5"/><rect x="13.5" y="4.5" width="6" height="6" rx="1.5"/><rect x="4.5" y="13.5" width="6" height="6" rx="1.5"/><rect x="13.5" y="13.5" width="6" height="6" rx="1.5"/>'
};
const GOOGLE = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22z"/><path fill="#FBBC05" d="M6.4 14c-.2-.6-.3-1.3-.3-2s.1-1.4.3-2V7.4H3.1a10 10 0 0 0 0 9.2z"/><path fill="#EA4335" d="M12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.4L6.4 10c.8-2.3 3-4.1 5.6-4.1z"/></svg>';
const icon = (n, cls = '') => n === 'google' ? GOOGLE : `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICON[n]}</svg>`;
// Without a Clerk key the button is a plain "Continue" (no fake Google).
if (!hasClerk()) { $('#goIc').remove(); $('#goT').textContent = 'Continue'; }
$$('[data-ic]').forEach(el => { el.outerHTML = icon(el.dataset.ic); });
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

/* ---------- words, colours, numbers ---------- */
const WORD_CLASS = { 'Yes': 'Yes', 'Barely': 'Barely', 'No': 'No', 'Not enough trades': 'few' };
const WORD_COLOR = { Yes: 'var(--yes)', Barely: 'var(--barely)', No: 'var(--no)', few: 'var(--few)' };
const PAPER = { Yes: '#5fbf93', Barely: '#e3a54a', No: '#ef6f61', few: '#a09e97' };
const HOLD_INK = '#a09e97';
const STRAT_COLORS = ['#6c9cf2', '#e3a54a', '#a493e6', '#5fbf93', '#a8c4f7', '#ef6f61'];
const wcls = w => WORD_CLASS[w] || 'few';
const fmt = {
  pct: v => { const r = Math.round(v * 10) / 10, a = Math.abs(r); return (r > 0 ? '+' : r < 0 ? '−' : '') + (Number.isInteger(a) ? a : a.toFixed(1)) + '%'; },
  money: v => '$' + Math.round(v).toLocaleString('en-US'),
  // Cheap coins need more digits than $0.07.
  price: v => { const n = Number(v); const d = n >= 1 ? 2 : n >= 0.01 ? 4 : 6; return '$' + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }
};
const pct = fmt.pct;
const nTrades = n => `${Number(n).toLocaleString('en-US')} trade${Number(n) === 1 ? '' : 's'}`;
const kMoney = v => (v % 1000 === 0 ? '$' + v / 1000 + 'k' : fmt.money(v));
const MONTH = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const month = d => MONTH.format(new Date(d + 'T00:00:00Z'));
const DAY = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York' });

/* ---------- data: one view-model per course at the chosen delay ---------- */
const COURSES = COURSE_META.map(m => ({ ...m, r: latest(m.key), set: proofSet(m.key) }));
const KEYS = COURSES.map(c => c.key);
const DELAYS = (COURSES.find(c => c.r)?.r.delays_min || [1, 3, 5, 10, 15, 30, 60]).slice().sort((a, b) => a - b);
const DEFAULT_DELAY = COURSES.find(c => c.r)?.r.default_delay_min || 5;
let delay = DELAYS.includes(store.get('delay', DEFAULT_DELAY)) ? store.get('delay', DEFAULT_DELAY) : DEFAULT_DELAY;

function dkey(byDelay) {
  const ks = Object.keys(byDelay || {}).map(Number);
  if (!ks.length) return null;
  return String(ks.reduce((b, k) => (Math.abs(k - delay) < Math.abs(b - delay) ? k : b), ks[0]));
}
const portfolioAt = p => (p.testable ? { ...p, at: p.by_delay?.[dkey(p.by_delay)] || null } : { ...p, at: null });
function holdName(h) {
  const sym = (h?.symbol || '').toUpperCase();
  if (sym.startsWith('BTC')) return 'Bitcoin';
  return sym || 'the market';
}
// contracts.md rule 9 (CAP-7): the benchmark in plain words, and a word that never reads as success when the copy lost money.
function benchName(r) {
  if (r?.compare_with?.name) return r.compare_with.name;
  const sym = (r?.hold?.symbol || '').toUpperCase();
  return sym.startsWith('BTC') ? 'Bitcoin' : sym === 'SPY' ? 'the S&P' : sym || 'the market';
}
const wordFor = (ret, bench, trades) => (trades != null && trades < 30 ? 'Not enough trades' : ret < 0 ? 'No' : ret - bench >= 2 ? 'Yes' : ret - bench <= -2 ? 'No' : 'Barely');
const outcomeFor = (ret, trades) => (trades === 0 ? 'No trades' : ret > 0 ? 'Made money' : ret < 0 ? 'Lost money' : 'Broke even');
function vsFor(ret, bench, trades, name) {
  if (trades === 0 || bench == null) return null;
  const gap = Math.round((ret - bench) * 100) / 100;
  if (gap >= 2) return ret < 0 ? `less than ${name}` : `beat ${name}`;
  if (gap > -2) return `about the same as ${name}`;
  return bench < 0 ? `more than ${name}` : `${name} did better`;
}
// The file's own words when it has them (results written after CAP-7); else the same rule on its numbers.
function says(row, ret, bench, trades, name) {
  return {
    word: row?.word ?? wordFor(ret, bench, trades),
    outcome: row?.outcome ?? outcomeFor(ret, trades),
    vs: row && 'vs' in row ? row.vs : vsFor(ret, bench, trades, name)
  };
}
// contracts.md rule 5 (CAP-17): the headline under three cost cases; the card leads with realistic.
const COST_CASES = [['realistic', 'Realistic'], ['simple', 'Simple'], ['x2', '2× realistic']];
const COST_WORDS = { simple: 'Simple', realistic: 'Realistic', x2: '2× realistic' };
let costCase = COST_CASES.some(([k]) => k === store.get('cost', 'realistic')) ? store.get('cost', 'realistic') : 'realistic';
function caseRows(r, pid) {
  const p = (r?.cost_cases?.portfolios || []).find(x => x.id === pid);
  return p ? p.by_delay?.[dkey(p.by_delay)] || null : null;
}
function vm(c) {
  const r = c.r;
  if (!r) return { tested: false, word: 'Not tested yet' };
  const ports = (r.portfolios || []).map(portfolioAt);
  const head = ports.find(p => p.id === r.headline_portfolio && p.at) || ports.find(p => p.at);
  if (!head) return { tested: false, word: 'Not tested yet' };
  const bench = benchName(r), cases = caseRows(r, head.id);
  // a non-simple case shows only what was computed for it, plus what costs never change (just holding, triggers)
  const s = cases?.[costCase] && costCase !== 'simple'
    ? { hold_end: head.at.hold_end, not_triggered: head.at.not_triggered, ...cases[costCase] } : head.at;
  return { tested: true, r, head, s, ports, cases, costCase: cases?.[costCase] ? costCase : 'simple',
           start: r.money_start || 10000, hold: holdName(r.hold), bench,
           ...says(s, s.ret_pct, s.hold_ret_pct, s.trades, bench) };
}
// The other two cost cases, one line: "Simple $9,735 (No) · 2× $9,102 (No) · borrow fees $13".
function costLine(v) {
  if (!v.cases) return '';
  const bits = COST_CASES.filter(([k]) => k !== v.costCase && v.cases[k]).map(([k]) =>
    `${COST_WORDS[k]} <b style="color:${WORD_COLOR[wcls(v.cases[k].word)]}">${fmt.money(v.cases[k].end)}</b> (${esc(v.cases[k].word ?? '')})`);
  const b = v.cases[v.costCase]?.borrow_usd;
  if (b > 0) bits.push(`borrow fees ${fmt.money(b)}`);
  if (v.costCase !== 'simple') bits.push('chart: simple costs');
  const day = v.r.cost_cases?.borrow?.checked?.to;
  if (v.costCase !== 'simple' && v.r.cost_cases?.borrow?.shorted_tickers && day) bits.push(`hard-to-borrow status as of ${day}, not the trade date`);
  return bits.join(' · ');
}
// One honest fine-print line: sizing, plus trades we couldn't copy or had to shrink.
function fineLine(r, s) {
  const sz = r.sizing || '', amt = sz.match(/\$[\d,]+/)?.[0];
  const unit = sz.match(/(?:per|a|each) (trade|call|setup)/i)?.[1] || 'trade';
  const bits = [];
  // Wording comes from `sizing`: whose size, scaled or not, and the amount.
  if (amt) bits.push(/scal/i.test(sz) ? `${/^his\b/i.test(sz) ? 'His trades' : 'Their trades'}, scaled to ${amt} each` : `${amt} per ${unit}`);
  if (s.couldnt_copy > 0) bits.push(`${s.couldnt_copy.toLocaleString('en-US')} couldn’t be copied`);
  if (s.sized_down > 0) bits.push(`${s.sized_down.toLocaleString('en-US')} sized down`);
  if (s.not_triggered > 0) bits.push(`${s.not_triggered.toLocaleString('en-US')} never triggered`);
  return bits.join(' · ');
}
// The fix, in money: the same sessions priced from v1's and v2's extraction (LPP's proof set).
function proofSetLine(c) {
  const ps = c.set, ss = ps?.same_sessions;
  if (!ss) return '';
  const a = ss.by_delay?.[dkey(ss.by_delay)];
  const h = (ps.portfolios || []).find(p => p.id === ps.headline_portfolio), b = h?.by_delay?.[dkey(h.by_delay)];
  if (!a || !b) return '';
  return `${ss.sessions}-session proof set (${ss.version} vs ${ps.version}: ${fmt.money(a.end)} → ${fmt.money(b.end)})`;
}
// The PRISM proof exists for LPP only (the extract-lpp runs).
const proofFor = c => (PROOF && c.key === 'lpp' ? PROOF : null);

/* ---------- state ---------- */
let user = null, booted = false, cur = 0, route = null, openedByUser = false;
const selected = new Set((store.get('picks', null) || KEYS).filter(k => KEYS.includes(k)));
if (!selected.size) KEYS.forEach(k => selected.add(k));
let onboarded = store.get('onboarded', false);
const visibleList = () => KEYS.map((k, i) => i).filter(i => selected.has(KEYS[i]));

/* ---------- course switcher ---------- */
const seg = $('#seg');
seg.insertAdjacentHTML('beforeend', COURSES.map((c, i) => `<button type="button" role="tab" data-i="${i}" aria-selected="false">${esc(c.name)}</button>`).join(''));
function syncSeg(instant) {
  const L = visibleList();
  $$('button', seg).forEach(b => { const i = +b.dataset.i; b.hidden = !L.includes(i); b.setAttribute('aria-selected', String(i === cur)); });
  const on = $('button[aria-selected=true]', seg), pill = $('.seg-pill', seg);
  if (!on) return;
  const A = on.getBoundingClientRect(), S = seg.getBoundingClientRect();
  if (!A.width) return;
  if (instant) seg.classList.add('instant');
  pill.style.width = A.width + 'px';
  pill.style.transform = `translateX(${A.left - S.left}px)`;
  if (instant) { void seg.offsetWidth; seg.classList.remove('instant'); }
}
seg.addEventListener('click', e => { const b = e.target.closest('button[data-i]'); if (b) goCourse(+b.dataset.i); });
function goCourse(i) {
  const scr = document.body.dataset.screen;
  location.hash = `#${scr === 'learn' ? 'learn' : 'verdict'}-${KEYS[i]}`;
}
function stepCourse(dir) {
  const L = visibleList(), k = L.indexOf(cur);
  if (L.length < 2) return;
  goCourse(L[(k + dir + L.length) % L.length]);
}

/* ---------- the delay slider (CAP-1): no network, just the file's numbers ---------- */
const delayIdx = () => Math.max(0, DELAYS.indexOf(delay));
const dLabel = d => (d >= 60 && d % 60 === 0 ? d / 60 + 'h' : d + 'm');
const delayChips = () => DELAYS.map((d, i) => `<button type="button" data-di="${i}" aria-label="${d} minutes after each post" aria-pressed="false">${dLabel(d)}</button>`).join('');
$('#vDelays').innerHTML = delayChips();
$('#lDelay').innerHTML = `<div class="sec">ENTERED AFTER EACH POST</div><div class="chips mono">${delayChips()}</div>`;
function syncDelay() {
  $$('[data-di]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.di === delayIdx())));
}
function setDelay(d) {
  if (d === delay || !DELAYS.includes(d)) return;
  delay = d; store.set('delay', d);
  syncDelay();
  const scr = document.body.dataset.screen;
  if (scr === 'verdict') renderVerdict(false);
  if (scr === 'learn') renderLearn(false);
}
document.addEventListener('click', e => { const b = e.target.closest('[data-di]'); if (b) setDelay(DELAYS[+b.dataset.di]); });

/* ---------- verdict (CAP-5): one sentence, one chip, then the detail cards ---------- */
// v2 keys (strategies, ranges, best_stop, combos, suggestion) come from the results file; a missing key hides its card.
const RANGES = [['3m', '3M', 3], ['6m', '6M', 6], ['1y', '1Y', 12], ['all', 'All', 0]];
let range = 'all';
const extra = (c, key) => (c.r?.[key] != null ? { v: c.r[key], sample: !!c.r.sample } : null);
const addMonths = (iso, n) => { const d = new Date(iso + 'T00:00:00Z'); d.setUTCMonth(d.getUTCMonth() + n); return d.toISOString().slice(0, 10); };
// The window, cut to the chosen range: numbers from ranges[...] when the file has them, else from the curve.
function cut(v) {
  const S = v.head.series, curve = S?.by_delay?.[dkey(S?.by_delay)], dates = S?.dates || [];
  let n = curve ? curve.length - 1 : -1;
  const R = RANGES.find(x => x[0] === range);
  if (R[2] && dates.length) { const lim = v.r.ranges?.[range]?.until || addMonths(dates[0], R[2]); while (n > 0 && dates[n] > lim) n--; }
  const out = { n, curve, dates, hold: S?.hold, end: v.s.end, hold_end: v.s.hold_end, word: v.word, outcome: v.outcome, vs: v.vs, ret: v.s.ret_pct, hold_ret: v.s.hold_ret_pct, trades: v.s.trades, from: 'file' };
  if (range === 'all' || !curve) return out;
  const fileR = v.r.ranges?.[range]?.by_delay?.[dkey(v.r.ranges[range].by_delay)];
  const end = fileR?.end ?? curve[n], hold_end = fileR?.hold_end ?? S.hold?.[n];
  const ret = (end / v.start - 1) * 100, hold_ret = (hold_end / v.start - 1) * 100;
  const trades = fileR?.trades ?? null;
  return { ...out, end, hold_end, ret, hold_ret, trades, ...says(fileR, ret, hold_ret, trades ?? (v.s.trades < 30 ? v.s.trades : null), v.bench), from: fileR ? 'file' : 'curve' };
}
function bestStop(v, k) {
  const bs = range === 'all' ? v.r.best_stop?.by_delay?.[dkey(v.r.best_stop?.by_delay)] : null;
  if (bs) return { date: bs.date, end: bs.end, i: k.dates.indexOf(bs.date) };
  if (!k.curve || k.n < 1) return null;
  let i = 0; for (let j = 1; j <= k.n; j++) if (k.curve[j] > k.curve[i]) i = j;
  return { date: k.dates[i], end: k.curve[i], i };
}
const LONGDAY = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
const longDay = d => LONGDAY.format(new Date(d + 'T00:00:00Z'));
// Outcome first, then the comparison, then the money (CAP-7): "Lost money, less than Bitcoin."
const sentence = x => esc(x.vs ? `${x.outcome}, ${x.vs}.` : `${x.outcome}.`);
function headline(v, k) {
  const few = k.word === 'Not enough trades' ? ' Too few trades to judge.' : '';
  return `${sentence(k)} <span class="acc">${kMoney(v.start)} became ${fmt.money(k.end)}.${few}</span>`;
}
// The held-out (sealed) months' own word, beside the headline.
function sealedSays(v) {
  const se = v.s.sealed, w = v.r.window;
  if (!se || !w?.sealed_from || w.sealed_from <= w.start) return null;
  return { ...says(se, se.ret_pct, se.hold_ret_pct, se.trades, v.bench), from: w.sealed_from, to: w.end, trades: se.trades };
}
function heldLine(v) {
  const h = sealedSays(v);
  if (!h) return '';
  return `Held-out months, ${month(h.from)} – ${month(h.to)}: <b style="color:${WORD_COLOR[wcls(h.word)]}">${esc(h.word ?? '')}</b> · ${sentence(h)}`;
}
function spark(arr, color, w = 92, h = 28) {
  if (!arr || arr.length < 2) return '';
  const mn = Math.min(...arr), mx = Math.max(...arr), span = mx - mn || 1;
  const step = Math.max(1, Math.floor(arr.length / 80)), pts = arr.filter((_, i) => i % step === 0 || i === arr.length - 1);
  const d = pts.map((y, i) => `${i ? 'L' : 'M'}${(i * w / (pts.length - 1)).toFixed(1)} ${(h - 3 - (y - mn) / span * (h - 6)).toFixed(1)}`).join('');
  return `<svg viewBox="0 0 ${w} ${h}" aria-hidden="true"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" pathLength="1" class="draw"/></svg>`;
}
function drawMain(v, k) {
  const host = $('#vChart');
  if (!k.curve || k.n < 1) { host.innerHTML = ''; $('#vStop').textContent = ''; return; }
  const col = PAPER[wcls(k.word)], c = k.curve.slice(0, k.n + 1), h = (k.hold || []).slice(0, k.n + 1);
  const W = Math.max(280, Math.round(host.clientWidth || 560)), H = 170, P = { l: 40, r: 10, t: 10, b: 22 };
  const all = c.concat(h), mn = Math.min(...all), mx = Math.max(...all);
  const step = [100, 250, 500, 1000, 2000, 2500, 5000].find(x => (mx - mn) / x <= 4) || 10000;
  const lo = Math.floor(mn / step) * step, hi = Math.max(lo + step, Math.ceil(mx / step) * step), n = c.length - 1;
  const X = i => P.l + i * (W - P.l - P.r) / n, Y = y => P.t + (hi - y) * (H - P.t - P.b) / (hi - lo);
  const path = a => a.map((y, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(y).toFixed(1)}`).join('');
  let g = '';
  for (let y = lo; y <= hi + 1; y += step) g += `<line class="gl${y === v.start ? ' base' : ''}" x1="${P.l}" x2="${W - P.r}" y1="${Y(y).toFixed(1)}" y2="${Y(y).toFixed(1)}"/><text x="${P.l - 6}" y="${(Y(y) + 3).toFixed(1)}" text-anchor="end">$${(y / 1000).toLocaleString('en-US', { maximumFractionDigits: 2 })}k</text>`;
  if (k.dates[0]) g += `<text x="${P.l}" y="${H - 4}">${month(k.dates[0])}</text>`;
  if (k.dates[n]) g += `<text x="${W - P.r}" y="${H - 4}" text-anchor="end">${month(k.dates[n])}</text>`;
  const bs = bestStop(v, k);
  const dot = bs && bs.i >= 0 && bs.i <= n ? `<circle cx="${X(bs.i).toFixed(1)}" cy="${Y(c[bs.i]).toFixed(1)}" r="9" fill="${PAPER.Barely}" opacity=".18" class="stopdot"/><circle cx="${X(bs.i).toFixed(1)}" cy="${Y(c[bs.i]).toFixed(1)}" r="4" fill="#f0d29f"/>` : '';
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${kMoney(v.start)} over time: copying ends at ${fmt.money(c[n])}, holding ${esc(v.hold)} at ${fmt.money(h[n] ?? 0)}.">${g}
    ${h.length ? `<path d="${path(h)}" fill="none" stroke="${HOLD_INK}" stroke-width="1.25" stroke-dasharray="4 4" class="flow"/>` : ''}
    <path d="${path(c)}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" pathLength="1" class="draw" style="filter:drop-shadow(0 0 6px ${col}55)"/>${dot}</svg>`;
  $('#chartMeta').innerHTML = `<span style="color:${col}">━</span> copying &nbsp;<span style="color:${HOLD_INK}">┅</span> holding ${esc(v.hold)}`;
  $('#vStop').hidden = !bs || k.word === 'Not enough trades';
  $('#vStop').innerHTML = bs ? (bs.end > v.start ? `Best day to stop: <b>${longDay(bs.date)}</b>, with ${fmt.money(bs.end)}.` : `Best day to stop: <b>the day you started</b>. It never got above ${kMoney(v.start)}.`) : '';
}
let openStrat = null;
function renderStrats(c, v) {
  const ex = extra(c, 'strategies');
  let rows, sample = false;
  if (ex && Array.isArray(ex.v) && ex.v.length) {
    sample = ex.sample;
    rows = ex.v.map((st, i) => ({ id: st.id, name: st.name, color: STRAT_COLORS[i % STRAT_COLORS.length], at: st.by_delay?.[dkey(st.by_delay)], curve: st.series?.by_delay?.[dkey(st.series?.by_delay)], st }));
  } else rows = [];
  $('#stratMeta').innerHTML = (sample ? '<span class="tagS">Sample</span> ' : '') + `<span class="mono">holding ${esc(v.hold)} ${pct(v.s.hold_ret_pct)}</span>`;
  rows.sort((a, b) => (b.at?.trades || 0) - (a.at?.trades || 0));
  $('#cStrat').hidden = !rows.length;
  $('#strats').innerHTML = rows.map(r => {
    const a = r.at; if (!a) return '';
    const open = openStrat === r.id && r.st;
    return `<li><button class="strat-row" type="button" data-sid="${esc(r.id)}" aria-expanded="${!!open}" ${r.st ? '' : 'aria-disabled="true"'}>
      <span class="sw" style="background:${r.color};box-shadow:0 0 8px ${r.color}88"></span>
      <span class="s-name">${esc(r.name)}</span>
      <span class="s-sub">${nTrades(a.trades)}${a.won_pct != null ? ` · won ${a.won_pct}%` : ''}</span>
      <span class="s-spark">${spark(r.curve, r.color)}</span>
      <span class="s-ret" style="color:${PAPER[wcls(a.word)]}">${pct(a.ret_pct)}<small>${esc(a.word)}</small></span></button>
      ${open ? entailsHTML(r.st) : ''}</li>`;
  }).join('');
}
function entailsHTML(st) {
  const E = st.entails || {}, lane = (k, t) => (t ? `<div class="lane"><span class="k">${k}</span><span>${esc(t)}</span></div>` : '');
  const q = (st.quotes || []).slice(0, 2).map(x => `<div class="lane"><span class="k">SAID</span><span><q>${esc(x.text)}</q><span class="cite">${esc(x.cite?.label || '')}</span></span></div>`).join('');
  const un = (st.untestable || []).length ? `<div class="lane"><span class="k">CAN’T TEST</span><span>${st.untestable.map(esc).join(' · ')}</span></div>` : '';
  return `<div class="entails">${lane('BUY', E.buy)}${lane('SELL', E.sell)}${lane('STOP', E.stop)}${lane('SIZE', E.size)}${lane('TIME', E.time)}${q}${un}</div>`;
}
$('#strats').addEventListener('click', e => {
  const b = e.target.closest('[data-sid]'); if (!b || b.getAttribute('aria-disabled') === 'true') return;
  openStrat = openStrat === b.dataset.sid ? null : b.dataset.sid;
  const c = COURSES[cur]; renderStrats(c, vm(c));
});
function stratName(ref, c) {
  const [ck, sid] = ref.includes(':') ? ref.split(':') : [c.key, ref];
  const course = COURSES.find(x => x.key === ck) || c;
  const list = course.r?.strategies || [];
  const st = list.find(x => x.id === sid);
  const port = course.r?.portfolios?.find(p => p.id === sid);
  const name = st?.name || port?.label || sid;
  return course.key === c.key ? name : `${course.name}: ${name}`;
}
// Plain words for small changes: the code decides, the copy only reports it.
const pct2 = v => { const r = Math.round(v * 100) / 100, a = Math.abs(r).toFixed(2); return (r > 0 ? '+' : r < 0 ? '−' : '') + a + '%'; };
// "How sure?" (spec-audit CAP-16, story 28): one row per claim from results/how-sure.json. Anything failing reads
// "Not proven"; every number is the file's.
const ptsS = v => { const r = Math.round(v * 10) / 10; return (r > 0 ? '+' : r < 0 ? '−' : '') + Math.abs(r).toFixed(1); };
const okCls = b => (b === true ? 'pos' : b === false ? 'neg' : '');
function howCount(ids) {
  const cs = ids.map(howSure).filter(Boolean), n = cs.filter(c => c.proven).length;
  return n ? `${n} of ${cs.length} survive every test` : `none of ${cs.length} survives every test, so none is proven`;
}
function howRow(c) {
  if (!c) return '';
  const t = [`${(HOW_SURE.families?.[c.family]?.trials ?? c.luck?.trials ?? 1).toLocaleString('en-US')} tried`];
  if (c.luck) t.push(`<span class="${okCls(c.luck.passes)}">luck test ${c.luck.passes ? 'passed' : 'failed'}</span>`);
  else if (c.trades < 30) t.push('too few trades to test');
  if (c.shuffle) t.push(`<span class="${okCls(c.shuffle.passes)}">beat ${Math.round(c.shuffle.pct_rank)}% of random</span>`);
  if (c.walk_forward) t.push(`<span class="${okCls(c.walk_forward.passes)}">walk-forward ${ptsS(c.walk_forward.oos_ret_pct)}% vs ${ptsS(c.walk_forward.as_is_oos_ret_pct)}% as posted</span>`);
  if (c.sensitivity) { const [lo, hi] = c.sensitivity.edge_range_pts; t.push(`<span class="${okCls(c.sensitivity.passes)}">thresholds moved: ${ptsS(lo)} to ${ptsS(hi)} pts</span>`); }
  if (c.regime && (c.regime.up.months || c.regime.down.months)) t.push(`<span class="${okCls(c.regime.passes)}">S&amp;P up months ${ptsS(c.regime.up.edge_pts)} pts, down ${ptsS(c.regime.down.edge_pts)}</span>`);
  return `<p class="how mono num"><span class="how-l">How sure?</span> <b class="${c.proven ? 'pos' : 'neg'}">${c.proven ? 'Survives' : 'Not proven'}</b> · ${t.join(' · ')}</p>`;
}
const moved = (before, after, where) => { const d = after - before; return (d > 0.05 ? 'Helped' : d < -0.05 ? 'Hurt' : 'No change') + ' on ' + where; };
// Kept only if the sealed months agree. The file's `kept` and `kept_reason` decide; a file
// without `kept_reason` whose sealed months didn't gain falls back to the same rule.
function keptOf(sb) {
  const gain = sb.sealed ? sb.sealed.after_pct - sb.sealed.before_pct : null;
  if (sb.kept_reason) return { kept: !!sb.kept, text: `${sb.kept ? 'Kept' : 'Not kept'}: ${sb.kept_reason}` };
  if (gain != null && gain <= 0.05) return { kept: false, text: 'Not kept: no gain on new months' };
  return { kept: !!sb.kept, text: sb.kept ? 'Kept: it held up on new months' : 'Not kept' };
}
function renderBotMix(c) {
  const sb = c.r?.suggestion, m = Array.isArray(c.r?.combos) ? c.r.combos[0] : null;
  $('#cBot').hidden = !sb;
  if (!sb) $('#cBot').innerHTML = '';
  if (!m) $('#cMix').innerHTML = '';
  if (sb) {
    const url = sb.prism_url || (sb.trajectory_id ? `https://prism.blockconvey.com/trajectories/${encodeURIComponent(sb.trajectory_id)}` : null);
    const past = sb.dev ? moved(sb.dev.before_pct, sb.dev.after_pct, 'past months') : '';
    const fresh = sb.sealed ? moved(sb.sealed.before_pct, sb.sealed.after_pct, 'new months').replace(/^./, ch => ch.toLowerCase()) : '';
    $('#cBot').innerHTML = `<div class="ch"><span>Bot suggests</span><span class="meta">PRISM-traced</span></div>
      <p class="bot-change">${esc(sb.change)}${sb.applies_to ? ` <span class="meta">on ${esc(stratName(sb.applies_to, c))}</span>` : ''}</p>
      ${sb.why ? `<p class="meta">${esc(sb.why)}</p>` : ''}
      <div class="bot-rows mono num">
        ${sb.dev ? `<div><span>Past months</span><b>${pct2(sb.dev.before_pct)} → ${pct2(sb.dev.after_pct)}</b></div>` : ''}
        ${sb.sealed ? `<div><span>New months${sb.sealed.trades != null ? ` · ${nTrades(sb.sealed.trades)}` : ''}</span><b>${pct2(sb.sealed.before_pct)} → ${pct2(sb.sealed.after_pct)}</b></div>` : ''}
      </div>
      <p class="bot-say">${[past, fresh].filter(Boolean).join(', ')}.</p>
      <p class="bot-kept" data-kept="${keptOf(sb).kept}">${esc(keptOf(sb).text)}</p>
      ${link(url, 'See the run in PRISM')}`;
  }
  $('#cMix').hidden = !m;
  if (m) {
    const say = m.dev && m.sealed ? `${m.dev.ret_pct >= m.dev.hold_ret_pct ? 'Beat holding' : m.dev.ret_pct >= 0 ? 'Trailed holding' : 'Lost money'} on past months, ${m.sealed.ret_pct < 0 ? 'lost on new ones' : m.sealed.ret_pct >= m.sealed.hold_ret_pct ? 'held up on new ones' : 'trailed holding on new ones'}.` : '';
    $('#cMix').innerHTML = `<div class="ch"><span>Best mix <span class="meta">within this course</span></span><span class="wchip" style="--word:${WORD_COLOR[wcls(m.word)]}">${esc(m.word || '')}</span></div>
      <p class="bot-change">${m.ids.map(id => esc(stratName(id, c))).join(' + ')}</p>
      <div class="bot-rows mono num">
        ${m.dev ? `<div><span>Past months${m.dev.pairs_tried ? ` · best of ${m.dev.pairs_tried} pairs` : ''}</span><b>${pct2(m.dev.ret_pct)} <small>vs ${pct2(m.dev.hold_ret_pct)} holding</small></b></div>` : ''}
        ${m.sealed ? `<div><span>New months${m.window ? ` · ${month(m.window.start)}–${month(m.window.end)}` : ''}</span><b>${pct2(m.sealed.ret_pct)} <small>vs ${pct2(m.sealed.hold_ret_pct)} holding</small></b></div>` : ''}
      </div>
      ${say ? `<p class="bot-say">${say}</p>` : ''}`;
  }
}
// Year by year (CAP-4): the headline portfolio at the chosen delay, each calendar year then all time. Missing key: hidden.
function renderYears(v) {
  const by = v.r?.by_year, rows = by?.portfolios?.[v.head.id]?.by_delay?.[dkey(by?.portfolios?.[v.head.id]?.by_delay)];
  $('#cYear').hidden = !rows;
  if (!rows) { $('#years').innerHTML = ''; return; }
  const tr = by.hold?.basis === 'total_return';
  $('#yearMeta').textContent = tr ? `holding ${v.hold} with dividends` : `holding ${v.hold}`;
  const few = w => (w === 'Not enough trades' ? 'Too few' : w);
  $('#years').innerHTML = `<thead><tr><th scope="col">Year</th><th scope="col">Copying</th><th scope="col">Holding</th><th scope="col">Trades</th><th scope="col">Answer</th></tr></thead><tbody>` +
    (by.periods || []).filter(p => rows[p.id]).map(p => {
      const r = rows[p.id], all = p.id === 'all', x = says(r, r.ret_pct, r.hold_ret_pct, r.trades, v.bench);
      return `<tr class="${all ? 'all' : ''}"><td>${all ? 'All time' : esc(p.id)}</td>
        <td>${pct(r.ret_pct)}<small>${fmt.money(r.end)}</small></td>
        <td>${pct(r.hold_ret_pct)}${tr ? `<small>${pct(r.hold_price_ret_pct)} price</small>` : ''}</td>
        <td>${Number(r.trades).toLocaleString('en-US')}</td>
        <td class="w-${wcls(x.word)}" title="${sentence(x)}">${esc(few(x.word))}${x.vs ? `<small>${esc(x.vs)}</small>` : ''}</td></tr>`;
    }).join('') + '</tbody>';
}
// His strategy (spec-audit CAP-14): rules the model worded and code checked, each with how often he follows it,
// its win rate and P&L; then the three patterns that lost the most. Every number is from strategy_profile. Missing key: hidden.
const signed = v => (v < 0 ? '−' : v > 0 ? '+' : '') + fmt.money(Math.abs(v));
const hisNums = r => `${nTrades(r.trades)} · won ${r.won_pct}% · <b class="${r.pnl_usd < 0 ? 'neg' : 'pos'}">${signed(r.pnl_usd)}</b>`;
function renderHis(v) {
  const sp = v.r?.strategy_profile;
  $('#cHis').hidden = !sp;
  if (!sp) { $('#hisRules').innerHTML = ''; $('#hisLoss').innerHTML = ''; return; }
  $('#hisMeta').textContent = `${nTrades(sp.summary.trades)} · entered ${sp.delay_min} min late`;
  $('#hisRules').innerHTML = (sp.rules || []).map(r => `<li>
      <p class="h-text">${esc(r.text)}</p>
      <p class="h-num mono num">Does it ${Math.round(r.follows_pct)}% of the time · ${hisNums(r)}</p>
      ${r.quote ? `<p class="h-said"><q>${esc(r.quote.text)}</q><span class="cite">${esc(r.quote.cite?.label || '')}</span></p>` : ''}</li>`).join('');
  $('#hisLoss').innerHTML = (sp.losing_patterns || []).map(p => `<li>
      <p class="h-text">${esc(p.label || p.id)}</p>
      <p class="h-num mono num">${hisNums(p)} · ${Math.round(p.share_of_losses_pct)}% of the $ lost on losing trades</p></li>`).join('');
}
// What would have helped (spec-audit CAP-15): rule changes from his losses, applied by code to his own trades,
// picked on past (dev) months and tested once on the held-out months. Kept and not kept, both shown. Missing key: hidden.
// The file's kept_reason, in plain words (the decision itself is the file's `kept`).
let LABEL = null;
function helpWhy(x) {
  const r = x.kept_reason || '';
  if (x.kept) return `${(LABEL || 'held up (not proven)').replace(/^./, ch => ch.toUpperCase())}: helped on past months, didn't lose on held-out ones`;
  if (/fewer than/.test(r)) return 'Not kept: too few trades left';
  if (/\(dev\)/.test(r)) return "Not kept: didn't help on past months";
  if (/held-out/.test(r)) return 'Not kept: helped on past months, hurt on held-out ones';
  return 'Not kept';
}
function renderHelp(v) {
  const im = v.r?.improvements;
  $('#cHelp').hidden = !im;
  if (!im) { $('#helpKept').innerHTML = ''; $('#helpNot').innerHTML = ''; return; }
  const w = im.window || {}, sp = im.spy || {}, tried = im.variants_tried || {};
  LABEL = im.kept_label || 'held up (not proven)';
  $('#helpMeta').textContent = `picked on ${month(w.dev_from)}–${month(w.sealed_from)}, tested on ${month(w.sealed_from)}–${month(w.sealed_to)}`;
  $('#helpBase').innerHTML = `As posted: <span class="mono num">${pct2(im.as_is.dev.ret_pct)}</span> past, <span class="mono num">${pct2(im.as_is.sealed.ret_pct)}</span> held-out. Holding SPY: <span class="mono num">${pct2(sp.dev_ret_pct)}</span>, <span class="mono num">${pct2(sp.sealed_ret_pct)}</span>.`;
  const row = x => `<li>
      <p class="h-text">${esc(x.text)}</p>
      <p class="h-num mono num">Past ${pct2(x.dev.as_is_ret_pct)} → <b class="${x.dev.vs_as_is_pts > 0 ? 'pos' : 'neg'}">${pct2(x.dev.ret_pct)}</b> · held-out ${pct2(x.sealed.as_is_ret_pct)} → <b class="${x.sealed.vs_as_is_pts >= 0 ? 'pos' : 'neg'}">${pct2(x.sealed.ret_pct)}</b> · ${nTrades(x.sealed.trades)}</p>
      <p class="h-num mono num">vs holding SPY: ${x.sealed.vs_spy_pts >= 0 ? 'ahead' : 'behind'} ${Math.abs(x.sealed.vs_spy_pts).toFixed(2)} pts held-out</p>
      <p class="bot-kept" data-kept="${!!x.kept}">${esc(helpWhy(x))}</p>${howRow(howSure(`improvements:${x.id}`))}</li>`;
  const vs = im.variants || [], kept = vs.filter(x => x.kept), not = vs.filter(x => !x.kept);
  $('#helpKept').innerHTML = kept.length ? kept.map(row).join('') : '<li><p class="h-text">Nothing held up on the held-out months.</p></li>';
  $('#helpNot').innerHTML = not.map(row).join('');
  $('#helpNotSec').hidden = !not.length;
  if (kept.length && im.kept_all_trail_spy) $('#helpBase').innerHTML += ' Every change that held up still trailed the S&P.';
  $('#helpKeptSec').textContent = `${LABEL.toUpperCase()}${tried.distinct_priced ? ` · ${kept.length} of ${tried.distinct_priced} tried` : ''}`;
  $('#helpNote').innerHTML = [
    HOW_SURE ? `Luck test after ${tried.distinct_priced || vs.length} tries: ${howCount(vs.map(x => `improvements:${x.id}`))}.` : `Not proven: gains this small on about 100 trades can be luck after ${tried.distinct_priced || vs.length} tries.`,
    ...(im.disclosure || []).slice(0, 2)].map(t => `<p class="meta">${esc(t)}</p>`).join('');
  $('#helpLink').innerHTML = link(im.prism_url, 'See the run in PRISM');
}
// His strategy on new data (spec-audit CAP-15, story 21): S4 and S5 as code, no post from him, on prices after his
// window, on his stocks (a) and on stocks he never traded (b). Every number from results/strategy-lab.json; LPP only.
const UNI_SHORT = { 'his-hot': 'His stocks', 'his-crypto': 'His stocks', 'new-hot': 'Other stocks',
  'new-crypto': 'Other stocks', 'new-hot-raw': 'Other stocks, corrected list' };
const C_LIST = { 'his-hot': 'His hot', 'his-crypto': 'His crypto', 'new-hot': 'Other hot', 'new-crypto': 'Other crypto',
  'new-hot-raw': 'Other hot, corrected list' };
// Every row shows its return four ways (base costs, 2x costs, borrow fees, small-cap spreads) and its hard-to-borrow count.
const fourWays = r => `<b class="${r.ret_pct < 0 ? 'neg' : 'pos'}">${pct(r.ret_pct)}</b> · 2× simple costs ${pct(r.costs.x2.ret_pct)} · borrow fees ${pct(r.borrow.borrow_high_ret_pct)} · small-cap costs ${pct(r.costs.small_cap.ret_pct)}`;
const htbLine = r => `${r.borrow.htb_trades.toLocaleString('en-US')} of ${nTrades(r.trades)} hard to borrow`;
function renderLab(c) {
  const L = LAB, show = !!L && c.key === 'lpp';
  $('#cLab').hidden = !show;
  if (!show) return;
  const spy = L.benchmark.ret_pct, run = (rule, u, vr) => L.runs.find(r => r.rule === rule && r.universe === u && r.variant === vr);
  const held = Object.entries(L.verdict).filter(([, x]) => x.held_up).map(([k]) => k);
  $('#labMeta').textContent = `${L.window.from} → ${L.window.to}`;
  $('#labHead').innerHTML = held.length
    ? `<b class="pos">${esc(held.join(' and '))} held up</b> on new prices and other stocks.`
    : `<b class="neg">Neither rule held up</b> on new prices and other stocks. The S&amp;P made ${pct(spy)}.`;
  const line = (r, name) => `<p class="h-num mono num">${esc(name)}: ${fourWays(r)}</p>
    <p class="h-num mono num">${esc(r.word === 'Not enough trades' ? 'Too few' : r.word)} · ${nTrades(r.trades)}${r.won_pct != null ? ` · won ${r.won_pct}%` : ''} · worst drop ${pct(r.max_drawdown_pct)} · ${htbLine(r)}</p>${howRow(howSure(`lab:${r.rule}|${r.variant}|${r.universe}`))}`;
  $('#labRules').innerHTML = L.rules.map(rule => {
    const rows = rule.universes.map(u => run(rule.id, u, rule.id === 'C' ? 'control' : 'P')).filter(Boolean);
    if (rule.id === 'C') return `<li><p class="h-text">${esc(rule.label)}: every day, no signal</p>${rows.map(r => line(r, C_LIST[r.universe])).join('')}</li>`;
    return `<li><p class="h-text">${esc(rule.id)} · ${esc(rule.text)}</p>${rows.map(r => line(r, UNI_SHORT[r.universe])).join('')}</li>`;
  }).join('');
  $('#labFine').textContent = `$1,000 a trade from $10,000. The S&P is fully invested; a rule holds money a few hours a trade. ${L.variants_tried} versions tried, all in the file. Rules fixed before the test (${L.preregistered_sha}); the corrected list is a disclosed change made after it.`;
}
// Paper test (spec-audit CAP-18, story 30): S4 and S5 frozen at a tagged commit, traded forward with fake money one
// session at a time. Every number from results/paper/summary.json; LPP only.
function renderPaper(c) {
  const P = PAPER_TEST, show = !!P && c.key === 'lpp';
  $('#cPaper').hidden = !show;
  if (!show) return;
  const since = new Date(P.freeze.at).toLocaleDateString('en-CA', { timeZone: 'America/New_York' });
  $('#paperTitle').textContent = `Paper test since ${since}: ${P.days} day${P.days === 1 ? '' : 's'}`;
  $('#paperMeta').textContent = P.last_session ? `to ${P.last_session}` : '';
  $('#paperHead').innerHTML = P.days
    ? `His rules, frozen, on days nobody had seen. The S&amp;P made ${pct(P.benchmark.ret_pct)}.`
    : 'His rules are frozen. The first day counts after the next session.';
  $('#paperRules').innerHTML = P.days ? P.rules.map(r => {
    const c = r.costs.realistic;
    return `<li><p class="h-text">${esc(r.id)} · ${esc(r.label)}</p>
      <p class="h-num mono num"><b class="${c.ret_pct < 0 ? 'neg' : 'pos'}">${pct(c.ret_pct)}</b> · 2× costs ${pct(r.costs.x2.ret_pct)} · ${nTrades(r.trades)}${r.won_pct != null ? ` · won ${r.won_pct}%` : ''}</p>
      <p class="h-num mono num">${esc(r.word === 'Not enough trades' ? 'Too few trades yet' : r.word)}${r.vs_random ? ` · vs random: ${r.vs_random.pct_rank}th percentile` : ''}</p></li>`;
  }).join('') : '';
  $('#paperFine').textContent = `Fake money: $1,000 a trade from $10,000, realistic small-cap and borrow costs. Rules fixed at ${P.freeze.sha.slice(0, 7)} before any of these days; nothing is re-run.`;
}
let shownWord = null;
function renderVerdict(fresh) {
  const c = COURSES[cur], v = vm(c);
  $('#vCourse').textContent = c.r?.course_name || c.name;
  if (!v.tested) {
    root.style.setProperty('--word', 'var(--few)');
    $('#vHead').innerHTML = `Not tested yet. <span class="acc">Copying every trade now.</span>`;
    $('#vChip').textContent = 'Pending'; $('#vFine').textContent = ''; $('#vMeta').textContent = ''; $('#vSealed').hidden = true;
    ['cChart', 'cYear', 'cHis', 'cHelp', 'cLab', 'cPaper', 'cStrat', 'cBot', 'cMix', 'vAct'].forEach(id => { $('#' + id).hidden = true; });
    $('#vRanges').innerHTML = ''; return;
  }
  ['cChart', 'vAct'].forEach(id => { $('#' + id).hidden = false; });
  if (range !== 'all' && v.r.ranges && !v.r.ranges[range]) range = 'all';
  const k = cut(v);
  root.style.setProperty('--word', WORD_COLOR[wcls(k.word)]);
  $('#vCostBox').hidden = !v.cases;
  if (v.cases) {
    $('#vCosts').innerHTML = COST_CASES.filter(([id]) => v.cases[id]).map(([id, lab]) => `<button type="button" data-cost="${id}" aria-pressed="${v.costCase === id}">${lab}</button>`).join('');
    $('#vCostLine').innerHTML = range === 'all' ? costLine(v) : 'Time ranges use simple costs.';
  }
  $('#vHead').innerHTML = headline(v, k);
  $('#vChip').textContent = k.word;
  $('#vMeta').textContent = k.trades != null ? nTrades(k.trades) : '';
  const held = heldLine(v); $('#vSealed').hidden = !held; $('#vSealed').innerHTML = held;
  const how = range === 'all' ? howRow(howSure(`course:${c.key}`)) : ''; $('#vHow').hidden = !how; $('#vHow').innerHTML = how;
  $('#vFine').innerHTML = fineLine(v.r, v.s).split(' · ').filter(Boolean).map(b => `<span class="nw">${esc(b)}</span>`).join(' · ');
  const span = v.head.series?.dates;
  $('#vRanges').innerHTML = RANGES.map(([id, lab, mo]) => {
    const ok = !mo || (v.r.ranges ? !!v.r.ranges[id] : span && span.length && addMonths(span[0], mo) <= span[span.length - 1]);
    return ok ? `<button type="button" data-range="${id}" aria-pressed="${range === id}">${lab}</button>` : '';
  }).join('');
  const onlyAll = $$('#vRanges button').length < 2;
  $('#vRanges').hidden = onlyAll; $('#vRanges').previousElementSibling.hidden = onlyAll;
  if (fresh && !STILL) { const h = $('#vHead'); h.classList.remove('reveal'); void h.offsetWidth; h.classList.add('reveal'); }
  shownWord = k.word;
  drawMain(v, k);
  renderYears(v);
  renderHis(v);
  renderHelp(v);
  renderLab(c);
  renderPaper(c);
  renderStrats(c, v);
  renderBotMix(c);
  const h = sealedSays(v);
  $('#live').textContent = `${c.name}: ${k.word}. ${k.vs ? `${k.outcome}, ${k.vs}` : k.outcome}. ${kMoney(v.start)} became ${fmt.money(k.end)}; holding ${v.hold} made ${fmt.money(k.hold_end)}.${h ? ` Held-out months: ${h.word}.` : ''}`;
}
$('#vCosts').addEventListener('click', e => { const b = e.target.closest('[data-cost]'); if (!b) return; costCase = b.dataset.cost; store.set('cost', costCase); renderVerdict(false); });
$('#vRanges').addEventListener('click', e => { const b = e.target.closest('[data-range]'); if (!b || b.disabled) return; range = b.dataset.range; renderVerdict(false); });
$('#proofBtn').addEventListener('click', () => { openedByUser = true; location.hash = '#proof-' + KEYS[cur]; });
$('#kindBtn').addEventListener('click', () => { location.hash = '#learn-' + KEYS[cur]; });
$('#backBtn').addEventListener('click', () => { location.hash = '#verdict-' + KEYS[cur]; });

/* swipe between courses on phone */
let sw = null;
$('#s-verdict').addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' && !e.target.closest('.chips,.strats,.vchart')) sw = { x: e.clientX, y: e.clientY }; });
$('#s-verdict').addEventListener('pointerup', e => {
  if (!sw) return; const dx = e.clientX - sw.x, dy = e.clientY - sw.y; sw = null;
  if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) stepCourse(dx < 0 ? 1 : -1);
});

/* ---------- by kind of trade (CAP-6) ---------- */
function renderLearn(fresh) {
  const c = COURSES[cur], v = vm(c), list = $('#kinds');
  if (!v.tested) {
    $('#lSub').textContent = 'Not tested yet.'; $('#lDelay').hidden = true; list.innerHTML = '';
    return;
  }
  $('#lDelay').hidden = false;
  $('#lSub').textContent = `Each kind as its own ${kMoney(v.start)}. Holding ${v.hold}: ${pct(v.s.hold_ret_pct)}.`;
  const psl = proofSetLine(c); $('#lSet').hidden = !psl; $('#lSet').textContent = psl;
  const ordered = [v.head, ...v.ports.filter(p => p.id !== v.head.id)];
  list.innerHTML = ordered.map(p => {
    if (!p.testable) {
      if (!p.count) return '';
      return `<li><div class="kind"><span class="k-name">${esc(p.label)}</span><span class="k-sub cap num">${nTrades(p.count)} · can’t test yet: ${esc(p.why || 'no prices')}</span></div></li>`;
    }
    const a = p.at;
    if (!a || (p.id !== v.head.id && !a.trades)) return '';
    return `<li><button class="kind" type="button" data-trades="${esc(p.id)}" aria-label="${esc(p.label)}: ${pct(a.ret_pct)}, ${esc(a.word)}. Check its trades.">
      <span class="k-name">${esc(p.id === v.head.id ? 'Everything' : p.label)}</span>
      <span class="k-sub cap num">${nTrades(a.trades)} · ${kMoney(v.start)} → ${fmt.money(a.end)}</span>
      <span class="k-ret num w-${wcls(a.word)}">${pct(a.ret_pct)}<small>${esc(a.word)}</small></span>${icon('chevR')}</button></li>`;
  }).join('');
  if (fresh && !STILL) $$('#kinds li').forEach((li, i) => { li.style.animationDelay = (i * 50) + 'ms'; li.classList.add('fade'); });
}
$('#kinds').addEventListener('click', e => {
  const b = e.target.closest('[data-trades]'); if (!b) return;
  openedByUser = true; location.hash = `#trades-${KEYS[cur]}-${b.dataset.trades}`;
});

/* ---------- onboarding: arc carousel (CAP-4) ---------- */
const arc = $('#arc');
arc.innerHTML = COURSES.map((c, i) => {
  const v = vm(c);
  const found = v.tested ? `${nTrades(v.s.trades)} copied` : 'Not tested yet';
  return `<button class="acard" type="button" data-i="${i}" aria-pressed="true" aria-label="${esc(c.name)}, ${esc(c.kind)}, ${found}">
    <span class="chk">${icon('check')}</span>
    <span class="a-name">${esc(c.name)}</span>
    <span class="a-kind">${esc(c.kind)}</span>
    <span class="a-found cap num">${found}</span>
  </button>`;
}).join('');
const acards = $$('.acard', arc);
const A = { active: 0, raf: 0, cw: 260, gap: 18, R: 1170, step: .245 };
function arcGeom() {
  const vw = innerWidth, desk = DESK.matches;
  A.cw = desk ? 320 : Math.min(260, vw - 110);
  A.gap = desk ? 28 : 18;
  A.R = 3 * (desk ? Math.min(vw, 760) : vw);
  A.step = (A.cw + A.gap) / A.R;
  arc.style.setProperty('--cw', A.cw + 'px');
  arc.style.setProperty('--ch', (desk ? 320 : 260) + 'px');
  arc.style.setProperty('--R', A.R + 'px');
}
function arcRender() {
  const focus = Math.round(A.active);
  acards.forEach((el, i) => {
    const d = i - A.active;
    el.style.transform = `rotate(${(d * A.step).toFixed(5)}rad)`;
    el.style.opacity = (1 - Math.min(1, Math.abs(d)) * .45).toFixed(3);
    el.style.zIndex = String(10 - Math.round(Math.abs(d) * 2));
    el.tabIndex = i === focus ? 0 : -1;
    el.setAttribute('aria-current', String(i === focus));
  });
  $('#aPrev').disabled = focus <= 0;
  $('#aNext').disabled = focus >= acards.length - 1;
}
function springTo(target, v0 = 0) {            // Apple spring: damping 1.0 (no bounce), response 0.4s
  cancelAnimationFrame(A.raf);
  target = Math.max(0, Math.min(acards.length - 1, target));
  if (QUIET) { A.active = target; arcRender(); return; }
  const w = 2 * Math.PI / 0.4, x0 = A.active - target, t0 = performance.now();
  const stepF = now => {
    const t = (now - t0) / 1000, x = (x0 + (v0 + w * x0) * t) * Math.exp(-w * t);
    A.active = target + x; arcRender();
    if (Math.abs(x) > .0004 || t < .05) A.raf = requestAnimationFrame(stepF); else { A.active = target; arcRender(); }
  };
  A.raf = requestAnimationFrame(stepF);
}
function syncCards() {
  acards.forEach(el => el.setAttribute('aria-pressed', String(selected.has(KEYS[+el.dataset.i]))));
  $('#ob1Next').disabled = selected.size === 0;
}
let ad = null, aSuppress = false;
arc.addEventListener('pointerdown', e => {
  if (e.pointerType === 'mouse' && e.button !== 0) return;
  cancelAnimationFrame(A.raf);
  ad = { id: e.pointerId, x0: e.clientX, y0: e.clientY, a0: A.active, on: false, s: [[performance.now(), e.clientX]] };
});
arc.addEventListener('pointermove', e => {
  if (!ad || e.pointerId !== ad.id) return;
  const dx = e.clientX - ad.x0, dy = e.clientY - ad.y0;
  if (!ad.on) {
    if (Math.abs(dx) > 6 && Math.abs(dx) > Math.abs(dy)) { ad.on = true; ad.x0 = e.clientX; try { arc.setPointerCapture(e.pointerId); } catch (_) {} }
    else if (Math.abs(dy) > 10) ad = null;
    return;
  }
  const u = A.cw + A.gap, n = acards.length - 1, d = A.cw;
  let a = ad.a0 - (e.clientX - ad.x0) / u;
  if (a < 0) { const o = -a * u; a = -(o * d * .55 / (d + .55 * o)) / u; }
  if (a > n) { const o = (a - n) * u; a = n + (o * d * .55 / (d + .55 * o)) / u; }
  A.active = a; arcRender();
  ad.s.push([performance.now(), e.clientX]); if (ad.s.length > 6) ad.s.shift();
});
function arcEnd(e) {
  if (!ad || e.pointerId !== ad.id) return;
  const was = ad; ad = null;
  if (!was.on) return;
  aSuppress = true; setTimeout(() => { aSuppress = false; }, 0);
  const [t1, x1] = was.s[0], [t2, x2] = was.s[was.s.length - 1];
  const vel = (x2 - x1) / Math.max(1, t2 - t1) * 1000;
  const u = A.cw + A.gap, dx = x2 - was.x0;
  const projected = dx + (vel / 1000) * 0.998 / (1 - 0.998);
  springTo(Math.round(was.a0 - projected / u), -vel / u);
}
arc.addEventListener('pointerup', arcEnd);
arc.addEventListener('pointercancel', arcEnd);
arc.addEventListener('click', e => {
  if (aSuppress) return;
  const el = e.target.closest('.acard'); if (!el) return;
  const i = +el.dataset.i;
  if (i !== Math.round(A.active)) { springTo(i); return; }
  const k = KEYS[i];
  selected.has(k) ? selected.delete(k) : selected.add(k);
  store.set('picks', [...selected]);
  syncCards();
});
$('#aPrev').addEventListener('click', () => springTo(Math.round(A.active) - 1));
$('#aNext').addEventListener('click', () => springTo(Math.round(A.active) + 1));

/* ---------- proof (CAP-8) ---------- */
const wrap = $('#sheetWrap'), sheet = $('#sheet');
const link = (url, label) => url ? `<a class="p-link cap" href="${esc(url)}" target="_blank" rel="noopener">${label}${icon('ext')}</a>` : '';
const pending = what => `<p class="p-s cap">${what}: pending in PRISM.</p>`;
const has = x => x !== null && x !== undefined && x !== '';
// KB snippets can be raw markdown chunks: strip the marks, keep the first ~140 characters.
const clip = t => { const c = String(t || '').replace(/[#_*|>`]+/g, ' ').replace(/\s+/g, ' ').trim(); return c.length > 140 ? c.slice(0, 139).replace(/\s\S*$/, '') + '…' : c; };
function renderProof() {
  const c = COURSES[cur], v = vm(c);
  if (!v.tested) return;
  const r = v.r, s = v.s, col = PAPER[wcls(v.word)];
  $('#pSub').textContent = `${c.r.course_name || c.name} · ${kMoney(v.start)} fake money · ${month(r.window.start)} – ${month(r.window.end)} · entered ${delay} min late`;
  $('#pWord').textContent = v.word; root.style.setProperty('--word', WORD_COLOR[wcls(v.word)]);
  const swatch = (cl, dash) => `<svg viewBox="0 0 20 8" aria-hidden="true"><line x1="1" y1="4" x2="19" y2="4" stroke="${cl}" stroke-width="${dash ? 2 : 3}" stroke-linecap="round" ${dash ? 'stroke-dasharray="4 3"' : ''}/></svg>`;
  const sub = [nTrades(s.trades), s.won_pct != null && `won ${s.won_pct}%`, s.worst_drop_pct != null && `worst drop ${pct(s.worst_drop_pct)}`, s.peak_invested_usd > 0 && `most in use at once ${fmt.money(s.peak_invested_usd)}`].filter(Boolean).join(' · ');
  $('#pNums').innerHTML =
    `<div><span class="n-name">${swatch(col)}Copying every trade</span><span class="n-pct" style="color:${col}">${pct(s.ret_pct)}<small>${fmt.money(s.end)}</small></span><span class="n-sub cap">${sub}</span></div>` +
    `<div><span class="n-name">${swatch(HOLD_INK, true)}Holding ${esc(v.hold)}</span><span class="n-pct">${pct(s.hold_ret_pct)}<small>${fmt.money(s.hold_end)}</small></span><span class="n-sub cap">${esc(r.hold?.what || '')}</span></div>`;

  const P = proofFor(c), kb = P?.knowledge_base, rc = P?.root_cause, ev = P?.evaluator;
  const rules = (r.rules || []).slice(0, 6);
  const rulesHTML = rules.length ? `<ol class="rules">${rules.map((x, k) => `
      <li class="${x.testable === false ? 'vague' : ''}"><span class="r-n num">${k + 1}</span><div><p class="r-q">${esc(x.text)}</p>
      ${x.quote ? `<p class="r-quote cap">“${esc(x.quote)}”</p>` : ''}
      <p class="r-c cap num">${icon(/^(yt|lpp):/.test(x.cite?.source_id || '') ? 'play' : 'chat')}${esc(x.cite?.label || '')}${x.testable === false ? '<span class="tag">Can’t test</span>' : ''}</p></div></li>`).join('')}</ol>` : '';
  const hits = (kb?.hits || []).filter(h => has(h?.snippet));
  $('#pKB').innerHTML = `<h3 class="p-h">Knowledge Base<span class="by">PRISM</span></h3>
    <p class="p-s cap">The course rules the agent looked up</p>
    ${has(kb?.query) ? `<p class="kb-q cap">Searched “${esc(kb.query)}” · ${hits.length} hits ${link(kb.run_url, 'See the run')}</p>
      ${hits.length ? `<ol class="hits">${hits.slice(0, 5).map(h => `<li><p class="r-q">${esc(clip(h.snippet))}</p><p class="r-c cap">${icon('doc')}${esc(h.doc || '')}</p></li>`).join('')}</ol>` : ''}` : pending('The retrieval step')}
    ${rulesHTML ? `<h4 class="p-h4">Rules found, with sources</h4>${rulesHTML}` : ''}`;

  $('#pRC').innerHTML = `<h3 class="p-h">Root Cause<span class="by">PRISM</span></h3>
    <p class="p-s cap">Why the first version failed</p>
    ${has(rc?.our_sentence) ? `<p class="rc-q">${esc(rc.our_sentence)}</p>
      <p class="rc-fix cap num">${icon('wrench')}${[has(rc.failed_runs) && `${rc.failed_runs} failed runs`, has(rc.cluster) && `“${esc(rc.cluster)}”`, has(rc.tier) && esc(rc.tier)].filter(Boolean).join(' · ')}</p>
      ${has(rc.prism_cause) ? `<p class="p-s cap">PRISM: ${esc(rc.prism_cause)}</p>` : ''}${link(rc.url, 'See the cluster')}` : pending('The failure cluster')}`;

  // Headline: our code's check on the full output. PRISM's own score sits under it with its caveat.
  const prismScore = has(ev?.v1?.pass_pct) && has(ev?.v2?.pass_pct);
  const mirror = ev?.code_mirror && has(ev.code_mirror.v1_pass_pct) && has(ev.code_mirror.v2_pass_pct) ? ev.code_mirror : null;
  const a = mirror ? mirror.v1_pass_pct : prismScore ? ev.v1.pass_pct : null, b = mirror ? mirror.v2_pass_pct : prismScore ? ev.v2.pass_pct : null;
  const fr = has(ev?.failed_runs?.v1) && has(ev?.failed_runs?.v2) ? ev.failed_runs : null;
  const psl = proofSetLine(c);
  $('#pEV').innerHTML = `<h3 class="p-h">Evaluator<span class="by">${mirror ? 'Our code · full output' : 'PRISM'}</span></h3>
    ${psl ? `<p class="p-s cap mono num">${esc(psl)}</p>` : ''}
    ${has(a) ? `<div class="ev num"><b style="color:${PAPER.No}">${a}%</b>${icon('arrowR')}<b style="color:${PAPER.Yes}">${b}%</b><small>v1 → v2 · numbers grounded</small></div>
      <p class="ev-t"><b>${esc(ev.name || 'Score')}:</b> ${esc(ev.checks || '')}</p>
      ${fr ? `<p class="p-s cap mono num">Runs failing a code check: ${fr.v1} of ${fr.of} → ${fr.v2} of ${fr.of}</p>` : ''}
      ${mirror ? (prismScore ? `<div class="ev2 mono num"><span>PRISM’s own score</span><b>${ev.v1.pass_pct}% → ${ev.v2.pass_pct}%</b></div>
        ${ev.caveat ? `<p class="p-s cap">${esc(ev.caveat)}</p>` : ''}` : `<p class="p-s cap">PRISM’s own score: pending.</p>`) : (ev.caveat ? `<p class="p-s cap">${esc(ev.caveat)}</p>` : '')}
      ${ev.framing ? `<p class="p-s cap">${esc(ev.framing)}</p>` : ''}
      ${link(ev.url, 'See the evaluator in PRISM')}` : pending('The v1 → v2 score')}`;

  const se = s.sealed;
  if (se && r.window.sealed_from && r.window.sealed_from > r.window.start) {
    const mx = Math.max(Math.abs(se.ret_pct), Math.abs(se.hold_ret_pct), 0.1);
    const bar = (x, cl) => { const w = Math.abs(x) / mx * 50; return `<i style="background:${cl};width:${w}%;left:${x >= 0 ? 50 : 50 - w}%"></i>`; };
    const h = sealedSays(v);
    $('#pNew').innerHTML = `<h3 class="p-h">Newest months</h3><p class="p-s cap num">${month(r.window.sealed_from)} – ${month(r.window.end)} · kept sealed${has(se.trades) ? ` · ${nTrades(se.trades)}` : ''}</p>
      ${h ? `<p class="held"><b style="color:${WORD_COLOR[wcls(h.word)]}">${esc(h.word ?? '')}</b> · ${sentence(h)}</p>` : ''}
      <div class="nd num">
        <div class="nd-row"><span>Copying</span><span class="nd-bar">${bar(se.ret_pct, col)}</span><b>${pct(se.ret_pct)}</b></div>
        <div class="nd-row"><span>Holding ${esc(v.hold)}</span><span class="nd-bar">${bar(se.hold_ret_pct, HOLD_INK)}</span><b>${pct(se.hold_ret_pct)}</b></div>
      </div>`;
  } else $('#pNew').innerHTML = '';

  const untestable = v.ports.filter(p => !p.testable && p.count).map(p => `${p.count.toLocaleString('en-US')} ${p.label.toLowerCase()} trades not tested: ${p.why || 'no prices'}.`);
  const unk = [...untestable, ...(r.unknown || [])];
  $('#pUnknown').innerHTML = `<h3 class="p-h">What we don’t know</h3><ul class="unk">${unk.map(u => `<li>${icon('help')}<span>${esc(u)}</span></li>`).join('')}</ul>`;
  drawChart();
}
function drawChart() {
  const c = COURSES[cur], v = vm(c), host = $('#pChart');
  if (!v.tested) return;
  const S = v.head.series, course = S?.by_delay?.[dkey(S?.by_delay)], col = PAPER[wcls(v.word)];
  if (!S || !course || !S.hold || course.length < 2) { host.innerHTML = ''; return; }
  const W = Math.max(280, Math.round(host.clientWidth || 600)), H = W < 520 ? 190 : 210;
  const P = { l: 46, r: 8, t: 8, b: 28 }, all = course.concat(S.hold);
  const mn = Math.min(...all), mx = Math.max(...all);
  const step = [250, 500, 1000, 2000, 2500, 5000, 10000].find(x => (mx - mn) / x <= 5) || 10000;
  const lo = Math.floor(mn / step) * step, hi = Math.max(lo + step, Math.ceil(mx / step) * step), n = course.length - 1;
  const X = i => P.l + i * (W - P.l - P.r) / n, Y = val => P.t + (hi - val) * (H - P.t - P.b) / (hi - lo);
  const path = a => a.map((val, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(val).toFixed(1)}`).join('');
  let g = '';
  for (let val = lo; val <= hi + 1; val += step)
    g += `<line class="gl${val === v.start ? ' base' : ''}" x1="${P.l}" x2="${W - P.r}" y1="${Y(val).toFixed(1)}" y2="${Y(val).toFixed(1)}"/><text x="${P.l - 8}" y="${(Y(val) + 4).toFixed(1)}" text-anchor="end">$${(val / 1000).toLocaleString('en-US', { maximumFractionDigits: 2 })}k</text>`;
  const dates = S.dates || [];
  [[0, 'start'], [n, 'end']].forEach(([i, anchor]) => { if (dates[i]) g += `<text x="${X(i).toFixed(1)}" y="${H - 6}" text-anchor="${anchor}">${month(dates[i])}</text>`; });
  const end = (arr, cl) => `<circle cx="${X(n).toFixed(1)}" cy="${Y(arr[n]).toFixed(1)}" r="4" fill="${cl}" stroke="#1b1a19" stroke-width="2"/>`;
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${kMoney(v.start)} over time: copying ends at ${fmt.money(course[n])}, holding ${esc(v.hold)} at ${fmt.money(S.hold[n])}.">${g}
    <path d="${path(S.hold)}" fill="none" stroke="${HOLD_INK}" stroke-width="1.5" stroke-dasharray="5 4" stroke-linejoin="round"/>
    <path d="${path(course)}" fill="none" stroke="${col}" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round"/>
    ${end(S.hold, HOLD_INK)}${end(course, col)}</svg>`;
}

/* ---------- check any trade (CAP-7) ---------- */
const tWrap = $('#tradeWrap'), tSheet = $('#tSheet');
let tPort = null, tSel = 0, tKill = 0;
function tradesFor(c, pid) {
  const all = c.r?.trades || [];
  return pid === (c.r?.headline_portfolio || 'all') ? all : all.filter(x => x.portfolio === pid);
}
function renderTrades() {
  const c = COURSES[cur], v = vm(c);
  if (!v.tested) return;
  const p = v.ports.find(x => x.id === tPort) || v.head;
  const list = tradesFor(c, p.id);
  $('#tTitle').textContent = p.id === v.head.id ? 'Every trade' : p.label;
  $('#tSub').textContent = `${c.r.course_name || c.name} · entered ${delay} min after each post`;
  const total = p.at?.trades;
  $('#tListH').textContent = total && total > list.length ? `${list.length} of ${nTrades(total)}` : 'Trades';
  if (!list.length) {
    $('#tHead').innerHTML = `<p>No sample trades in the file for this kind.</p>`;
    $('#tList').innerHTML = ''; $('#tQuote').innerHTML = ''; $('#tLegend').textContent = '';
    destroyTrade(); $('#tChart').innerHTML = '';
    return;
  }
  tSel = Math.min(tSel, list.length - 1);
  const retCol = r => (r >= 0 ? PAPER.Yes : PAPER.No);
  $('#tList').innerHTML = list.map((x, i) => {
    const me = x.by_delay?.[dkey(x.by_delay)];
    return `<li><button type="button" class="t-row${i === tSel ? ' on' : ''}" data-t="${i}" aria-pressed="${i === tSel}">
      <b>${esc(x.ticker)}</b><span class="cap">${DAY.format(new Date(x.posted_at))}</span><span class="t-ret" style="color:${me ? retCol(me.ret_pct) : 'inherit'}">${me ? pct(me.ret_pct) : '—'}</span></button></li>`;
  }).join('');
  const x = list[tSel], me = x.by_delay?.[dkey(x.by_delay)];
  $('#tHead').innerHTML = `<span class="t-tick">${esc(x.ticker)}</span><span class="t-meta cap">${x.side === 'short' ? 'Short' : 'Long'} · posted ${DAY.format(new Date(x.posted_at))}, ${etTime(x.posted_at)} ET</span>
    ${me ? `<span class="t-res" style="color:${retCol(me.ret_pct)}">${pct(me.ret_pct)}</span>` : ''}`;
  $('#tLegend').textContent = me
    ? `In at ${fmt.price(me.entry)} (${etTime(me.entry_at)}), out at ${fmt.price(me.exit)} (${etTime(me.exit_at)})${me.assumed_exit ? ', exit assumed' : ''}. ${x.bars ? 'Minute bars.' : 'Line joins the prices at each delay.'}`
    : 'Not entered at this delay.';
  $('#tQuote').innerHTML = x.quote ? `<p>“${esc(x.quote)}”</p><footer class="cap">${icon(/^(yt|lpp):/.test(x.cite?.source_id || '') ? 'play' : 'chat')}${esc(x.cite?.label || '')}</footer>` : '';
  requestAnimationFrame(() => drawTrade($('#tChart'), x, +dkey(x.by_delay), PAPER[wcls(v.word)], fmt.price));
}
$('#tList').addEventListener('click', e => { const b = e.target.closest('[data-t]'); if (!b) return; tSel = +b.dataset.t; renderTrades(); });

/* ---------- sheets ---------- */
let lastFocus = null;
function openSheet(w, focusBtn) {
  clearTimeout(tKill);
  if (w.classList.contains('open')) return;
  lastFocus = document.activeElement;
  $('.sheet', w).scrollTop = 0;
  w.classList.add('open');
  if (openedByUser) setTimeout(() => focusBtn.focus({ preventScroll: true }), QUIET ? 0 : 120);
  openedByUser = false;
}
function closeSheet(w) {
  if (!w.classList.contains('open')) return;
  w.classList.remove('open');
  if (w === tWrap) { clearTimeout(tKill); tKill = setTimeout(destroyTrade, 460); }
  if (lastFocus && document.contains(lastFocus) && lastFocus.offsetParent) lastFocus.focus({ preventScroll: true });
}
wrap.addEventListener('click', e => { if (e.target.closest('[data-close]')) location.hash = '#verdict-' + KEYS[cur]; });
tWrap.addEventListener('click', e => { if (e.target.closest('[data-close]')) location.hash = '#learn-' + KEYS[cur]; });
[sheet, tSheet].forEach(sh => sh.addEventListener('keydown', e => {
  if (e.key !== 'Tab') return;
  const f = $$('button:not([disabled]),[href],input,[tabindex]:not([tabindex="-1"])', sh).filter(x => x.offsetParent);
  if (!f.length) return;
  if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
  else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
}));

/* ---------- onboarding run ---------- */
let runTimers = [];
const clearRun = () => { runTimers.forEach(clearTimeout); runTimers = []; };
function finishOnboarding() { onboarded = true; store.set('onboarded', true); store.set('picks', [...selected]); }
function startRun() {
  const items = $$('#runList li');
  const target = '#verdict-' + KEYS[visibleList()[0] ?? 0];
  if (STILL) { items.forEach(li => { li.dataset.state = 'done'; }); finishOnboarding(); location.replace(target); return; }
  items.forEach(li => { li.dataset.state = 'wait'; });
  items.forEach((li, k) => {
    runTimers.push(setTimeout(() => { li.dataset.state = 'now'; }, k * 650 + 60));
    runTimers.push(setTimeout(() => { li.dataset.state = 'done'; }, (k + 1) * 650 - 80));
  });
  runTimers.push(setTimeout(() => { finishOnboarding(); location.hash = target; }, items.length * 650 + 250));
}
$('#ob1Next').addEventListener('click', () => { if (selected.size) location.hash = '#onboard-2'; });
$('#ob2Next').addEventListener('click', () => { location.hash = '#onboard-3'; });

/* ---------- popovers, account, toast ---------- */
const dataPop = $('#dataPop'), menu = $('#menu'), dataPill = $('#dataPill'), avatarBtn = $('#avatarBtn');
function syncPill() {
  const scr = document.body.dataset.screen, r = COURSES[cur].r;
  const on = (scr === 'verdict' || scr === 'learn') && !!(r?.sample || r?.partial);
  dataPill.hidden = !on;
  if (!on) { dataPop.hidden = true; return; }
  $('#dataPillT').textContent = r.sample ? 'Sample data' : 'Partial data';
  dataPop.textContent = r.sample ? 'Made-up numbers to build the screens. Not a real test of this course yet.' : 'Not every post is priced yet. Numbers will move.';
}
function closePops() {
  dataPop.hidden = true; menu.hidden = true;
  dataPill.setAttribute('aria-expanded', 'false'); avatarBtn.setAttribute('aria-expanded', 'false');
}
const popOpen = () => !dataPop.hidden || !menu.hidden;
dataPill.addEventListener('click', e => {
  e.stopPropagation(); const open = dataPop.hidden; closePops();
  if (open) { dataPop.hidden = false; dataPill.setAttribute('aria-expanded', 'true'); }
});
avatarBtn.addEventListener('click', e => {
  e.stopPropagation(); const open = menu.hidden; closePops();
  if (open) { menu.hidden = false; avatarBtn.setAttribute('aria-expanded', 'true'); $('#pickAgain').focus({ preventScroll: true }); }
});
document.addEventListener('click', e => { if (popOpen() && !e.target.closest('.pop')) closePops(); });
let toastT = 0;
function toast(msg) {
  const el = $('#toast'); el.innerHTML = icon('check') + esc(msg); el.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(() => el.classList.remove('show'), 2400);
}
function showUser() {
  const ini = user?.initials || 'ME';
  [avatarBtn, $('#menuAvatar')].forEach(a => {
    a.textContent = user?.image ? '' : ini;
    a.style.backgroundImage = user?.image ? `url("${user.image}")` : '';
    a.classList.toggle('has-img', !!user?.image);
  });
  avatarBtn.setAttribute('aria-label', 'Account: ' + (user?.name || 'you'));
  $('#menuName').textContent = user?.name || 'You';
}
$('#pickAgain').addEventListener('click', () => { closePops(); location.hash = '#onboard-1'; });
$('#signOut').addEventListener('click', async () => {
  closePops();
  try { await signOut(); } catch (e) { console.warn(e); }
  user = null; showUser();
  location.hash = '#signin'; toast('Signed out');
});
const goBtn = $('#goBtn');
goBtn.addEventListener('click', async () => {
  goBtn.disabled = true; $('#siErr').hidden = true;
  try {
    const u = await signInWithGoogle();
    if (u) { user = u; showUser(); location.hash = onboarded ? '#verdict-' + KEYS[visibleList()[0] ?? 0] : '#onboard-1'; }
  } catch (e) {
    console.warn('Sign-in failed', e);
    $('#siErr').textContent = 'Sign-in didn’t work. Try again.'; $('#siErr').hidden = false;
  } finally { goBtn.disabled = false; }
});

/* ---------- keyboard ---------- */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (popOpen()) { closePops(); return; }
    if (wrap.classList.contains('open')) location.hash = '#verdict-' + KEYS[cur];
    if (tWrap.classList.contains('open')) location.hash = '#learn-' + KEYS[cur];
    return;
  }
  if (e.target.matches('input')) return;
  if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !wrap.classList.contains('open') && !tWrap.classList.contains('open') && !popOpen()) {
    const scr = document.body.dataset.screen, dir = e.key === 'ArrowRight' ? 1 : -1;
    if (scr === 'onboard-1') {
      e.preventDefault();
      const t = Math.max(0, Math.min(acards.length - 1, Math.round(A.active) + dir));
      springTo(t); acards[t].focus({ preventScroll: true }); return;
    }
    if (scr === 'verdict' || scr === 'learn') { e.preventDefault(); stepCourse(dir); }
  }
});

/* ---------- router ---------- */
const KEY_RE = KEYS.join('|');
function parse() {
  const h = (location.hash || '').replace(/^#/, '') || 'signin';
  let m = h.match(new RegExp(`^(verdict|proof|learn)-(${KEY_RE})$`));
  if (m) return { screen: m[1], course: m[2] };
  m = h.match(new RegExp(`^trades-(${KEY_RE})-([a-z0-9_]+)$`));
  if (m) return { screen: 'trades', course: m[1], port: m[2] };
  return { screen: ['signin', 'onboard-1', 'onboard-2', 'onboard-3'].includes(h) ? h : 'signin' };
}
function render() {
  if (!booted) return;
  let r = parse();
  if (!user && r.screen !== 'signin') { history.replaceState(null, '', '#signin'); r = { screen: 'signin' }; }
  else if (user && r.screen === 'signin') {
    history.replaceState(null, '', '#' + (onboarded ? 'verdict-' + KEYS[visibleList()[0] ?? 0] : 'onboard-1')); r = parse();
  }
  const prev = route; route = r;
  clearRun(); closePops();
  const scr = r.screen === 'proof' ? 'verdict' : r.screen === 'trades' ? 'learn' : r.screen;
  const screenChanged = document.body.dataset.screen !== scr;
  document.body.dataset.screen = scr;
  $$('.screen').forEach(s => { s.hidden = s.id !== 's-' + scr; });
  const courseChanged = r.course && KEYS.indexOf(r.course) !== cur;
  if (r.course) {
    if (!selected.has(r.course)) { selected.add(r.course); store.set('picks', [...selected]); syncCards(); }
    cur = KEYS.indexOf(r.course);
  }
  if (scr === 'verdict' || scr === 'learn') { syncSeg(!prev || !['verdict', 'proof', 'learn', 'trades'].includes(prev.screen)); syncDelay(); }
  if (scr === 'verdict') {
    renderVerdict(screenChanged || courseChanged);
    closeSheet(tWrap);
    if (r.screen === 'proof' && vm(COURSES[cur]).tested) { renderProof(); openSheet(wrap, $('#pClose')); } else closeSheet(wrap);
  } else {
    closeSheet(wrap);
    if (scr === 'learn') {
      if (screenChanged || courseChanged) renderLearn(true);
      if (r.screen === 'trades') {
        if (tPort !== r.port) { tPort = r.port; tSel = 0; }
        renderTrades(); openSheet(tWrap, $('#tClose'));
      } else closeSheet(tWrap);
    } else closeSheet(tWrap);
    if (scr === 'onboard-1') { syncCards(); arcGeom(); arcRender(); }
    if (scr === 'onboard-3') startRun();
  }
  syncPill();
  if (screenChanged) scrollTo(0, 0);
}
addEventListener('hashchange', render);
let rz = 0;
addEventListener('resize', () => {
  cancelAnimationFrame(rz);
  rz = requestAnimationFrame(() => {
    const scr = document.body.dataset.screen;
    if (scr === 'verdict' || scr === 'learn') syncSeg(true);
    if (scr === 'onboard-1') { arcGeom(); arcRender(); }
    if (wrap.classList.contains('open')) drawChart();
  });
});

/* ---------- boot ---------- */
syncCards(); arcGeom(); arcRender(); syncDelay();
$('#s-boot').hidden = false;
initAuth(u => {
  const was = user;
  user = u; showUser();
  if (!booted) { booted = true; render(); return; }
  if (!was && u) render();
  if (was && !u && document.body.dataset.screen !== 'signin') location.hash = '#signin';
}).catch(e => {
  console.warn('Auth failed to load', e);
  booted = true; render();
  $('#siErr').textContent = 'Sign-in is down right now.'; $('#siErr').hidden = false;
});
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { const scr = document.body.dataset.screen; if (scr === 'verdict' || scr === 'learn') syncSeg(true); });

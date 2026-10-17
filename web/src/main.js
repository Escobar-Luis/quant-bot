import './stamp.css';
import './app.css';
import { COURSE_META, latest, PROOF } from './data.js';
import { initAuth, signInWithGoogle, signOut, currentUser } from './auth.js';
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
  stampIc: '<path d="M9.5 12.5V9a2.5 2.5 0 1 1 5 0v3.5"/><rect x="4.5" y="12.5" width="15" height="4" rx="1"/><path d="M6 20h12"/>',
  trend: '<path d="M4 17l5.5-5.5 3.5 3.5L20 8"/><path d="M14.5 8H20v5.5"/>',
  doc: '<path d="M14 3.5H7.5A1.5 1.5 0 0 0 6 5v14a1.5 1.5 0 0 0 1.5 1.5h9A1.5 1.5 0 0 0 18 19V7.5z"/><path d="M14 3.5v4h4M9 12h6M9 15.5h6"/>',
  wrench: '<path d="M14.5 5.5a4 4 0 0 0 4.9 4.9l-8.6 8.6a2.1 2.1 0 0 1-3-3l8.6-8.6"/>',
  ext: '<path d="M13.5 5.5H18.5V10.5M18.5 5.5 11 13"/><path d="M16.5 13.5v4a1.5 1.5 0 0 1-1.5 1.5H7a1.5 1.5 0 0 1-1.5-1.5V9.5A1.5 1.5 0 0 1 7 8h4"/>',
  grid: '<rect x="4.5" y="4.5" width="6" height="6" rx="1.5"/><rect x="13.5" y="4.5" width="6" height="6" rx="1.5"/><rect x="4.5" y="13.5" width="6" height="6" rx="1.5"/><rect x="13.5" y="13.5" width="6" height="6" rx="1.5"/>'
};
const GOOGLE = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.7 3-4.3 3-7.3z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.8-1.8-5.6-4.1H3.1v2.6A10 10 0 0 0 12 22z"/><path fill="#FBBC05" d="M6.4 14c-.2-.6-.3-1.3-.3-2s.1-1.4.3-2V7.4H3.1a10 10 0 0 0 0 9.2z"/><path fill="#EA4335" d="M12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.9A10 10 0 0 0 3.1 7.4L6.4 10c.8-2.3 3-4.1 5.6-4.1z"/></svg>';
const icon = (n, cls = '') => n === 'google' ? GOOGLE : `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICON[n]}</svg>`;
$$('[data-ic]').forEach(el => { el.outerHTML = icon(el.dataset.ic); });
const esc = s => String(s ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

/* ---------- deep, calm fields (all text AA, secondary at ~72%) ---------- */
const W72 = 'rgba(255,255,255,.72)';
const TONE = {
  red: { field: '#8E2A20', deep: '#6E2019', on: '#FFFFFF', on2: W72, paper: '#A2301F' },
  rust: { field: '#8A3A16', deep: '#6C2C10', on: '#FFFFFF', on2: W72, paper: '#A0421A' },
  amber: { field: '#C98A15', deep: '#B47B12', on: '#1C1407', on2: 'rgba(28,20,7,.85)', paper: '#8E5C08' },
  olive: { field: '#4A5818', deep: '#3A4512', on: '#FFFFFF', on2: W72, paper: '#4E5D18' },
  green: { field: '#176039', deep: '#114A2B', on: '#FFFFFF', on2: W72, paper: '#1E6C3E' },
  grey: { field: '#55595F', deep: '#45484D', on: '#FFFFFF', on2: W72, paper: '#55595F' },
  ink: { field: '#15171C', deep: '#101216', on: '#FFFFFF', on2: W72, paper: '#1D1D1F' }
};
const WORD_TONE = { 'Yes': 'green', 'Barely': 'amber', 'No': 'red', 'Not enough trades': 'grey' };

const fmt = {
  pct: v => { const r = Math.round(v * 10) / 10, a = Math.abs(r); return (r > 0 ? '+' : r < 0 ? '−' : '') + (Number.isInteger(a) ? a : a.toFixed(1)) + '%'; },
  money: v => '$' + Math.round(v).toLocaleString('en-US'),
  int: v => String(Math.round(v))
};
const pct = fmt.pct;
const kMoney = v => (v % 1000 === 0 ? '$' + v / 1000 + 'k' : fmt.money(v));
// A part's colour follows its answer word, so a "No" never looks like a win.
function toneOf(a) {
  if (a.word === 'Yes') return 'green';
  if (a.word === 'Barely') return 'amber';
  if (a.word === 'No') return a.ret_pct < 0 ? 'red' : 'rust';
  return 'grey';
}
const vars = t => `--field:${t.field};--on:${t.on};--on2:${t.on2};--stampInk:${t.on}`;
const setVars = (el, t) => { el.style.setProperty('--field', t.field); el.style.setProperty('--on', t.on); el.style.setProperty('--on2', t.on2); el.style.setProperty('--stampInk', t.on); };
const cnt = (to, f, from = 0, cls = '') => `<span class="cnt ${cls}" data-to="${to}" data-from="${from}" data-fmt="${f}">${fmt[f](to)}</span>`;
const MONTH = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const month = d => MONTH.format(new Date(d + 'T00:00:00Z'));
const DAY = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York' });

/* ---------- count-up: tabular, ~900ms ease-out ---------- */
const easeOut = t => 1 - Math.pow(1 - t, 5);
function countUp(el, delay = 0) {
  const to = +el.dataset.to, from = +el.dataset.from || 0, f = fmt[el.dataset.fmt];
  cancelAnimationFrame(el._raf); clearTimeout(el._t);
  el.style.minWidth = ''; el.textContent = f(to);
  if (QUIET) return;
  el.style.minWidth = el.getBoundingClientRect().width + 'px';
  el.textContent = f(from);
  el._t = setTimeout(() => {
    const t0 = performance.now();
    const whole = Number.isInteger(to) && Number.isInteger(from);
    const tick = now => { const t = Math.min(1, (now - t0) / 900), v = from + (to - from) * easeOut(t); el.textContent = f(whole ? Math.round(v) : v); if (t < 1) el._raf = requestAnimationFrame(tick); };
    el._raf = requestAnimationFrame(tick);
  }, delay);
}
const countAll = (scope, delay = 0) => $$('.cnt', scope).forEach(el => countUp(el, delay + (+el.dataset.delay || 0)));

/* ---------- data: one view-model per course at the chosen delay ---------- */
const COURSES = COURSE_META.map(m => ({ ...m, r: latest(m.key) }));
const KEYS = COURSES.map(c => c.key);
const DELAYS = (COURSES.find(c => c.r)?.r.delays_min || [1, 3, 5, 10, 15, 30, 60]).slice().sort((a, b) => a - b);
const DEFAULT_DELAY = COURSES.find(c => c.r)?.r.default_delay_min || 5;
let delay = DELAYS.includes(store.get('delay', DEFAULT_DELAY)) ? store.get('delay', DEFAULT_DELAY) : DEFAULT_DELAY;

// The file's own delay key closest to the chosen one (every file should carry all seven).
function dkey(byDelay) {
  const ks = Object.keys(byDelay || {}).map(Number);
  if (!ks.length) return null;
  return String(ks.reduce((b, k) => (Math.abs(k - delay) < Math.abs(b - delay) ? k : b), ks[0]));
}
function portfolioAt(p) {
  if (!p.testable) return { ...p, at: null };
  const k = dkey(p.by_delay);
  return { ...p, at: k ? p.by_delay[k] : null };
}
function vm(c) {
  const r = c.r;
  if (!r) return { tested: false, tone: 'ink', word: 'Not yet' };
  const ports = (r.portfolios || []).map(portfolioAt);
  const head = ports.find(p => p.id === r.headline_portfolio && p.at) || ports.find(p => p.at);
  if (!head) return { tested: false, tone: 'ink', word: 'Not yet' };
  const s = head.at;
  const parts = ports.filter(p => p.at && p.id !== head.id);
  const best = parts.length ? parts.reduce((a, b) => (b.at.ret_pct - b.at.hold_ret_pct > a.at.ret_pct - a.at.hold_ret_pct ? b : a)) : null;
  return {
    tested: true, r, head, s, best, ports,
    word: s.word, tone: WORD_TONE[s.word] || 'grey',
    holdLabel: r.hold?.label || 'Just holding',
    start: r.money_start || 10000
  };
}
const nameOf = c => c.r?.course_name || c.name;

/* ---------- state ---------- */
let user = null, booted = false, cur = 0, route = null, openedByUser = false;
const selected = new Set((store.get('picks', null) || KEYS).filter(k => KEYS.includes(k)));
if (!selected.size) KEYS.forEach(k => selected.add(k));
let onboarded = store.get('onboarded', false);

/* ---------- field colour ---------- */
const meta = $('meta[name=theme-color]');
function setDrench(name, ms = 400) {
  const t = TONE[name];
  root.style.setProperty('--fd', ms + 'ms');
  root.classList.remove('no-tx');
  root.style.setProperty('--d-field', t.field);
  root.style.setProperty('--d-deep', t.deep);
  root.style.setProperty('--d-on', t.on);
  root.style.setProperty('--d-on2', t.on2);
  meta.setAttribute('content', t.field);
}
const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, p) => { const A = rgb(a), B = rgb(b); return `rgb(${A.map((v, k) => Math.round(v + (B[k] - v) * p)).join(',')})`; };
function dragDrench(to, p) {
  const A = TONE[vm(COURSES[cur]).tone], B = TONE[vm(COURSES[to]).tone];
  root.classList.add('no-tx');
  root.style.setProperty('--d-field', mix(A.field, B.field, p));
  root.style.setProperty('--d-deep', mix(A.deep, B.deep, p));
  root.style.setProperty('--d-on', mix(A.on, B.on, p));
  root.style.setProperty('--d-on2', p < .5 ? A.on2 : B.on2);
}

/* ---------- segmented controls with a sliding pill ---------- */
const ctabs = $('#ctabs'), vseg = $('#vseg');
ctabs.insertAdjacentHTML('beforeend', COURSES.map((c, i) => `<button type="button" role="tab" data-i="${i}" aria-selected="false">${esc(c.name)}</button>`).join(''));
function pillTo(seg, a, b = null, p = 0) {
  const pill = $('.seg-pill', seg), A = a.getBoundingClientRect(), S = seg.getBoundingClientRect();
  if (!A.width) return;
  let x = A.left - S.left, w = A.width;
  if (b) { const B = b.getBoundingClientRect(); x += (B.left - S.left - x) * p; w += (B.width - w) * p; }
  const inset = seg === vseg && !DESK.matches ? 4 : 3;
  pill.style.width = (w - inset * 2) + 'px';
  pill.style.transform = `translateX(${x + inset}px)`;
}
function syncTabs(instant) {
  const L = visibleList();
  $$('button', ctabs).forEach(b => { const i = +b.dataset.i; b.hidden = !L.includes(i); b.setAttribute('aria-selected', String(i === cur)); });
  const scr = document.body.dataset.screen;
  $$('button', vseg).forEach(b => b.setAttribute('aria-selected', String((b.dataset.view === 'learn') === (scr === 'learn'))));
  [ctabs, vseg].forEach(seg => {
    const on = $('button[aria-selected=true]', seg); if (!on) return;
    if (instant) seg.classList.add('dragging');
    pillTo(seg, on);
    if (instant) { void seg.offsetWidth; seg.classList.remove('dragging'); }
  });
  syncSample();
}
ctabs.addEventListener('click', e => { const b = e.target.closest('button[data-i]'); if (b) setCourse(+b.dataset.i); });
$$('button', vseg).forEach(b => b.addEventListener('click', () => {
  const key = COURSES[cur].key;
  if (b.dataset.view === 'learn' && document.body.dataset.screen === 'verdict') goLearn();
  else location.hash = '#' + b.dataset.view + '-' + key;
}));

/* ---------- the delay slider (CAP-1): no network, just the file's numbers ---------- */
const delayIdx = () => Math.max(0, DELAYS.indexOf(delay));
const delayHTML = id => `<div class="delay" data-delay>
    <label class="dl-label num" for="${id}"><span>Got in</span> <b class="dl-v">${delay} min</b> <span>after each post</span></label>
    <input class="dl-range" id="${id}" type="range" min="0" max="${DELAYS.length - 1}" step="1" value="${delayIdx()}" aria-valuetext="${delay} minutes after each post">
    <div class="dl-ticks cap num" aria-hidden="true">${DELAYS.map(d => `<span>${d}</span>`).join('')}</div>
  </div>`;
function syncDelayControls() {
  $$('[data-delay]').forEach(w => {
    $('.dl-v', w).textContent = delay + ' min';
    const inp = $('.dl-range', w);
    if (+inp.value !== delayIdx()) inp.value = delayIdx();
    inp.setAttribute('aria-valuetext', `${delay} minutes after each post`);
    inp.style.setProperty('--p', (delayIdx() / (DELAYS.length - 1) * 100) + '%');
  });
}
document.addEventListener('input', e => {
  if (!e.target.matches('.dl-range')) return;
  const d = DELAYS[+e.target.value];
  if (d === delay) return;
  delay = d; store.set('delay', d);
  syncDelayControls();
  onDelay();
});

/* ---------- onboarding: arc carousel ---------- */
const arc = $('#arc');
arc.innerHTML = COURSES.map((c, i) => {
  const v = vm(c);
  const found = v.tested ? `${v.s.trades.toLocaleString('en-US')} trades copied` : 'Not tested yet';
  return `<button class="acard" type="button" data-i="${i}" aria-pressed="true" aria-label="${esc(c.name)}, ${esc(c.kind)}, ${found}">
    <span class="chk">${icon('check')}</span>
    <span class="a-name">${esc(c.name)}</span>
    <span class="a-kind">${esc(c.kind)}</span>
    <span class="a-found cap num">${found}</span>
  </button>`;
}).join('');
const acards = $$('.acard', arc);
const A = { active: 0, raf: 0, cw: 270, gap: 18, R: 1170, step: .245 };
function arcGeom() {
  const vw = innerWidth, desk = DESK.matches;
  A.cw = desk ? 340 : Math.min(270, vw - 110);
  A.gap = desk ? 28 : 18;
  A.R = 3 * (desk ? Math.min(vw, 760) : vw);
  A.step = (A.cw + A.gap) / A.R;
  arc.style.setProperty('--cw', A.cw + 'px');
  arc.style.setProperty('--ch', (desk ? 360 : 280) + 'px');
  arc.style.setProperty('--R', A.R + 'px');
}
function arcRender() {
  const focus = Math.round(A.active);
  acards.forEach((el, i) => {
    const d = i - A.active;
    el.style.transform = `rotate(${(d * A.step).toFixed(5)}rad)`;
    el.style.opacity = (1 - Math.min(1, Math.abs(d)) * .5).toFixed(3);
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
  acards.forEach(el => el.setAttribute('aria-pressed', String(selected.has(COURSES[+el.dataset.i].key))));
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
  const v = (x2 - x1) / Math.max(1, t2 - t1) * 1000;
  const u = A.cw + A.gap, dx = x2 - was.x0;
  const projected = dx + (v / 1000) * 0.998 / (1 - 0.998);
  springTo(Math.round(was.a0 - projected / u), -v / u);
}
arc.addEventListener('pointerup', arcEnd);
arc.addEventListener('pointercancel', arcEnd);
arc.addEventListener('click', e => {
  if (aSuppress) return;
  const el = e.target.closest('.acard'); if (!el) return;
  const i = +el.dataset.i;
  if (i !== Math.round(A.active)) { springTo(i); return; }
  const k = COURSES[i].key;
  selected.has(k) ? selected.delete(k) : selected.add(k);
  store.set('picks', [...selected]);
  syncCards(); syncDeck();
});
$('#aPrev').addEventListener('click', () => springTo(Math.round(A.active) - 1));
$('#aNext').addEventListener('click', () => springTo(Math.round(A.active) + 1));

/* ---------- verdict deck (CAP-5) ---------- */
const deck = $('#deck');
deck.innerHTML = COURSES.map((c, i) => `<article class="slide" data-i="${i}" aria-roledescription="slide" aria-label="${esc(c.name)}">
    <div class="card">
      <div class="v-main">
        <p class="v-claim">Beats just holding?</p>
        <div class="v-stampbox"><span class="sr">${esc(c.name)}, answer: </span><span class="stamp xl" data-fit></span></div>
        <div class="v-foot">
          <div class="v-left">
            <p class="v-line num"></p>
            ${delayHTML('dl-' + c.key)}
            <p class="v-note cap">Fake money · not advice</p>
          </div>
          <button class="see press-fb" type="button" data-why>See the proof</button>
        </div>
      </div>
      <button class="stub press-fb" type="button" data-learn></button>
    </div>
  </article>`).join('');
const slides = $$('.slide', deck);

function fillSlide(el, c, animateNums) {
  const v = vm(c), t = TONE[v.tone];
  setVars(el, t);
  const st = $('.stamp.xl', el);
  st.textContent = v.word;
  const line = $('.v-line', el), stub = $('.stub', el), see = $('[data-why]', el), dl = $('[data-delay]', el);
  el.classList.toggle('untested', !v.tested);
  if (!v.tested) {
    line.innerHTML = `<span>Not tested yet.</span> <span>Copying every trade now.</span>`;
    stub.hidden = true; see.hidden = true; dl.hidden = true;
    return v;
  }
  stub.hidden = false; see.hidden = false; dl.hidden = false;
  const s = v.s;
  line.innerHTML = `<span>${kMoney(v.start)} became ${animateNums ? cnt(s.end, 'money') : fmt.money(s.end)}.</span> <span>${esc(v.holdLabel)} made ${animateNums ? cnt(s.hold_end, 'money') : fmt.money(s.hold_end)}.</span>`;
  if (v.best) {
    const b = v.best.at, bt = TONE[toneOf(b)];
    setVars(stub, bt);
    stub.setAttribute('aria-label', `${v.best.label}: ${pct(b.ret_pct)}, ${b.word}. See each kind of trade.`);
    stub.innerHTML = `<span class="stub-label">${esc(v.best.label)} ${icon('chevR')}</span>
      <span class="stub-pct num">${animateNums ? cnt(b.ret_pct, 'pct') : pct(b.ret_pct)}</span>
      <span class="stamp sm">${esc(b.word)}</span>
      ${scoreHTML(animateNums)}`;
  } else {
    setVars(stub, TONE.ink);
    stub.innerHTML = `<span class="stub-label">Each kind of trade ${icon('chevR')}</span>${scoreHTML(animateNums)}`;
  }
  return v;
}
function scoreHTML(animateNums) {
  const ev = PROOF?.evaluator;
  if (!ev?.v1 || !ev?.v2) return '';
  const a = ev.v1.pass_pct, b = ev.v2.pass_pct;
  return `<span class="score num"><span class="k">PRISM check</span><b>${animateNums ? cnt(a, 'int') : a}</b>${icon('arrowR')}<b>${animateNums ? cnt(b, 'int', a) : b}</b></span>`;
}

const visibleList = () => COURSES.map((c, i) => i).filter(i => selected.has(COURSES[i].key));
function neighbor(dir) {
  const L = visibleList(), n = L.length;
  if (n < 2) return null;
  let k = L.indexOf(cur) + dir;
  if (n >= 3) k = (k + n) % n; else if (k < 0 || k >= n) return null;
  return L[k];
}
function posOf(i) {
  const L = visibleList(), n = L.length, a = L.indexOf(i), b = L.indexOf(cur);
  if (a < 0) return null;
  let d = a - b;
  if (n >= 3) { d = ((d % n) + n) % n; if (d > n / 2) d -= n; }
  return d;
}
function geom() {
  const vw = deck.clientWidth || innerWidth, desk = DESK.matches;
  const W = desk ? Math.min(1180, vw - 240) : vw, G = desk ? 32 : 0;
  return { vw, W, G, left: (vw - W) / 2, desk };
}
const lastPos = {};
function layoutDeck(animate, dx = 0) {
  const g = geom();
  slides.forEach((el, i) => {
    const p = posOf(i);
    if (p === null) { el.hidden = true; lastPos[i] = undefined; return; }
    el.hidden = false;
    const jump = lastPos[i] !== undefined && Math.abs(lastPos[i] - p) > 1;
    el.style.transition = (!animate || jump || QUIET) ? 'none' : '';
    el.style.width = g.W + 'px';
    const x = g.left + p * (g.W + g.G) + dx;
    el.style.transform = `translate3d(${x.toFixed(1)}px,0,0) scale(${g.desk && p !== 0 ? .94 : 1})`;
    el.classList.toggle('is-active', p === 0);
    el.setAttribute('aria-hidden', p === 0 ? 'false' : 'true');
    $$('button,input', el).forEach(b => { b.tabIndex = p === 0 ? 0 : -1; });
    lastPos[i] = p;
  });
}
function syncDeck() { syncTabs(true); }
function press(el, delayMs) {
  el.style.setProperty('--pd', delayMs + 'ms');
  el.classList.remove('press'); void el.offsetWidth; el.classList.add('press');
  clearTimeout(el._pt); el._pt = setTimeout(() => el.classList.remove('press'), delayMs + 1200);
  countAll(el, delayMs);
}
function markStamped(doPress, delayMs = 300) {
  slides.forEach((el, i) => {
    if (STILL) { el.classList.add('is-stamped'); return; }
    if (i === cur) { el.classList.add('is-stamped'); if (doPress) press(el, delayMs); }
    else el.classList.remove('is-stamped', 'press');
  });
}
function fitStamps() {
  const max = DESK.matches ? 290 : 128, rad = 4 * Math.PI / 180, c = Math.cos(rad), s = Math.sin(rad);
  $$('.stamp[data-fit]', deck).forEach(st => {
    const box = st.parentElement, bw = box.clientWidth, bh = box.clientHeight;
    if (!bw || !bh) return;
    st.style.fontSize = '100px';
    const w = st.offsetWidth, h = st.offsetHeight;
    const k = Math.min(bw * .92 / (w * c + h * s), bh * .9 / (w * s + h * c));
    st.style.fontSize = Math.max(40, Math.min(max, 100 * k)).toFixed(1) + 'px';
  });
}
const live = $('#live');
function setCourse(i) {
  const scr = document.body.dataset.screen;
  if (i === cur) { if (scr === 'verdict') { layoutDeck(true); setDrench(vm(COURSES[cur]).tone); syncTabs(); } return; }
  cur = i;
  const c = COURSES[i], v = vm(c);
  live.textContent = `${c.name}: ${v.word}`;
  if (scr === 'learn') {
    history.replaceState(null, '', '#learn-' + c.key); route = { screen: 'learn', course: c.key };
    syncTabs(); renderLearn(false); return;
  }
  history.replaceState(null, '', '#verdict-' + c.key); route = { screen: 'verdict', course: c.key };
  fillSlide(slides[i], c, true);
  layoutDeck(true);
  if (REDUCE) { slides[i].classList.remove('fade'); void slides[i].offsetWidth; slides[i].classList.add('fade'); }
  setDrench(v.tone, 400);
  syncTabs();
  fitStamps();
  markStamped(true, 220);
}
const stepCourse = dir => { const t = neighbor(dir); if (t !== null) setCourse(t); };

// Delay moved: numbers update in place; the stamp presses again only if the word changed.
function onDelay() {
  const scr = document.body.dataset.screen;
  if (scr === 'verdict') {
    const was = $('.stamp.xl', slides[cur]).textContent;
    slides.forEach((el, i) => { if (i !== cur) fillSlide(el, COURSES[i], false); });
    const v = fillSlide(slides[cur], COURSES[cur], false);
    if (v.word !== was) { fitStamps(); setDrench(v.tone, 300); if (!STILL) press(slides[cur], 0); live.textContent = `${COURSES[cur].name}: ${v.word}`; }
  } else if (scr === 'learn') renderLearn(false, true);
}

/* swipe between courses */
let drag = null, suppress = false;
deck.addEventListener('pointerdown', e => {
  if (e.pointerType === 'mouse' && e.button !== 0) return;
  if (e.target.closest('[data-delay]')) return;
  drag = { id: e.pointerId, x0: e.clientX, y0: e.clientY, dx: 0, t0: performance.now(), on: false };
});
deck.addEventListener('pointermove', e => {
  if (!drag || e.pointerId !== drag.id) return;
  const dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
  if (!drag.on) {
    if (Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy) * 1.2) {
      drag.on = true; drag.x0 = e.clientX; drag.t0 = performance.now();
      try { deck.setPointerCapture(e.pointerId); } catch (_) {}
      ctabs.classList.add('dragging');
    } else if (Math.abs(dy) > 12) drag = null;
    return;
  }
  const g = geom(), raw = e.clientX - drag.x0, target = neighbor(raw < 0 ? 1 : -1);
  const d = target === null ? (raw * g.W * .55) / (g.W + .55 * Math.abs(raw)) : raw;
  drag.dx = d;
  layoutDeck(false, d);
  if (target !== null) {
    const p = Math.min(1, Math.abs(d) / g.W);
    dragDrench(target, p);
    pillTo(ctabs, $(`button[data-i="${cur}"]`, ctabs), $(`button[data-i="${target}"]`, ctabs), p);
  }
});
function endDrag(e, cancel) {
  if (!drag || e.pointerId !== drag.id) return;
  const was = drag; drag = null;
  if (!was.on) return;
  ctabs.classList.remove('dragging');
  suppress = true; setTimeout(() => { suppress = false; }, 0);
  const g = geom(), v = was.dx / Math.max(1, performance.now() - was.t0);
  const go = !cancel && (Math.abs(was.dx) > g.W * .2 || (Math.abs(v) > .45 && Math.abs(was.dx) > 30));
  const t = go ? neighbor(was.dx < 0 ? 1 : -1) : null;
  if (t !== null) setCourse(t); else { layoutDeck(true); setDrench(vm(COURSES[cur]).tone); syncTabs(); }
}
deck.addEventListener('pointerup', e => endDrag(e, false));
deck.addEventListener('pointercancel', e => endDrag(e, true));
deck.addEventListener('click', e => {
  if (suppress) { e.preventDefault(); e.stopPropagation(); return; }
  const sl = e.target.closest('.slide'); if (!sl) return;
  const i = +sl.dataset.i;
  if (i !== cur) { e.preventDefault(); e.stopPropagation(); setCourse(i); }
}, true);
deck.addEventListener('click', e => {
  if (e.target.closest('[data-why]')) { openedByUser = true; location.hash = '#proof-' + COURSES[cur].key; }
  else if (e.target.closest('[data-learn]')) goLearn();
});

/* stub -> learning, as one shared element */
function goLearn() {
  const key = COURSES[cur].key;
  const stub = $('.slide.is-active .stub', deck);
  if (!document.startViewTransition || QUIET || !stub || stub.hidden) { location.hash = '#learn-' + key; return; }
  stub.style.viewTransitionName = 'better';
  const vt = document.startViewTransition(() => { history.pushState(null, '', '#learn-' + key); render(true); });
  vt.finished.finally(() => { stub.style.viewTransitionName = ''; $$('.band', $('#bands')).forEach(b => { b.style.viewTransitionName = ''; }); });
}

/* ---------- learning: each kind of trade as its own $10k (CAP-6) ---------- */
$('#lDelay').innerHTML = delayHTML('dl-learn');
function renderLearn(vt, quietNums = false) {
  const c = COURSES[cur], v = vm(c);
  const list = $('#bands');
  if (!v.tested) {
    $('#lHoldK').textContent = 'Not tested yet'; $('#lHold').textContent = '';
    $('#lDelay').hidden = true;
    list.innerHTML = `<li class="band" style="${vars(TONE.grey)}"><div class="band-in"><div class="b-main"><span class="b-text">No results file for ${esc(c.name)} yet.</span></div></div></li>`;
    return;
  }
  $('#lDelay').hidden = false;
  $('#lHoldK').textContent = v.holdLabel;
  $('#lHold').textContent = pct(v.s.hold_ret_pct);
  const ordered = [v.head, ...v.ports.filter(p => p.id !== v.head.id)];
  const n = x => (quietNums ? fmt.pct(x) : cnt(x, 'pct'));
  let html = '';
  ordered.forEach((p, k) => {
    if (!p.testable) {
      html += `<li class="band" data-k="${k}" style="${vars(TONE.grey)}"><div class="band-in">
        <span class="b-step num">${(p.count ?? 0).toLocaleString('en-US')} trades</span>
        <div class="b-main"><span class="b-text">${esc(p.label)}</span>
          <span class="b-why"><span class="b-rej">Can’t test yet</span>${esc(p.why || '')}</span></div>
        </div></li>`;
      return;
    }
    if (!p.at) return;
    const a = p.at, t = TONE[toneOf(a)];
    const vtName = vt && k === 1 ? ' data-vt="1"' : '';
    html += `<li class="band"${vtName}><button class="band-btn" type="button" data-trades="${esc(p.id)}" style="${vars(t)}" aria-label="${esc(p.label)}: ${pct(a.ret_pct)}, ${esc(a.word)}. Check its trades."><div class="band-in">
      <span class="b-step num">${a.trades.toLocaleString('en-US')} trades<span class="b-tag">${esc(a.word)}</span></span>
      <div class="b-main"><span class="b-text">${esc(p.label)}</span>
        <span class="b-why num">${kMoney(v.start)} became ${fmt.money(a.end)}${a.won_pct != null ? ` · won ${a.won_pct}%` : ''}</span></div>
      <span class="b-res num">${n(a.ret_pct)}</span>
      <span class="b-prism num">${p.id === v.head.id ? 'Headline' : 'Check trades'} ${icon('chevR')}</span>
    </div></button></li>`;
  });
  list.innerHTML = html;
  const vtBand = $('.band[data-vt]', list);
  if (vtBand) vtBand.style.viewTransitionName = 'better';
  if (quietNums) return;
  $$('.band', list).forEach((b, i) => {
    if (b === vtBand) return;
    if (!STILL) { b.style.setProperty('--sd', (i * 50) + 'ms'); b.classList.add('up'); }
    countAll(b, i * 50 + 60);
  });
}
$('#bands').addEventListener('click', e => {
  const b = e.target.closest('[data-trades]'); if (!b) return;
  location.hash = `#trades-${COURSES[cur].key}-${b.dataset.trades}`;
});

/* ---------- proof (CAP-8) ---------- */
const wrap = $('#sheetWrap'), sheet = $('#sheet');
const link = (url, label = 'Open in PRISM') => url ? `<a class="p-link cap" href="${esc(url)}" target="_blank" rel="noopener">${label}${icon('ext')}</a>` : '';
const pending = what => `<p class="p-s cap">${what} lands here from PRISM soon.</p>`;
function renderProof() {
  const c = COURSES[cur], v = vm(c), t = TONE[v.tone];
  if (!v.tested) return;
  const r = v.r, s = v.s;
  $('#pSub').textContent = `${nameOf(c)} · ${kMoney(v.start)} fake money · ${month(r.window.start)} – ${month(r.window.end)} · got in ${delay} min late`;
  const ps = $('#pStamp'); ps.textContent = v.word; ps.style.setProperty('--stampInk', t.paper);
  const sw = (col, dash) => `<svg viewBox="0 0 20 8" aria-hidden="true"><line x1="1" y1="4" x2="19" y2="4" stroke="${col}" stroke-width="${dash ? 2 : 3}" stroke-linecap="round" ${dash ? 'stroke-dasharray="4 3"' : ''}/></svg>`;
  const sub = [`${s.trades.toLocaleString('en-US')} trades`, s.won_pct != null && `won ${s.won_pct}%`, s.worst_drop_pct != null && `worst drop ${pct(s.worst_drop_pct)}`, s.not_triggered ? `${s.not_triggered} never triggered` : null].filter(Boolean).join(' · ');
  $('#pNums').innerHTML =
    `<div><span class="n-name">${sw(t.paper)}Copying every trade</span><span class="n-pct" style="color:${t.paper}">${pct(s.ret_pct)}<small>${fmt.money(s.end)}</small></span><span class="n-sub cap">${sub}</span></div>` +
    `<div><span class="n-name">${sw('#1D1D1F', true)}${esc(v.holdLabel)}</span><span class="n-pct">${pct(s.hold_ret_pct)}<small>${fmt.money(s.hold_end)}</small></span><span class="n-sub cap">${esc(r.hold?.what || '')}</span></div>`;

  const kb = PROOF?.knowledge_base;
  const rules = (r.rules || []).slice(0, 6);
  const rulesHTML = rules.length ? `<ol class="rules">${rules.map((x, k) => `
      <li class="${x.testable === false ? 'vague' : ''}"><span class="r-n num">${k + 1}</span><div><p class="r-q">${esc(x.text)}</p>
      ${x.quote ? `<p class="r-quote cap">“${esc(x.quote)}”</p>` : ''}
      <p class="r-c cap num">${icon(/^yt:/.test(x.cite?.source_id || '') ? 'play' : 'chat')}${esc(x.cite?.label || '')}${x.testable === false ? '<span class="tag">Can’t test</span>' : ''}</p></div></li>`).join('')}</ol>` : '';
  const hits = kb?.hits?.length ? `<ol class="hits">${kb.hits.slice(0, 5).map(h => `<li><p class="r-q">${esc(h.snippet)}</p><p class="r-c cap">${icon('doc')}${esc(h.doc)}</p></li>`).join('')}</ol>` : '';
  $('#pKB').innerHTML = `<h3 class="p-h">Knowledge Base<span class="by">PRISM</span></h3>
    <p class="p-s cap">The course rules the agent looked up</p>
    ${kb ? `<p class="kb-q cap">Searched “${esc(kb.query)}” · ${kb.hits?.length || 0} hits ${link(kb.run_url, 'See the run')}</p>${hits}` : pending('The retrieval step')}
    ${rulesHTML ? `<h4 class="p-h4">Rules found, with sources</h4>${rulesHTML}` : ''}`;

  const rc = PROOF?.root_cause;
  $('#pRC').innerHTML = `<h3 class="p-h">Root Cause<span class="by">PRISM</span></h3>
    <p class="p-s cap">Why the first version failed</p>
    ${rc ? `<p class="rc-q">${esc(rc.our_sentence)}</p>
      <p class="rc-fix cap num">${icon('wrench')}${rc.failed_runs} failed runs · “${esc(rc.cluster)}” · ${esc(rc.tier)}</p>
      ${rc.prism_cause ? `<p class="p-s cap">PRISM: ${esc(rc.prism_cause)}</p>` : ''}${link(rc.url, 'See the cluster')}` : pending('The failure cluster')}`;

  const ev = PROOF?.evaluator;
  $('#pEV').innerHTML = `<h3 class="p-h">Evaluator<span class="by">PRISM</span></h3>
    ${ev?.v1 && ev?.v2 ? `<div class="ev num"><b style="color:${TONE.red.paper}">${cnt(ev.v1.pass_pct, 'int')}%</b>${icon('arrowR')}<b style="color:${TONE.green.paper}">${cnt(ev.v2.pass_pct, 'int', ev.v1.pass_pct)}%</b><small>v1 → v2 · ${esc(ev.inputs || 'same inputs')}</small></div>
      <p class="ev-t"><b>${esc(ev.name)}:</b> ${esc(ev.checks)}</p>${link(ev.url, 'See the scores')}` : pending('The v1 → v2 score')}`;

  const se = s.sealed;
  if (se && r.window.sealed_from) {
    const mx = Math.max(Math.abs(se.ret_pct), Math.abs(se.hold_ret_pct), 0.1);
    const bar = (x, col) => { const w = Math.abs(x) / mx * 50; return `<i style="background:${col};width:${w}%;left:${x >= 0 ? 50 : 50 - w}%"></i>`; };
    $('#pNew').innerHTML = `<h3 class="p-h">Newest months</h3><p class="p-s cap">${month(r.window.sealed_from)} – ${month(r.window.end)} · kept sealed</p>
      <div class="nd num">
        <div class="nd-row"><span>Copying</span><span class="nd-bar">${bar(se.ret_pct, t.paper)}</span><b>${pct(se.ret_pct)}</b></div>
        <div class="nd-row"><span>${esc(v.holdLabel)}</span><span class="nd-bar">${bar(se.hold_ret_pct, '#1D1D1F')}</span><b>${pct(se.hold_ret_pct)}</b></div>
      </div>`;
  } else $('#pNew').innerHTML = '';

  const untestable = v.ports.filter(p => !p.testable).map(p => `${(p.count ?? 0).toLocaleString('en-US')} ${p.label.toLowerCase()} trades not tested: ${p.why || 'no prices'}.`);
  const unk = [...untestable, ...(r.unknown || [])];
  $('#pUnknown').innerHTML = `<h3 class="p-h">What we don’t know</h3><ul class="unk">${unk.map(u => `<li>${icon('help')}<span>${esc(u)}</span></li>`).join('')}</ul>`;
  drawChart();
}
function drawChart() {
  const c = COURSES[cur], v = vm(c), host = $('#pChart');
  if (!v.tested) return;
  const t = TONE[v.tone], S = v.head.series;
  const course = S?.by_delay?.[dkey(S?.by_delay)];
  if (!S || !course || !S.hold || course.length < 2) { host.innerHTML = ''; return; }
  const W = Math.max(280, Math.round(host.clientWidth || 600)), H = W < 520 ? 190 : 200;
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
  const end = (a, col) => `<circle cx="${X(n).toFixed(1)}" cy="${Y(a[n]).toFixed(1)}" r="4" fill="${col}" stroke="#FBFBFD" stroke-width="2"/>`;
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${kMoney(v.start)} over time: copying ends at ${fmt.money(course[n])}, ${esc(v.holdLabel.toLowerCase())} at ${fmt.money(S.hold[n])}.">${g}
    <path d="${path(S.hold)}" fill="none" stroke="#1D1D1F" stroke-width="1.75" stroke-dasharray="5 4" stroke-linejoin="round"/>
    <path d="${path(course)}" fill="none" stroke="${t.paper}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
    ${end(S.hold, '#1D1D1F')}${end(course, t.paper)}</svg>`;
}

/* ---------- check any trade (CAP-7) ---------- */
const tWrap = $('#tradeWrap'), tSheet = $('#tSheet');
let tPort = null, tSel = 0;
function tradesFor(c, pid) {
  const all = c.r?.trades || [];
  return pid === (c.r?.headline_portfolio || 'all') ? all : all.filter(x => x.portfolio === pid);
}
function renderTrades() {
  const c = COURSES[cur], v = vm(c);
  if (!v.tested) return;
  const p = v.ports.find(x => x.id === tPort) || v.head;
  const list = tradesFor(c, p.id);
  $('#tTitle').textContent = p.label;
  $('#tSub').textContent = `${nameOf(c)} · got in ${delay} min after each post`;
  if (!list.length) {
    $('#tHead').innerHTML = `<p>No sample trades in the file for this kind.</p>`;
    $('#tList').innerHTML = ''; $('#tQuote').innerHTML = ''; $('#tLegend').textContent = '';
    destroyTrade(); $('#tChart').innerHTML = '';
    return;
  }
  tSel = Math.min(tSel, list.length - 1);
  $('#tList').innerHTML = list.slice(0, 60).map((x, i) => {
    const me = x.by_delay?.[dkey(x.by_delay)];
    return `<li><button type="button" class="t-row${i === tSel ? ' on' : ''}" data-t="${i}" aria-pressed="${i === tSel}">
      <b>${esc(x.ticker)}</b><span class="cap">${DAY.format(new Date(x.posted_at))}</span><span class="t-ret" style="color:${me ? TONE[me.ret_pct >= 0 ? 'green' : 'red'].paper : 'inherit'}">${me ? pct(me.ret_pct) : '—'}</span></button></li>`;
  }).join('');
  const x = list[tSel], me = x.by_delay?.[dkey(x.by_delay)];
  $('#tHead').innerHTML = `<span class="t-tick">${esc(x.ticker)}</span><span class="t-side cap">${x.side === 'short' ? 'Short' : 'Long'} · posted ${DAY.format(new Date(x.posted_at))}, ${etTime(x.posted_at)} ET</span>
    ${me ? `<span class="t-res" style="color:${TONE[me.ret_pct >= 0 ? 'green' : 'red'].paper}">${pct(me.ret_pct)}</span>` : ''}`;
  $('#tLegend').textContent = me
    ? `In at ${fmt.money2(me.entry)} (${etTime(me.entry_at)}), out at ${fmt.money2(me.exit)} (${etTime(me.exit_at)}). ${x.bars ? 'Minute bars.' : 'Line joins the prices at each delay.'}`
    : 'Not entered at this delay.';
  $('#tQuote').innerHTML = x.quote ? `<p>“${esc(x.quote)}”</p><footer class="cap">${icon(/^yt:/.test(x.cite?.source_id || '') ? 'play' : 'chat')}${esc(x.cite?.label || '')}</footer>` : '';
  requestAnimationFrame(() => drawTrade($('#tChart'), x, +dkey(x.by_delay), TONE[v.tone].paper));
}
fmt.money2 = val => '$' + Number(val).toFixed(2);
$('#tList').addEventListener('click', e => { const b = e.target.closest('[data-t]'); if (!b) return; tSel = +b.dataset.t; renderTrades(); });

/* ---------- sheets ---------- */
let lastFocus = null;
function openSheet(w, focusBtn) {
  if (w.classList.contains('open')) return;
  lastFocus = document.activeElement;
  $('.sheet', w).scrollTop = 0;
  w.classList.add('open');
  if (w === wrap) countAll($('#pEV'), 250);
  if (openedByUser) setTimeout(() => focusBtn.focus({ preventScroll: true }), QUIET ? 0 : 120);
  openedByUser = false;
}
function closeSheet(w) {
  if (!w.classList.contains('open')) return;
  w.classList.remove('open');
  if (w === tWrap) setTimeout(destroyTrade, 460);
  if (lastFocus && document.contains(lastFocus) && lastFocus.offsetParent) lastFocus.focus({ preventScroll: true });
}
wrap.addEventListener('click', e => { if (e.target.closest('[data-close]')) location.hash = '#verdict-' + COURSES[cur].key; });
tWrap.addEventListener('click', e => { if (e.target.closest('[data-close]')) location.hash = '#learn-' + COURSES[cur].key; });
[sheet, tSheet].forEach(sh => sh.addEventListener('keydown', e => {
  if (e.key !== 'Tab') return;
  const f = $$('button:not([disabled]),[href],input,[tabindex]:not([tabindex="-1"])', sh).filter(x => x.offsetParent);
  if (!f.length) return;
  if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
  else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
}));

/* ---------- onboarding run (CAP-4) ---------- */
let runTimers = [];
const clearRun = () => { runTimers.forEach(clearTimeout); runTimers = []; };
function finishOnboarding() { onboarded = true; store.set('onboarded', true); store.set('picks', [...selected]); }
function startRun() {
  const items = $$('#runList li');
  const target = '#verdict-' + COURSES[visibleList()[0] ?? 0].key;
  if (STILL) { items.forEach(li => { li.dataset.state = 'done'; }); finishOnboarding(); location.replace(target); return; }
  items.forEach(li => { li.dataset.state = 'wait'; });
  items.forEach((li, k) => {
    runTimers.push(setTimeout(() => { li.dataset.state = 'now'; }, k * 700 + 60));
    runTimers.push(setTimeout(() => { li.dataset.state = 'done'; }, (k + 1) * 700 - 80));
  });
  runTimers.push(setTimeout(() => { finishOnboarding(); location.hash = target; }, items.length * 700 + 300));
}

/* ---------- popovers, account, toast ---------- */
const samplePop = $('#samplePop'), menu = $('#menu'), sampleBtn = $('#sampleBtn'), avatarBtn = $('#avatarBtn');
function syncSample() {
  const scr = document.body.dataset.screen;
  const on = (scr === 'verdict' || scr === 'learn') && !!COURSES[cur].r?.sample;
  sampleBtn.hidden = !on;
  if (!on) samplePop.hidden = true;
}
function closePops() {
  samplePop.hidden = true; menu.hidden = true;
  sampleBtn.setAttribute('aria-expanded', 'false'); avatarBtn.setAttribute('aria-expanded', 'false');
}
const popOpen = () => !samplePop.hidden || !menu.hidden;
sampleBtn.addEventListener('click', e => {
  e.stopPropagation(); const open = samplePop.hidden; closePops();
  if (open) { samplePop.hidden = false; sampleBtn.setAttribute('aria-expanded', 'true'); }
});
avatarBtn.addEventListener('click', e => {
  e.stopPropagation(); const open = menu.hidden; closePops();
  if (open) { menu.hidden = false; avatarBtn.setAttribute('aria-expanded', 'true'); $('#signOut').focus({ preventScroll: true }); }
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
$('#signOut').addEventListener('click', async () => {
  closePops();
  try { await signOut(); } catch (e) { console.warn(e); }
  user = null; showUser();
  location.hash = '#signin'; toast('Signed out');
});
const googleBtn = $('#googleBtn');
googleBtn.addEventListener('click', async () => {
  googleBtn.disabled = true; $('#siErr').hidden = true;
  try {
    const u = await signInWithGoogle();
    if (u) { user = u; showUser(); location.hash = onboarded ? '#verdict-' + COURSES[visibleList()[0] ?? 0].key : '#onboard-1'; }
  } catch (e) {
    console.warn('Google sign-in failed', e);
    $('#siErr').textContent = 'Sign-in didn’t work. Try again.'; $('#siErr').hidden = false;
  } finally { googleBtn.disabled = false; }
});
$('#ob1Next').addEventListener('click', () => { if (selected.size) location.hash = '#onboard-2'; });
$('#ob2Next').addEventListener('click', () => { location.hash = '#onboard-3'; });

/* ---------- keyboard ---------- */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (popOpen()) { closePops(); return; }
    if (wrap.classList.contains('open')) location.hash = '#verdict-' + COURSES[cur].key;
    if (tWrap.classList.contains('open')) location.hash = '#learn-' + COURSES[cur].key;
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
    if (scr !== 'verdict' && scr !== 'learn') return;
    e.preventDefault(); stepCourse(dir);
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
function render(vt = false) {
  if (!booted) return;
  let r = parse();
  if (!user && r.screen !== 'signin') { history.replaceState(null, '', '#signin'); r = { screen: 'signin' }; }
  else if (user && r.screen === 'signin') {
    const to = onboarded ? 'verdict-' + COURSES[visibleList()[0] ?? 0].key : 'onboard-1';
    history.replaceState(null, '', '#' + to); r = parse();
  }
  const prev = route; route = r;
  clearRun(); closePops();
  const scr = r.screen === 'proof' ? 'verdict' : r.screen === 'trades' ? 'learn' : r.screen;
  document.body.dataset.screen = scr;
  $$('.screen').forEach(s => { s.hidden = s.id !== 's-' + scr; });
  if (r.course) {
    if (!selected.has(r.course)) { selected.add(r.course); syncCards(); }
    cur = KEYS.indexOf(r.course);
  }
  if (scr === 'verdict') {
    const wasDeck = prev && (prev.screen === 'verdict' || prev.screen === 'proof');
    const same = wasDeck && prev.course === r.course;
    slides.forEach((el, i) => fillSlide(el, COURSES[i], i === cur && !same));
    syncDelayControls();
    layoutDeck(wasDeck && !same);
    setDrench(vm(COURSES[cur]).tone, 300);
    syncTabs(!wasDeck);
    fitStamps();
    if (!same) markStamped(r.screen === 'verdict', 300);
    closeSheet(tWrap);
    if (r.screen === 'proof' && vm(COURSES[cur]).tested) { renderProof(); openSheet(wrap, $('#pClose')); } else closeSheet(wrap);
  } else {
    closeSheet(wrap);
    if (scr !== 'learn') closeSheet(tWrap);
    setDrench('ink', 300);
    if (scr === 'learn') {
      const wasLearn = prev && (prev.screen === 'learn' || prev.screen === 'trades') && prev.course === r.course;
      syncTabs(!(prev && ['learn', 'verdict', 'proof', 'trades'].includes(prev.screen)));
      syncDelayControls();
      if (!wasLearn || r.screen === 'learn' && prev?.screen !== 'trades') renderLearn(vt);
      if (r.screen === 'trades') {
        if (tPort !== r.port) { tPort = r.port; tSel = 0; }
        renderTrades(); openedByUser = true; openSheet(tWrap, $('#tClose'));
      } else closeSheet(tWrap);
    }
    if (scr === 'onboard-1') { syncCards(); arcGeom(); arcRender(); }
    if (scr === 'onboard-3') startRun();
  }
  syncSample();
}
addEventListener('hashchange', () => render(false));
let rz = 0;
addEventListener('resize', () => {
  cancelAnimationFrame(rz);
  rz = requestAnimationFrame(() => {
    const scr = document.body.dataset.screen;
    if (scr === 'verdict') { layoutDeck(false); fitStamps(); }
    if (scr === 'verdict' || scr === 'learn') syncTabs(true);
    if (scr === 'onboard-1') { arcGeom(); arcRender(); }
    if (wrap.classList.contains('open')) drawChart();
  });
});

/* ---------- boot ---------- */
syncCards(); arcGeom(); arcRender(); syncDelayControls();
document.body.dataset.screen = 'boot';
$('#s-boot').hidden = false;
setDrench('ink', 0);
initAuth(u => {
  const was = user;
  user = u; showUser();
  if (!booted) { booted = true; render(false); return; }
  if (!was && u) render(false);
  if (was && !u && document.body.dataset.screen !== 'signin') { location.hash = '#signin'; }
}).catch(e => {
  console.warn('Auth failed to load', e);
  booted = true; render(false);
  $('#siErr').textContent = 'Sign-in is down right now.'; $('#siErr').hidden = false;
});
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => {
  const scr = document.body.dataset.screen;
  if (scr === 'verdict') fitStamps();
  if (scr === 'verdict' || scr === 'learn') syncTabs(true);
});

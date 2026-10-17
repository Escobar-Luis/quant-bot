import './ui.css';
import { COURSE_META, latest, PROOF } from './data.js';
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
const PAPER = { Yes: '#1A7F37', Barely: '#B25E00', No: '#D92D20', few: '#6E6E73' };
const wcls = w => WORD_CLASS[w] || 'few';
const fmt = {
  pct: v => { const r = Math.round(v * 10) / 10, a = Math.abs(r); return (r > 0 ? '+' : r < 0 ? '−' : '') + (Number.isInteger(a) ? a : a.toFixed(1)) + '%'; },
  money: v => '$' + Math.round(v).toLocaleString('en-US'),
  // Cheap coins need more digits than $0.07.
  price: v => { const n = Number(v); const d = n >= 1 ? 2 : n >= 0.01 ? 4 : 6; return '$' + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }); }
};
const pct = fmt.pct;
const kMoney = v => (v % 1000 === 0 ? '$' + v / 1000 + 'k' : fmt.money(v));
const MONTH = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const month = d => MONTH.format(new Date(d + 'T00:00:00Z'));
const DAY = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York' });

/* ---------- data: one view-model per course at the chosen delay ---------- */
const COURSES = COURSE_META.map(m => ({ ...m, r: latest(m.key) }));
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
function vm(c) {
  const r = c.r;
  if (!r) return { tested: false, word: 'Not tested yet' };
  const ports = (r.portfolios || []).map(portfolioAt);
  const head = ports.find(p => p.id === r.headline_portfolio && p.at) || ports.find(p => p.at);
  if (!head) return { tested: false, word: 'Not tested yet' };
  return { tested: true, r, head, s: head.at, ports, word: head.at.word, start: r.money_start || 10000, hold: holdName(r.hold) };
}
// One honest fine-print line: sizing, plus trades we couldn't copy or had to shrink.
function fineLine(r, s) {
  const sz = r.sizing || '', amt = sz.match(/\$[\d,]+/)?.[0];
  const unit = sz.match(/(?:per|a|each) (trade|call|setup)/i)?.[1] || 'trade';
  const bits = [];
  if (amt) bits.push(/scal/i.test(sz) ? `Scaled to ${amt} per ${unit}` : `${amt} per ${unit}`);
  if (s.couldnt_copy > 0) bits.push(`${s.couldnt_copy.toLocaleString('en-US')} couldn’t be copied`);
  if (s.sized_down > 0) bits.push(`${s.sized_down.toLocaleString('en-US')} sized down`);
  if (s.not_triggered > 0) bits.push(`${s.not_triggered.toLocaleString('en-US')} never triggered`);
  return bits.join(' · ');
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
const delayHTML = id => `<div class="d-head num"><label for="${id}">Entered <b class="d-v">${delay} min</b> after each post</label></div>
    <input class="d-range" id="${id}" type="range" min="0" max="${DELAYS.length - 1}" step="1" value="${delayIdx()}" aria-valuetext="${delay} minutes after each post">
    <div class="d-stops num">${DELAYS.map((d, i) => `<button type="button" data-di="${i}" aria-label="${d} minutes" aria-pressed="false">${d}</button>`).join('')}</div>`;
$('#vDelay').innerHTML = delayHTML('dlV');
$('#lDelay').innerHTML = delayHTML('dlL');
function syncDelay() {
  $$('.delay').forEach(w => {
    $('.d-v', w).textContent = delay + ' min';
    const inp = $('.d-range', w);
    if (+inp.value !== delayIdx()) inp.value = delayIdx();
    inp.setAttribute('aria-valuetext', `${delay} minutes after each post`);
    inp.style.setProperty('--p', (delayIdx() / (DELAYS.length - 1) * 100) + '%');
    $$('.d-stops button', w).forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.di === delayIdx())));
  });
}
function setDelay(d) {
  if (d === delay || !DELAYS.includes(d)) return;
  delay = d; store.set('delay', d);
  syncDelay();
  const scr = document.body.dataset.screen;
  if (scr === 'verdict') renderVerdict(false);
  if (scr === 'learn') renderLearn(false);
}
document.addEventListener('input', e => { if (e.target.matches('.d-range')) setDelay(DELAYS[+e.target.value]); });
document.addEventListener('click', e => { const b = e.target.closest('.d-stops button'); if (b) setDelay(DELAYS[+b.dataset.di]); });

/* ---------- verdict (CAP-5): the answer, huge ---------- */
let shownWord = null;
function renderVerdict(fresh) {
  const c = COURSES[cur], v = vm(c), word = $('#vWord');
  $('#vQ').innerHTML = `<b>${esc(c.r?.course_name || c.name)}</b> · beat just holding?`;
  const label = v.tested ? v.word : 'Not tested yet';
  const changed = label !== shownWord;
  word.textContent = v.tested && v.word.length <= 6 ? v.word + '.' : label;
  word.classList.toggle('long', label.length > 6);
  root.style.setProperty('--word', v.tested ? WORD_COLOR[wcls(v.word)] : 'var(--ink3)');
  if ((fresh || changed) && !STILL) { word.classList.remove('reveal'); void word.offsetWidth; word.classList.add('reveal'); }
  shownWord = label;
  $('#vDelay').hidden = !v.tested; $('#vAct').hidden = !v.tested;
  if (!v.tested) {
    $('#vMoney').innerHTML = `<span class="v-vs">Copying every trade now.</span>`;
    $('#vFine').textContent = '';
    return;
  }
  const s = v.s;
  $('#vMoney').innerHTML = `${kMoney(v.start)} <span class="arrow">→</span> ${fmt.money(s.end)}<span class="v-vs">vs ${fmt.money(s.hold_end)} holding ${esc(v.hold)}</span>`;
  $('#vFine').innerHTML = fineLine(v.r, s).split(' · ').map(b => `<span class="nw">${esc(b)}</span>`).join(' · ');
  $('#live').textContent = `${c.name}: ${v.word}. ${kMoney(v.start)} became ${fmt.money(s.end)}; holding ${v.hold} made ${fmt.money(s.hold_end)}.`;
}
$('#proofBtn').addEventListener('click', () => { openedByUser = true; location.hash = '#proof-' + KEYS[cur]; });
$('#kindBtn').addEventListener('click', () => { location.hash = '#learn-' + KEYS[cur]; });
$('#backBtn').addEventListener('click', () => { location.hash = '#verdict-' + KEYS[cur]; });

/* swipe between courses on phone */
let sw = null;
$('#s-verdict').addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' && !e.target.closest('.delay')) sw = { x: e.clientX, y: e.clientY }; });
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
  const ordered = [v.head, ...v.ports.filter(p => p.id !== v.head.id)];
  list.innerHTML = ordered.map(p => {
    if (!p.testable) {
      if (!p.count) return '';
      return `<li><div class="kind"><span class="k-name">${esc(p.label)}</span><span class="k-sub cap num">${p.count.toLocaleString('en-US')} trades · can’t test yet: ${esc(p.why || 'no prices')}</span></div></li>`;
    }
    const a = p.at;
    if (!a || (p.id !== v.head.id && !a.trades)) return '';
    return `<li><button class="kind" type="button" data-trades="${esc(p.id)}" aria-label="${esc(p.label)}: ${pct(a.ret_pct)}, ${esc(a.word)}. Check its trades.">
      <span class="k-name">${esc(p.id === v.head.id ? 'Everything' : p.label)}</span>
      <span class="k-sub cap num">${a.trades.toLocaleString('en-US')} trades · ${kMoney(v.start)} → ${fmt.money(a.end)}</span>
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
  const found = v.tested ? `${v.s.trades.toLocaleString('en-US')} trades copied` : 'Not tested yet';
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
function renderProof() {
  const c = COURSES[cur], v = vm(c);
  if (!v.tested) return;
  const r = v.r, s = v.s, col = PAPER[wcls(v.word)];
  $('#pSub').textContent = `${c.r.course_name || c.name} · ${kMoney(v.start)} fake money · ${month(r.window.start)} – ${month(r.window.end)} · entered ${delay} min late`;
  $('#pWord').textContent = v.word; root.style.setProperty('--word', WORD_COLOR[wcls(v.word)]);
  const swatch = (cl, dash) => `<svg viewBox="0 0 20 8" aria-hidden="true"><line x1="1" y1="4" x2="19" y2="4" stroke="${cl}" stroke-width="${dash ? 2 : 3}" stroke-linecap="round" ${dash ? 'stroke-dasharray="4 3"' : ''}/></svg>`;
  const sub = [`${s.trades.toLocaleString('en-US')} trades`, s.won_pct != null && `won ${s.won_pct}%`, s.worst_drop_pct != null && `worst drop ${pct(s.worst_drop_pct)}`].filter(Boolean).join(' · ');
  $('#pNums').innerHTML =
    `<div><span class="n-name">${swatch(col)}Copying every trade</span><span class="n-pct" style="color:${col}">${pct(s.ret_pct)}<small>${fmt.money(s.end)}</small></span><span class="n-sub cap">${sub}</span></div>` +
    `<div><span class="n-name">${swatch('#1D1D1F', true)}Holding ${esc(v.hold)}</span><span class="n-pct">${pct(s.hold_ret_pct)}<small>${fmt.money(s.hold_end)}</small></span><span class="n-sub cap">${esc(r.hold?.what || '')}</span></div>`;

  const P = proofFor(c), kb = P?.knowledge_base, rc = P?.root_cause, ev = P?.evaluator;
  const rules = (r.rules || []).slice(0, 6);
  const rulesHTML = rules.length ? `<ol class="rules">${rules.map((x, k) => `
      <li class="${x.testable === false ? 'vague' : ''}"><span class="r-n num">${k + 1}</span><div><p class="r-q">${esc(x.text)}</p>
      ${x.quote ? `<p class="r-quote cap">“${esc(x.quote)}”</p>` : ''}
      <p class="r-c cap num">${icon(/^yt:/.test(x.cite?.source_id || '') ? 'play' : 'chat')}${esc(x.cite?.label || '')}${x.testable === false ? '<span class="tag">Can’t test</span>' : ''}</p></div></li>`).join('')}</ol>` : '';
  const hits = (kb?.hits || []).filter(h => has(h?.snippet));
  $('#pKB').innerHTML = `<h3 class="p-h">Knowledge Base<span class="by">PRISM</span></h3>
    <p class="p-s cap">The course rules the agent looked up</p>
    ${has(kb?.query) ? `<p class="kb-q cap">Searched “${esc(kb.query)}” · ${hits.length} hits ${link(kb.run_url, 'See the run')}</p>
      ${hits.length ? `<ol class="hits">${hits.slice(0, 5).map(h => `<li><p class="r-q">${esc(h.snippet)}</p><p class="r-c cap">${icon('doc')}${esc(h.doc || '')}</p></li>`).join('')}</ol>` : ''}` : pending('The retrieval step')}
    ${rulesHTML ? `<h4 class="p-h4">Rules found, with sources</h4>${rulesHTML}` : ''}`;

  $('#pRC').innerHTML = `<h3 class="p-h">Root Cause<span class="by">PRISM</span></h3>
    <p class="p-s cap">Why the first version failed</p>
    ${has(rc?.our_sentence) ? `<p class="rc-q">${esc(rc.our_sentence)}</p>
      <p class="rc-fix cap num">${icon('wrench')}${[has(rc.failed_runs) && `${rc.failed_runs} failed runs`, has(rc.cluster) && `“${esc(rc.cluster)}”`, has(rc.tier) && esc(rc.tier)].filter(Boolean).join(' · ')}</p>
      ${has(rc.prism_cause) ? `<p class="p-s cap">PRISM: ${esc(rc.prism_cause)}</p>` : ''}${link(rc.url, 'See the cluster')}` : pending('The failure cluster')}`;

  const prismScore = has(ev?.v1?.pass_pct) && has(ev?.v2?.pass_pct);
  const mirror = ev?.code_mirror && has(ev.code_mirror.v1_pass_pct) && has(ev.code_mirror.v2_pass_pct) ? ev.code_mirror : null;
  const a = prismScore ? ev.v1.pass_pct : mirror?.v1_pass_pct, b = prismScore ? ev.v2.pass_pct : mirror?.v2_pass_pct;
  $('#pEV').innerHTML = `<h3 class="p-h">Evaluator<span class="by">${prismScore ? 'PRISM' : 'Our code'}</span></h3>
    ${has(a) ? `<div class="ev num"><b style="color:${PAPER.No}">${a}%</b>${icon('arrowR')}<b style="color:${PAPER.Yes}">${b}%</b><small>v1 → v2${ev.inputs ? ' · ' + esc(ev.inputs) : ''}</small></div>
      <p class="ev-t"><b>${esc(ev.name || 'Score')}:</b> ${esc(ev.checks || '')}</p>
      ${prismScore ? link(ev.url, 'See the scores') : `<p class="p-s cap">PRISM’s own score: pending.</p>`}` : pending('The v1 → v2 score')}`;

  const se = s.sealed;
  if (se && r.window.sealed_from && r.window.sealed_from > r.window.start) {
    const mx = Math.max(Math.abs(se.ret_pct), Math.abs(se.hold_ret_pct), 0.1);
    const bar = (x, cl) => { const w = Math.abs(x) / mx * 50; return `<i style="background:${cl};width:${w}%;left:${x >= 0 ? 50 : 50 - w}%"></i>`; };
    $('#pNew').innerHTML = `<h3 class="p-h">Newest months</h3><p class="p-s cap num">${month(r.window.sealed_from)} – ${month(r.window.end)} · kept sealed${has(se.trades) ? ` · ${se.trades} trades` : ''}</p>
      <div class="nd num">
        <div class="nd-row"><span>Copying</span><span class="nd-bar">${bar(se.ret_pct, col)}</span><b>${pct(se.ret_pct)}</b></div>
        <div class="nd-row"><span>Holding ${esc(v.hold)}</span><span class="nd-bar">${bar(se.hold_ret_pct, '#1D1D1F')}</span><b>${pct(se.hold_ret_pct)}</b></div>
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
  const end = (arr, cl) => `<circle cx="${X(n).toFixed(1)}" cy="${Y(arr[n]).toFixed(1)}" r="4" fill="${cl}" stroke="#FBFBFD" stroke-width="2"/>`;
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${kMoney(v.start)} over time: copying ends at ${fmt.money(course[n])}, holding ${esc(v.hold)} at ${fmt.money(S.hold[n])}.">${g}
    <path d="${path(S.hold)}" fill="none" stroke="#1D1D1F" stroke-width="1.5" stroke-dasharray="5 4" stroke-linejoin="round"/>
    <path d="${path(course)}" fill="none" stroke="${col}" stroke-width="2.25" stroke-linejoin="round" stroke-linecap="round"/>
    ${end(S.hold, '#1D1D1F')}${end(course, col)}</svg>`;
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
  $('#tListH').textContent = total && total > list.length ? `${list.length} of ${total.toLocaleString('en-US')} trades` : 'Trades';
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
  $('#tQuote').innerHTML = x.quote ? `<p>“${esc(x.quote)}”</p><footer class="cap">${icon(/^yt:/.test(x.cite?.source_id || '') ? 'play' : 'chat')}${esc(x.cite?.label || '')}</footer>` : '';
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

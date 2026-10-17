// Browser half of the number check (story/5-full-flow-test).
// check_numbers.py --dom-js <file> writes `const EXPECTED = {...};` + this file; paste it into the
// page (signed in, ideally with ?still=1) and it clicks every course, delay and time-range chip,
// then compares what the verdict card shows with the files on main. Selectors: web/index.html (Mission Control).
async function flowCheck(EXP, delays = [1, 5, 15]) {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = id => (document.getElementById(id)?.innerText || '').replace(/\s+/g, ' ').trim();
  const chip = (box, label) => [...document.querySelectorAll(`#${box} button`)]
    .find(b => b.innerText.trim().toLowerCase() === label.toLowerCase());
  const dl = d => (d === 60 ? '1h' : d + 'm');
  const fails = [], passes = [];
  const want = (where, hay, s) => (hay.includes(s) ? passes : fails).push(`${where}: want "${s}", saw "${hay.slice(0, 90)}"`);
  const overflow = () => document.documentElement.scrollWidth > innerWidth;
  for (const [course, e] of Object.entries(EXP)) {
    location.hash = '#verdict-' + course; await sleep(700);
    if (!e.tested) { want(course, T('vHead') + ' ' + T('vChip'), 'Not tested'); continue; }
    chip('vRanges', 'All')?.click(); await sleep(250);
    for (const d of delays) {
      const b = chip('vDelays', dl(d));
      if (!b) { fails.push(`${course}: no ${dl(d)} chip`); continue; }
      b.click(); await sleep(450);
      const x = e.by_delay[String(d)], head = T('vHead'), w = `${course}@${dl(d)}`;
      want(w + ' end', head, x.end);
      want(w + ' holding (anywhere on the card)', document.body.innerText, x.hold_end);
      want(w + ' word', T('vChip').toLowerCase(), x.word.toLowerCase());
      want(w + ' trades', T('vMeta'), x.trades);
      if (x.couldnt_copy) want(w + ' couldn\'t copy', T('vFine'), x.couldnt_copy.toLocaleString('en-US'));
      if (x.sized_down) want(w + ' sized down', T('vFine'), x.sized_down.toLocaleString('en-US'));
      if (x.best_stop) want(w + ' best stop', T('vStop'), x.best_stop.end);
      for (const s of x.strategies || []) {
        const st = T('strats');
        want(`${w} strategy "${s.name}"`, st, s.name);
        want(`${w} strategy "${s.name}" result`, st, s.ret);
      }
      for (const [rg, r] of Object.entries(x.ranges || {})) {
        const rb = chip('vRanges', rg.toUpperCase());
        if (!rb) { fails.push(`${w}: no ${rg.toUpperCase()} chip`); continue; }
        rb.click(); await sleep(400);
        const h2 = T('vHead');
        want(`${w} ${rg} end`, h2, r.end);
        want(`${w} ${rg} holding (anywhere)`, document.body.innerText, r.hold_end);
        want(`${w} ${rg} word`, T('vChip').toLowerCase(), r.word.toLowerCase());
        if (r.trades) want(`${w} ${rg} trades`, T('vMeta'), r.trades);
      }
      for (const m of x.combos || []) {
        const mx = T('cMix');
        want(`${w} best mix word`, mx.toLowerCase(), m.word.toLowerCase());
        want(`${w} best mix past months`, mx, m.dev.find(v => mx.includes(v)) || m.dev[0]);
        want(`${w} best mix new months`, mx, m.sealed.find(v => mx.includes(v)) || m.sealed[0]);
        if (!m.dev_beat && /looked good|worked|beat/i.test(mx)) fails.push(`${w} best mix: praises past months that lost to holding: "${mx.slice(0, 90)}"`);
      }
      chip('vRanges', 'All')?.click(); await sleep(250);
      if (overflow()) fails.push(`${w}: page wider than the screen (${document.documentElement.scrollWidth} > ${innerWidth})`);
    }
  }
  if (typeof PROOF !== 'undefined') {
    location.hash = '#proof-lpp'; await sleep(1000);
    const sh = document.getElementById('sheet'), st = (sh?.innerText || '').replace(/\s+/g, ' ');
    for (const s of PROOF.text) want(`proof shows ${s}`, st, s);
    const hrefs = [...(sh?.querySelectorAll('a') || [])].map(a => a.href).join(' ');
    for (const u of PROOF.links) want('proof links', hrefs, u);
    if (/\bnull\b|NaN|undefined|0% → 0%/.test(st)) fails.push('proof sheet shows null / NaN / undefined / 0% → 0%');
    location.hash = '#verdict-lpp'; await sleep(500);
  }
  return { width: innerWidth, pass: passes.length, fail: fails.length, fails: fails.slice(0, 40) };
}
flowCheck(EXPECTED);

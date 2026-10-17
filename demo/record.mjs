// Screen-record the live app along tests/flow/demo-run.md, timed to demo/narration.mp3, then mux.
//
//   node demo/record.mjs [url]        -> demo/out/demo.mp4 (gitignored); uses a local or global `playwright`
//
// Real app, real clicks (Playwright, Google Chrome). Frames come from Chrome's screencast with their own
// timestamps, so picture and voice stay in sync (Playwright's recordVideo drifts ~10%). Captions and the
// corner label are an overlay injected for the recording only. Cue times come from a Whisper pass over narration.mp3.
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = (() => {
  try { return require('playwright'); } catch { return require(join(execFileSync('npm', ['root', '-g']).toString().trim(), 'playwright')); }
})();
const OUT = join(HERE, 'out');
const URL = process.argv[2] || 'https://day-trader-ai.vercel.app/';
const W = 1440, H = 810;
const END = 59.5; // seconds: narration is 58.0 s, then a short hold
const STAMP = new Date().toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

// [start, end, text]: the narration's words, timed by Whisper.
const CUES = [
  [0.0, 4.0, 'Luis paid for three day-trading courses. None shows a full record.'],
  [4.1, 7.4, 'Would copying every trade they posted have worked?'],
  [7.5, 14.5, 'It copies every trade with $10,000 of fake money, after costs, vs just holding the market.'],
  [14.6, 20.2, 'Learn Plan Profit: No. $10,000 became $9,766.'],
  [20.3, 24.8, 'Just holding the S&P 500 made $11,964.'],
  [24.9, 27.8, 'Crypto Wizard: Yes. It lost less than Bitcoin.'],
  [27.9, 29.6, 'ZipTrader: not enough trades.'],
  [29.7, 34.1, 'An AI, through Nicrron, reads every session. Code checks every number.'],
  [34.2, 40.7, 'v1 failed our checks in 28 of 30 runs: long quotes, lost track of open trades.'],
  [40.8, 44.0, 'PRISM grouped 25 of them into one cluster.'],
  [44.1, 47.8, 'v2, partly a code fix, cut failures to 18.'],
  [47.9, 51.3, 'Our numbers check: 52% → 66%.'],
  [51.4, 54.3, 'Every answer cites the course notes it found in PRISM.'],
  [54.4, END, 'The model proposes. The code decides.'],
];

const overlay = ({ cues, stamp }) => {
  const css = document.createElement('style');
  css.textContent = `
    #rec-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);max-width:1100px;z-index:2147483647;
      font:600 26px/1.3 -apple-system,BlinkMacSystemFont,"Inter",sans-serif;color:#fff;background:rgba(10,10,12,.82);
      padding:12px 22px;border-radius:14px;text-align:center;pointer-events:none;transition:opacity .15s}
    #rec-tag{position:fixed;right:14px;top:12px;z-index:2147483647;font:500 13px/1 -apple-system,sans-serif;color:#fff;
      background:rgba(10,10,12,.7);padding:7px 10px;border-radius:8px;pointer-events:none}`;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'rec-cap'; cap.style.opacity = 0;
  const tag = document.createElement('div'); tag.id = 'rec-tag';
  tag.textContent = `Live app · day-trader-ai.vercel.app · recorded ${stamp} ET · AI voice`;
  document.body.append(cap, tag);
  const t0 = performance.now();
  const tick = () => {
    const t = (performance.now() - t0) / 1000;
    const c = cues.find(([a, b]) => t >= a && t < b);
    cap.textContent = c ? c[2] : ''; cap.style.opacity = c ? 1 : 0;
    if (t < cues[cues.length - 1][1] + 1) requestAnimationFrame(tick);
  };
  tick();
};

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const RAW = join(OUT, 'raw');
  rmSync(RAW, { recursive: true, force: true });
  mkdirSync(RAW, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: W, height: H } });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const frames = []; // [wall-clock seconds, file]
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    const file = join(RAW, `f${String(frames.length).padStart(5, '0')}.jpg`);
    writeFileSync(file, Buffer.from(data, 'base64'));
    frames.push([metadata.timestamp, file]);
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  });
  await page.goto(URL + (URL.includes('#') ? '' : '#signin'), { waitUntil: 'networkidle' });
  await page.locator('#goBtn').waitFor({ state: 'visible' });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  await sleep(800);

  // t0: narration starts here.
  await page.evaluate(overlay, { cues: CUES, stamp: STAMP });
  const t0 = Date.now();
  const at = async s => { const wait = t0 + s * 1000 - Date.now(); if (wait > 0) await sleep(wait); };
  const log = [];
  const late = () => ((Date.now() - t0) / 1000).toFixed(2);
  const step = async (s, what, fn) => { await at(s); try { await fn(); log.push(`${s}s ok   ${what} (done ${late()}s)`); } catch (e) { log.push(`${s}s FAIL ${what}: ${e.message.split('\n')[0]}`); } };
  // Instant DOM clicks on the app's own buttons: Playwright's actionability waits drift seconds behind the voice.
  const click = sel => page.evaluate(q => { const el = typeof q === 'string' ? document.querySelector(q) : null; if (!el) throw new Error('missing ' + q); el.click(); }, sel);
  const clickText = (sel, text) => page.evaluate(([q, t]) => { const el = [...document.querySelectorAll(q)].find(e => e.textContent.trim() === t); if (!el) throw new Error(`missing ${q} "${t}"`); el.click(); }, [sel, text]);
  const scrollSheet = sel => page.evaluate(s => document.querySelector(s)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), sel);
  const delay = label => clickText('#vDelays button', label);
  const tab = name => clickText('button[role=tab]', name);

  await step(6.6, 'Continue', () => click('#goBtn'));
  await step(9.2, 'Next', () => click('#ob1Next'));
  await step(10.8, 'Run the audit', () => click('#ob2Next'));
  await step(20.6, 'delay 1m', () => delay('1m'));
  await step(22.0, 'delay 15m', () => delay('15m'));
  await step(23.6, 'delay 5m', () => delay('5m'));
  await step(24.9, 'tab Crypto Wizard', () => tab('Crypto Wizard'));
  await step(27.9, 'tab ZipTrader', () => tab('ZipTrader'));
  await step(29.7, 'tab Learn Plan Profit', () => tab('Learn Plan Profit'));
  await step(31.0, 'See the proof', () => click('#proofBtn'));
  await step(35.5, 'scroll Root Cause', () => scrollSheet('#pRC'));
  await step(44.2, 'scroll Evaluator', () => scrollSheet('#pEV'));
  await step(51.4, 'scroll Knowledge Base', () => scrollSheet('#pKB'));
  await step(54.4, 'close sheet', () => click('#pClose'));
  await at(END);

  const headline = await page.locator('#vHead').innerText().catch(() => '');
  await cdp.send('Page.stopScreencast').catch(() => {});
  await context.close(); await browser.close();

  // Concat list on the wall clock: each frame lasts until the next one; the timeline starts at t0.
  const start = t0 / 1000, stop = start + END;
  const kept = frames.filter(([ts], i) => ts < stop && (frames[i + 1]?.[0] ?? Infinity) > start);
  const lines = kept.map(([ts, file], i) => {
    const a = Math.max(ts, start), b = Math.min(kept[i + 1]?.[0] ?? stop, stop);
    return `file '${file}'\nduration ${Math.max(b - a, 0.001).toFixed(4)}`;
  });
  lines.push(`file '${kept[kept.length - 1][1]}'`);
  writeFileSync(join(RAW, 'list.txt'), lines.join('\n') + '\n');
  const offset = (frames[0][0] - Date.now() / 1000).toFixed(1); // sanity: screencast clock vs wall clock
  const mp4 = join(OUT, 'demo.mp4');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(RAW, 'list.txt'), '-i', join(HERE, 'narration.mp3'),
    '-t', String(END), '-map', '0:v', '-map', '1:a', '-vf', `scale=${W}:${H},fps=30`, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-af', 'apad', '-movflags', '+faststart', mp4]);
  console.log(`${frames.length} frames, ${kept.length} in the cut; first frame vs now: ${offset}s`);
  console.log(log.join('\n'));
  console.log(`final headline: ${headline.replace(/\s+/g, ' ')}`);
  console.log(`wrote ${mp4} (${END}s)`);
}

main().catch(e => { console.error(e); process.exit(1); });

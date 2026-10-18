// The merged ~2-minute video: act 1 (the problem), act 2 (the live app), act 3 (the architecture explainer).
//
//   node demo/merged/record.mjs [act1|act2|join|all]   -> demo/out/act1.mp4, act2.mp4, day-trader-ai.mp4
//
// Acts 1 and 2 are recorded in Google Chrome (Playwright) at 1920×1080 from Chrome's screencast, each frame on its own
// timestamp, timed to demo/out/<act>.mp3 (voice.py). Captions are an overlay added for the recording. Act 3 is the
// HyperFrames explainer render (~/dev/showcase-videos/day-trader-arch), trimmed to start where its map pulls out.
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, '..', 'out');
const require = createRequire(import.meta.url);
const { chromium } = (() => {
  try { return require('playwright'); } catch { return require(join(execFileSync('npm', ['root', '-g']).toString().trim(), 'playwright')); }
})();
const W = 1920, H = 1080;
const APP = 'https://day-trader-ai.vercel.app/';
const EXPLAINER = join(homedir(), 'dev/showcase-videos/day-trader-arch/renders/day-trader-arch.mp4');
const ACT3_FROM = 6.05; // the explainer's own intro repeats act 1; start on its name card as the map pulls out
const STAMP = new Date().toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

const ACTS = {
  act1: {
    url: pathToFileURL(join(HERE, 'act1.html')).href, voiceAt: 0, end: 24.8, tag: null,
    cues: [
      [0.0, 3.6, 'Trading courses sell their wins, never a full record.'],
      [3.9, 9.2, 'US retail options traders lost an estimated $2.1B in 20 months.'],
      [9.4, 14.6, 'The FTC on one day-trading course: most accounts lost money.'],
      [14.8, 16.5, 'Luis paid for three of these courses.'],
      [16.6, 19.7, 'So he built Day Trader AI.'],
      [19.8, 24.8, 'Copy every trade they posted: would it have worked?'],
    ],
    steps: async (s) => { await s(0, 'start scenes', (p) => p.evaluate(() => window.start())); },
  },
  act2: {
    url: APP + '#signin', voiceAt: 2.0, end: 45.6,
    tag: () => `Live app · day-trader-ai.vercel.app · recorded ${STAMP} ET · AI voice`,
    cues: [
      [2.0, 5.4, "Here's the live app. Pick your courses; it runs the audit."],
      [6.0, 11.7, 'Learn Plan Profit: No. $10,000 became $9,766.'],
      [11.9, 16.0, 'Just holding the S&P 500 made $11,964.'],
      [16.4, 21.7, 'How late you got in after each post: still No.'],
      [21.8, 25.5, 'Crypto Wizard: Yes. It lost money, just less than Bitcoin.'],
      [25.6, 28.8, 'ZipTrader: too few trades to judge.'],
      [29.0, 33.1, 'The proof: the notes it searched, why v1 failed.'],
      [33.1, 36.8, 'The fix: 28 failed runs down to 18.'],
      [37.3, 41.9, 'Our agent tried to improve a strategy…'],
      [41.9, 45.6, '…the newest months disagreed: not kept.'],
    ],
    steps: async (s, { click, clickText, scrollTo }) => {
      await s(0.6, 'Continue', () => click('#goBtn'));
      await s(2.0, 'Next', () => click('#ob1Next'));
      await s(2.9, 'Run the audit', () => click('#ob2Next'));
      await s(19.3, 'delay 1m', () => clickText('#vDelays button', '1m'));
      await s(20.3, 'delay 15m', () => clickText('#vDelays button', '15m'));
      await s(21.3, 'delay 5m', () => clickText('#vDelays button', '5m'));
      await s(21.7, 'tab Crypto Wizard', () => clickText('button[role=tab]', 'Crypto Wizard'));
      await s(25.6, 'tab ZipTrader', () => clickText('button[role=tab]', 'ZipTrader'));
      await s(28.3, 'tab Learn Plan Profit', () => clickText('button[role=tab]', 'Learn Plan Profit'));
      await s(29.0, 'See the proof', () => click('#proofBtn'));
      await s(32.3, 'scroll Root Cause', () => scrollTo('#pRC', 'start'));
      await s(33.6, 'scroll Evaluator', () => scrollTo('#pEV', 'start'));
      await s(37.1, 'close sheet', () => click('#pClose'));
      await s(37.6, 'scroll to the agent card', () => scrollTo('#cBot', 'center'));
      await s(42.1, 'flash the agent card', (p) => p.evaluate(() => {
        const el = document.querySelector('#cBot');
        el.animate([{ boxShadow: '0 0 0 0 rgba(232,115,90,0)' }, { boxShadow: '0 0 0 10px rgba(232,115,90,.55)' }, { boxShadow: '0 0 0 0 rgba(232,115,90,0)' }], { duration: 1200 });
      }));
    },
  },
};

const overlay = ({ cues, tag }) => {
  const css = document.createElement('style');
  css.textContent = `
    #rec-cap{position:fixed;left:50%;bottom:48px;transform:translateX(-50%);max-width:1700px;z-index:2147483647;white-space:nowrap;
      font:500 44px/1.25 -apple-system,BlinkMacSystemFont,"Inter",sans-serif;color:#F4F1EA;background:#1F1E1B;
      border:2px solid rgba(244,241,234,.45);padding:18px 38px;border-radius:20px;text-align:center;pointer-events:none}
    #rec-tag{position:fixed;left:50px;top:40px;z-index:2147483647;font:500 22px/1 -apple-system,sans-serif;color:#F4F1EA;
      background:rgba(31,30,27,.82);padding:12px 18px;border-radius:14px;pointer-events:none}`;
  document.head.appendChild(css);
  const cap = document.createElement('div'); cap.id = 'rec-cap'; cap.style.opacity = 0; document.body.append(cap);
  if (tag) { const t = document.createElement('div'); t.id = 'rec-tag'; t.textContent = tag; document.body.append(t); }
  const t0 = performance.now();
  const tick = () => {
    const t = (performance.now() - t0) / 1000;
    const c = cues.find(([a, b]) => t >= a && t < b);
    if (c && cap.textContent !== c[2]) { cap.textContent = c[2]; cap.animate([{ transform: 'translateX(-50%) scale(.92)' }, { transform: 'translateX(-50%) scale(1)' }], { duration: 260, easing: 'cubic-bezier(.2,1.6,.4,1)' }); }
    cap.style.opacity = c ? 1 : 0;
    if (t < cues[cues.length - 1][1] + 1) requestAnimationFrame(tick);
  };
  tick();
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function record(name) {
  const A = ACTS[name];
  const RAW = join(OUT, 'raw-' + name);
  rmSync(RAW, { recursive: true, force: true }); mkdirSync(RAW, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: W, height: H } });
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  const frames = [];
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    const file = join(RAW, `f${String(frames.length).padStart(5, '0')}.jpg`);
    writeFileSync(file, Buffer.from(data, 'base64'));
    frames.push([metadata.timestamp, file]);
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  });
  await page.goto(A.url, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  if (name === 'act2') await page.locator('#goBtn').waitFor({ state: 'visible' });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  await sleep(800);
  await page.evaluate(overlay, { cues: A.cues, tag: A.tag ? A.tag() : null });
  const t0 = Date.now();
  const log = [];
  const late = () => ((Date.now() - t0) / 1000).toFixed(2);
  const s = async (sec, what, fn) => {
    const wait = t0 + sec * 1000 - Date.now(); if (wait > 0) await sleep(wait);
    try { await fn(page); log.push(`${sec}s ok   ${what} (done ${late()}s)`); } catch (e) { log.push(`${sec}s FAIL ${what}: ${e.message.split('\n')[0]}`); }
  };
  const helpers = {
    click: (q) => page.evaluate((q) => { const el = document.querySelector(q); if (!el) throw new Error('missing ' + q); el.click(); }, q),
    clickText: (q, t) => page.evaluate(([q, t]) => { const el = [...document.querySelectorAll(q)].find((e) => e.textContent.trim() === t); if (!el) throw new Error(`missing ${q} "${t}"`); el.click(); }, [q, t]),
    scrollTo: (q, block) => page.evaluate(([q, b]) => { const el = document.querySelector(q); if (!el) throw new Error('missing ' + q); el.scrollIntoView({ behavior: 'smooth', block: b }); }, [q, block]),
  };
  await A.steps(s, helpers);
  const wait = t0 + A.end * 1000 - Date.now(); if (wait > 0) await sleep(wait);
  await cdp.send('Page.stopScreencast').catch(() => {});
  await context.close(); await browser.close();

  const start = t0 / 1000, stop = start + A.end;
  const kept = frames.filter(([ts], i) => ts < stop && (frames[i + 1]?.[0] ?? Infinity) > start);
  const lines = kept.map(([ts, file], i) => `file '${file}'\nduration ${Math.max(Math.min(kept[i + 1]?.[0] ?? stop, stop) - Math.max(ts, start), 0.001).toFixed(4)}`);
  lines.push(`file '${kept[kept.length - 1][1]}'`);
  writeFileSync(join(RAW, 'list.txt'), lines.join('\n') + '\n');
  const mp4 = join(OUT, name + '.mp4');
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(RAW, 'list.txt'), '-i', join(OUT, name + '.mp3'),
    '-t', String(A.end), '-map', '0:v', '-map', '1:a', '-vf', `scale=${W}:${H},fps=30`, '-af', `adelay=${Math.round(A.voiceAt * 1000)}:all=1,apad,aresample=48000`,
    '-ac', '2', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', mp4]);
  console.log(`${name}: ${kept.length} frames\n` + log.join('\n') + `\nwrote ${mp4} (${A.end}s)`);
}

function join3() {
  if (!existsSync(EXPLAINER)) throw new Error('missing explainer render: ' + EXPLAINER);
  const out = join(OUT, 'day-trader-ai.mp4');
  // Normalize all three to 1920×1080 · 30 fps · 48 kHz stereo, short fades at each seam, then concatenate.
  const f = '[0:v]fps=30,scale=1920:1080,format=yuv420p,fade=t=out:st=24.4:d=0.4[v0];[0:a]aresample=48000,afade=t=out:st=24.4:d=0.4[a0];'
    + '[1:v]fps=30,scale=1920:1080,format=yuv420p,fade=t=in:st=0:d=0.3,fade=t=out:st=45.2:d=0.4[v1];[1:a]aresample=48000,afade=t=out:st=45.2:d=0.4[a1];'
    + `[2:v]trim=start=${ACT3_FROM},setpts=PTS-STARTPTS,fps=30,scale=1920:1080,format=yuv420p,fade=t=in:st=0:d=0.3[v2];`
    + `[2:a]atrim=start=${ACT3_FROM},asetpts=PTS-STARTPTS,aresample=48000[a2];`
    + '[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]';
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', join(OUT, 'act1.mp4'), '-i', join(OUT, 'act2.mp4'), '-i', EXPLAINER,
    '-filter_complex', f, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-c:a', 'aac', '-b:a', '160k',
    '-movflags', '+faststart', out]);
  console.log('wrote ' + out);
}

const what = process.argv[2] || 'all';
if (what === 'act1' || what === 'all') await record('act1');
if (what === 'act2' || what === 'all') await record('act2');
if (what === 'join' || what === 'all') join3();

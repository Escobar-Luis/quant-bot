// One trade on a TradingView Lightweight Chart: when it was posted, when you
// got in at the chosen delay, and when you got out. Prices come only from the
// results file: minute bars when the file carries them (`trade.bars`),
// otherwise the entry price at every delay plus the exit, as a line.
import { createChart, LineSeries, CandlestickSeries, createSeriesMarkers, ColorType } from 'lightweight-charts';

const sec = iso => Math.floor(Date.parse(iso) / 1000);
const ET = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' });
const ETD = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
export const etTime = iso => ET.format(new Date(iso));
const fmtT = t => ET.format(new Date(t * 1000));

let chart = null, series = null, marks = null, host = null, ro = null;

function ensure(el) {
  if (chart && host === el) return;
  destroy();
  host = el;
  chart = createChart(el, {
    autoSize: true,
    layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#a09e97', fontFamily: 'IBM Plex Mono,ui-monospace,monospace', fontSize: 12, attributionLogo: true },
    grid: { vertLines: { visible: false }, horzLines: { color: '#2a2927' } },
    rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.2, bottom: 0.2 } },
    timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false, tickMarkFormatter: t => fmtT(t), rightOffset: 1 },
    localization: { timeFormatter: t => ETD.format(new Date(t * 1000)), priceFormatter: p => '$' + p.toFixed(2) },
    crosshair: { horzLine: { labelBackgroundColor: '#3a3936' }, vertLine: { labelBackgroundColor: '#3a3936' } },
    handleScroll: false, handleScale: false
  });
}

export function destroy() {
  if (ro) { ro.disconnect(); ro = null; }
  if (chart) { chart.remove(); chart = null; series = null; marks = null; host = null; }
}

function linePoints(trade, delay) {
  const pts = Object.entries(trade.by_delay || {})
    .filter(([, v]) => v && v.entry_at && Number.isFinite(v.entry))
    .map(([, v]) => ({ time: sec(v.entry_at), value: v.entry }));
  const me = trade.by_delay?.[String(delay)];
  if (me && me.exit_at && Number.isFinite(me.exit)) pts.push({ time: sec(me.exit_at), value: me.exit });
  return uniq(pts);
}

function uniq(pts) {
  pts.sort((a, b) => a.time - b.time);
  return pts.filter((p, i) => i === 0 || p.time !== pts[i - 1].time);
}

const nearest = (pts, t) => pts.reduce((best, p) => (Math.abs(p.time - t) < Math.abs(best.time - t) ? p : best), pts[0]).time;

export function drawTrade(el, trade, delay, color, priceFmt) {
  ensure(el);
  if (priceFmt) chart.applyOptions({ localization: { priceFormatter: priceFmt } });
  if (series) { chart.removeSeries(series); series = null; marks = null; }
  const bars = Array.isArray(trade.bars) && trade.bars.length
    ? uniq(trade.bars.map(b => ({ time: sec(b.t || b.time), open: b.o ?? b.open, high: b.h ?? b.high, low: b.l ?? b.low, close: b.c ?? b.close })))
    : null;
  let pts;
  if (bars) {
    series = chart.addSeries(CandlestickSeries, { upColor: '#5fbf93', downColor: '#ef6f61', borderVisible: false, wickUpColor: '#5fbf93', wickDownColor: '#ef6f61', priceLineVisible: false, lastValueVisible: false });
    series.setData(bars);
    pts = bars;
  } else {
    series = chart.addSeries(LineSeries, { color: '#ecebe6', lineWidth: 2, priceLineVisible: false, lastValueVisible: false, pointMarkersVisible: true, pointMarkersRadius: 2.5 });
    pts = linePoints(trade, delay);
    series.setData(pts);
  }
  if (!pts.length) return false;
  const me = trade.by_delay?.[String(delay)];
  const short = trade.side === 'short';
  const list = [{ time: nearest(pts, sec(trade.posted_at)), position: 'belowBar', shape: 'arrowUp', color: '#a09e97', text: 'Posted' }];
  if (me?.entry_at) list.push({ time: nearest(pts, sec(me.entry_at)), position: short ? 'aboveBar' : 'belowBar', shape: 'circle', color, text: 'In' });
  if (me?.exit_at) list.push({ time: nearest(pts, sec(me.exit_at)), position: 'aboveBar', shape: 'arrowDown', color: '#a8c4f7', text: 'Out' });
  list.sort((a, b) => a.time - b.time);
  marks = createSeriesMarkers(series, list);
  chart.timeScale().fitContent();
  return true;
}

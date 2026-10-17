// Every number on screen comes from these files, bundled at build time:
// results/<course>/<version>.json (story 1) and proofs/prism.json (story 2).
// results/_sample.json stands in for a course until its real file exists.

const RESULTS = import.meta.glob('../../results/*/*.json', { eager: true, import: 'default' });
const SAMPLE = import.meta.glob('../../results/_sample.json', { eager: true, import: 'default' });
const PROOFS = import.meta.glob('../../proofs/prism.json', { eager: true, import: 'default' });

export const COURSE_META = [
  { key: 'lpp', name: 'Learn Plan Profit', kind: 'Stocks & options', hold: 'SPY' },
  { key: 'ziptrader', name: 'ZipTrader', kind: 'Stocks', hold: 'SPY' },
  { key: 'cryptowizard', name: 'Crypto Wizard', kind: 'Crypto', hold: 'BTC' }
];

const vnum = v => parseInt(String(v).replace(/\D/g, ''), 10) || 0;

function byCourse() {
  const out = {};
  for (const [path, json] of Object.entries(RESULTS)) {
    const m = path.match(/results\/([^/]+)\/([^/]+)\.json$/);
    if (!m || !json || json.schema !== 'results/1') continue;
    const [, course, version] = m;
    (out[course] ||= {})[version] = json;
  }
  const sample = Object.values(SAMPLE)[0];
  if (sample && sample.course && !out[sample.course]) out[sample.course] = { [sample.version || 'v1']: sample };
  return out;
}

export const RESULTS_BY_COURSE = byCourse();

// Latest extraction version wins the verdict (v2 is the fix).
export function latest(course) {
  const vs = RESULTS_BY_COURSE[course];
  if (!vs) return null;
  const k = Object.keys(vs).sort((a, b) => vnum(b) - vnum(a))[0];
  return vs[k];
}

export const PROOF = Object.values(PROOFS)[0] || null;

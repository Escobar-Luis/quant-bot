// Every number on screen comes from these files, bundled at build time:
// results/<course>/<version>.json (story 1) and proofs/prism.json (story 2).
// results/_sample.json stands in for a course until its real file exists.
// Two places: the repo root (normal build) or inside web/ (the Ninoo ZIP).

const RESULTS = import.meta.glob(['../../results/*/*.json', '../results/*/*.json'], { eager: true, import: 'default' });
const SAMPLE = import.meta.glob(['../../results/_sample.json', '../results/_sample.json'], { eager: true, import: 'default' });
const PROOFS = import.meta.glob(['../../proofs/prism.json', '../proofs/prism.json'], { eager: true, import: 'default' });

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

// The headline is the full-window file. A file marked `same_sessions.proof_set`
// (LPP v2: only the 30 traced sessions) is the fix's proof, never the headline.
const isProofSet = r => !!r?.same_sessions?.proof_set;
export function latest(course) {
  const vs = RESULTS_BY_COURSE[course];
  if (!vs) return null;
  const keys = Object.keys(vs).sort((a, b) => vnum(b) - vnum(a));
  return vs[keys.find(k => !isProofSet(vs[k])) ?? keys[0]];
}
export function proofSet(course) {
  const vs = RESULTS_BY_COURSE[course];
  return vs ? Object.values(vs).find(isProofSet) || null : null;
}

// results/strategy-lab.json (spec-audit story 21): his rules as code on new prices and other stocks. Missing: hidden.
const LABS = import.meta.glob(['../../results/strategy-lab.json', '../results/strategy-lab.json'], { eager: true, import: 'default' });
export const LAB = Object.values(LABS).find(j => j?.schema === 'strategy-lab/1') || null;

// results/paper/summary.json (spec-audit story 30): the frozen rules paper-traded forward from the freeze. Missing: hidden.
const PAPERS = import.meta.glob(['../../results/paper/summary.json', '../results/paper/summary.json'], { eager: true, import: 'default' });
export const PAPER_TEST = Object.values(PAPERS).find(j => j?.schema === 'paper/1') || null;

export const PROOF = Object.values(PROOFS)[0] || null;

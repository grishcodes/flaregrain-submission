// Checker stress test: synthetic sentences against the dashboard's own sentence checker.
//   node checker_stress.mjs <built dashboard page> <out.json> [sampleEvery]
// For every pair of comparable checked records it builds sentences from the records' real facts. GOOD sentences restate a
// cited fact faithfully and should pass; BAD sentences carry one known defect (a wrong number, a wrong unit, the other record's
// fact, a cause word, no citation, an invented detail, a disputed value stated as fact, ...) and should be removed. It reports,
// by class, the bad sentences that pass (misses) and the good ones that are removed (false alarms).
// The checker is checkSentence() from the built page, loaded with page-logic.mjs, so the test exercises the code users get.
// Ported from the team's Mac Mini run of November 14 (job5_fuzz.mjs), which drove the same generator through a browser; the
// sentence generator below is unchanged. Node 18 or later; no browser, no network.
import {writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {loadPageLogic} from './page-logic.mjs';

const [pagePath, outPath, sampleArg] = process.argv.slice(2);
if (!pagePath || !outPath) { console.error('usage: node checker_stress.mjs <built dashboard page> <out.json> [sampleEvery]'); process.exit(2); }
const sampleEvery = Number(sampleArg || 1);
const t0 = Date.now();
const L = loadPageLogic(resolve(pagePath));
const ids = [...new Set(L.nasaComparisonIds)];
const pairs = [];
for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) pairs.push([ids[i], ids[j]]);
const P = {};
const meta = pairs.map(([a, b]) => {
  const facts = L.explanationFacts([a, b].flatMap(L.recordExportRows)), names = [a, b].map(id => L.comparisonRun(id).name);
  P[a + '|' + b] = {facts, names};
  return {key: a + '|' + b, facts, names};
});

{
  // ---------- generator ----------
  const NUM = /(?<![A-Za-z\d.])(\d+(?:\.\d+)?)/g;
  const verbs = ['reports', 'lists', 'records', 'gives', 'shows', 'notes', 'states', 'has'];
  const unitSwap = [[/ mm\b/, ' cm'], [/ cm\/s\b/, ' mm/s'], [/ mm\/s\b/, ' cm/s'], [/ s\b/, ' min'], [/ psi\b/, ' kPa'], [/ kPa\b/, ' psi'], [/ cm\b/, ' mm'], [/%/, ' ppm']];
  const invented = [' in a vacuum chamber', ' using a laser igniter', ' with a tungsten filament', ' under argon dilution'];
  const cases = [];
  let n = 0;
  const FRAME = /^(.+?) (reports|lists|records|gives|shows|notes|states|has) (.+?) of (.+)\.$/;
  const push = (key, expect, klass, text, cites) => { if ((n++ % sampleEvery) === 0) cases.push({key, expect, klass, text, cites}); };
  // Every "X verb field of V." sentence is also tried in two other frames, to test phrasing robustness.
  const add = (key, expect, klass, text, cites) => {
    push(key, expect, klass, text, cites);
    const m = text.match(FRAME);
    if (m && !/^Both /.test(text)) {
      push(key, expect, klass + ' [frame: For X, field is V]', `For ${m[1]}, ${m[3]} is ${m[4]}.`, cites);
      push(key, expect, klass + ' [frame: X — field: V]', `${m[1]} — ${m[3]}: ${m[4]}.`, cites);
    }
  };
  const lc = s => s.charAt(0).toLowerCase() + s.slice(1);
  const clean = v => v.replace(/\s+/g, ' ').replace(/[.;]\s*$/, '');
  for (const {key, facts, names} of meta) {
    const allText = facts.map(f => f.field + ' ' + f.value).join(' ').toLowerCase();
    for (const order of [[0, 1], [1, 0]]) {
      const [A, B] = order.map(i => names[i]);
      const fa = facts.filter(f => f.record === A), fb = facts.filter(f => f.record === B);
      for (const f of fa) {
        const v = clean(f.value);
        if (f.kind === 'disputed') {
          add(key, 'pass', 'G3 dispute stated', `${A}'s ${lc(f.field)} is disputed: the report and the archive disagree.`, [f.id]);
          add(key, 'remove', 'B5 disputed field stated as fact', `${A} reports ${lc(f.field)} of ${v}.`, [f.id]);
          continue;
        }
        if (f.kind === 'missing') continue;
        for (const verb of verbs) {
          const good = `${A} ${verb} ${lc(f.field)} of ${v}.`;
          add(key, 'pass', 'G1 single fact restated', good, [f.id]);
          add(key, 'pass', 'G4 fact marker in parentheses (cleaned)', `${A} ${verb} ${lc(f.field)} of ${v} (${f.id}).`, [f.id]);
          add(key, 'remove', 'B6 cause word', good.replace(/\.$/, ', which caused the flame to go out.'), [f.id]);
          add(key, 'remove', 'B7 no citation', good, []);
          add(key, 'remove', 'B2 fact given to the other record', `${B} ${verb} ${lc(f.field)} of ${v}.`, [f.id]);
          add(key, 'remove', 'B8 fact ID left in text', `${A} ${verb} ${lc(f.field)} of ${v} as ${f.id} shows.`, [f.id]);
          for (const term of invented)
            if (!new RegExp('\\b' + term.trim().split(' ').at(-1) + '\\b', 'i').test(allText)) add(key, 'remove', 'B10 invented detail', good.replace(/\.$/, term + '.'), [f.id]);
          const nums = [...v.matchAll(NUM)].map(m => m[1]);
          for (const [k, num] of nums.slice(0, 3).entries()) {
            for (const factor of [1.37, 0.5, 10, 0.1, 1.1, 2]) {
              const wrong = String(+(Number(num) * factor + (factor === 10 ? 0 : 7)).toFixed(num.includes('.') ? num.split('.')[1].length : 0));
              if (wrong === num || allText.includes(wrong)) continue;
              let idx = -1; const re = new RegExp('(?<![A-Za-z\\d.])' + num.replace('.', '\\.') + '(?![\\d])', 'g');
              const bad = v.replace(re, m => (++idx === 0 ? wrong : m));  // first occurrence of this number
              add(key, 'remove', 'B1 wrong number', `${A} ${verb} ${lc(f.field)} of ${bad}.`, [f.id]);
            }
          }
          for (const [re, to] of unitSwap) if (re.test(v)) { add(key, 'remove', 'B3 wrong unit', `${A} ${verb} ${lc(f.field)} of ${v.replace(re, to)}.`, [f.id]); break; }
          if (!fb.some(g => clean(g.value) === v)) add(key, 'remove', 'B4 "both" for one record\'s fact', `Both ${A} and ${B} ${verb.replace(/s$/, '')} ${lc(f.field)} of ${v}.`, [f.id]);
          add(key, 'remove', 'B9 false absence', `${A} does not report ${lc(f.field)}.`, [f.id]);
        }
      }
      // two-record sentences
      for (const f of fa) for (const g of fb) {
        if (f.kind || g.kind) continue;
        const vf = clean(f.value), vg = clean(g.value);
        if (f.field === g.field) {
          add(key, 'pass', 'G2 same field, both records', `${A} reports ${lc(f.field)} of ${vf}, while ${B} reports ${lc(g.field)} of ${vg}.`, [f.id, g.id]);
          const nf = [...vf.matchAll(NUM)].map(m => m[1]), ng = [...vg.matchAll(NUM)].map(m => m[1]);
          if (nf.length && ng.length) add(key, 'remove', 'B12 "respectively"', `${A} and ${B} report ${lc(f.field)} of ${nf[0]} and ${ng[0]} respectively.`, [f.id, g.id]);
        }
        const uf = vf.match(/\d\s?(mm|cm\/s|mm\/s|psi|kPa|s)\b/), ug = vg.match(/\d\s?(mm|cm\/s|mm\/s|psi|kPa|s)\b/);
        const dim = u => ({mm: 'L', 'cm/s': 'V', 'mm/s': 'V', psi: 'P', kPa: 'P', s: 'T'})[u];
        if (uf && ug && dim(uf[1]) !== dim(ug[1]) && f.field !== g.field)
          add(key, 'remove', 'B11 unlike quantities set against each other', `${A} reports ${lc(f.field)} of ${vf}, while ${B} reports ${lc(g.field)} of ${vg}.`, [f.id, g.id]);
      }
    }
  }
  // ---------- run through the checker ----------
  const results = cases.map(c => {
    const p = P[c.key];
    let problems;
    try { problems = L.checkSentence({text: c.text, cites: c.cites}, p.facts, p.names).problems; } catch (e) { problems = ['ERROR ' + e.message]; }
    return {...c, problems};
  });
  const byClass = {};
  for (const r of results) {
    const c = byClass[r.klass] ||= {expect: r.expect, total: 0, wrong: 0, examples: [], reasons: {}};
    c.total++;
    const passed = r.problems.length === 0;
    const wrong = r.expect === 'pass' ? !passed : passed;
    if (wrong) { c.wrong++; if (c.examples.length < 8) c.examples.push({text: r.text, cites: r.cites, problems: r.problems}); }
    if (r.expect === 'pass' && !passed) for (const p of r.problems) { const k = p.replace(/“[^”]*”/g, '“…”').replace(/[\d.]+/g, '#').slice(0, 90); c.reasons[k] = (c.reasons[k] || 0) + 1; }
  }
  for (const c of Object.values(byClass)) c.reasons = Object.fromEntries(Object.entries(c.reasons).sort((a, b) => b[1] - a[1]).slice(0, 8));
  const summary = {records: ids.length, pairs: meta.length, sentences: results.length,
    good: results.filter(r => r.expect === 'pass').length, bad: results.filter(r => r.expect === 'remove').length,
    bad_that_pass: results.filter(r => r.expect === 'remove' && !r.problems.length).length,
    good_removed: results.filter(r => r.expect === 'pass' && r.problems.length).length,
    errors: results.filter(r => r.problems.some(p => p.startsWith('ERROR'))).length, seconds: (Date.now() - t0) / 1000};
  await writeFile(outPath, JSON.stringify({summary, byClass}, null, 1));
  console.log(JSON.stringify(summary));
  for (const [k, c] of Object.entries(byClass)) console.log(`${k}: ${c.wrong}/${c.total} wrong (expected ${c.expect})`);
}

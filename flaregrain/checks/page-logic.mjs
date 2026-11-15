// Loads the dashboard's own script and hands back its explanation functions, so the proxy uses
// exactly the page's facts, prompt and checker (explanationFacts, comparisonPrompt, checkSentence),
// never a copy that can drift.
//
// How: read the built page, take its data blocks and its one application script, and run that
// script in a Node vm with an inert stand-in for the DOM. One line is added before the script's
// final render() call to export the functions; render() itself is not run. Nothing is fetched
// and nothing is written.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// An object that absorbs any property read, call or assignment. The page's setup code touches the
// DOM at load; none of that matters here, it only has to not throw.
function inert() {
  const target = function () {};
  const handler = {
    get(_, key) {
      if (key === Symbol.toPrimitive) return hint => (hint === 'number' ? 0 : '');
      if (key === Symbol.iterator) return function* () {};
      if (key === 'then') return undefined; // never look like a promise
      if (key === 'length' || key === 'scrollTop' || key === 'offsetWidth' || key === 'clientWidth') return 0;
      if (key === 'dataset' || key === 'style') return {};
      if (key === 'classList') return {add() {}, remove() {}, toggle() {}, contains: () => false};
      return proxy;
    },
    set: () => true,
    apply: () => proxy,
    construct: () => proxy,
    has: () => false,
  };
  const proxy = new Proxy(target, handler);
  return proxy;
}

const EXPORT = 'globalThis.__flaregrain={recordExportRows,explanationFacts,comparisonPrompt,checkSentence,' +
  'explanationSchema,explanationSystem,comparisonRun,nasaComparisonIds,explainableId,isPsiRow,factsDigest};';

export function loadPageLogic(pagePath) {
  const html = readFileSync(pagePath, 'utf8');
  const blocks = new Map();
  for (const m of html.matchAll(/<script id="([^"]+)" type="application\/json">([\s\S]*?)<\/script>/g)) {
    blocks.set(m[1], m[2].replaceAll('<\\/', '</'));
  }
  const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)(?![^>]*application\/json)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  const app = scripts.find(s => s.includes("'use strict'") && s.includes('function checkSentence('));
  if (!app) throw new Error('No application script with checkSentence() in ' + pagePath);
  const tail = /\n\s*render\(\);\s*\n\}\)\(\);\s*$/;
  if (!tail.test(app)) throw new Error('The application script no longer ends with render(); })(); — update page-logic.mjs');
  const source = app.replace(tail, '\n' + EXPORT + '\n})();\n');

  const element = id => {
    if (blocks.has(id)) return {textContent: blocks.get(id)};
    return inert();
  };
  const document = inert();
  const documentShim = new Proxy(document, {
    get(target, key) {
      if (key === 'getElementById') return element;
      if (key === 'documentElement') return {dataset: {build: 'proxy'}, classList: inert(), style: {}};
      if (key === 'querySelectorAll') return () => [];
      return target[key];
    },
  });
  const storage = {getItem: () => null, setItem() {}, removeItem() {}};
  const context = {
    console, JSON, Math, Date, Intl, Map, Set, WeakMap, WeakSet, Array, Object, String, Number, Boolean, RegExp, Symbol, Promise, Error,
    TypeError, SyntaxError, URL, URLSearchParams, Blob: function () {}, AbortSignal, structuredClone,
    document: documentShim, window: inert(), navigator: {userAgent: 'mini-api'}, location: {search: '', protocol: 'http:', hash: '', href: 'http://proxy/'},
    localStorage: storage, sessionStorage: storage, performance: {now: () => 0},
    matchMedia: () => ({matches: false, addEventListener() {}, addListener() {}}),
    requestAnimationFrame: () => 0, cancelAnimationFrame() {}, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
    getComputedStyle: () => inert(), ResizeObserver: function () { return inert(); }, IntersectionObserver: function () { return inert(); },
    MutationObserver: function () { return inert(); }, CSS: {escape: s => String(s)},
    fetch: () => Promise.reject(new Error('no network in the proxy page logic')),
    d3: inert(), gsap: inert(), Flip: inert(),
  };
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(source, context, {filename: 'Foundry dashboard (page logic)', timeout: 20000});
  const logic = context.__flaregrain;
  if (!logic || typeof logic.checkSentence !== 'function') throw new Error('Page logic did not export');
  // Checked NASA records only: the issue's contract is "two record IDs from the checked-records list".
  const checkedIds = [...new Set(logic.nasaComparisonIds)].filter(id => !logic.isPsiRow(id));
  return {...logic, checkedIds};
}

// Live Explain checks for redesign/server.mjs, against a stand-in model proxy on a free local port. run.py runs this
// and reads its "passed"/"FAILED" lines. Nothing leaves this computer.
import http from 'node:http';
import {server, live, factsDigest} from '../redesign/server.mjs';

delete process.env.FLAREGRAIN_MINI_EXPLAIN_URL;
let failed = 0;
const expect = (name, ok, detail = '') => {
  if (!ok) failed += 1;
  console.log((ok ? 'passed ' : 'FAILED ') + 'live Explain: ' + name + (ok || !detail ? '' : ' (' + detail + ')'));
};
const listen = s => new Promise(resolve => s.listen(0, '127.0.0.1', () => resolve(s.address().port)));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

// The public fingerprints the Mini's public copy returns for the same records (mini-api/public-facts.json).
const PUBLIC = {'B1,S1': 'e0595b4c', 'S1,B1': '0b065766', 'B1,B10': '60f94e18', 'B10,B1': 'bbec013e',
  'FLEX-002,S31': 'a8ae59fc', 'S31,FLEX-002': '93ef1bf4'};
const NAMES = {B1: 'BASS-II B1', S1: 'Saffire I-1', B10: 'BASS-II B10', 'FLEX-002': 'FLEX test 2', S31: 'Saffire III-1'};

// Stand-in proxy. `stub` decides each reply; every request is recorded.
const seen = [];
const stub = {health: () => [200, {ok: true, model: 'qwen3:4b', records: 11, usedThisHour: 0, capPerHour: 6}], healthDelay: 0,
  explain: ids => [200, answer(ids)], explainDelay: 0};
function answer(ids, extra = {}) {
  return {ids, records: ids.map(id => NAMES[id]), model: 'qwen3:4b', seconds: 10.4, factsHash: PUBLIC[ids.join(',')],
    passed: [{text: 'Both records report a flame that went out after the airflow stopped.', cites: ['F1', 'F9'], problems: []},
      {text: ids[0] + ' is the first record.', cites: ['F2'], problems: []}],
    removed: [{text: 'An invented 987 vol% oxygen sentence.', cites: ['F1'], problems: ['987 vol% is not in the fields']}], ...extra};
}
const proxy = http.createServer((req, res) => {
  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', async () => {
    seen.push({method: req.method, path: req.url, type: req.headers['content-type'] || '', body});
    const reply = req.url === '/health' ? (await wait(stub.healthDelay), stub.health())
      : req.url === '/explain' && req.method === 'POST' ? (await wait(stub.explainDelay), stub.explain(JSON.parse(body).ids))
      : [404, {error: 'Not found'}];
    if (res.destroyed) return;
    res.writeHead(reply[0], {'Content-Type': 'application/json'});
    res.end(typeof reply[1] === 'string' ? reply[1] : JSON.stringify(reply[1]));
  });
});
const proxyUrl = 'http://127.0.0.1:' + await listen(proxy);
const site = 'http://127.0.0.1:' + await listen(server);

const get = path => fetch(site + path).then(async r => ({status: r.status, text: await r.text()}));
const post = (body, {path = '/api/explain', type = 'application/json'} = {}) => {
  const started = Date.now();
  return fetch(site + path, {method: 'POST', headers: {'Content-Type': type}, body: typeof body === 'string' ? body : JSON.stringify(body)})
    .then(async r => ({status: r.status, body: await r.json().catch(() => null), cache: r.headers.get('cache-control'), ms: Date.now() - started}));
};
const compareLive = async ids => JSON.parse((await get('/api/compare?ids=' + ids)).text).live;
const reset = () => {
  seen.length = 0;
  Object.assign(stub, {health: () => [200, {ok: true, model: 'qwen3:4b', records: 11, usedThisHour: 0, capPerHour: 6}], healthDelay: 0,
    explain: ids => [200, answer(ids)], explainDelay: 0});
};
const savedReply = (r, code, reason, status) => r.status === code && r.body?.reason === reason && r.body.error === status &&
  r.body.status === status && 'explanation' in r.body && r.cache === 'no-store';
const UNAVAILABLE = 'Live model unavailable. The saved comparison stays.';
const LIMITED = 'Live answers are limited right now. The saved comparison stays.';

// The ported fingerprint gives the published records' values, in both orders.
expect('the facts fingerprint matches the public records for all six starter orders',
  Object.entries(PUBLIC).every(([key, hash]) => factsDigest(key.split(',')) === hash),
  Object.keys(PUBLIC).map(key => key + '=' + factsDigest(key.split(','))).join(' '));
expect('the wait is a 4 s check, then the answer, within 40 s in all (functions stop at 45 s)',
  live.checkMs === 4000 && live.waitMs === 40000 && live.deadlineMs === 40000);

// Unset: no live flag, no call to any proxy, and the saved comparison with a status.
reset();
expect('unset: Compare offers no live model', (await compareLive('B1,S1')) === false && (await compareLive('FLEX-002,S31')) === false);
let r = await post({ids: ['B1', 'S1']});
expect('unset: Explain returns the saved comparison and "Live model unavailable"', savedReply(r, 503, 'off', UNAVAILABLE) &&
  r.body.explanation === null && String(r.body.ids) === 'B1,S1', JSON.stringify(r.body));
r = await post({ids: ['B1', 'B10']});
expect('unset: a pair with a saved explanation gets it back unchanged', savedReply(r, 503, 'off', UNAVAILABLE) &&
  r.body.explanation?.kind === 'saved' && r.body.explanation.sentences.length > 0, JSON.stringify(r.body).slice(0, 200));
process.env.FLAREGRAIN_MINI_EXPLAIN_URL = 'not a url';
expect('a malformed address counts as unset', (await compareLive('B1,S1')) === false && (await post({ids: ['B1', 'S1']})).body?.reason === 'off');
process.env.FLAREGRAIN_MINI_EXPLAIN_URL = 'ftp://127.0.0.1/';
expect('a non-HTTP address counts as unset', (await compareLive('B1,S1')) === false);
expect('unset: nothing reaches the proxy', seen.length === 0);

// Set: the three starter pairs, either order.
process.env.FLAREGRAIN_MINI_EXPLAIN_URL = proxyUrl + '/';
expect('set: Compare offers the live model for the starter pairs in both orders',
  (await Promise.all(Object.keys(PUBLIC).map(compareLive))).every(flag => flag === true));
expect('set: other pairs keep no live model', (await compareLive('B1,S25')) === false && (await compareLive('S12,S26')) === false);
for (const key of Object.keys(PUBLIC)) {
  reset();
  const ids = key.split(',');
  r = await post({ids});
  const forwarded = seen.find(item => item.path === '/explain');
  expect('accept: ' + key + ' (fingerprint ' + PUBLIC[key] + ')', r.status === 200 && String(r.body.ids) === key &&
    r.body.factsHash === PUBLIC[key] && r.body.passed.length === 2 && r.body.passed.every(item => Object.keys(item).join() === 'text') &&
    r.body.removed.length === 1 && !JSON.stringify(r.body.removed).includes('987') && r.body.seconds === 10.4 && r.cache === 'no-store',
  JSON.stringify(r.body));
  expect('forward: ' + key + ' sends exactly {"ids":[…]} as JSON after one health check',
    seen.length === 2 && seen[0].path === '/health' && seen[0].method === 'GET' && forwarded?.method === 'POST' &&
    /^application\/json/.test(forwarded.type) && forwarded.body === JSON.stringify({ids}));
}

reset();
r = await post({ids: ['B1', 'S25']});
expect('non-starter pair: saved comparison, nothing forwarded', savedReply(r, 503, 'pair', UNAVAILABLE) && seen.length === 0, JSON.stringify(r.body));

reset();
stub.explain = ids => [200, answer(ids, {ids: [...ids].reverse()})];
r = await post({ids: ['B1', 'S1']});
expect('wrong pair: an answer naming S1,B1 for B1,S1 is refused', savedReply(r, 503, 'mismatch', UNAVAILABLE), JSON.stringify(r.body));

reset();
stub.explain = ids => [200, answer(ids, {factsHash: '77980310'})];
r = await post({ids: ['B1', 'S1']});
expect('wrong fingerprint: the laptop build\'s 77980310 is refused for the public B1,S1', savedReply(r, 503, 'mismatch', UNAVAILABLE), JSON.stringify(r.body));

reset();
stub.explain = ids => [200, answer(ids, {passed: [{text: 'A sentence the checker flagged.', cites: ['F1'], problems: ['Cites no fact']}]})];
r = await post({ids: ['B1', 'B10']});
expect('a "passed" sentence with problems is refused', savedReply(r, 503, 'mismatch', UNAVAILABLE));

reset();
stub.explain = () => [200, 'not json'];
r = await post({ids: ['B1', 'B10']});
expect('an answer that is not JSON is refused', savedReply(r, 503, 'mismatch', UNAVAILABLE));

reset();
stub.explain = () => [429, {error: 'Hourly limit reached'}];
r = await post({ids: ['B1', 'S1']});
expect('429 from the proxy: "Live answers are limited right now"', savedReply(r, 429, 'limit', LIMITED), JSON.stringify(r.body));

reset();
stub.health = () => [200, {ok: true, model: 'qwen3:4b', records: 11, usedThisHour: 6, capPerHour: 6}];
r = await post({ids: ['B1', 'S1']});
expect('cap used up at the health check: limited, and no answer is spent', savedReply(r, 429, 'cap', LIMITED) &&
  !seen.some(item => item.path === '/explain'));

reset();
stub.explain = () => [503, {error: 'The model is busy with another request'}];
r = await post({ids: ['FLEX-002', 'S31']});
expect('503 busy: limited, at once', savedReply(r, 429, 'busy', LIMITED) && r.ms < 2000);

reset();
stub.explain = () => [504, {error: 'The model took too long'}];
r = await post({ids: ['FLEX-002', 'S31']});
expect('504 or other proxy errors: unavailable', savedReply(r, 503, 'upstream', UNAVAILABLE));

reset();
stub.health = () => [502, 'Bad Gateway'];
r = await post({ids: ['B1', 'S1']});
expect('proxy stopped behind the tunnel (health 502): unavailable, nothing spent', savedReply(r, 503, 'unreachable', UNAVAILABLE) &&
  !seen.some(item => item.path === '/explain'));

reset();
stub.healthDelay = 6000;
r = await post({ids: ['B1', 'S1']});
expect('health hangs: the saved comparison comes back at 4 s, nothing spent',
  savedReply(r, 503, 'unreachable', UNAVAILABLE) && r.ms >= 3900 && r.ms < 5500 && !seen.some(item => item.path === '/explain'), r.ms + ' ms');

reset();
stub.explainDelay = 5000;
r = await post({ids: ['B1', 'S1']});
expect('a real-speed answer after 5 s is still shown (no 4 s cut-off on the answer)', r.status === 200 && r.body.factsHash === 'e0595b4c', r.ms + ' ms');

reset();
live.waitMs = 1500;
stub.explainDelay = 3000;
r = await post({ids: ['B1', 'S1']});
live.waitMs = 40000;
expect('an answer past the wait is dropped: unavailable at the limit', savedReply(r, 503, 'timeout', UNAVAILABLE) && r.ms >= 1400 && r.ms < 2800, r.ms + ' ms');

reset();
live.deadlineMs = 2500;
stub.healthDelay = 1000;
stub.explainDelay = 3000;
r = await post({ids: ['B1', 'S1']});
live.deadlineMs = 40000;
expect('a slow health check shortens the wait: the whole request ends at the overall limit',
  savedReply(r, 503, 'timeout', UNAVAILABLE) && r.ms >= 2400 && r.ms < 3300, r.ms + ' ms');

const closed = http.createServer();
const closedPort = await listen(closed);
await new Promise(resolve => closed.close(resolve));
process.env.FLAREGRAIN_MINI_EXPLAIN_URL = 'http://127.0.0.1:' + closedPort;
reset();
r = await post({ids: ['B1', 'S1']});
expect('network error (nothing listening): unavailable at once', savedReply(r, 503, 'unreachable', UNAVAILABLE) && r.ms < 2000, r.ms + ' ms');
process.env.FLAREGRAIN_MINI_EXPLAIN_URL = proxyUrl;

// Requests the page never sends. GET keeps today's 404; other POSTs keep today's 405.
reset();
const refusals = [
  ['extra key', {ids: ['B1', 'S1'], question: 'Why?'}, 400], ['one ID', {ids: ['B1']}, 400], ['the same ID twice', {ids: ['B1', 'B1']}, 400],
  ['unknown ID', {ids: ['B1', 'nope']}, 400], ['SAME baseline (not a comparable run)', {ids: ['B1', 'SAME-KAPTON']}, 400],
  ['not JSON', 'ids=B1,S1', 400], ['oversized body', {ids: ['B1', 'S1'], pad: 'x'.repeat(400)}, 413],
];
for (const [name, body, code] of refusals) {
  r = await post(body);
  expect('refuses ' + name + ' (' + code + ')', r.status === code && typeof r.body?.error === 'string');
}
r = await post({ids: ['B1', 'S1']}, {type: 'text/plain'});
expect('refuses a non-JSON content type (415)', r.status === 415);
r = await post({ids: ['B1', 'S1']}, {path: '/api/compare'});
expect('other POSTs keep 405 "Use GET or HEAD."', r.status === 405 && r.body?.error === 'Use GET or HEAD.');
const g = await get('/api/explain');
expect('GET /api/explain keeps 404 "Not found."', g.status === 404 && JSON.parse(g.text).error === 'Not found.');
expect('refused requests never reach the proxy', seen.length === 0);

server.close();
proxy.close();
console.log(failed ? failed + ' live Explain check(s) failed' : 'all live Explain checks passed');
process.exit(failed ? 1 : 0);

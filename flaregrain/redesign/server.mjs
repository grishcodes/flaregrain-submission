import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const data = JSON.parse(await readFile(new URL('../data/compare-data.json', import.meta.url), 'utf8'));
const starter = data.starters[0];
const orderedPair = data.pairs[starter.ids.join(',')];
// The Ask matcher below answers from the two records of the prepared airflow pair only (Codex's lane, unchanged).
const records = new Map(orderedPair.records.map(record => [record.id, record]));
// Everything else reads the 13 hand-checked NASA records; 11 are runs with prepared comparisons, and SAME's two Kapton
// material baselines are records only.
const checked = new Map(data.checked.map(record => [record.id, record]));
const comparable = new Set(data.records.map(record => record.id));
// Moon & Mars air: a snapshot of the full-data demo's habitat answers (counts and record ids only; data/moon-mars-air.json,
// copied beside the pages because the preview ships this folder whole). Names and NASA sources come from the checked records.
const habitat = JSON.parse(await readFile(new URL('moon-mars-air.json', import.meta.url), 'utf8'));
const habitatRecords = Object.fromEntries([...checked.values()].map(record =>
  [record.id, {name: record.name, investigation: record.investigation, source: record.source, comparable: comparable.has(record.id)}]));

const files = new Set([
  'index.html', 'answer.html', 'browse.html', 'compare.html', 'evidence.html', 'habitat.html',
  'insights.html', 'system.html', 'app.js', 'compare.js', 'drawer.js', 'pages.js', 'styles.css', 'favicon.svg', 'favicon.png',
]);
const types = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css', 'svg': 'image/svg+xml', 'png': 'image/png'};
const notIncluded = 'This view needs the full NASA PSI dataset, which the team shows in the full-data demo.';
const cutoffQuestion = 'How long did the flame take to go out after airflow was cut?';
const scopeLimit = 'The cited passages give no elapsed time from airflow shutoff to extinction in seconds.';
const saffireDuration = ' In Saffire, 420 seconds is the time up to shutoff.';

function answer(query) {
  const mentionsCutoff = /\b(?:airflow|flow|fan)\b.{0,36}\b(?:cut|off|stop(?:s|ped)?|shut)\b|\b(?:cutoff|shutoff)\b/i.test(query);
  const mentionsExtinction = /\b(?:extinction|extinguish\w*|(?:go|went) out|how (?:long|quickly)|time|seconds?)\b/i.test(query);
  const asksWhatHappened = /^what (?:happened|happens) (?:when|after|once)\b/i.test(query);
  const selected = [
    [/\b(?:B1|BASS(?:-II)?)\b/i, 'B1'],
    [/\b(?:Saffire|S1)\b/i, 'S1'],
  ].filter(([pattern]) => pattern.test(query)).map(([, id]) => records.get(id));
  const pair = selected.length ? selected : [...records.values()];
  const findings = mentionsCutoff && (mentionsExtinction || asksWhatHappened) ? pair.map(record => ({
    text: record.id === 'B1'
      ? 'The BASS-II B1 flame went out quickly after airflow was stopped.'
      : 'The Saffire I-1 flame went out immediately when airflow stopped at the end of the run.',
    source: record.source,
  })) : [];
  const related = mentionsCutoff || selected.length > 0;
  return {
    query,
    status: findings.length ? 'supported' : 'no-match',
    findings,
    limitation: findings.length ? scopeLimit + (pair.some(record => record.id === 'S1') ? saffireDuration : '') : 'For now, Ask answers from 2 of the 13 checked records, and they do not answer that question directly.',
    supportingSources: findings.map(finding => finding.source),
    ranks: (related ? pair : []).map(record => ({
      id: record.id, name: record.name, relevance: 'Checked record', source: record.source, comparable: true,
    })),
    compare: related && pair.length === 2 ? starter.ids : null,
    investigations: [], passages: [],
  };
}

function summary() {
  const countFields = tier => [...checked.values()].flatMap(record =>
    record.fields.filter(field => field.tier === tier).map(field => ({record: record.name, field: field.field})));
  const describe = fields => ({
    values: fields.length, records: new Set(fields.map(field => field.record)).size,
    checkedRecords: checked.size, example: fields[0] || null,
  });
  return {
    library: {investigations: new Set([...checked.values()].map(record => record.study)).size, runs: comparable.size},
    moon: {runs: '—', investigations: []},
    gaps: describe(countFields('missing')), disputes: describe(countFields('dispute')),
  };
}

function catalog(search) {
  const query = (search.get('q') || '').trim().toLowerCase();
  const study = search.get('study');
  const rows = [...checked.values()].filter(record =>
    (!study || record.study === study) && [record.name, record.study, record.observation, ...(record.events || [])].join(' ').toLowerCase().includes(query));
  return {
    total: rows.length, page: 0, pageSize: checked.size,
    records: rows.map(record => ({...record, observation: (record.events || []).at(-1) ?? record.observation, origin: 'checked', comparable: comparable.has(record.id)})),
    studies: [...new Set([...checked.values()].map(record => record.study))].map(name => ({name})),
  };
}

function evidence(ids) {
  return ids.map(id => {
    const record = checked.get(id);
    const citedFields = record.fields.filter(field => field.tier === 'dispute')
      .flatMap(field => [{label: field.source, url: field.url}, {label: field.archive, url: field.archiveUrl}]);
    const sources = [...new Map([record.source, ...citedFields].filter(source => source.url)
      .map(source => [source.url, source])).values()];
    return {...record, sources};
  });
}

function exportRows(pair, format) {
  const rows = pair.records.flatMap(record => record.fields.map(field => ({record: record.name, ...field})));
  if (format === 'json') return JSON.stringify({ids: pair.ids, rows}, null, 2);
  const cols = ['record', 'field', 'value', 'tier', 'status', 'source', 'url', 'archive', 'archiveUrl'];
  const quote = value => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  return [cols.join(','), ...rows.map(row => cols.map(col => quote(row[col])).join(','))].join('\r\n') + '\r\n';
}

// Live Explain (#13, #15). Off unless the deployment sets FLAREGRAIN_MINI_EXPLAIN_URL to the public model proxy's base
// URL (never committed). Only the three starter pairs, in either order. The server first asks the proxy's /health for up
// to 4 s: if it can't be reached or the hourly cap is used up, the page gets its saved comparison back at once and no
// live answer is spent. Otherwise it waits for checked sentences, but never past 40 s from the request in all,
// because the deployment's functions stop at 45 s. A warm answer takes about 13 s on the Mini and about 4 s more through
// the tunnel and the function start, so a 14 s limit cut off every answer. It keeps the sentences only if they name the pair
// asked for and carry the facts fingerprint of the published records below. Anything else (429, 503, another pair or
// fingerprint, a timeout or a network error) returns what the page already shows for the pair, with a short status.
// While the variable is unset, every other response is unchanged.
export const live = {checkMs: 4000, waitMs: 40000, deadlineMs: 40000};
const livePairs = new Set([['B1', 'S1'], ['B1', 'B10'], ['FLEX-002', 'S31']].flatMap(([a, b]) => [a + ',' + b, b + ',' + a]));
const unavailable = 'Live model unavailable. The saved comparison stays.';
const limited = 'Live answers are limited right now. The saved comparison stays.';

function liveBase() {
  try {
    const url = new URL((process.env.FLAREGRAIN_MINI_EXPLAIN_URL || '').trim());
    return /^https?:$/.test(url.protocol) && !url.username && !url.password && !url.search && !url.hash ? url.href.replace(/\/+$/, '') : '';
  } catch { return ''; }
}

// The dashboard's facts fingerprint (factsDigest over explanationFacts in its model code): FNV-1a over the record name,
// field, value and status of every exported field except the sample identifier, in the order of the pair.
export function factsDigest(ids) {
  const text = ids.flatMap(id => checked.get(id).fields.filter(field => field.field !== 'Sample or identifier')
    .map(field => [checked.get(id).name, field.field, String(field.value), field.status || ''].join('|'))).join('\n');
  let hash = 2166136261 >>> 0;
  for (let i = 0; i < text.length; i++) { hash ^= text.charCodeAt(i); hash = Math.imul(hash, 16777619) >>> 0; }
  return hash.toString(16).padStart(8, '0');
}

// A proxy answer counts only for the pair asked, with these records' fingerprint, and only its checked sentences go out.
function bound(answer, ids, started) {
  const sentence = item => item && typeof item.text === 'string' && item.text.trim() && item.text.length <= 600 &&
    (item.problems === undefined || (Array.isArray(item.problems) && !item.problems.length));
  if (!answer || !Array.isArray(answer.ids) || answer.ids.length !== 2 || answer.ids[0] !== ids[0] || answer.ids[1] !== ids[1] ||
    answer.factsHash !== factsDigest(ids) || !Array.isArray(answer.passed) || !answer.passed.length || answer.passed.length > 7 ||
    !answer.passed.every(sentence) || (answer.removed !== undefined && !Array.isArray(answer.removed))) return null;
  return {
    ids, records: ids.map(id => checked.get(id).name), model: typeof answer.model === 'string' ? answer.model.slice(0, 40) : 'qwen3:4b',
    seconds: Number.isFinite(answer.seconds) ? answer.seconds : +((Date.now() - started) / 1000).toFixed(1),
    factsHash: answer.factsHash, passed: answer.passed.map(item => ({text: item.text.trim()})),
    removed: (answer.removed || []).map(() => ({})), // counted on the page; sentences the checker removed are not sent
    // The proxy keeps each pair's answer and sends it again at once (same model, same facts, temperature 0); the page says
    // when the model wrote it, so a reused answer is never shown as freshly written.
    ...(answer.cached === true && typeof answer.generatedAt === 'string' && Number.isFinite(Date.parse(answer.generatedAt))
      ? {cached: true, generatedAt: new Date(Date.parse(answer.generatedAt)).toISOString()} : {}),
  };
}

function readBody(req, limit = 256) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', chunk => { size += chunk.length; if (size <= limit) chunks.push(chunk); });
    req.on('end', () => resolve(size <= limit ? Buffer.concat(chunks).toString('utf8') : null));
    req.on('error', reject);
  });
}

async function explain(req, res) {
  const started = Date.now();
  const noStore = {'Cache-Control': 'no-store'};
  if (!/^application\/json\b/i.test(req.headers['content-type'] || '')) return send(res, 415, {error: 'Send application/json.'}, undefined, noStore);
  const text = await readBody(req);
  if (text === null) return send(res, 413, {error: 'Request too large.'}, undefined, noStore);
  let ids = null;
  try {
    const body = JSON.parse(text);
    if (body && typeof body === 'object' && !Array.isArray(body) && Object.keys(body).join() === 'ids') ids = body.ids;
  } catch {}
  if (!Array.isArray(ids) || ids.length !== 2 || !ids.every(id => typeof id === 'string' && comparable.has(id)) || ids[0] === ids[1]) {
    return send(res, 400, {error: 'Choose two different runs from the 11 comparable records.'}, undefined, noStore);
  }
  const key = ids.join(',');
  const saved = (code, status, reason) =>
    send(res, code, {error: status, status, reason, ids, explanation: data.pairs[key].explanation ?? null}, undefined, noStore);
  const base = liveBase();
  if (!base) return saved(503, unavailable, 'off');
  if (!livePairs.has(key)) return saved(503, unavailable, 'pair');
  let health = null;
  try {
    const reply = await fetch(base + '/health', {headers: {Accept: 'application/json'}, signal: AbortSignal.timeout(live.checkMs)});
    if (reply.ok) health = await reply.json();
  } catch {}
  if (!health || health.ok !== true) return saved(503, unavailable, 'unreachable');
  if (Number.isFinite(health.usedThisHour) && Number.isFinite(health.capPerHour) && health.usedThisHour >= health.capPerHour) {
    return saved(429, limited, 'cap');
  }
  let answer;
  try {
    const reply = await fetch(base + '/explain', {method: 'POST', headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify({ids}), signal: AbortSignal.timeout(Math.min(live.waitMs, live.deadlineMs - (Date.now() - started)))});
    if (reply.status === 429 || reply.status === 503) return saved(429, limited, reply.status === 429 ? 'limit' : 'busy');
    if (!reply.ok) return saved(503, unavailable, 'upstream');
    const body = await reply.text();
    try { answer = body.length <= 65536 ? JSON.parse(body) : null; } catch { answer = null; }
  } catch (error) {
    return saved(503, unavailable, error?.name === 'TimeoutError' ? 'timeout' : 'network');
  }
  const checkedAnswer = bound(answer, ids, started);
  return checkedAnswer ? send(res, 200, checkedAnswer, undefined, noStore) : saved(503, unavailable, 'mismatch');
}

function send(res, status, body, type = 'application/json', headers = {}) {
  res.writeHead(status, {'Content-Type': type + '; charset=utf-8', 'X-Content-Type-Options': 'nosniff', ...headers});
  res.end(type === 'application/json' && typeof body !== 'string' ? JSON.stringify(body) : body);
}

function api(res, url) {
  const search = url.searchParams;
  const ids = (search.get('ids') || '').split(',');
  const pair = ids.length === 2 ? data.pairs[ids.join(',')] : null;
  switch (url.pathname) {
    // commit: the Git commit Vercel deployed (null when run anywhere else), so anyone can see which revision is live.
    case '/api/health': return send(res, 200, {ok: true, records: checked.size, commit: process.env.VERCEL_GIT_COMMIT_SHA || null});
    case '/api/questions': return send(res, 200, {questions: [cutoffQuestion]});
    case '/api/records': return send(res, 200, {records: data.records});
    case '/api/starters': return send(res, 200, {starters: data.starters});
    case '/api/summary': return send(res, 200, summary());
    case '/api/catalog': return send(res, 200, catalog(search));
    case '/api/ask': {
      const query = (search.get('q') || '').trim().slice(0, 300);
      return query ? send(res, 200, answer(query)) : send(res, 400, {error: 'Type a question first.'});
    }
    case '/api/record': {
      const record = checked.get(search.get('id'));
      return record ? send(res, 200, record) : send(res, 404, {error: 'Unknown record.'});
    }
    case '/api/evidence':
      return ids.length <= 2 && new Set(ids).size === ids.length && ids.every(id => checked.has(id))
        ? send(res, 200, {records: evidence(ids)}) : send(res, 400, {error: 'Choose one or two published records.'});
    case '/api/compare':
      if (!pair) return send(res, 400, {error: 'Choose two different runs from the 11 comparable records.'});
      return send(res, 200, {...pair, conditions: pair.conditions.map(run => run.map(condition =>
        condition.readings ? {...condition, value: condition.readings.map(reading => reading.value).join(' / ')} : condition)),
        ...(liveBase() && livePairs.has(ids.join(',')) ? {live: true} : {})});
    case '/api/export': {
      if (!pair) return send(res, 400, {error: 'Choose two different runs from the 11 comparable records.'});
      const format = search.get('format') === 'json' ? 'json' : 'csv';
      return send(res, 200, exportRows(pair, format), format === 'json' ? 'application/json' : 'text/csv',
        {'Content-Disposition': 'attachment; filename="flaregrain-compare.' + format + '"'});
    }
    case '/api/habitat': return send(res, 200, {...habitat, records: habitatRecords});
    case '/api/insights':
      return send(res, 404, {error: notIncluded});
    default:
      return send(res, 404, {error: 'Not found.'});
  }
}

export const server = createServer(async (req, res) => {
  if (req.method === 'POST' && /^\/api\/explain(?:\?|$)/.test(req.url)) return explain(req, res).catch(error => {
    console.error(error);
    if (!res.headersSent) send(res, 500, {error: 'Unable to load the submission.'});
  });
  if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, {error: 'Use GET or HEAD.'});
  try {
    const url = new URL(req.url, 'http://127.0.0.1');
    if (url.pathname.startsWith('/api/')) return api(res, url);
    if (url.pathname === '/dashboard/Foundry%20dashboard.html') return send(res, 200,
      '<!doctype html><html lang="en"><meta charset="utf-8"><title>Submission scope</title><link rel="stylesheet" href="/styles.css"><main class="page-main"><p>' + notIncluded + '</p><p><a href="/compare.html" target="_parent">Open Compare</a></p></main></html>', 'text/html');
    const filename = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
    if (!files.has(filename)) return send(res, 404, {error: 'Not found.'});
    const body = await readFile(new URL(filename, import.meta.url));
    return send(res, 200, body, types[filename.split('.').at(-1)]);
  } catch (error) {
    console.error(error);
    return send(res, 500, {error: 'Unable to load the submission.'});
  }
});

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  server.listen(Number(process.env.PORT ?? 8790), '127.0.0.1',
    () => console.log('Flaregrain ready at http://127.0.0.1:' + server.address().port + '/'));
}

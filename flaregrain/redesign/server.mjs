import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';

const data = JSON.parse(await readFile(new URL('../data/compare-data.json', import.meta.url), 'utf8'));
const starter = data.starters[0];
const orderedPair = data.pairs[starter.ids.join(',')];
const records = new Map(orderedPair.records.map(record => [record.id, record]));

const files = new Set([
  'index.html', 'answer.html', 'browse.html', 'compare.html', 'evidence.html', 'habitat.html',
  'insights.html', 'system.html', 'app.js', 'compare.js', 'drawer.js', 'pages.js', 'styles.css',
]);
const types = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css'};
const notIncluded = 'This view needs data outside the two-record submission.';
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
    limitation: findings.length ? scopeLimit + (pair.some(record => record.id === 'S1') ? saffireDuration : '') : 'The two records in this submission do not answer that question directly.',
    supportingSources: findings.map(finding => finding.source),
    ranks: (related ? pair : []).map(record => ({
      id: record.id, name: record.name, relevance: 'Checked record', source: record.source, comparable: true,
    })),
    compare: related && pair.length === 2 ? starter.ids : null,
    investigations: [], passages: [],
  };
}

function summary() {
  const countFields = tier => [...records.values()].flatMap(record =>
    record.fields.filter(field => field.tier === tier).map(field => ({record: record.name, field: field.field})));
  const describe = fields => ({
    values: fields.length, records: new Set(fields.map(field => field.record)).size,
    checkedRecords: records.size, example: fields[0] || null,
  });
  return {
    library: {investigations: new Set(data.records.map(record => record.study)).size, runs: records.size},
    moon: {runs: '—', investigations: []},
    gaps: describe(countFields('missing')), disputes: describe(countFields('dispute')),
  };
}

function catalog(search) {
  const query = (search.get('q') || '').trim().toLowerCase();
  const study = search.get('study');
  const rows = [...records.values()].filter(record =>
    (!study || record.study === study) && [record.name, record.study, ...record.events].join(' ').toLowerCase().includes(query));
  return {
    total: rows.length, page: 0, pageSize: records.size,
    records: rows.map(record => ({...record, observation: record.events.at(-1), origin: 'checked', comparable: true})),
    studies: [...records.values()].map(record => ({name: record.study})),
  };
}

function evidence(ids) {
  return ids.map(id => {
    const record = records.get(id);
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

function send(res, status, body, type = 'application/json', headers = {}) {
  res.writeHead(status, {'Content-Type': type + '; charset=utf-8', 'X-Content-Type-Options': 'nosniff', ...headers});
  res.end(type === 'application/json' && typeof body !== 'string' ? JSON.stringify(body) : body);
}

function api(res, url) {
  const search = url.searchParams;
  const ids = (search.get('ids') || '').split(',');
  const pair = ids.length === 2 ? data.pairs[ids.join(',')] : null;
  switch (url.pathname) {
    case '/api/health': return send(res, 200, {ok: true, records: records.size});
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
      const record = records.get(search.get('id'));
      return record ? send(res, 200, record) : send(res, 404, {error: 'Unknown record.'});
    }
    case '/api/evidence':
      return ids.length <= 2 && new Set(ids).size === ids.length && ids.every(id => records.has(id))
        ? send(res, 200, {records: evidence(ids)}) : send(res, 400, {error: 'Choose one or two published records.'});
    case '/api/compare':
      if (!pair) return send(res, 400, {error: 'Choose the two different published records.'});
      return send(res, 200, {...pair, conditions: pair.conditions.map(run => run.map(condition =>
        condition.readings ? {...condition, value: condition.readings.map(reading => reading.value).join(' / ')} : condition))});
    case '/api/export': {
      if (!pair) return send(res, 400, {error: 'Choose the two different published records.'});
      const format = search.get('format') === 'json' ? 'json' : 'csv';
      return send(res, 200, exportRows(pair, format), format === 'json' ? 'application/json' : 'text/csv',
        {'Content-Disposition': 'attachment; filename="flaregrain-compare.' + format + '"'});
    }
    case '/api/habitat':
    case '/api/insights':
      return send(res, 404, {error: notIncluded});
    default:
      return send(res, 404, {error: 'Not found.'});
  }
}

export const server = createServer(async (req, res) => {
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

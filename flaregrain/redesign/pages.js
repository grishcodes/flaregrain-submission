/* Secondary destinations: Browse, Evidence, Habitat, What the data says, System design. Data comes from the prototype API. */
(function () {
  const D = window.FlaregrainDrawer;
  const esc = D.esc, mk = D.mk;
  const $ = id => document.getElementById(id);
  const page = document.body.dataset.page;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const OUT = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M2 8 8 2M3.5 2H8v4.5"/></svg>';
  const ARROW = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 5h8M5.5 1.5 9 5 5.5 8.5"/></svg>';
  const plural = (n, one, many) => n.toLocaleString('en-CA') + ' ' + (n === 1 ? one : many);
  const store = {get: k => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} }};

  const api = path => fetch(path, {headers: {Accept: 'application/json'}}).then(async r => {
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || 'Request failed'), {status: r.status});
    return body;
  });
  function offline(el) {
    el.innerHTML = `<div class="cmp-offline"><h2>Start the prototype server</h2><p>This page reads the dashboard’s own data through the small local server:</p>
      <pre>cd server && node server.mjs</pre><p>Then open <a href="http://127.0.0.1:8790/${esc(location.pathname.split('/').pop())}">http://127.0.0.1:8790/${esc(location.pathname.split('/').pop())}</a>.</p></div>`;
  }
  const served = location.protocol !== 'file:';
  const retry = (status, message, again) => {
    status.innerHTML = `${esc(message)} <button type="button" class="retry">Retry</button>`;
    status.querySelector('.retry').addEventListener('click', again);
  };
  // This submission carries the 13 hand-checked records. Views that need the full dataset say so plainly, instead of an error with Retry.
  const SCOPE = `<p><b>Part of the full-data demo.</b> This view reads Flaregrain’s full NASA PSI dataset (24 investigations, 2,009 table rows), which the team shows live. This public site carries 13 hand-checked NASA records (11 comparable runs), with links to the original reports.</p>
    <p class="scope-links"><a class="btn btn-line" href="compare.html?ids=B1,S1">Compare B1 and Saffire I-1</a> <a class="btn btn-line" href="evidence.html">Open the evidence</a></p>`;
  const scope = (el, hide = []) => {
    hide.forEach(x => { if (x) { x.hidden = true; x.textContent = ''; } });
    el.className = 'scope-note';
    el.innerHTML = SCOPE;
  };

  // Tabs with arrow-key movement (role=tablist).
  function tabs(list, onSelect) {
    const all = [...list.querySelectorAll('[role=tab]')];
    const select = (tab, focus) => {
      all.forEach(t => { const on = t === tab; t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1; });
      if (focus) tab.focus();
      onSelect(tab);
    };
    all.forEach((t, i) => {
      t.addEventListener('click', () => select(t));
      t.addEventListener('keydown', e => {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        select(all[(i + (e.key === 'ArrowRight' ? 1 : all.length - 1)) % all.length], true);
      });
    });
    return select;
  }

  // The dashboard's own view, embedded unchanged and opened on the right destination by its own controls.
  function embed(el) {
    if (el.dataset.loaded) return;
    el.dataset.loaded = '1';
    if (!served) return offline(el);
    const frame = document.createElement('iframe');
    frame.title = el.dataset.embedView === 'map' ? 'Atlas map from the current dashboard' : 'System design from the current dashboard';
    frame.src = '/dashboard/Foundry%20dashboard.html';
    frame.loading = 'lazy';
    frame.addEventListener('load', () => {
      const doc = frame.contentDocument;
      const click = sel => doc?.querySelector(sel)?.click();
      if (el.dataset.embedView === 'system') click('[data-view="system"]');
      else { click('[data-view="explore"]'); setTimeout(() => click('[data-explore-pane="map"]'), 150); }
    });
    el.appendChild(frame);
  }

  document.addEventListener('click', async e => {
    const opener = e.target.closest('[data-open]');
    if (opener) {
      store.set('fg-last-record', opener.dataset.open);
      try { await D.open(opener.dataset.open, {opener}); } catch (err) { opener.insertAdjacentHTML('afterend', `<span class="small" role="status">${esc(err.message)}</span>`); }
    }
  });

  /* ---------- Browse: Catalog list + Atlas map ---------- */
  if (page === 'browse') {
    const list = $('cat-list'), status = $('cat-status'), q = $('cat-q'), study = $('cat-study'), pager = $('cat-pager');
    let pageNo = 0, timer = 0, ticket = 0;
    const load = async () => {
      if (!served) return offline(list);
      const mine = ++ticket;
      status.textContent = 'Loading records…';
      try {
        const data = await api(`/api/catalog?q=${encodeURIComponent(q.value.trim())}&study=${encodeURIComponent(study.value)}&page=${pageNo}`);
        if (mine !== ticket) return;
        if (study.options.length === 1) study.insertAdjacentHTML('beforeend', data.studies.map(s => `<option value="${esc(s.name)}">${esc(s.name)}${s.psi ? ' · ' + esc(s.psi) : ''}</option>`).join(''));
        const from = data.page * data.pageSize + 1, to = Math.min(data.total, from + data.records.length - 1);
        status.textContent = data.total ? `${plural(data.total, 'record', 'records')}${data.total > data.pageSize ? ` · showing ${from}–${to}` : ''}` : 'No records match. Try fewer words or another investigation.';
        list.innerHTML = data.records.map(r => `<li class="cat-row">
          <div class="cat-main">${mk(r.origin === 'checked' ? 'checked' : 'psi')}<b>${esc(r.name)}</b><span class="mono">${r.origin === 'checked' ? 'Checked NASA record' : 'PSI table row'}</span></div>
          <p>${esc([r.conditions, r.observation].filter(Boolean).join(' · '))}</p>
          <div class="acts"><button class="btn btn-line" type="button" data-open="${esc(r.id)}">Open full record ${ARROW}</button>
          ${r.comparable ? `<a class="btn btn-line" href="compare.html?a=${encodeURIComponent(r.id)}">Compare with… ${ARROW}</a>` : ''}</div></li>`).join('');
        const pages = Math.ceil(data.total / data.pageSize);
        pager.innerHTML = pages > 1 ? `<button class="btn btn-line" type="button" data-pg="-1"${data.page === 0 ? ' disabled' : ''}>Previous</button><span class="mono">Page ${data.page + 1} of ${pages}</span><button class="btn btn-line" type="button" data-pg="1"${data.page + 1 >= pages ? ' disabled' : ''}>Next</button>` : '';
      } catch (err) { if (mine === ticket) retry(status, err.status ? err.message : 'The catalog is unavailable right now.', load); }
    };
    q.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { pageNo = 0; load(); }, 250); });
    study.addEventListener('change', () => { pageNo = 0; load(); });
    $('cat-form').addEventListener('submit', e => { e.preventDefault(); pageNo = 0; load(); });
    pager.addEventListener('click', e => { const b = e.target.closest('[data-pg]'); if (b) { pageNo += Number(b.dataset.pg); load(); list.scrollIntoView({behavior: reduced ? 'auto' : 'smooth'}); } });
    const sel = tabs(document.querySelector('.tabs-bar'), tab => {
      const atlas = tab.id === 'tab-atlas';
      $('panel-catalog').hidden = atlas; $('panel-atlas').hidden = !atlas;
      if (atlas) embed($('atlas-embed'));
      history.replaceState(null, '', atlas ? '#atlas' : location.pathname);
    });
    if (location.hash === '#atlas') sel($('tab-atlas'));
    load();
  }

  /* ---------- Evidence: one or two records side by side ---------- */
  if (page === 'evidence') {
    const cols = $('ev-cols'), status = $('ev-status'), a = $('ev-a'), b = $('ev-b');
    const fieldRow = (f, r) => `<div class="${f.tier === 'missing' ? 'miss' : ''}">${mk(f.tier)}<dt>${esc(f.field)}</dt><dd>${esc(f.value)}${f.status ? `<small>${esc(f.status)}</small>` : ''}${f.url && f.url !== r.source.url ? ` <a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.source)}</a>` : ''}</dd></div>`;
    const column = r => `<article class="ev-col">
      <p class="mono">${esc([r.investigation, r.sample].filter(Boolean).join(' · '))}</p>
      <h2>${esc(r.name)}</h2>
      ${r.sources.map(s => `<figure class="excerpt">${s.excerpt ? `<a href="${esc(s.url)}" target="_blank" rel="noopener"><img src="${esc(s.excerpt.src)}" alt="${esc(s.excerpt.alt)}"${s.excerpt.width ? ` width="${s.excerpt.width}" height="${s.excerpt.height}"` : ''}></a>` : ''}
        <figcaption><a class="cite-link" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)} ${OUT}</a>${s.excerpt ? '' : ' <span class="mono">· no page crop yet</span>'}</figcaption></figure>`).join('')}
      ${r.fields.some(f => f.tier === 'dispute') ? `<div class="sec"><span class="mono">Needs a second reading</span>${r.fields.filter(f => f.tier === 'dispute').map(f => `<div class="dispute-box"><div class="t">${mk('dispute')}${esc(f.field)} · sources disagree</div><p>${esc(f.value)}</p></div>`).join('')}</div>` : ''}
      <div class="sec"><span class="mono">Every field</span><dl class="fields">${r.fields.filter(f => f.tier !== 'dispute').map(f => fieldRow(f, r)).join('')}</dl></div>
    </article>`;
    async function show(ids) {
      status.textContent = 'Loading sources…';
      try {
        const {records} = await api('/api/evidence?ids=' + ids.map(encodeURIComponent).join(','));
        cols.innerHTML = records.map(column).join('');
        cols.classList.toggle('one', records.length === 1);
        status.textContent = records.length === 2 ? `${records[0].name} and ${records[1].name}, side by side.` : `${records[0].name}.`;
        history.replaceState(null, '', '?ids=' + ids.map(encodeURIComponent).join(','));
        if (ids.length === 2) store.set('fg-last-pair', ids.join(','));
      } catch (err) { retry(status, err.status ? err.message : 'The sources are unavailable right now.', () => show(ids)); }
    }
    (async () => {
      if (!served) return offline(cols);
      let records;
      try { ({records} = await api('/api/records')); } catch { return offline(cols); }
      const opts = sel => records.map(r => `<option value="${esc(r.id)}"${r.id === sel ? ' selected' : ''}>${esc(r.name)}</option>`).join('');
      // From the nav: your last pair or record; otherwise the cutoff pair.
      const asked = (new URLSearchParams(location.search).get('ids') || store.get('fg-last-pair') || store.get('fg-last-record') || 'B1,S1').split(',').filter(Boolean).slice(0, 2);
      a.innerHTML = opts(asked[0]); b.innerHTML = '<option value="">None (one record)</option>' + opts(asked[1]);
      if (!records.some(r => r.id === asked[0])) a.insertAdjacentHTML('afterbegin', `<option value="${esc(asked[0])}" selected>${esc(asked[0])}</option>`);
      const go = () => { if (a.value === b.value) { status.textContent = 'Choose two different records, or none for B.'; return; } show([a.value, b.value].filter(Boolean)); };
      a.addEventListener('change', go); b.addEventListener('change', go);
      show(asked);
    })();
  }

  /* ---------- Habitat ---------- */
  if (page === 'habitat') {
    const o2 = $('hab-o2'), psi = $('hab-psi'), g = $('hab-g'), status = $('hab-status'), chart = $('hab-chart'), read = $('hab-read'), presets = $('hab-presets');
    let timer = 0, ticket = 0, presetList = [];
    const outs = () => { $('hab-o2-out').textContent = Number(o2.value).toFixed(1) + '%'; $('hab-psi-out').textContent = Number(psi.value).toFixed(1) + ' psi'; };
    function draw(d) {
      const W = 640, H = 400, L = 52, R = 14, T = 14, B = 70, maxO2 = 50, maxPsi = 30;
      const X = v => L + Math.min(v, maxO2) / maxO2 * (W - L - R), Y = v => T + (1 - Math.min(v, maxPsi) / maxPsi) * (H - T - B), strip = H - 26;
      const dots = d.points.map(([x, y]) => `<circle class="hp${Math.abs(x - d.chosen.o2) <= 3 && Math.abs(y - d.chosen.psi) <= 1.5 ? ' near' : ''}" cx="${X(x).toFixed(1)}" cy="${Y(y).toFixed(1)}" r="2.3"/>`).join('');
      const ox = d.oxygenOnly.map(x => `<rect class="hs" x="${(X(x) - .8).toFixed(1)}" y="${strip}" width="1.6" height="9"/>`).join('');
      const ticksX = [10, 20, 30, 40, 50].map(v => `<text x="${X(v)}" y="${strip - 10}" text-anchor="middle">${v}%</text>`).join('');
      const ticksY = [0, 10, 20, 30].map(v => `<text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${v}</text><line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="grid"/>`).join('');
      chart.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`NASA PSI rows by oxygen and pressure. ${d.points.length} rows with a pressure, ${d.oxygenOnly.length} with oxygen only. ${d.nearCount} near your choice.`)}">
        ${ticksY}<rect class="moon" x="${X(30)}" y="${Y(10.2)}" width="${X(50) - X(30)}" height="${Y(0) - Y(10.2)}"/>
        <text class="moon-l" x="${X(30) + 6}" y="${Y(10.2) - 6}">Moon base: ≥30% O₂, ≤10.2 psi</text>
        ${dots}${ox}${ticksX}
        <circle class="you" cx="${X(d.chosen.o2)}" cy="${Y(d.chosen.psi)}" r="10"/>
        <text x="${(L + W - R) / 2}" y="${H - 2}" text-anchor="middle">Oxygen</text><text x="14" y="${(T + H - B) / 2}" transform="rotate(-90 14 ${(T + H - B) / 2})" text-anchor="middle">Pressure (psi)</text>
        <text x="${L}" y="${strip + 22}" class="small">Oxygen-only rows (no pressure in the PSI table)</text></svg>
        <figcaption class="mono">Each dot is a NASA PSI table row · bright: within 3 points of oxygen and 1.5 psi of your choice · ring: your choice</figcaption>`;
      const flags = d.flags.map(f => `<li class="flag-${esc(f.kind)}">${esc(f.text)}</li>`).join('');
      read.innerHTML = `
        <p class="hab-big"><b>${plural(d.nearCount, 'row', 'rows')}</b> tested near ${d.chosen.o2}% oxygen and ${d.chosen.psi} psi${d.nearStudies.length ? `, from ${esc(d.nearStudies.join(', '))}` : ''}.</p>
        <p class="mono">Oxygen partial pressure ${d.chosen.partialPressure} psi · Earth air 3.09 psi</p>
        ${flags ? `<ul class="hab-flags" aria-label="Limits at this condition">${flags}</ul>` : ''}
        <section class="hab-fan"><h2>Fan off at this oxygen?</h2>
          <p>${mk('t3')}<span class="mono">Flaregrain reading</span> ${esc(d.fanOff.answer)}</p>
          <ul>${d.fanOff.evidence.map(e => `<li>${mk(e.tier === 'context' ? 'context' : 'checked')} ${esc(e.text)}${e.url ? ` <a class="cite-link" href="${esc(e.url)}" target="_blank" rel="noopener">NASA source ${OUT}</a>` : ''}</li>`).join('')}</ul></section>
        ${d.near.length ? `<details class="related"><summary class="mono">${plural(d.near.length, 'nearby row', 'nearby rows')}</summary><table class="near"><thead><tr><th scope="col">Investigation</th><th scope="col">Row</th><th scope="col">O₂</th><th scope="col">psi</th><th scope="col">Fuel</th></tr></thead><tbody>${d.near.map(r => `<tr><td>${esc(r.study)}</td><td>${esc(r.label)}</td><td>${r.o2}%</td><td>${r.psi}</td><td>${esc(r.fuel)}</td></tr>`).join('')}</tbody></table></details>` : ''}`;
    }
    async function load() {
      const mine = ++ticket;
      outs();
      presets.querySelectorAll('button').forEach(btn => btn.setAttribute('aria-pressed', presetList[btn.dataset.i] && presetList[btn.dataset.i].o2 == o2.value && presetList[btn.dataset.i].psi == psi.value && presetList[btn.dataset.i].gravity === g.value));
      try {
        const d = await api(`/api/habitat?o2=${o2.value}&psi=${psi.value}&gravity=${g.value}`);
        if (mine !== ticket) return;
        if (!presetList.length) {
          presetList = d.presets;
          presets.innerHTML = presetList.map((p, i) => `<button type="button" data-i="${i}" title="${esc(p.note)}">${esc(p.label)}</button>`).join('');
          load(); return;
        }
        draw(d);
        status.textContent = `${d.nearCount} rows near ${d.chosen.o2}% oxygen and ${d.chosen.psi} psi.`;
      } catch (err) {
        if (mine !== ticket) return;
        if (err.status === 404) return scope(document.querySelector('.hab-layout'), [presets, $('hab-form'), status]);
        retry(status, err.status ? err.message : 'Habitat data is unavailable right now.', load);
      }
    }
    const later = () => { outs(); clearTimeout(timer); timer = setTimeout(load, 120); };
    o2.addEventListener('input', later); psi.addEventListener('input', later); g.addEventListener('change', load);
    presets.addEventListener('click', e => { const btn = e.target.closest('[data-i]'); if (!btn) return; const p = presetList[btn.dataset.i]; o2.value = p.o2; psi.value = p.psi; g.value = p.gravity; load(); });
    o2.value = 30; psi.value = 10.2; g.value = 'moon';
    if (!served) offline(read); else load();
  }

  /* ---------- What the data says ---------- */
  if (page === 'insights') {
    const panel = $('panel-in'), status = $('in-status');
    let data = null;
    const trendSvg = (fit, model) => {
      const W = 420, H = 230, L = 40, R = 10, T = 10, B = 34;
      const xs = [...fit.points.map(p => p[0]), ...fit.curve.map(c => c[0])], ys = [...fit.points.map(p => p[1]), ...fit.curve.map(c => c[3])];
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.ceil(Math.max(...ys));
      const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - v / y1) * (H - T - B);
      const band = fit.curve.map(c => `${X(c[0]).toFixed(1)},${Y(c[3]).toFixed(1)}`).join(' ') + ' ' + fit.curve.slice().reverse().map(c => `${X(c[0]).toFixed(1)},${Y(c[2]).toFixed(1)}`).join(' ');
      return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(`${model.title}, ${fit.fuel}: ${fit.n} PSI rows and the Flaregrain fit`)}">
        <polygon class="band" points="${band}"/><polyline class="fit" points="${fit.curve.map(c => `${X(c[0]).toFixed(1)},${Y(c[1]).toFixed(1)}`).join(' ')}"/>
        ${fit.points.map(p => `<circle class="${p[2] ? 'faint' : 'pt'}" cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="2.6"/>`).join('')}
        <text x="${L}" y="${H - 6}">${Math.round(x0 * 100)}% O₂</text><text x="${W - R}" y="${H - 6}" text-anchor="end">${Math.round(x1 * 100)}% O₂</text>
        <text x="${L - 6}" y="${T + 8}" text-anchor="end">${y1}</text><text x="${L - 6}" y="${H - B}" text-anchor="end">0</text></svg>`;
    };
    const panes = {
      needs: d => d.needs.map(n => `<article class="in-card"><h2>${esc(n.label)}</h2>
        <p>${mk('context')}<span class="mono">NASA</span> ${esc(n.nasa)}</p>
        ${n.gap ? `<p class="limit"><span class="mono">Gap</span>${esc(n.gap)}</p>` : ''}
        <details class="related"><summary class="mono">${plural(n.investigations.length, 'investigation', 'investigations')}</summary><ul class="inv">${n.investigations.map(v => `<li><b>${esc(v.name)}</b> <span class="mono">${esc(v.psi)}</span>${v.lines.filter(l => l[1]).map(l => `<span>${esc(l[0])}: ${esc(l[1])}</span>`).join('')}</li>`).join('')}</ul></details></article>`).join(''),
      equipment: d => d.equipment.map(c => `<article class="in-card"><p class="mono">${esc(c.area)}</p><h2>${esc(c.title)}</h2>
        <ul class="in-ev">${c.evidence.map(e => `<li>${mk(e.tier === 'checked' ? 'checked' : e.tier === 'psi' ? 'psi' : e.tier === 'reading' ? 't3' : 'context')}${esc(e.text)}${e.source ? ` <a class="cite-link" href="${esc(e.source.url)}" target="_blank" rel="noopener">${esc(e.source.label)} ${OUT}</a>` : ''}</li>`).join('')}</ul>
        <p class="in-impl">${mk('t3')}<span class="mono">Flaregrain reading · implication</span> ${esc(c.implication)}</p>
        <p class="limit"><span class="mono">Not yet tested</span>${esc(c.untested)}</p>
        <p class="mono in-rel">${c.related.map(r => esc(r.name)).join(' · ')}</p></article>`).join(''),
      trends: d => d.trends.map(m => `<article class="in-card wide"><p class="mono">${mk('t3')}Flaregrain model · not NASA evidence · ${esc(m.psi)}</p><h2>${esc(m.title)}</h2>
        <p>${esc(m.method)}</p>
        ${m.fits.length ? `<div class="trend-grid">${m.fits.map(f => `<figure>${trendSvg(f, m)}<figcaption class="mono">${esc(f.fuel)} · ${f.n} PSI rows · r² ${f.r2}${f.effect != null ? ` · ${f.effect}% per 0.01 O₂` : ''}</figcaption></figure>`).join('')}</div>`
          : `<p class="mono">${m.stats.n} rows · ${m.stats.ignited} ignited · ${m.stats.moonRows} Moon-base rows · cross-validated accuracy ${(m.stats.accuracy * 100).toFixed(0)}% (base rate ${(m.stats.baseRate * 100).toFixed(0)}%)</p>`}
        <p class="limit"><span class="mono">Label</span>${esc(m.label)}</p></article>`).join(''),
      issues: d => `<p class="in-total"><b>${plural(d.issues.flagged, 'flagged table value', 'flagged table values')}</b> and ${plural(d.issues.recordIssues, 'record issue', 'record issues')} across ${plural(d.issues.investigations.length, 'investigation', 'investigations')}. NASA’s printed value always stays visible; our reading sits beside it.</p>` +
        d.issues.investigations.map(i => `<article class="in-card"><h2>${esc(i.name)} <a class="cite-link" href="${esc(i.page)}" target="_blank" rel="noopener">${esc(i.psi)} on NASA PSI ${OUT}</a></h2>
        ${i.record.length ? `<ul class="in-ev">${i.record.map(t => `<li>${mk('context')}${esc(t)}</li>`).join('')}</ul>` : ''}
        ${i.groups.length ? `<ul class="in-ev">${i.groups.map(gr => `<li>${mk('flag')}<b>${esc(gr.kind)}</b> · <span class="mono">${esc(gr.column)}</span> · ${gr.count}<span class="small">${gr.examples.map(esc).join(' ')}</span></li>`).join('')}</ul>` : ''}</article>`).join(''),
    };
    const show = pane => {
      panel.setAttribute('aria-labelledby', 'tab-' + pane);
      panel.innerHTML = `<div class="in-grid">${panes[pane](data)}</div>`;
      history.replaceState(null, '', '#' + pane);
    };
    const sel = tabs(document.querySelector('.tabs-bar'), tab => data && show(tab.dataset.pane));
    (async () => {
      if (!served) return offline(panel);
      status.textContent = 'Loading…';
      try { data = await api('/api/insights'); status.textContent = ''; }
      catch (err) {
        if (err.status === 404) return scope(panel, [document.querySelector('.tabs-bar'), status]);
        return retry(status, 'This section is unavailable right now.', () => location.reload());
      }
      const start = document.querySelector(`[data-pane="${location.hash.slice(1)}"]`) || $('tab-needs');
      sel(start);
    })();
  }

  /* ---------- System design ---------- */
  if (page === 'system') scope($('system-embed'));
})();

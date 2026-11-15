/* Compare page. Everything shown comes from the prototype API (server/server.mjs), which runs the dashboard's own comparison logic. */
(function () {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const OUT = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M2 8 8 2M3.5 2H8v4.5"/></svg>';
  const ARROW = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 5h8M5.5 1.5 9 5 5.5 8.5"/></svg>';
  const CHEV = '<svg viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 1l4 4 4-4"/></svg>';
  const X = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12"/></svg>';
  const TIER = {checked: ['t1', 'Checked NASA record'], psi: ['t2', 'PSI table row'], context: ['t4', 'Context, not evidence'],
    dispute: ['dispute', 'Sources disagree'], flag: ['flag', 'NASA printed it, we read it differently'], missing: ['missing', 'Not in the source'], unrated: ['unrated', 'From the cited record, no field-level status']};
  const status = $('cmp-status'), result = $('cmp-result'), pickA = $('pick-a'), pickB = $('pick-b');
  let records = [], current = null, latest = 0, last = {a: '', b: ''};
  // Opened from a cited answer: the question rides along in the address so Compare can lead back to it.
  const fromQuestion = (new URLSearchParams(location.search).get('q') || '').trim().slice(0, 300);

  const api = path => fetch(path, {headers: {Accept: 'application/json'}}).then(async r => {
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || 'Request failed'), {status: r.status});
    return body;
  });

  function offline() {
    status.textContent = '';
    result.hidden = false;
    result.innerHTML = `<div class="cmp-offline"><h2 id="cmp-title">Start the prototype server to compare</h2>
      <p>Compare runs the dashboard’s own comparison logic, so it needs the small local server. From this folder:</p>
      <pre>cd server && node server.mjs</pre><p>Then open <a href="http://127.0.0.1:8790/compare.html">http://127.0.0.1:8790/compare.html</a>.</p></div>`;
  }

  /* ---------- Pickers ---------- */
  function fillPickers(a, b) {
    const groups = [...new Set(records.map(r => r.study))];
    const options = sel => `<option value="" disabled${sel ? '' : ' selected'}>Choose a record</option>` + groups.map(g => `<optgroup label="${esc(g)}">` + records.filter(r => r.study === g)
      .map(r => `<option value="${esc(r.id)}"${r.id === sel ? ' selected' : ''}>${esc(r.name)}</option>`).join('') + '</optgroup>').join('');
    pickA.innerHTML = options(a); pickB.innerHTML = options(b);
    pickA.disabled = pickB.disabled = false;
  }
  // Focus moves to the result after a deliberate action (starter, suggestion, swap). After a picker change the
  // result is announced instead, so keyboard users changing a select aren't pulled away from it.
  function choose(a, b, focus) {
    if (!a || !b) { pickA.value = a || ''; pickB.value = b || ''; status.textContent = 'Choose a second record to compare.'; return; }
    if (a === b) {
      pickA.value = last.a; pickB.value = last.b;
      status.textContent = 'Choose two different records. Keeping ' + (current ? current.label : 'the previous choice') + '.';
      return;
    }
    pickA.value = a; pickB.value = b; last = {a, b};
    history.replaceState(null, '', '?ids=' + encodeURIComponent(a) + ',' + encodeURIComponent(b) + (fromQuestion ? '&q=' + encodeURIComponent(fromQuestion) : ''));
    load(a, b, focus);
  }
  pickA.addEventListener('change', () => choose(pickA.value, pickB.value));
  pickB.addEventListener('change', () => choose(pickA.value, pickB.value));
  $('swap').addEventListener('click', () => { if (pickA.value && pickB.value) choose(pickB.value, pickA.value, true); });

  /* ---------- Start state: no pair chosen ---------- */
  async function starters() {
    let list = [];
    try { ({starters: list} = await api('/api/starters')); } catch { return offline(); }
    status.textContent = 'Choose two records, or start with a prepared pair.';
    result.hidden = false;
    result.classList.remove('play'); result.classList.add('static');
    result.innerHTML = `<h2 id="cmp-title" class="starter-title" tabindex="-1">Start with a prepared pair</h2>
      <div class="starters">${list.map(st => `<button type="button" class="starter" data-pair="${esc(st.ids.join(','))}">
        <span class="mono">${esc(st.label)}</span><b>${esc(st.names[0])} <em>and</em> ${esc(st.names[1])}</b><span>${esc(st.note)}</span>${ARROW}</button>`).join('')}</div>`;
  }

  /* ---------- Result: three layers ---------- */
  const mk = t => `<span class="mk ${TIER[t]?.[0] || 'unrated'}" aria-hidden="true"></span>`;
  function render(c) {
    const [A, B] = c.records;
    // A page shared by both records drops the record-specific part of its label and names the records instead.
    const srcLabel = s => s.records.length > 1
      ? s.label.split(' · ').filter(seg => !/sample|\btests?\b|^(B|S|M)\d|FLEX|GMT|^[IV]+-\d/i.test(seg)).join(' · ')
      : s.label;
    const srcChip = s => `<a class="src-pill" href="${esc(s.url)}" target="_blank" rel="noopener">${mk('checked')}<b>${esc(s.records.join(', '))}</b><span>${esc(srcLabel(s))}</span>${OUT}</a>`;
    const N = c.supportingSources.length;
    const cell = (text, flag) => `<span${flag ? ` class="flag-${flag}"` : ''}>${flag ? mk(flag) + `<span class="vh">${flag === 'dispute' ? 'Sources disagree: ' : 'Not in source: '}</span>` : ''}${esc(text)}</span>`;
    const rows = c.rows.map(([label, a, b], i) => `<div class="row line-in" style="--d:${8 + i}"><span class="mono">${esc(label)}</span>${cell(a, c.rowFlags[i][0])}${cell(b, c.rowFlags[i][1])}</div>`).join('');
    const strip = c.conditions.map((list, i) => `<div class="strip-run"><span class="mono">${esc(c.records[i].name)}</span><dl>${list.map(x =>
      `<div class="${x.tier === 'missing' ? 'miss' : ''}"><dt>${esc(x.label)}</dt><dd>${mk(x.tier)}<span>${esc(x.value)}</span></dd></div>`).join('')}</dl></div>`).join('');
    const issues = [c.issues.disputed && `${c.issues.disputed} ${c.issues.disputed === 1 ? 'value needs' : 'values need'} a second reading`,
      c.issues.missing && `${c.issues.missing} not in source`].filter(Boolean).join(' · ');
    const n = c.explanation?.sentences.length || 0;
    const plural = (k, one, many) => k + ' ' + (k === 1 ? one : many);
    const liveBtn = label => c.live ? `<button class="btn btn-line" type="button" id="live">${label}</button><p class="small" id="live-status" role="status"></p>` : '';
    const expl = c.explanation ? `
      <details class="why line-in" style="--d:5">
        <summary><b>Why they differ</b><small>Flaregrain reading · ${plural(n, 'checked sentence', 'checked sentences')}</small><i aria-hidden="true">${CHEV}</i></summary>
        <div class="reading-block">
          <span class="mono">Flaregrain reading · not NASA evidence</span>
          <p class="small">Written by ${esc(c.explanation.model)}. Each sentence was kept only because it matched the record fields it cites${c.explanation.removed ? `; ${plural(c.explanation.removed, 'sentence was', 'sentences were')} removed` : ''}.</p>
          <ol>${c.explanation.sentences.map(s => `<li><p>${esc(s.text)}</p><span class="cites">${s.cites.map(ci => `<button type="button" class="cite" data-open="${esc(ci.record === A.name ? A.id : B.id)}" data-field="${esc(ci.field)}" title="${esc(ci.value)}">${esc(ci.record.replace(/^BASS-II |^Saffire /, ''))} · ${esc(ci.field)}</button>`).join('')}</span></li>`).join('')}</ol>
          ${liveBtn('Ask the live model again')}
        </div>
      </details>` : `<p class="why-none line-in" style="--d:5">No checked explanation for this pair yet.${c.live ? '' : ' The live model isn’t connected to this prototype.'}${c.candidates.length ? ' Try a suggested pair below.' : ''}</p>${c.live ? '<div class="reading-block">' + liveBtn('Ask the live model') + '</div>' : ''}`;
    const cands = c.candidates.length ? `<div class="cands"><span class="mono">Also worth comparing with ${esc(A.id)}</span>${c.candidates.map(k =>
      `<button type="button" class="cand" data-cand="${esc(k.id)}"><b>${esc(k.name)}</b><span>${esc(k.reason)}</span>${ARROW}</button>`).join('')}</div>` : '';

    result.innerHTML = `
      ${fromQuestion ? `<p class="back-q line-in" style="--d:0"><a class="full" href="answer.html?q=${encodeURIComponent(fromQuestion)}">← Back to your question</a></p>` : ''}
      <p class="mono line-in" style="--d:0">${c.prepared ? 'Prepared comparison' : 'Comparison'} · ${esc(A.investigation)} and ${esc(B.investigation)}</p>
      <h2 id="cmp-title" class="line-in" style="--d:1" tabindex="-1">${esc(A.name)} <em>and</em> ${esc(B.name)}</h2>
      <dl class="verdict">
        <div class="line-in" style="--d:2"><dt class="mono">Shared</dt><dd>${esc(c.summary.shared)}</dd></div>
        <div class="line-in" style="--d:3"><dt class="mono">Different</dt><dd>${esc(c.summary.differences)}</dd></div>
        <div class="line-in gap" style="--d:4"><dt class="mono">${mk('missing')}Not settled</dt><dd>${esc(c.summary.gap)}</dd></div>
      </dl>
      <div class="strip line-in" style="--d:5" aria-label="Test conditions">${strip}</div>
      ${issues ? `<p class="issues line-in" style="--d:6">${mk(c.issues.disputed ? 'dispute' : 'missing')}<span>${esc(issues)}</span><button type="button" class="full" data-open="${esc(c.issues.disputed ? (A.fields.some(f => f.tier === 'dispute') ? A.id : B.id) : A.id)}">Review in full record ${ARROW}</button></p>` : ''}
      <div class="support line-in" style="--d:7">
        <p class="support-n">${mk('checked')}Supported by ${N} cited NASA ${N === 1 ? 'source' : 'sources'}</p>
        <div class="srcs">${c.supportingSources.map(srcChip).join('')}</div>
        <p class="limit"><span class="mono">Limitation</span>${esc(c.limitations[0])}</p>
      </div>
      ${expl}

      <section class="layer2" aria-label="Side by side and supporting detail">
        <div class="table" role="table" aria-label="Side by side">
          <div class="row head" role="row"><span></span>
            <span>${esc(A.name)}<button type="button" class="full" data-open="${esc(A.id)}">Full record ${ARROW}</button></span>
            <span>${esc(B.name)}<button type="button" class="full" data-open="${esc(B.id)}">Full record ${ARROW}</button></span></div>
          ${rows}
        </div>
        ${cands}
        <div class="exports"><a class="btn btn-ink" href="evidence.html?ids=${encodeURIComponent(A.id)},${encodeURIComponent(B.id)}">See both sources side by side ${ARROW}</a></div>
        <div class="exports"><span class="mono">Export both records</span>
          <a class="btn btn-line" href="/api/export?ids=${esc(A.id)},${esc(B.id)}&format=csv" download>CSV</a>
          <a class="btn btn-line" href="/api/export?ids=${esc(A.id)},${esc(B.id)}&format=json" download>JSON</a></div>
      </section>`;
    result.hidden = false;
    result.classList.remove('play', 'static'); void result.offsetWidth;
    result.classList.add(reduced ? 'static' : 'play');
    clearTimeout(render.settle);
    render.settle = setTimeout(() => result.classList.replace('play', 'static'), 2000);
  }

  async function load(a, b, focus) {
    status.textContent = 'Comparing…';
    const ticket = ++latest;
    try {
      const data = await api(`/api/compare?ids=${encodeURIComponent(a)},${encodeURIComponent(b)}`);
      if (ticket !== latest) return;
      current = data;
      try { localStorage.setItem('fg-last-pair', data.ids.join(',')); } catch {}
      render(current);
      status.textContent = `Comparing ${current.records[0].name} and ${current.records[1].name}.`;
      // Decision 10: focus goes to the result heading, not the section around it.
      if (focus) $('cmp-title').focus({preventScroll: true});
    } catch (e) {
      if (ticket !== latest) return;
      if (!e.status && !current) return offline();
      status.innerHTML = `${esc(e.status ? e.message : 'The comparison data is unavailable right now.')} <button type="button" class="retry" id="retry">Retry</button>`;
      $('retry').addEventListener('click', () => load(a, b, focus));
    }
  }

  result.addEventListener('click', async e => {
    const cand = e.target.closest('[data-cand]');
    if (cand) return choose(pickA.value, cand.dataset.cand, true);
    const starter = e.target.closest('[data-pair]');
    if (starter) { const [a, b] = starter.dataset.pair.split(','); return choose(a, b, true); }
    const open = e.target.closest('[data-open]');
    if (open) return openRecord(open.dataset.open, open.dataset.field, open);
    if (e.target.closest('#live')) {
      const s = $('live-status'); s.textContent = 'Asking the live model…';
      const asked = current;
      try {
        const r = await fetch('/api/explain', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ids: asked.ids})});
        const body = await r.json().catch(() => ({}));
        if (current !== asked || !s.isConnected) return; // the pair changed while the model answered: this reply is for another panel
        if (!r.ok) throw new Error(body.error);
        if (String(body.ids) !== String(asked.ids)) throw new Error('The live answer was for another pair. The saved explanation stays.');
        s.textContent = `${body.passed.length} sentences passed the checker, ${body.removed.length} removed (${body.seconds}s).`;
        const why = result.querySelector('.why'); if (why) why.open = true;
        const block = result.querySelector('.reading-block');
        // A pair without a saved explanation gets the same label for the live reading.
        if (!block.querySelector('.mono')) block.insertAdjacentHTML('afterbegin', '<span class="mono">Flaregrain reading · not NASA evidence</span>');
        const list = block.querySelector('ol') || block.appendChild(document.createElement('ol'));
        list.innerHTML = body.passed.map(p => `<li><p>${esc(p.text)}</p></li>`).join('');
      } catch (err) { if (current === asked && s.isConnected) s.textContent = err.message || 'Live model unavailable. The saved explanation stays.'; }
    }
  });

  /* ---------- Layer 3: the shared record drawer (drawer.js) ---------- */
  async function openRecord(id, field, opener) {
    const record = current?.records.find(x => x.id === id);
    try { await window.FlaregrainDrawer.open(id, {field, opener, record}); }
    catch (e) { status.textContent = e.message; }
  }

  /* ---------- Start ---------- */
  (async () => {
    if (location.protocol === 'file:') return offline();
    try { ({records} = await api('/api/records')); } catch (e) { return offline(); }
    const asked = (new URLSearchParams(location.search).get('ids') || '').split(',');
    const valid = id => records.some(r => r.id === id);
    if (asked.length === 2 && valid(asked[0]) && valid(asked[1]) && asked[0] !== asked[1]) {
      fillPickers(asked[0], asked[1]);
      return choose(asked[0], asked[1]);
    }
    // "Compare with…" from an answer: Run A is chosen, Run B is the researcher's pick.
    const a = new URLSearchParams(location.search).get('a');
    if (valid(a)) {
      fillPickers(a, '');
      last = {a, b: ''};
      await starters();
      status.textContent = 'Choose a record to compare with ' + records.find(r => r.id === a).name + '.';
      pickB.focus();
      return;
    }
    fillPickers('', '');
    starters();
  })();
})();

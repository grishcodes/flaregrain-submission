/* Compare page using the two checked records embedded at build time. */
(function () {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const OUT = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M2 8 8 2M3.5 2H8v4.5"/></svg>';
  const ARROW = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M1 5h8M5.5 1.5 9 5 5.5 8.5"/></svg>';
  const TIER = {checked: ['t1', 'Checked NASA record'], psi: ['t2', 'PSI table row'], context: ['t4', 'Context, not evidence'],
    dispute: ['dispute', 'Sources disagree'], flag: ['flag', 'NASA printed it, we read it differently'], missing: ['missing', 'Not in the source'], unrated: ['unrated', 'From the cited record, no field-level status']};
  const status = $('cmp-status'), result = $('cmp-result'), pickA = $('pick-a'), pickB = $('pick-b');
  const {records, starters: starterPairs, pairs} = JSON.parse($('compare-data').textContent);
  let current = null;
  let last = {a: '', b: ''};

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
    load(a, b, focus);
    if (location.protocol === 'http:' || location.protocol === 'https:') {
      history.replaceState(null, '', '?ids=' + encodeURIComponent(a) + ',' + encodeURIComponent(b));
    }
  }
  pickA.addEventListener('change', () => choose(pickA.value, pickB.value));
  pickB.addEventListener('change', () => choose(pickA.value, pickB.value));
  $('swap').addEventListener('click', () => { if (pickA.value && pickB.value) choose(pickB.value, pickA.value, true); });

  /* ---------- Start state: no pair chosen ---------- */
  function starters() {
    status.textContent = 'Choose two records, or start with a prepared pair.';
    result.hidden = false;
    result.classList.remove('play'); result.classList.add('static');
    result.innerHTML = `<h2 id="cmp-title" class="starter-title" tabindex="-1">Start with a prepared pair</h2>
      <div class="starters">${starterPairs.map(st => `<button type="button" class="starter" data-pair="${esc(st.ids.join(','))}">
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
    const cell = (text, flag) => `<span role="cell"${flag ? ` class="flag-${flag}"` : ''}>${flag ? mk(flag) + `<span class="vh">${flag === 'dispute' ? 'Sources disagree: ' : 'Not in source: '}</span>` : ''}${esc(text)}</span>`;
    const rows = c.rows.map(([label, a, b], i) => `<div class="row line-in" role="row" style="--d:${8 + i}"><span class="mono" role="rowheader">${esc(label)}</span>${cell(a, c.rowFlags[i][0])}${cell(b, c.rowFlags[i][1])}</div>`).join('');
    const condition = ({tier, label, value, readings}) => {
      const content = readings
        ? '<span>Sources disagree</span><ul>' + readings.map(reading => `<li><a href="${esc(reading.url)}" target="_blank" rel="noopener">${esc(reading.value)} · ${esc(reading.label)}</a></li>`).join('') + '</ul>'
        : `<span>${esc(value)}</span>`;
      return `<div class="${tier === 'missing' ? 'miss' : ''}"><dt>${esc(label)}</dt><dd>${mk(tier)}${content}</dd></div>`;
    };
    const strip = c.conditions.map((list, i) => `<div class="strip-run"><span class="mono">${esc(c.records[i].name)}</span><dl>${list.map(condition).join('')}</dl></div>`).join('');
    const issues = [c.issues.disputed && `${c.issues.disputed} ${c.issues.disputed === 1 ? 'value needs' : 'values need'} a second reading`,
      c.issues.missing && `${c.issues.missing} not in source`].filter(Boolean).join(' · ');
    result.innerHTML = `
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
      <section class="layer2" aria-label="Side by side and supporting detail">
        <div class="table" role="table" aria-label="Side by side">
          <div class="row head" role="row"><span role="columnheader" aria-label="Field"></span>
            <span role="columnheader">${esc(A.name)}<button type="button" class="full" data-open="${esc(A.id)}">Full record ${ARROW}</button></span>
            <span role="columnheader">${esc(B.name)}<button type="button" class="full" data-open="${esc(B.id)}">Full record ${ARROW}</button></span></div>
          ${rows}
        </div>
      </section>`;
    result.hidden = false;
    result.classList.remove('play', 'static'); void result.offsetWidth;
    result.classList.add(reduced ? 'static' : 'play');
    clearTimeout(render.settle);
    render.settle = setTimeout(() => result.classList.replace('play', 'static'), 2000);
  }

  function load(a, b, focus) {
    current = pairs[a + ',' + b];
    render(current);
    status.textContent = `Comparing ${current.records[0].name} and ${current.records[1].name}.`;
    if (focus) $('cmp-title').focus({preventScroll: true});
  }

  result.addEventListener('click', e => {
    const starter = e.target.closest('[data-pair]');
    if (starter) {
      const [a, b] = starter.dataset.pair.split(',');
      choose(a, b, true);
      return;
    }
    const opener = e.target.closest('[data-open]');
    if (opener) {
      const record = current.records.find(item => item.id === opener.dataset.open);
      window.FlaregrainDrawer.open(record, {opener});
    }
  });

  /* ---------- Start ---------- */
  (() => {
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
      starters();
      status.textContent = 'Choose a record to compare with ' + records.find(r => r.id === a).name + '.';
      pickB.focus();
      return;
    }
    fillPickers('', '');
    starters();
  })();
})();

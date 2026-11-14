/* Full-record drawer for the selected comparison. */
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const OUT = '<svg viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M2 8 8 2M3.5 2H8v4.5"/></svg>';
  const X = '<svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12"/></svg>';
  const TIER = {checked: ['t1', 'Checked NASA record'], psi: ['t2', 'PSI table row'], context: ['t4', 'Context, not evidence'],
    dispute: ['dispute', 'Sources disagree'], flag: ['flag', 'NASA printed it, we read it differently'], missing: ['missing', 'Not in the source'], unrated: ['unrated', 'From the cited record, no field-level status']};
  const mk = t => `<span class="mk ${TIER[t]?.[0] || 'unrated'}" aria-hidden="true"></span>`;

  document.body.insertAdjacentHTML('beforeend', `
    <dialog class="drawer" id="drawer" aria-labelledby="d-title"><div class="d-wrap">
      <div class="d-head"><div class="d-row"><div><span class="mono" id="d-sub"></span><h2 id="d-title"></h2></div>
        <button class="close" type="button" aria-label="Close record" data-close>${X}</button></div></div>
      <div class="d-body" id="d-body"></div></div></dialog>`);
  const drawer = document.getElementById('drawer');
  drawer.addEventListener('click', e => { if (e.target === drawer || e.target.closest('[data-close]')) drawer.close(); });
  // Keep Tab and Shift+Tab inside the open drawer. Chromium otherwise lets focus leave a modal dialog for one stop.
  const FOCUSABLE = 'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
  drawer.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const items = [...drawer.querySelectorAll(FOCUSABLE)].filter(el => el.offsetParent !== null || el === document.activeElement);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || !drawer.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || !drawer.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
  });

  function open(r, {field, opener} = {}) {
    document.getElementById('d-title').textContent = r.name;
    document.getElementById('d-sub').textContent = [r.investigation, r.sample].filter(Boolean).join(' · ');
    const disputes = r.fields.filter(f => f.tier === 'dispute');
    const sourceLink = (url, label) => ` <a href="${esc(url)}" target="_blank" rel="noopener">${esc(label)}</a>`;
    const row = f => {
      const primary = f.url && f.url !== r.source.url ? sourceLink(f.url, f.source) : '';
      const secondary = f.archiveUrl && f.archiveUrl !== f.url && f.archiveUrl !== r.source.url
        ? sourceLink(f.archiveUrl, f.archive) : '';
      return `<div class="${f.tier === 'missing' ? 'miss' : ''}${field && f.field === field ? ' hl' : ''}">${mk(f.tier)}<dt>${esc(f.field)}</dt><dd>${esc(f.value)}${f.status ? `<small>${esc(f.status)}</small>` : ''}${primary}${secondary}</dd></div>`;
    };
    document.getElementById('d-body').innerHTML = `
      ${r.source.url ? `<a class="open-src" href="${esc(r.source.url)}" target="_blank" rel="noopener"><span>Open the NASA page<small>${esc(r.source.label)}</small></span>${OUT}</a>` : ''}
      ${disputes.length ? `<div class="sec"><span class="mono">Needs a second reading</span>${disputes.map(f => `<div class="dispute-box"><div class="t">${mk('dispute')}${esc(f.field)} · sources disagree</div><p>${esc(f.value)}</p><ul><li><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.source)}</a></li><li><a href="${esc(f.archiveUrl)}" target="_blank" rel="noopener">${esc(f.archive)}</a></li></ul></div>`).join('')}</div>` : ''}
      <div class="sec"><span class="mono">Record</span><dl class="fields">${r.fields.filter(f => f.tier !== 'dispute').map(row).join('')}</dl></div>
      <div class="sec"><span class="mono">What the markers mean</span><ul class="key">${Object.values(TIER).map(([c, l]) => `<li><span class="mk ${c}"></span>${esc(l)}</li>`).join('')}</ul></div>`;
    drawer.showModal();
    const hl = document.querySelector('#d-body .hl');
    if (hl) hl.scrollIntoView({block: 'center'});
    drawer.querySelector('[data-close]').focus();
    drawer.addEventListener('close', () => opener?.focus(), {once: true});
  }

  window.FlaregrainDrawer = {open, mk, esc, TIER};
})();

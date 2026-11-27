/* media.js (offline prepper kit v1.17.0): helpers shared by the Books, Movies and Software pages. */
window.fzMedia = (() => {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  // A command to type on the computer that runs the kit, with a Copy button
  const cmd = text => `<span class="cmd"><span>${esc(text)}</span><button type="button" data-copy="${esc(text)}">Copy</button></span>`;
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-copy]');
    if (!b) return;
    const done = () => { b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1500); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(b.dataset.copy).then(done, () => {});
    else {  // phones on http://192.168... are not a "secure context": select-and-copy fallback
      const t = document.createElement('textarea');
      t.value = b.dataset.copy; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (_) {}
      t.remove();
    }
  });
  const store = {  // per-device conveniences only (resume position, last tab); fine if it's blocked
    get(k, d) { try { const v = localStorage.getItem('fz:' + k); return v === null ? d : JSON.parse(v); } catch (_) { return d; } },
    set(k, v) { try { localStorage.setItem('fz:' + k, JSON.stringify(v)); } catch (_) {} },
  };
  const json = u => fetch(u, {cache: 'no-store'}).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
  // "Module not installed" box: what it is, and the commands that add it
  const banner = (title, lines) => `<div class="banner"><h3>${esc(title)}</h3>${lines.map(l => `<p>${l}</p>`).join('')}</div>`;
  return {esc, cmd, store, json, banner};
})();

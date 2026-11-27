/* media.js (offline prepper kit v1.19.0): helpers shared by the Books, Movies and Software pages (incl. uploads). */
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
  // Send one file to the kit (POST /uploads, raw body) with progress; resolves with the kit's answer
  const upload = (file, params, onProgress) => new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open('POST', '/uploads?' + new URLSearchParams(Object.assign({name: file.name}, params)));
    x.setRequestHeader('X-Kit-Upload', '1');
    x.setRequestHeader('Content-Type', 'application/octet-stream');
    x.upload.onprogress = e => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    x.onload = () => { let d = {}; try { d = JSON.parse(x.responseText); } catch (_) {}
      x.status === 200 ? resolve(d) : reject(new Error(d.error || `The kit answered ${x.status}.`)); };
    x.onerror = () => reject(new Error('The upload stopped (Wi-Fi dropped, or the kit was closed).'));
    x.send(file);
  });
  // Several files one after another, one progress bar for all, a ✓/✗ line per file. send(file, onProgress) -> Promise
  async function uploadAll(files, send, bar, msg, after) {
    const total = files.reduce((a, f) => a + f.size, 0) || 1, lines = [];
    let done = 0;
    bar.hidden = false;
    for (const f of files) {
      msg.innerHTML = lines.join('<br>') + (lines.length ? '<br>' : '') + `Uploading ${esc(f.name)}…`;
      try {
        const d = await send(f, p => bar.firstElementChild.style.width = (100 * (done + p * f.size) / total) + '%');
        lines.push(`✓ ${esc(f.name)}`); after(d);
      } catch (err) { lines.push(`<span class="bad">✗ ${esc(f.name)}: ${esc(err.message)}</span>`); }
      done += f.size; bar.firstElementChild.style.width = (100 * done / total) + '%';
    }
    msg.innerHTML = lines.join('<br>');
    setTimeout(() => { bar.hidden = true; bar.firstElementChild.style.width = 0; }, 800);
  }
  const removeUpload = (kind, key) => fetch('/uploads/delete', {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Kit-Upload': '1'}, body: JSON.stringify({kind, key})})
    .then(r => r.json().catch(() => ({})).then(d => { if (!r.ok) throw new Error(d.error || 'Could not remove it.'); return d; }));
  return {esc, cmd, store, json, banner, upload, uploadAll, removeUpload};
})();

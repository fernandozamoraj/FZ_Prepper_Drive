/* nav.js (offline prepper kit v1.14.1): the header bar on every page of the kit:
   ⌂ Home (hub, port 8000) · Library (8080) · Bible (8000/bible) · Maps (8090) · Books · Movies · Software (8000/...).
   The library and map ports can move when another program has them: the hub's /ports.json says where they are,
   and window.fzKit (.lib, .maps, .hub, .ready) gives other page scripts the current addresses.
   Served as /nav.js by intranet.py, serve-maps.py and kiwix-serve (KIWIX_SERVE_CUSTOMIZED_RESOURCES,
   set up by serve.sh; the library viewer loads it from home/viewer_settings.js).
   Links use the page's own host name, so they work on phones over the Wi-Fi too.
   A page can set <body data-fznav="overlay"> to get a fixed bar (the map), otherwise the bar sits
   at the top of the page and sticks while scrolling. */
(function () {
  if (window.__fznav) return;
  window.__fznav = true;

  const h = location.hostname, p = location.protocol, port = location.port || (p === 'https:' ? '443' : '80');
  const NAV_VERSION = '1.14.1';  // = intranet.py VERSION; a running hub that reports another one is older: restart it
  const K = window.fzKit = {ports: {hub: 8000, library: 8080, maps: 8090}};
  const at = n => `${p}//${h}:${K.ports[n]}/`;
  Object.defineProperties(K, {hub: {get: () => at('hub')}, lib: {get: () => at('library')}, maps: {get: () => at('maps')}});
  const getPorts = u => fetch(u, {cache: 'no-store'}).then(r => { if (!r.ok) throw 0; return r.json(); });
  K.ready = getPorts(`${p}//${h}:8000/ports.json`).catch(() => getPorts('/ports.json'))  // 2nd: a hub on another port
    .then(j => { K.hubVersion = j.version || 'older'; delete j.version; Object.assign(K.ports, j); return K; })
    // No /ports.json at all: a hub from before 1.13.3 still answers /status.json (only the hub does)
    .catch(() => fetch('/status.json', {cache: 'no-store'}).then(r => { if (r.ok) K.hubVersion = 'older'; return K; }, () => K));

  function current() {
    if (port === String(K.ports.maps)) return 'maps';
    if (port === String(K.ports.library)) return /^#bible_/.test(location.hash) ? 'bible' : 'library';
    if (port === String(K.ports.hub)) return (location.pathname.match(/^\/(bible|books|movies|software)/) || [0, 'home'])[1];
    return '';
  }

  const css = `
#fznav{--fz-bg:#1f3a26;--fz-fg:#f3f6f1;--fz-on:#7cc48a;--fz-onfg:#10200f;--fz-hover:rgba(255,255,255,.12);
  display:flex;align-items:center;gap:4px;height:40px;padding:0 10px;box-sizing:border-box;width:100%;
  background:var(--fz-bg);color:var(--fz-fg);font:600 14px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  z-index:2147483000;box-shadow:0 1px 3px rgba(0,0,0,.25);overflow-x:auto;scrollbar-width:none;-webkit-text-size-adjust:100%}
#fznav::-webkit-scrollbar{display:none}
#fznav.fz-sticky{position:sticky;top:0}
#fznav.fz-overlay{position:fixed;top:0;left:0;right:0}
#fznav a{display:inline-flex;align-items:center;gap:5px;height:30px;padding:0 11px;border-radius:8px;
  color:var(--fz-fg);text-decoration:none;white-space:nowrap}
#fznav a:hover{background:var(--fz-hover)}
#fznav a[aria-current=page]{background:var(--fz-on);color:var(--fz-onfg)}
#fznav .fz-home{font-size:15px;margin-right:6px}
#fznav .fz-ico{font-size:15px;line-height:1}
@media (max-width:420px){ #fznav a{padding:0 8px} #fznav .fz-lbl-long{display:none} }
@media print{ #fznav{display:none} }`;

  function build() {
    if (document.getElementById('fznav')) return;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    const cur = current();
    const nav = document.createElement('nav');
    nav.id = 'fznav';
    nav.setAttribute('aria-label', 'Kit navigation');
    nav.className = document.body.dataset.fznav === 'overlay' ? 'fz-overlay' : 'fz-sticky';
    const item = (id, href, ico, label, cls = '') =>
      `<a href="${href}" class="${cls}"${cur === id ? ' aria-current="page"' : ''}><span class="fz-ico">${ico}</span>${label}</a>`;
    nav.innerHTML =
      item('home', K.hub, '⌂', 'Home', 'fz-home') +
      item('library', K.lib, '📚', 'Library') +
      item('bible', K.hub + 'bible', '📖', 'Bible') +
      item('maps', K.maps, '🗺️', 'Maps') +
      item('books', K.hub + 'books', '📕', 'Books') +
      item('movies', K.hub + 'movies', '🎬', 'Movies') +
      item('software', K.hub + 'software', '💾', 'Software');
    // Links open in this tab, never inside the library's content frame
    nav.querySelectorAll('a').forEach(a => a.target = '_top');
    document.body.insertBefore(nav, document.body.firstChild);

    // The library viewer switches between books via the URL hash; keep "Bible" vs "Library" right
    window.addEventListener('hashchange', () => {
      const c = current();
      nav.querySelectorAll('a[data-sec]').forEach(a =>
        a.dataset.sec === c ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    });
    const SECS = ['home', 'library', 'bible', 'maps', 'books', 'movies', 'software'];
    nav.querySelectorAll('a').forEach((a, i) => a.dataset.sec = SECS[i]);
    // Once the hub says where everything runs, point the links there
    K.ready.then(() => {
      const href = {home: K.hub, library: K.lib, bible: K.hub + 'bible', maps: K.maps, books: K.hub + 'books',
        movies: K.hub + 'movies', software: K.hub + 'software'}, c = current();
      nav.querySelectorAll('a[data-sec]').forEach(a => {
        a.href = href[a.dataset.sec];
        a.dataset.sec === c ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
      });
    });

    // The kit's files were updated but the kit running now is the old one (it was not restarted): its server
    // doesn't know the new pages yet. Say so, instead of letting people hit "404 Not Found".
    K.ready.then(() => {
      if (!K.hubVersion || K.hubVersion === NAV_VERSION || document.getElementById('fz-restart')) return;
      const bar = document.createElement('div');
      bar.id = 'fz-restart';
      bar.setAttribute('role', 'status');
      bar.style.cssText = 'background:#fff3cd;color:#3d2e00;font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;' +
        'padding:8px 14px;border-bottom:1px solid #e8cf8a;position:relative;z-index:2147482999';
      bar.innerHTML = `<b>Restart the kit to finish updating.</b> Its files are version ${NAV_VERSION}, but the kit that is ` +
        `running is ${K.hubVersion === 'older' ? 'an older version' : 'version ' + K.hubVersion}, so new pages (Books, Movies, Software) ` +
        `won't open yet. On the computer running it, close the kit's window (or press Ctrl+C) and start it again.`;
      if (nav.classList.contains('fz-overlay')) bar.style.cssText += ';position:fixed;top:40px;left:0;right:0';
      nav.insertAdjacentElement('afterend', bar);
    });

    // Library articles with a location (Wikipedia, Wikivoyage...) link to the offline map
    const frame = document.getElementById('content_iframe');
    if (frame) {
      const onMap = document.createElement('a');
      onMap.id = 'fz-onmap';
      onMap.target = '_top';
      onMap.style.cssText = 'margin-left:auto;display:none';
      nav.appendChild(onMap);
      frame.addEventListener('load', () => { try { linkMaps(frame.contentDocument, onMap); } catch (e) { onMap.style.display = 'none'; } });
    }
  }

  // ---------- Library article → offline map ----------
  // Articles mark places with geo: links (Wikipedia's coordinates, Wikivoyage's numbered listing markers).
  // Offline those do nothing, so point the US ones at the offline map with a pin, and add a header button.
  const inUS = (lat, lon) => lat > 17 && lat < 72 && lon > -180 && lon < -64;
  const mapURL = (lat, lon, label, zoom) =>
    `${K.maps}?pin=${(+lat).toFixed(5)},${(+lon).toFixed(5)}&label=${encodeURIComponent(label || '')}#${zoom}/${(+lat).toFixed(5)}/${(+lon).toFixed(5)}`;

  function linkMaps(doc, btn) {
    btn.style.display = 'none';
    if (!doc || !doc.body) return;
    const title = (doc.title || '').replace(/\s+[-–—]\s+(Wikipedia|Wikivoyage).*$/, '').trim();
    let main = null;
    doc.querySelectorAll('a[href^="geo:"]').forEach(a => {
      const m = a.getAttribute('href').match(/^geo:(-?[\d.]+),(-?[\d.]+)/);
      if (!m || !inUS(+m[1], +m[2])) return;
      // A Wikivoyage listing's name follows its marker; Wikipedia's coordinates belong to the article itself
      const item = a.closest('.vcard, .listing, li, p');
      const nameEl = item && item.querySelector('.listing-name');  // Wikivoyage only (Wikipedia infoboxes also use .vcard/.fn)
      const label = nameEl ? nameEl.textContent.trim() : title;
      a.href = mapURL(m[1], m[2], label, +a.dataset.zoom || (nameEl ? 16 : 12));
      a.target = '_top';
      a.title = 'Show on the offline map';
      a.removeAttribute('rel');
      if (!nameEl && !main) main = {lat: m[1], lon: m[2]};
    });
    // Page location: Wikipedia's coordinates, else a Wikivoyage page map (mapframe), else the first listing
    if (!main) {
      const f = doc.querySelector('[data-mw-kartographer="mapframe"][data-lat], .mw-kartographer-map[data-lat]');
      if (f && inUS(+f.dataset.lat, +f.dataset.lon)) main = {lat: f.dataset.lat, lon: f.dataset.lon, zoom: +f.dataset.zoom || 11};
    }
    if (!main) {  // no page location: the middle of the page's listings (the first one may be an outlying airport)
      const pts = [...doc.querySelectorAll('a[href*="?pin="]')].map(a => new URL(a.href).searchParams.get('pin').split(',').map(Number));
      const mid = arr => arr.sort((x, y) => x - y)[Math.floor(arr.length / 2)];
      if (pts.length) main = {lat: mid(pts.map(p => p[0])), lon: mid(pts.map(p => p[1])), zoom: pts.length > 1 ? 11 : 14};
    }
    if (!main) return;
    btn.href = mapURL(main.lat, main.lon, title, main.zoom || 12);
    btn.innerHTML = `<span class="fz-ico">📍</span>Show on map`;
    btn.style.display = '';
  }

  if (document.body) build();
  else document.addEventListener('DOMContentLoaded', build);
})();

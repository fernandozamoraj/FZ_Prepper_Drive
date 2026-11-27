/* reader.js (offline prepper kit v1.20.1): the e-book reader page (home/reader.html), on top of foliate-js.
   /reader?book=/files/<...>.epub&title=Name. Remembers the place in each book and the text size and colors on this
   device. Books are shown in frames whose scripts the page's Content-Security-Policy blocks (see intranet.py). */
const $ = id => document.getElementById(id);
const store = {
  get(k, d) { try { const v = localStorage.getItem('fz:' + k); return v === null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem('fz:' + k, JSON.stringify(v)); } catch (_) {} },
};
const THEMES = ['light', 'sepia', 'dark'];
const COLORS = {light: ['#fbfaf6', '#1d1d1b', '#2f6b3a'], sepia: ['#f4ecd8', '#5b4636', '#7a4b1e'], dark: ['#161714', '#e6e4dc', '#7cc48a']};
const prefs = Object.assign({size: 100, theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'},
  store.get('reader:prefs', {}));
const params = new URLSearchParams(location.search);
const book = params.get('book') || '';
let view = null;

function fail(html) {
  $('rmsg').innerHTML = html;
  $('rtitle').textContent = 'Reader';
}

const bookCSS = () => {
  const [bg, ink, link] = COLORS[prefs.theme];
  return `html { color-scheme: ${prefs.theme === 'dark' ? 'dark' : 'light'}; }
    html, body { background: ${bg} !important; color: ${ink} !important; }
    body { font-size: ${prefs.size}% !important; }
    p, li, blockquote, dd { line-height: 1.5; }
    a:link, a:visited { color: ${link} !important; }
    img, svg, video { max-width: 100%; height: auto; }
    pre { white-space: pre-wrap !important; }`;
};
function applyPrefs() {
  document.body.classList.remove(...THEMES);
  document.body.classList.add(prefs.theme);
  view?.renderer?.setStyles?.(bookCSS());
  store.set('reader:prefs', prefs);
}

function tocList(items) {
  const ol = document.createElement('ol');
  for (const it of items || []) {
    const li = document.createElement('li'), a = document.createElement('a');
    a.href = '#';
    a.textContent = (it.label || '').trim() || '…';
    a.dataset.href = it.href || '';
    li.append(a);
    if (it.subitems?.length) li.append(tocList(it.subitems));
    ol.append(li);
  }
  return ol;
}

async function main() {
  // Only the kit's own files (never another web site, which the page's policy would block anyway)
  if (!/^\/files\/[^?#]+\.(epub|mobi|azw3|azw|fb2|fbz|cbz|kf8)$/i.test(book)) {
    return fail('No book chosen. Open one from the <a href="/books">Books</a> page with <b>📖 Read</b>.');
  }
  const name = decodeURIComponent(book.split('/').pop());
  $('rtitle').textContent = params.get('title') || name;
  $('dl').href = book + '?download';
  try {
    await import('/reader-lib/view.js');
  } catch (e) {
    return fail(`<b>The e-book reader isn't installed in this kit yet.</b> On the computer that runs the kit, open a
      terminal in the kit folder and run <code>./kit.sh setup-reader</code> (Windows: <code>kit.bat setup-reader</code>),
      then reload. Meanwhile you can <a href="${book}?download">download the book</a>.`);
  }
  view = document.createElement('foliate-view');
  $('rmsg').remove();
  $('rview').append(view);
  try {
    await view.open(book);
  } catch (e) {
    view.remove();
    $('rview').innerHTML = '<p class="rmsg" id="rmsg"></p>';
    return fail(`<b>This book can't be opened here</b> (${String(e.message || e).replace(/[<>&]/g, '')}).
      Some Kindle files are copy-protected. You can still <a href="${book}?download">download it</a> and open it in an app.`);
  }
  const meta = view.book.metadata || {};
  const title = params.get('title') || (typeof meta.title === 'string' ? meta.title : Object.values(meta.title || {})[0]) || name;
  document.title = title;
  $('rtitle').textContent = title;
  view.renderer.setAttribute('flow', 'paginated');
  view.renderer.setAttribute('max-column-count', '2');
  view.renderer.setAttribute('margin', '32px');
  applyPrefs();

  if (view.book.toc?.length) {
    $('toclist').append(tocList(view.book.toc));
    $('tocbtn').disabled = false;
  }

  const key = 'reader:pos:' + book;
  view.addEventListener('relocate', e => {
    const {fraction, tocItem, cfi} = e.detail;
    $('rpos').textContent = [Math.round((fraction || 0) * 100) + '%', tocItem?.label?.trim()].filter(Boolean).join(' · ');
    $('rslider').value = fraction || 0;
    if (cfi) store.set(key, cfi);
  });
  // Arrow keys and taps on the left/right edge of the page turn pages (also inside the book's frame)
  view.addEventListener('load', e => {
    const doc = e.detail.doc;
    doc.addEventListener('keydown', onKey);
    doc.addEventListener('click', ev => {
      if (ev.target.closest?.('a[href]') || doc.getSelection()?.toString()) return;
      const w = doc.defaultView.innerWidth || 1, x = ev.clientX % w;
      if (x < w * 0.25) view.goLeft(); else if (x > w * 0.75) view.goRight();
    });
  });
  await view.init({lastLocation: store.get(key, null), showTextStart: true});
  $('rslider').hidden = false;
}

function onKey(e) {
  if (!view) return;
  if (e.key === 'ArrowLeft' || e.key === 'PageUp') view.goLeft();
  else if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); view.goRight(); }
}
document.addEventListener('keydown', onKey);
$('prev').onclick = () => view?.goLeft();
$('next').onclick = () => view?.goRight();
$('rslider').addEventListener('input', e => view?.goToFraction(parseFloat(e.target.value)));
$('smaller').onclick = () => { prefs.size = Math.max(70, prefs.size - 10); applyPrefs(); };
$('bigger').onclick = () => { prefs.size = Math.min(220, prefs.size + 10); applyPrefs(); };
$('theme').onclick = () => { prefs.theme = THEMES[(THEMES.indexOf(prefs.theme) + 1) % THEMES.length]; applyPrefs(); };
$('tocbtn').onclick = () => { $('rtoc').hidden = false; };
$('tocclose').onclick = () => { $('rtoc').hidden = true; };
$('toclist').addEventListener('click', e => {
  const a = e.target.closest('a');
  if (!a) return;
  e.preventDefault();
  $('rtoc').hidden = true;
  if (a.dataset.href) view?.goTo(a.dataset.href).catch(() => {});
});
document.body.classList.add(prefs.theme);
main().catch(e => fail(`Something went wrong opening the book: ${String(e.message || e).replace(/[<>&]/g, '')}`));

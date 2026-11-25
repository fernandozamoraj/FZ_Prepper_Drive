#!/usr/bin/env python3
"""build-bible.py (v1.8.0): build kiwix/bible_en_kjv_<yyyy-mm>.zim (the offline King James Bible)
and home/kjv.json (verse data for the Bible search page at the intranet hub's /bible).

Source: eBible.org eng-kjv2006 verse-per-line text (KJV, standardized 1769 text, 66 books,
public domain). Words the translators supplied ([was]) are shown in italics, as in printed KJVs.
Pages: home (Old/New Testament book list), one page per book (chapter grid), one page per chapter
(numbered verses, verse anchors #v16, previous/next chapter). Full-text search is built in, so
the library home page and kiwix-serve can search phrases ("my shepherd") and titles ("John 3").

Usage: bible/.venv/bin/python bible/build-bible.py   (download with bible/build-bible.sh)
"""
import datetime
import html
import json
import os
import re
import struct
import sys
import zlib

from libzim.writer import Creator, Hint, IndexData, Item, StringProvider

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "src", "kjv2006", "eng-kjv2006_vpl.txt")
VERSION = "1.8.0"

# eBible's book codes in Bible order, with display names. 39 Old Testament + 27 New Testament.
BOOKS = [
    ("GEN", "Genesis"), ("EXO", "Exodus"), ("LEV", "Leviticus"), ("NUM", "Numbers"), ("DEU", "Deuteronomy"),
    ("JOS", "Joshua"), ("JDG", "Judges"), ("RUT", "Ruth"), ("1SA", "1 Samuel"), ("2SA", "2 Samuel"),
    ("1KI", "1 Kings"), ("2KI", "2 Kings"), ("1CH", "1 Chronicles"), ("2CH", "2 Chronicles"), ("EZR", "Ezra"),
    ("NEH", "Nehemiah"), ("EST", "Esther"), ("JOB", "Job"), ("PSA", "Psalms"), ("PRO", "Proverbs"),
    ("ECC", "Ecclesiastes"), ("SOL", "Song of Solomon"), ("ISA", "Isaiah"), ("JER", "Jeremiah"),
    ("LAM", "Lamentations"), ("EZE", "Ezekiel"), ("DAN", "Daniel"), ("HOS", "Hosea"), ("JOE", "Joel"),
    ("AMO", "Amos"), ("OBA", "Obadiah"), ("JON", "Jonah"), ("MIC", "Micah"), ("NAH", "Nahum"),
    ("HAB", "Habakkuk"), ("ZEP", "Zephaniah"), ("HAG", "Haggai"), ("ZEC", "Zechariah"), ("MAL", "Malachi"),
    ("MAT", "Matthew"), ("MAR", "Mark"), ("LUK", "Luke"), ("JOH", "John"), ("ACT", "Acts"),
    ("ROM", "Romans"), ("1CO", "1 Corinthians"), ("2CO", "2 Corinthians"), ("GAL", "Galatians"),
    ("EPH", "Ephesians"), ("PHI", "Philippians"), ("COL", "Colossians"), ("1TH", "1 Thessalonians"),
    ("2TH", "2 Thessalonians"), ("1TI", "1 Timothy"), ("2TI", "2 Timothy"), ("TIT", "Titus"),
    ("PHM", "Philemon"), ("HEB", "Hebrews"), ("JAM", "James"), ("1PE", "1 Peter"), ("2PE", "2 Peter"),
    ("1JO", "1 John"), ("2JO", "2 John"), ("3JO", "3 John"), ("JUD", "Jude"), ("REV", "Revelation"),
]
OT_COUNT = 39

CSS = """
:root { --bg:#fbf8f1; --fg:#222; --muted:#6b6357; --accent:#7a2e1f; --line:#e6dfd0; --card:#fff; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#1b1a18; --fg:#e8e3d8; --muted:#a59d8f; --accent:#e0a27a; --line:#3a3731; --card:#252320; }
}
html { background: var(--bg); }
body { margin: 0 auto; max-width: 760px; padding: 16px; color: var(--fg); background: var(--bg);
  font: 19px/1.65 Georgia, "Times New Roman", serif; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 1.7em; margin: .3em 0 .2em; text-align: center; }
h2 { font: 600 .8em system-ui, sans-serif; letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
  margin: 1.6em 0 .6em; border-bottom: 1px solid var(--line); padding-bottom: .3em; }
.sub { text-align: center; color: var(--muted); font-size: .85em; margin-bottom: 1em; }
.crumbs, .nav { font: 15px system-ui, sans-serif; display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.crumbs { margin-bottom: .4em; }
.nav { margin: 1.6em 0 .4em; padding-top: .8em; border-top: 1px solid var(--line); }
.nav a, .nav span { padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); }
.nav span { visibility: hidden; }
.books { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 6px;
  font: 16px system-ui, sans-serif; }
.books a { display: block; padding: 8px 10px; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
.books small { color: var(--muted); float: right; }
.chapters { display: grid; grid-template-columns: repeat(auto-fill, minmax(52px, 1fr)); gap: 6px;
  font: 16px system-ui, sans-serif; }
.chapters a { display: block; text-align: center; padding: 9px 0; background: var(--card); border: 1px solid var(--line); border-radius: 6px; }
p.v { margin: 0 0 .35em; }
p.v.para { margin-top: .9em; }
sup { font: 600 .62em system-ui, sans-serif; color: var(--accent); margin-right: .25em; vertical-align: .55em; }
p.v:target { background: rgba(255, 214, 102, .35); border-radius: 4px; }
i.s { color: var(--muted); }
.note { color: var(--muted); font: 14px system-ui, sans-serif; margin-top: 2em; }
"""


def page(title, body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(title)}</title><link rel="stylesheet" href="style.css"></head>'
            f'<body>{body}</body></html>')


def slug(name):
    return name.replace(" ", "_")


def verse_html(text):
    """KJV markup: [word] = supplied word (italics), ¶ = paragraph start."""
    para = "¶" in text
    text = html.escape(text.replace("¶", "").strip())
    text = re.sub(r"\[([^\]]+)\]", r'<i class="s">\1</i>', text)
    return para, text


def load():
    by_book = {code: {} for code, _ in BOOKS}
    pat = re.compile(r"^(\w{3}) (\d+):(\d+) (.*)$")
    with open(SRC, encoding="utf-8-sig") as f:
        for line in f:
            m = pat.match(line.rstrip("\n"))
            if not m:
                continue
            code, ch, v, text = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
            if code not in by_book:
                sys.exit(f"Unknown book code {code}")
            by_book[code].setdefault(ch, []).append((v, text))
    return by_book


def icon_png(size=48):
    """A simple open-book icon as PNG (no image libraries needed)."""
    bg, page_c, spine, line = (122, 46, 31), (251, 248, 241), (90, 30, 20), (190, 180, 160)
    px = []
    for y in range(size):
        row = []
        for x in range(size):
            c = bg
            if 10 <= y <= 39 and 6 <= x <= 41:
                c = page_c
                if x in (23, 24):
                    c = spine
                elif y in (16, 21, 26, 31) and (9 <= x <= 20 or 27 <= x <= 38):
                    c = line
            row.append(c)
        px.append(row)
    raw = b"".join(b"\x00" + bytes(v for c in row for v in c) for row in px)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


class Index(IndexData):
    """What full-text search sees for a page. text=None keeps the page out of search entirely."""

    def __init__(self, title, text):
        super().__init__()
        self._t, self._x = title, text

    def has_indexdata(self):
        return self._x is not None

    def get_title(self):
        return self._t

    def get_content(self):
        return self._x or ""

    def get_keywords(self):
        return ""

    def get_wordcount(self):
        return len((self._x or "").split())

    def get_geoposition(self):
        return None


class Page(Item):
    def __init__(self, path, title, content, mimetype="text/html", front=True, index_text=None):
        super().__init__()
        self._p, self._t, self._c, self._m, self._f = path, title, content, mimetype, front
        self._ix = index_text

    def get_indexdata(self):
        # Only verse entries are searchable (see below); chapter/book/home pages are for browsing
        return Index(self._t, self._ix)

    def get_path(self):
        return self._p

    def get_title(self):
        return self._t

    def get_mimetype(self):
        return self._m

    def get_contentprovider(self):
        return StringProvider(self._c)

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: self._f}


def main():
    books = load()
    total = sum(len(vs) for chs in books.values() for vs in chs.values())
    month = datetime.date.today().strftime("%Y-%m")
    out = os.path.join(KIT, "kiwix", f"bible_en_kjv_{month}.zim")
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)

    # Flat chapter list for previous/next links across book boundaries
    order = [(code, name, ch) for code, name in BOOKS for ch in sorted(books[code])]
    index_of = {(code, ch): i for i, (code, _, ch) in enumerate(order)}

    with Creator(tmp).config_indexing(True, "eng") as c:
        c.set_mainpath("index")
        for k, v in {
            "Name": "bible_en_kjv", "Title": "Holy Bible (KJV)", "Language": "eng",
            "Creator": "King James Version (1769 standard text)", "Publisher": "eBible.org; offline prepper kit",
            "Description": "The King James Bible: 66 books, every chapter, searchable",
            "LongDescription": "Authorized King James Version, standardized 1769 text, from eBible.org "
                               "(public domain outside the UK). Words supplied by the translators are in italics.",
            "Date": datetime.date.today().isoformat(), "Tags": "_category:other;bible;religion",
            "Source": "https://ebible.org/Scriptures/eng-kjv2006_vpl.zip",
            "Flavour": "kjv", "Scraper": f"offline-prepper-kit build-bible.py {VERSION}",
        }.items():
            c.add_metadata(k, v)
        c.add_illustration(icon_png(), 48)
        c.add_item(Page("style.css", "", CSS, "text/css", front=False))

        # Home: book list
        def book_links(sl):
            return '<div class="books">' + "".join(
                f'<a href="{slug(n)}">{html.escape(n)} <small>{len(books[c_])}</small></a>' for c_, n in sl) + "</div>"
        home = (f'<h1>Holy Bible</h1><div class="sub">King James Version · {len(BOOKS)} books · '
                f'{len(order):,} chapters · {total:,} verses</div>'
                f"<h2>Old Testament</h2>{book_links(BOOKS[:OT_COUNT])}"
                f"<h2>New Testament</h2>{book_links(BOOKS[OT_COUNT:])}"
                '<p class="note">Tip: search for a phrase ("the Lord is my shepherd") or a chapter ("John 3") '
                "from the library search box. Words in <i>italics</i> were supplied by the translators.</p>")
        c.add_item(Page("index", "Holy Bible (KJV)", page("Holy Bible (KJV)", home)))

        # Book pages: chapter grid
        for code, name in BOOKS:
            chs = sorted(books[code])
            body = (f'<div class="crumbs"><a href="index">Holy Bible</a></div><h1>{html.escape(name)}</h1>'
                    f'<div class="sub">{len(chs)} chapter{"s" if len(chs) > 1 else ""}</div>'
                    '<div class="chapters">' + "".join(f'<a href="{slug(name)}_{ch}">{ch}</a>' for ch in chs) + "</div>")
            c.add_item(Page(slug(name), name, page(f"{name} (KJV)", body)))

        # Chapter pages
        for code, name in BOOKS:
            for ch in sorted(books[code]):
                i = index_of[(code, ch)]
                link = lambda j, arrow: (  # noqa: E731
                    f'<a href="{slug(order[j][1])}_{order[j][2]}">{arrow}</a>' if 0 <= j < len(order) else "<span>·</span>")
                prev_l = link(i - 1, f"← {order[i - 1][1]} {order[i - 1][2]}" if i > 0 else "")
                next_l = link(i + 1, f"{order[i + 1][1]} {order[i + 1][2]} →" if i + 1 < len(order) else "")
                verses = []
                for v, text in books[code][ch]:
                    para, t = verse_html(text)
                    verses.append(f'<p class="v{" para" if para and v > 1 else ""}" id="v{v}"><sup>{v}</sup>{t}</p>')
                title = f"{name} {ch}"
                body = (f'<div class="crumbs"><a href="index">Holy Bible</a><a href="{slug(name)}">{html.escape(name)}: all chapters</a></div>'
                        f"<h1>{html.escape(title)}</h1>" + "".join(verses) + f'<div class="nav">{prev_l}{next_l}</div>')
                c.add_item(Page(f"{slug(name)}_{ch}", title, page(f"{title} (KJV)", body)))

                # One small search entry per verse (the only searchable pages). kiwix-serve has no phrase
                # search and ranks whole chapters by word counts, so "the lord is my shepherd" found
                # Ezekiel 34 before Psalm 23.
                # A short verse page matches a quoted verse almost exactly; opening it jumps to the verse
                # (highlighted) in its chapter. Not a front article, so title suggestions stay chapter-level.
                for v, text in books[code][ch]:
                    _, t = verse_html(text)
                    ref = f"{name} {ch}:{v}"
                    target = f"{slug(name)}_{ch}#v{v}"
                    # Verse text first: kiwix-serve builds search snippets from the start of the page
                    vbody = (f'<p class="v">{t}</p><p class="note">{html.escape(ref)} · '
                             f'<a href="{target}">read all of {html.escape(title)}</a></p>')
                    vpage = page(f"{ref} (KJV)", vbody).replace(
                        "</head>", f'<meta http-equiv="refresh" content="0; url={target}"></head>')
                    plain = re.sub(r"\[([^\]]+)\]", r"\1", text.replace("¶", "")).strip()
                    c.add_item(Page(f"{slug(name)}_{ch}_v{v}", ref, vpage, front=False, index_text=plain))
    os.replace(tmp, out)
    write_json(books)
    print(f"{out}: {len(BOOKS)} books, {len(order)} chapters, {total} verses, {os.path.getsize(out) / 1e6:.1f} MB")


def write_json(books):
    """home/kjv.json for the Bible search page (intranet /bible): [[name, [[verse text, ...] per chapter]], ...].
    Verse text keeps [supplied] brackets and ¶ marks; the page renders them."""
    data = [[name, [[t for _, t in books[code][ch]] for ch in sorted(books[code])]] for code, name in BOOKS]
    out = os.path.join(KIT, "home", "kjv.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"version": "KJV", "source": "eBible.org eng-kjv2006 (public domain)", "books": data},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"{out}: {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

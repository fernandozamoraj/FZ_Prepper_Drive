#!/usr/bin/env python3
"""tests/test_reader.py (offline prepper kit v1.20.1): the e-book reader's server side and its library.

    python3 tests/test_reader.py

/reader is sent with a Content-Security-Policy that allows only the kit's own scripts (no inline scripts, no blob:
scripts: e-books can carry scripts) and other pages are not; /reader.js and /reader.css are served; /reader-lib/ serves
only the library's .js files (no LICENSE, no path tricks); the installed library (kit setup-reader) matches the
pinned sha256 list in scripts/kit.py, if it is installed.
"""
import hashlib
import http.client
import http.server
import importlib.util
import os
import re
import sys
import threading

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


def main():
    sys.path.insert(0, os.path.join(KIT, "bin"))
    import intranet
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), intranet.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(path):
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
        c.request("GET", path)
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, dict(r.getheaders()), body

    try:
        st, h, body = get("/reader?book=/files/books/x.epub")
        csp = h.get("Content-Security-Policy", "")
        check(st == 200 and b"/reader.js" in body, "/reader serves the reader page")
        check("script-src 'self';" in csp and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
              and "blob:" not in csp.split("script-src")[1].split(";")[0], f"CSP: only the kit's own scripts ({csp[:60]}…)")
        check("frame-src 'self' blob:" in csp and "object-src 'none'" in csp, "CSP: book frames allowed, plugins not")
        page = re.sub(rb"<!--.*?-->", b"", body, flags=re.S)
        check(not re.search(rb"<script(?![^>]*\bsrc=)[^>]*>", page), "reader page has no inline scripts (CSP would block them)")
        st, h, _ = get("/books")
        check(st == 200 and "Content-Security-Policy" not in h, "other pages are not given the reader's policy")
        st, h, _ = get("/reader?x=1")
        check("Content-Security-Policy" in h, "policy is sent again on a second request")
        for path in ("/reader.js", "/reader.css"):
            check(get(path)[0] == 200, f"{path} served")
        check(get("/reader-lib/LICENSE")[0] == 404, "/reader-lib/LICENSE not served (only .js)")
        check(get("/reader-lib/../bin/intranet.py")[0] == 404, "/reader-lib/ path trick refused")
        check(get("/reader-lib/sub/dir/x.js")[0] == 404, "/reader-lib/ only top level and vendor/")

        spec = importlib.util.spec_from_file_location("kit", os.path.join(KIT, "scripts", "kit.py"))
        kit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(kit)
        lib = os.path.join(KIT, "home", "reader-lib")
        check(len(kit.READER_LIBS) == len({r for r, _ in kit.READER_LIBS}) and all(len(s) == 64 for _, s in kit.READER_LIBS),
              f"{len(kit.READER_LIBS)} pinned reader files, each with a sha256")
        if os.path.isdir(lib):
            bad = [r for r, sha in kit.READER_LIBS
                   if not os.path.isfile(os.path.join(lib, r)) or
                   hashlib.sha256(open(os.path.join(lib, r), "rb").read()).hexdigest() != sha]
            check(not bad, f"installed reader library matches the pinned checksums {bad or ''}")
            st, h, body = get("/reader-lib/view.js")
            check(st == 200 and "javascript" in h.get("Content-type", h.get("Content-Type", "")), "/reader-lib/view.js served as JavaScript")
        else:
            print("skip installed-library checks: run ./kit.sh setup-reader")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
    print(f"\n{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    sys.exit(1 if FAILS else 0)

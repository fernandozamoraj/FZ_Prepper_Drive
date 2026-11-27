#!/usr/bin/env python3
"""tests/test_family.py (offline prepper kit v1.16.0): the Family page's lock (home/family-crypto.js) and its server
side (bin/intranet.py /family.json, /family/forget).

    python3 tests/test_family.py        (needs node for the JavaScript half; uses a temporary folder, not family/)

1. A Python copy of the "fz-family-1" format (hashlib/hmac only) opens what the JavaScript locks, and the other way
   round, with both the fast (crypto.subtle) and the plain-JavaScript PBKDF2 (what phones on http:// use).
2. A wrong password, a changed byte, or another file's tag is refused.
3. The server: first setup only from this computer; later saves need the password's write key and the newest rev;
   5 earlier saves kept; a phone can save with the key but can't start over; "start over" renames, never deletes.
"""
import base64
import hashlib
import hmac
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unicodedata
import urllib.request

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(KIT, "home", "family-crypto.js")
FAILS = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


# ---- Python copy of the format -----------------------------------------------------------------------------------------
def H(k, m):
    return hmac.new(k, m, "sha256").digest()


def ring(pw, salt, it):
    master = hashlib.pbkdf2_hmac("sha256", unicodedata.normalize("NFC", pw).encode(), salt, it)
    write = H(master, b"fz-family write")
    return {"enc": H(master, b"fz-family enc"), "mac": H(master, b"fz-family mac"), "write": write.hex(),
            "verifier": hashlib.sha256(write).hexdigest(), "salt": salt, "iter": it}


def stream(k, nonce, data):
    ks = b"".join(H(k, nonce + i.to_bytes(4, "big")) for i in range((len(data) + 31) // 32))
    return bytes(a ^ b for a, b in zip(data, ks))


def tag(r, nonce, ct):
    return H(r["mac"], b"fz-family-1" + r["iter"].to_bytes(4, "big") + r["salt"] + nonce + ct)


def py_open(pw, f):
    r = ring(pw, base64.b64decode(f["salt"]), f["iter"])
    nonce, ct = base64.b64decode(f["nonce"]), base64.b64decode(f["ct"])
    if not hmac.compare_digest(tag(r, nonce, ct), base64.b64decode(f["tag"])):
        raise ValueError("wrong password")
    return json.loads(stream(r["enc"], nonce, ct)), r


def py_seal(pw, obj, it=100000):
    r, nonce = ring(pw, os.urandom(16), it), os.urandom(16)
    ct = stream(r["enc"], nonce, json.dumps(obj).encode())
    e = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return {"format": "fz-family-1", "iter": it, "salt": e(r["salt"]), "nonce": e(nonce), "ct": e(ct),
            "tag": e(tag(r, nonce, ct)), "verifier": r["verifier"]}, r


NODE = r"""
require(process.argv[1]);
const C = globalThis.fzFamilyCrypto, [mode, pw, arg] = process.argv.slice(2);
(async () => {
  if (mode.endsWith('plainjs')) { globalThis.crypto.subtle.importKey = () => { throw new Error('no subtle'); }; }
  if (mode.startsWith('open')) { const o = await C.open(pw, JSON.parse(arg)); console.log(JSON.stringify({data: o.data, write: o.ring.write})); return; }
  const r = await C.newRing(pw, 100000);
  const f = C.seal(r, JSON.parse(arg));
  console.log(JSON.stringify({file: f, write: r.write, reopened: C.openWithRing(r, f)}));
})().catch(e => { console.log(JSON.stringify({error: e.message, wrong: !!e.wrongPassword})); });
"""


def node(*args):
    out = subprocess.run(["node", "-e", NODE, JS, *args], capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout.strip().splitlines()[-1])


def crypto_tests():
    data = {"schema": 1, "contacts": [{"name": "Tía Rosa ñ 👵", "phone": "+1 555 0100"}], "notes": "x" * 5000}
    for mode in ("subtle", "plainjs"):
        j = node(mode, "correct horse battery", json.dumps(data))
        got, r = py_open("correct horse battery", j["file"])
        check(got == data, f"JS ({mode}) locks, Python opens: same contents (unicode, emoji, 5 KB)")
        check(r["write"] == j["write"] and r["verifier"] == j["file"]["verifier"], f"JS ({mode}) write key/verifier match Python")
        check(j["reopened"] == data, f"JS ({mode}) openWithRing re-reads its own save")
    f, r = py_seal("pässwörd ü", data)
    j = node("open-plainjs", "pässwörd ü", json.dumps(f))
    check(j.get("data") == data and j.get("write") == r["write"], "Python locks, plain JS opens (non-ASCII password)")
    j = node("open-subtle", "wrong one", json.dumps(f))
    check(j.get("wrong") is True, "wrong password refused")
    bad = dict(f, ct=base64.b64encode(bytes([base64.b64decode(f["ct"])[0] ^ 1]) + base64.b64decode(f["ct"])[1:]).decode())
    check(node("open-subtle", "pässwörd ü", json.dumps(bad)).get("wrong") is True, "one changed byte is refused (tag)")
    f2, _ = py_seal("pässwörd ü", data)
    check(node("open-subtle", "pässwörd ü", json.dumps(dict(f, tag=f2["tag"]))).get("wrong") is True, "another file's tag is refused")
    check(f["ct"] != f2["ct"], "same contents and password lock differently each time (new salt/nonce)")


# ---- Server ----------------------------------------------------------------------------------------------------------
def server_tests():
    sys.path.insert(0, os.path.join(KIT, "bin"))
    import intranet
    tmp = tempfile.mkdtemp(prefix="family-test-")
    intranet.FAMILY_DIR = tmp
    intranet.FAMILY_FILE = os.path.join(tmp, "family.enc.json")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), intranet.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    remote = {"on": False}
    real_is_local = intranet.Handler.is_local
    intranet.Handler.is_local = lambda self: False if remote["on"] else real_is_local(self)

    def req(path, body=None, origin=None):
        r = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                   headers={"Content-Type": "application/json", **({"Origin": origin} if origin else {})})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        st, d = req("/family.json")
        check(st == 200 and d["exists"] is False and d["local"] is True, "empty: exists=false, local=true")
        with urllib.request.urlopen(base + "/family") as r:
            check(b"Family emergency page" in r.read(), "/family serves the page")
        with urllib.request.urlopen(base + "/family-crypto.js") as r:
            check(b"fzFamilyCrypto" in r.read(), "/family-crypto.js is served")
        f1, r1 = py_seal("pw one long", {"n": 1})
        remote["on"] = True
        check(req("/family.json", {"file": f1, "rev": 0})[0] == 403, "first setup from a phone refused")
        remote["on"] = False
        check(req("/family.json", {"file": f1, "rev": 0}, origin="http://evil.example")[0] == 403, "other web site refused")
        check(req("/family.json", {"file": dict(f1, extra=1), "rev": 0})[0] == 400, "malformed file refused")
        st, d = req("/family.json", {"file": f1, "rev": 0})
        check(st == 200 and d["rev"] == 1, "first setup on this computer: rev 1")
        st, d = req("/family.json")
        check(d["exists"] and "verifier" not in d["file"] and d["rev"] == 1, "GET returns the file without the verifier")
        check(py_open("pw one long", d["file"])[0] == {"n": 1}, "what GET returns opens with the password")
        f2, r2 = py_seal("pw one long", {"n": 2})
        check(req("/family.json", {"file": f2, "rev": 1})[0] == 403, "save without the write key refused")
        check(req("/family.json", {"file": f2, "rev": 1, "proof": r2["write"]})[0] == 403,
              "save with another password's key refused (no overwriting by a stranger)")
        check(req("/family.json", {"file": f2, "rev": 0, "proof": r1["write"]})[0] == 409, "save from a stale copy: 409")
        remote["on"] = True
        st, d = req("/family.json", {"file": f2, "rev": 1, "proof": r1["write"]})
        check(st == 200 and d["rev"] == 2, "a phone with the password's key can save")
        check(req("/family/forget", {})[0] == 403, "a phone can't start over")
        remote["on"] = False
        codes = []
        for n in range(3, 10):  # 7 more saves to fill the backups; the phone's save above set r2's verifier
            f, _ = py_seal("x", {"n": n})
            f["verifier"] = r2["verifier"]
            codes.append(req("/family.json", {"file": f, "rev": n - 1, "proof": r2["write"]})[0])
        check(codes == [200] * 7, f"7 more saves with the current key: {codes}")
        check(req("/family.json", {"file": f, "rev": 9, "proof": r1["write"]})[0] == 403,
              "the old key stops working once a save re-locked with another password")
        kept = sorted(x for x in os.listdir(tmp) if x.startswith("family.enc.json."))
        check(kept == [f"family.enc.json.{i}" for i in range(1, 6)], f"5 earlier saves kept: {kept}")
        with open(os.path.join(tmp, "family.enc.json.1")) as fh:
            check(json.load(fh)["rev"] == 8, "newest backup is the save before the current one")
        st, d = req("/family/forget", {})
        check(st == 200 and d["exists"] is False, "start over on this computer")
        check(any(x.startswith("family.enc.json.forgotten-") for x in os.listdir(tmp)), "the old file was renamed, not deleted")
        check(req("/settings/rescan", {})[0] == 200, "Settings page POST still works")
    finally:
        srv.shutdown()
        shutil.rmtree(tmp)


if __name__ == "__main__":
    crypto_tests()
    server_tests()
    print(f"\n{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    sys.exit(1 if FAILS else 0)

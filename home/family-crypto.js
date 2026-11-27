/* family-crypto.js (offline prepper kit v1.17.0): locks and unlocks the Family page (home/family.html).
   Everything is encrypted in the browser; the kit's server only ever stores the locked file (family/family.enc.json)
   and never sees the password or the contents.

   Why not just AES from the browser (crypto.subtle)? Browsers turn crypto.subtle off on plain http:// pages that
   aren't localhost, which is exactly how phones on the Wi-Fi open the kit (http://192.168...). So the scheme is built
   from HMAC-SHA256 only, which is small enough to write here in plain JavaScript, and crypto.subtle is used where it
   exists just to make the slow step (PBKDF2) faster. Both give identical results (tests/test_family.py checks this
   against Python's hashlib/hmac).

   Format "fz-family-1":
     master  = PBKDF2-HMAC-SHA256(password, salt[16], iter) -> 32 bytes
     encKey  = HMAC(master, "fz-family enc")   macKey = HMAC(master, "fz-family mac")   writeKey = HMAC(master, "fz-family write")
     stream  = HMAC(encKey, nonce[16] || uint32be(0)) || HMAC(encKey, nonce || uint32be(1)) || ...   (HMAC as a PRF in counter mode)
     ct      = utf8(JSON) XOR stream
     tag     = HMAC(macKey, "fz-family-1" || uint32be(iter) || salt || nonce || ct)   (encrypt-then-MAC)
     verifier= SHA256(writeKey)  (the server keeps it; a save must send writeKey, so only someone who knows the password
               can change or replace the file, and phones can edit too)
   File: {format, iter, salt, nonce, ct, tag, verifier} with byte strings in base64. A new random nonce on every save. */
(function (root) {
  'use strict';
  const FORMAT = 'fz-family-1', ITER = 600000;  // OWASP's PBKDF2-SHA256 figure; ~0.3 s on a laptop, a second or two on a phone
  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
    0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
  const IV = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const W = new Uint32Array(64);

  // One SHA-256 block: out = compress(st, 16 words of block)
  function compress(st, blk, out) {
    for (let i = 0; i < 16; i++) W[i] = blk[i];
    for (let i = 16; i < 64; i++) {
      const a = W[i - 15], b = W[i - 2];
      const s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3);
      const s1 = ((b >>> 17) | (b << 15)) ^ ((b >>> 19) | (b << 13)) ^ (b >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) | 0;
    }
    let a = st[0], b = st[1], c = st[2], d = st[3], e = st[4], f = st[5], g = st[6], h = st[7];
    for (let i = 0; i < 64; i++) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const t1 = (h + S1 + ((e & f) ^ (~e & g)) + K[i] + W[i]) | 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    out[0] = st[0] + a; out[1] = st[1] + b; out[2] = st[2] + c; out[3] = st[3] + d;
    out[4] = st[4] + e; out[5] = st[5] + f; out[6] = st[6] + g; out[7] = st[7] + h;
    return out;
  }

  const words = (bytes, off) => ((bytes[off] << 24) | (bytes[off + 1] << 16) | (bytes[off + 2] << 8) | bytes[off + 3]) >>> 0;
  function toBytes(st) {
    const o = new Uint8Array(32);
    for (let i = 0; i < 8; i++) { o[4 * i] = st[i] >>> 24; o[4 * i + 1] = st[i] >>> 16; o[4 * i + 2] = st[i] >>> 8; o[4 * i + 3] = st[i]; }
    return o;
  }
  function concat(...parts) {
    const o = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
    let n = 0;
    for (const p of parts) { o.set(p, n); n += p.length; }
    return o;
  }
  const u32 = n => new Uint8Array([n >>> 24, n >>> 16, n >>> 8, n]);
  const utf8 = s => new TextEncoder().encode(s);

  function sha256(msg, st0 = IV, prefixLen = 0) {
    const len = msg.length, total = len + prefixLen;
    const padded = new Uint8Array(((len + 9 + 63) >> 6) << 6);
    padded.set(msg); padded[len] = 0x80;
    const bits = total * 8, n = padded.length;
    padded[n - 5] = Math.floor(bits / 2 ** 32); padded[n - 4] = bits >>> 24; padded[n - 3] = bits >>> 16;
    padded[n - 2] = bits >>> 8; padded[n - 1] = bits;
    let st = new Uint32Array(st0);
    const blk = new Uint32Array(16);
    for (let off = 0; off < n; off += 64) {
      for (let i = 0; i < 16; i++) blk[i] = words(padded, off + 4 * i);
      compress(st, blk, st);
    }
    return toBytes(st);
  }

  // HMAC-SHA256 with the key's inner/outer states worked out once (PBKDF2 calls it hundreds of thousands of times)
  function hmacKey(key) {
    if (key.length > 64) key = sha256(key);
    const pad = (x) => { const b = new Uint8Array(64); b.set(key); for (let i = 0; i < 64; i++) b[i] ^= x; return b; };
    const st = (block) => { const w = new Uint32Array(16); for (let i = 0; i < 16; i++) w[i] = words(block, 4 * i); return compress(IV, w, new Uint32Array(8)); };
    return {inner: st(pad(0x36)), outer: st(pad(0x5c))};
  }
  function hmac(key, msg) {
    const k = key.inner ? key : hmacKey(key);
    return sha256(sha256(msg, k.inner, 64), k.outer, 64);
  }

  function pbkdf2JS(pw, salt, iter) {
    const k = hmacKey(pw);
    let u = hmac(k, concat(salt, u32(1)));
    const t = new Uint32Array(8), blk = new Uint32Array(16), mid = new Uint32Array(8), out = new Uint32Array(8);
    for (let i = 0; i < 8; i++) t[i] = out[i] = words(u, 4 * i);
    blk[8] = 0x80000000; blk[15] = (64 + 32) * 8;  // padding for a 32-byte message after the 64-byte key block
    for (let n = 1; n < iter; n++) {
      for (let i = 0; i < 8; i++) blk[i] = out[i];
      compress(k.inner, blk, mid);
      for (let i = 0; i < 8; i++) blk[i] = mid[i];
      compress(k.outer, blk, out);
      for (let i = 0; i < 8; i++) t[i] ^= out[i];
    }
    return toBytes(t);
  }

  const subtle = root.crypto && root.crypto.subtle && (root.isSecureContext !== false) ? root.crypto.subtle : null;
  async function pbkdf2(pw, salt, iter) {
    if (subtle) {
      try {
        const key = await subtle.importKey('raw', pw, 'PBKDF2', false, ['deriveBits']);
        return new Uint8Array(await subtle.deriveBits({name: 'PBKDF2', hash: 'SHA-256', salt, iterations: iter}, key, 256));
      } catch (_) { /* fall through to plain JavaScript */ }
    }
    await new Promise(r => setTimeout(r, 30));  // let the page show "Unlocking…" first
    return pbkdf2JS(pw, salt, iter);
  }

  function stream(encKey, nonce, data) {
    const k = hmacKey(encKey), out = new Uint8Array(data.length);
    for (let off = 0, i = 0; off < data.length; off += 32, i++) {
      const ks = hmac(k, concat(nonce, u32(i)));
      for (let j = 0; j < 32 && off + j < data.length; j++) out[off + j] = data[off + j] ^ ks[j];
    }
    return out;
  }

  const b64 = bytes => { let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); };
  const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
  const hex = bytes => Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  const random = n => root.crypto.getRandomValues(new Uint8Array(n));  // allowed on http:// pages too
  function same(a, b) { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i]; return d === 0; }

  // A key ring: what an unlocked page keeps in memory so it can save again without asking for the password
  async function keys(password, salt, iter) {
    const master = await pbkdf2(utf8(password.normalize('NFC')), salt, iter);
    const write = hmac(master, utf8('fz-family write'));
    return {salt, iter, enc: hmac(master, utf8('fz-family enc')), mac: hmac(master, utf8('fz-family mac')),
            write: hex(write), verifier: hex(sha256(write))};
  }
  const tagOf = (ring, nonce, ct) => hmac(ring.mac, concat(utf8(FORMAT), u32(ring.iter), ring.salt, nonce, ct));

  function seal(ring, obj) {
    const nonce = random(16), ct = stream(ring.enc, nonce, utf8(JSON.stringify(obj)));
    return {format: FORMAT, iter: ring.iter, salt: b64(ring.salt), nonce: b64(nonce), ct: b64(ct),
            tag: b64(tagOf(ring, nonce, ct)), verifier: ring.verifier};
  }

  async function open(password, file) {
    if (!file || file.format !== FORMAT) throw new Error('This file is not a Family page the kit knows how to open.');
    const ring = await keys(password, unb64(file.salt), file.iter);
    const nonce = unb64(file.nonce), ct = unb64(file.ct);
    if (!same(tagOf(ring, nonce, ct), unb64(file.tag))) {
      const e = new Error('Wrong password.'); e.wrongPassword = true; throw e;
    }
    return {ring, data: JSON.parse(new TextDecoder().decode(stream(ring.enc, nonce, ct)))};
  }

  const newRing = (password, iter = ITER) => keys(password, random(16), iter);

  // Re-read a saved file with keys already in memory (no password, no PBKDF2). Fails if it was re-locked with another
  // password in the meantime (different salt), or changed by someone without these keys.
  function openWithRing(ring, file) {
    if (!file || file.format !== FORMAT || file.iter !== ring.iter || !same(unb64(file.salt), ring.salt))
      throw new Error('The Family page was locked with a different password since you opened it. Lock it and unlock again.');
    const nonce = unb64(file.nonce), ct = unb64(file.ct);
    if (!same(tagOf(ring, nonce, ct), unb64(file.tag))) throw new Error('The saved file does not match these keys.');
    return JSON.parse(new TextDecoder().decode(stream(ring.enc, nonce, ct)));
  }

  root.fzFamilyCrypto = {newRing, seal, open, openWithRing, ITER, FORMAT, fast: !!subtle,
    _test: {sha256, hmac, pbkdf2JS, keys, hex, b64, unb64}};
})(typeof window !== 'undefined' ? window : globalThis);

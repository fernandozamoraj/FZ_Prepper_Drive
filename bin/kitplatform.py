"""kitplatform (offline prepper kit v1.11.0): find this computer's programs and start the library server.

The kit carries portable programs for each system in runtime/:
  runtime/win-x64/   Windows 64-bit (also runs on Windows on ARM through emulation)
  runtime/mac-arm64/ Macs with Apple Silicon (M1 and later)
  runtime/mac-x64/   Intel Macs
each with python/, java/ and kiwix/. If a program isn't there (e.g. the Mac copy without runtime/),
the one installed on the computer is used instead.
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOWS = sys.platform == "win32"
EXE = ".exe" if WINDOWS else ""


def runtime_dir():
    if WINDOWS:
        return os.path.join(KIT, "runtime", "win-x64")
    if sys.platform == "darwin":
        arch = "mac-arm64" if platform.machine() == "arm64" else "mac-x64"
        return os.path.join(KIT, "runtime", arch)
    return None


def _first(*paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


def find_java():
    rt = runtime_dir()
    return _first(rt and os.path.join(rt, "java", "bin", "java" + EXE),
                  "/opt/homebrew/opt/openjdk@21/bin/java", "/usr/local/opt/openjdk@21/bin/java",
                  shutil.which("java"))


def find_kiwix_serve():
    rt = runtime_dir()
    return _first(rt and os.path.join(rt, "kiwix", "kiwix-serve" + EXE),
                  os.path.join(KIT, "bin", "kiwix-serve" + EXE), shutil.which("kiwix-serve"))


def visible_files(folder, ext):
    """Files with this extension, skipping macOS '._' shadow files that appear on exFAT drives."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(f for f in names if f.endswith(ext) and not f.startswith("._") and not f.startswith("."))


def _no_space_dir():
    """A folder whose path has no spaces: kiwix-serve's resource list (KIWIX_SERVE_CUSTOMIZED_RESOURCES)
    cuts paths at the first space, so on e.g. C:\\Users\\John Smith\\... the header files are copied here."""
    home = os.path.join(KIT, "home")
    if " " not in home:
        return home
    for base in (tempfile.gettempdir(), os.environ.get("PUBLIC", ""), "C:\\Users\\Public", "/tmp"):
        if base and " " not in base and os.path.isdir(base):
            d = os.path.join(base, "prepper-kit")
            os.makedirs(d, exist_ok=True)
            for f in ("nav.js", "viewer_settings.js"):
                shutil.copyfile(os.path.join(home, f), os.path.join(d, f))
            return d
    return home


def library_command(port):
    """kiwix-serve command + environment for all libraries in kiwix/, with the kit's home page and header bar.
    Returns (cmd, env) or (None, reason)."""
    exe = find_kiwix_serve()
    if not exe:
        return None, "kiwix-serve not found"
    folder = os.path.join(KIT, "kiwix")
    zims = [os.path.join(folder, f) for f in visible_files(folder, ".zim")
            if os.path.getsize(os.path.join(folder, f)) > 1_000_000 or f.startswith("bible_")]
    if not zims:
        return None, "no libraries in kiwix/"
    cmd = [exe, "--port", str(port)]
    index = os.path.join(KIT, "home", "index.html")
    if os.path.isfile(index):
        cmd += ["--customIndex", index]
    env = dict(os.environ)
    home = os.path.join(KIT, "home")
    if os.path.isfile(os.path.join(home, "nav.js")) and os.path.isfile(os.path.join(home, "viewer_settings.js")):
        d = _no_space_dir()
        lst = os.path.join(tempfile.gettempdir(), "prepper-kit-kiwix-resources.txt")
        with open(lst, "w", encoding="utf-8") as f:
            f.write(f"/nav.js application/javascript {os.path.join(d, 'nav.js')}\n")
            f.write(f"/viewer_settings.js application/javascript {os.path.join(d, 'viewer_settings.js')}\n")
        env["KIWIX_SERVE_CUSTOMIZED_RESOURCES"] = lst
    return cmd + zims, env


def start_quietly(cmd, cwd=None, env=None, log=None):
    """Start a background program. On Windows it shares this console window, so closing the window
    (or Ctrl+C) stops it too; on macOS/Linux the caller stops it explicitly."""
    out = open(log, "ab") if log else subprocess.DEVNULL
    kw = {} if WINDOWS else {"start_new_session": True}
    return subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, **kw)


def stop(proc, timeout=20):
    """Ask a program to stop (SIGTERM / TerminateProcess), then force it after `timeout` seconds.
    SIGTERM, not SIGINT: a program started from a background shell ignores SIGINT. serve-maps.py
    handles SIGTERM by stopping its router first, so it gets time for that."""
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        proc.kill()

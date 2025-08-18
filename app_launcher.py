#!/usr/bin/env python3
import atexit
import os
import signal
import subprocess
import sys
import time
import webbrowser
from urllib.request import urlopen

# --- Config ---
HTTP_PORT = 8081
# Demo stations (match your earlier coords & IDs)
SOURCES = [
    '127.0.0.1:18001@XX.JINJ1..BHZ@-31.9619,115.9488',
    '127.0.0.1:18002@XX.JINJ2..BHZ@-31.9389,115.9670',
    '127.0.0.1:18003@XX.JINJ3..BHZ@-31.9200,115.9900',
]
METRIC = "rms"  # or "mean"
RECEIVER_RECLEN = "4096"  # keep in sync with your receiver default

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

procs = []

def spawn(cmd, **kw):
    print(">", " ".join(cmd))
    p = subprocess.Popen(cmd, cwd=ROOT, **kw)
    procs.append(p)
    return p

def cleanup():
    # try gentle first
    for p in procs:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass
    # wait a moment, then force kill any stragglers
    deadline = time.time() + 3
    while time.time() < deadline:
        alive = [p for p in procs if p.poll() is None]
        if not alive:
            break
        time.sleep(0.1)
    for p in procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass

atexit.register(cleanup)

def wait_http(port, path="/live", timeout=10):
    url = f"http://127.0.0.1:{port}{path}"
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def main():
    # 1) Start the multi-sender (uses its own defaults: 3 demo stations on 18001–18003)
    sender_cmd = [PY, "seedlink_multi_sender.py"]
    spawn(sender_cmd)

    # 2) Start the receiver (serves RMS_station_viewer.html at '/')
    receiver_cmd = [
        PY, "seedlink_multi_receiver.py",
        "--http-port", str(HTTP_PORT),
        "--metric", METRIC,
        "--reclen", RECEIVER_RECLEN,
    ]
    for s in SOURCES:
        receiver_cmd += ["--source", s]
    spawn(receiver_cmd)

    # 3) Wait for /live, then open browser
    print(f"[launcher] Waiting for http://127.0.0.1:{HTTP_PORT}/live ...")
    if wait_http(HTTP_PORT, "/live", timeout=20):
        url = f"http://127.0.0.1:{HTTP_PORT}/"
        print(f"[launcher] Opening {url}")
        webbrowser.open(url)
    else:
        print(f"[launcher] Warning: /live did not respond in time. You can still try opening http://127.0.0.1:{HTTP_PORT}/ manually.")

    # 4) Keep the launcher alive; forward Ctrl+C to cleanup
    try:
        while True:
            # if either child exits unexpectedly, quit
            for p in procs:
                if p.poll() is not None:
                    print("[launcher] A child process exited; stopping...")
                    return
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[launcher] Ctrl-C received, shutting down...")

if __name__ == "__main__":
    # Handle Ctrl-C / SIGTERM gracefully
    signal.signal(signal.SIGINT, lambda *_: None)
    signal.signal(signal.SIGTERM, lambda *_: None)
    main()

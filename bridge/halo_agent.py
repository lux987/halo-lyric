"""HaloBridge Agent: one process that both serves the lyric endpoint and
supervises Folia.

Why one process: the previous split (watch_folia.py + halo_bridge.py) had to
kill the bridge when Folia closed, and on Windows that kill cannot run any
cleanup code, so the speaker kept the last lyric line instead of going back to
its clock screen. Here the supervisor and the HID writer are the same process,
so the restore happens before anything exits.

Behaviour:
  - HTTP endpoint 127.0.0.1:8765/state is always up (the Folia mod posts here)
  - while Folia runs, incoming lines are written to the speaker
  - when Folia exits, the screen is put back to its idle (clock) face
  - a second instance refuses to start (port already in use)
"""

import os
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer

import halo_bridge as hb

FOLIA = "Folia.exe"
CREATE_NO_WINDOW = 0x08000000
POLL_SECONDS = 2.0


def folia_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {FOLIA}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
        )
        return FOLIA.lower() in (out.stdout or "").lower()
    except Exception:
        return False


def serve() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", hb.PORT), hb.Handler)
    server.serve_forever()


def main() -> None:
    try:
        threading.Thread(target=serve, daemon=True).start()
    except OSError:
        print("HaloBridge 已在运行，本次启动取消")
        return

    hb.SCREEN._open()
    was_running = False
    idle_sent = False

    while True:
        try:
            running = folia_running()
            if running and not was_running:
                idle_sent = False
            if was_running and not running and not idle_sent:
                hb.SCREEN.restore()
                idle_sent = True
            if not running and not idle_sent:
                hb.SCREEN.restore()
                idle_sent = True
            was_running = running
            time.sleep(POLL_SECONDS)
        except Exception:
            time.sleep(3)


if __name__ == "__main__":
    main()

"""Watch for Folia and run the HaloBridge only while Folia is running.

Started at logon with pythonw.exe (no console window). Every couple of seconds:
  - Folia is running and the bridge is not -> start halo_bridge.py hidden
  - Folia is gone -> ask the bridge to restore the screen, then stop it

On Windows, Popen.terminate() kills the process without running its cleanup, so
the screen restore is requested over HTTP before the kill.

The bridge is started with the venv's own pythonw.exe (absolute path), not
sys.executable, so the child always sees the venv's site-packages (hidapi).
"""

import json
import os
import subprocess
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, "halo_bridge.py")
PYTHONW = os.path.join(HERE, "venv", "Scripts", "pythonw.exe")
FOLIA = "Folia.exe"
CREATE_NO_WINDOW = 0x08000000
RESTORE_URL = "http://127.0.0.1:8765/restore"


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


def restore_screen() -> None:
    """Ask the bridge to put the speaker back to its idle screen."""
    try:
        req = urllib.request.Request(
            RESTORE_URL,
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3).read()
        time.sleep(0.3)
    except Exception:
        pass


def main() -> None:
    proc = None
    while True:
        try:
            running = folia_running()
            if running:
                if proc is None or proc.poll() is not None:
                    proc = subprocess.Popen(
                        [PYTHONW, BRIDGE],
                        cwd=HERE,
                        creationflags=CREATE_NO_WINDOW,
                    )
            else:
                if proc is not None and proc.poll() is None:
                    restore_screen()
                    proc.terminate()
                    try:
                        proc.wait(5)
                    except Exception:
                        proc.kill()
                proc = None
            time.sleep(2)
        except Exception:
            time.sleep(3)


if __name__ == "__main__":
    main()

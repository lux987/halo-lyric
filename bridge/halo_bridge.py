"""HaloBridge: receive lyric lines from the Folia mod and push them to the
Halo PixelBar dot-matrix screen over USB HID.

Protocol reference: HaloPixelToolBox / HaloLyricSync (64-byte HID write packets).

Per-request parameters from the Folia mod:
    windowChars   glyphs per frame
    windowStart   which glyph the window starts at (progress-following)
    stepChars / frameMs   fallback scrolling when windowStart is absent
    entryEffect   typewriter | slide | blink | none
    layout        stretch | center | left | right

Entry animations run from the worker thread as a queue of (text, delay) frames,
so incoming lyric updates cannot cut them short.

Only one process may write to the screen at a time: close EDIFIER TempoHub while
this bridge runs, otherwise the two applications overwrite each other.
"""

import json
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import hid

PACKET_LEN = 64
VID = 0x2D99
PID = 0xA106
PORT = 8765
MAX_TEXT_BYTES = 50

LAYOUT_HEADER = bytes([0x2E, 0xAA, 0xEC, 0xEF, 0x00, 0x09, 0x01, 0xF0, 0xB4, 0xC8, 0x00, 0x02, 0x00])
LAYOUTS = {
    "left": bytes([0x00, 0xFF, 0xFC, 0x00]),
    "center": bytes([0x01, 0xFF, 0xFD, 0x00]),
    "right": bytes([0x02, 0xFF, 0xFE, 0x00]),
    "stretch": bytes([0x03, 0xFF, 0xFF, 0x00]),
    "scroll": bytes([0x01, 0xFF, 0xFE, 0x00]),
}

DEFAULTS = {
    "windowChars": 16,
    "stepChars": 1,
    "frameMs": 220,
    "layout": "stretch",
    "followProgress": True,
    "entryEffect": "typewriter",
}

UI_HEADER = bytes([0x2E, 0xAA, 0xEC, 0xEF, 0x00, 0x09, 0x02, 0xF0, 0xB4, 0xC8, 0x00, 0x01])
UI_MODES = {
    "clock": bytes([0x00, 0xFF, 0xFF, 0xFB, 0x00]),
    "game": bytes([0x01, 0xFF, 0xFF, 0xFC, 0x00]),
    "work": bytes([0x02, 0xFF, 0xFF, 0xFD, 0x00]),
    "read": bytes([0x03, 0xFF, 0xFF, 0xFE, 0x00]),
    "cats": bytes([0x04, 0xFF, 0xFF, 0xFF, 0x00]),
    "dogs": bytes([0x05, 0xFF, 0xFF, 0x00, 0x00]),
    "memes": bytes([0x06, 0xFF, 0xFF, 0x01, 0x00]),
    "cyber": bytes([0x07, 0xFF, 0xFF, 0x02, 0x00]),
    "waves": bytes([0x08, 0xFF, 0xFF, 0x03, 0x00]),
}

TYPE_STEP_MS = 55
SLIDE_STEP_MS = 45
BLINK_STEP_MS = 90


def _pad(data: bytes) -> bytes:
    if len(data) >= PACKET_LEN:
        return data[:PACKET_LEN]
    return data + bytes(PACKET_LEN - len(data))


def _checksum(raw: bytes) -> int:
    acc = 128
    for byte in raw:
        acc += byte + 2
    return acc % 256


def build_text(text: str, color: int = 0) -> bytes:
    raw = text.encode("utf-8")
    while len(raw) > MAX_TEXT_BYTES:
        text = text[:-1]
        raw = text.encode("utf-8")
    packet = bytearray([0x2E, 0xAA, 0xEC, 0xE8, color])
    packet.extend(struct.pack("<H", 1 + len(raw) + 1))
    packet.append(len(raw))
    packet.extend(raw)
    packet.append(_checksum(raw))
    return _pad(bytes(packet))


def build_layout(mode: str) -> bytes:
    return _pad(LAYOUT_HEADER + LAYOUTS.get(mode, LAYOUTS["stretch"]))


def build_ui_packet(mode: str = "clock") -> bytes:
    return _pad(UI_HEADER + UI_MODES.get(mode, UI_MODES["clock"]))


def build_frames(text: str, window: int, step: int) -> list:
    window = max(1, min(30, window))
    step = max(1, min(window, step))
    if len(text) <= window:
        return [text]
    frames = []
    start = 0
    while True:
        frames.append(text[start:start + window])
        if start + window >= len(text):
            break
        start += step
    return frames or [""]


def build_anim(text: str, window: int, effect: str, prev: str = "") -> list:
    """A short queue of (text, delay_ms) frames for the line transition."""
    if effect == "none" or not text:
        return []
    base = text[:window]
    frames = []
    if effect == "blink":
        frames.append(("", BLINK_STEP_MS))
        frames.append((base[: max(2, len(base) // 2)], BLINK_STEP_MS))
        frames.append(("", 60))
        frames.append((base, 60))
    elif effect == "double_blink":
        half = base[: max(2, len(base) // 2)]
        for _ in range(2):
            frames.append(("", 60))
            frames.append((half, 70))
        frames.append((base, 60))
    elif effect == "erase":
        old = (prev or "")[:window]
        while len(old) > 0:
            frames.append((old, 35))
            old = old[:-2]
        frames.append(("", 30))
        step = max(2, len(base) // 6)
        size = step
        while size < len(base):
            frames.append((base[:size], 35))
            size += step
        frames.append((base, 40))
    elif effect == "slide":
        start = max(0, len(text) - window)
        while True:
            frames.append((text[start:start + window], SLIDE_STEP_MS))
            if start == 0:
                break
            start = max(0, start - 4)
        frames.append((base, 50))
    else:  # typewriter
        step = max(2, len(base) // 7)
        size = step
        while size < len(base):
            frames.append((base[:size], TYPE_STEP_MS))
            size += step
        frames.append((base, 40))
    return frames


class Screen:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._dev = None
        self._layout = None
        self._line = None
        self._line_index = -2
        self._params = dict(DEFAULTS)
        self._frames = []
        self._index = 0
        self._last_shown = None
        self._next_at = 0.0
        self._anim = []
        self._anim_at = 0.0
        threading.Thread(target=self._loop, daemon=True).start()

    # ---------------------------------------------------------------- device
    def _open(self) -> bool:
        for info in hid.enumerate():
            if info.get("vendor_id") != VID or info.get("product_id") != PID:
                continue
            try:
                dev = hid.device()
                dev.open_path(info["path"])
            except Exception:
                continue
            try:
                if dev.write(_pad(bytes([0x2E, 0xAA, 0xEC, 0xE8, 0x00, 0x06, 0x00, 0x04]))) < 0:
                    dev.close()
                    continue
            except Exception:
                try:
                    dev.close()
                except Exception:
                    pass
                continue
            self._dev = dev
            self._layout = None
            return True
        return False

    def _write(self, packet: bytes) -> bool:
        if self._dev is None and not self._open():
            return False
        try:
            if self._dev.write(packet) < 0:
                raise OSError("hid write failed")
            return True
        except Exception:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
            return False

    def _ensure_layout(self, mode: str) -> None:
        if self._layout == mode:
            return
        if self._write(build_layout(mode)):
            self._layout = mode

    # ---------------------------------------------------------------- state
    def _frames_for(self, text: str, merged: dict, raw: dict) -> list:
        window = max(1, min(30, merged["windowChars"]))
        if len(text) <= window:
            return [text]
        try:
            start = int(raw.get("windowStart"))
        except (TypeError, ValueError):
            start = -1
        if start >= 0:
            start = max(0, min(start, len(text) - window))
            return [text[start:start + window]]
        return build_frames(text, window, merged["stepChars"])

    def show(self, text: str, params: dict) -> bool:
        params = params or {}
        with self._lock:
            merged = dict(DEFAULTS)
            merged.update({k: v for k, v in params.items() if k in DEFAULTS})
            try:
                merged["windowChars"] = int(merged["windowChars"])
                merged["stepChars"] = int(merged["stepChars"])
                merged["frameMs"] = int(merged["frameMs"])
            except (TypeError, ValueError):
                merged = dict(DEFAULTS)

            frames = self._frames_for(text, merged, params)
            prev_line = self._line or ""
            line_index = int(params.get('lineIndex', -1) or -1)
            new_line = text != self._line or line_index != self._line_index
            if not new_line and merged == self._params and frames == self._frames:
                return True

            self._params = merged
            self._line = text
            self._line_index = line_index
            self._frames = frames
            self._index = 0
            self._next_at = 0.0
            self._ensure_layout(merged["layout"])

            if new_line:
                self._anim = build_anim(
                    text, merged["windowChars"], merged["entryEffect"], prev_line
                )
                self._anim_at = 0.0
                if self._anim:
                    return True
            elif self._anim:
                # 动画还在排队：只更新窗口，别把它打断
                return True

            return self._render()

    def restore(self, mode: str = "clock") -> bool:
        """把屏幕切回原来的待机界面（默认时钟）。"""
        with self._lock:
            ok = self._write(build_ui_packet(mode))
            self._frames = []
            self._anim = []
            self._last_shown = None
            self._line = None
            self._line_index = -2
            return ok

    def _render(self) -> bool:
        frame = self._frames[self._index] if self._frames else ""
        if frame == self._last_shown:
            return True
        ok = self._write(build_text(frame))
        if ok:
            self._last_shown = frame
        return ok

    # ---------------------------------------------------------------- worker
    def _loop(self) -> None:
        while True:
            time.sleep(0.008)
            try:
                with self._lock:
                    now = time.monotonic() * 1000
                    if self._anim:
                        if now < self._anim_at:
                            continue
                        frame, delay = self._anim.pop(0)
                        if self._write(build_text(frame)):
                            self._last_shown = frame
                        self._anim_at = now + delay
                        if not self._anim:
                            self._render()
                        continue
                    if len(self._frames) <= 1:
                        continue
                    if now < self._next_at:
                        continue
                    self._index = (self._index + 1) % len(self._frames)
                    self._render()
                    self._next_at = now + max(60, self._params["frameMs"])
            except Exception:
                continue


SCREEN = Screen()


def compose(payload: dict) -> str:
    text = (payload.get("text") or "").strip()
    title = (payload.get("title") or "").strip()
    artist = (payload.get("artist") or "").strip()
    state = payload.get("state") or ""
    if not text:
        text = f"{title} - {artist}" if (title and artist) else (title or "Folia")
    if state == "paused":
        text = "II " + text
    return text


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/restore":
            ok = SCREEN.restore()
            self.send_response(200 if ok else 503)
            self.end_headers()
            self.wfile.write(b"ok" if ok else b"hid-unavailable")
            return
        if self.path != "/state":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}
        ok = SCREEN.show(compose(payload), payload)
        self.send_response(200 if ok else 503)
        self.end_headers()
        self.wfile.write(b"ok" if ok else b"hid-unavailable")

    def log_message(self, *args) -> None:  # silence default logging
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"HaloBridge listening on http://127.0.0.1:{PORT}/state")
    SCREEN._open()
    server.serve_forever()


def _install_exit_hook() -> None:
    import atexit
    import os
    import signal

    def _restore_and_exit(*_args):
        try:
            SCREEN.restore()
            time.sleep(0.3)
        except Exception:
            pass
        os._exit(0)

    try:
        signal.signal(signal.SIGTERM, _restore_and_exit)
        signal.signal(signal.SIGINT, _restore_and_exit)
    except Exception:
        pass
    atexit.register(lambda: SCREEN.restore())


if __name__ == "__main__":
    _install_exit_hook()
    main()

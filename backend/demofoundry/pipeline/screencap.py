"""Screen-capture capture path — record a real walkthrough instead of driving the app.

The browser/automation path (capture.py) needs the app to expose stable hooks.
Desktop apps mostly don't. This path sidesteps that entirely: it records the
screen with ffmpeg (gdigrab) while logging your real mouse clicks and optional
hotkey marks, then hands the rest of the pipeline the SAME contract capture.py
produces — (video_path, {step_id: ActionRecord}) — so narrate -> sync -> compose
run unchanged.

You drive your own app once; your clicks become the timeline anchors and the
zoom/highlight source. Windows-only for now (gdigrab + pynput).

Run standalone:
    python -m demofoundry.pipeline.screencap --out work --window "FunscriptForge"
    # walk through the app; press F9 at each new narration beat; Esc to stop.
Writes <out>/recording.mp4 and <out>/events.json.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..models import ActionRecord, Rect, Step


@dataclass
class CaptureGeometry:
    """Screen rect being recorded, in absolute desktop pixels. Clicks are logged
    in absolute coords and translated to video-local coords by subtracting the
    origin, so zoom/highlight land in the right place in the recording."""

    x: int
    y: int
    width: int
    height: int

    def to_local(self, sx: float, sy: float) -> tuple[float, float]:
        return (sx - self.x, sy - self.y)


def _even(n: int) -> int:
    return n - (n % 2)  # yuv420p needs even dimensions


def primary_monitor() -> CaptureGeometry:
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return CaptureGeometry(0, 0, _even(w), _even(h))


def window_geometry(title: str) -> CaptureGeometry | None:
    """Screen rect of a top-level window by (substring of) its title, or None."""
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()
    found: list[int] = []

    # Exact match first; fall back to substring scan over visible windows.
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        found.append(hwnd)
    else:
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _cb(h, _l):
            if not user32.IsWindowVisible(h):
                return True
            n = user32.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, buf, n + 1)
                if title.lower() in buf.value.lower():
                    found.append(h)
                    return False
            return True

        user32.EnumWindows(EnumProc(_cb), 0)

    if not found:
        return None
    rect = _RECT()
    user32.GetWindowRect(found[0], ctypes.byref(rect))
    return CaptureGeometry(
        rect.left, rect.top, _even(rect.right - rect.left), _even(rect.bottom - rect.top)
    )


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _ffmpeg_cmd(geo: CaptureGeometry, out: Path, fps: int) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-f", "gdigrab", "-framerate", str(fps),
        "-offset_x", str(geo.x), "-offset_y", str(geo.y),
        "-video_size", f"{geo.width}x{geo.height}",
        "-i", "desktop",
        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
        str(out),
    ]


def resolve_geometry(
    window_title: str | None = None, geometry: CaptureGeometry | None = None
) -> CaptureGeometry:
    """Pick the capture rect: explicit geometry > named window > primary monitor."""
    if geometry is not None:
        return geometry
    if window_title:
        geo = window_geometry(window_title)
        if geo is None:
            raise RuntimeError(f"No visible window matching {window_title!r}.")
        return geo
    return primary_monitor()


class Recorder:
    """A start/stop screen-recording session the web layer can drive.

    Unlike `record()` (which blocks until Esc, for the CLI), this exposes
    start(), status(), and stop() so an HTTP endpoint can begin a recording,
    poll it, and end it on a button press — recording the screen with gdigrab
    (video only, no audio) while a pynput hook logs clicks + F9 marks.
    """

    def __init__(
        self,
        out_dir: Path,
        geometry: CaptureGeometry,
        fps: int = 15,
        mark_key: str = "f9",
    ) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.video = self.out_dir / "recording.mp4"
        self.geo = geometry
        self.fps = fps
        self.mark_key = mark_key
        self.clicks: list[dict] = []
        self.marks: list[float] = []
        self._proc: subprocess.Popen | None = None
        self._ml = None
        self._kl = None
        self._t0: float | None = None
        self._duration = 0.0
        self._stopped = False
        import threading

        self.esc_event = threading.Event()  # set if the user hits Esc

    def start(self) -> None:
        from pynput import keyboard, mouse

        self._proc = subprocess.Popen(
            _ffmpeg_cmd(self.geo, self.video, self.fps),
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)  # let gdigrab spin up before the clock starts
        self._t0 = time.monotonic()
        self._ml = mouse.Listener(on_click=self._on_click)
        self._kl = keyboard.Listener(on_press=self._on_press)
        self._ml.start()
        self._kl.start()

    def _now(self) -> float:
        return (time.monotonic() - self._t0) if self._t0 is not None else 0.0

    def _on_click(self, x, y, button, pressed) -> None:
        if pressed and self._t0 is not None:
            lx, ly = self.geo.to_local(x, y)
            self.clicks.append({"t": self._now(), "x": lx, "y": ly})

    def _on_press(self, key) -> None:
        from pynput import keyboard

        name = getattr(key, "char", None) or getattr(key, "name", None)
        if name == self.mark_key:
            self.mark()
        elif key == keyboard.Key.esc:
            self.esc_event.set()

    def mark(self) -> float:
        """Drop a scene mark at the current time (F9 or an API call). Returns it."""
        t = self._now()
        self.marks.append(t)
        return t

    def status(self) -> dict:
        return {
            "recording": self._proc is not None and not self._stopped,
            "elapsed": round(self._now(), 2),
            "clicks": len(self.clicks),
            "marks": len(self.marks),
            "esc": self.esc_event.is_set(),
        }

    def events(self) -> dict:
        return {
            "duration": self._duration,
            "origin": [self.geo.x, self.geo.y],
            "size": [self.geo.width, self.geo.height],
            "clicks": self.clicks,
            "marks": self.marks,
            "video": str(self.video),
        }

    def stop(self) -> dict:
        """End the recording, finalize the file, write events.json, return it."""
        if self._stopped:
            return self.events()
        self._duration = self._now()
        if self._ml:
            self._ml.stop()
        if self._kl:
            self._kl.stop()
        # Ask ffmpeg to finalize cleanly (q on stdin), then fall back to terminate.
        if self._proc:
            try:
                self._proc.stdin.write(b"q")
                self._proc.stdin.flush()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    self._proc.kill()
        self._faststart()
        self._stopped = True
        ev = self.events()
        (self.out_dir / "events.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
        return ev

    def _faststart(self) -> None:
        """Remux so the moov atom is at the front — lets a browser <video> seek
        immediately instead of waiting for the whole file. A fast -c copy pass."""
        if not self.video.exists():
            return
        tmp = self.video.with_suffix(".faststart.mp4")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(self.video), "-c", "copy",
                 "-movflags", "+faststart", str(tmp)],
                check=True, capture_output=True,
            )
            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(self.video)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)  # keep the original on failure


def record(
    out_dir: Path,
    window_title: str | None = None,
    geometry: CaptureGeometry | None = None,
    fps: int = 15,
    mark_key: str = "f9",
    verbose: bool = True,
) -> dict:
    """CLI recorder: record until Esc, logging clicks + F9 marks. Returns events."""
    geo = resolve_geometry(window_title, geometry)
    if verbose:
        print(f"[screencap] recording {geo.width}x{geo.height} at ({geo.x},{geo.y})")
        print(f"[screencap]  - press {mark_key.upper()} at each new narration beat")
        print("[screencap]  - press Esc to stop")
    rec = Recorder(out_dir, geo, fps, mark_key)
    rec.start()
    rec.esc_event.wait()  # block until the user presses Esc
    events = rec.stop()
    if verbose:
        print(f"[screencap] done: {events['duration']:.1f}s, {len(events['clicks'])} "
              f"clicks, {len(events['marks'])} marks -> {events['video']}")
    return events


def to_records(events: dict, steps: list[Step], anchor: str = "marks") -> dict[str, ActionRecord]:
    """Turn recorded events + the script into per-step ActionRecords.

    The anchor times are the boundaries *between* scenes: scene 1 runs from 0 to
    the first boundary, scene 2 from the first to the second, and so on, with the
    last scene running to the end of the recording. So for N scenes you mark the
    N-1 transitions (the first scene starts at the top automatically).

    `anchor`="marks" uses the F9 marks; "clicks" uses click times as a rough
    auto-split. click_xy is the first click inside each scene's slot, for
    zoom/highlight in post.
    """
    duration = float(events.get("duration", 0.0))
    clicks = events.get("clicks", [])
    raw = list(events.get("marks", [])) if anchor == "marks" else [c["t"] for c in clicks]
    bounds = sorted(t for t in raw if 0.0 < t < duration)

    records: dict[str, ActionRecord] = {}
    for i, step in enumerate(steps):
        start = 0.0 if i == 0 else (bounds[i - 1] if (i - 1) < len(bounds) else duration)
        end = bounds[i] if i < len(bounds) else duration
        if end < start:
            end = start  # ran out of marks: a zero-length tail scene (audio still plays)
        in_slot = [c for c in clicks if start <= c["t"] < end]
        click_xy = (in_slot[0]["x"], in_slot[0]["y"]) if in_slot else None
        target_rect = (
            Rect(click_xy[0] - 40, click_xy[1] - 16, 80, 32) if click_xy else None
        )
        records[step.id] = ActionRecord(
            step_id=step.id,
            started_at=start,
            ended_at=end,
            click_xy=click_xy,
            target_rect=target_rect,
            zoom_rect=None,        # screencap demos default to full-frame
            highlight_rect=target_rect,
            status="ok",
        )
    return records


def _load_steps(path: str) -> list[Step]:
    from .. import store

    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = doc["steps"] if isinstance(doc, dict) else doc
    return [
        store.step_from_dict({**s, "id": s.get("id") or f"s{i + 1}"})
        for i, s in enumerate(raw)
    ]


def _main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Record a screen walkthrough for DemoFoundry.")
    p.add_argument("--out", required=True, help="output dir for recording.mp4 + events.json")
    p.add_argument("--window", help="capture this window (substring of its title)")
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--steps", help="steps.json — if given, render a narrated demo after recording")
    p.add_argument("--voice", default="default", help="ElevenLabs voice id for narration")
    p.add_argument("--anchor", default="marks", choices=["marks", "clicks"],
                   help="use F9 marks (default) or clicks as scene boundaries")
    args = p.parse_args()

    events = record(Path(args.out), window_title=args.window, fps=args.fps)

    if args.steps:
        import asyncio

        from .. import render

        steps = _load_steps(args.steps)
        print(f"[render] {len(steps)} scenes — narrating + composing…")
        video, srt = asyncio.run(
            render.render_screencap_to_files(
                events, steps, Path(args.out), voice_id=args.voice, anchor=args.anchor,
                on_status=lambda s: print(f"[render] {s}"),
                on_progress=lambda m: print(f"[render]   {m}"),
            )
        )
        print(f"[render] demo: {video}")
        print(f"[render] srt:  {srt}")


if __name__ == "__main__":
    _main()

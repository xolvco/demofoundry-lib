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


def record(
    out_dir: Path,
    window_title: str | None = None,
    geometry: CaptureGeometry | None = None,
    fps: int = 15,
    mark_key: str = "f9",
    verbose: bool = True,
) -> dict:
    """Record the screen until Esc, logging clicks + F9 marks against the clock.

    Returns the events dict (also written to events.json) and writes recording.mp4.
    """
    from pynput import keyboard, mouse

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / "recording.mp4"

    geo = geometry
    if geo is None and window_title:
        geo = window_geometry(window_title)
        if geo is None:
            raise RuntimeError(f"No visible window matching {window_title!r}.")
    if geo is None:
        geo = primary_monitor()

    if verbose:
        print(f"[screencap] recording {geo.width}x{geo.height} at ({geo.x},{geo.y})")
        print(f"[screencap]  - press {mark_key.upper()} at each new narration beat")
        print("[screencap]  - press Esc to stop")

    proc = subprocess.Popen(
        _ffmpeg_cmd(geo, video, fps),
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)  # let gdigrab spin up before we start the clock
    t0 = time.monotonic()

    clicks: list[dict] = []
    marks: list[float] = []
    stop = {"flag": False}

    def on_click(x, y, button, pressed):
        if pressed:
            lx, ly = geo.to_local(x, y)
            clicks.append({"t": time.monotonic() - t0, "x": lx, "y": ly})

    def on_press(key):
        try:
            name = key.char
        except AttributeError:
            name = getattr(key, "name", None)
        if name == mark_key:
            t = time.monotonic() - t0
            marks.append(t)
            if verbose:
                print(f"[screencap]  mark {len(marks)} @ {t:.1f}s")
        elif key == keyboard.Key.esc:
            stop["flag"] = True
            return False  # stop the keyboard listener

    ml = mouse.Listener(on_click=on_click)
    kl = keyboard.Listener(on_press=on_press)
    ml.start()
    kl.start()
    kl.join()  # blocks until Esc
    ml.stop()
    duration = time.monotonic() - t0

    # Ask ffmpeg to finalize the file cleanly (q on stdin), then fall back to term.
    try:
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=5)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    events = {
        "duration": duration,
        "origin": [geo.x, geo.y],
        "size": [geo.width, geo.height],
        "clicks": clicks,
        "marks": marks,
        "video": str(video),
    }
    (out_dir / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    if verbose:
        print(f"[screencap] done: {duration:.1f}s, {len(clicks)} clicks, "
              f"{len(marks)} marks -> {video}")
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

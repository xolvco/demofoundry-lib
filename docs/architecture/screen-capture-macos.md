# Screen capture on macOS

**Status: the macOS backend is written but has _not_ been run on a Mac yet.** It was developed on
Windows, so the parts that depend on real hardware — the avfoundation device index, Retina (points ↔
pixels) scaling, and window coordinates — need verification. This page is the checklist for the
person who brings it up on a Mac.

The rest of DemoFoundry is already cross-platform: only [`pipeline/screencap.py`](#where-the-code-is)
touches the OS, behind a per-platform `Backend`. Everything downstream — narrate → sync → compose,
the web UI, the Record/Mark screens — runs unchanged.

## Setup on a Mac

```bash
cd backend
pip install -e ".[screencap-macos]"   # pynput + pyobjc-framework-Quartz
# ffmpeg must be on PATH (brew install ffmpeg)
```

Then grant two permissions in **System Settings → Privacy & Security** (DemoFoundry can't enable
these for you — macOS requires the user to):

- **Screen Recording** — for the app running the backend (your terminal, or the packaged app).
  Without it, avfoundation records a **black** frame.
- **Input Monitoring** (and often **Accessibility**) — for the same app, so `pynput` can see your
  clicks and the F9 marks. Without it, no clicks or marks are logged.

You'll usually be prompted on first run; if not, add the app manually and restart it.

## What needs verifying (the three risk areas)

1. **avfoundation screen-capture device index.** `_MacBackend._screen_index()` parses
   `ffmpeg -f avfoundation -list_devices true -i ""` for the `Capture screen 0` line and uses its
   bracketed index. Confirm that index is right on your machine (run the command and read the list).
   The input is video-only (`-i "<idx>"`, no audio device).
2. **Retina scaling.** `CaptureGeometry.scale` is pixels-per-point. avfoundation records in **pixels**
   but `pynput` reports clicks in **points**, so `to_local` multiplies clicks by `scale`. Verify a
   click lands on the highlight box in the rendered video — if it's off by ~2×, the scale or the
   click units are wrong.
3. **Window bounds origin.** `window_geometry()` reads `kCGWindowBounds` (documented top-left origin)
   and scales to pixels for the `-vf crop`. Verify a window-targeted capture crops to exactly that
   window (not shifted vertically — a Cocoa bottom-left origin would shift it).

## How to test

Record a few seconds of a window, marking one scene, and render:

```bash
python -m demofoundry.pipeline.screencap \
  --out work --window "Safari" \
  --steps examples/desktop-feature-demo.steps.json --voice <voice_id>
# walk through; F9 once or twice; Esc to stop
```

Check, in order:

- `work/recording.mp4` plays and shows the **right region** (not black, not the whole desktop, not
  shifted) → grabber + crop + permissions OK.
- `work/events.json` has non-empty `clicks` and `marks` → input hook + permissions OK.
- the rendered `work/render/demo.mp4` puts the highlight box **where you clicked** → scaling OK.

The in-app flow (Project → Desktop → Record → Mark → Run) uses the same backend, so once the CLI
works, the UI does too.

## Where the code is

All macOS-specific logic is in `backend/demofoundry/pipeline/screencap.py`:

- `_MacBackend.primary_monitor()` / `window_geometry()` — Quartz (`CGMainDisplayID`,
  `CGDisplayBounds`, `CGWindowListCopyWindowInfo`).
- `_MacBackend.capture_args()` — avfoundation input + a `-vf crop` filter (avfoundation can't crop on
  input the way gdigrab does).
- `_backend()` dispatches on `sys.platform`. A Linux backend (`x11grab` / PipeWire) slots in the same
  way.

See [Automation & capture](automation.md) for how this sits in the pipeline.

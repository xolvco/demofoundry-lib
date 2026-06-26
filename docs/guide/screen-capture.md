# Screen capture (desktop apps)

The [CLI capture path](cli.md) drives your app from the outside with Playwright. That works well
for web apps, but it needs the app to expose stable selectors — and most **desktop apps don't**.

The **screen-capture path** sidesteps automation entirely: you record yourself walking through the
app, and DemoFoundry narrates, syncs, and composes the result. It never touches the app, so it works
with **anything on screen** — a Tauri or Electron app, a native Windows program, a game, a terminal.

!!! info "What's the same"
    Only *how the video is produced* changes. Once you have a recording and per-scene timings,
    `narrate → sync → compose` runs exactly as it does for the browser path — same audio-as-master
    clock, same HOLD/SPEED sync, same MP4 + SRT out. Your script's narration is unchanged.

## Requirements

- **ffmpeg** on `PATH` (already needed for compose) — provides the screen grabber (`gdigrab`).
- **pynput** for the global input hook: `pip install -e ".[screencap]"` (or `".[all]"`).
- **Windows** (the grabber is `gdigrab`; macOS/Linux backends are not wired yet).
- `ELEVENLABS_API_KEY` in `.env` for narration (otherwise you get silent clips).

## Record and render in one command

From `backend/`:

```bash
python -m demofoundry.pipeline.screencap \
  --out work \
  --window "FunscriptForge" \
  --steps script.json \
  --voice <voice_id>
```

This:

1. starts recording the chosen window,
2. lets you **drive the app yourself**,
3. then narrates each scene and composes — writing `work/render/demo.mp4` and `demo.srt`.

While recording:

| Key | Does |
|---|---|
| **F9** | Mark the start of the next narration beat. |
| **Esc** | Stop recording (then narrate + compose run). |

!!! tip "How many marks?"
    A mark is the boundary *between* scenes. The first scene starts automatically at the top of the
    recording, so for **N scenes you press F9 N−1 times** — once each time you move to the next beat.
    An 8-scene script needs 7 marks.

Leave off `--steps` to just record — it writes `work/recording.mp4` and `work/events.json` (the
clicks + marks) so you can render later.

## How your recording maps to the script

DemoFoundry pairs your script's scenes with the recording by time:

- **Marks** (default, `--anchor marks`) become the scene boundaries — scene 1 runs from the start to
  your first F9, scene 2 to your second, and so on, the last scene to the end.
- **Clicks** are logged automatically with their on-screen position. Each scene uses the first click
  inside its slot to place the highlight (and, later, zoom). Pass `--anchor clicks` to use clicks
  themselves as a rough auto-split when you'd rather not press F9.

Because **audio is the master clock**, each video slice is stretched or held to fit its narration —
so you don't have to match timing precisely while recording. Just linger on each view about as long
as its narration runs and do something worth showing.

## The script file

Same shape as the [step file](cli.md#the-step-file), but for screen capture the **selectors are
ignored** — you're driving by hand, so only the narration (and the number/order of scenes) matters:

```json
{
  "steps": [
    { "narration_text": "This is the Library — every project in one place." },
    { "narration_text": "Open a video and FunscriptForge builds the first draft for you." },
    { "narration_text": "Analysis stacks the video, its audio, and the script together." }
  ]
}
```

A bare JSON array works too. Any `action`/`target`/`zoom_target` fields are accepted but unused on
this path.

## Tips

- **Pick the window, not the desktop.** `--window` crops to just that app (matched on a substring of
  its title). Without it, DemoFoundry records your primary monitor.
- **Aspect ratio.** Output is forced to 1920×1080; a window that isn't ~16:9 will stretch slightly.
  Size the window close to 16:9 for the cleanest result.
- **Show, don't just tell.** This is the payoff over the browser path — scrub, play, click during
  each beat so the video demonstrates what the narration describes instead of holding a still frame.
- **Re-narrate cheaply.** The recording + `events.json` are reusable; changing the voice or wording
  re-runs only narrate → compose, never the recording.

See [Automation & capture](../architecture/automation.md) for how this sits alongside the browser
path in the pipeline.

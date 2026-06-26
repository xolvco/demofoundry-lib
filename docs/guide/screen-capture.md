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

## Two ways to run it

- **In the app (recommended).** On the **Project** screen choose **Desktop app**, then follow the
  rail: **Record** (start/stop a screen capture) → **Mark** (play it back and place scene boundaries
  on a timeline) → **Voice** → **Run**. Nothing to install beyond the requirements below.
- **From the CLI.** One command records and renders — handy for scripting or headless runs (see
  [below](#record-and-render-in-one-command)).

Both paths produce the same recording + per-scene marks and feed the same render.

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

## Example: a script that demos this feature

Here's a complete, copy-ready script whose subject **is the screen-capture feature** — the lines you'd
narrate while recording a walkthrough of DemoFoundry's own **Project → Record → Mark → Run** flow.
Save it as `steps.json`, start a **Desktop** demo with it (New demo → *Desktop app*), record the
walkthrough, mark the scenes, pick a voice, and render.

```json
{
  "name": "DemoFoundry — Record a desktop demo",
  "steps": [
    { "narration_text": "This is DemoFoundry. It turns a walkthrough of your app into a narrated, captioned demo video — and now it works for desktop apps, not just web pages." },
    { "narration_text": "Here's the problem it solves. A web app can be driven automatically, but a native desktop app can't — there's nothing to click from the outside. So instead of driving your app, DemoFoundry records you using it, and takes care of the narration, timing, and polish." },
    { "narration_text": "It begins on the Project screen. You choose how you'll capture this demo — drive a web app, or record a desktop app. We'll pick Desktop. There's no URL and no selectors to wire up." },
    { "narration_text": "You drop in a script — just the words you want narrated, one line per scene — and click Create and record." },
    { "narration_text": "On the Record screen you point DemoFoundry at a window: your app. Press Start, and it records the screen. No audio is captured — your narration is added later, so you can re-record your voice any time without re-recording the screen." },
    { "narration_text": "Now you simply use your app, beat by beat, the way you'd show it to a colleague. Take your time and actually do things — scrub, click, type — so the video shows what the words describe. Press Stop when you're done." },
    { "narration_text": "Next comes Mark. Your recording plays back on a timeline, and you drop a boundary at the start of each scene. The clicks you made while recording appear as snap points, so landing on the right moment is easy — and you're never editing the original footage." },
    { "narration_text": "Each boundary splits the recording into scenes, shown as colored bands. This is the human part: you decide where each line of narration belongs, watching the video, not guessing at timestamps." },
    { "narration_text": "Then you pick a voice, and DemoFoundry narrates every scene with it." },
    { "narration_text": "Finally, Run. DemoFoundry narrates each scene, syncs the video to the audio — holding or speeding the footage so every line fits perfectly — and composes a finished MP4 with captions." },
    { "narration_text": "That's the whole loop: record your real app once, mark the beats, and ship a polished demo. Approachable on the very first day — and it works with anything you can put on screen." }
  ]
}
```

Eleven scenes, so when you record you'll mark **ten** boundaries. As you capture, linger on each
matching screen and perform the action the line describes — choose Desktop, press Start, drop a mark —
so the footage demonstrates the feature instead of just describing it.

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

# CLI

DemoFoundry exposes **each pipeline step as a subcommand**. Steps chain on the filesystem (JSON
artifacts), so you can run the whole thing at once or run — and debug — any single stage on its own.

!!! tip "Demoing a desktop app?"
    This page covers the browser/automation path. For native desktop apps (where there are no
    selectors to drive), record yourself instead — see [Screen capture](screen-capture.md).

## Install

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # macOS/Linux: .venv/bin/activate
pip install -e ".[all]"        # editable install with every extra
playwright install chromium    # one time (for capture)
# ffmpeg must be on PATH (https://ffmpeg.org) for compose
```

This installs the `demofoundry` command. Without keys the pipeline still runs (silent narration, no
Claude scripting) — copy `.env.example` to `.env` to enable `ANTHROPIC_API_KEY` (scripting) and
`ELEVENLABS_API_KEY` (voice).

## One-shot

```bash
demofoundry render --url http://localhost:3000 --steps steps.json --out-dir work
# optionally let Claude write the narration first:
demofoundry render --url http://localhost:3000 --steps steps.json --out-dir work \
  --desc "a quick tour of the new checkout flow"
```

Outputs `work/render/demo.mp4` and `demo.srt`.

### Pacing

Two knobs control how relaxed the result feels (both have sensible defaults, so
you only set them to taste):

```bash
demofoundry render --url http://localhost:3000 --steps steps.json --out-dir work \
  --voice-speed 0.9 \   # speaking rate: 1.0 normal, <1.0 slower (0.7–1.2). Default 0.9
  --scene-lead 600      # silent hold (ms) on each new screen before the voice. Default 600
```

- **`--voice-speed`** slows (or speeds) the narration. It's a native ElevenLabs
  setting, so pitch is preserved — `0.9` is a gentle, unhurried default.
- **`--scene-lead`** freezes each scene's first frame silently for that many
  milliseconds before the voice starts, giving the viewer a beat to take in a
  new screen. Set `0` to start talking immediately.

The same defaults apply on every path (browser and screen-capture) and can be
set globally with the `DEMOFOUNDRY_VOICE_SPEED` / `DEMOFOUNDRY_SCENE_LEAD_MS`
environment variables.

## Step by step

Each command consumes and produces files, so you can stop, inspect, and re-run any stage:

```bash
# 1. drive your app once and record it
demofoundry capture --url http://localhost:3000 --steps steps.json --out-dir work
#    -> work/recording.webm, work/records.json

# 2. (optional) Claude writes narration + zoom/highlight suggestions
demofoundry script --steps steps.json --desc "tour of checkout"
#    -> steps.json (updated in place; use --out to write elsewhere)

# 3. render one narration clip per step
demofoundry tts --steps steps.json --out-dir work --voice <voice_id>
#    -> work/durations.json, work/audio.json, work/audio/*.wav

# 4. build the time-remap plan (the sync engine; no binaries needed)
demofoundry sync --steps steps.json --records work/records.json \
  --durations work/durations.json --audio work/audio.json --out work/plan.json

# 5. render the plan to MP4 + SRT
demofoundry compose --steps steps.json --plan work/plan.json \
  --video work/recording.webm --records work/records.json --out work/demo.mp4
```

Because `capture` runs once and the later stages read its artifacts, re-narrating or adding a
language only re-runs steps 3–5 — the browser is never re-driven.

## The step file

A step list is a JSON array. Selectors are Playwright locators (prefer `data-testid`):

```json
[
  { "action": "click", "target": "[data-testid='start']" },
  { "action": "type",  "target": "#email", "value": "demo@acme.com" },
  { "action": "click", "target": "text=Continue", "zoom_target": "#order-summary" },
  { "action": "wait",  "value": "1500" }
]
```

| Field | Meaning |
|---|---|
| `action` | `click` · `type` · `navigate` · `keypress` · `wait` |
| `target` | selector the action applies to |
| `value` | text to type / URL to navigate / key to press / ms to wait |
| `narration_text` | what the voice says (also the caption source) |
| `pronunciation_override` | what TTS speaks, if different from `narration_text` |
| `zoom_target` / `highlight_target` | selectors to zoom to / highlight |

## Commands

| Command | Does |
|---|---|
| `capture` | Drive the target app with Playwright; record video + timestamped action log. |
| `script` | Claude writes narration and suggests zoom/highlight. |
| `tts` | Render one narration clip per step (+ durations). |
| `sync` | Build the time-remap plan (the sync engine). |
| `compose` | Render the plan to MP4 and write the SRT. |
| `render` | Run the whole pipeline. |
| `serve` | Launch the [local web app](../architecture/mvp.md). |

# DemoFoundry — backend (MVP)

Local web app that turns a click-flow through your React app into a narrated,
subtitled demo video. See the [architecture docs](../docs/architecture/mvp.md)
and [feature list](../docs/features.md).

It ships three layers over one library: the **`demofoundry` library** (pure
pipeline), a **CLI** (each step a subcommand — see the [CLI guide](../docs/guide/cli.md)),
and the **web app**.

## Install

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows; macOS/Linux: .venv/bin/activate
pip install -e ".[all]"                            # library + CLI + web
playwright install chromium                         # one time (capture)
# ffmpeg must be on PATH (https://ffmpeg.org) for compose
```

## Run

```bash
# Web app
demofoundry serve --port 8000          # or: uvicorn demofoundry.main:app --reload
# CLI (whole pipeline)
demofoundry render --url http://localhost:3000 --steps steps.json --out-dir work
```

Open <http://localhost:8000>, point it at your app (e.g. `http://localhost:3000`),
paste a step list, optionally let Claude write the narration, then render.

Keys are optional — copy `../.env.example` to `../.env` to enable Claude
scripting (`ANTHROPIC_API_KEY`) and real voice (`ELEVENLABS_API_KEY`). Without
them the pipeline still produces a synced video with silent narration.

## Layout

```text
demofoundry/
  config.py        local keys + workspace
  models.py        Step, ActionRecord, Segment, RenderPlan (dataclasses)
  serde.py         JSON (de)serialization for pipeline artifacts
  store.py         SQLite project store
  render.py        orchestration: capture -> tts -> sync -> compose
  cli.py           each pipeline step as a subcommand
  main.py          FastAPI app + static UI
  static/          minimal local UI (React port is the next step)
  pipeline/
    capture.py     Playwright: drive + record + timestamps/rects
    tts.py         ElevenLabs + silent fallback
    sync.py        the sync engine (unit-tested)
    compose.py     ffmpeg: remap, zoom, highlight, click marker, SRT
    scripting.py   Claude: narration + zoom/highlight suggestions
tests/
  test_sync.py  test_serde.py  test_tts.py  test_cli.py  test_compose.py
  test_capture.py            # real Playwright path; skips without the browser
  fixtures/sample.html       # bundled target for the capture smoke test
```

## Test the core

```bash
for t in sync serde tts cli compose capture; do python tests/test_$t.py; done
```

`test_capture` skips without Playwright + Chromium; `test_compose`'s render skips
without ffmpeg (its SRT test always runs). The rest need no binaries or keys.

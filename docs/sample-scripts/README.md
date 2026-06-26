# Sample scripts

Copy-ready `steps.json` scripts you can run through DemoFoundry. Each is either a **web** script
(DemoFoundry drives it with Playwright — needs real selectors) or a **screen-capture** script
(narration only — you record yourself; selectors are ignored). See the
[CLI guide](../guide/cli.md) and [Screen capture guide](../guide/screen-capture.md).

| File | Mode | What it demos |
|---|---|---|
| [`demofoundry-self-demo.playwright.steps.json`](demofoundry-self-demo.playwright.steps.json) | Web (Playwright) | DemoFoundry's own UI, fully click-driven — every step has a real selector. |
| [`demofoundry-web-tour.steps.json`](demofoundry-web-tour.steps.json) | Web (Playwright) | A lighter narrated tour of the DemoFoundry New-demo flow. |
| [`webmethods-getting-started.steps.json`](webmethods-getting-started.steps.json) | Screen capture (Desktop) | Getting started with IBM webMethods.io Integration. |

## Running a web script

The two DemoFoundry scripts drive the app at `http://localhost:3000`, so start the app first
(`npm run dev` for the frontend, the backend on `:8001`). Then:

```bash
cd backend
demofoundry render --url http://localhost:3000 \
  --steps ../docs/sample-scripts/demofoundry-self-demo.playwright.steps.json \
  --out-dir work
```

The selectors are taken from the live UI (`text=New demo`, `button:has-text("Web app")`, `#name`,
`#target`, `text=Reset to sample`, `text=What we read`, `text=Cancel`). If the UI changes, update the
`target` fields to match.

### Build the DemoFoundry demo with no GUI

This is the exact, copy-paste recipe used to produce the **DemoFoundry self-demo** — Playwright
drives the live UI, so nothing is recorded by hand.

#### 1. Set up the backend (one time)

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate        # macOS/Linux: . .venv/bin/activate
pip install -e ".[all]"          # installs the `demofoundry` CLI + Playwright, FastAPI, etc.
playwright install chromium      # the headless browser that drives the app
# ffmpeg must also be on PATH (https://ffmpeg.org) — it does the compose step.
```

#### 2. Add your API keys

The self-demo narrates with ElevenLabs (and can let Claude write narration), so it needs keys.
Copy the template and fill it in:

```bash
cp ../.env.example ../.env       # both live at the repo root, next to backend/
```

Edit `.env` and set:

```ini
ELEVENLABS_API_KEY=sk_...        # required for voice (without it, narration is silent)
ANTHROPIC_API_KEY=sk-ant-...     # optional — only if you let Claude write/expand the script
```

`.env` is gitignored — your keys never get committed. The backend loads it automatically; for the
CLI you load it into the shell (step 4).

#### 3. Start the app it will demo

In two terminals (the demo drives DemoFoundry itself, so DemoFoundry must be running):

```bash
# terminal A — backend API on :8001
cd backend && uvicorn demofoundry.main:app --port 8001

# terminal B — frontend UI on :3000
cd ../../demofoundry-app && npm install && npm run dev
```

The frontend reads the backend URL from `demofoundry-app/.env.local` —
set `NEXT_PUBLIC_API_BASE=http://localhost:8001` there so the UI can reach the API. (Only the
DemoFoundry self-demo needs the backend running, because the *app being demoed* is DemoFoundry
itself; `demofoundry render` on its own just needs the target app reachable at `--url`.)

#### 4. Render the demo

From `backend/`, with the app up on `:3000`:

```bash
# load the keys from the repo-root .env into this shell
set -a; . ../.env; set +a

demofoundry render \
  --url http://localhost:3000 \
  --steps ../docs/sample-scripts/demofoundry-self-demo.playwright.steps.json \
  --out-dir work-demo \
  --voice EXAVITQu4vr4xnSDxMaL \   # ElevenLabs voice id (any from your voice list)
  --voice-speed 0.9 \              # optional — slower, unhurried narration (default 0.9)
  --scene-lead 600                 # optional — silent beat on each new screen (ms, default 600)
```

Output lands in `backend/work-demo/render/`: `demo.mp4` and `demo.srt`.

!!! warning "Pass a real `--voice`"
    The CLI's default `--voice` is the literal `default`, which ElevenLabs rejects (404). Always pass
    a voice id — the one above is the same warm "Sarah" voice the app defaults to.

!!! tip "Windows note"
    On PowerShell, load the env with
    `Get-Content ..\.env | %{ if ($_ -match '^(\w+)=(.*)$') { Set-Item "env:$($matches[1])" $matches[2] } }`
    (or just rely on the backend's own `.env` loader when running through the app). The Bash form
    above works in Git Bash / WSL.

## Running a screen-capture script

`webmethods-getting-started.steps.json` targets IBM webMethods.io — an external SaaS you can't (and
shouldn't) drive with selectors. Use the **Desktop** capture path: create the demo as a Desktop app,
record yourself walking through webMethods.io in the browser, mark the eleven scenes, pick a voice,
and render. The script supplies the narration for each beat. See
[Screen capture](../guide/screen-capture.md).

## IBM webMethods — where to get started (official docs)

For the webMethods script above, these are the official starting points:

- **IBM webMethods documentation home** — <https://docs.webmethods.io>
- **Getting started (IBM Docs)** — <https://www.ibm.com/docs/en/wam/wdp/11.1.0?topic=getting-started>
- **webMethods Integration overview** — <https://www.ibm.com/docs/en/wm-integration-ipaas?topic=overview>
- **Getting Started with webMethods.io: A Beginner's Guide (IBM Community)** —
  <https://community.ibm.com/community/user/integration/viewdocument/getting-started-with-webmethodsio>
- **Working with IBM webMethods Integration Server** —
  <https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/11.1.0?topic=guide-working-webmethods-integration-server>

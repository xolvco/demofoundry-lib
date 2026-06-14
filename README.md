# DemoFoundry

[![Repository](https://img.shields.io/badge/github-xolvco%2Fdemofoundry--lib-181717?logo=github)](https://github.com/xolvco/demofoundry-lib)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

**Repository:** <https://github.com/xolvco/demofoundry-lib>

Turn a click-flow through your web app into a **narrated, subtitled demo video — automatically.**
Building demos by hand is as slow as building the app; DemoFoundry generates them, so a release is a
command, not a week of screen-recording.

> **Status:** MVP, local-first. Targets your own React/web apps on `localhost`. Native-desktop and
> SaaS are documented future tracks.

## How it works

```mermaid
flowchart LR
    P[Steps + target URL] --> CAP[Capture<br/>Playwright]
    CAP --> SCR[Script<br/>Claude]
    SCR --> TTS[Narrate<br/>per-step clips]
    TTS --> SYNC[Sync engine]
    SYNC --> COMP[Compose<br/>ffmpeg]
    COMP --> OUT[MP4 + SRT]
```

DemoFoundry drives your app once with Playwright (recording video + timestamped actions), has Claude
write the narration, renders per-step voice clips, and then the **sync engine** — the core
differentiator — automatically aligns audio and video: it pauses the video when the narration runs
long and fast-forwards it when the action runs long. Because the tool owns *both* timelines, that
alignment is computed, not hand-edited.

## Install

```bash
git clone git@github.com:xolvco/demofoundry-lib.git
cd demofoundry-lib/backend
python -m venv .venv && . .venv/Scripts/activate     # macOS/Linux: .venv/bin/activate
pip install -e ".[all]"
playwright install chromium                           # for capture
# ffmpeg must be on PATH (https://ffmpeg.org) for compose
```

Keys are optional — without them the pipeline still produces a synced video (silent narration, no
Claude scripting). Copy `.env.example` to `.env` to enable `ANTHROPIC_API_KEY` (scripting) and
`ELEVENLABS_API_KEY` (voice).

## Use

```bash
# whole pipeline against your app
demofoundry render --url http://localhost:3000 --steps steps.json --out-dir work
#   -> work/render/demo.mp4 + demo.srt

# or the local web UI
demofoundry serve --port 8000          # http://localhost:8000
```

Each pipeline stage is also its own subcommand (`capture`, `script`, `tts`, `sync`, `compose`) that
chains on JSON artifacts — see the [CLI guide](docs/guide/cli.md).

## Library

It's a reusable library with a CLI and web app as thin frontends; the core
(`models`/`sync`/`serde`/`compose`) is pure stdlib. See the [library guide](docs/guide/library.md).

```python
from demofoundry.pipeline import sync   # the sync engine, dependency-free
```

## Docs

Built with MkDocs Material (`pip install -r requirements-docs.txt && mkdocs serve`):

- [Architecture overview](docs/architecture/index.md) · [MVP](docs/architecture/mvp.md) ·
  [Sync engine](docs/architecture/sync-engine.md)
- [Feature list](docs/features.md) · [CLI](docs/guide/cli.md) · [Library](docs/guide/library.md)

## Tests

Per-stage; the core runs with no binaries or keys:

```bash
cd backend
for t in sync serde tts cli compose capture; do python tests/test_$t.py; done
```

`test_capture` (Playwright) and `test_compose`'s render (ffmpeg) skip when their binary is absent.

## Acknowledgements

DemoFoundry is built on open-source software. Each remains under its own copyright and license:

| Project | License | Role |
|---|---|---|
| [Playwright for Python](https://github.com/microsoft/playwright-python) | Apache-2.0 | Browser automation + recording |
| [FFmpeg](https://ffmpeg.org/) (external binary) | LGPL-2.1-or-later / GPL-2.0-or-later | Video composition |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | Web API |
| [Starlette](https://github.com/encode/starlette) | BSD-3-Clause | ASGI framework (via FastAPI) |
| [Uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | ASGI server |
| [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) | MIT | Claude scripting |
| [HTTPX](https://github.com/encode/httpx) | BSD-3-Clause | HTTP client (TTS) |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | API request/response models |
| [Material for MkDocs](https://github.com/squidfunk/mkdocs-material) | MIT | Documentation site |
| [Python](https://www.python.org/) | PSF License | Runtime |

FFmpeg is used as an external binary; if you redistribute a build that bundles it, comply with its
LGPL/GPL terms. Provider APIs (Anthropic, ElevenLabs, Azure) are used under their own terms of
service with your own keys.

## License

DemoFoundry is released under the [MIT License](LICENSE) — © 2026 Xolvco.

The MIT license applies to DemoFoundry's own source. Third-party dependencies and tools listed under
[Acknowledgements](#acknowledgements) remain under their respective copyrights and licenses.

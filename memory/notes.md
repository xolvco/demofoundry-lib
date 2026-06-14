# Notes — open items & next steps

Running scratchpad. Check off / prune as things land.

## Gating milestone

- [ ] **First real end-to-end render** against one of the launching apps (with `data-testid`s).
      This is the launch-gating step. Use it to tune `compose` from real output.

## Build status (as of initial commit)

- Done: library + CLI + web app scaffolded; all six pipeline stages implemented.
- Tests green: sync 5/5, serde 3/3, tts 2/2, cli 2/2, compose 2/2 (real ffmpeg render),
  capture 1/1 (real Chromium against the bundled fixture). venv set up; package builds wheel + sdist.

## To do / watch

- [ ] **compose tuning** — most likely area to need iteration. Cursor is currently a simple red box
      marker; upgrade to a real cursor asset + animated movement. Zoom is static (per-segment), not
      smooth Ken Burns yet.
- [ ] **Packaging root decision** — keep `backend/` (install with `#subdirectory=backend`) vs move to
      repo root for clean `pip install git+…`. Then add PyPI publish metadata.
- [ ] **`--narrate-only` shortcut** — re-run TTS→sync→compose on an existing capture for fast script
      iteration (no browser re-drive).
- [ ] **React UI** — replace the static `index.html` (the editor/timeline is nicer in React).
- [ ] **Seeded app state** for deterministic re-runs (animations / random data cause drift).

## Deferred (future tracks)

- Agentic step-discovery (Claude drives the app to find steps).
- Vertical / social output formats.
- Native desktop-app capture backend; camera-based unboxing/product demos.
- SaaS: deploy same code, job queue + worker pool, auth for private targets, usage billing.

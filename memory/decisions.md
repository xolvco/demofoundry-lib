# Decision log

Concise records of the choices that shape DemoFoundry, with rationale. Newest context at the bottom.

## Product / scope

1. **MVP is local-first, not cloud SaaS.** Targets are the user's own apps on `localhost`, which a
   cloud server can't reach. Running on the laptop makes them trivially reachable and removes the
   auth/SSRF/tunnel problems. SaaS is a documented future track (same code, deployed).
2. **First targets = the user's React web apps.** Native desktop apps are a future capture backend.
   Demoing third-party apps (tutorials) is in scope long-term but not for v1.
3. **Building demos is as costly as building the app** — automating it is the value prop and the
   reason this gates product launches.

## Pipeline / architecture

4. **Sync engine is the differentiator.** It auto-aligns audio↔video (pause video when narration
   runs long, fast-forward when the action runs long). Possible *because* the tool owns both
   timelines. This is what separates it from a manual competitor tool.
5. **Playwright is the capture keystone.** Beyond recording, its network/DOM-settle detection gives
   clean per-action timestamps that feed the sync engine. Free, MIT, first-class in Python.
6. **Effects rendered in post (ffmpeg), not in-browser.** Cursor, zoom, highlight are drawn from
   coordinates captured during the run — deterministic and re-runnable.
7. **Record once, narrate cheaply.** Capture is decoupled from TTS→sync→compose, so re-narrating or
   adding a language never re-drives the browser.
8. **Claude's MVP role = narrate + suggest.** User provides the click-flow (record mode); Claude
   writes narration and suggests zoom/highlight. Agentic step-discovery is deferred to v2.
9. **Reusable library + thin CLI + thin web app.** Pure-stdlib core (`models`/`sync`/`serde`/
   `compose`); heavy deps are optional extras (`browser`/`ai`/`voice`/`web`). Each pipeline step is
   also a CLI subcommand chaining JSON artifacts.
10. **Tests per stage.** Pure stages (sync/serde/tts/cli) always run; binary-gated stages
    (capture/compose) skip cleanly without Chromium/ffmpeg.

## Tooling

11. **TTS:** ElevenLabs / Azure, bring-your-own key (both give word-level timing). Silent fallback so
    the pipeline runs keyless.
12. **Scripting:** Claude `claude-opus-4-8`, adaptive thinking, structured output for the step list.
13. **Compose:** ffmpeg. **Store:** SQLite + local assets. **Docs:** MkDocs Material.
14. **Output:** 1080p 16:9 MP4 + SRT (web-playable). Branding (Claude-designed) is in the MVP;
    vertical/social formats deferred.

## Future SaaS / billing

15. **Usage-based billing** (per finished video or render-minute). Because users bring their own TTS
    key, metered COGS is compute + Claude scripting, not audio.

## Repo / infra

16. **GitHub:** `xolvco/demofoundry-lib`. Push over SSH via the **`github-xolvco`** host alias
    (key `id_ed25519_brucedkyle`, account `brucedkyle`) — the default `git@github.com` key auths as
    `bruceatxolvco` and is denied. `origin` is set to `git@github-xolvco:xolvco/demofoundry-lib.git`.
17. **License:** MIT © Xolvco.
18. **Packaging:** `pyproject.toml` lives in `backend/`, so VCS installs need
    `#subdirectory=backend`. Open: move packaging to repo root for a clean `pip install git+…`, and
    add PyPI publish metadata (readme/license/authors/urls/classifiers).

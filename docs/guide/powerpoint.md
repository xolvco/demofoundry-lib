# PowerPoint → narrated video

Turn a PowerPoint deck into a narrated, captioned MP4 from the command line.
DemoFoundry exports each slide to a faithful image, writes (or reuses) narration,
and renders the slides as a clean full-screen video — one scene per slide.

!!! info "Requirements (alpha)"
    Slide export uses **Microsoft PowerPoint** via COM automation, so this path
    needs **Windows with PowerPoint installed**. A cross-platform path
    (LibreOffice headless) is planned. Check availability any time:
    ```bash
    python -c "from demofoundry.pipeline.pptx_ingest import powerpoint_available as a; print(a())"
    ```

## 1. Install the extras

The ingester needs `python-pptx` (reads text/notes) and `pywin32` (drives
PowerPoint). They ship in the `pptx` extra:

```bash
pip install "demofoundry[pptx]"
# or, into an existing checkout:
pip install python-pptx pywin32
```

## 2. Ingest the deck

```bash
demofoundry ingest-pptx "C:/path/to/Deck.pptx" --out-dir out
```

This produces, in `out/`:

| File | What it is |
| --- | --- |
| `slides/slide-01.png …` | one faithful 1920×1080 image per slide |
| `deck.html` | a clean full-screen slideshow of those images |
| `steps.json` | the scene list — navigate to slide 1, then one `ArrowRight` per slide |

It prints the exact `render` command to run next, including the deck URL.

### Where the narration comes from

For each slide, in priority order:

1. **Speaker notes** in the `.pptx` — used **verbatim**. This is the way to
   bring your own script (see [below](#bring-your-own-narration)).
2. **Claude** writes spoken narration from the slide's on-screen text, for any
   slide that has no notes. Needs `ANTHROPIC_API_KEY`.

Skip Claude entirely with `--no-narrate` — you then get narration from notes only
(blank where there are none), to fill in by hand:

```bash
demofoundry ingest-pptx "Deck.pptx" --out-dir out --no-narrate
```

## 3. Render the video

Use the command `ingest-pptx` printed, or:

```bash
demofoundry render \
  --url "file:///C:/full/path/to/out/deck.html" \
  --steps out/steps.json \
  --out-dir video \
  --voice EXAVITQu4vr4xnSDxMaL \
  --voice-speed 0.85
```

The result is `video/render/demo.mp4` plus a matching `demo.srt`. Slides render
full-bleed with no navigation chrome — the deck advances by arrow key during
capture, so there are no buttons or click markers in the video.

!!! tip "Pacing"
    `--voice-speed` (default `0.85`, lower is slower) and `--scene-lead` (silent
    hold in ms on each new slide, default `600`) tune the rhythm. Slides with a
    lot of text read better a touch slower.

## Bring your own narration

Put your script in each slide's **Speaker Notes** in PowerPoint, then ingest.
DemoFoundry uses notes exactly as written and only asks Claude to fill slides you
left blank. This gives you full control of the voiceover while still letting
Claude cover any gaps. (You can also edit `out/steps.json` directly — each
scene's `narration_text` is plain text.)

## Good to know

- **One scene per slide.** The script schema is the same as a web demo; for
  slides, `narration_text` is the only field that matters per scene.
- **Builds/animations are flattened.** Each slide exports at its final state;
  click-by-click builds aren't stepped through (a later enhancement).
- **Emphasis within a slide** (zoom/highlight a region) isn't supported yet —
  a slide is a flat image, so there's no selector to point at.
- **Re-run freely.** Ingesting again re-exports the slides and rewrites
  `deck.html`/`steps.json`; your edits live in the deck's speaker notes, so they
  survive.

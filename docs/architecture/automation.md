# Automation & Capture

DemoFoundry drives the target application, performs the clicks and keystrokes for each
[step](index.md#core-data-model-the-step-list), and records the screen — logging the exact
timestamp of every action so the [sync engine](sync-engine.md) can align the video to the
narration.

Because the primary targets are **native desktop apps** (and arbitrary third-party apps for
tutorials), automation cannot rely on a DOM or a cooperative accessibility tree. The design is a
**driver abstraction** with two backends behind one interface.

```mermaid
flowchart TD
    STEP[Step list] --> DRV{Driver}
    DRV -->|native target| DESK[Desktop backend]
    DRV -->|URL target| WEB[Web backend]

    subgraph DESK[Desktop backend]
        VIS[Locate element:<br/>vision · Claude / accessibility]
        INP[Input: PyAutoGUI]
        CAP1[Capture: ffmpeg screen grab]
    end

    subgraph WEB[Web backend]
        SEL[Locate element:<br/>Playwright selectors]
        ACT[Input: Playwright]
        CAP2[Capture: Playwright video / ffmpeg]
    end

    DESK --> LOG[Timestamped action log + video]
    WEB --> LOG
```

## Desktop backend (primary)

For native apps the robust, general approach is **screen-record + vision-driven input**:

| Concern | Approach |
|---|---|
| **Where to click** | Send a screenshot to **Claude vision / computer-use**; it returns the target element's coordinates. This works on any app, including ones DemoFoundry has never seen. |
| **Fast path** | Where the app exposes an accessibility tree (**UIAutomation** on Windows, **AX** on macOS, **AT-SPI** on Linux), query it directly for stable, cheap element lookup before falling back to vision. |
| **Input** | **PyAutoGUI** for cross-platform mouse moves, clicks, and keystrokes. |
| **Capture** | **ffmpeg** with the platform screen input: `gdigrab` (Windows), `avfoundation` (macOS), `x11grab` / PipeWire (Linux). Region/window capture where supported. |

Each executed step writes an entry to the **action log** — `{ step_id, action, started_at, ended_at,
click_xy }` — timestamped against the same clock as the recording. That log is what makes automatic
sync possible.

!!! note "Why vision, not just accessibility"
    Accessibility trees are faster and more precise, but third-party apps expose them
    inconsistently (custom-drawn UIs, games, Electron apps with poor a11y). Vision-based location
    via Claude is the universal fallback so a tutorial can target *any* app; the accessibility path
    is an optimization layered on top.

## Web backend

When the target is a URL, **Playwright (Python)** is the specialized backend: stable selectors,
reliable waits, and **native video recording**. It produces the same timestamped action log as the
desktop backend, so everything downstream is identical.

## Output contract

Both backends produce exactly two things for the rest of the pipeline:

1. a **screen recording** of the walkthrough, and
2. a **timestamped action log** aligned to that recording.

The [sync engine](sync-engine.md) consumes both, plus the narration timings from TTS, to build the
final time-aligned video.

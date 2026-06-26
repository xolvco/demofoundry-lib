"""Render orchestration — ties the pipeline together.

capture (once) -> tts (per step) -> sync -> compose (+ srt). Decoupled by
design: re-narrating or adding a language re-runs from TTS onward without
re-driving the browser.

`render_to_files` is the store-free core used by the CLI and the web layer.
`run` wraps it with project-status updates for the web app.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Callable

from . import store
from .models import ActionRecord, Step
from .pipeline import capture, compose, screencap, sync, tts


def apply_pronunciations(text: str, catalog: dict[str, str] | None) -> str:
    """Swap catalog terms for their spoken form (whole-word, case-insensitive).

    Applied to the audio only — captions keep the original `narration_text`.
    """
    if not catalog:
        return text
    for term, spoken in catalog.items():
        if term.strip():
            text = re.sub(rf"\b{re.escape(term)}\b", spoken, text, flags=re.IGNORECASE)
    return text


async def render_to_files(
    target_url: str,
    steps: list[Step],
    out_dir: Path,
    voice_id: str = "default",
    on_status: Callable[[str], None] | None = None,
    on_records: Callable[[dict[str, ActionRecord]], None] | None = None,
    on_progress: Callable[[str], None] | None = None,
    pronunciations: dict[str, str] | None = None,
    voice_speed: float | None = None,
    scene_lead_ms: int | None = None,
) -> tuple[Path, Path]:
    """Run the whole pipeline to disk. Returns (video_path, srt_path).

    `on_status` reports the coarse stage (capturing/narrating/composing).
    `on_progress`, if given, reports a human sub-message per scene ("Recording
    scene 3 of 7") so a UI can show the pipeline is alive between stage changes.
    `on_records`, if given, is called with the capture records as soon as the
    capture stage finishes — so callers can persist which steps fired/failed
    before the (slower) narration + compose stages run.
    """
    if not steps:
        # An empty step list yields an empty RenderPlan and an empty ffmpeg
        # concat list, which crashes the muxer with an opaque error. Fail early
        # with something a human can act on.
        raise RuntimeError("This demo has no scenes — add at least one step before rendering.")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(steps)

    def status(s: str) -> None:
        if on_status:
            on_status(s)

    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    status("capturing")

    def on_capture_step(i: int, n: int, step: Step) -> None:
        progress(f"Recording scene {i} of {n}")

    video, records = await capture.capture(
        target_url, steps, out_dir / "capture", on_step=on_capture_step
    )
    if on_records:
        on_records(records)

    return await _narrate_sync_compose(
        video, records, steps, out_dir, voice_id, pronunciations, status, progress,
        voice_speed, scene_lead_ms,
    )


async def _narrate_sync_compose(
    video: Path,
    records: dict[str, ActionRecord],
    steps: list[Step],
    out_dir: Path,
    voice_id: str,
    pronunciations: dict[str, str] | None,
    status: Callable[[str], None],
    progress: Callable[[str], None],
    voice_speed: float | None = None,
    scene_lead_ms: int | None = None,
) -> tuple[Path, Path]:
    """The capture-agnostic tail: narrate each scene, sync to the video, compose.

    Shared by the browser path (capture.py) and the screen-capture path
    (screencap.py) — both just supply (video, records). Audio is the master
    clock; sync HOLDs/SPEEDs each video slice to fit its narration.

    `voice_speed` (<1.0 = slower) and `scene_lead_ms` (silent hold on each new
    screen before the voice) default to `config.VOICE_SPEED`/`SCENE_LEAD_MS`.
    """
    total = len(steps)
    status("narrating")
    durations: dict[str, float] = {}
    audio_paths: dict[str, str] = {}
    for i, step in enumerate(steps, start=1):
        progress(f"Narrating scene {i} of {total}")
        spoken = apply_pronunciations(step.speech_text(), pronunciations)
        # tts.synth is a blocking network/file call — run it off the event loop so
        # the web server stays responsive (status/progress stay pollable live).
        path, dur, _timings = await asyncio.to_thread(
            tts.synth, spoken, voice_id, out_dir / "audio" / step.id, voice_speed
        )
        durations[step.id] = dur
        audio_paths[step.id] = str(path)

    status("composing")
    progress("Composing video + captions")
    lead_seconds = None if scene_lead_ms is None else scene_lead_ms / 1000.0
    plan = sync.build_plan(steps, records, durations, audio_paths, lead_seconds)
    # ffmpeg compose is the longest blocking call — also off-loop.
    video_out = await asyncio.to_thread(
        compose.render, plan, video, records, out_dir / "render"
    )
    srt_out = await asyncio.to_thread(
        compose.write_srt, steps, plan, out_dir / "render" / "demo.srt"
    )
    return video_out, srt_out


async def render_screencap_to_files(
    events: dict,
    steps: list[Step],
    out_dir: Path,
    voice_id: str = "default",
    anchor: str = "marks",
    on_status: Callable[[str], None] | None = None,
    on_records: Callable[[dict[str, ActionRecord]], None] | None = None,
    on_progress: Callable[[str], None] | None = None,
    pronunciations: dict[str, str] | None = None,
    voice_speed: float | None = None,
    scene_lead_ms: int | None = None,
) -> tuple[Path, Path]:
    """Screen-capture render: a recording you made + your script -> narrated MP4.

    `events` is the dict screencap.record() produced (it carries the video path,
    clicks, and marks). The marks/clicks become per-scene boundaries; everything
    after is identical to the browser path.
    """
    if not steps:
        raise RuntimeError("This demo has no scenes — add at least one step before rendering.")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def status(s: str) -> None:
        if on_status:
            on_status(s)

    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    status("capturing")
    progress("Aligning your recording to the script")
    records = screencap.to_records(events, steps, anchor=anchor)
    if on_records:
        on_records(records)

    video = Path(events["video"])
    return await _narrate_sync_compose(
        video, records, steps, out_dir, voice_id, pronunciations, status, progress,
        voice_speed, scene_lead_ms,
    )


async def run(pid: str) -> None:
    """Store-backed render for the web app: updates project status as it goes."""
    project = store.get(pid)
    if not project:
        return
    steps = store.get_steps(pid)

    def save_results(records: dict[str, ActionRecord]) -> None:
        # Compact per-step outcome for the review UI: did each step fire?
        store.set_step_results(
            pid,
            {
                r.step_id: {
                    "status": r.status,
                    "error": r.error,
                    "duration": round(r.duration, 2),
                }
                for r in records.values()
            },
        )

    common = dict(
        # New stage clears the per-scene sub-message so it never shows stale.
        on_status=lambda s: store.update(pid, status=s, progress=""),
        on_records=save_results,
        on_progress=lambda m: store.update(pid, progress=m),
        pronunciations=project.get("pronunciations") or {},
    )
    try:
        store.update(pid, status="capturing", error=None, progress="")
        store.set_step_results(pid, {})  # clear any prior run's results
        if project.get("capture_mode") == "desktop":
            # Desktop: render from the recording the user made, not a live drive.
            events_path = store.asset_dir(pid) / "screencap" / "events.json"
            if not events_path.exists():
                raise RuntimeError("No recording yet — record a walkthrough first.")
            events = json.loads(events_path.read_text(encoding="utf-8"))
            video, srt = await render_screencap_to_files(
                events, steps, store.asset_dir(pid),
                project.get("voice_id") or "default", **common,
            )
        else:
            video, srt = await render_to_files(
                project["target_url"], steps, store.asset_dir(pid),
                project.get("voice_id") or "default", **common,
            )
        store.update(pid, status="done", video_path=str(video), srt_path=str(srt), progress="")
    except Exception as exc:  # surface failures to the UI
        store.update(pid, status="error", error=str(exc))
        raise

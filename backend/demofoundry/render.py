"""Render orchestration — ties the pipeline together.

capture (once) -> tts (per step) -> sync -> compose (+ srt). Decoupled by
design: re-narrating or adding a language re-runs from TTS onward without
re-driving the browser.

`render_to_files` is the store-free core used by the CLI and the web layer.
`run` wraps it with project-status updates for the web app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import store
from .models import Step
from .pipeline import capture, compose, sync, tts


async def render_to_files(
    target_url: str,
    steps: list[Step],
    out_dir: Path,
    voice_id: str = "default",
    on_status: Callable[[str], None] | None = None,
) -> tuple[Path, Path]:
    """Run the whole pipeline to disk. Returns (video_path, srt_path)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def status(s: str) -> None:
        if on_status:
            on_status(s)

    status("capturing")
    video, records = await capture.capture(target_url, steps, out_dir / "capture")

    status("narrating")
    durations: dict[str, float] = {}
    audio_paths: dict[str, str] = {}
    for step in steps:
        path, dur, _timings = tts.synth(
            step.speech_text(), voice_id, out_dir / "audio" / step.id
        )
        durations[step.id] = dur
        audio_paths[step.id] = str(path)

    status("composing")
    plan = sync.build_plan(steps, records, durations, audio_paths)
    video_out = compose.render(plan, video, records, out_dir / "render")
    srt_out = compose.write_srt(steps, plan, out_dir / "render" / "demo.srt")
    return video_out, srt_out


async def run(pid: str) -> None:
    """Store-backed render for the web app: updates project status as it goes."""
    project = store.get(pid)
    if not project:
        return
    steps = store.get_steps(pid)
    try:
        store.update(pid, status="capturing", error=None)
        video, srt = await render_to_files(
            project["target_url"],
            steps,
            store.asset_dir(pid),
            project.get("voice_id") or "default",
            on_status=lambda s: store.update(pid, status=s),
        )
        store.update(pid, status="done", video_path=str(video), srt_path=str(srt))
    except Exception as exc:  # surface failures to the UI
        store.update(pid, status="error", error=str(exc))
        raise

"""Compose — render the RenderPlan to MP4 with ffmpeg, and emit SRT.

Per segment we: trim the source slice, remap speed (fast-forward) or freeze the
tail (pause), zoom, draw a highlight + click marker, and attach the per-step
narration. Segments are rendered independently then concatenated, so a single
step can be re-rendered without redoing the whole video.

Effects are applied in post from coordinates captured during the run —
deterministic and re-runnable. Requires ffmpeg on PATH.

This is the piece most likely to need tuning on your machine (filtergraphs are
finicky); the structure is intentionally one-segment-at-a-time so it's easy to
debug a single step's command.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..models import RenderPlan, Rect, Segment, SegmentOp, Step

VW, VH = 1920, 1080
ZOOM_PAD = 0.35  # fraction of the rect added as breathing room around a zoom


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH")
    return exe


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _zoom_crop(rect: Rect) -> tuple[int, int, int, int]:
    """Crop window around a rect, padded and clamped to the frame, 16:9."""
    cx, cy = rect.x + rect.width / 2, rect.y + rect.height / 2
    w = min(VW, rect.width * (1 + 2 * ZOOM_PAD))
    h = w * VH / VW
    if h < rect.height * (1 + 2 * ZOOM_PAD):
        h = min(VH, rect.height * (1 + 2 * ZOOM_PAD))
        w = h * VW / VH
    x = max(0, min(VW - w, cx - w / 2))
    y = max(0, min(VH - h, cy - h / 2))
    return int(w), int(h), int(x), int(y)


def _video_filter(seg: Segment, rec_rects) -> str:
    f = ["scale=%d:%d" % (VW, VH), "setpts=PTS-STARTPTS"]
    if seg.op in (SegmentOp.SPEED, SegmentOp.TRIM) and seg.speed != 1.0:
        f.append("setpts=PTS/%.4f" % seg.speed)
    zoom = rec_rects.get("zoom")
    if zoom:
        w, h, x, y = _zoom_crop(zoom)
        f.append("crop=%d:%d:%d:%d" % (w, h, x, y))
        f.append("scale=%d:%d" % (VW, VH))
    hl = rec_rects.get("highlight")
    if hl:
        f.append(
            "drawbox=x=%d:y=%d:w=%d:h=%d:color=yellow@0.9:t=5"
            % (int(hl.x), int(hl.y), int(hl.width), int(hl.height))
        )
    click = rec_rects.get("click")
    if click:
        cx, cy = click
        f.append(
            "drawbox=x=%d:y=%d:w=28:h=28:color=red@0.6:t=fill"
            % (int(cx) - 14, int(cy) - 14)
        )
    if seg.hold_tail > 0.01:
        f.append(
            "tpad=stop_mode=clone:stop_duration=%.3f" % seg.hold_tail
        )
    return ",".join(f)


def _render_segment(
    seg: Segment, src_video: Path, rects: dict, out: Path
) -> None:
    ff = _ffmpeg()
    vf = _video_filter(seg, rects)
    cmd = [ff, "-y"]
    # video input: the captured slice
    cmd += ["-ss", "%.3f" % seg.src_start, "-to", "%.3f" % seg.src_end, "-i", str(src_video)]
    # audio input: narration clip, or generated silence to keep streams aligned
    if seg.audio_path:
        cmd += ["-i", seg.audio_path]
    else:
        cmd += ["-f", "lavfi", "-t", "%.3f" % seg.target_duration, "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += [
        "-filter_complex",
        "[0:v]%s[v];[1:a]apad,atrim=0:%.3f,asetpts=PTS-STARTPTS[a]"
        % (vf, seg.target_duration),
        "-map", "[v]", "-map", "[a]",
        "-t", "%.3f" % seg.target_duration,
        "-r", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-c:a", "aac",
        str(out),
    ]
    _run(cmd)


def render(
    plan: RenderPlan,
    src_video: Path,
    records: dict,
    out_dir: Path,
    out_name: str = "demo.mp4",
) -> Path:
    """Render the plan to a single MP4 by composing per-segment clips."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seg_paths: list[Path] = []
    for i, seg in enumerate(plan.segments):
        rec = records.get(seg.step_id)
        rects = {
            "zoom": rec.zoom_rect if rec else None,
            "highlight": rec.highlight_rect if rec else None,
            "click": rec.click_xy if rec else None,
        }
        seg_out = out_dir / f"seg_{i:03d}.mp4"
        _render_segment(seg, src_video, rects, seg_out)
        seg_paths.append(seg_out)

    listing = out_dir / "segments.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in seg_paths), encoding="utf-8")
    final = out_dir / out_name
    _run([_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", str(final)])
    return final


def write_srt(steps: list[Step], plan: RenderPlan, out_path: Path) -> Path:
    """Build SRT from the *original* narration text and segment timings."""
    lines, t = [], 0.0
    by_id = {s.step_id: s for s in plan.segments}
    for i, step in enumerate(steps, 1):
        seg = by_id.get(step.id)
        if not seg or not step.narration_text.strip():
            continue
        start, end = t, t + seg.target_duration
        t = end
        lines += [str(i), f"{_ts(start)} --> {_ts(end)}", step.narration_text, ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

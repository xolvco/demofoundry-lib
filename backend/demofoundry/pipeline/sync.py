"""Sync engine — the core differentiator.

Audio is the master clock. For each step we own both timelines: the narration
duration (from TTS) and the action's video window (from capture). We remap the
*video* to fit the narration:

  - action shorter than narration  -> HOLD: freeze the tail (video pauses)
  - action longer than narration    -> SPEED: speed the slice up (fast-forward)
  - action much longer (dead time)  -> SPEED capped at MAX_SPEED (a TRIM)

Pure function of durations — no video touched here, so it is unit-testable.
"""

from __future__ import annotations

from .. import config, models
from ..models import ActionRecord, RenderPlan, Segment, SegmentOp, Step

# Beyond this we're just cutting dead time (page loads, spinners) rather than
# showing a comically fast action.
MAX_SPEED = 4.0
# Floor so a long narration over a quick click doesn't crawl the video.
MIN_SPEED = 1.0


def build_plan(
    steps: list[Step],
    records: dict[str, ActionRecord],
    narration_durations: dict[str, float],
    audio_paths: dict[str, str] | None = None,
    lead_seconds: float | None = None,
) -> RenderPlan:
    """Reconcile each step's video window against its narration duration.

    Args:
        steps: ordered step list.
        records: step_id -> ActionRecord (video window, from capture).
        narration_durations: step_id -> seconds of rendered narration.
        audio_paths: step_id -> per-step audio clip path (optional).
        lead_seconds: silent hold of each scene's first frame before the voice
            starts (lets the viewer register a new screen). Defaults to
            `config.SCENE_LEAD_MS`.

    Returns:
        A RenderPlan whose total duration = sum(narration) + lead-per-scene.
    """
    audio_paths = audio_paths or {}
    if lead_seconds is None:
        lead_seconds = config.SCENE_LEAD_MS / 1000.0
    lead_seconds = max(0.0, lead_seconds)
    segments: list[Segment] = []

    for step in steps:
        rec = records.get(step.id)
        narr = max(0.0, narration_durations.get(step.id, 0.0))
        # A step with no captured action still gets its narration time as a hold.
        src_dur = rec.duration if rec else 0.0
        src_start = rec.started_at if rec else 0.0
        src_end = rec.ended_at if rec else 0.0

        # Narration of 0 (silent step) still needs a minimum beat so the action
        # is visible; fall back to the source duration.
        target = narr if narr > 0 else src_dur

        if src_dur <= 0.0:
            # No video to show — hold a frame for the narration.
            seg = Segment(
                step_id=step.id,
                src_start=src_start,
                src_end=src_end,
                target_duration=target,
                op=SegmentOp.HOLD,
                hold_tail=target,
                audio_path=audio_paths.get(step.id),
            )
        elif src_dur <= target:
            # Action finishes before narration -> hold the tail (video pauses).
            seg = Segment(
                step_id=step.id,
                src_start=src_start,
                src_end=src_end,
                target_duration=target,
                op=SegmentOp.HOLD,
                hold_tail=target - src_dur,
                audio_path=audio_paths.get(step.id),
            )
        else:
            # Action runs long -> speed it up to fit (capped = trim dead time).
            raw_speed = src_dur / target
            speed = min(max(raw_speed, MIN_SPEED), MAX_SPEED)
            op = SegmentOp.TRIM if raw_speed > MAX_SPEED else SegmentOp.SPEED
            # If capped, the segment will be shorter than narration; pad with a
            # hold so audio still leads.
            shown = src_dur / speed
            seg = Segment(
                step_id=step.id,
                src_start=src_start,
                src_end=src_end,
                target_duration=target,
                op=op,
                speed=speed,
                hold_tail=max(0.0, target - shown),
                audio_path=audio_paths.get(step.id),
            )
        # Prepend a silent hold of the scene's first frame: the new screen is
        # held quietly for `lead_seconds`, then the narration begins. Extends
        # the scene's total by the lead (compose freezes the head + delays audio).
        seg.lead = lead_seconds
        seg.target_duration += lead_seconds
        segments.append(seg)

    return RenderPlan(segments=segments)

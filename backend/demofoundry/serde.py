"""JSON serialization for pipeline artifacts.

Each CLI step reads and writes these so stages chain on the filesystem and each
is testable in isolation. Shared by the CLI, the web layer, and the store.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import (
    ActionRecord,
    ActionType,
    Rect,
    RenderPlan,
    Segment,
    SegmentOp,
    Step,
)

# --- Step ---------------------------------------------------------------


def step_to_dict(s: Step) -> dict:
    return {
        "id": s.id,
        "action": s.action.value,
        "target": s.target,
        "value": s.value,
        "narration_text": s.narration_text,
        "pronunciation_override": s.pronunciation_override,
        "zoom_target": s.zoom_target,
        "highlight_target": s.highlight_target,
    }


def step_from_dict(d: dict) -> Step:
    return Step(
        id=d["id"],
        action=ActionType(d.get("action", "click")),
        target=d.get("target"),
        value=d.get("value"),
        narration_text=d.get("narration_text", ""),
        pronunciation_override=d.get("pronunciation_override"),
        zoom_target=d.get("zoom_target"),
        highlight_target=d.get("highlight_target"),
    )


def load_steps(path: str | Path) -> list[Step]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # accept either a bare array or {"steps": [...]}
    items = data["steps"] if isinstance(data, dict) else data
    out = []
    for i, d in enumerate(items):
        d.setdefault("id", f"s{i + 1}")
        out.append(step_from_dict(d))
    return out


def save_steps(steps: list[Step], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps([step_to_dict(s) for s in steps], indent=2), encoding="utf-8"
    )


# --- Rect / ActionRecord -----------------------------------------------


def _rect_to(r: Rect | None) -> dict | None:
    return None if r is None else {"x": r.x, "y": r.y, "width": r.width, "height": r.height}


def _rect_from(d: dict | None) -> Rect | None:
    return None if d is None else Rect(d["x"], d["y"], d["width"], d["height"])


def record_to_dict(r: ActionRecord) -> dict:
    return {
        "step_id": r.step_id,
        "started_at": r.started_at,
        "ended_at": r.ended_at,
        "click_xy": list(r.click_xy) if r.click_xy else None,
        "target_rect": _rect_to(r.target_rect),
        "zoom_rect": _rect_to(r.zoom_rect),
        "highlight_rect": _rect_to(r.highlight_rect),
        "status": r.status,
        "error": r.error,
    }


def record_from_dict(d: dict) -> ActionRecord:
    xy = d.get("click_xy")
    return ActionRecord(
        step_id=d["step_id"],
        started_at=d["started_at"],
        ended_at=d["ended_at"],
        click_xy=tuple(xy) if xy else None,
        target_rect=_rect_from(d.get("target_rect")),
        zoom_rect=_rect_from(d.get("zoom_rect")),
        highlight_rect=_rect_from(d.get("highlight_rect")),
        status=d.get("status", "ok"),
        error=d.get("error"),
    )


def save_records(records: dict[str, ActionRecord], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps({k: record_to_dict(v) for k, v in records.items()}, indent=2),
        encoding="utf-8",
    )


def load_records(path: str | Path) -> dict[str, ActionRecord]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: record_from_dict(v) for k, v in data.items()}


# --- RenderPlan ---------------------------------------------------------


def save_plan(plan: RenderPlan, path: str | Path) -> None:
    payload = [
        {
            "step_id": s.step_id, "src_start": s.src_start, "src_end": s.src_end,
            "target_duration": s.target_duration, "op": s.op.value,
            "speed": s.speed, "hold_tail": s.hold_tail, "audio_path": s.audio_path,
        }
        for s in plan.segments
    ]
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_plan(path: str | Path) -> RenderPlan:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segs = [
        Segment(
            step_id=d["step_id"], src_start=d["src_start"], src_end=d["src_end"],
            target_duration=d["target_duration"], op=SegmentOp(d["op"]),
            speed=d.get("speed", 1.0), hold_tail=d.get("hold_tail", 0.0),
            audio_path=d.get("audio_path"),
        )
        for d in data
    ]
    return RenderPlan(segments=segs)


# --- plain dict artifacts ----------------------------------------------


def save_json(obj, path: str | Path) -> None:
    Path(path).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

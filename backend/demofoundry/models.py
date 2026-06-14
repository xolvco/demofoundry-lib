"""Domain models — the step list and the timing records the pipeline passes around.

Plain dataclasses (stdlib only) so the sync engine is testable without installing
FastAPI/pydantic. The API layer (main.py) maps these to/from JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    CLICK = "click"
    TYPE = "type"
    NAVIGATE = "navigate"
    KEYPRESS = "keypress"
    WAIT = "wait"


@dataclass
class Step:
    """One scene: a narration beat paired with an action and presentation notes."""

    id: str
    action: ActionType
    # Where the action applies. For web targets this is a Playwright selector
    # (prefer data-testid); `value` carries text to type / url to navigate / key.
    target: Optional[str] = None
    value: Optional[str] = None
    # Narration. `text` is the original (caption source); `pronunciation` (if set)
    # is what TTS speaks.
    narration_text: str = ""
    pronunciation_override: Optional[str] = None
    # Presentation. Selectors whose on-screen rect we zoom to / highlight.
    zoom_target: Optional[str] = None
    highlight_target: Optional[str] = None

    def speech_text(self) -> str:
        return self.pronunciation_override or self.narration_text


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass
class ActionRecord:
    """What capture observed for one step, timed against the recording clock."""

    step_id: str
    started_at: float  # seconds from recording start
    ended_at: float
    click_xy: Optional[tuple[float, float]] = None
    target_rect: Optional[Rect] = None
    zoom_rect: Optional[Rect] = None
    highlight_rect: Optional[Rect] = None
    # Did the action actually run? "ok" = fired; "skipped" = no matching branch
    # (a required selector/value was missing); "failed" = the action raised
    # (e.g. the selector matched nothing). `error` carries the reason for the
    # latter two so the review UI can show which steps silently no-op'd.
    status: str = "ok"
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        return max(0.0, self.ended_at - self.started_at)


class SegmentOp(str, Enum):
    SPEED = "speed"  # remap video faster/slower to fit narration
    HOLD = "hold"    # freeze the tail so video waits for narration
    TRIM = "trim"    # cut dead time (treated as a fast SPEED cap)


@dataclass
class Segment:
    """One step's slot in the final timeline: a video slice remapped to the audio."""

    step_id: str
    src_start: float        # slice of the source recording
    src_end: float
    target_duration: float  # = narration duration (audio is the master clock)
    op: SegmentOp
    speed: float = 1.0      # SPEED: src_dur/target_dur; >1 = fast-forward
    hold_tail: float = 0.0  # HOLD: seconds to freeze the last frame
    audio_path: Optional[str] = None  # per-step narration clip

    @property
    def src_duration(self) -> float:
        return max(0.0, self.src_end - self.src_start)


@dataclass
class RenderPlan:
    """The full time-remap plan the compositor renders."""

    segments: list[Segment] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(s.target_duration for s in self.segments)

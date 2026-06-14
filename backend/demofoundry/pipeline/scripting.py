"""Scripting — Claude writes the narration and suggests zoom/highlight points.

MVP role: the user provides the click-flow (the step list, e.g. via record mode);
Claude writes the spoken narration for each step and *suggests* what to zoom to
or highlight. The user stays in control and edits. Agentic step-discovery (Claude
driving the app to find steps itself) is a later track.

Uses the Anthropic SDK with structured output so the result is schema-validated
JSON — no fragile parsing. Default model: claude-opus-4-8.
"""

from __future__ import annotations

import json

from .. import config
from ..models import Step

_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "narration_text": {"type": "string"},
                    "zoom_target": {"type": ["string", "null"]},
                    "highlight_target": {"type": ["string", "null"]},
                },
                "required": ["id", "narration_text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You write concise, natural voiceover narration for software demo videos. "
    "One or two spoken sentences per step — what the viewer is seeing and why it "
    "matters. No stage directions, no 'in this step'. When a step centers on a "
    "specific UI element, suggest a CSS/test-id selector to zoom to or highlight."
)


def generate(description: str, steps: list[Step]) -> dict[str, dict]:
    """Return {step_id: {narration_text, zoom_target?, highlight_target?}}.

    Requires ANTHROPIC_API_KEY. Raises if unset (scripting is opt-in enrichment;
    narration can also be authored by hand).
    """
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set — set it to use Claude scripting")

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    step_brief = [
        {"id": s.id, "action": s.action.value, "target": s.target, "value": s.value}
        for s in steps
    ]
    user = (
        f"App / feature being demoed:\n{description}\n\n"
        f"Steps (ordered walkthrough):\n{json.dumps(step_brief, indent=2)}\n\n"
        "Write narration for every step id above."
    )

    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    return {s["id"]: s for s in data.get("steps", [])}


def apply(steps: list[Step], generated: dict[str, dict]) -> None:
    """Merge Claude's narration/suggestions into the step list in place."""
    for step in steps:
        g = generated.get(step.id)
        if not g:
            continue
        step.narration_text = g.get("narration_text", step.narration_text)
        step.zoom_target = g.get("zoom_target") or step.zoom_target
        step.highlight_target = g.get("highlight_target") or step.highlight_target

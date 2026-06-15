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

    # Non-destructive: only write narration for steps that don't already have it.
    # Lines the user wrote are kept verbatim (the captions source). Pass the full
    # ordered list as context so Claude writes coherent copy, but only request the
    # blank ones.
    blank = [s for s in steps if not s.narration_text.strip()]
    if not blank:
        return {}

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    step_brief = [
        {
            "id": s.id,
            "action": s.action.value,
            "target": s.target,
            "value": s.value,
            "existing_narration": s.narration_text or None,
            "needs_narration": not s.narration_text.strip(),
        }
        for s in steps
    ]
    user = (
        f"App / feature being demoed:\n{description}\n\n"
        f"Steps (ordered walkthrough):\n{json.dumps(step_brief, indent=2)}\n\n"
        "Write narration ONLY for steps where needs_narration is true. Keep the "
        "existing_narration of the others as-is (don't return them). Use the full "
        "sequence as context so the new lines flow with the ones already written."
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


# --- Build: author a whole steps.json from goal + app + reference -----------

BUILD_SYSTEM = (
    "You author demo scripts for DemoFoundry, which drives a web app with "
    "Playwright and narrates it. You output a steps.json: an ordered list of "
    "scenes. Each scene has an action (navigate | click | type | keypress | "
    "wait), a Playwright `target` selector taken from the app's element list "
    "(prefer data-testid), a `value` when relevant (type=text, navigate=url, "
    "keypress=key, wait=ms), and one or two sentences of natural `narration_text`. "
    "Keep it to 6-12 meaningful steps. Use ONLY selectors that appear in the "
    "element list; if the goal needs an element that isn't listed, prefer a "
    "text= selector or a wait. No stage directions in narration."
)

_BUILD_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"enum": ["navigate", "click", "type", "keypress", "wait"]},
                    "target": {"type": ["string", "null"]},
                    "value": {"type": ["string", "null"]},
                    "narration_text": {"type": "string"},
                    "zoom_target": {"type": ["string", "null"]},
                    "highlight_target": {"type": ["string", "null"]},
                },
                "required": ["action", "narration_text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["steps"],
    "additionalProperties": False,
}


def build_prompt(
    goal: str,
    reference: str,
    element_lines: str,
    audio_script: str = "",
    partial_steps: list[dict] | None = None,
) -> str:
    """Assemble the user prompt for the builder. Returned verbatim to the UI so
    the user can read and edit it before hitting Go."""
    parts = [
        f"Goal of the demo:\n{goal.strip() or '(not given — infer a sensible product tour)'}",
    ]
    if reference.strip():
        parts.append(f"Reference material about the app:\n{reference.strip()}")
    parts.append(f"The app's interactive elements (use these selectors):\n{element_lines}")
    if audio_script.strip():
        parts.append(
            "Existing narration / audio script — keep this wording, just attach "
            f"each line to the right action and selector:\n{audio_script.strip()}"
        )
    if partial_steps:
        parts.append(f"Existing partial steps to refine:\n{json.dumps(partial_steps, indent=2)}")
    parts.append(
        "Produce the complete steps.json now: the ordered scenes that achieve the "
        "goal against this app."
    )
    return "\n\n".join(parts)


def build(prompt: str) -> list[dict]:
    """Run Claude with the (possibly user-edited) prompt; return a list of step
    dicts (no ids — the caller assigns them)."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set — set it to use Claude scripting")

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=BUILD_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": _BUILD_SCHEMA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text).get("steps", [])


def apply(steps: list[Step], generated: dict[str, dict]) -> None:
    """Merge Claude's narration/suggestions into the step list in place.

    Non-destructive: narration the user already wrote is kept; only blank lines
    are filled. Zoom/highlight suggestions never clobber an existing value.
    """
    for step in steps:
        g = generated.get(step.id)
        if not g:
            continue
        if not step.narration_text.strip():
            step.narration_text = g.get("narration_text", step.narration_text)
        step.zoom_target = step.zoom_target or g.get("zoom_target")
        step.highlight_target = step.highlight_target or g.get("highlight_target")

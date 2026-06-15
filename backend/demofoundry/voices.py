"""Voices — the narrator catalog for the Voice screen.

Fetches the account's ElevenLabs voices (with `preview_url` so the UI can play
a sample). Falls back to a small curated list (no previews) when there's no key
or the call fails, so the picker always has something to show.
"""

from __future__ import annotations

import json
import urllib.request

from . import config

# Shown when ElevenLabs can't be reached. Ids are real library voices, so they
# still work for TTS even without a preview clip.
CURATED = [
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "description": "Warm · reassuring"},
    {"id": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice", "description": "Clear · articulate"},
    {"id": "FGY2WhTYpPnrIDTdsKH5", "name": "Laura", "description": "Upbeat · friendly"},
    {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "description": "Storyteller · rich"},
    {"id": "CwhRBWXzGAHq8TQ4Fs17", "name": "Roger", "description": "Casual · confident"},
    {"id": "SAz9YHcvj6GT2YYXdXww", "name": "River", "description": "Neutral · even"},
]


def _fallback() -> list[dict]:
    return [{**v, "preview_url": None} for v in CURATED]


def list_voices() -> list[dict]:
    """Return [{id, name, description, preview_url}] — live from ElevenLabs when
    possible, otherwise the curated fallback."""
    if not config.ELEVENLABS_API_KEY:
        return _fallback()
    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        out = []
        for v in data.get("voices", []):
            labels = v.get("labels") or {}
            desc = " · ".join(
                p for p in (labels.get("accent"), labels.get("description"), labels.get("use_case")) if p
            ) or v.get("category", "")
            out.append({
                "id": v["voice_id"],
                "name": v.get("name", ""),
                "description": desc,
                "preview_url": v.get("preview_url"),
            })
        return out or _fallback()
    except Exception as exc:  # never block the picker on a flaky API
        print(f"[voices] could not list ElevenLabs voices: {exc}")
        return _fallback()

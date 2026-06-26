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
    return [{**v, "preview_url": None, "category": "premade"} for v in CURATED]


def clone_voice(
    name: str, files: list[tuple[str, bytes, str | None]], description: str = ""
) -> dict:
    """Create an Instant Voice Clone from audio samples and return its catalog row.

    `files` is a list of (filename, bytes, content_type). ElevenLabs makes the
    clone near-instantly; the returned voice_id then works exactly like any other
    narrator (TTS speaks the script in that voice). Requires a key — cloning has
    no offline fallback.

    NOTE: you must have the speaker's consent to clone their voice; ElevenLabs
    requires you to attest to this.
    """
    import httpx

    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is required to clone a voice.")
    if not name.strip():
        raise ValueError("A name for the voice is required.")
    if not files:
        raise ValueError("At least one audio sample is required.")

    multipart = [
        ("files", (fn or "sample", blob, ct or "application/octet-stream"))
        for fn, blob, ct in files
    ]
    data = {"name": name.strip()}
    if description.strip():
        data["description"] = description.strip()

    resp = httpx.post(
        "https://api.elevenlabs.io/v1/voices/add",
        headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        data=data,
        files=multipart,
        timeout=120,
    )
    resp.raise_for_status()
    voice_id = resp.json()["voice_id"]
    return {
        "id": voice_id,
        "name": name.strip(),
        "description": "Your voice",
        "preview_url": None,
        "category": "cloned",
    }


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
                # "cloned" / "professional" / "premade" / "generated" — lets the
                # UI badge a user's own (cloned) voices.
                "category": v.get("category", "premade"),
            })
        # Cloned voices first so a user's own voice is easy to find.
        out.sort(key=lambda x: x["category"] != "cloned")
        return out or _fallback()
    except Exception as exc:  # never block the picker on a flaky API
        print(f"[voices] could not list ElevenLabs voices: {exc}")
        return _fallback()

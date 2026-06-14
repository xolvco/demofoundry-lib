"""TTS — render one narration clip per step.

Provider-pluggable. ElevenLabs is the first real provider; a silent fallback
lets the whole pipeline run end-to-end with no key (you still get a synced
video, just no voice) so the engine is demoable before you wire up audio.

Returns, per step: (audio_path, duration_seconds, word_timings).
word_timings = [(word, start, end)] feeds SRT + word-accurate sync; empty when
the provider doesn't supply them (the silent fallback estimates duration only).
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

from .. import config

WordTimings = list[tuple[str, float, float]]
# Rough speaking rate for the silent fallback's duration estimate.
WORDS_PER_SECOND = 2.6
SAMPLE_RATE = 44100


def synth(text: str, voice_id: str, out_path: Path) -> tuple[Path, float, WordTimings]:
    """Render `text` to `out_path`. Uses ElevenLabs if keyed, else silence."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if config.ELEVENLABS_API_KEY:
        return _elevenlabs(text, voice_id, out_path)
    return _silent(text, out_path.with_suffix(".wav"))


def _silent(text: str, out_path: Path) -> tuple[Path, float, WordTimings]:
    words = max(1, len(text.split()))
    duration = max(0.8, words / WORDS_PER_SECOND)
    frames = int(duration * SAMPLE_RATE)
    with wave.open(str(out_path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(struct.pack("<%dh" % frames, *([0] * frames)))
    return out_path, duration, []


def _elevenlabs(text: str, voice_id: str, out_path: Path) -> tuple[Path, float, WordTimings]:
    """Render via ElevenLabs with character-level timestamps -> word timings."""
    import base64

    import httpx

    mp3 = out_path.with_suffix(".mp3")
    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    )
    resp = httpx.post(
        url,
        headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))

    timings = _words_from_chars(text, data.get("alignment") or {})
    duration = timings[-1][2] if timings else max(0.8, len(text.split()) / WORDS_PER_SECOND)
    return mp3, duration, timings


def _words_from_chars(text: str, alignment: dict) -> WordTimings:
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not (chars and starts and ends):
        return []
    words: WordTimings = []
    cur, w_start = "", None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append((cur, w_start, prev_end))
                cur, w_start = "", None
        else:
            if not cur:
                w_start = s
            cur += ch
        prev_end = e
    if cur:
        words.append((cur, w_start, prev_end))
    return words

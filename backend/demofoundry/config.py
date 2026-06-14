"""Local configuration and key storage (MVP: env / .env file).

Keys live locally only. Deferred: OS keychain (see docs/features.md). The .env
file is read once at import; nothing is sent anywhere except the provider APIs.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = Path(os.environ.get("DEMOFOUNDRY_WORKSPACE", REPO_ROOT / "workspace"))
WORKSPACE.mkdir(parents=True, exist_ok=True)


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")

# Provider keys (bring-your-own). None until the user sets them.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
AZURE_SPEECH_KEY = os.environ.get("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.environ.get("AZURE_SPEECH_REGION")

# Default scripting model (see the claude-api guidance).
CLAUDE_MODEL = os.environ.get("DEMOFOUNDRY_CLAUDE_MODEL", "claude-opus-4-8")

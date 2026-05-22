#!/usr/bin/env python3
"""Generate ElevenLabs MP3 narration for each step of the /demo tour.

Walks the 12 narrations in dashboard/src/demo/demoScript.ts, calls the
ElevenLabs Text-to-Speech API with Adam (pNInz6obpgDQGcFmaJgB) at the
voice settings dialled in for the boutique-hospitality brand voice,
and writes step-01.mp3 through step-12.mp3 into
dashboard/public/demo-audio/. Skips files that already exist so reruns
only generate new or changed steps.

Usage:
    python3 scripts/generate_demo_audio.py            # uses .env
    ELEVENLABS_API_KEY=sk_... python3 scripts/generate_demo_audio.py

Requires ELEVENLABS_API_KEY. Cost: ~12,000 characters across 12 steps,
which is roughly 4 percent of a Starter tier monthly allowance.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")


ROOT       = Path(__file__).resolve().parent.parent
SCRIPT_TS  = ROOT / "dashboard" / "src" / "demo" / "demoScript.ts"
OUT_DIR    = ROOT / "dashboard" / "public" / "demo-audio"
ENV_FILE   = ROOT / ".env"

VOICE_ID   = "pNInz6obpgDQGcFmaJgB"        # Adam
MODEL_ID   = "eleven_turbo_v2_5"
VOICE_SETTINGS = {
    "stability":         0.38,
    "similarity_boost":  0.82,
    "style":             0.40,
    "use_speaker_boost": True,
}


def _load_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("ELEVENLABS_API_KEY not found in environment or .env")


def _parse_narrations(ts_path: Path) -> list[str]:
    """Extract the 12 narration strings from demoScript.ts in order.

    The script keeps each narration as a single double-quoted string
    literal (possibly preceded by whitespace and a newline). This regex
    matches that shape; if the source layout changes to backticks or
    concatenated strings, update the pattern here.
    """
    text = ts_path.read_text()
    # Match:  narration: "any non-quote chars or escaped quote"
    pattern = re.compile(r'narration:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
    narrations = [m.group(1) for m in pattern.finditer(text)]
    # Unescape standard JSON-style escapes
    narrations = [n.replace("\\\"", '"').replace("\\n", " ").replace("\\\\", "\\") for n in narrations]
    if len(narrations) != 12:
        print(f"⚠ expected 12 narrations, found {len(narrations)}")
    return narrations


def _check_subscription(api_key: str) -> None:
    """Print remaining ElevenLabs character allowance before generating."""
    try:
        r = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"⚠ could not reach ElevenLabs subscription endpoint: {exc}")
        return

    if r.status_code != 200:
        print(f"⚠ subscription check returned HTTP {r.status_code}: {r.text[:200]}")
        return

    info     = r.json()
    used     = info.get("character_count", 0)
    limit    = info.get("character_limit", 0)
    tier     = info.get("tier", "?")
    remaining = max(limit - used, 0)
    pct      = (used / limit * 100) if limit else 0
    print(f"ElevenLabs subscription:")
    print(f"  tier:       {tier}")
    print(f"  used:       {used:,} / {limit:,} characters ({pct:.1f}% consumed)")
    print(f"  remaining:  {remaining:,} characters")
    print()


def _tts(api_key: str, text: str, out_path: Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text":           text,
        "model_id":       MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    out_path.write_bytes(r.content)


def main() -> int:
    api_key = _load_api_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SCRIPT_TS.exists():
        sys.exit(f"demoScript not found at {SCRIPT_TS}")

    _check_subscription(api_key)

    narrations = _parse_narrations(SCRIPT_TS)
    if not narrations:
        sys.exit("No narrations parsed — check demoScript.ts format")

    total_chars = sum(len(n) for n in narrations)
    print(f"Generating {len(narrations)} files, ~{total_chars:,} characters total")
    print(f"Voice: Adam ({VOICE_ID}) · Model: {MODEL_ID}")
    print(f"Settings: stability {VOICE_SETTINGS['stability']} · "
          f"similarity {VOICE_SETTINGS['similarity_boost']} · "
          f"style {VOICE_SETTINGS['style']} · "
          f"speaker_boost {VOICE_SETTINGS['use_speaker_boost']}")
    print()

    generated = 0
    skipped   = 0
    for i, text in enumerate(narrations[:12], start=1):
        out_path = OUT_DIR / f"step-{i:02d}.mp3"
        label    = f"step-{i:02d}"
        snippet  = text[:60].replace("\n", " ") + ("…" if len(text) > 60 else "")

        if out_path.exists():
            print(f"  ⏭  {label}  ({out_path.stat().st_size:>7,} bytes)  skipped — already exists")
            skipped += 1
            continue

        print(f"  ▶  {label}  generating…  ({len(text):>4} chars)  \"{snippet}\"")
        try:
            _tts(api_key, text, out_path)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗  {label}  FAILED: {exc}")
            continue
        size = out_path.stat().st_size
        print(f"  ✓  {label}  saved  ({size:>7,} bytes)")
        generated += 1

    print()
    print(f"Done. {generated} generated · {skipped} skipped (already on disk)")
    print(f"Output directory: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

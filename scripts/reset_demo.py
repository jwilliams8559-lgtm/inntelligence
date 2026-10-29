#!/usr/bin/env python3
"""
Nightly backstop: restore the public demo to pristine state.

Resets the demo tenant row (plan_tier=boutique, clears any stripe/subscription/
trial state), deletes any feature_trials for the demo tenant, and restores the
shared mutable config files from their committed baselines. Idempotent.

Usage (local):
    ./venv/bin/python scripts/reset_demo.py

On Railway, schedule this nightly as a Cron service:
    /app/venv/bin/python scripts/reset_demo.py
(or POST /api/admin/demo-reset with the X-Cron-Secret header.)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.demo import reset_demo  # noqa: E402

if __name__ == "__main__":
    result = reset_demo()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)

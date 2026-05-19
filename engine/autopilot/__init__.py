"""
engine/autopilot — Autopilot rate publishing + demand alerts (Phase 8).

Public API:
    run_autopilot(property_id, mock=False) -> dict
    run_alert_checks(property_id) -> list[dict]
    generate_autopilot_report(property_id, weeks=1) -> dict
    dismiss_alert(alert_id) -> bool
    list_alerts(property_id, *, unread_only=True, limit=50) -> list[dict]
    upsert_autopilot_config(...) -> dict
"""
from __future__ import annotations

from engine.autopilot.autopilot import (
    dismiss_alert,
    generate_autopilot_report,
    list_alerts,
    run_alert_checks,
    run_autopilot,
    upsert_autopilot_config,
)

__all__ = [
    "run_autopilot",
    "run_alert_checks",
    "generate_autopilot_report",
    "dismiss_alert",
    "list_alerts",
    "upsert_autopilot_config",
]

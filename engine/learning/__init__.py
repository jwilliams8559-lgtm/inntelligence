"""
engine/learning — Federated Learning layer for The Gracious Collection (Phase 7).

Anonymized, market-level signal extraction and aggregation. No PII, no
property-identifying information. Signals roll up by (market, month,
day_of_week) so individual properties contribute to a shared pool of
benchmarks but cannot be reconstructed from queries.

Public API:
    extract_anonymized_signals(property_id) -> int
    run_market_aggregation() -> dict
    get_market_benchmarks(market, month=None, day_of_week=None) -> dict
"""
from __future__ import annotations

from engine.learning.market_signals import (
    extract_anonymized_signals,
    get_market_benchmarks,
    run_market_aggregation,
)

__all__ = [
    "extract_anonymized_signals",
    "get_market_benchmarks",
    "run_market_aggregation",
]

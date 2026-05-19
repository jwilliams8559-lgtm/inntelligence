"""
engine/crm — Guest CRM and email marketing for The Gracious Collection (Phase 6).

Public API:
    upsert_guest(tenant_id, property_id, guest_data) -> guest_id
    update_guest_segments(tenant_id, property_id) -> {segment: count, ...}
    unsubscribe_token_for(guest_id) -> str
    consume_unsubscribe(token) -> guest_id | None

    send_campaign(campaign_id) -> send summary
    check_and_create_campaigns(property_id) -> [campaign_id, ...]
    create_draft_campaign(tenant_id, property_id, ...) -> campaign_id

The implementation talks to Supabase over REST (same as the rest of the
engine). PII columns (email_encrypted / phone_encrypted) use the same
`enc:placeholder:` envelope as engine.pms — replace with KMS in prod.
"""
from __future__ import annotations

from engine.crm.guest_manager import (
    consume_unsubscribe,
    unsubscribe_token_for,
    update_guest_segments,
    upsert_guest,
)
from engine.crm.campaigns import (
    check_and_create_campaigns,
    create_draft_campaign,
    send_campaign,
)

__all__ = [
    "upsert_guest",
    "update_guest_segments",
    "unsubscribe_token_for",
    "consume_unsubscribe",
    "send_campaign",
    "check_and_create_campaigns",
    "create_draft_campaign",
]

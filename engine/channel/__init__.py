"""
engine/channel — OTA & Channel Manager rate publishing for The Gracious Collection.

Each channel manager / direct OTA integration implements the
ChannelManagerConnector ABC defined in engine.channel.base.

Public re-exports:
    ChannelManagerConnector       — abstract base
    RateUpdate, PushResult        — dataclasses
    SiteMinderConnector           — XML OTA_HotelRateAmountNotifRQ
    DirectBookingComConnector     — Booking.com Rates API
    DirectExpediaConnector        — Expedia Partner Central API
    get_channel_connector(...)    — DB-backed factory (engine.channel.factory)
    publish_approved_rate(...)    — publisher entry point
    publish_all_pending(...)      — batch publish entry point
"""
from __future__ import annotations

from engine.channel.base import ChannelManagerConnector, PushResult, RateUpdate
from engine.channel.direct_booking import DirectBookingComConnector, DirectExpediaConnector
from engine.channel.factory import get_channel_connector
from engine.channel.publisher import publish_all_pending, publish_approved_rate
from engine.channel.siteminder import SiteMinderConnector

__all__ = [
    "ChannelManagerConnector",
    "RateUpdate",
    "PushResult",
    "SiteMinderConnector",
    "DirectBookingComConnector",
    "DirectExpediaConnector",
    "get_channel_connector",
    "publish_approved_rate",
    "publish_all_pending",
]

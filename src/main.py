"""
Entry point — wires together a presence provider, light controller and the engine.

To swap provider or controller, just change the imports and instantiation below.
No other files need to be touched.

Author: Hushen Savani
"""

import asyncio
import os

import config  # noqa: F401 — imported for side-effects (timestamps, dotenv)
from config import (
    BULB_IP,
    CLIENT_ID,
    TENANT_ID,
    POLL_FAST,
    POLL_SLOW,
    DEFAULT_BLINK_INTERVAL,
    ENABLE_QUIET_HOURS,
    QUIET_HOURS_START,
    QUIET_HOURS_END,
)

from providers.ms_teams.teams_presence_provider import TeamsPresenceProvider
from lights.wiz.wiz_light_controller import WizLightController
from engine import SyncEngine


def _resolve_cache_file() -> str:
    if os.getenv("IS_DOCKER"):
        return "/app/data/.presence_beam_token_cache.json"
    return os.path.expanduser("~/.presence_beam_token_cache.json")


def main():
    # ── Wire up provider ──────────────────────────────────────────────────────
    provider = TeamsPresenceProvider(
        client_id  = CLIENT_ID,
        tenant_id  = TENANT_ID,
        cache_file = _resolve_cache_file(),
    )

    # ── Wire up light controller ──────────────────────────────────────────────
    controller = WizLightController(
        bulb_ip                = BULB_IP,
        default_blink_interval = DEFAULT_BLINK_INTERVAL,
    )

    # ── Wire up engine ────────────────────────────────────────────────────────
    engine = SyncEngine(
        provider           = provider,
        controller         = controller,
        poll_fast          = POLL_FAST,
        poll_slow          = POLL_SLOW,
        enable_quiet_hours = ENABLE_QUIET_HOURS,
        quiet_hours_start  = QUIET_HOURS_START,
        quiet_hours_end    = QUIET_HOURS_END,
    )

    asyncio.run(engine.run())


if __name__ == "__main__":
    main()

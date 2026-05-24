"""
Sync engine — the core polling loop.

This module is provider-agnostic and light-agnostic. It orchestrates the
interaction between any BasePresenceProvider and any BaseLightController.

Features:
  - Adaptive polling (fast for non-critical statuses, slow otherwise)
  - Quiet hours support (turns off bulb, pauses polling during a time window)
  - Token expiry recovery
  - Graceful shutdown on KeyboardInterrupt

Author: Hushen Savani
"""

import asyncio
from datetime import datetime, time

from core.base_presence_provider import BasePresenceProvider
from core.base_light_controller import BaseLightController


def _parse_time(time_str: str) -> time:
    return datetime.strptime(time_str, "%H:%M").time()


def _is_quiet_hour(current: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= current <= end
    # Crosses midnight (e.g. 21:00 → 10:00)
    return current >= start or current <= end


class SyncEngine:
    """
    Generic status-to-light sync engine.

    Args:
        provider            : Any BasePresenceProvider implementation.
        controller          : Any BaseLightController implementation.
        poll_fast           : Polling interval (seconds) for non-critical statuses.
        poll_slow           : Polling interval (seconds) for everything else.
        enable_quiet_hours  : Whether to activate the quiet hours feature.
        quiet_hours_start   : Quiet window start time as "HH:MM" string.
        quiet_hours_end     : Quiet window end time as "HH:MM" string.
    """

    def __init__(
        self,
        provider:           BasePresenceProvider,
        controller:         BaseLightController,
        poll_fast:          int   = 5,
        poll_slow:          int   = 30,
        enable_quiet_hours: bool  = False,
        quiet_hours_start:  str   = "21:00",
        quiet_hours_end:    str   = "10:00",
    ):
        self._provider           = provider
        self._controller         = controller
        self._poll_fast          = poll_fast
        self._poll_slow          = poll_slow
        self._enable_quiet_hours = enable_quiet_hours
        self._quiet_start        = _parse_time(quiet_hours_start) if enable_quiet_hours else None
        self._quiet_end          = _parse_time(quiet_hours_end)   if enable_quiet_hours else None
        self._quiet_hours_start  = quiet_hours_start
        self._quiet_hours_end    = quiet_hours_end

    def _print_startup_info(self) -> None:
        print("Status → Light Sync Engine started")
        print(f"  Provider   : {type(self._provider).__name__}")
        print(f"  Controller : {type(self._controller).__name__}")
        print(f"  Poll fast  : {self._poll_fast}s  {sorted(self._provider.NON_CRITICAL_STATUSES)}")
        print(f"  Poll slow  : {self._poll_slow}s  (everything else)")
        if self._enable_quiet_hours:
            print(f"  Quiet hours: ENABLED ({self._quiet_hours_start} – {self._quiet_hours_end})")
        else:
            print("  Quiet hours: DISABLED")

    async def run(self) -> None:
        self._print_startup_info()

        self._provider.authenticate()
        print("✓ Authenticated\n")

        last_status      = None
        current_interval = self._poll_fast
        in_quiet_mode    = False

        try:
            while True:
                try:
                    # ── Quiet Hours ───────────────────────────────────────────
                    if self._enable_quiet_hours:
                        now = datetime.now().time()
                        if _is_quiet_hour(now, self._quiet_start, self._quiet_end):
                            if not in_quiet_mode:
                                print(
                                    f"  Entering quiet hours "
                                    f"({self._quiet_hours_start} – {self._quiet_hours_end}). "
                                    f"Bulb off, pausing sync."
                                )
                                await self._controller.turn_off()
                                in_quiet_mode = True
                                last_status   = None  # force re-apply on resume
                            await asyncio.sleep(self._poll_slow)
                            continue
                        else:
                            if in_quiet_mode:
                                print("  Quiet hours ended. Resuming sync.")
                                in_quiet_mode = False

                    # ── Poll presence ─────────────────────────────────────────
                    availability, activity = self._provider.get_status()

                    # ── Apply to bulb only when status changes ────────────────
                    if availability != last_status:
                        print(f"  Status : {last_status or 'startup'} → {availability} / {activity}")
                        await self._controller.apply_status(availability)
                        last_status = availability
                    else:
                        print(f"  No change : {availability} / {activity}  [next in {current_interval}s]")

                    # ── Adaptive interval ─────────────────────────────────────
                    next_interval = (
                        self._poll_fast
                        if availability in self._provider.NON_CRITICAL_STATUSES
                        else self._poll_slow
                    )
                    if next_interval != current_interval:
                        direction = "↓ slow" if next_interval == self._poll_slow else "↑ fast"
                        print(f"  Polling {direction} ({current_interval}s → {next_interval}s)")
                        current_interval = next_interval

                except RuntimeError as e:
                    if "Token expired" in str(e):
                        print("  Token expired, re-authenticating...")
                        self._provider.on_token_expired()
                    else:
                        print(f"  Error: {e}")

                await asyncio.sleep(current_interval)

        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            await self._controller.cleanup()
            print("Bye.")

"""
Philips WiZ light controller.

Controls a WiZ bulb (B22/A19/A60 etc.) over the local network using the
pywizlight library. Supports solid colors, brightness control, and blinking.

Author: Hushen Savani
"""

import asyncio
from pywizlight import wizlight, PilotBuilder

from core.base_light_controller import BaseLightController


class WizLightController(BaseLightController):
    """
    Controls a Philips WiZ smart bulb via UDP on the local network.

    STATUS_MAP keys should match the availability strings returned by your
    chosen presence provider (e.g. TeamsPresenceProvider).

    Each entry is a dict with:
        rgb             : (R, G, B) tuple  — the solid color to display
        brightness      : int 0–255        — bulb brightness
        blink           : bool             — whether to blink
        blink_interval  : float (optional) — seconds per on/off cycle (overrides default)

    A value of None means "turn the bulb off" for that status.
    """

    STATUS_MAP: dict = {
        # ── Available ─────────────────────────────────────────────────────────
        "Available":       {"rgb": (0, 255, 0),   "brightness": 180, "blink": False},
        "AvailableIdle":   {"rgb": (0, 255, 0),   "brightness": 100, "blink": False},
        # ── Busy / DND ────────────────────────────────────────────────────────
        "Busy":            {"rgb": (255, 0, 0),   "brightness": 200, "blink": False},
        "BusyIdle":        {"rgb": (255, 0, 0),   "brightness": 130, "blink": False},
        "InAMeeting":      {"rgb": (255, 0, 0),   "brightness": 200, "blink": False},
        "InACall":         {"rgb": (255, 0, 0),   "brightness": 200, "blink": True},
        "DoNotDisturb":    {"rgb": (255, 0, 0),   "brightness": 200, "blink": True},
        "Presenting":      {"rgb": (255, 0, 0),   "brightness": 255, "blink": True,  "blink_interval": 0.4},
        # ── Away ──────────────────────────────────────────────────────────────
        "Away":            {"rgb": (255, 200, 0), "brightness": 150, "blink": False},
        "BeRightBack":     {"rgb": (255, 200, 0), "brightness": 100, "blink": False},
        # ── Focus ─────────────────────────────────────────────────────────────
        "Focusing":        {"rgb": (0, 80, 255),  "brightness": 160, "blink": False},
        # ── Off / Unknown ─────────────────────────────────────────────────────
        "Offline":         None,
        "PresenceUnknown": {"rgb": (255, 0, 0),   "brightness": 200, "blink": True},
    }

    def __init__(self, bulb_ip: str, default_blink_interval: float = 0.7):
        self._bulb_ip                = bulb_ip
        self._default_blink_interval = default_blink_interval
        self._light: wizlight | None  = None   # created lazily inside the event loop
        self._blink_task: asyncio.Task | None = None
        self._blink_stop: asyncio.Event | None = None

    def _get_light(self) -> wizlight:
        """Return the wizlight instance, creating it on first call (inside the event loop)."""
        if self._light is None:
            self._light = wizlight(self._bulb_ip)
        return self._light

    # ── Blink helpers ─────────────────────────────────────────────────────────

    async def _blink_loop(self, rgb: tuple, brightness: int, interval: float, stop_event: asyncio.Event):
        pilot_on = PilotBuilder(rgb=rgb, brightness=brightness)
        light = self._get_light()
        while not stop_event.is_set():
            await light.turn_on(pilot_on)
            await asyncio.sleep(interval)
            if stop_event.is_set():
                break
            await light.turn_off()
            await asyncio.sleep(interval)

    async def _stop_blink(self):
        if self._blink_task and not self._blink_task.done():
            self._blink_stop.set()
            await self._blink_task
        self._blink_task = None
        self._blink_stop = None

    # ── BaseLightController interface ─────────────────────────────────────────

    async def apply_status(self, status: str) -> None:
        await self._stop_blink()
        light  = self._get_light()
        config = self.STATUS_MAP.get(status)

        if config is None:
            await light.turn_off()
            print(f"  Bulb → OFF  [{status}]")

        elif config["blink"]:
            interval         = config.get("blink_interval", self._default_blink_interval)
            self._blink_stop = asyncio.Event()
            self._blink_task = asyncio.create_task(
                self._blink_loop(config["rgb"], config["brightness"], interval, self._blink_stop)
            )
            print(f"  Bulb → BLINKING RGB{config['rgb']} interval={interval}s  [{status}]")

        else:
            await light.turn_on(PilotBuilder(rgb=config["rgb"], brightness=config["brightness"]))
            print(f"  Bulb → RGB{config['rgb']} brightness={config['brightness']}  [{status}]")

    async def turn_off(self) -> None:
        await self._stop_blink()
        await self._get_light().turn_off()
        print("  Bulb → OFF")

    async def cleanup(self) -> None:
        await self._stop_blink()
        if self._light is not None:
            await self._light.turn_off()
            await self._light.async_close()
        print("  Bulb connection closed.")

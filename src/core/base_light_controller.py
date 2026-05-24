"""
Base class for all smart light/bulb controllers (e.g. Philips WiZ, TP-Link Tapo, Govee).

To add a new light controller:
1. Create a new folder under src/lights/<your_bulb_brand>/
2. Subclass BaseLightController
3. Implement all abstract methods using your bulb's SDK or API
4. Wire it up in src/main.py

Author: Hushen Savani
"""

from abc import ABC, abstractmethod


class BaseLightController(ABC):
    """
    Abstract base class for a smart light controller.

    A controller is responsible for:
    - Translating a generic status string into a light effect
      (color, brightness, blink, etc.)
    - Applying that effect to the physical bulb
    - Turning the bulb off
    - Cleaning up resources on shutdown

    The STATUS_MAP is the core mapping that each controller must define.
    Keys are generic status strings (e.g. "Busy", "Available").
    Values are controller-specific dicts describing the desired light state.
    """

    # ── Status → Light effect map ─────────────────────────────────────────────
    # Override this dict in your subclass.
    # The engine passes status strings from the presence provider directly
    # into apply_status(), so make sure your keys match what your chosen
    # provider returns from get_status().
    STATUS_MAP: dict = {}

    @abstractmethod
    async def apply_status(self, status: str) -> None:
        """
        Apply the light effect that corresponds to `status`.
        If the status is not in STATUS_MAP (or maps to None), turn the bulb off.

        Args:
            status: The availability string returned by the presence provider.
        """
        ...

    @abstractmethod
    async def turn_off(self) -> None:
        """
        Unconditionally turn the bulb off and stop any ongoing effects (e.g. blink tasks).
        Called at the start of quiet hours and on shutdown.
        """
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Release any resources held by the controller (sockets, background tasks, etc.).
        Called once when the engine shuts down.
        """
        ...

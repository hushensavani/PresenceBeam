"""
Base class for all presence/status providers (e.g. MS Teams, Slack, Zoom).

To add a new provider:
1. Create a new folder under src/providers/<your_provider>/
2. Subclass BasePresenceProvider
3. Implement all abstract methods
4. Wire it up in src/main.py

Author: Hushen Savani
"""

from abc import ABC, abstractmethod


class BasePresenceProvider(ABC):
    """
    Abstract base class for a presence/status provider.

    A provider is responsible for:
    - Authenticating with a communication platform (Teams, Slack, etc.)
    - Polling the user's current availability status
    - Defining which statuses are "non-critical" (for adaptive polling)
    """

    # ── Status that are considered non-critical (fast polling) ────────────────
    # Override this in your subclass to define your platform's non-critical statuses.
    NON_CRITICAL_STATUSES: set[str] = set()

    @abstractmethod
    def authenticate(self) -> None:
        """
        Perform any authentication or session initialisation required.
        This is called once at startup before the polling loop begins.
        Raise a RuntimeError if authentication fails.
        """
        ...

    @abstractmethod
    def get_status(self) -> tuple[str, str]:
        """
        Fetch the user's current status from the provider.

        Returns:
            A tuple of (availability: str, activity: str).
            e.g. ("Busy", "InACall") for MS Teams,
                 ("active", "in_a_meeting") for Slack.

        Raise a RuntimeError("Token expired") to trigger a re-authentication.
        Raise any other RuntimeError for general fetch failures.
        """
        ...

    def on_token_expired(self) -> None:
        """
        Called by the engine when a "Token expired" RuntimeError is caught.
        Default implementation re-runs authenticate(). Override if needed.
        """
        self.authenticate()

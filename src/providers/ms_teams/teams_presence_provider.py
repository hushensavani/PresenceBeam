"""
Microsoft Teams presence provider.

Uses the Microsoft Graph API (device-flow auth via MSAL) to poll the
authenticated user's availability and activity status.

Author: Hushen Savani
"""

import os
import requests
import msal

from core.base_presence_provider import BasePresenceProvider


GRAPH_SCOPES = ["Presence.Read"]


class TeamsPresenceProvider(BasePresenceProvider):
    """
    Fetches presence status from Microsoft Teams via the Microsoft Graph API.

    Required env vars (loaded via config.py / .env):
        CLIENT_ID  — Azure App Registration client ID
        TENANT_ID  — Azure tenant ID
        IS_DOCKER  — set automatically in Dockerfile; controls cache file path
    """

    # ── Non-critical statuses for adaptive polling ────────────────────────────
    # When the user is in one of these states, the engine uses POLL_FAST.
    # All other statuses use POLL_SLOW.
    NON_CRITICAL_STATUSES: set[str] = {"Available", "AvailableIdle", "Focusing"}

    def __init__(self, client_id: str, tenant_id: str, cache_file: str):
        self._client_id   = client_id
        self._tenant_id   = tenant_id
        self._cache_file  = cache_file
        self._access_token: str | None = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _save_cache(self, cache: msal.SerializableTokenCache) -> None:
        if cache.has_state_changed:
            with open(self._cache_file, "w") as f:
                f.write(cache.serialize())
            os.chmod(self._cache_file, 0o600)

    def _build_app(self, cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
        return msal.PublicClientApplication(
            client_id=self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            token_cache=cache,
        )

    # ── BasePresenceProvider interface ────────────────────────────────────────

    def authenticate(self) -> None:
        """
        Authenticate using a cached refresh token if available, otherwise
        initiate a device-flow login (prints a URL + code to stdout).
        Stores the resulting access token internally.
        """
        cache = msal.SerializableTokenCache()
        if os.path.exists(self._cache_file):
            with open(self._cache_file, "r") as f:
                cache.deserialize(f.read())

        app = self._build_app(cache)

        # Try silent auth first
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._save_cache(cache)
                self._access_token = result["access_token"]
                return

        # Device flow (first run or expired refresh token)
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to create device flow: {flow.get('error_description')}")

        print("\n" + "=" * 50)
        print("ACTION REQUIRED: Authenticate with Microsoft")
        print("=" * 50)
        print(flow["message"])
        print("=" * 50 + "\n")

        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Auth failed: {result.get('error_description')}")

        self._save_cache(cache)
        self._access_token = result["access_token"]

    def get_status(self) -> tuple[str, str]:
        """
        Fetch presence from the Microsoft Graph API.

        Returns:
            (availability, activity) — e.g. ("Busy", "InACall")

        Raises:
            RuntimeError("Token expired") — triggers re-auth in the engine.
            RuntimeError(...)             — general Graph API error.
        """
        if not self._access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        url     = "https://graph.microsoft.com/v1.0/me/presence"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        resp    = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 401:
            raise RuntimeError("Token expired")
        if not resp.ok:
            raise RuntimeError(f"Graph API error {resp.status_code}: {resp.text}")

        data = resp.json()
        return (
            data.get("availability", "PresenceUnknown"),
            data.get("activity", "Unknown"),
        )

    def on_token_expired(self) -> None:
        """Re-authenticate silently using the cached refresh token."""
        self.authenticate()

# Contributing to PresenceBeam

Thank you for your interest in contributing! PresenceBeam is designed from the ground up to be extended — adding a new communication platform or a new smart bulb is a focused, self-contained task that doesn't require touching the core engine at all.

This guide walks you through everything you need to know.

---

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Project Architecture](#project-architecture)
- [Development Setup](#development-setup)
- [Adding a New Presence Provider](#adding-a-new-presence-provider)
  - [Full Example: Slack](#full-example-slack)
  - [Full Example: Zoom](#full-example-zoom)
  - [Presence Provider Checklist](#presence-provider-checklist)
- [Adding a New Light Controller](#adding-a-new-light-controller)
  - [Full Example: TP-Link Tapo](#full-example-tp-link-tapo)
  - [Full Example: Govee](#full-example-govee)
  - [Light Controller Checklist](#light-controller-checklist)
- [Key Design Rules](#key-design-rules)
- [Submitting a Pull Request](#submitting-a-pull-request)

---

## Ways to Contribute

| Type | Examples |
|---|---|
| **New presence provider** | Slack, Zoom, Google Chat, Webex, Discord |
| **New light controller** | TP-Link Tapo, Govee, LIFX, Nanoleaf, Yeelight |
| **Core engine improvements** | Better error handling, retry logic, logging |
| **Bug fixes** | Anything broken — open an issue or send a PR |
| **Documentation** | Typos, clarity, missing details |

---

## Project Architecture

Before writing any code, read [`AGENTS.md`](AGENTS.md). It describes the full architecture, component responsibilities, engine behaviour, and key design rules that every contributor must follow.

The short version: the `SyncEngine` in `engine.py` drives everything and knows nothing about any specific platform or bulb. It talks only to two abstract base classes:

- `BasePresenceProvider` — defines `authenticate()`, `get_status()`, `on_token_expired()`
- `BaseLightController` — defines `apply_status()`, `turn_off()`, `cleanup()`

Your job as a contributor is to implement one (or both) of these abstractions. You will not need to touch `engine.py`, `config.py`, or any existing provider/controller.

---

## Development Setup

```bash
# Clone the repo
git clone https://github.com/your-username/PresenceBeam.git
cd PresenceBeam

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and fill in the config
cp .env.example .env
```

Edit `.env` with a real bulb IP and Azure credentials (see [`README.md`](README.md) for setup instructions), then run:

```bash
python src/main.py
```

---

## Adding a New Presence Provider

A presence provider fetches the user's current availability from a communication platform and returns it as a string (e.g. `"Available"`, `"Busy"`, `"Offline"`).

### File Structure

```
src/providers/<platform>/
├── __init__.py                        # Empty file — makes it a package
└── <platform>_presence_provider.py   # Your implementation
```

### The Contract

Subclass `BasePresenceProvider` from `core/base_presence_provider.py` and implement three methods:

```python
from core.base_presence_provider import BasePresenceProvider

class MyProvider(BasePresenceProvider):

    # Statuses where polling should be fast (POLL_FAST seconds).
    # All other statuses use POLL_SLOW. Be conservative — only truly
    # "idle" statuses (user is free and waiting) belong here.
    NON_CRITICAL_STATUSES: set[str] = {"Available"}

    def authenticate(self) -> None:
        """Authenticate with the platform. Called once on startup."""
        ...

    def get_status(self) -> tuple[str, str]:
        """
        Poll the platform and return (availability, activity).
        - availability: the primary status string (passed to the light controller)
        - activity: secondary info (logged, not used by the engine)
        Raise RuntimeError("Token expired") if the auth token needs refreshing.
        """
        ...

    def on_token_expired(self) -> None:
        """Called by the engine when get_status() raises RuntimeError("Token expired")."""
        self.authenticate()
```

### Full Example: Slack

Slack exposes presence via its Web API (`users.getPresence`). The two possible values are `"active"` and `"away"`.

**Step 1** — Create the module files:

```
src/providers/slack/__init__.py
src/providers/slack/slack_presence_provider.py
```

**Step 2** — Implement the provider:

```python
# src/providers/slack/slack_presence_provider.py

import requests
from core.base_presence_provider import BasePresenceProvider


class SlackPresenceProvider(BasePresenceProvider):
    """Fetches user presence from the Slack Web API."""

    NON_CRITICAL_STATUSES: set[str] = {"active"}

    _API_URL = "https://slack.com/api/users.getPresence"

    def __init__(self, token: str):
        self._token = token

    def authenticate(self) -> None:
        # Slack uses a static bot/user token — nothing to do at startup.
        # Validate the token is present so we fail fast.
        if not self._token:
            raise RuntimeError("SLACK_TOKEN is not set")

    def get_status(self) -> tuple[str, str]:
        response = requests.get(
            self._API_URL,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=10,
        )

        if response.status_code == 401:
            raise RuntimeError("Token expired")

        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error')}")

        presence = data["presence"]   # "active" or "away"
        return presence, presence

    def on_token_expired(self) -> None:
        # Static tokens don't expire in the traditional sense.
        # Log and re-raise so the operator knows to rotate the token.
        raise RuntimeError("Slack token is invalid. Set a new SLACK_TOKEN in .env")
```

**Step 3** — Add `SLACK_TOKEN` to `.env.example`:

```env
# Slack Bot/User OAuth Token (xoxb-... or xoxp-...)
SLACK_TOKEN=xoxb-your-token-here
```

**Step 4** — Wire it up in `src/main.py` (two lines):

```python
# Replace:
from providers.ms_teams.teams_presence_provider import TeamsPresenceProvider
provider = TeamsPresenceProvider(client_id=CLIENT_ID, tenant_id=TENANT_ID, cache_file=CACHE_FILE)

# With:
from providers.slack.slack_presence_provider import SlackPresenceProvider
provider = SlackPresenceProvider(token=os.getenv("SLACK_TOKEN", ""))
```

> **Note on `STATUS_MAP` alignment:** Slack returns `"active"` and `"away"`. Make sure the light controller's `STATUS_MAP` has keys for these exact strings — or map them to the existing Teams keys (e.g. `"active"` → `"Available"`) inside your provider's `get_status()` before returning.

---

### Full Example: Zoom

Zoom presence is available via the Zoom REST API (`/users/me/presence_status`). Possible values include `"Available"`, `"Away"`, `"Do_Not_Disturb"`, `"In_Meeting"`, `"Presenting"`, `"On_Phone_Call"`.

**Step 1** — Create the module files:

```
src/providers/zoom/__init__.py
src/providers/zoom/zoom_presence_provider.py
```

**Step 2** — Implement the provider:

```python
# src/providers/zoom/zoom_presence_provider.py

import requests
from core.base_presence_provider import BasePresenceProvider


class ZoomPresenceProvider(BasePresenceProvider):
    """Fetches user presence from the Zoom REST API using a Server-to-Server OAuth token."""

    NON_CRITICAL_STATUSES: set[str] = {"Available"}

    _TOKEN_URL  = "https://zoom.us/oauth/token"
    _STATUS_URL = "https://api.zoom.us/v2/users/me/presence_status"

    def __init__(self, account_id: str, client_id: str, client_secret: str):
        self._account_id    = account_id
        self._client_id     = client_id
        self._client_secret = client_secret
        self._access_token: str = ""

    def authenticate(self) -> None:
        resp = requests.post(
            self._TOKEN_URL,
            params={"grant_type": "account_credentials", "account_id": self._account_id},
            auth=(self._client_id, self._client_secret),
            timeout=10,
        )
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]

    def get_status(self) -> tuple[str, str]:
        resp = requests.get(
            self._STATUS_URL,
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=10,
        )

        if resp.status_code == 401:
            raise RuntimeError("Token expired")

        resp.raise_for_status()
        status = resp.json().get("status", "Away")
        return status, status

    def on_token_expired(self) -> None:
        self.authenticate()
```

**Step 3** — Add variables to `.env.example`:

```env
# Zoom Server-to-Server OAuth credentials
ZOOM_ACCOUNT_ID=your_account_id
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret
```

**Step 4** — Wire it up in `src/main.py`:

```python
from providers.zoom.zoom_presence_provider import ZoomPresenceProvider
provider = ZoomPresenceProvider(
    account_id=os.getenv("ZOOM_ACCOUNT_ID", ""),
    client_id=os.getenv("ZOOM_CLIENT_ID", ""),
    client_secret=os.getenv("ZOOM_CLIENT_SECRET", ""),
)
```

---

### Presence Provider Checklist

Before opening a PR, confirm:

- [ ] Module lives under `src/providers/<platform>/`
- [ ] `__init__.py` exists (can be empty)
- [ ] Class subclasses `BasePresenceProvider`
- [ ] `NON_CRITICAL_STATUSES` is defined and contains only statuses where the user is idle/free
- [ ] `get_status()` returns `(availability, activity)` as a tuple of strings
- [ ] `get_status()` raises `RuntimeError("Token expired")` — exact string — on auth failure (401)
- [ ] `on_token_expired()` re-authenticates (calls `self.authenticate()` or equivalent)
- [ ] The availability strings returned by `get_status()` are documented so light controller authors can align their `STATUS_MAP`
- [ ] New env vars are added to `.env.example` with comments
- [ ] `README.md` Current Implementation table is updated

---

## Adding a New Light Controller

A light controller translates an availability string into a physical bulb state (color, brightness, blinking).

### File Structure

```
src/lights/<bulb>/
├── __init__.py                   # Empty file — makes it a package
└── <bulb>_light_controller.py   # Your implementation
```

### The Contract

Subclass `BaseLightController` from `core/base_light_controller.py` and implement three async methods:

```python
from core.base_light_controller import BaseLightController

class MyController(BaseLightController):

    # Maps availability strings (from the provider) to bulb settings.
    # A value of None means "turn the bulb off".
    # Unknown keys also result in the bulb being turned off (safe default).
    STATUS_MAP: dict = {
        "Available": {...},
        "Busy":      {...},
        "Offline":   None,
    }

    async def apply_status(self, status: str) -> None:
        """Apply the given availability status to the bulb."""
        ...

    async def turn_off(self) -> None:
        """Turn the bulb off completely."""
        ...

    async def cleanup(self) -> None:
        """Release connections or resources on shutdown."""
        ...
```

> **Critical:** Do NOT create SDK/hardware objects in `__init__()`. Create them lazily inside the first async call. See [Key Design Rules](#key-design-rules) for why.

---

### Full Example: TP-Link Tapo

TP-Link Tapo bulbs (e.g. L530) can be controlled using the [`PyP100`](https://github.com/almottier/TapoP100) library.

**Step 1** — Create the module files:

```
src/lights/tplink/__init__.py
src/lights/tplink/tplink_light_controller.py
```

**Step 2** — Implement the controller:

```python
# src/lights/tplink/tplink_light_controller.py

import asyncio
from PyP100 import PyL530
from core.base_light_controller import BaseLightController


class TplinkLightController(BaseLightController):
    """Controls a TP-Link Tapo L530 color bulb."""

    # RGB tuples + brightness (0–100). None = turn off.
    STATUS_MAP: dict = {
        "Available":      {"rgb": (0, 255, 0),   "brightness": 70},
        "AvailableIdle":  {"rgb": (0, 255, 0),   "brightness": 40},
        "Busy":           {"rgb": (255, 0, 0),   "brightness": 80},
        "BusyIdle":       {"rgb": (255, 0, 0),   "brightness": 50},
        "InAMeeting":     {"rgb": (255, 0, 0),   "brightness": 80},
        "InACall":        {"rgb": (255, 0, 0),   "brightness": 80},
        "DoNotDisturb":   {"rgb": (255, 0, 0),   "brightness": 80},
        "Presenting":     {"rgb": (255, 0, 0),   "brightness": 100},
        "Away":           {"rgb": (255, 200, 0), "brightness": 60},
        "BeRightBack":    {"rgb": (255, 200, 0), "brightness": 40},
        "Focusing":       {"rgb": (0, 100, 255), "brightness": 60},
        "Offline":        None,
        "PresenceUnknown": {"rgb": (255, 0, 0),  "brightness": 80},
    }

    def __init__(self, bulb_ip: str, username: str, password: str):
        self._bulb_ip  = bulb_ip
        self._username = username
        self._password = password
        self._bulb     = None   # Lazy — created on first async call

    def _get_bulb(self) -> PyL530.L530:
        if self._bulb is None:
            self._bulb = PyL530.L530(self._bulb_ip, self._username, self._password)
            self._bulb.handshake()
            self._bulb.login()
        return self._bulb

    async def apply_status(self, status: str) -> None:
        config = self.STATUS_MAP.get(status)
        if config is None:
            await self.turn_off()
            return

        bulb = await asyncio.get_event_loop().run_in_executor(None, self._get_bulb)
        r, g, b = config["rgb"]
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: (
                bulb.setBrightness(config["brightness"]),
                bulb.setColor(r, g, b),
                bulb.turnOn(),
            )
        )

    async def turn_off(self) -> None:
        bulb = await asyncio.get_event_loop().run_in_executor(None, self._get_bulb)
        await asyncio.get_event_loop().run_in_executor(None, bulb.turnOff)

    async def cleanup(self) -> None:
        self._bulb = None
```

**Step 3** — Add to `requirements.txt`:

```
PyP100
```

**Step 4** — Add variables to `.env.example`:

```env
# TP-Link Tapo credentials (your Tapo app account email + password)
TAPO_USERNAME=your@email.com
TAPO_PASSWORD=your_password
```

**Step 5** — Wire it up in `src/main.py`:

```python
from lights.tplink.tplink_light_controller import TplinkLightController
controller = TplinkLightController(
    bulb_ip=os.getenv("BULB_IP", ""),
    username=os.getenv("TAPO_USERNAME", ""),
    password=os.getenv("TAPO_PASSWORD", ""),
)
```

---

### Full Example: Govee

Govee bulbs support local LAN control over UDP on port 4003. The community library [`govee-led-wax9`](https://github.com/wez/govee2mqtt) or direct UDP can be used.

**Step 1** — Create the module files:

```
src/lights/govee/__init__.py
src/lights/govee/govee_light_controller.py
```

**Step 2** — Implement the controller (sketch — adjust for your chosen Govee library):

```python
# src/lights/govee/govee_light_controller.py

import asyncio
from core.base_light_controller import BaseLightController


class GoveeLightController(BaseLightController):
    """Controls a Govee color bulb via local LAN API."""

    # HSV: hue (0–360), saturation (0–100), value/brightness (0–100)
    STATUS_MAP: dict = {
        "Available":      {"hsv": (120, 100, 70)},   # green
        "AvailableIdle":  {"hsv": (120, 60,  40)},   # dim green
        "Busy":           {"hsv": (0,   100, 80)},   # red
        "BusyIdle":       {"hsv": (0,   80,  50)},   # dim red
        "InAMeeting":     {"hsv": (0,   100, 80)},
        "InACall":        {"hsv": (0,   100, 80)},
        "DoNotDisturb":   {"hsv": (0,   100, 80)},
        "Presenting":     {"hsv": (0,   100, 100)},
        "Away":           {"hsv": (45,  100, 60)},   # yellow
        "BeRightBack":    {"hsv": (45,  80,  40)},
        "Focusing":       {"hsv": (210, 100, 60)},   # blue
        "Offline":        None,
        "PresenceUnknown": {"hsv": (0,  100, 80)},
    }

    def __init__(self, bulb_ip: str):
        self._bulb_ip = bulb_ip
        self._client  = None   # Lazy init

    async def _get_client(self):
        if self._client is None:
            # Replace with your chosen Govee LAN library init
            from govee_lan import GoveeClient
            self._client = GoveeClient(self._bulb_ip)
            await self._client.connect()
        return self._client

    async def apply_status(self, status: str) -> None:
        config = self.STATUS_MAP.get(status)
        if config is None:
            await self.turn_off()
            return
        client = await self._get_client()
        h, s, v = config["hsv"]
        await client.set_color_hsv(h, s, v)
        await client.turn_on()

    async def turn_off(self) -> None:
        client = await self._get_client()
        await client.turn_off()

    async def cleanup(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None
```

**Step 3** — Wire it up in `src/main.py`:

```python
from lights.govee.govee_light_controller import GoveeLightController
controller = GoveeLightController(bulb_ip=os.getenv("BULB_IP", ""))
```

---

### Light Controller Checklist

Before opening a PR, confirm:

- [ ] Module lives under `src/lights/<bulb>/`
- [ ] `__init__.py` exists (can be empty)
- [ ] Class subclasses `BaseLightController`
- [ ] `STATUS_MAP` is defined and keys cover all statuses your target provider returns
- [ ] `STATUS_MAP` uses `None` for statuses that should turn the bulb off
- [ ] `apply_status()` falls back to `turn_off()` for unknown/`None` statuses
- [ ] Hardware SDK objects are **not** created in `__init__()` — lazy init only
- [ ] `cleanup()` releases connections/sockets on shutdown
- [ ] New dependencies added to `requirements.txt`
- [ ] New env vars added to `.env.example` with comments
- [ ] `README.md` Current Implementation table is updated

---

## Key Design Rules

These rules are load-bearing. Violating them causes subtle, hard-to-debug failures.

### 1. Lazy-initialize hardware SDKs

Any library that opens a socket or uses `asyncio` internally must **not** be instantiated in `__init__()`. Create it inside the first async method call instead.

```python
# WRONG — will crash with "Future attached to a different loop"
def __init__(self, ip):
    self._bulb = SomeSdk(ip)   # asyncio object created outside the event loop

# CORRECT — created lazily inside the running event loop
def __init__(self, ip):
    self._ip   = ip
    self._bulb = None

async def _get_bulb(self):
    if self._bulb is None:
        self._bulb = SomeSdk(self._ip)  # safe — we're inside the event loop now
    return self._bulb
```

### 2. Signal token expiry with the exact string `"Token expired"`

The engine catches `RuntimeError` and checks the message. The exact string `"Token expired"` triggers `on_token_expired()`. Any other message is logged as a transient error and skipped.

```python
# In get_status():
if response.status_code == 401:
    raise RuntimeError("Token expired")   # exact string — don't change it
```

### 3. `STATUS_MAP` keys must match `get_status()` return values

The engine passes `availability` directly from the provider into `controller.apply_status()`. If the key is missing from `STATUS_MAP`, the bulb turns off — which is the safe default, but will be confusing. Always document what strings your provider returns.

### 4. `apply_status()` must handle unknown statuses gracefully

Always have a fallback to `turn_off()` for any key not in your `STATUS_MAP`:

```python
async def apply_status(self, status: str) -> None:
    config = self.STATUS_MAP.get(status)
    if config is None:
        await self.turn_off()
        return
    # ... apply config
```

### 5. `NON_CRITICAL_STATUSES` drives polling speed

Statuses in this set use `POLL_FAST` (default: 5s). All others use `POLL_SLOW` (default: 30s). Only include statuses where the user is genuinely idle and no rapid change is expected (e.g. `"Available"`). Meeting/call statuses should be absent so the engine polls slowly and reduces API load.

---

## Submitting a Pull Request

1. **Fork** the repository and create a branch: `git checkout -b add-slack-provider`
2. **Implement** your provider or controller following the checklists above
3. **Test** it end-to-end with a real account and real bulb if possible; otherwise document what you tested
4. **Update `README.md`** — add your integration to the Current Implementation table (even if it's a "community" entry)
5. **Open a PR** with a clear title (e.g. `feat: add Slack presence provider`) and describe:
   - What platform/bulb you added
   - Any credentials or app registrations the user needs to set up
   - How you tested it

If you're unsure about anything, open a draft PR and ask — contributions at any stage are welcome.

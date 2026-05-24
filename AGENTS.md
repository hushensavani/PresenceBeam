# AGENTS.md

This file provides context for AI agents and contributors working in this repository.
Read this file before making any code changes.

---

## Project Overview

**PresenceBeam** is an open-source, extensible daemon that polls a user's
availability status from a workplace communication platform (e.g. Microsoft Teams,
Slack) and reflects that status in real-time on a smart light bulb (e.g. Philips
WiZ, TP-Link Tapo, Govee).

The project is deliberately **provider-agnostic** and **controller-agnostic**. The
core engine contains zero platform-specific or bulb-specific code. All concrete
integrations live in isolated modules under `src/providers/` and `src/lights/`.

---

## Repository Layout

```
PresenceBeam/
├── src/
│   ├── config.py                        # Env-driven config + global timestamp patch
│   ├── engine.py                        # Core polling loop (provider/controller agnostic)
│   ├── main.py                          # Entry point — wires provider + controller → engine
│   │
│   ├── core/
│   │   ├── base_presence_provider.py    # ABC for all presence providers
│   │   └── base_light_controller.py     # ABC for all light controllers
│   │
│   ├── providers/
│   │   └── ms_teams/
│   │       └── teams_presence_provider.py  # Microsoft Teams via Graph API
│   │
│   └── lights/
│       └── wiz/
│           └── wiz_light_controller.py     # Philips WiZ via pywizlight (UDP)
│
├── data/                    # Runtime data (token cache); volume-mounted in Docker
├── Dockerfile               # python:3.11-slim; sets IS_DOCKER=1
├── docker-compose.yml       # Reads .env via env_file; mounts ./data:/app/data
├── requirements.txt         # pip dependencies
├── .env.example             # Template — copy to .env and fill in secrets
├── .gitignore               # Excludes .env, .venv, data cache, __pycache__
├── CONTRIBUTING.md          # How to add new providers and light controllers
└── LICENSE                  # MIT
```

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                         main.py                            │
│  Instantiates provider, controller, engine and calls run() │
└──────────────┬─────────────────────────┬───────────────────┘
               │                         │
               ▼                         ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│  BasePresenceProvider│   │     BaseLightController       │
│  (ABC — core/)       │   │     (ABC — core/)             │
│                      │   │                               │
│  + authenticate()    │   │  + apply_status(status) async │
│  + get_status()      │   │  + turn_off()           async │
│  + on_token_expired()│   │  + cleanup()            async │
│  NON_CRITICAL_STATUSES   │  STATUS_MAP: dict             │
└──────────┬───────────┘   └──────────────┬────────────────┘
           │                              │
           │  (concrete implementations)  │
           ▼                              ▼
  TeamsPresenceProvider          WizLightController
  providers/ms_teams/            lights/wiz/
           │                              │
           └──────────┬───────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  SyncEngine   │
              │  engine.py    │
              └───────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|---|---|---|
| `SyncEngine` | `engine.py` | Adaptive polling loop, quiet hours, token refresh recovery, graceful shutdown |
| `BasePresenceProvider` | `core/base_presence_provider.py` | Contract for all presence integrations |
| `BaseLightController` | `core/base_light_controller.py` | Contract for all light integrations |
| `TeamsPresenceProvider` | `providers/ms_teams/teams_presence_provider.py` | MSAL device-flow auth + Graph API polling |
| `WizLightController` | `lights/wiz/wiz_light_controller.py` | pywizlight UDP control, blink loop, lazy init |
| `config.py` | `src/config.py` | Loads `.env`, exposes typed constants, patches `builtins.print` with timestamps |
| `main.py` | `src/main.py` | Wires all components, resolves cache file path, runs `asyncio.run()` |

---

## Engine Behaviour (SyncEngine)

The engine (`engine.py`) is the core loop. It has **no knowledge** of Microsoft,
WiZ, or any specific integration. It only operates on the abstractions.

### Polling Loop

1. **Quiet Hours check** (if enabled): If current time falls within the quiet
   window, call `controller.turn_off()` **once**, set `in_quiet_mode = True`,
   then sleep and `continue`. No provider API calls are made during quiet hours.
   When quiet hours end, `in_quiet_mode` resets and syncing resumes immediately.

2. **Presence poll**: Call `provider.get_status()` → returns `(availability, activity)`.

3. **Change detection**: Call `controller.apply_status(availability)` **only if**
   `availability` changed since the last iteration. This avoids redundant bulb
   commands.

4. **Adaptive interval**: Use `POLL_FAST` if `availability` is in
   `provider.NON_CRITICAL_STATUSES`, otherwise use `POLL_SLOW`.

5. **Error recovery**: A `RuntimeError("Token expired")` calls
   `provider.on_token_expired()`. Other `RuntimeError`s are logged and skipped.

6. **Shutdown**: `KeyboardInterrupt` triggers `controller.cleanup()`.

---

## Key Design Rules

1. **`wizlight` must be instantiated inside the asyncio event loop.**
   `WizLightController.__init__()` does NOT create the `wizlight` instance.
   It uses a lazy `_get_light()` helper that creates it on first async call.
   Breaking this causes: `"Future attached to a different loop"`.

2. **`config.py` must be imported first in `main.py`** (or at least before any
   `print()` calls) because it patches `builtins.print` globally to add timestamps.

3. **`IS_DOCKER=1`** is baked into the `Dockerfile` via `ENV IS_DOCKER=1`.
   `main.py` uses this to switch the token cache path:
   - Docker: `/app/data/.status_light_token_cache.json`
   - Local:  `~/.status_light_token_cache.json`

4. **`STATUS_MAP` keys must match `get_status()` return values.**
   The engine passes `availability` strings directly from the provider into
   `controller.apply_status()`. If the keys don't align, the bulb turns off
   (which is the safe default for an unknown status).

5. **Quiet hours time format is `"HH:MM"` (24-hour).** Parsed by
   `datetime.strptime(time_str, "%H:%M")`. Windows crossing midnight are supported
   (e.g. `21:00` to `10:00`).

6. **`ENABLE_QUIET_HOURS`** is truthy if the env value is `"true"`, `"1"`, or
   `"yes"` (case-insensitive). Any other value (including `"False"`) disables it.

---

## Configuration Reference

All configuration is read from environment variables. Use a `.env` file locally
(see `.env.example`). In Docker, `env_file: .env` in `docker-compose.yml` injects
them without baking secrets into the image.

| Variable | Required | Default | Description |
|---|---|---|---|
| `BULB_IP` | ✅ | — | IP address of the smart bulb on the local network |
| `CLIENT_ID` | ✅ | — | Azure App Registration client ID |
| `TENANT_ID` | ✅ | — | Azure tenant ID |
| `POLL_FAST` | ❌ | `5` | Polling interval (seconds) for non-critical statuses |
| `POLL_SLOW` | ❌ | `30` | Polling interval (seconds) for critical/idle statuses |
| `DEFAULT_BLINK_INTERVAL` | ❌ | `0.7` | Seconds per on/off cycle for blinking statuses |
| `ENABLE_QUIET_HOURS` | ❌ | `False` | Enable the quiet hours feature (`True`/`False`) |
| `QUIET_HOURS_START` | ❌ | `21:00` | Start of quiet window (24h `HH:MM`) |
| `QUIET_HOURS_END` | ❌ | `10:00` | End of quiet window (24h `HH:MM`) |
| `IS_DOCKER` | 🚫 | — | Set automatically by `Dockerfile`. Do not set manually |

---

## Adding New Providers or Controllers

For step-by-step guides with full code examples for adding new presence providers
(Slack, Zoom, Google Chat…) or new light controllers (TP-Link Tapo, Govee, LIFX…),
see [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Running the Project

### With Docker
```bash
cp .env.example .env       # fill in BULB_IP, CLIENT_ID, TENANT_ID
docker compose up -d --build
docker compose logs -f     # watch for first-time Microsoft auth prompt
```

### Manually
```bash
pip install -r requirements.txt
cp .env.example .env       # fill in values
python src/main.py
```

### First-time Authentication (Microsoft Teams)
On first run, the app prints a Microsoft device-flow prompt:
```
ACTION REQUIRED: Authenticate with Microsoft
==================================================
To sign in, visit https://microsoft.com/devicelogin and enter code XXXXXXXX
```
After signing in, the token is cached to `data/.status_light_token_cache.json`
(Docker) or `~/.status_light_token_cache.json` (local). Subsequent runs
authenticate silently with no user interaction required.

---

## Dependencies

| Package | Purpose |
|---|---|
| `pywizlight` | UDP control of Philips WiZ bulbs |
| `msal` | Microsoft Authentication Library (MSAL) for device-flow + token cache |
| `requests` | HTTP client for Microsoft Graph API calls |
| `python-dotenv` | Load `.env` file into environment variables |

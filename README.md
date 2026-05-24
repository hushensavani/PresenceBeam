# 🗨️ PresenceBeam 🟢💡

**A smart bulb outside your work room that lets people nearby know when you're free — automatically synced to your Teams status.**

[![CI](https://github.com/hushensavani/PresenceBeam/actions/workflows/build.yml/badge.svg)](https://github.com/hushensavani/PresenceBeam/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![GitHub stars](https://img.shields.io/github/stars/hushensavani/PresenceBeam?style=flat&logo=github)](https://github.com/hushensavani/PresenceBeam/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/hushensavani/PresenceBeam)](https://github.com/hushensavani/PresenceBeam/issues)
[![Last commit](https://img.shields.io/github/last-commit/hushensavani/PresenceBeam)](https://github.com/hushensavani/PresenceBeam/commits/master)

Place a smart bulb outside your work room. PresenceBeam keeps it in sync with your Microsoft Teams presence so that anyone nearby — family, roommates, colleagues — can see at a glance when it's a good time to knock. Glows green when you're free. Dims when you're away. Blinks red when you're in a call.

Built with an extensible, provider-agnostic architecture — adding support for Slack, Zoom, TP-Link Tapo, Govee, or any other platform/bulb is as simple as adding a single class.

---

## ✨ Features

- **Real-time status sync** — Bulb color changes within seconds of your status changing
- **Adaptive polling** — Polls faster during non-critical statuses (e.g. Available), slower during meetings to reduce API calls
- **Blink support** — Bulb blinks for attention-grabbing statuses like "In a Call" or "Presenting"
- **Quiet hours** — Automatically turns off the bulb and pauses polling during configurable hours (e.g. 9 PM to 10 AM)
- **Token caching** — Microsoft authentication is cached to disk; authenticate once, run forever
- **Dockerized** — Run as a lightweight background container with `docker compose up`
- **Extensible** — Swap providers or light controllers by changing two lines in `main.py`

---

## 🎨 Status → Light Mapping

The current implementation (Microsoft Teams → Philips WiZ) maps statuses as follows:

| Teams Status | Bulb Color | Brightness | Effect |
|---|---|---|---|
| Available | 🟢 Green | 180 | Solid |
| AvailableIdle | 🟢 Green | 100 | Solid (dimmed) |
| Busy | 🔴 Red | 200 | Solid |
| BusyIdle | 🔴 Red | 130 | Solid (dimmed) |
| InAMeeting | 🔴 Red | 200 | Solid |
| InACall | 🔴 Red | 200 | **Blinking** |
| DoNotDisturb | 🔴 Red | 200 | **Blinking** |
| Presenting | 🔴 Red | 255 | **Fast blinking** (0.4s) |
| Away | 🟡 Yellow | 150 | Solid |
| BeRightBack | 🟡 Yellow | 100 | Solid (dimmed) |
| Offline | ⚫ Off | — | Bulb off |
| PresenceUnknown | 🔴 Red | 200 | **Blinking** |

---

## 🏗️ Architecture

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
└──────────┬───────────┘   └──────────────┬────────────────┘
           │                              │
           ▼                              ▼
  TeamsPresenceProvider          WizLightController
  (providers/ms_teams/)          (lights/wiz/)
           │                              │
           └──────────┬───────────────────┘
                      ▼
              ┌───────────────┐
              │  SyncEngine   │
              │  (engine.py)  │
              └───────────────┘
```

The **SyncEngine** is fully provider-agnostic. It knows nothing about Microsoft Teams or Philips WiZ. It only interacts with the abstract base classes, making it trivial to swap implementations.

### Project Structure

```
PresenceBeam/
├── src/
│   ├── config.py                           # Environment-driven configuration + timestamp logging
│   ├── engine.py                           # Core polling loop (provider/controller agnostic)
│   ├── main.py                             # Entry point — wires provider + controller → engine
│   ├── core/
│   │   ├── base_presence_provider.py       # Abstract base class for presence providers
│   │   └── base_light_controller.py        # Abstract base class for light controllers
│   ├── providers/
│   │   └── ms_teams/
│   │       └── teams_presence_provider.py  # Microsoft Teams via Graph API + MSAL
│   └── lights/
│       └── wiz/
│           └── wiz_light_controller.py     # Philips WiZ via pywizlight (UDP)
├── data/                    # Runtime data (token cache); volume-mounted in Docker
├── Dockerfile               # python:3.11-slim container
├── docker-compose.yml       # Production-ready compose file
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── docs/
│   └── index.html           # GitHub Pages landing page
├── AGENTS.md                # Architecture context for AI agents and contributors
├── CONTRIBUTING.md          # How to add new providers and light controllers
├── LICENSE                  # MIT
└── README.md                # This file
```

---

## 🔌 Current Implementation

| Component | Implementation | Technology |
|---|---|---|
| **Presence Provider** | Microsoft Teams | Microsoft Graph API + MSAL (device-flow auth) |
| **Light Controller** | [Philips WiZ Neo 12W B22](https://www.amazon.in/dp/B0CHYDWZ77) | pywizlight library (UDP, local network) |

---

## 📋 Prerequisites

- **Python 3.11+** (for manual run)
- **Docker & Docker Compose** (for containerized run)
- A **[Philips WiZ Neo 12W B22](https://www.amazon.in/dp/B0CHYDWZ77)** smart bulb (Wi-Fi & Bluetooth) connected to your local network
- A **Microsoft 365 work/school account** with Teams
- An **Azure App Registration** (free — setup instructions below)

---

## 🔧 Setup

### Step 1: Register a Microsoft Azure App

You need to register an app in Azure AD to get permission to read your Teams presence status via the Graph API.

#### 1.1 Create the App Registration

1. Go to [portal.azure.com](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations** → **New registration**
3. Name it anything (e.g. `PresenceBeam`), leave all other defaults
4. Click **Register**
5. Note down the **Application (client) ID** and **Directory (tenant) ID** — you'll need these later

#### 1.2 Add API Permissions

1. In your app registration, go to **API Permissions** → **Add a permission**
2. Select **Microsoft Graph** → **Delegated permissions**
3. Search for `Presence.Read` and check it
4. Click **Add permissions**
5. If you're an admin, click **Grant admin consent**. If not, ask your IT admin to grant it

#### 1.3 Enable Public Client Flows (Device Flow Auth)

This allows the app to authenticate via device flow (interactive browser login) without needing a client secret.

1. In your app registration, click **Authentication** in the left menu
2. Click **Add a platform** → **Mobile and desktop applications**
3. Check `https://login.microsoftonline.com/common/oauth2/nativeclient` → Click **Configure**
4. Scroll down to **Advanced settings**
5. Set **"Allow public client flows"** → **Yes**
6. Click **Save**

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# IP Address of the WiZ Bulb (find it in your router's DHCP table or the WiZ app)
BULB_IP=192.168.1.100

# Azure App Registration details (from Step 1)
CLIENT_ID=your_client_id_here
TENANT_ID=your_tenant_id_here
```

#### Full Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `BULB_IP` | ✅ | — | IP address of the smart bulb on the local network |
| `CLIENT_ID` | ✅ | — | Azure App Registration client ID |
| `TENANT_ID` | ✅ | — | Azure tenant ID |
| `POLL_FAST` | ❌ | `5` | Polling interval (seconds) for non-critical statuses |
| `POLL_SLOW` | ❌ | `30` | Polling interval (seconds) for critical/idle statuses |
| `DEFAULT_BLINK_INTERVAL` | ❌ | `0.7` | Seconds per on/off cycle for blinking statuses |
| `ENABLE_QUIET_HOURS` | ❌ | `False` | Enable the quiet hours feature (`True` / `False`) |
| `QUIET_HOURS_START` | ❌ | `21:00` | Start of quiet window (24-hour `HH:MM` format) |
| `QUIET_HOURS_END` | ❌ | `10:00` | End of quiet window (24-hour `HH:MM` format) |

> **Note:** `ENABLE_QUIET_HOURS` accepts `true`, `1`, or `yes` (case-insensitive) as truthy values. Anything else disables it.

---

## 🚀 Running the Project

### Option A: Run with Docker (Recommended)

```bash
# Build and start the container in detached mode
docker compose up -d --build

# Watch logs — important on first run for the Microsoft auth prompt
docker compose logs -f
```

On the first run, you'll see a Microsoft device-flow prompt in the logs:
```
ACTION REQUIRED: Authenticate with Microsoft
==================================================
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
and enter the code XXXXXXXX to authenticate.
==================================================
```

1. Visit the URL shown
2. Enter the code displayed
3. Log in with your Microsoft work/school account

The token is cached to `./data/.presence_beam_token_cache.json` (volume-mounted from the container). Subsequent runs authenticate silently — no user interaction needed.

**Useful Docker commands:**
```bash
docker compose logs -f       # View live logs
docker compose restart       # Restart (e.g. after changing .env)
docker compose down          # Stop and remove the container
```

### Option B: Run Manually

```bash
# Install dependencies
pip install -r requirements.txt

# Create the token cache file with secure permissions
touch ~/.presence_beam_token_cache.json
chmod 600 ~/.presence_beam_token_cache.json

# Run
python src/main.py
```

On the first run, the same Microsoft device-flow prompt will appear directly in your terminal. Follow the instructions to authenticate.

The token is cached to `~/.presence_beam_token_cache.json`. Subsequent runs authenticate silently.

**To run in the background:**
```bash
nohup python src/main.py > sync.log 2>&1 &
```

---

## 🌙 Quiet Hours

When enabled, the daemon automatically turns off the bulb and **stops polling** the Teams API during a configurable time window. This is useful for after-work hours so the bulb isn't glowing while you sleep.

**How it works:**
1. When the current time enters the quiet window, the bulb is turned off **once**
2. No further API calls or bulb commands are made until the window ends
3. When quiet hours end, syncing resumes immediately

**Configuration:**
```env
ENABLE_QUIET_HOURS=True
QUIET_HOURS_START=21:00
QUIET_HOURS_END=10:00
```

> **Note:** Windows that cross midnight are fully supported (e.g. `21:00` to `10:00` means "quiet from 9 PM until 10 AM the next day").

---

## 🧩 Extending PresenceBeam

PresenceBeam is designed to be extended. Adding support for a new communication platform (Slack, Zoom, Google Chat…) or a new smart bulb (TP-Link Tapo, Govee, LIFX…) requires implementing a single class and wiring it up in two lines.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full step-by-step guides with complete code examples.

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `pywizlight` | UDP control of Philips WiZ smart bulbs |
| `msal` | Microsoft Authentication Library for device-flow auth + token caching |
| `requests` | HTTP client for Microsoft Graph API calls |
| `python-dotenv` | Load `.env` file into environment variables |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🤝 Contributing

Contributions are welcome! Whether it's a new presence provider (Slack, Zoom, Google Chat), a new light controller (TP-Link, Govee, LIFX), or improvements to the core engine — PRs are appreciated.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full contribution guides with code examples, and [`AGENTS.md`](AGENTS.md) for architecture context.

---

## 👤 Author

**Hushen Savani**
[linkedin.com/in/hushensavani](https://www.linkedin.com/in/hushensavani/)

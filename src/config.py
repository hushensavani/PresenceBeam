# src/config.py
# Author: Hushen Savani
import os
import builtins
from datetime import datetime
from dotenv import load_dotenv

# Globally override print to include timestamps
_original_print = builtins.print
def _timestamped_print(*args, **kwargs):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _original_print(f"[{timestamp}]", *args, **kwargs)
builtins.print = _timestamped_print

load_dotenv()

# ── Bulb ──────────────────────────────────────────────────────────────────────
BULB_IP = os.getenv("BULB_IP")

# ── Azure App Registration ────────────────────────────────────────────────────
CLIENT_ID = os.getenv("CLIENT_ID")
TENANT_ID = os.getenv("TENANT_ID")

# ── Adaptive Polling ──────────────────────────────────────────────────────────
POLL_FAST = int(os.getenv("POLL_FAST", 5)) # seconds — non-critical states (Available, Focusing)
POLL_SLOW = int(os.getenv("POLL_SLOW", 30)) # seconds — critical + idle states

# ── Blink ─────────────────────────────────────────────────────────────────────
DEFAULT_BLINK_INTERVAL = float(os.getenv("DEFAULT_BLINK_INTERVAL", 0.7))   # seconds

# ── Quiet Hours ───────────────────────────────────────────────────────────────
ENABLE_QUIET_HOURS = os.getenv("ENABLE_QUIET_HOURS", "False").lower() in ("true", "1", "yes")
QUIET_HOURS_START = os.getenv("QUIET_HOURS_START", "21:00")
QUIET_HOURS_END = os.getenv("QUIET_HOURS_END", "10:00")

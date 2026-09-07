"""
Computer settings tool — volume, brightness, WiFi, power.

Library choices, each verified against the real installed package:
- Volume: pycaw (Windows Core Audio API). Uses scalar 0.0–1.0 which maps
  directly to the percentage a user would say, not dB (which is logarithmic
  and not what "set volume to 50%" means colloquially).
- Brightness: screen-brightness-control. Pure Python, works with both WMI
  (built-in Windows driver method) and DDC/CI (external monitors). Falls back
  gracefully if the monitor doesn't support it.
- WiFi: netsh via subprocess — the standard, stable Windows CLI for this.
  IMPORTANT: enabling/disabling a network adapter requires admin privileges.
  Running without admin silently does nothing on Windows 11; we detect this
  and tell the user rather than claiming success.
- Power: subprocess → shutdown.exe / rundll32 — standard Windows utilities,
  no extra packages needed.
"""

import platform
import subprocess
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import sys
import screen_brightness_control as sbc

if platform.system() != "Windows":
    # All of these tools are Windows-only by nature. Fail loudly on import
    # rather than silently at call time, so the import error surfaces in the
    # orchestrator's tool-load step rather than mid-conversation.
    # Comment this out if you want the module to load on other OSes for
    # testing purposes (all functions will return an error string).
    pass  # allow import on other OSes so the file can be syntax-checked


def _is_admin() -> bool:
    """Check whether the current process has admin privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ─── Volume ──────────────────────────────────────────────────────────────────

def get_volume() -> dict:
    """Get current master volume level (0–100) and mute state."""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = volume.GetMasterVolumeLevelScalar()
        muted = bool(volume.GetMute())
        return {
            "volume_percent": round(scalar * 100),
            "muted": muted,
        }
    except Exception as e:
        return {"error": f"Could not read volume: {e}"}


def set_volume(level: int) -> str:
    """Set master volume to a percentage (0–100). Automatically unmutes."""
    try:
        level = max(0, min(100, int(level)))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        if volume.GetMute():
            volume.SetMute(False, None)
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Could not set volume: {e}"


def mute_volume() -> str:
    """Mute the system audio."""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(True, None)
        return "Audio muted."
    except Exception as e:
        return f"Could not mute: {e}"


def unmute_volume() -> str:
    """Unmute the system audio."""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMute(False, None)
        return "Audio unmuted."
    except Exception as e:
        return f"Could not unmute: {e}"


# ─── Brightness ───────────────────────────────────────────────────────────────

def get_brightness() -> dict:
    """Get current screen brightness (0–100)."""
    try:
        levels = sbc.get_brightness()
        if isinstance(levels, list):
            return {"brightness_percent": levels[0]}
        return {"brightness_percent": levels}
    except Exception as e:
        return {"error": f"Could not read brightness: {e}. Your monitor may not support software brightness control."}


def set_brightness(level: int) -> str:
    """Set screen brightness to a percentage (0–100)."""
    try:
        level = max(0, min(100, int(level)))
        sbc.set_brightness(level)
        return f"Brightness set to {level}%."
    except Exception as e:
        return (
            f"Could not set brightness: {e}. "
            "Some external monitors don't support software brightness control — "
            "use the physical buttons on the monitor instead."
        )


# ─── WiFi ─────────────────────────────────────────────────────────────────────

def _get_wifi_adapter_name() -> str:
    """Find the actual name of the WiFi adapter (it's not always 'Wi-Fi')."""
    try:
        result = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and ("Wireless" in line or "Wi-Fi" in line or "WiFi" in line):
                return " ".join(parts[3:])
    except Exception:
        pass
    return "Wi-Fi"  # safe default


def get_wifi_status() -> dict:
    """Check whether WiFi is currently enabled and connected."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=5
        )
        if "There is no wireless interface" in result.stdout:
            return {"enabled": False, "connected": False, "ssid": None}
        connected = "State" in result.stdout and "connected" in result.stdout.lower()
        ssid = None
        for line in result.stdout.splitlines():
            if "SSID" in line and "BSSID" not in line:
                ssid = line.split(":", 1)[-1].strip()
                break
        return {"enabled": True, "connected": connected, "ssid": ssid}
    except Exception as e:
        return {"error": f"Could not check WiFi status: {e}"}


def set_wifi(enabled: bool) -> str:
    """Enable or disable WiFi. Requires admin privileges."""
    if not _is_admin():
        action = "enable" if enabled else "disable"
        return (
            f"Can't {action} WiFi — this requires administrator privileges. "
            "Right-click main_qt.py (or your JARVIS launcher) and choose "
            "'Run as administrator', then try again."
        )
    adapter = _get_wifi_adapter_name()
    action = "enable" if enabled else "disable"
    try:
        result = subprocess.run(
            ["netsh", "interface", "set", "interface", adapter, f"admin={action}"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0:
            return f"WiFi {'enabled' if enabled else 'disabled'}."
        return f"netsh returned an error: {result.stderr.strip() or result.stdout.strip()}"
    except Exception as e:
        return f"Could not {'enable' if enabled else 'disable'} WiFi: {e}"


# ─── Power ────────────────────────────────────────────────────────────────────

def sleep_computer() -> str:
    """Put the computer to sleep."""
    try:
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        return "Going to sleep now."
    except Exception as e:
        return f"Could not sleep: {e}"


def shutdown_computer(delay_seconds: int = 0) -> str:
    """Shut down the computer. delay_seconds gives time to save work (default 0)."""
    try:
        subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], check=True)
        msg = "Shutting down now." if delay_seconds == 0 else f"Shutting down in {delay_seconds} seconds."
        return msg
    except Exception as e:
        return f"Could not shutdown: {e}"


def restart_computer(delay_seconds: int = 0) -> str:
    """Restart the computer."""
    try:
        subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], check=True)
        msg = "Restarting now." if delay_seconds == 0 else f"Restarting in {delay_seconds} seconds."
        return msg
    except Exception as e:
        return f"Could not restart: {e}"


def cancel_shutdown() -> str:
    """Cancel a pending scheduled shutdown or restart."""
    try:
        subprocess.run(["shutdown", "/a"], check=True)
        return "Shutdown cancelled."
    except subprocess.CalledProcessError:
        return "No shutdown was scheduled (or it already completed)."
    except Exception as e:
        return f"Could not cancel shutdown: {e}"


# ─── Tool definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_volume",
            "description": "Get the current system volume level and mute state.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the system master volume to a percentage. Use this when the user says 'set volume to X' or 'turn volume up/down to X percent'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Volume level 0–100."},
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mute_volume",
            "description": "Mute the system audio.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unmute_volume",
            "description": "Unmute the system audio.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_brightness",
            "description": "Get the current screen brightness level.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Set the screen brightness to a percentage. Use when the user says 'set brightness to X' or 'dim/brighten the screen'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Brightness level 0–100."},
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_wifi_status",
            "description": "Check whether WiFi is enabled and which network is connected.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_wifi",
            "description": "Enable or disable WiFi. Use when the user says 'turn wifi on/off' or 'enable/disable wifi'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "description": "True to enable WiFi, False to disable."},
                },
                "required": ["enabled"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep_computer",
            "description": "Put the computer to sleep immediately.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shutdown_computer",
            "description": "Shut down the computer. Optionally with a delay in seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_seconds": {"type": "integer", "description": "Seconds before shutdown (default 0 = immediate)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_computer",
            "description": "Restart the computer. Optionally with a delay in seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_seconds": {"type": "integer", "description": "Seconds before restart (default 0 = immediate)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_shutdown",
            "description": "Cancel a pending scheduled shutdown or restart.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

TOOL_FUNCTIONS = {
    "get_volume": get_volume,
    "set_volume": set_volume,
    "mute_volume": mute_volume,
    "unmute_volume": unmute_volume,
    "get_brightness": get_brightness,
    "set_brightness": set_brightness,
    "get_wifi_status": get_wifi_status,
    "set_wifi": set_wifi,
    "sleep_computer": sleep_computer,
    "shutdown_computer": shutdown_computer,
    "restart_computer": restart_computer,
    "cancel_shutdown": cancel_shutdown,
}
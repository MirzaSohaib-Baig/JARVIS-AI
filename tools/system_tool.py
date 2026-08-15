"""
System control & monitoring tool.

CPU/RAM/disk stats use psutil — the standard cross-platform library for
this, actively maintained, no reason to hand-roll it.

GPU stats use nvidia-ml-py (NVIDIA's own official Python package —
`pip install nvidia-ml-py`, then `import pynvml`, which is the correct,
documented usage even though the pip package name changed). This is
deliberately NOT hand-rolled ctypes bindings to nvml.dll — getting a
struct layout or function signature wrong in raw ctypes is the kind of bug
that segfaults or silently returns garbage rather than erroring cleanly,
and NVIDIA already ships tested bindings for exactly this. Non-NVIDIA GPUs
(AMD, Intel) report as unavailable rather than guessing — there's no
vendor-neutral way to query them from Python.

Camera opening launches the OS's actual camera app (what "open the camera"
means here) — this is separate from AI vision (JARVIS looking through the
webcam to describe what it sees), which is a different, bigger feature
involving a vision-capable model call. Worth building later if wanted, not
assumed here.
"""

import platform
import subprocess

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False

try:
    import pynvml
    _PYNVML_IMPORTED = True
except ImportError:
    _PYNVML_IMPORTED = False

_nvml_ready = None  # None = untested, True/False = tested result, cached


def _init_nvml() -> bool:
    global _nvml_ready
    if _nvml_ready is not None:
        return _nvml_ready
    if not _PYNVML_IMPORTED:
        _nvml_ready = False
        return False
    try:
        pynvml.nvmlInit()
        _nvml_ready = True
    except Exception:
        _nvml_ready = False
    return _nvml_ready


def open_camera() -> str:
    """Open the OS's default camera app."""
    system = platform.system()
    try:
        if system == "Windows":
            # microsoft.windows.camera: is the official URI scheme for the
            # built-in Camera app on Windows 10/11.
            subprocess.Popen(["cmd", "/c", "start", "", "microsoft.windows.camera:"])
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "Photo Booth"])
        elif system == "Linux":
            # cheese is the common GNOME camera app; not installed by
            # default on every distro.
            subprocess.Popen(["cheese"])
        else:
            return f"Don't know how to open the camera on {system}."
        return "Camera app opened."
    except FileNotFoundError:
        return f"Couldn't find a camera app to launch on {system} — you may need to install one."
    except Exception as e:
        return f"Failed to open camera: {e}"

def close_camera() -> str:
    """Close the OS's default camera app."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["taskkill", "/IM", "WindowsCamera.exe", "/F"])
        elif system == "Darwin":
            subprocess.Popen(["osascript", "-e", 'quit app "Photo Booth"'])
        elif system == "Linux":
            subprocess.Popen(["pkill", "cheese"])
        else:
            return f"Don't know how to close the camera on {system}."
        return "Camera app closed."
    except Exception as e:
        return f"Failed to close camera: {e}"


def get_system_performance() -> dict:
    """CPU, RAM, and disk usage — cross-platform via psutil."""
    if not _PSUTIL_OK:
        return {"error": "psutil isn't installed. Run: pip install psutil"}

    disk_path = "C:\\" if platform.system() == "Windows" else "/"
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(disk_path)

    return {
        "cpu_percent": cpu_percent,
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_used_gb": round(mem.used / (1024**3), 1),
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "ram_percent": mem.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_percent": disk.percent,
    }


def get_gpu_status() -> dict:
    """NVIDIA GPU utilization/memory/temperature via NVML. Returns an
    explanatory 'available': False rather than an error for non-NVIDIA
    GPUs or missing drivers — this is an expected case, not a failure."""
    if not _init_nvml():
        return {
            "available": False,
            "message": "No NVIDIA GPU detected, or drivers/nvidia-ml-py aren't installed.",
        }

    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode(errors="replace")

        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

        return {
            "available": True,
            "name": name,
            "gpu_utilization_percent": util.gpu,
            "memory_utilization_percent": util.memory,
            "memory_used_mb": round(mem.used / (1024**2)),
            "memory_total_mb": round(mem.total / (1024**2)),
            "temperature_c": temp,
        }
    except Exception as e:
        return {"available": False, "message": f"NVML query failed: {e}"}


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "open_camera",
            "description": "Open the computer's default camera app. Use when the user asks to open, launch, or start the camera.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_camera",
            "description": "Close the computer's default camera app. Use when the user asks to close, quit, or stop the camera.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_performance",
            "description": "Get CPU usage, RAM usage, and disk usage. Use for questions about computer performance, memory, or storage.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gpu_status",
            "description": "Get GPU utilization, memory usage, and temperature (NVIDIA GPUs only). Use for questions about GPU/graphics card performance.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

TOOL_FUNCTIONS = {
    "close_camera": close_camera,
    "open_camera": open_camera,
    "get_system_performance": get_system_performance,
    "get_gpu_status": get_gpu_status,
}
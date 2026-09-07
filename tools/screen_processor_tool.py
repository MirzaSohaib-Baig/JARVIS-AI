"""
Screen processor tool (Gap 2) — JARVIS can see your screen.

Capture uses mss (pure Python, no Tkinter/display dependency on Windows,
works headlessly on Linux). Vision analysis routes through OpenRouter using
the same OpenAI-compatible client your orchestrator already uses, pointed at
a free vision-capable model (google/gemini-2.0-flash-exp:free).

The screen capture → base64 encode → send as image_url (data URI) pattern
is the standard way to feed a local screenshot to a vision model via the
OpenAI messages API. Confirmed this is the exact format OpenRouter's
vision models expect: {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}

webcam_snapshot() is included but intentionally kept simple — it uses
OpenCV (cv2) which is the standard Python webcam interface. If cv2 isn't
installed it tells you clearly rather than crashing.

All functions return plain strings — same shape as every other tool in this
project, so _run_tool() in the orchestrator handles them without any
special casing.
"""

import base64
import io
import platform

from openai import OpenAI
from config.settings import settings


_client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.BASE_URL,
    default_headers={
        "HTTP-Referer": settings.SITE_URL,
        "X-OpenRouter-Title": settings.SITE_NAME,
    },
)


def _screenshot_to_base64(monitor_index: int = 1) -> str:
    """
    Capture a screenshot using mss and return it as a base64-encoded PNG
    string. monitor_index=1 is the primary monitor (0 is a virtual
    all-monitors combined view in mss).
    """
    import mss
    import mss.tools

    with mss.mss() as sct:
        monitors = sct.monitors
        idx = min(monitor_index, len(monitors) - 1)
        monitor = monitors[idx]
        screenshot = sct.grab(monitor)

        # Convert mss screenshot to PNG bytes via Pillow
        from PIL import Image
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Resize if very large — vision models work fine at 1280px wide,
        # and smaller images use fewer tokens
        max_width = 1280
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize(
                (max_width, int(img.height * ratio)),
                Image.LANCZOS,
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def _vision_query(b64_image: str, prompt: str) -> str:
    """Send a base64 image to the vision model and return its response."""
    response = _client.chat.completions.create(
        model=settings.VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content


def analyze_screen(question: str = "") -> str:
    """
    Take a screenshot of the primary monitor and answer a question about it.
    If no question is given, gives a general description of what's on screen.
    """
    try:
        b64 = _screenshot_to_base64(monitor_index=1)
        prompt = (
            question.strip()
            if question.strip()
            else "Describe what is currently on this screen concisely and clearly."
        )
        return _vision_query(b64, prompt)
    except ImportError as e:
        return (
            f"Screen capture isn't available: {e}. "
            "Run: pip install mss Pillow"
        )
    except Exception as e:
        return f"Screen analysis failed: {e}"


def read_screen_text() -> str:
    """
    Take a screenshot and extract all readable text from it — useful for
    reading a document, error message, or anything on screen that's text.
    """
    try:
        b64 = _screenshot_to_base64(monitor_index=1)
        return _vision_query(
            b64,
            "Extract and return all readable text visible on this screen. "
            "Preserve the structure where possible. Return only the text, no commentary."
        )
    except Exception as e:
        return f"Screen text extraction failed: {e}"


def webcam_snapshot(question: str = "") -> str:
    """
    Take a snapshot from the webcam and answer a question about it —
    or describe what the camera sees if no question is given.
    """
    try:
        import cv2
    except ImportError:
        return (
            "Webcam access requires OpenCV. "
            "Run: pip install opencv-python"
        )

    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "No webcam found or webcam is already in use by another application."

        # Read a few frames first so the camera auto-adjusts exposure
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return "Webcam capture failed — couldn't read a frame."

        # Encode to PNG → base64
        success, buffer = cv2.imencode(".png", frame)
        if not success:
            return "Webcam capture failed — couldn't encode the image."

        b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")
        prompt = (
            question.strip()
            if question.strip()
            else "Describe what the webcam currently sees."
        )
        return _vision_query(b64, prompt)

    except Exception as e:
        return f"Webcam analysis failed: {e}"


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": (
                "Take a screenshot of the user's screen and analyse it. "
                "Use when the user asks 'what's on my screen', 'can you see this', "
                "'what does this error say', 'help me with what I'm looking at', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": (
                            "A specific question about what's on screen. "
                            "Leave empty for a general description."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen_text",
            "description": (
                "Extract all readable text from the user's screen. "
                "Use when the user says 'read what's on my screen', "
                "'what does that say', or wants text from a document/error visible on screen."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "webcam_snapshot",
            "description": (
                "Take a snapshot from the webcam and describe or answer a question "
                "about what it sees. Use when the user asks JARVIS to look at them, "
                "their surroundings, or something they're holding up to the camera."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "A specific question about what the webcam sees. Leave empty for a general description.",
                    }
                },
                "required": [],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "analyze_screen": analyze_screen,
    "read_screen_text": read_screen_text,
    "webcam_snapshot": webcam_snapshot,
}
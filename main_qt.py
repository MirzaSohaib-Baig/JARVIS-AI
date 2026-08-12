"""
JARVIS desktop shell (PyQt6). This is the desktop-app sibling of running
`uvicorn server:app` and opening a browser tab — it does the same thing, just
wrapped in a real window with no browser chrome around it, and it fixes the
popup-blocker problem structurally instead of asking you to grant browser
permissions.

Why this works when a real browser tab didn't:
Chrome/Firefox's popup blocker is a browser-chrome feature that refuses
window.open() calls unless they happen synchronously inside a click handler.
Our news-card code in script.js calls window.open() *after* an awaited
fetch() resolves, which trips that heuristic every time. Qt's embedded
WebEngine has no such browser-chrome popup blocker at all — instead, ANY
window.open() call simply does nothing unless the host app explicitly
provides a window to open into, via QWebEnginePage.createWindow(). Since
we're the host app, we just... provide one. No permission dialogs, no
async-timing restrictions, and script.js's existing window.open() calls work
completely unchanged.

Run with:
    python main_qt.py

First run: pip install PyQt6 PyQt6-WebEngine  (see README for details — this
one is a large download, ~150-250MB, since it bundles Chromium).
"""

import atexit
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import quote

from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QRect, QUrl, Qt
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

import subprocess

PROJECT_DIR = Path(__file__).parent
BACKEND_URL = "http://127.0.0.1:8000"

_open_windows = []


def start_backend() -> subprocess.Popen:
    """
    Launches `uvicorn server:app` as a child process and waits until it's
    actually answering requests before returning — otherwise the main window
    would try to load the page before the server exists yet.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--port", "8000"],
        cwd=PROJECT_DIR,
    )
    for _ in range(60):  # up to ~30s for a cold start
        try:
            urlopen(BACKEND_URL, timeout=0.5)
            return proc
        except URLError:
            time.sleep(0.5)
    raise RuntimeError(
        "JARVIS backend didn't come up in time. Run `uvicorn server:app --port 8000` "
        "manually in this folder to see the actual error."
    )

class VideoPlayerPage(QWebEnginePage):
    """Page for native video player windows. Intercepts navigation to keep
    everything inside the embedded player."""
    
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True
        )
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
        )
        self.setBackgroundColor(Qt.GlobalColor.transparent)

    def createWindow(self, _window_type):
        """Capture any popup attempts from the video player."""
        return ExternalBrowserPage(self.profile(), self)
    
class ExternalBrowserPage(QWebEnginePage):
    """
    Dummy interceptor page used to capture window.open() targets
    and divert them straight into native desktop browser windows.
    """
    def __init__(self, profile, parent = None):
        super().__init__(profile, parent)
        self.urlChanged.connect(self._launch_in_os_browser)

    def _launch_in_os_browser(self, url: QUrl):
        if url.isValid() and not url.toString() in ("about:blank", ""):
            QDesktopServices.openUrl(url)
        self.deleteLater()
    
class CardWindow(QMainWindow):
    """One floating, borderless window for a single news card — this is
    what 'different windows' actually means now: real native OS windows,
    not browser popups and not an in-page simulation."""

    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.view = QWebEngineView(self)
        self.view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        self.setCentralWidget(self.view)

        _open_windows.append(self)  # keep a reference so it doesn't get GC'd

        self.destroyed.connect(lambda: _open_windows.remove(self) if self in _open_windows else None)  # remove from list when closed

class VideoWindow(QMainWindow):
    """Native OS window for YouTube video playback."""
    
    def __init__(self, embed_url: str, title: str = "JARVIS Video Player"):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Size: 16:9 aspect ratio
        self.resize(854, 510)
        
        # Center on screen
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - 854) // 2,
            (screen.height() - 510) // 2
        )
        
        # Central widget with border styling
        central = QWidget()
        central.setObjectName("videoWindow")
        central.setStyleSheet("""
            #videoWindow {
                background: #00060a;
                border: 1px solid #00d4ff;
                border-radius: 12px;
            }
        """)
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        title_bar = self._create_title_bar(title)
        layout.addWidget(title_bar)
        
        # Video player - load from server endpoint
        self.view = QWebEngineView()
        self.view.setStyleSheet("background: #000; border-radius: 0 0 12px 12px;")
        
        # Build the URL for the server's video player endpoint
        encoded_url = quote(embed_url, safe='')
        video_player_url = f"{BACKEND_URL}/video-player?embed_url={encoded_url}&title={quote(title, safe='')}"
        
        self.view.load(QUrl(video_player_url))
        layout.addWidget(self.view)
        
        # Keep reference to prevent garbage collection
        _open_windows.append(self)
        self.destroyed.connect(lambda: _open_windows.remove(self) if self in _open_windows else None)
    
    def _create_title_bar(self, title: str) -> QWidget:
        """Create JARVIS-styled title bar."""
        bar = QWidget()
        bar.setFixedHeight(38)
        bar.setStyleSheet("""
            background: #000d14;
            border-bottom: 1px solid #1a5c7a;
            border-radius: 12px 12px 0 0;
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(8)
        
        # Glowing dot
        dot = QLabel("●")
        dot.setFixedWidth(16)
        dot.setStyleSheet("""
            color: #00d4ff; 
            font-size: 10px; 
            background: transparent;
        """)
        layout.addWidget(dot)
        
        # Title text
        title_label = QLabel(title[:50])
        title_label.setStyleSheet("""
            color: #00d4ff; 
            font-family: 'Courier New', monospace; 
            font-size: 10px; 
            font-weight: bold;
            letter-spacing: 2px;
            background: transparent;
        """)
        layout.addWidget(title_label)
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ff3355;
                border: 1px solid #ff3355;
                border-radius: 13px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 51, 85, 0.2);
            }
        """)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return bar
    
class MainPage(QWebEnginePage):
    """Main HUD view page controller."""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True
        )
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
        )
        self._main_window = parent

    def createWindow(self, _window_type):
        """Intercepts window.open() calls from the main page."""
        return ExternalBrowserPage(self.profile(), self)
    
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        """Listen for console messages from JS to trigger native video windows."""
        msg = message.strip()
        
        # Listen for a special console message format to open video windows
        # Format: JARVIS_OPEN_VIDEO:{"embed_url":"...", "title":"..."}
        if msg.startswith("JARVIS_OPEN_VIDEO:"):
            try:
                import json
                data = json.loads(msg[len("JARVIS_OPEN_VIDEO:"):])
                embed_url = data.get("embed_url", "")
                title = data.get("title", "JARVIS Video Player")
                
                if embed_url:
                    self._open_video_window(embed_url, title)
            except Exception as e:
                print(f"[JARVIS] Failed to open video window: {e}")
        
        # Also listen for card window requests
        elif msg.startswith("JARVIS_OPEN_CARD:"):
            try:
                import json
                data = json.loads(msg[len("JARVIS_OPEN_CARD:"):])
                url = data.get("url", "")
                title = data.get("title", "JARVIS Card")
                
                if url:
                    self._open_card_window(url, title)
            except Exception as e:
                print(f"[JARVIS] Failed to open card window: {e}")
    
    def _open_video_window(self, embed_url: str, title: str):
        """Open a native video player window."""
        window = VideoWindow(embed_url, title)
        window.show()
    
    def _open_card_window(self, url: str, title: str):
        """Open a native card window for articles."""
        window = CardWindow(title)
        window.view.load(QUrl(url))
        window.show()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S")
        self.resize(1100, 820)

        self.view = QWebEngineView()
        self.page = MainPage(self.view.page().profile(), self.view)
        self.page._main_window = self
        self.view.setPage(self.page)
        self.view.load(QUrl(BACKEND_URL))
        self.setCentralWidget(self.view)


def main():
    backend_proc = start_backend()
    atexit.register(backend_proc.terminate)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    exit_code = app.exec()

    backend_proc.terminate()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
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

        self._embed_url = embed_url
        self._is_closing = False
        
        # Size: 16:9 aspect ratio
        win_w, win_h = 860, 520
        self.resize(win_w, win_h)
        
        # Center on screen
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - win_w) // 2,
            (screen.height() - win_h) // 2
        )
        
        # Central widget with border styling
        central = QWidget()
        central.setObjectName("videoWindow")
        central.setStyleSheet("""
            #videoWindow {
                background: #00060a;
                border: 1.5px solid #00d4ff;
                border-radius: 14px;
            }
        """)
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        self._title_bar = self._create_title_bar(title)
        layout.addWidget(self._title_bar)
        
        # Video player - load from server endpoint
        self.view = QWebEngineView()
        self.view.setStyleSheet("background: #000; border-radius: 0 0 13px 13px;")
        
        # Build the URL for the server's video player endpoint
        encoded_url = quote(embed_url, safe='')
        video_player_url = f"{BACKEND_URL}/video-player?embed_url={encoded_url}&title={quote(title, safe='')}"
        
        self.view.load(QUrl(video_player_url))

        # Set the page to stop media when window closes
        page = self.view.page()
        page.setBackgroundColor(Qt.GlobalColor.black)
        page.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
        )

        layout.addWidget(self.view)
        
        # Keep reference to prevent garbage collection
        _open_windows.append(self)
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._cleanup_and_close)
    
    def _create_title_bar(self, title: str) -> QWidget:
        """Create JARVIS-styled draggable title bar."""
        bar = QWidget()
        bar.setFixedHeight(42)
        bar.setCursor(Qt.CursorShape.OpenHandCursor)  # Shows it's draggable
        bar.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #001420, stop:1 #000a14);
            border-bottom: 1px solid #1a5c7a;
            border-radius: 13px 13px 0 0;
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(10)
        
        # JARVIS logo/icon
        icon = QLabel("◈")
        icon.setFixedWidth(20)
        icon.setStyleSheet("""
            color: #00d4ff; 
            font-size: 14px; 
            background: transparent;
            font-weight: bold;
        """)
        layout.addWidget(icon)
        
        # Video title
        display_title = title[:55] + "..." if len(title) > 55 else title
        title_label = QLabel(display_title)
        title_label.setStyleSheet("""
            color: #00d4ff; 
            font-family: 'Courier New', monospace; 
            font-size: 10px; 
            font-weight: bold;
            letter-spacing: 1.5px;
            background: transparent;
        """)
        layout.addWidget(title_label)
        layout.addStretch()
        
        # Minimize button
        min_btn = QPushButton("—")
        min_btn.setFixedSize(28, 28)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #5f8fa3;
                border: 1px solid #1a3f52;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.1);
                border-color: #00d4ff;
                color: #00d4ff;
            }
        """)
        min_btn.clicked.connect(self.showMinimized)
        layout.addWidget(min_btn)
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ff3355;
                border: 1px solid #5a1530;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 51, 85, 0.2);
                border-color: #ff3355;
            }
        """)
        close_btn.clicked.connect(self._cleanup_and_close)
        layout.addWidget(close_btn)
        
        # Make the title bar draggable
        bar.mousePressEvent = self._title_bar_mouse_press
        bar.mouseMoveEvent = self._title_bar_mouse_move
        bar.mouseReleaseEvent = self._title_bar_mouse_release
        
        return bar
    def _title_bar_mouse_press(self, event):
        """Start window drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._title_bar.setCursor(Qt.CursorShape.ClosedHandCursor)
    
    def _title_bar_mouse_move(self, event):
        """Move window during drag."""
        if hasattr(self, '_drag_pos') and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
    
    def _title_bar_mouse_release(self, event):
        """End window drag."""
        if hasattr(self, '_drag_pos'):
            del self._drag_pos
            self._title_bar.setCursor(Qt.CursorShape.OpenHandCursor)
    
    def _cleanup_and_close(self):
        """Stop video playback and close the window properly."""
        if self._is_closing:
            return
        self._is_closing = True
        
        # Stop video by loading a blank page
        if hasattr(self, 'view'):
            self.view.stop()
            self.view.setHtml("<html><body></body></html>")
            self.view.deleteLater()
        
        # Remove from tracking list
        if self in _open_windows:
            _open_windows.remove(self)
        
        # Close the window
        self.close()
        self.deleteLater()
    
    def closeEvent(self, event):
        """Override close event to ensure cleanup."""
        self._cleanup_and_close()
        event.accept()
    
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
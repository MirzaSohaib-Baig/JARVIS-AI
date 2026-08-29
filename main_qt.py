"""
JARVIS desktop shell (PyQt6). Simplified — all browser management via JS fetch.
"""

import atexit
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

import subprocess

PROJECT_DIR = Path(__file__).parent
BACKEND_URL = "http://127.0.0.1:8000"


def start_backend() -> subprocess.Popen:
    """Launches uvicorn server and waits until it's ready."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--port", "8000"],
        cwd=PROJECT_DIR,
    )
    for _ in range(60):
        try:
            urlopen(BACKEND_URL, timeout=0.5)
            return proc
        except URLError:
            time.sleep(0.5)
    raise RuntimeError("JARVIS backend didn't come up in time.")


class ExternalBrowserPage(QWebEnginePage):
    """Captures window.open() and diverts to OS browser."""
    
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.urlChanged.connect(self._launch_in_os_browser)

    def _launch_in_os_browser(self, url: QUrl):
        if url.isValid() and url.toString() not in ("about:blank", ""):
            QDesktopServices.openUrl(url)
        self.deleteLater()


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

    def createWindow(self, _window_type):
        """Intercepts window.open() calls."""
        return ExternalBrowserPage(self.profile(), self)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S")
        self.resize(1100, 820)

        self.view = QWebEngineView()
        self.page = MainPage(self.view.page().profile(), self.view)
        self.view.setPage(self.page)
        self.view.load(QUrl(BACKEND_URL))
        self.setCentralWidget(self.view)


def main():
    backend_proc = start_backend()
    atexit.register(backend_proc.terminate)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    exit_code = app.exec()

    backend_proc.terminate()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
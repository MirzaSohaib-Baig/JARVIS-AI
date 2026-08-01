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

from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QRect, QUrl, Qt
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

import subprocess

PROJECT_DIR = Path(__file__).parent
BACKEND_URL = "http://127.0.0.1:8000"


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


class NewsWindow(QMainWindow):
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

class NewsPage(QWebEnginePage):

    def acceptNavigationRequest(self, url: QUrl, _type, isMainFrame):

        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
            return False  # Cancel navigation inside the Qt window.
        return super().acceptNavigationRequest(url, _type, isMainFrame)

class ExternalLinkPage(QWebEnginePage):
    """
    A throwaway, never-shown page used only to catch a URL that should open
    in the user's actual default browser (Chrome/Edge/whatever) rather than
    another window inside JARVIS — this is what "Open Source" needs. When
    the /card page's <a target="_blank"> gets clicked, Chromium asks its
    page's createWindow() for somewhere to put it; CardPage below hands it
    one of these instead of a real window. We never navigate this page
    anywhere ourselves — we just watch for the URL Chromium loads into it,
    hand that off to the OS's real browser via QDesktopServices, then
    delete this page since it was only ever a catcher, not something meant
    to be seen.
    """
 
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.urlChanged.connect(self._open_externally)
 
    def _open_externally(self, url: QUrl):
        if url.isValid() and not url.toString() in ("about:blank", ""):
            QDesktopServices.openUrl(url)
        self.deleteLater()
 
 
class CardPage(QWebEnginePage):
    """
    The page used inside each news card window (the /card route). Its only
    job is createWindow(): the "Open Source" link uses target="_blank",
    which Chromium treats as a new-window request rather than a normal
    navigation — without this override that request has nowhere to go and
    silently does nothing (the bug this class fixes). Every such request
    here should mean "open in the real system browser", so it always hands
    back an ExternalLinkPage instead of another JARVIS window.
    """
 
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
 
    def createWindow(self, _window_type):
        return ExternalLinkPage(self.profile(), self)


class MainPage(QWebEnginePage):
    """
    The main window's page. The only job here is createWindow(): whenever
    script.js calls window.open(...) — which it already does, for the news
    card popups — Qt calls this method to ask "is a new window OK?". We say
    yes and hand back a fresh NewsWindow's page, then apply whatever
    position/size window.open()'s features string requested once Chromium
    reports it via geometryChangeRequested.
    """

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)  # Disable JS popups for the main page
        self._children: list[NewsWindow] = []  # keeps references alive

    def createWindow(self, _window_type):
        win = NewsWindow()
        page = CardPage(self.profile(), win.view)
        # page = QWebEnginePage(self.profile(), win.view)
        # page = NewsPage(self.profile(), win.view)
        win.view.setPage(page)
        page.geometryChangeRequested.connect(lambda rect, w=win: self._apply_geometry(w, rect))
        win.show()
        self._children.append(win)
        return page

    @staticmethod
    def _apply_geometry(win: "NewsWindow", rect: QRect):
        if rect.width() > 0 and rect.height() > 0:
            win.setGeometry(rect)
        win.show()


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
    window = MainWindow()
    window.show()
    exit_code = app.exec()

    backend_proc.terminate()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
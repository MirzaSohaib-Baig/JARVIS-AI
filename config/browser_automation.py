"""
browser_manager_selenium.py — Selenium-based browser window manager for JARVIS.
Uses Chrome with separate profiles for each window to maintain isolation.
"""

import tempfile
import uuid
import threading
import asyncio
from typing import Dict

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

# Optional: Auto-download ChromeDriver
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service as ChromeService
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False


class SeleniumWindow:
    """Represents a single browser window with its driver instance."""
    
    def __init__(self, window_id: str, driver: webdriver.Chrome):
        self.window_id = window_id
        self.driver = driver
        self.closed = False
    
    def close(self):
        """Close this window."""
        if not self.closed:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.closed = True


class SeleniumBrowserManager:
    """
    Manages multiple Chrome windows using Selenium.
    Each window runs in its own Chrome instance with a unique profile.
    """
    
    def __init__(self):
        self.windows: Dict[str, SeleniumWindow] = {}
        self._lock = threading.Lock()
        self._shutdown = False
    
    def _create_driver(self, left: int, top: int, width: int, height: int, url: str) -> webdriver.Chrome:
        """
        Create a new Chrome driver instance with custom window position.
        Uses a unique profile directory for isolation.
        """
        options = Options()
        
        # Use unique profile for each window
        profile_dir = tempfile.mkdtemp(prefix="jarvis-chrome-")
        options.add_argument(f"--user-data-dir={profile_dir}")
        
        # Window position and size
        options.add_argument(f"--window-position={left},{top}")
        options.add_argument(f"--window-size={width},{height}")
        
        # Important: Open as app window (no address bar)
        options.add_argument(f"--app={url}")
        
        # Enable media playback
        options.add_argument("--autoplay-policy=no-user-gesture-required")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Disable infobars and other Chrome UI elements
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        
        # Enable hardware acceleration for better video playback
        options.add_argument("--enable-accelerated-video-decode")
        options.add_argument("--enable-gpu-rasterization")
        
        # Set browser preferences
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.media_stream": 1,  # Allow media
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.default_content_setting_values.notifications": 2,  # Block notifications
        })
        
        # Exclude automation flags that might cause issues
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Create driver
        if WEBDRIVER_MANAGER_AVAILABLE:
            # Auto-download ChromeDriver if needed
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        else:
            # Use system ChromeDriver (must be in PATH)
            driver = webdriver.Chrome(options=options)
        
        # Set window position and size explicitly (in case --app ignores it)
        driver.set_window_position(left, top)
        driver.set_window_size(width, height)
        
        return driver
    
    async def _ensure_not_shutdown(self):
        """Check if manager has been shut down."""
        if self._shutdown:
            raise RuntimeError("Browser manager has been shut down")
    
    async def open(
        self,
        url: str,
        left: int,
        top: int,
        width: int,
        height: int,
        window_id: str | None = None,
    ) -> str:
        """
        Opens a new positioned window and returns its window_id.
        Auto-generates a unique ID if not provided.
        """
        await self._ensure_not_shutdown()
        
        # Generate window ID if not provided
        if window_id is None:
            window_id = uuid.uuid4().hex[:8]
        elif window_id in self.windows:
            await self.close(window_id)
        
        # Create driver in a separate thread to avoid blocking
        def _create():
            return self._create_driver(left, top, width, height, url)
        
        try:
            # Run driver creation in thread pool
            driver = await asyncio.to_thread(_create)
        except WebDriverException as e:
            raise RuntimeError(f"Failed to create browser window: {e}")
        
        # Store window
        window = SeleniumWindow(window_id, driver)
        
        with self._lock:
            self.windows[window_id] = window
        
        return window_id
    
    async def close(self, window_id: str) -> bool:
        """
        Closes one window on command.
        Returns False if that ID isn't currently open.
        """
        await self._ensure_not_shutdown()
        
        with self._lock:
            window = self.windows.pop(window_id, None)
        
        if window is None:
            return False
        
        # Close driver in a separate thread
        await asyncio.to_thread(window.close)
        return True
    
    async def close_all(self) -> int:
        """Closes every currently open window. Returns count of closed."""
        await self._ensure_not_shutdown()
        
        with self._lock:
            window_ids = list(self.windows.keys())
        
        closed_count = 0
        for wid in window_ids:
            if await self.close(wid):
                closed_count += 1
        
        return closed_count
    
    async def shutdown(self):
        """Closes all windows and shuts down the manager."""
        if self._shutdown:
            return
        
        await self.close_all()
        self._shutdown = True

    async def _monitor_window(self):
        while not self._shutdown:
            await asyncio.sleep(1)
            with self._lock:
                closed_ids = [
                    wid for wid, window in self.windows.items() if window.closed
                ]
            for wid in closed_ids:
                await self.close(wid)
    
    def get_open_count(self) -> int:
        """Get the number of currently open windows."""
        with self._lock:
            return len(self.windows)
    
    def is_open(self, window_id: str) -> bool:
        """Check if a specific window is open."""
        with self._lock:
            window = self.windows.get(window_id)
            return window is not None and not window.closed

    def _is_driver_alive(self, window: SeleniumWindow) -> bool:
        try:
            window.driver.current_url
            return True
        except WebDriverException:
            return False


# Singleton instance
browser_manager = SeleniumBrowserManager()
"""
JARVIS Playwright Window Dispatcher.
Launches browser windows at exact grid positions across all operating systems.

Uses launch_persistent_context() rather than launch() + new_context() —
persistent context is Playwright's intended pattern for a single real,
visible browser window with custom launch args like --app=. launch() +
new_context() is built for spinning up multiple isolated automated
sessions (its usual testing/scraping use case), and asking it to also
honor --app='s window-mode/position via a separately-created context isn't
something it's designed to guarantee.
"""
import asyncio
import tempfile
import traceback

from playwright.async_api import async_playwright


async def launch_positioned_browser_window(url: str, left: int, top: int, width: int, height: int):
    """
    Launches a dedicated, chrome-less Chromium window at exact OS
    coordinates. Raises on failure — the caller (open_window_async) is
    responsible for making that visible, not swallowing it.
    """
    async with async_playwright() as p:
        # A fresh temp profile per launch — these are throwaway JARVIS
        # content windows, not sessions that need to persist login state
        # across runs. Using a real (even if temporary) user_data_dir is
        # what makes launch_persistent_context's window behave like an
        # actual app window rather than an automation-only context.
        with tempfile.TemporaryDirectory(prefix="jarvis-window-") as profile_dir:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                args=[
                    f"--window-position={left},{top}",
                    f"--window-size={width},{height}",
                    f"--app={url}",  # chrome-less window, no address bar
                ],
            )
            # launch_persistent_context already opens one page for the
            # --app= window — reuse it instead of creating an unrelated
            # second one via new_page().
            page = context.pages[0] if context.pages else await context.new_page()
            if page.url in ("about:blank", ""):
                await page.goto(url)

            # Keep the window's process alive until the user closes it.
            while context.pages:
                await asyncio.sleep(1)


def open_window_async(url: str, left: int, top: int, width: int, height: int):
    """
    Bridge sync call to async event loop. Runs in a background thread
    (started by server.py's /open-browser route) — any exception here
    would otherwise vanish silently, since the HTTP response has already
    been sent by the time this actually executes. Printing it loudly is
    the minimum needed to make failures visible again; see the note in
    server.py about surfacing this to the frontend too.
    """
    try:
        asyncio.run(launch_positioned_browser_window(url, left, top, width, height))
    except Exception:
        print(f"\n[JARVIS] Failed to open browser window for {url}:")
        traceback.print_exc()
        print(
            "[JARVIS] If this says something like 'Executable doesn't exist', "
            "run: playwright install chromium\n"
        )
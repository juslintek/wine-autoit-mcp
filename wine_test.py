"""
wine_test — Playwright-style testing framework for Windows apps running in Wine.

Usage:
    from wine_test import WineApp

    app = WineApp("path/to/app.exe")
    app.wait_for_window("My App", timeout=15)
    app.screenshot("login.png")
    app.seq("c s1 t s1 e")  # clear, type 1, tab, type 1, enter
    app.wait_for_window("Main Window")
    app.screenshot("main.png")
    app.close()
"""

import os
import json
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Window:
    hwnd: int
    title: str


class WineApp:
    def __init__(self, exe_path: str, wineprefix: str = None, wine: str = None, winetools: str = None):
        self.exe_path = exe_path
        self.wineprefix = wineprefix or os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine-gotas"))
        self.wine = wine or os.environ.get("WINE", "/opt/homebrew/bin/wine")
        self.winetools = winetools or os.environ.get("WINETOOLS_PATH", "C:\\winetools.exe")
        self._process = None
        self._hwnd = None

    # --- Lifecycle ---

    def launch(self):
        """Launch the app. Called automatically if not already running."""
        env = {**os.environ, "WINEPREFIX": self.wineprefix, "WINEDEBUG": "-all"}
        self._process = subprocess.Popen(
            [self.wine, self.exe_path],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return self

    def close(self):
        """Kill the app."""
        if self._process:
            self._process.kill()
            self._process = None

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, *_):
        self.close()

    # --- Window discovery ---

    def windows(self) -> list[Window]:
        """List all visible Wine windows."""
        result = self._wt("windows")
        return [Window(hwnd=w["hwnd"], title=w["title"]) for w in result.get("windows", [])]

    def wait_for_window(self, title_contains: str, timeout: float = 20) -> Window:
        """Wait until a window matching title appears. Sets it as the active target."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for w in self.windows():
                if title_contains in w.title:
                    self._hwnd = w.hwnd
                    return w
            time.sleep(0.5)
        raise TimeoutError(f"No window matching '{title_contains}' within {timeout}s")

    @property
    def hwnd(self) -> int:
        if not self._hwnd:
            raise RuntimeError("No window targeted. Call wait_for_window() first.")
        return self._hwnd

    # --- Input ---

    def type(self, text: str):
        """Type text into the focused field."""
        self._wt("type", str(self.hwnd), text)
        return self

    def tab(self):
        """Send Tab key."""
        self._wt("tab", str(self.hwnd))
        return self

    def enter(self):
        """Send Enter key."""
        self._wt("enter", str(self.hwnd))
        return self

    def clear(self):
        """Clear current field (End + 20x Backspace)."""
        self._wt("clear", str(self.hwnd))
        return self

    def key(self, vk: int):
        """Send a virtual key code. Common: 9=Tab, 13=Enter, 27=Escape."""
        self._wt("key", str(self.hwnd), str(vk))
        return self

    def seq(self, actions: str):
        """
        Execute multiple actions in one call (single SetForegroundWindow).
        Format: space-separated codes: t=tab, e=enter, c=clear, s<text>=type, k<vk>=key
        Example: "c s1 t s1 e" = clear, type 1, tab, type 1, enter
        """
        self._wt("seq", str(self.hwnd), *actions.split())
        return self

    # --- Screenshot ---

    def screenshot(self, path: str = None, title_filter: str = "") -> str:
        """Capture screenshot of the Wine window. Returns file path."""
        swift = f'''
import CoreGraphics, Foundation
let opts = CGWindowListOption([.optionOnScreenOnly, .excludeDesktopElements])
guard let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {{ exit(1) }}
var best = (wid: 0, area: 0)
for w in list {{
    let owner = w["kCGWindowOwnerName"] as? String ?? ""
    let name = w["kCGWindowName"] as? String ?? ""
    guard owner == "wine" else {{ continue }}
    if !{json.dumps(title_filter)}.isEmpty && !name.contains({json.dumps(title_filter)}) {{ continue }}
    let b = w["kCGWindowBounds"] as? [String: Any] ?? [:]
    let area = (b["Width"] as? Int ?? 0) * (b["Height"] as? Int ?? 0)
    let wid = w["kCGWindowNumber"] as? Int ?? 0
    if area > best.area {{ best = (wid, area) }}
}}
if best.wid > 0 {{ print(best.wid) }}
'''
        r = subprocess.run(["swift", "-"], input=swift, capture_output=True, text=True, timeout=8)
        wid = r.stdout.strip()
        if not wid:
            raise RuntimeError("No Wine window found for screenshot")
        out = path or f"/tmp/wine_screenshot_{int(time.time())}.png"
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["screencapture", "-x", "-l", wid, out], check=True, timeout=5)
        return out

    # --- Assertions ---

    def assert_window_title(self, contains: str):
        """Assert the current window title contains the given text."""
        result = self._wt("title", str(self.hwnd))
        title = result.get("title", "")
        assert contains in title, f"Expected '{contains}' in title, got: '{title}'"
        return self

    def assert_window_exists(self, title_contains: str):
        """Assert a window with matching title exists."""
        for w in self.windows():
            if title_contains in w.title:
                return self
        raise AssertionError(f"No window matching '{title_contains}'")

    # --- Internal ---

    def _wt(self, *args) -> dict:
        env = {**os.environ, "WINEPREFIX": self.wineprefix, "WINEDEBUG": "-all"}
        r = subprocess.run(
            [self.wine, self.winetools, *args],
            env=env, capture_output=True, text=True, timeout=10,
        )
        if r.stdout.strip():
            return json.loads(r.stdout.strip())
        return {}


# --- Convenience ---

def wine_app(exe_path: str, **kwargs) -> WineApp:
    """Create and launch a WineApp. Use as context manager or call .close()."""
    app = WineApp(exe_path, **kwargs)
    app.launch()
    return app

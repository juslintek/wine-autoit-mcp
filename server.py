#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0"]
# ///
"""
Wine MCP Server — control Windows apps running in Wine on macOS.

Uses winetools.exe (compiled C, 50KB) for window enumeration and keyboard input.
Uses macOS screencapture -l for screenshots. No AutoIt, no file IPC, no polling.

Setup:
  1. Compile: i686-w64-mingw32-gcc -O2 -o winetools.exe winetools.c -luser32
  2. Copy winetools.exe to your Wine prefix: C:\winetools.exe
  3. Register this server in your MCP client config
"""

import os
import time
import json
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

WINEPREFIX = os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine-gotas"))
WINE = os.environ.get("WINE", "/opt/homebrew/bin/wine")
WINETOOLS = os.environ.get("WINETOOLS_PATH", "C:\\winetools.exe")
SCREENSHOT_DIR = Path(WINEPREFIX) / "drive_c/screenshots"

mcp = FastMCP("wine-mcp")


def _run(*args: str, timeout: float = 10) -> dict:
    """Run winetools.exe with args, return parsed JSON output."""
    env = {**os.environ, "WINEPREFIX": WINEPREFIX, "WINEDEBUG": "-all"}
    try:
        r = subprocess.run(
            [WINE, WINETOOLS, *args],
            env=env, capture_output=True, text=True, timeout=timeout,
        )
        if r.stdout.strip():
            return json.loads(r.stdout.strip())
        if r.returncode != 0:
            return {"error": r.stderr.strip() or f"exit code {r.returncode}"}
        return {"ok": True}
    except json.JSONDecodeError:
        return {"raw": r.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}


def _screenshot_macos(title_substring: str = "") -> dict:
    """Capture Wine window via macOS screencapture -l."""
    swift = f'''
import CoreGraphics, Foundation
let opts = CGWindowListOption([.optionOnScreenOnly, .excludeDesktopElements])
guard let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {{ exit(1) }}
var best = (wid: 0, area: 0)
for w in list {{
    let owner = w["kCGWindowOwnerName"] as? String ?? ""
    let name = w["kCGWindowName"] as? String ?? ""
    guard owner == "wine" else {{ continue }}
    if !{json.dumps(title_substring)}.isEmpty && !name.contains({json.dumps(title_substring)}) {{ continue }}
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
        return {"error": "no Wine window found"}
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = str(SCREENSHOT_DIR / f"cap_{int(time.time())}.png")
    subprocess.run(["screencapture", "-x", "-l", wid, out], check=True, timeout=5)
    return {"ok": True, "file": out, "window_id": int(wid)}


@mcp.tool()
def windows_list() -> dict:
    """List all visible windows in Wine with their HWNDs and titles."""
    return _run("windows")


@mcp.tool()
def window_children(hwnd: str) -> dict:
    """List child windows of a given HWND."""
    return _run("children", hwnd)


@mcp.tool()
def window_title(hwnd: str) -> dict:
    """Get the title of a window."""
    return _run("title", hwnd)


@mcp.tool()
def window_pos(hwnd: str) -> dict:
    """Get window position and size: {x, y, w, h}."""
    return _run("pos", hwnd)


@mcp.tool()
def type_text(hwnd: str, text: str) -> dict:
    """Type text into a window using SendInput (Unicode). Brings window to foreground."""
    return _run("type", hwnd, text)


@mcp.tool()
def send_key(hwnd: str, vk: str) -> dict:
    """Send a virtual key code. Common: 9=Tab, 13=Enter, 27=Escape, 8=Backspace."""
    return _run("key", hwnd, vk)


@mcp.tool()
def send_tab(hwnd: str) -> dict:
    """Send Tab key."""
    return _run("tab", hwnd)


@mcp.tool()
def send_enter(hwnd: str) -> dict:
    """Send Enter key."""
    return _run("enter", hwnd)


@mcp.tool()
def clear_field(hwnd: str) -> dict:
    """Clear current field (End + 20x Backspace)."""
    return _run("clear", hwnd)


@mcp.tool()
def send_sequence(hwnd: str, actions: str) -> dict:
    """
    Execute multiple actions in one invocation (single SetForegroundWindow call).
    actions: space-separated action codes:
      t = Tab, e = Enter, c = Clear
      s<text> = type text (e.g. 's1' types '1', 'sHello' types 'Hello')
      k<vk> = virtual key (e.g. 'k27' sends Escape)
    Example: 'c s1 t s1 e' = clear, type 1, tab, type 1, enter
    """
    parts = actions.split()
    return _run("seq", hwnd, *parts)


@mcp.tool()
def screenshot(title_substring: str = "") -> dict:
    """
    Capture a screenshot of a Wine window (macOS only).
    title_substring: optional filter. Empty = largest Wine window.
    Returns file path of the PNG.
    """
    return _screenshot_macos(title_substring)


@mcp.tool()
def login(hwnd: str, user_id: str, password: str) -> dict:
    """
    Login to a VFP app. Uses seq: clear ID, type user_id, tab, type password, enter.
    All in one invocation so SetForegroundWindow is only called once.
    """
    return _run("seq", hwnd, f"c", f"s{user_id}", "t", f"s{password}", "e")


if __name__ == "__main__":
    mcp.run()

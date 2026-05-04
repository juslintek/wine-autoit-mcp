#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0"]
# ///
"""
Wine AutoIt MCP Server — wraps file-based IPC with bridge.au3 running in Wine.

Bridge IPC directory: ~/.wine-gotas/drive_c/AutoIt3/bridge/
Commands are written to command.json; results read from result.json.
"""

import os
import time
import json
import subprocess
import glob as _glob
from pathlib import Path
from mcp.server.fastmcp import FastMCP

WINEPREFIX = os.environ.get("WINEPREFIX", os.path.expanduser("~/.wine-gotas"))
BRIDGE_DIR = Path(WINEPREFIX) / "drive_c/AutoIt3/bridge"
CMD_FILE = BRIDGE_DIR / "command.json"
RESULT_FILE = BRIDGE_DIR / "result.json"
STATUS_FILE = BRIDGE_DIR / "status.txt"
AUTOIT_EXE = "C:\\AutoIt3\\AutoIt3.exe"
BRIDGE_SCRIPT = "C:\\AutoIt3\\bridge.au3"
WINE = os.environ.get("WINE", "/opt/homebrew/bin/wine")

mcp = FastMCP("wine-autoit-bridge")


def _send(command: str, timeout: float = 10.0) -> dict:
    """Write command, wait for result, return parsed JSON."""
    RESULT_FILE.unlink(missing_ok=True)
    CMD_FILE.write_text(command)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if RESULT_FILE.exists():
            raw = RESULT_FILE.read_text().strip()
            if raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"raw": raw}
        time.sleep(0.1)
    return {"error": f"timeout after {timeout}s waiting for result"}


def _bridge_running() -> bool:
    return STATUS_FILE.exists() and STATUS_FILE.read_text().strip() == "ready"


def _macos_window_id(title_substring: str) -> str | None:
    """Find macOS window ID by title substring using Swift CGWindowList."""
    swift = f'''
import CoreGraphics
import Foundation
let opts = CGWindowListOption([.optionOnScreenOnly, .excludeDesktopElements])
if let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String:Any]] {{
    for w in list {{
        let name = w["kCGWindowName"] as? String ?? ""
        let wid = w["kCGWindowNumber"] as? Int ?? 0
        if name.contains({json.dumps(title_substring)}) {{
            print(wid)
            break
        }}
    }}
}}
'''
    r = subprocess.run(["swift", "-"], input=swift, capture_output=True, text=True)
    return r.stdout.strip() or None


@mcp.tool()
def bridge_start() -> dict:
    """Start the AutoIt3 bridge inside Wine. Idempotent — safe to call if already running."""
    if _bridge_running():
        return {"ok": True, "status": "already running"}
    STATUS_FILE.unlink(missing_ok=True)
    env = {**os.environ, "WINEPREFIX": WINEPREFIX, "WINEDEBUG": "-all"}
    subprocess.Popen(
        [WINE, AUTOIT_EXE, BRIDGE_SCRIPT],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if _bridge_running():
            return {"ok": True, "status": "started"}
        time.sleep(0.1)
    return {"error": "bridge did not signal ready within 5s"}


@mcp.tool()
def bridge_stop() -> dict:
    """Stop the AutoIt3 bridge."""
    return _send("quit", timeout=3.0)


@mcp.tool()
def bridge_status() -> dict:
    """Check if the AutoIt3 bridge is running."""
    running = _bridge_running()
    return {"running": running, "status": STATUS_FILE.read_text().strip() if STATUS_FILE.exists() else "not found"}


@mcp.tool()
def windows_list() -> dict:
    """List all visible windows currently open in Wine."""
    return _send("windows")


@mcp.tool()
def screenshot() -> dict:
    """Capture a full-screen screenshot inside Wine. Returns file path."""
    return _send("screenshot")


@mcp.tool()
def screenshot_window(hwnd: str) -> dict:
    """
    Capture a screenshot of a specific Wine window by HWND, without needing it in front.
    Uses macOS screencapture -l with Swift CGWindowList to find the window by title.
    hwnd: window handle (integer as string, from windows_list).
    """
    result = _send(f"wintitle|{hwnd}")
    title = result.get("title", "")
    if not title:
        return {"error": "could not get window title"}
    wid = _macos_window_id(title)
    if not wid:
        return {"error": f"macOS window not found for title: {title}"}
    out = str(BRIDGE_DIR / f"screenshots/mac_{int(time.time())}.png")
    subprocess.run(["screencapture", "-l", wid, out], check=True)
    return {"ok": True, "file": out}


@mcp.tool()
def screenshot_by_title(title_substring: str) -> dict:
    """
    Capture a screenshot of a Wine window matching a title substring.
    Works without the window being in front (macOS screencapture -l).
    title_substring: partial window title, e.g. 'Gotas SQL' or 'Program Error'.
    """
    wid = _macos_window_id(title_substring)
    if not wid:
        return {"error": f"no window found matching: {title_substring}"}
    out = str(BRIDGE_DIR / f"screenshots/mac_{int(time.time())}.png")
    subprocess.run(["screencapture", "-l", wid, out], check=True)
    return {"ok": True, "file": out, "window_id": wid}


@mcp.tool()
def window_tree(hwnd: str) -> dict:
    """
    List all controls inside a window.
    hwnd: window handle (integer as string, from windows_list).
    """
    return _send(f"tree|{hwnd}")


@mcp.tool()
def control_get_text(hwnd: str, control_id: str) -> dict:
    """
    Read text from a control.
    hwnd: window handle. control_id: e.g. '[CLASS:Edit; INSTANCE:1]'.
    """
    return _send(f"gettext|{hwnd}|{control_id}")


@mcp.tool()
def control_set_text(hwnd: str, control_id: str, text: str) -> dict:
    """
    Set text in a control (type into a field).
    hwnd: window handle. control_id: e.g. '[CLASS:Edit; INSTANCE:1]'. text: value to set.
    """
    return _send(f"settext|{hwnd}|{control_id}|{text}")


@mcp.tool()
def control_click(hwnd: str, control_id: str = "") -> dict:
    """
    Click a control or window.
    hwnd: window handle. control_id: optional, e.g. '[CLASS:Button; INSTANCE:1]'.
    """
    if control_id:
        return _send(f"click|{hwnd}|{control_id}")
    return _send(f"click|{hwnd}")


@mcp.tool()
def send_key(key: str) -> dict:
    """
    Send keystrokes to the active window. Uses AutoIt Send() syntax.
    Examples: '{ENTER}', '{TAB}', '{ESC}', 'Hello{ENTER}', '!{F4}'.
    """
    return _send(f"key|{key}")


@mcp.tool()
def send_to_window(hwnd: str, keys: str) -> dict:
    """
    Activate a window and send keystrokes to it atomically.
    Waits for the window to have focus before sending.
    hwnd: window handle. keys: AutoIt Send() syntax.
    """
    return _send(f"sendtowindow|{hwnd}|{keys}")


@mcp.tool()
def window_activate(hwnd: str) -> dict:
    """Bring a window to the foreground."""
    return _send(f"activate|{hwnd}")


@mcp.tool()
def window_pos(hwnd: str) -> dict:
    """Get position and size of a window: {x, y, w, h}."""
    return _send(f"winpos|{hwnd}")


@mcp.tool()
def click_pos(x: int, y: int) -> dict:
    """Click at screen coordinates (Wine coordinate space)."""
    return _send(f"clickpos|{x}|{y}")


@mcp.tool()
def list_screenshots() -> dict:
    """List all screenshots captured by the bridge."""
    screen_dir = BRIDGE_DIR / "screenshots"
    files = sorted(_glob.glob(str(screen_dir / "*.png")))
    return {"screenshots": files, "count": len(files)}


if __name__ == "__main__":
    mcp.run()

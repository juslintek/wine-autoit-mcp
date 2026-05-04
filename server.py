#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0"]
# ///
"""
Wine AutoIt MCP Server — wraps file-based IPC with bridge.au3 running in Wine.

Bridge IPC directory: ~/.wine-gotas/drive_c/AutoIt3/bridge/
Commands are written to command.json; results read from result.json.

Screenshot approach:
- Inside Wine virtual desktop: use bridge screenshot command (AutoIt _ScreenCapture_Capture)
- Both app and bridge must run inside the same named virtual desktop:
    wine explorer /desktop=gotas,1024x768 gotassql.exe
    wine explorer /desktop=gotas,1024x768 AutoIt3.exe bridge.au3
- screenshot_by_title: macOS-only fallback using screencapture -l <windowID>
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
DESKTOP = os.environ.get("WINE_DESKTOP", "gotas")  # virtual desktop name

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
        time.sleep(0.02)  # 20ms — matches bridge poll interval
    return {"error": f"timeout after {timeout}s waiting for result"}


def _bridge_running() -> bool:
    return STATUS_FILE.exists() and STATUS_FILE.read_text().strip() == "ready"


def _wine_run(*args: str) -> subprocess.Popen:
    """Launch a Wine process inside the named virtual desktop."""
    env = {**os.environ, "WINEPREFIX": WINEPREFIX, "WINEDEBUG": "-all"}
    return subprocess.Popen(
        [WINE, "explorer", f"/desktop={DESKTOP},1024x768", *args],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@mcp.tool()
def bridge_start() -> dict:
    """
    Start the AutoIt3 bridge inside Wine virtual desktop.
    Both bridge and app must share the same desktop name (default: 'gotas').
    Idempotent — safe to call if already running.
    """
    if _bridge_running():
        return {"ok": True, "status": "already running"}
    STATUS_FILE.unlink(missing_ok=True)
    _wine_run(AUTOIT_EXE, BRIDGE_SCRIPT)
    for _ in range(250):  # wait up to 5s
        if _bridge_running():
            return {"ok": True, "status": "started"}
        time.sleep(0.02)
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
    """List all visible windows in the Wine virtual desktop."""
    return _send("windows")


@mcp.tool()
def screenshot() -> dict:
    """
    Capture a screenshot of the Wine virtual desktop.
    Requires bridge and app to share the same virtual desktop (explorer /desktop=gotas).
    Returns the file path of the saved PNG inside the Wine prefix.
    """
    return _send("screenshot")


@mcp.tool()
def screenshot_by_title(title_substring: str) -> dict:
    """
    macOS-only: capture a Wine window by title substring using screencapture -l.
    Works without the window being in front. Does NOT require virtual desktop.
    title_substring: partial window title, e.g. 'Gotas SQL'.
    """
    swift = f'''
import CoreGraphics,Foundation
let opts=CGWindowListOption([.optionOnScreenOnly,.excludeDesktopElements])
if let l=CGWindowListCopyWindowInfo(opts,kCGNullWindowID) as? [[String:Any]] {{
    for w in l {{
        let name=w["kCGWindowName"] as? String ?? ""
        let wid=w["kCGWindowNumber"] as? Int ?? 0
        if name.contains({json.dumps(title_substring)}) {{ print(wid); break }}
    }}
}}
'''
    r = subprocess.run(["swift", "-"], input=swift, capture_output=True, text=True)
    wid = r.stdout.strip()
    if not wid:
        return {"error": f"no window found matching: {title_substring}"}
    out = str(BRIDGE_DIR / f"screenshots/mac_{int(time.time())}.png")
    subprocess.run(["screencapture", "-l", wid, out], check=True)
    return {"ok": True, "file": out, "window_id": wid}


@mcp.tool()
def login(hwnd: str, user_id: str, password: str) -> dict:
    """
    Fill and submit the GotasSQL login form.
    Uses PostMessage WM_CHAR to child HWNDs — no WinActivate, no mouse movement.
    hwnd: login window handle (from windows_list).
    user_id: operator ID string, e.g. '1'.
    password: plaintext password (e.g. '1').
    """
    return _send(f"login|{hwnd}|{user_id}|{password}", timeout=10.0)


@mcp.tool()
def window_children(hwnd: str) -> dict:
    """List direct child window HWNDs of a window."""
    return _send(f"children|{hwnd}")


@mcp.tool()
def window_tree(hwnd: str) -> dict:
    """List all controls inside a window by Win32 class/instance."""
    return _send(f"tree|{hwnd}")


@mcp.tool()
def control_get_text(hwnd: str, control_id: str) -> dict:
    """Read text from a control. control_id: e.g. '[CLASS:Edit; INSTANCE:1]'."""
    return _send(f"gettext|{hwnd}|{control_id}")


@mcp.tool()
def control_set_text(hwnd: str, control_id: str, text: str) -> dict:
    """Set text in a control via WM_SETTEXT."""
    return _send(f"settext|{hwnd}|{control_id}|{text}")


@mcp.tool()
def control_click(hwnd: str, control_id: str = "") -> dict:
    """Click a control or window."""
    if control_id:
        return _send(f"click|{hwnd}|{control_id}")
    return _send(f"click|{hwnd}")


@mcp.tool()
def send_key(key: str) -> dict:
    """
    Send keystrokes to the active window. AutoIt Send() syntax.
    Examples: '{ENTER}', '{TAB}', '1{TAB}password{ENTER}'.
    Only works reliably inside a Wine virtual desktop (no focus stealing).
    """
    return _send(f"key|{key}")


@mcp.tool()
def post_char(hwnd: str, char: str) -> dict:
    """Post a single WM_CHAR to a window HWND without focus/activation."""
    return _send(f"postchar|{hwnd}|{char}")


@mcp.tool()
def post_key(hwnd: str, vkcode: int) -> dict:
    """Post WM_KEYDOWN+KEYUP for a virtual key code to a window HWND."""
    return _send(f"postkey|{hwnd}|{vkcode}")


@mcp.tool()
def window_pos(hwnd: str) -> dict:
    """Get position and size of a window: {x, y, w, h}."""
    return _send(f"winpos|{hwnd}")


@mcp.tool()
def list_screenshots() -> dict:
    """List all screenshots captured by the bridge."""
    files = sorted(_glob.glob(str(BRIDGE_DIR / "screenshots" / "*.png")))
    return {"screenshots": files, "count": len(files)}


if __name__ == "__main__":
    mcp.run()

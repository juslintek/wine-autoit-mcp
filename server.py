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

Input injection:
- sendinput.exe: compiled C program using Win32 SendInput API
- Works cross-process, uses SetForegroundWindow + SendInput with proper scan codes
- Compile: i686-w64-mingw32-gcc -O2 -o sendinput.exe sendinput.c -luser32
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
DESKTOP = os.environ.get("WINE_DESKTOP", "gotas")

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
        time.sleep(0.02)
    return {"error": f"timeout after {timeout}s waiting for result"}


def _bridge_running() -> bool:
    return STATUS_FILE.exists() and STATUS_FILE.read_text().strip() == "ready"


def _wine_run(*args: str) -> subprocess.Popen:
    env = {**os.environ, "WINEPREFIX": WINEPREFIX, "WINEDEBUG": "-all"}
    return subprocess.Popen(
        [WINE, "explorer", f"/desktop={DESKTOP},1024x768", *args],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _screenshot_macos() -> dict | None:
    """macOS fallback: find largest Wine window and capture via screencapture -l."""
    import platform
    if platform.system() != "Darwin":
        return None
    swift = """
import CoreGraphics, Foundation
let opts = CGWindowListOption([.optionOnScreenOnly, .excludeDesktopElements])
guard let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else { exit(1) }
var best = (wid: 0, area: 0)
for w in list {
    guard (w["kCGWindowOwnerName"] as? String) == "wine" else { continue }
    let b = w["kCGWindowBounds"] as? [String: Any] ?? [:]
    let area = (b["Width"] as? Int ?? 0) * (b["Height"] as? Int ?? 0)
    let wid = w["kCGWindowNumber"] as? Int ?? 0
    if area > best.area { best = (wid, area) }
}
if best.wid > 0 { print(best.wid) }
"""
    try:
        r = subprocess.run(["swift", "-"], input=swift, capture_output=True, text=True, timeout=8)
        wid = r.stdout.strip()
        if not wid:
            return None
        out = str(BRIDGE_DIR / f"screenshots/mac_{int(time.time())}.png")
        subprocess.run(["screencapture", "-x", "-l", wid, out], check=True, timeout=5)
        return {"ok": True, "file": out, "source": "macos_fallback"}
    except Exception:
        return None


@mcp.tool()
def bridge_start() -> dict:
    """Start the AutoIt3 bridge inside Wine virtual desktop. Idempotent."""
    if _bridge_running():
        return {"ok": True, "status": "already running"}
    STATUS_FILE.unlink(missing_ok=True)
    _wine_run(AUTOIT_EXE, BRIDGE_SCRIPT)
    for _ in range(250):
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
    return {"running": _bridge_running(), "status": STATUS_FILE.read_text().strip() if STATUS_FILE.exists() else "not found"}


@mcp.tool()
def windows_list() -> dict:
    """List all visible windows in the Wine session."""
    return _send("windows")


@mcp.tool()
def screenshot() -> dict:
    """
    Capture a screenshot. Tries AutoIt _ScreenCapture_Capture first (works in virtual desktop).
    Falls back to macOS screencapture -l if result is black (<5KB).
    """
    result = _send("screenshot")
    if not (isinstance(result, dict) and result.get("ok")):
        return result
    wine_path = result.get("file", "")
    unix_path = Path(WINEPREFIX) / "drive_c" / wine_path.replace("C:\\", "").replace("\\", "/")
    if unix_path.exists() and unix_path.stat().st_size < 5000:
        fallback = _screenshot_macos()
        if fallback:
            return fallback
    return result


@mcp.tool()
def screenshot_by_title(title_substring: str) -> dict:
    """
    macOS-only: capture a Wine window by title substring using screencapture -l.
    Works without the window being in front.
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
    subprocess.run(["screencapture", "-x", "-l", wid, out], check=True)
    return {"ok": True, "file": out, "window_id": wid}


@mcp.tool()
def sendinput(hwnd: str, action: str, value: str = "") -> dict:
    """
    Inject keyboard input into a Wine window using SendInput (via sendinput.exe).
    Works cross-process, brings window to foreground.
    hwnd: target window handle (decimal, from windows_list).
    action: one of 'text', 'tab', 'enter', 'clear', 'vk'.
    value: text to type (for 'text'), or VK code string (for 'vk').
    """
    exe = Path(WINEPREFIX) / "drive_c/AutoIt3/sendinput.exe"
    if not exe.exists():
        return {"error": "sendinput.exe not found — copy it to C:\\AutoIt3\\sendinput.exe"}
    env = {**os.environ, "WINEPREFIX": WINEPREFIX, "WINEDEBUG": "-all"}
    args = [WINE, "C:\\AutoIt3\\sendinput.exe", hwnd]
    if action == "text":
        args.append(value)
    elif action == "tab":
        args.append("--tab")
    elif action == "enter":
        args.append("--enter")
    elif action == "clear":
        args.append("--clear")
    elif action == "vk":
        args.extend(["--vk", value])
    else:
        return {"error": f"unknown action: {action}. Use text/tab/enter/clear/vk"}
    subprocess.run(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    return {"ok": True}


@mcp.tool()
def login(hwnd: str, user_id: str, password: str) -> dict:
    """
    Fill and submit login form using sendinput.exe.
    Assumes focus starts on user ID field (pre-filled). Tabs to password, types, submits.
    hwnd: login window handle. user_id: operator ID. password: plaintext password.
    """
    exe = Path(WINEPREFIX) / "drive_c/AutoIt3/sendinput.exe"
    if not exe.exists():
        return {"error": "sendinput.exe not found"}
    env = {**os.environ, "WINEPREFIX": WINEPREFIX, "WINEDEBUG": "-all"}
    def si(*a):
        subprocess.run([WINE, "C:\\AutoIt3\\sendinput.exe", hwnd, *a],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        time.sleep(0.3)
    si("--clear")
    si(user_id)
    si("--tab")
    si(password)
    si("--enter")
    return {"ok": True}


@mcp.tool()
def window_children(hwnd: str) -> dict:
    """List direct child window HWNDs."""
    return _send(f"children|{hwnd}")


@mcp.tool()
def window_tree(hwnd: str) -> dict:
    """List all controls by Win32 class/instance."""
    return _send(f"tree|{hwnd}")


@mcp.tool()
def control_get_text(hwnd: str, control_id: str) -> dict:
    """Read text from a control."""
    return _send(f"gettext|{hwnd}|{control_id}")


@mcp.tool()
def control_click(hwnd: str, control_id: str = "") -> dict:
    """Click a control or window."""
    if control_id:
        return _send(f"click|{hwnd}|{control_id}")
    return _send(f"click|{hwnd}")


@mcp.tool()
def send_key(key: str) -> dict:
    """Send keystrokes to active window (AutoIt Send syntax). Only reliable in virtual desktop."""
    return _send(f"key|{key}")


@mcp.tool()
def window_pos(hwnd: str) -> dict:
    """Get window position and size: {x, y, w, h}."""
    return _send(f"winpos|{hwnd}")


@mcp.tool()
def list_screenshots() -> dict:
    """List all captured screenshots."""
    files = sorted(_glob.glob(str(BRIDGE_DIR / "screenshots" / "*.png")))
    return {"screenshots": files, "count": len(files)}


if __name__ == "__main__":
    mcp.run()

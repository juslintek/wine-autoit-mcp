# wine-autoit-mcp Improvement Plan

## Current Issues

### 1. Screenshots are BLACK (Critical)
**Root cause**: Wine's Mac driver renders via Metal/CoreAnimation. Neither GDI `BitBlt` nor `PrintWindow` can capture the framebuffer — they return black pixels.

**Solutions (in order of feasibility)**:
- **A. Use Wine's X11 driver instead of Mac driver**: Set `DISPLAY` and use XQuartz. X11 driver uses GDI-compatible rendering. Requires XQuartz installed.
- **B. Use `explorer /desktop=name,WxH` with X11 backend**: Virtual desktop with X11 allows GDI capture.
- **C. Add a macOS-native screenshot tool to the MCP**: Use `screencapture -l <windowID>` to capture the Wine window from the macOS side. Requires finding the CGWindowID.
- **D. Use Wine's built-in screenshot via D3D/Vulkan capture**: Not practical.
- **Recommended**: Option C — add a `screenshot_macos` command to server.py that uses `screencapture` with the Wine window ID.

### 2. VFP Custom Controls Not Accessible (Critical)
**Root cause**: VFP renders ALL UI elements (buttons, textboxes, grids, menus) inside a single Win32 window using its own drawing engine. There are no Win32 child controls for AutoIt to interact with.

**Impact**: `window_tree` returns only top-level VFP container controls with no text. Cannot click individual buttons, read form fields, or interact with grids.

**Solutions**:
- **A. Mouse click at coordinates**: Requires knowing the layout (from source code or OCR).
- **B. Keyboard navigation**: VFP forms respond to Tab, Enter, arrow keys. Menu responds to Alt+letter IF the pad has a hotkey defined.
- **C. Inject VFP commands**: Add a command executor PRG that reads commands from a file and executes them inside the running VFP app. Requires modifying the app startup.
- **D. Add MCP tool: `mouse_click(x, y)`**: Click at absolute coordinates within the Wine window.
- **Recommended**: Combination of B + D. Add `mouse_click` tool and use keyboard navigation.

### 3. Menu Navigation Broken (High)
**Root cause**: VFP's SET SYSMENU doesn't respond to Alt key activation on Wine's Mac driver. The menu bar is rendered by VFP, not by Win32's menu system.

**Solutions**:
- **A. Add `mouse_click` tool**: Click menu items at known coordinates.
- **B. Modify app source**: Add ON KEY LABEL bindings for each menu item.
- **C. Use VFP's KEYBOARD command**: Inject keystrokes into VFP's keyboard buffer (requires command injection).

### 4. MCP Server Not Being Used Effectively
**Root cause**: The MCP tools (`bridge_start`, `windows_list`, `send_key`, etc.) work but return raw JSON strings that need parsing. The `screenshot` tool returns black images. The `window_tree` tool returns useless data for VFP apps.

**Improvements needed**:
- Parse JSON responses properly in server.py (return structured data, not raw strings)
- Add new tools specific to VFP automation
- Add coordinate-based mouse click tool
- Add OCR-based text reading (if screenshots work)

## Proposed New MCP Tools

| Tool | Description |
|------|-------------|
| `mouse_click(x, y)` | Click at coordinates relative to Wine window |
| `mouse_double_click(x, y)` | Double-click at coordinates |
| `screenshot_macos()` | Capture Wine window via macOS screencapture |
| `vfp_command(cmd)` | Execute VFP command in running app (requires injection) |
| `get_pixel_color(x, y)` | Read pixel color at position (for UI state detection) |
| `wait_for_change(timeout)` | Wait until window content changes |
| `drag(x1, y1, x2, y2)` | Mouse drag operation |

## Architecture Issues

1. **server.py writes commands as files** — this is correct but the newline handling caused issues earlier
2. **Bridge polls every 100ms** — adequate for interactive use
3. **No error recovery** — if bridge crashes, MCP server doesn't restart it
4. **Single-threaded** — can't take screenshot while waiting for a command result

## Priority Fixes

1. **Fix screenshots** — implement macOS-native capture via `screencapture -l`
2. **Add `mouse_click` tool** — essential for VFP menu/button interaction
3. **Fix JSON response parsing** — return clean structured data
4. **Add auto-restart** — bridge_start should kill stale bridges
5. **Add coordinate mapping** — tool to convert VFP form layout to click coordinates

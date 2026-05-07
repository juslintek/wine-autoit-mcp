# wine-mcp

An [MCP](https://modelcontextprotocol.io) server for controlling Windows applications running in [Wine](https://www.winehq.org/) on macOS.

**No AutoIt. No file IPC. No polling.** Just a 50KB compiled C tool (`winetools.exe`) and a Python MCP wrapper.

## Architecture

```
AI agent / MCP client
        ↕  MCP (stdio)
    server.py          ← Python, runs on host
        ↕  subprocess
    winetools.exe      ← runs inside Wine, returns JSON to stdout
        ↕  Win32 API (EnumWindows, SendInput, SetForegroundWindow)
  Windows app (Wine)
```

Screenshots use macOS `screencapture -l <windowID>` via Swift CGWindowList — non-invasive, works without focus.

## Requirements

- macOS (ARM64 or Intel)
- [Wine](https://www.winehq.org/) (tested with 11.0)
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [mingw-w64](https://www.mingw-w64.org/) — for compiling winetools.exe (`brew install mingw-w64`)

## Setup

### 1. Compile winetools.exe

```bash
i686-w64-mingw32-gcc -O2 -o winetools.exe winetools.c -luser32
```

### 2. Copy to Wine prefix

```bash
cp winetools.exe ~/.wine/drive_c/winetools.exe
```

### 3. Register MCP server

Add to your MCP client config:

```json
{
  "mcpServers": {
    "wine-mcp": {
      "command": "uv",
      "args": ["run", "--script", "/path/to/server.py"],
      "env": {
        "WINEPREFIX": "/Users/you/.wine",
        "WINE": "/opt/homebrew/bin/wine"
      }
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `windows_list` | List all visible Wine windows (HWND + title) |
| `window_children` | List child HWNDs of a window |
| `window_title` | Get window title |
| `window_pos` | Get window position and size |
| `type_text` | Type text via SendInput (Unicode) |
| `send_key` | Send virtual key code (9=Tab, 13=Enter, 27=Esc) |
| `send_tab` | Send Tab |
| `send_enter` | Send Enter |
| `clear_field` | Clear field (End + 20×Backspace) |
| `send_sequence` | Multiple actions in one call (no re-activation) |
| `screenshot` | Capture Wine window via macOS screencapture -l |
| `login` | VFP login sequence (clear, type ID, tab, type password, enter) |

## Example: Login

```python
# From MCP client:
result = windows_list()  # {"windows": [{"title": "My App", "hwnd": 131174}]}
login(hwnd="131174", user_id="1", password="secret")
screenshot()  # captures the window after login
```

## winetools.exe Commands

```bash
wine winetools.exe windows                    # list windows
wine winetools.exe children 131174            # list child HWNDs
wine winetools.exe title 131174               # get title
wine winetools.exe pos 131174                 # get position
wine winetools.exe type 131174 "Hello"        # type text
wine winetools.exe key 131174 9               # send Tab
wine winetools.exe tab 131174                 # send Tab
wine winetools.exe enter 131174               # send Enter
wine winetools.exe clear 131174               # clear field
wine winetools.exe seq 131174 c s1 t s1 e     # clear, type 1, tab, type 1, enter
```

## Limitations

- **Input requires foreground**: `SendInput` only works on the foreground window. Each `winetools.exe` call brings the target window to front.
- **Screenshots are macOS-only**: Uses `screencapture -l` with CGWindowList. Linux would need a different approach (Xvfb + xwd).
- **No accessibility tree**: VFP custom controls don't expose MSAA/UIA. Navigation is by Tab order only.

## Why not AutoIt?

AutoIt was the original approach but has critical issues in Wine on macOS:
- `WinActivate` crashes Wine (null pointer dereference in cross-process window activation)
- `_ScreenCapture_Capture` produces black images (winemac.drv doesn't support GDI BitBlt from screen DC)
- File-based IPC adds 100ms+ latency per command
- `ControlSend`/`PostMessage WM_CHAR` don't work with VFP custom controls

`winetools.exe` solves all of these: direct subprocess call, JSON on stdout, `SendInput` with proper scan codes.

## License

MIT

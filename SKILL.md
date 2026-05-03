# wine-autoit-mcp

MCP server that bridges AI agent tool calls to AutoIt3 running inside Wine, enabling programmatic control of Windows desktop applications on macOS/Linux.

## When to Load This Skill

Load when the task involves:
- Automating or testing Windows apps running in Wine
- Window enumeration, control interaction, screenshots of Wine apps
- `bridge.au3` or `server.py` from this repo

## Architecture

```
AI agent / MCP client
  ↕ MCP (stdio)
server.py  (Python, uv inline deps)
  ↕ file IPC  (~/.wine-prefix/drive_c/AutoIt3/bridge/)
bridge.au3  (AutoIt3.exe inside Wine)
  ↕ Win32 API
Windows app (Wine)
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `bridge_start` | Start AutoIt3 bridge in Wine (idempotent) |
| `bridge_stop` | Stop the bridge |
| `bridge_status` | Check if bridge is running |
| `windows_list` | List all visible Wine windows |
| `screenshot` | Capture full-screen PNG, returns file path |
| `window_tree` | List all controls in a window by HWND |
| `control_get_text` | Read text from a control |
| `control_set_text` | Type text into a control |
| `control_click` | Click a control or window |
| `send_key` | Send keystrokes (AutoIt Send() syntax) |
| `list_screenshots` | List all captured screenshots |

## Typical Workflow

```
1. bridge_start()                                        → start bridge
2. windows_list()                                        → find app HWND
3. window_tree(hwnd)                                     → enumerate controls
4. control_set_text(hwnd, "[CLASS:Edit; INSTANCE:1]", "user")
5. control_click(hwnd, "[CLASS:Button; INSTANCE:1]")     → submit
6. screenshot()                                          → verify result
7. bridge_stop()                                         → clean up
```

## AutoIt Send() Key Syntax

| Key | AutoIt string |
|-----|---------------|
| Enter | `{ENTER}` |
| Tab | `{TAB}` |
| Escape | `{ESC}` |
| F4 | `{F4}` |
| Alt+F4 | `!{F4}` |
| Ctrl+A | `^a` |
| Shift+Tab | `+{TAB}` |

## Troubleshooting

- **Bridge not starting:** Check `WINEPREFIX`; verify `AutoIt3.exe` at `C:\AutoIt3\`
- **Timeout on command:** Bridge crashed — check `status.txt`; call `bridge_start()` again
- **Empty windows list:** Target app not running — launch it first
- **Black screenshot:** No virtual desktop — wrap Wine launch with `explorer /desktop=name,1024x768`

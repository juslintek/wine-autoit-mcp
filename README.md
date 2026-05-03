# wine-autoit-mcp

An [MCP](https://modelcontextprotocol.io) server that lets AI agents control Windows applications running inside [Wine](https://www.winehq.org/) on macOS or Linux.

Uses [AutoIt3](https://www.autoitscript.com/) running inside Wine as a Win32 automation agent, bridged to the host via file-based IPC.

## Use Case

Automating legacy Windows desktop apps (VFP, Delphi, MFC, etc.) that run in Wine — for testing, scripting, or AI-driven interaction.

## Architecture

```
AI agent / MCP client
        ↕  MCP (stdio)
    server.py          ← Python, runs on host
        ↕  file IPC    ← ~/.wine-prefix/drive_c/AutoIt3/bridge/
    bridge.au3         ← AutoIt3.exe inside Wine
        ↕  Win32 API
  Windows app (Wine)
```

## Requirements

- macOS or Linux
- [Wine](https://www.winehq.org/) (tested with 11.0)
- [AutoIt3 v3.3.16+](https://www.autoitscript.com/site/autoit/downloads/) installed inside your Wine prefix
- [uv](https://docs.astral.sh/uv/) — Python package manager

## Setup

### 1. Install AutoIt3 in Wine

Download AutoIt3 and install it into your Wine prefix, or copy the files manually:

```bash
# AutoIt3 should be at C:\AutoIt3\AutoIt3.exe inside your Wine prefix
ls ~/.wine/drive_c/AutoIt3/AutoIt3.exe
```

### 2. Copy bridge script into Wine prefix

```bash
cp bridge.au3 ~/.wine/drive_c/AutoIt3/bridge.au3
```

### 3. Register the MCP server

Add to your MCP client config:

**Kiro** (`~/.kiro/settings/mcp.json`):
```json
{
  "mcpServers": {
    "wine-autoit-bridge": {
      "command": "uv",
      "args": ["run", "--script", "/path/to/server.py"],
      "env": {
        "WINEPREFIX": "/Users/you/.wine",
        "WINEDEBUG": "-all"
      }
    }
  }
}
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "wine-autoit-bridge": {
      "command": "uv",
      "args": ["run", "--script", "/path/to/server.py"],
      "env": {
        "WINEPREFIX": "/Users/you/.wine",
        "WINEDEBUG": "-all"
      }
    }
  }
}
```

### 4. (Kiro only) Install the skill and agent

Copy the skill so Kiro loads it automatically when working with Wine apps:

```bash
# Skill — loaded automatically based on context
mkdir -p ~/.kiro/skills/wine-autoit-mcp
cp SKILL.md ~/.kiro/skills/wine-autoit-mcp/SKILL.md

# Agent — available as a named agent in Kiro
mkdir -p ~/.kiro/agents
cp .kiro/agents/wine-autoit.md ~/.kiro/agents/wine-autoit.md
```

Then in Kiro you can invoke it directly:
```
agent: wine-autoit  automate the login flow for my app
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `bridge_start` | Start the AutoIt3 bridge inside Wine (idempotent) |
| `bridge_stop` | Stop the bridge |
| `bridge_status` | Check if bridge is running |
| `windows_list` | List all visible windows in Wine |
| `screenshot` | Capture full-screen PNG, returns file path |
| `window_tree` | List all controls in a window by HWND |
| `control_get_text` | Read text from a control |
| `control_set_text` | Type text into a control |
| `control_click` | Click a control or window |
| `send_key` | Send keystrokes (AutoIt `Send()` syntax) |
| `list_screenshots` | List all captured screenshots |

## Example: Login Flow

```
bridge_start()
windows_list()                                          → find app HWND
window_tree(hwnd)                                       → find Edit controls
control_set_text(hwnd, "[CLASS:Edit; INSTANCE:1]", "admin")
control_set_text(hwnd, "[CLASS:Edit; INSTANCE:2]", "password")
control_click(hwnd, "[CLASS:Button; INSTANCE:1]")
screenshot()                                            → verify result
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WINEPREFIX` | `~/.wine-gotas` | Wine prefix path |
| `WINE` | `/opt/homebrew/bin/wine` | Path to wine binary |
| `WINEDEBUG` | _(unset)_ | Set to `-all` to suppress Wine debug output |

## IPC Protocol

Commands are pipe-delimited strings written to `command.json`; results are JSON in `result.json`.

```
windows                          → {"windows":[{"title":"...","hwnd":12345}]}
screenshot                       → {"ok":true,"file":"C:\\...\\capture_HHmmss.png"}
tree|<hwnd>                      → {"title":"...","controls":[{"id":"...","text":"..."}]}
gettext|<hwnd>|<controlId>       → {"text":"..."}
settext|<hwnd>|<controlId>|<val> → {"ok":true}
click|<hwnd>[|<controlId>]       → {"ok":true}
key|<AutoItSendStr>              → {"ok":true}
quit                             → bridge exits
```

## Limitations

- **Full-screen screenshots only** — window-specific capture not yet implemented
- **Single-threaded IPC** — one command at a time
- **HWNDs are session-scoped** — call `windows_list()` fresh after wineserver restart

## License

MIT

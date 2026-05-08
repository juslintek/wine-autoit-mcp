# Known Issues — wine-mcp (winetools.exe)

## Critical: Input Delivery on macOS

### SendInput requires macOS foreground window

**Problem:** `SendInput` (keyboard) only delivers keystrokes when the Wine window is the frontmost macOS window. If any other app (Chrome, Terminal, Finder) is in front, keystrokes go nowhere.

**Root cause:** Wine's `winemac.drv` maps `SetForegroundWindow` to macOS window activation. But macOS doesn't allow apps to steal focus from other apps programmatically (security restriction since macOS 10.12).

**Workaround:** Manually click the Wine window before running input commands, or use `osascript -e 'tell application "wine" to activate'` (untested).

**Impact:** `type_text`, `send_key`, `send_tab`, `send_enter`, `clear_field`, `send_sequence`, `login` — all affected.

---

### Mouse click via SendInput moves physical cursor

**Problem:** `SendInput` with `MOUSEEVENTF_ABSOLUTE` and `SetCursorPos` both move the real macOS mouse pointer. There's no way to send a "virtual" mouse click that only affects the Wine window.

**Root cause:** `winemac.drv` maps Wine's mouse directly to the macOS pointer — no isolation layer.

**Impact:** `acc_click` moves your physical mouse. Cannot be used non-invasively.

---

### PostMessage WM_CHAR doesn't work with VFP controls

**Problem:** Posting `WM_CHAR` or `WM_KEYDOWN` directly to VFP child window HWNDs has no effect. VFP ignores messages not routed through its own message loop.

**Root cause:** VFP processes keyboard input at the form level via its own `ReadEvent` loop, not via standard Win32 message dispatch to child controls.

**Impact:** Cannot type into specific fields without keyboard focus. Must use Tab navigation.

---

## Critical: Screenshot Limitations

### GDI BitBlt produces black images

**Problem:** GDI `BitBlt` from screen DC returns all-black on macOS.

**Root cause:** `winemac.drv` renders via Metal/CoreGraphics. GDI DCs are empty — actual pixels live in Metal surfaces, not GDI memory.

**Solution:** Use macOS `screencapture -l <windowID>` via Swift CGWindowList.

---

### Virtual desktop doesn't work

**Problem:** `explorer /desktop=name,WxH` creates nothing visible. Screenshots from inside are black.

**Root cause:** Virtual desktop requires `winex11.drv` (X11). macOS Wine only ships `winemac.drv`.

---

## Moderate: MSAA Limitations

### put_accValue doesn't sync to VFP internal state

**Problem:** `IAccessible::put_accValue` sets the MSAA value but VFP's textbox `.Value` property remains unchanged.

**Root cause:** VFP implements `get_accValue` (reads from internal state) but `put_accValue` only updates the MSAA cache.

**Impact:** Cannot fill form fields via MSAA alone. Must use SendInput keyboard.

---

### accSelect(SELFLAG_TAKEFOCUS) doesn't trigger VFP focus

**Problem:** MSAA focus selection calls `SetFocus()` at Win32 level but VFP's internal focus tracking doesn't follow.

**Root cause:** VFP maintains its own focus chain. Only mouse click or Tab key triggers internal focus change.

---

### accLocation coordinates mismatch with SendInput on Retina

**Problem:** MSAA `accLocation` returns coordinates that click the wrong element when used with `SendInput MOUSEEVENTF_ABSOLUTE`.

**Root cause:** Suspected Retina scaling mismatch. Unresolved.

---

## Moderate: Wine Process Issues

### WinActivate crashes Wine

**Problem:** AutoIt's `WinActivate` on a cross-process window causes null pointer dereference (SIGKILL).

**Solution:** Replaced AutoIt with `winetools.exe` using `SetForegroundWindow` (doesn't crash).

---

### Wine ARM64 native build doesn't run

**Problem:** Wine compiled for ARM64 with `--enable-win32on64` gets killed by macOS.

**Root cause:** macOS restricts memory operations needed for i386 emulation on ARM64. Wine Stable works via Rosetta 2 (x86_64).

---

## Performance

### Subprocess calls take ~5s each

**Workaround:** Daemon mode (`--daemon`) — first call slow, subsequent instant. But daemon can't use SendInput.

**Recommendation:** Daemon for reads, subprocess for input.

---

## Resolved

| Issue | Solution |
|-------|----------|
| Login submission | `seq c s1 t s1` + `acc_do OK` |
| Button clicking | MSAA `accDoDefaultAction` |
| Reading field values | MSAA `acc_get` |
| Window enumeration | `EnumWindows` cross-process |
| Screenshot | macOS `screencapture -l` via Swift |

---

## Recommended Path Forward

**Use a Windows VM (QEMU) instead of Wine for reliable automation.** All Wine/macOS limitations disappear in a real Windows environment with RDP access.

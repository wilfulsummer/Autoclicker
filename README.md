# AutoClicker

A customizable autoclicker with a clean desktop GUI for Windows.

## Features

- Adjustable click interval in milliseconds
- Choose click type: single or double
- Choose mouse button: left, right, or middle
- Position mode:
  - `current`: click wherever the mouse currently is
  - `fixed`: click a fixed `X,Y` position
- Global hotkeys for Start, Stop, and Toggle
- Capture buttons to set hotkeys quickly
- Edge safety guard with per-side pixel controls (left/right/top/bottom)
- Optional app targeting (only click when selected app is active)
- Optional edge guard relative to selected app window bounds
- Gear-based settings UI:
  - `⚙ Clicker` for click behavior, keybinds, edge, and target-app controls
  - `⚙ App` for light/dark mode and background color

## Setup

1. Install Python 3.10+.
2. In this folder, install dependencies:

```powershell
pip install -r requirements.txt
```

## Run For Development

```powershell
python app.pyw
```

Or double-click:

- `launch_autoclicker.vbs`

This keeps the app in normal source-file form while you are developing it.

## Build A Standalone `.exe`

Install PyInstaller once:

```powershell
pip install pyinstaller
```

Then build the Windows release:

```powershell
.\build_exe.ps1
```

The packaged app will be created at:

```text
dist\AutoClicker.exe
```

Notes:

- The packaged `.exe` is for other people using the app.
- Your local development workflow can stay source-based with `python app.pyw`.
- The packaged build writes user settings to `%LOCALAPPDATA%\AutoClicker` so it does not need write access beside the `.exe`.

## Default Hotkeys

- Start: `<f6>`
- Stop: `<f7>`
- Toggle: `<f8>`

You can change these in `⚙ Clicker` and click **Apply**.
You can click **Capture** beside a hotkey field and press the key combo you want.
You can also click **Capture Current App** in `⚙ Clicker` to lock clicking to that app.

## Hotkey Format Examples

- `<f6>`
- `<ctrl>+<alt>+s`
- `<shift>+a`

## Notes

- Some systems may require running with elevated privileges for global hotkeys to work consistently in all apps.
- If edge safety is enabled, clicking pauses whenever the target click point is within any configured edge distance.
- If `Only click on selected app` is enabled, clicking pauses whenever that app is not the active window.
- Use responsibly and only where allowed.

## Hybrid Engine

This project now includes a scaffold for a native click engine:

- Python stays responsible for UI/settings
- a future C# engine will handle timing/click accuracy

Files added for this:

- [engine_bridge.py](C:\Users\Kevin\Documents\Cursor Projects\Autoclicker\engine_bridge.py)
- [HYBRID_ENGINE_PLAN.md](C:\Users\Kevin\Documents\Cursor Projects\Autoclicker\HYBRID_ENGINE_PLAN.md)
- [engine/AutoClicker.Engine/Program.cs](C:\Users\Kevin\Documents\Cursor Projects\Autoclicker\engine\AutoClicker.Engine\Program.cs)

Note:

- `.NET SDK` is not installed in this environment right now, so the engine scaffold is present but not built yet.

# Hybrid Engine Plan

## Goal

Keep the current Python app for:

- UI
- themes
- presets
- app settings
- info/test screens
- hotkey/config flow

Move the click/timing engine into a native Windows component for better sync and lower jitter.

## Recommended Split

### Python app

Owns:

- Tkinter UI in `app.py`
- reading/writing:
  - `app_settings.json`
  - `clicker_settings.json`
  - `theme_settings.json`
  - presets
- validation of user-entered settings
- launching/stopping the native engine
- showing engine state and sync stats

### Native engine

Recommended language: `C# / .NET`

Owns:

- precise scheduling
- Windows timer resolution
- process/thread priority
- click dispatch
- jittered timing / randomized offsets
- live timing stats

## Why C# For The Engine

- strong Windows API access
- easier than C++ for this project
- much better native timing/control than pure Python
- can be built as a small console or background executable
- easy to communicate with from Python over stdin/stdout

## First Version

Build a small executable:

- name idea: `AutoClicker.Engine.exe`
- mode: background console process
- communication: line-delimited JSON over stdin/stdout

Python launches it when needed and sends commands.

## Minimal Protocol

### Python -> Engine

```json
{"type":"configure","interval_ms":100,"button":"left","double_click":false,"jitter_enabled":false,"jitter_radius_px":3,"random_interval_offset_min_ms":0,"random_interval_offset_max_ms":0,"high_precision_timing":true,"process_priority_boost":true,"precision_mode":true}
```

```json
{"type":"start"}
```

```json
{"type":"stop"}
```

```json
{"type":"shutdown"}
```

### Engine -> Python

```json
{"type":"ready","engine_version":"0.1.0"}
```

```json
{"type":"state","running":true}
```

```json
{"type":"stats","samples":120,"avg_interval_ms":100.7,"min_interval_ms":98.9,"max_interval_ms":104.3,"avg_error_ms":1.4,"late_clicks":3}
```

```json
{"type":"error","message":"Failed to raise timer resolution"}
```

## First Engine Responsibilities

Version 1 should only replace timing and clicking.

Do not move these yet:

- themes
- settings UI
- presets UI
- info/safe test UI
- hotkey editing UI

This keeps the migration small.

## Runtime Flow

1. Python starts normally.
2. User presses `Start`.
3. Python validates settings as it already does.
4. Python launches engine if not running.
5. Python sends `configure`.
6. Python sends `start`.
7. Engine clicks and emits `stats` periodically.
8. Python updates the `Info` tab stats.
9. User presses `Stop`.
10. Python sends `stop`.
11. On app close, Python sends `shutdown`.

## Safe Rollout Plan

### Stage 1

Create the engine as a separate executable with:

- fixed interval clicking
- left/middle/right button support
- single/double click support
- `start`, `stop`, `shutdown`

Keep Python click loop as fallback.

### Stage 2

Add advanced sync features in the engine:

- high precision timer
- precision mode
- process priority boost
- randomized interval offset
- jitter clicking

### Stage 3

Add engine stats reporting:

- average interval
- min/max interval
- average error
- late click count

Wire those into the current `Info` tab.

### Stage 4

Optionally move global hotkey handling into the engine if needed.

Only do this if Python-side hotkeys become a real limitation.

## Python Integration Layer

Add a thin adapter in Python, not engine logic inside UI code.

Suggested file:

- `engine_bridge.py`

Responsibilities:

- start process
- send JSON commands
- read JSON messages
- queue stats/errors back to Tk safely
- restart engine if it crashes

Keep `app.py` talking to the bridge, not directly to process pipes.

## Fallback Strategy

Keep a setting/flag for:

- `engine_backend = "python"` or `"native"`

That gives you:

- easy testing
- easier debugging
- safe rollback if the native engine fails

## Suggested Folder Layout

```text
Autoclicker/
  app.py
  app.pyw
  engine_bridge.py
  engine/
    AutoClicker.Engine.sln
    AutoClicker.Engine/
      Program.cs
      EngineConfig.cs
      ClickLoop.cs
      JsonProtocol.cs
```

## First C# Classes

### `EngineConfig`

Holds:

- interval
- button
- click count
- jitter settings
- random offset settings
- sync settings

### `ClickLoop`

Owns:

- timer resolution setup
- priority setup
- precise scheduling loop
- click dispatch
- stats collection

### `JsonProtocol`

Owns:

- parsing commands from stdin
- writing responses to stdout

## Good First Milestone

The smallest worthwhile milestone is:

- Python UI unchanged
- `Start` launches native engine
- native engine performs fixed-interval clicks
- `Stop` stops engine
- Python still falls back to old loop if engine is unavailable

That gives you a real architecture upgrade without a full rewrite.

## Recommendation

Build the first engine as:

- `C# console app`
- `stdin/stdout JSON protocol`
- `fixed interval + start/stop`

Then add the advanced sync features one by one after the bridge is stable.

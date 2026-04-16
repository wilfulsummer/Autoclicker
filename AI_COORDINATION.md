# AI Coordination

## Ownership

- UI AI:
  - Main window layout
  - App Settings layout and theme styling
  - Visual polish, spacing, resizing behavior, widget placement

- Backend AI:
  - Click logic
  - Native engine bridge
  - C# engine timing/clicking behavior
  - Tests
  - Non-visual app functionality

## Current Backend Status

- Native engine bridge is active and launches hidden
- Native engine now receives correct camelCase config keys
- Native engine supports fractional interval timing for high CPS
- Sync Stats include:
  - Actual CPS
  - Target CPS
  - Average interval
  - Min / Max
  - Average error
  - Late clicks

## Current Caution

- App Settings UI/theme is being actively worked on by the UI AI
- Backend AI should avoid editing visual/layout/theme code unless explicitly requested

## Safe Division Of Work

- UI AI should prefer editing:
  - `app.py` UI-building sections
  - theme/layout/responsive behavior

- Backend AI should prefer editing:
  - `engine_bridge.py`
  - `engine/AutoClicker.Engine/*`
  - `test_app_logic.py`
  - non-visual logic in `app.py`

## Handoff Notes

- If UI AI changes widget names/structure in `app.py`, note it here before backend work resumes on UI-adjacent code
- If Backend AI changes settings fields or runtime behavior, note it here before UI wiring changes

## Latest Backend Notes

- Command/console window on native-engine start was fixed by hidden process launch flags
- CPS mismatch bug was fixed by:
  - correct bridge payload field names
  - fractional interval support in the native engine path
- Latest backend validation:
  - `python -m py_compile app.py app.pyw engine_bridge.py`
  - `python -m unittest test_app_logic.py`

## Latest UI Notes

- App Settings layout was refactored for visual cleanup and clearer grouping
- Main functional settings are unchanged:
  - theme mode / theme color fields
  - UI scale controls
  - sync options
  - presets
- App Settings structure changed in `app.py`:
  - appearance area now uses an "Appearance Studio" layout
  - color inputs are grouped into helper-built palette controls
  - sync random offset fields now live inside a dedicated `sync_offset_block`
- App Settings reopen behavior was tightened:
  - settings vars are resynced from the active saved theme before rebuilding the window
  - a follow-up style pass runs after open to reduce stale/light restyling on reopen
- Reopen theme bug fix:
  - stale destroyed settings-window buttons are pruned from the shared animated-button list
  - pending settings resize callbacks are canceled on close to avoid redraws against destroyed widgets
- App Settings sizing was loosened to reduce clipping in the preview and right-side cards
- Preview canvas mockup was updated to better match the current compact main-window layout
- Backend AI should avoid assuming the old App Settings widget container layout
- Existing setting vars and callbacks were preserved, so non-visual settings behavior should still wire up the same way

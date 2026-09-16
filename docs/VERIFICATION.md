# Verification — 2026-09-16

Environment: Omarchy 4.0.4-1, Hyprland 0.56.2, built-in Quickshell bar,
3440×1440 DP-2 ultrawide at scale 1. Original theme: Osaka Jade.

## Automated controller tests

`python3 -m unittest discover -s tests -v`: 18 passing tests.

Coverage includes 30/40/30 geometry, symmetric rounding, fractional scale,
negative monitor offsets, rotation, reserved panel space, CSS gap values,
focused-first activation, opening-event order, rapid bursts, slot reuse,
overflow skipping occupied/other-monitor workspaces, window exclusions,
fullscreen, deliberate workspace moves, monitor changes/disconnection,
failed cleanup, constrained clients, vanished windows, repeated toggles,
and journal recovery without affecting recycled window addresses.

## Actual desktop checks

`python3 tests/live_smoke.py --run`:

- Opened one through seven disposable Foot windows on isolated empty
  workspaces. Verified geometry, slot occupancy, and focused window/workspace
  at every step.
- Confirmed content rectangles on Osaka Jade:
  left `(11, 37, 1018, 1392)`, center `(1041, 37, 1358, 1392)`,
  right `(2411, 37, 1018, 1392)`.
- Verified left-slot refill after closing its window, fullscreen exit,
  release after a manual move to an unmanaged workspace, and repeated toggles.
- Captured `docs/preview.png` from the real three-window layout.

`python3 tests/live_lifecycle.py --run`:

- Disabled the plugin directly while a demo was managed; verified return to
  normal tiling. This test initially found that Quickshell could kill its
  child before cleanup. The independent lifetime-pipe recovery watcher fixes it.
- Forcibly killed the helper, verified the UI reports termination, and checked
  the recovery watcher and clean helper restart.
- Closed a helper's stdin and verified clean shutdown and restored tiling.
- Removed and reinstalled the plugin, comparing parsed shell configuration to
  confirm no unrelated changes and preservation of the centered clock anchor.
- Switched to Catppuccin Latte, checked center geometry, and captured the
  theme-aware widget. Restored Osaka Jade and the original background afterward.

Both opt-in scripts close only their own demonstration windows and restore the
original workspace/focus. Final installed state is tiling **off**.

## Keyboard compatibility — 0.1.1

`python3 tests/live_hotkeys.py --run` sends actual key combinations through a
disposable Linux uinput keyboard (using existing user access, without changing
permissions). It verifies:

- Super+Shift+Left/Right swaps column assignments and 30/40% widths, with no snap-back.
- Super+Arrow still changes focus; empty slots accept moves and edges do not wrap.
- Super+Shift+Number moves windows out of and back into managed workspaces.
- Super+Shift+Alt+Number preserves silent workspace movement.
- A real `hyprctl reload` reinstalls active movement handlers with no config errors.
- Deactivation and plugin unload restore native shortcut definitions and tiling.

The controller suite also covers stale window identities and unmanaged-window
isolation during keyboard moves. The normal Omarchy hotkey definitions are
restored after testing. Hyprland configuration files remain unchanged.

## Static checks and limits

- `omarchy plugin validate .` passes.
- `qmllint -I /usr/share/omarchy/shell Service.qml BarWidget.qml` passes.
- Hyprland reports no config errors; the plugin changes no Hyprland config.
- Fractional scaling, rotation, and monitor disconnection were tested with
  fixtures, not by changing the user's physical display setup.
- Multi-monitor hardware and compositor versions outside the stated baseline
  have not been tested on physical hardware.
- Marketplace submission has not been performed.

## GitHub publication checks

Repository: `https://github.com/TheBoxer71/OmniTiler`.
Before the initial commit and push, all 18 unit tests, manifest validation,
and QML checks passed again. The live desktop results above record the earlier functional
checks; documentation and artwork updates do not change runtime behavior.

Root-level `preview.png` is a generated promotional illustration, 1672×941
pixels, below the marketplace's 50 MB / 40 megapixel input limits. It is distinct
from the real screenshots in `docs/`. The exact generation prompt and source
requirements are recorded in [marketplace-image-prompt.md](marketplace-image-prompt.md).

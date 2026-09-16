# Prepared marketplace listing

**Name:** OmniTiler — Ultrawide Window Tiler for Omarchy

**Repository:** https://github.com/TheBoxer71/OmniTiler

**ID:** `theboxer71.omnitiler`

**Version:** 0.1.2
**Author:** Fredrick Thorsen

**License:** MIT

**Suggested category:** Productivity

**Tags:** hyprland, workspaces, bar

**Search keywords for description:** ultrawide window tiler, three-column tiling,
30/40/30 layout, Omarchy keyboard shortcuts, workspace automation

## Short description

Center-first ultrawide window tiling for Omarchy and Hyprland: fixed 30/40/30
columns, automatic workspace overflow, and a theme-aware bar toggle.

## Listing copy

Put your main app where your attention is: in the center. OmniTiler gives
ultrawide Omarchy desktops three predictable columns—40% in the middle and
30% on each side. Open windows fill center, left, then right. When all three
are occupied, the next window moves to a new empty workspace automatically.

Toggle it beside the clock, keep unused columns empty, and switch back to
normal Hyprland tiling with one click. The icon follows your active Omarchy
theme, with a tooltip showing workspace occupancy. No root access or manual
Hyprland configuration edits are required.

Use Omarchy's Super+Shift+Left/Right shortcuts to move or swap columns, and
the usual workspace shortcuts to move windows between workspaces.

## Release preparation

- Repository: [TheBoxer71/OmniTiler](https://github.com/TheBoxer71/OmniTiler).
- Marketplace submission remains a separate step; no listing has been submitted.
- Root manifest, README, MIT license, and screenshot are included.
- Marketplace preview: root-level `preview.png` (1672×941 PNG promotional
  illustration generated with built-in imagegen; see `marketplace-image-prompt.md`).
- Desktop screenshot: `docs/preview.png` (real demonstration windows).
- Additional preview: `docs/preview-light.png` (40% center, sides vacant).
- Repository name: `OmniTiler`.
- Use the current [publishing guide](https://plugins.omarchy.org/publish.html)
  and [submission requirements](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)
  when ready. Category and the three tags above match the allowed values checked
  on 2026-09-16.
- Supported baseline: Omarchy 4.0.4 / Hyprland 0.56.2, Python standard library.
- Capabilities: local compositor IPC, window placement/workspace control,
  session-local recovery files, and a local Python child process. No network
  requests, privileged operations, downloaded executables, or telemetry.

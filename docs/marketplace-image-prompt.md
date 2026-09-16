# Marketplace showcase artwork

- Asset: repository-root `preview.png`.
- Tool: built-in imagegen.
- Actual dimensions: 1672×941 pixels (approximately 16:9).
- Requested dimensions: 2048×1152; the generator returned its native size above.
- This is a promotional illustration; real desktop screenshots remain in
  `docs/preview.png` and `docs/preview-light.png`.
- The [marketplace submission requirements](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)
  accept root-level preview images and automatically optimize them for cards and
  detail pages. No exact pixel dimensions are required. This asset is below the
  50 MB and 40 megapixel limits. Requirements checked on 2026-09-16.

## Generation prompt

```text
Use case: ads-marketing.
Create one finished premium marketplace showcase image for a real Omarchy Linux plugin called OmniTiler.
Output dimensions: exactly 2048 x 1152 pixels, landscape 16:9 PNG. Single image, no variants.
This is a polished promotional illustration of the plugin's function, not a photograph or an exact screenshot.
Art direction: sophisticated Osaka Jade-inspired desktop aesthetic: near-black charcoal/forest green background, soft jade-teal accents, warm ivory typography, subtle fine grain, understated ambient glow. Crisp flat front-facing interface illustration, editorial typography, precise geometry, generous negative space. No perspective distortion, no stock laptop, no people, no unrelated branding.
Composition: all essential content inside a generous 10% safe margin. Upper portion: small custom icon of three vertical outlined panes (wider middle pane), followed by a large beautifully typeset wordmark "OmniTiler". Below it one clean subtitle "Ultrawide window tiling for Omarchy". The wordmark must be the dominant headline and remain readable in a small marketplace card.
Main central visual: one elegant ultra-wide desktop frame, roughly 2.8 times wider than tall, with a very slim status bar. Small centered three-pane icon in this top bar. Within the desktop, exactly three tall application window panes at the SAME HEIGHT and aligned along their top and bottom edges. Precise visible widths LEFT 30%, CENTER 40%, RIGHT 30%, with equal narrow gutters. The center pane is wider and emphasized with a refined jade border and subtle glow; side panes are dimmer. Each pane contains quiet generic content lines suggesting app windows, without illegible fabricated text. In the middle of each pane place a large clear percentage: left "30%", center "40%", right "30%". Just below each percentage place respectively "CONTEXT", "FOCUS", "TOOLS", all uppercase small text. No literal white screenshot outlines.
Below the desktop illustration, understated three-part feature line with equal spacing: "Center first" · "Auto workspace overflow" · "Super + Shift + ← / →". Small rounded keyboard-key styling only for the last item, with arrows correct.
Exact permitted visible text:
"OmniTiler"
"Ultrawide window tiling for Omarchy"
"30%"  "40%"  "30%"
"CONTEXT"  "FOCUS"  "TOOLS"
"Center first"
"Auto workspace overflow"
"Super + Shift + ← / →"
Keep all typography exceptionally clean, perfectly spelled, high contrast, readable at thumbnail sizes. No extra copy, badges, approval seals, watermark, GitHub logos, or claims of official endorsement. Showcase the functional 30/40/30 column layout clearly, with the center at the geometric center of the desktop.
```

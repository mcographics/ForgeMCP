# UE 5.6 alpha.9 — compact reference-matched layout

The first Unreal React tab used a wider content column, roomier cards, oversized
corner treatment and generic glyphs. The revised layout follows the proportions
of the supplied reference more closely: a 970px maximum content column, tighter
card spacing, 13px card corners, aligned labels and controls, and purpose-drawn
blue/orange section icons. The transfer behavior, fields, confirmation buttons,
official application marks and safety wording remain present.

The production page was rendered at the reference image's 1086×1448 viewport in
Chromium and visually reviewed. Preview: [compact Unreal panel](../Saved/forge-ui-compact-review.png).
The exact interface inside the running desktop Unreal WebBrowser still requires
closing and reopening the ForgeMCP tab.

Validation: React/Vite build passed; the local single-file UI verifier passed;
the UE 5.6.1 clean-project package test loaded the plugin and confirmed live
plugin health and MCP Unreal project identity. Native Unreal binaries did not
change in this visual-only update.

- Engine-installed UI SHA-256:
  `64116ca7d26460ccdb8ea8d93f4c488d28ef16ca5e1ccd57b5d250c8b2929079`.
- Reissued alpha archive SHA-256:
  `d953539b7dac9c505962af85e7594b95d8edc1a65049f557e4bc479dbc85da3c`.

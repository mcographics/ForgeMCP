---
name: lookdev
description: Look development workflow for Blender assets combining materials, lighting, and camera, with visual review when an actual image is available through the current toolchain.
license: MIT
metadata:
  author: https://github.com/arjun988
  version: "1.0.0"
  domain: blender
  role: specialist
  triggers: lookdev, look development, shading review, material lighting loop, turntable, asset presentation
  related-skills: materials, lighting, rendering, camera-cinematography, compositing, qa-review
---

# Lookdev

Material + light + camera loop. Compare actual images when available; do not claim a
visual pass based only on scene data or render-job status.

## When to Use

- Finalizing asset shading before export/portfolio
- Turntable / grey shader checks
- Matching material references
- Bridging `materials` and `lighting` intentionally

## Workflow

```
Clay/grey pass → Base materials → Neutral light rig
  → Beauty light → Review actual image when available → Gap list → Iterate (≤3–5)
  → Optional grade → QA
```

## Standard Rigs

| Rig | Use |
|-----|-----|
| Neutral 3-point | Evaluate materials fairly |
| HDRI studio | Product / character |
| In-situ scene lights | Final context |

Keep a reusable `COL_Lookdev_Lights` + `CAM_Lookdev_*`.

## Checklist

- [ ] Values read in grayscale
- [ ] Specular roughness believable
- [ ] Edges catch light (bevels/normals)
- [ ] Emissive under control
- [ ] No pure black / pure white traps unless stylized
- [ ] Matches reference palette if provided

## Iteration Rule

Each pass: change one major variable (material OR light OR camera), then review an
actual image if available. If no image can be reviewed, keep visual acceptance pending.

## Constraints

### MUST DO
- Grey pass before fancy textures when forms unsure
- Review actual screenshots or render images when available; do not infer visual quality from inspection data
- Hand off to `qa-review` before ship

### MUST NOT DO
- Fix modeling problems only with roughness maps
- Infinite tweak loops without gap list

## Reference Guide

| Topic | Reference | Load When |
|-------|-----------|----------|
| Lookdev Rig | `references/lookdev-rig.md` | When needed |
| Lookdev Checklist | `references/lookdev-checklist.md` | When needed |

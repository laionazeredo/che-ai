---
version: 1
name: "acme"
created_at: "2026-09-14T20:52:56Z"
spec: stitch-design-md
colors:
  primary: "{{primary_color}}"
  secondary: "{{secondary_color}}"
  surface: "{{surface_color}}"
  on_surface: "{{on_surface_color}}"
typography:
  font_family_sans: "{{font_family_sans}}"
  font_family_serif: "{{font_family_serif}}"
  scale: "{{type_scale}}"
rounded:
  sm: "{{radius_sm}}"
  md: "{{radius_md}}"
  lg: "{{radius_lg}}"
  full: "{{radius_full}}"
spacing:
  base: 4
  scale: [4, 8, 12, 16, 24, 32, 48, 64, 96, 128]
components:
  button:
    radius: "{{button_radius}}"
    height: "{{button_height}}"
  card:
    radius: "{{card_radius}}"
    padding: "{{card_padding}}"
---

# DESIGN.md — acme

> Single handoff contract (Stitch spec). One file per sub-product tree; referenced by every downstream agent.

## Overview

Sub-product slug: `acme`. Bootstrap timestamp: `2026-09-14T20:52:56Z`. This DESIGN.md is generated from `design/tokens/tokens.json` (single source of truth — see R4 in SPEC `che-design-domain-v1`). Edit `tokens.json` and re-run `che designer tokens render` to keep this file in sync.

## Colors

| Token | Value | Usage |
|---|---|---|
| `primary` | `{{primary_color}}` | brand accents, primary CTA |
| `secondary` | `{{secondary_color}}` | secondary actions |
| `surface` | `{{surface_color}}` | page background |
| `on_surface` | `{{on_surface_color}}` | body text on surface |

Contrast targets (WCAG 2.2 AA): 4.5:1 body · 3:1 large text. Validated by `skills/accessibility-expert` skill.

## Typography

| Token | Value |
|---|---|
| font_family_sans | `{{font_family_sans}}` |
| font_family_serif | `{{font_family_serif}}` |
| scale | `{{type_scale}}` (modular — see `domains/ux/profile.md`) |

Body 16px / line-height 1.5. Headings follow the modular scale.

## Layout

Mobile-first breakpoint scale (canonical — `domains/ux/profile.md`):

| Breakpoint | Min width |
|---|---|
| sm | 640px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |
| 2xl | 1536px |

Base grid: 4pt (`spacing.base`). Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.

## Elevation & Depth

| Token | Shadow | Use |
|---|---|---|
| e0 | none | flat surfaces |
| e1 | `0 1px 2px rgba(0,0,0,.06)` | cards |
| e2 | `0 4px 12px rgba(0,0,0,.08)` | dialogs, popovers |
| e3 | `0 12px 32px rgba(0,0,0,.12)` | modals |

## Shapes

| Token | Value |
|---|---|
| radius_sm | `{{radius_sm}}` |
| radius_md | `{{radius_md}}` |
| radius_lg | `{{radius_lg}}` |
| radius_full | `{{radius_full}}` (pills, avatars) |

## Components

### Button

- radius: `{{button_radius}}`
- height: `{{button_height}}`
- states: default · hover · pressed · focus · disabled (7 states per `domains/ux/playbook.md` §2.1)

### Card

- radius: `{{card_radius}}`
- padding: `{{card_padding}}`
- elevation: e1

## Do's and Don'ts

**Do**

- Edit `design/tokens/tokens.json` only — never hand-edit the YAML frontmatter.
- Re-run `che designer tokens render <wt>` after any token change.
- Commit `design/DESIGN.md`, `design/tokens/*.json`, `design/tokens/*.css`, and `*.op` / `*.svg` together for one sub-product change.

**Don't**

- Don't introduce a second source of design tokens (no inline `#hex` in deliverables).
- Don't paste Figma exports here without provenance in `design/assets/CREDITS.md`.
- Don't commit rendered bitmap previews — keep the source `.op` and let CI render on demand.
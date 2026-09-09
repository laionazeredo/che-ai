---
template_id: "ux-component-spec"
domain: "ux"
version: "0.1.0"
consumed_by_playbook_stage: "Stage 2 — Hi-fi Prototype (after tokens applied, before quality gates)"
cross_ref_design_tokens_table: "domains/ux/profile.md §Conventions tokens 4/8 scale"
cross_ref_states_table: "domains/ux/playbook.md Stage 2.3 7 states table"
---

# Template — Component Specification (Enters Design System)

> **Fill 100% of mandatory fields (🔴). Fill optional fields (🟡) only if applicable.** No "approximately" fields. All tokens or exact values. No "try". No "see in Figma".

---

## Metadata (🔴 100% mandatory)
| Field | Value filled here |
|---|---|
| **Canonical Component Name (EN slug · PascalCase)** | 🔴 `<ComponentName>` |
| **Design System Category** | 🔴 `Primitives` / `Components` / `Patterns` / `Templates` |
| **Owner Responsible (team/designer/dev)** | 🔴 `<name>` |
| **Associated Ticket / SPEC ID** | 🔴 `<LINEAR-ID>` / `<SPEC-slug.md>` |
| **Dependencies on other components** | 🟡 `<ComponentA>, <ComponentB>` |
| **Figma / PenPot dev-mode node link** | 🔴 `https://...?node-id=<ID>` |
| **Mobile-first? (always YES)** | 🔴 ✅ Yes / ❌ No (if No → justify below) |
| **If not mobile-first, ADR justification:** | 🟡 `Only on internal admin desktop screens. Minimum breakpoint MD ≥768` |

---

## 1. Design Tokens used by this component (🔴 ALL mandatory)

> **Golden rule:** EVERY value in THIS section references the TOKEN and its VALUE, NOT just a standalone value. Example: ✅ `spacing.md (16px)`. ❌ Just `16px`. If you need a value that does not exist in the tokens → FIRST create the token, THEN reference it here. No exceptions.

### 1.1 Spacing (internal padding · external margin)
| Token | Value | Applied at which position? |
|---|---|---|
| 🔴 spacing.`<xs|sm|md|lg|xl|...>` | `X px` | padding-top / padding-right / padding-bottom / padding-left |
| 🔴 spacing.`<md|lg|...>` | `X px` | margin-top / margin-right / margin-bottom / margin-left (outer elements) |

### 1.2 Radius
| Token | Value | Applied to (container / button / input?) |
|---|---|---|
| 🔴 radius.`<xs|sm|md|lg|xl|full>` | `X px` | container corners / button / avatar ... |

### 1.3 Colors (Foreground text · Background surface · Border stroke)
| Token (e.g.: neutral-900 / primary-500 / danger) | Hex/RGB Value | Applied to? |
|---|---|---|
| 🔴 color.`<on-primary / on-surface / ...>` | `#...` | Text heading / Text body / Text caption |
| 🔴 color.`<surface / background / primary-500>` | `#...` | Container bg / Button bg / Card bg |
| 🔴 color.`<neutral-200 / neutral-300>` | `#...` | Container border stroke / Divider |
| 🟡 color.`<success / warning / danger / info>` | `#...` | Status badge / Alert type |

### 1.4 Typography (text styles per role)
| Textual role within the component | Font Token size · weight · line-height | Exact Value |
|---|---|---|
| 🔴 Heading (if has H3/H4/H5/H6) | typography.`<3xl / 2xl / xl>` · bold/semibold · 1.2 / 1.1 | `31px / 700 / 1.2` |
| 🔴 Body (paragraph) | typography.`<base / lg>` · regular/medium · 1.5 | `16px / 400 / 1.5` |
| 🔴 Caption / Helper / Badge | typography.`<xs / sm>` · medium/semibold · 1.4 | `12px / 500 / 1.4` |
| 🟡 Overline / Eyebrow | typography.`<xs>` · semibold · 1.4 · uppercase · tracking-wide | `12px / 600 / 1.4` |

### 1.5 Elevation / Shadow (🔴 mandatory if component floats, e.g.: Card/Dropdown/Modal)
| Shadow Token | Value | Applied to which state? |
|---|---|---|
| 🔴 elevation.`<sm / md / lg / xl>` | `0 4px 8px rgba(0,0,0,0.08)` | default / hover / active |

### 1.6 Motion (🟡 mandatory if interaction · animation exists)
| Interaction (hover / focus / open modal) | Duration token | Easing token (standard / enter / exit) | Value |
|---|---|---|---|
| 🟡 Button hover elevation change | duration.`<150ms / 300ms>` | easing.standard | `300ms cubic-bezier(0.2,0,0,1)` |

---

## 2. The 7 Mandatory States (🔴 NONE can be missing. See profile states table)
> For each state, fill: described appearance + exact values that change (e.g.: hover: elevation sm → md, +0.98 scale). NO state "does not apply". Every interactive component ALWAYS has all 7.

| State | 🔴 Values that change vs Default | ✅ Described appearance + screenshot path |
|---|---|---|
| **Default** | — (baseline for all tokens above) | `<default screenshot>` |
| **Hover** `:hover` + pointer cursor | elevation sm→md, optional scale 0.98 | `<hover screenshot>` |
| **Focus-visible** `:focus-visible` | ring 2px primary-500 + ring-offset-2 surface | `<focus screenshot>` |
| **Active** `:active` / mousedown | scale 0.97 · elevation downgrade sm · 0.96 opaque | `<active screenshot>` |
| **Disabled** `disabled` / `aria-disabled` | opacity 0.4 · cursor not-allowed · remove hover interaction | `<disabled screenshot>` |
| **Loading** `aria-busy="true"` role="status" | content replaced by spinner · same width/height · SR text "Loading…" | `<loading screenshot>` |
| **Error / Invalid** `aria-invalid="true"` | 2px danger border + icon + red helper text (ICON + TEXT + COLOR = never just color) | `<error screenshot>` |

---

## 3. 4 Complete Breakpoints (🔴 mandatory mobile-first)
> Can a layout have only one appearance? NO. Every component reacts to SM/MD/LG/XL. Fill in: does padding change? Do columns break? Does font size decrease?

| Breakpoint · width | Viewport width | 🔴 Changes in this component? (paddings / fonts / grid columns) | Screenshot |
|---|---|---|---|
| **SM** | ≥ 640px | 🔴 `<description>` | `<sm>` |
| **MD** | ≥ 768px | 🔴 `<description>` | `<md>` |
| **LG** | ≥ 1024px | 🔴 `<description>` | `<lg>` |
| **XL ≥** | ≥ 1280px | 🔴 `<description>` | `<xl>` |

---

## 4. Final Accessibility Checklist (🔴 100% mandatory to fill · a11y gate summary)
- [ ] 🔴 **44×44px minimum mobile touch area** on all interactive targets (buttons / links / inputs / chips / tabs).
- [ ] 🔴 **Full keyboard nav**: Tab / Shift+Tab / Enter / Space / Arrow keys / Esc → each action documented in this table.
- [ ] 🔴 **Focus follows visual DOM order**: no skipping sections. Positive tabindex PROHIBITED.
- [ ] 🔴 **All text contrast**: Body ≥ 4.5:1 · Large Heading ≥ 3.0:1. Verified.
- [ ] 🔴 **Focus ring NEVER removed without adequate replacement** (`outline: 0` banned).
- [ ] 🔴 **Roles / ARIA**: Button has `<button>`. Link has `<a>`. Modal role="dialog" aria-modal="true". Alert role="alert". Never `<div onClick>`.
- [ ] 🔴 **Images**: Decorative `alt=""` · Informative `alt="..."` ≤125 characters. SVG icon aria-hidden + title if needed.
- [ ] 🔴 **Reduced motion**: Animations DISABLED if `prefers-reduced-motion: reduce`.
- [ ] 🔴 **Never use color alone to indicate state**: Always icon + text + color (error state above).
- [ ] 🟡 **Practical screen reader test**: VoiceOver (macOS/iOS) or NVDA (Windows) run and correct reading heard. (Bonus delivery, not mandatory.)

---

## 5. Sign-off (Human Approved Gate)
| Role | Name | Date | EXPLICIT Approval ("Component Spec Approved" literal) |
|---|---|---|---|
| Responsible DesignOps / UI Designer | `<name>` | `<YYYY-MM-DD>` | ✅ / ❌ Comments: `<...>` |
| Frontend Dev implementing | `<name>` | `<YYYY-MM-DD>` | ✅ / ❌ Comments: `<...>` (clear measurements? tokens exist? etc.) |

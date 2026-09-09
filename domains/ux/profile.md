---
domain: "ux"
name: "UI/UX DesignOps (Figma · PenPot)"
owner: "Che Domain Layer — UX Pilot"
created: "2026-09-01"
status: "Active · Pilot"
version: "0.1.0"
notes: "First non-engineering domain pilot. Model proven here, rollout of remaining 5 domains in phase 2 (1/month)."
---

# Domain Profile — UI/UX DesignOps (`ux`)

## 🎯 Persona (Senior DesignOps)

**Canonical Name:** Flockr DesignOps.
**Position:** Senior UI/UX + DesignOps responsible for consistent quality between designers, agencies, and dev.
**Mandatory Stack:** Atomic Design System (tokens as 1st source of truth) · Figma as primary hi-fi tool · PenPot as open-source alternative for external communities/vendors · WCAG 2.2 AA basic level HARD STOP (non-negotiable) · Mandatory 8pt-grid spatial design tokens.
**Mindset:** "Pixel perfect is the starting line, not the finish line. No component goes to production without structured handoff, exact measures, and validated a11y."
**Dev Partnership:** Handoff delivery = structured Markdown file (see `templates/dev-handoff-template.md`), NOT just a Figma/PenPot link. Measures in absolute px per breakpoint, not "roughly".

---

## 📐 Conventions & House Style (HARD rules, no "trying")

### 0. Design System Tokens — always reference, never magic values

**NO EXCEPTION: every visual value comes from a token. No hardcoded hex / px without a corresponding token.**

| Token Category | Canonical Values (4/8 base scale) |
|---|---|
| **Spacing (4pt-grid step, 8pt major scale)** | `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 / 128` px. NEVER use 6, 14, 20, 28, 36. |
| **Border Radius** | `xs=2px`, `sm=4px`, `md=8px`, `lg=16px`, `xl=24px`, `full=9999px`. NEVER 3/5/6/10/12px outside this scale. |
| **Color Palette** | 12 canonical tokens per brand: `primary.{50,100,200,…,900}`, `secondary.{50…900}`, `neutral.{0,50,…,950}`, `success`, `warning`, `danger`, `info`, `on-primary`, `on-secondary`, `surface`, `background`. If brand needs more → sub-tokenize, never break base structure. |
| **Typography (1.25 modular scale)** | `xs=12`, `sm=14`, `base=16`, `lg=18`, `xl=20`, `2xl=25`, `3xl=31`, `4xl=39`, `5xl=49`, `6xl=61` px. Line-height: display 1.1, heading 1.2, body 1.5, caption 1.4. Weight: `regular 400`, `medium 500`, `semibold 600`, `bold 700`. |
| **Elevation / Shadows** | 4 levels: `sm` (1dp), `md` (4dp), `lg` (8dp), `xl` (16dp). NEVER hard-edged shadows, always blur = spread × 2 and neutral 900 color alpha 0.08~0.16. |
| **Motion Duration & Easing** | Duration: `75ms` / `150ms` / `300ms` / `500ms`. Easing: `standard=cubic-bezier(0.2,0,0,1)`, `enter=cubic-bezier(0,0,0,1)`, `exit=cubic-bezier(0.4,0,1,1)`. NEVER generic `ease-in-out`, NEVER >500ms for common interaction (except 1x hero onboarding). |
| **Breakpoints (mobile-first)** | `sm ≥ 640px`, `md ≥ 768px`, `lg ≥ 1024px`, `xl ≥ 1280px`, `2xl ≥ 1536px`. NEVER custom breakpoint outside these — if needed, justify in ADR. |

### 1. Composition and Layout

- Textual content container max-width: **72ch** (not wider). Comfortable reading.
- Hero screen ratio: 16/9 or 4/3. NEVER 1/1 square full-screen.
- Grid alignment: always align to 12-column container (16px xl/2xl gutter, 8px sm/md gutter). Deviations = justify.
- Whitespace: minimum **24px** breathing room between sections on mobile, **48px** on desktop. "Breathe before you speak" — design too.

### 2. Accessibility (WCAG 2.2 AA — HARD STOP)

| WCAG 2.2 AA Item | Mandatory Threshold | Fail = Hard Stop |
|---|---|---|
| **Normal text contrast ≥ 18pt bold / ≥ 24pt** | **≥ 3.0:1** | ❌ |
| **Small body text contrast** | **≥ 4.5:1** | ❌ |
| **UI components / interactive icons contrast** | **≥ 3.0:1** | ❌ |
| **Mobile touch target area** | **≥ 44×44px minimum** (buttons, links, inputs, tabs, chips) | ❌ |
| **Spacing between adjacent touch targets** | **≥ 8px minimum** between each | ❌ |
| **Full keyboard navigation** | Tab/Shift+Tab / Enter / Space / Arrow keys / Esc works WITHOUT failing JavaScript | ❌ |
| **Logical DOM focus order** | Focus follows visual reading order, no random jumps | ❌ |
| **Visible focus ring WITHOUT outline: 0 / :focus-visible:none** | NEVER remove focus ring without adequate replacement | ❌ |
| **Heading hierarchy (H1-H6)** | Exactly 1 H1 per page. Never skip levels (H1 → H3 directly). | ❌ |
| **ARIA labels only when no visible text** | Never `aria-label` duplicating visible text. Never `role=presentation` on interactive content. | ❌ |
| **Decorative img** | `alt=""` empty string, NEVER omit alt. | ❌ |
| **Informational img** | `alt="functional description"` max 125 characters. | ❌ |
| **Reduced Motion (prefers-reduced-motion)** | All animations/transitions OFF if user checks. Do not force parallax hero. | ❌ |
| **Color-only indicators** | Never communicate info ONLY by color (e.g. "red field = error"). Always icon + text + color. | ❌ |
| **200% zoom without horizontal overflow** | 360px width viewport, 200% zoom, no horizontal scroll appears. | ❌ |

**Golden Rule:** If in doubt whether it passes → **FAIL by default** and adjust until it passes.

---

## ✋ Forbidden Patterns (fail = domain gate FAIL, ignores pixel-check score)

1. ❌ **Stadium / pill shapes prohibited in Mermaid SDLC.** (Core contract — non-negotiable.)
2. ❌ **Empty placeholder images ("visual Lorem ipsum") in any hi-fi delivery for stakeholder.** Always use official `coresg-normal.trae.ai` text_to_image API with product context prompt. Generic images = lazy design.
3. ❌ **Handoff by Figma/PenPot link only WITHOUT filled `dev-handoff-template.md`.** Dev shouldn't need to open Figma for exact measures.
4. ❌ **"Approximately 10px", "About 80% width" measures.** All measures = absolute px per breakpoint. No relatives in handoff (unless % calculated and explicit).
5. ❌ **Component duplication without design token.** If 2 screens have same card with 2px padding difference → it's a bug, not "designer variation."
6. ❌ **Hardcoded inline styles in exported SVGs.** Always use `fill="currentColor"` for interface icons. No inline hex.
7. ❌ **Literal "ugly" screenshot for human validation without first running `/figma-pixel-check`.** Automatic first, human second.
8. ❌ **Empty skeleton loading state with bars only.** Always accompanied by `aria-busy="true"` + `role="status"` + SR text "Loading…".
9. ❌ **Component created without full states table.** See `templates/component-spec-template.md`: default/hover/focus/active/disabled/loading/error = ALWAYS the 7 states. Do not accept "we only do default, rest later."
10. ❌ **Design created mobile-last / desktop-first.** Mandatory mobile-first: hi-fi prototype starts SM (640), then MD (768), then LG (1024), then XL (1280). NEVER reduce from desktop → mobile.

---

## 🔗 Cross-references to official skills / tools / gates

- **Existing official Figma design skill in Flockr ecosystem:** `/che-figma` — build Figma screen/component in code accurately on first pass: gathers exact dev-mode values up front, checks for component reuse, implements, then self-verifies.
- **Official pixel verification skill:** `/figma-pixel-check` — verify implemented component against Figma using exact dev-mode values (padding, radius, icon/font size). Base for our `pixel-check-gate` (below).
- **Official A11y Gate:** `domains/ux/gates/accessibility-gate.md` (official axe-core CLI `@axe-core/cli`, WCAG 2.2 AA).
- **Official Pixel Gate:** `domains/ux/gates/pixel-check-gate.md` (inspired by `/figma-pixel-check`).
- **Figma Connector:** `domains/ux/connectors/figma.config.md` (official `mcp_open-pencil` MCP + official `figma-cli` npm).
- **PenPot Connector:** `domains/ux/connectors/penpot.config.md` (official open-source PenPot MCP https://penpot.app/).
- **Reuse core §13 Language 4-axis:** LANG_CODE=en (token names, filenames, variant slugs), LANG_DOCS=project-preferred (UI labels, UX copy), LANG_CHAT=project-preferred (designer-user conversation), LANG_REPORT=en (a11y audit reports for CI).
- **Reuse §19 Logging Standard:** Any Figma Variables → dev JSON ETL script uses `[STEP 1/N]` numbered echo, anti-flood loops >100 batch.

---

## 🧩 Templates path (relative)

- Component specification (new component enters design system): `domains/ux/templates/component-spec-template.md`
- Structured developer handoff (delivery to dev): `domains/ux/templates/dev-handoff-template.md`

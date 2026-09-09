---
template_id: "ux-dev-handoff"
domain: "ux"
version: "0.1.0"
consumed_by_playbook_stage: "Stage 4 — Dev Handoff (FINAL DELIVERY · DO NOT skip)"
cross_ref_component_spec_template: "domains/ux/templates/component-spec-template.md"
cross_ref_accessibility_gate: "domains/ux/gates/accessibility-gate.md"
cross_ref_pixel_gate: "domains/ux/gates/pixel-check-gate.md"
---

# Template — Structured Developer Handoff (NOT just a Figma link)

> **Fundamental rule:** Devs should NEVER need to open Figma/PenPot to find EXACT MEASUREMENTS. Everything is in this file. If any measurement is missing → INCOMPLETE handoff → return to stage 2. No "look at page 3 frame B".

---

## 0. Header Metadata (🔴 100% mandatory)
| Field | Value |
|---|---|
| 🔴 **Canonical Handoff ID slug** | `ux-handoff-<YYYYMMDD>-<feature-slug>` |
| 🔴 **Approved SPEC ID** (link to `spec_<slug>.md` in workspace) | `../../specs/spec_<slug>.md` |
| 🔴 **Linear / ClickUp / Jira Ticket** | `<LINEAR-ID>` / `<CLICKUP-ID>` |
| 🔴 **Feature / 1-line Description** | `<1 line, what this delivery provides>` |
| 🔴 **Designer Owner** | `<designer name>` |
| 🔴 **Assigned Dev Owner** | `<frontend dev name>` |
| 🔴 **Figma Page Link (MANDATORY, but for reference only, not as the sole source of measurements)** | `https://www.figma.com/design/<FILE_ID>/...?node-id=<ROOT_PAGE_ID>` |
| 🟡 **PenPot Page Link (if alternative)** | `https://design.penpot.app/#/workspace/...` |
| 🔴 **Handoff Delivery Date** | `<YYYY-MM-DD>` |
| 🔴 **Dev Implementation Deadline (estimate)** | `<business days>` |

---

## 1. List of Components + Screens in this delivery (🔴 100%)
> For EACH new or modified component/screen, reference 1 filled `component-spec-template.md` file (see sibling template). No component without a spec.

| # | Screen / Component Name (PascalCase slug) | Direct Figma node_id | Filled Component Spec link | Supported Breakpoints |
|---|---|---|---|---|
| 1 | 🔴 `<PageHeroSection>` | `?node-id=<ID>&m=dev` | `./components/component-spec-PageHeroSection.md` | ✅ SM · MD · LG · XL |
| 2 | 🔴 `<PrimaryButtonCTA>` | `?node-id=<ID>&m=dev` | `./components/component-spec-PrimaryButtonCTA.md` | ✅ SM · MD · LG · XL |
| N | ... | ... | ... | ... |

---

## 2. Absolute Measurements per Breakpoint (🔴 NOT "approximately". ALL 4 breakpoints filled)
> 12-column layout container (mobile-first). For each breakpoint, measure the container MAX-WIDTH and gutters.

### 2.1 Global Layout Container
| Breakpoint | Viewport Min-width | Container MAX-WIDTH | Left/Right Gutter | Grid Column Count | Inter-column Gutter |
|---|---|---|---|---|---|
| 🔴 SM | ≥ 640px | `<X px>` | `<16 / 24 px>` | 4 | `8 px` |
| 🔴 MD | ≥ 768px | `<X px>` | `<24 / 32 px>` | 8 | `12 px` |
| 🔴 LG | ≥ 1024px | `<X px>` | `<32 / 48 px>` | 12 | `16 px` |
| 🔴 XL | ≥ 1280px | `<X px>` | `<48 / 64 px>` | 12 | `16 px` |
| 🔴 2XL | ≥ 1536px | `<X px>` | `<64 / 96 px>` | 12 | `16 px` |

### 2.2 Screen / Component Specific Measurements (example — repeat for each screen)
**Screen Name:** `<Homepage Hero Section>`
| Breakpoint | Hero Height | Internal Padding Top | Padding Bottom | Heading size (H1) | Body copy size | CTA width / height | CTA gap |
|---|---|---|---|---|---|---|---|
| SM | `<px>` | `<px>` | `<px>` | `<31px / 700 / 1.1>` | `<16px / 400>` | `<full / 44px>` | `<12px>` |
| MD | `<px>` | `<px>` | `<px>` | `<39px / 700 / 1.1>` | `<16px / 400>` | `<260px / 48px>` | `<16px>` |
| LG | `<px>` | `<px>` | `<px>` | `<49px / 700 / 1.1>` | `<18px / 400>` | `<320px / 52px>` | `<20px>` |
| XL | `<px>` | `<px>` | `<px>` | `<61px / 700 / 1.1>` | `<18px / 400>` | `<360px / 56px>` | `<24px>` |

---

## 3. Exported Assets (🔴 mandatory relative path)
> SVG: always `fill="currentColor"` for icons (Profile Forbidden Pattern #6). PNG: ALWAYS export 2x (@2x) for retina + 4x for 4K if hero image. No JPEG images unless it's real photography.

| Asset Name | Type | Relative path in this delivery | Px Size (W × H) | Density | Color Token Used / Note |
|---|---|---|---|---|---|
| 🔴 `<icon-user.svg>` | Interface SVG Icon | `./assets/icons/icon-user.svg` | `24×24` | Vector | ✅ `fill="currentColor"` |
| 🔴 `<icon-arrow-right.svg>` | SVG Icon | `./assets/icons/...` | `20×20` | Vector | ✅ currentColor |
| 🔴 `<hero-background-mobile.png>` | PNG Image | `./assets/hero/...sm.png` | `640×960` | @2x | Optimized AVIF / WebP + fallback PNG |
| 🔴 `<hero-background-desktop.png>` | PNG Image | `./assets/hero/...xl.png` | `1280×720` | @2x | ... |
| 🟡 `<illustration-empty-state.svg>` | SVG Illustration | `./assets/illustrations/...` | `400×300` | Vector | Neutral/Primary tokens maintained |

---

## 4. Supported Browsers (🔴 mandatory table)
> NEVER write "latest 2 versions" without numbering. Always specific. Last 2 + iOS Safari 15.7+ minimum.

| Browser Platform | Minimum Supported Version | Nav / Touch? | Tested Screenshot? |
|---|---|---|---|
| 🔴 Chrome (desktop) | Last 2 (130+) | Mouse + Keyboard | ✅ / ❌ |
| 🔴 Firefox (desktop) | Last 2 (131+) | Mouse + Keyboard | ✅ / ❌ |
| 🔴 Safari (macOS · WebKit) | Latest 2 (17.4+) | Mouse + Keyboard | ✅ / ❌ |
| 🔴 Chrome (Android) | Latest 2 | Touch + Android back | ✅ / ❌ |
| 🔴 Safari (iOS · iPhone) | iOS 15.7+ (absolute minimum for security) | Touch + Safari tab bar | ✅ / ❌ |
| 🟡 Edge (Windows) | Latest 2 | Mouse + Keyboard | ✅ / ❌ (PC tester) |

---

## 5. Motion / Animation tokens (🟡 mandatory if interaction exists)
| Interaction | Element | Duration token | Easing token | Exact Value | Reduced motion accessibility? |
|---|---|---|---|---|---|
| 🟡 CTA button hover | PrimaryButtonCTA | duration.150ms | easing.standard | `150ms cubic-bezier(0.2,0,0,1)` | ✅ disabled if prefers-reduced-motion |
| 🟡 Open modal overlay | `<ModalCheckout>` | duration.300ms | easing.enter + exit | `300ms enter · 150ms exit` | ✅ disabled |

---

## 6. Executed Quality Gates Results (🔴 mandatory to attach reports · playbook section 3)
> Results of Gate G-UX-1 (A11y) and G-UX-2 (Pixel). NOT just PASS/FAIL. Include score + JSON path.

| Gate | PASS / FAIL Result? | Score / Threshold | Relative JSON Report Path | HTML Report Path (if available for stakeholders) |
|---|---|---|---|---|
| 🔴 **A11y axe-core WCAG 2.2 AA** | PASS / FAIL | CRITICAL_count = N · serious_count = M · Score 0-10 = x.y | `./reports/accessibility-report.json` | `./reports/accessibility-report.html` |
| 🔴 **Pixel Perfect (Figma ref vs code)** | PASS / FAIL | Score = x.y (≥8.0?). Within 4px % = 0.xx. Max deviation = N px | `./reports/pixel-check-report.json` | `./reports/pixel-visual-diff.png` |
| 🟡 **Lighthouse Performance (optional UX gate, bonus)** | PASS / FAIL | LCP / TTI / CLS = x,y,z · Performance score ≥ 90? | `./reports/lighthouse-report.json` | `./reports/lighthouse-report.html` |

---

## 7. Final Accessibility Checklist Summary (🔴 15 items · copied from profile, 100% must be ✅ to pass A11y Gate)
- [ ] 🔴 1 Unique H1 per page. Heading levels DO NOT skip (H1 → H3 prohibited).
- [ ] 🔴 Body text contrast ≥ 4.5:1 · Large headings ≥ 3.0:1. Verified.
- [ ] 🔴 Mobile touch targets ≥ 44×44px. Spacing between ≥ 8px.
- [ ] 🔴 Keyboard nav: Tab / Shift+Tab / Enter / Space / Arrow / Esc. Works 100%.
- [ ] 🔴 DOM focus order = visual order. No positive tabindex > 0.
- [ ] 🔴 Focus ring `:focus-visible` NEVER removed without replacement.
- [ ] 🔴 Decorative img alt="". Informative functional alt ≤125char. Never omitted alt.
- [ ] 🔴 Real `<button>`, not `<div onClick>`. Real `<a href>` for internal/external links.
- [ ] 🔴 ARIA only if no visible text. Never duplicates visible text.
- [ ] 🔴 Never indicate state ONLY by color. Always icon + text + color.
- [ ] 🔴 Associated `<label>` or aria-labelledby for input. Never placeholder as label only.
- [ ] 🔴 Modal role="dialog" aria-modal="true". Esc key closes. Focus trap.
- [ ] 🔴 Loading spinner aria-busy role="status". SR Text "Loading…".
- [ ] 🔴 `prefers-reduced-motion: reduce` = animations/transitions DISABLED.
- [ ] 🔴 200% zoom on 360px viewport = NO horizontal overflow.

---

## 8. Human Approval Signature (double check · Design + Dev · mandatory)
| Party | Name | Role | Date | EXPLICIT "Handoff Complete and Understood" approval |
|---|---|---|---|---|
| Design Delivery | 🔴 `<Designer Owner>` | UI/UX DesignOps | `<YYYY-MM-DD>` | ✅ / ❌ Comments: `<...>` |
| Dev Received | 🔴 `<Dev Owner>` | Frontend Engineer | `<YYYY-MM-DD>` | ✅ / ❌ Comments: `<Measurements X missing, token Y does not exist...>` |
| QA (if involved) | 🟡 `<QA Owner>` | QA Engineer | `<YYYY-MM-DD>` | ✅ / ❌ Comments |

---
gate_id: "ux-pixel-check-gate"
domain: "ux"
version: "0.2.0"
executable: false
blocked_by: "The comparison engine does not exist yet. §3 states the real mechanism; until it is implemented there is no tool to run, so this gate must be SKIPPED (never passed) by che-ship §0.9.5."
inspired_by_reference_skill: "Flockr official /figma-pixel-check skill (see domains/ux/profile.md cross-references) — NOTE: that skill is a NUMERIC token diff, not an image diff. Adopt its method: compare design properties against rendered properties, never screenshot against screenshot."
threshold_pass: "score_0_to_10 ≥ 8.0  AND  pct_elements_within_4px_tolerance ≥ 95%"
threshold_single_critical_fail: "Any single critical element (CTA button, hero heading) with deviation > 8px → FAIL, regardless of overall score."
tool_official: "Design side: mcp_Figma_AI_Bridge.get_figma_data (Figma) or mcp_open-pencil.get_jsx/node_bounds/analyze_spacing/analyze_typography/analyze_colors (OpenPencil). Implementation side: mcp_Chrome_DevTools_MCP.evaluate_script (getBoundingClientRect + getComputedStyle)."
tool_evidence_only: "Image diff (export_image + playwright_screenshot + pixelmatch) — attaches a human-readable artefact to the PR. NEVER the PASS/FAIL signal: whole-frame pixel deltas are dominated by text antialiasing/DPR/font-loading noise while being near-blind to a 2px radius error, which inverts the signal-to-noise ratio for exactly the deviations this gate exists to catch."
retry_policy: "1 free automatic retry (fixes top 3 deviations / padding / radius / font-size). 2nd failure → HUMAN REQUIRED hard stop ship."
log_format_decisions: "[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status={PASS|FAIL} score={x.y} within_4px_pct={0.xx} deviation_max_px={n} duration_ms={ms} traceId=..."
---

# Executable Gate — UX · Pixel Perfect (based on `/figma-pixel-check`)

> **Philosophy: Absolute measures per element (padding, radius, font size, EXACT hex color, X/Y position) are NUMERICAL — not a matter of taste. We don't evaluate "beauty" — we evaluate the absolute deviation of N pixels between the Figma/PenPot reference and the code implementation. 100% mathematical. 0% subjective.**

---

## Executability status — READ THIS BEFORE ATTEMPTING

**This gate has no working tool path yet.** `executable: false`.

Do NOT attempt to run it, and do NOT report a PASS: a skipped gate reported as passed is worse than no gate at all. `che-ship §0.9.5` must skip it and log `DOMAIN-GATE-SKIPPED-NOT-IMPLEMENTED`.

What is missing is the **engine**, not the thresholds. §1's tolerances, §2's scoring and §4's retry policy are complete and correct — they are the specification. §3 describes the mechanism that must be built to execute them.

---

## 0. Prerequisites (what a working engine will need)

- Valid design reference: a Figma `node_id` or an OpenPencil `.op` node id. NOT "any image".
- Code implementation running locally (Next.js build or dev server).
- Design-side MCP: `mcp_Figma_AI_Bridge` (`figma`) or `mcp_open-pencil` (`openpencil`).
- Implementation-side MCP: `mcp_Chrome_DevTools_MCP`.
- A `design-map.json` plus matching `data-design-node` attributes in the JSX (§3.3).
- Evidence only, never the verdict: `pixelmatch` + `pngjs`, installed with the project's own package manager.

---

## 1. Comparison Methodology (13 elements per analyzed frame)

For each unique node/frame = a page / screen / component, we measure these absolute values and compare reference vs implementation:

| # | Measurement Category | How we measure | Allowed tolerance (pass) |
|---|---|---|---|
| 1 | **Width / Height box model** | `node.width`, `node.height` (Figma) vs `getBoundingClientRect()` (implementation) | ≤ 4px on each axis |
| 2 | **Internal Padding-top / right / bottom / left** | 4 individual values | ≤ 4px each (all 4 must pass) |
| 3 | **External Margin to near siblings** | Space between previous and next element | ≤ 4px |
| 4 | **Border-radius (all 4 corners top-left…bottom-right individually)** | Exact profile token value: xs=2/sm=4/md=8/lg=16/xl=24/full=9999 | ≤ 2px (radius is highly sensitive; 3px deviation is visually perceptible) |
| 5 | **Border-width / Border-color hex** | `getComputedStyle` vs Figma stroke | Width ≤1px · Color delta E ≤ 5 CIE76 |
| 6 | **Typography font-size (px point-by-point)** | Computed vs Figma font size | ≤ 2px (visually very sensitive) |
| 7 | **Typography font-weight (400/500/600/700)** | Exact. No tolerance. | EXACT match (no "almost 600"). |
| 8 | **Typography line-height (leading)** | Exact value (1.5, 1.2, 1.4 profile) | ≤ 0.05 leading |
| 9 | **Typography letter-spacing** | 0.01em default, exact tokens | ≤ 0.01em |
| 10 | **Foreground color hex / RGB (text)** | Delta E 1976 CIE76 | ≤ 5 (human eye doesn't see difference) |
| 11 | **Background color hex / RGB (surface)** | Delta E 1976 CIE76 | ≤ 5 |
| 12 | **Box-shadow parameters (x/y/blur/spread/color alpha)** | 5 values per individual shadow | x,y ≤ 2px · blur,spread ≤ 4px · alpha ≤ 0.04 |
| 13 | **Absolute X / Y position in SM/MD/LG/XL viewport** (12-column grid alignment) | Figma x,y vs screenshot | ≤ 8px per breakpoint |

---

## 2. Final Score 0–10 (weighted average by importance)

Each element above has a different WEIGHT for the score (more important = higher penalty if wrong):

| Weight | Categories |
|---|---|
| **×2 (Double weight · Critical Element)** | #2 Internal padding, #6 Font-size, #7 Font-weight, #10 Foreground color |
| **×1.5 (Medium weight)** | #3 Margin, #4 Radius, #13 X/Y Position |
| **×1 (Standard weight)** | All other remaining categories |

### Calculation
```
raw_score_per_element = max(0, 1.0 - (measured_deviation / allowed_tolerance))
weighted_score = Σ (raw_score_per_element × WEIGHT) / Σ WEIGHTS
final_score_0_10 = round(weighted_score × 10, 1)
```

### PASS Condition (all 3 must be TRUE simultaneously)
1. `final_score_0_10 ≥ 8.0`
2. `(total_passed_measurements / total_measurements) ≥ 0.95` (95% of individual values within tolerance)
3. **No element with ×2 WEIGHT (critical) has deviation > 8px** (CTA button with 8px wrong padding = FAIL, even if overall score is 9.0)

---

## 3. Mechanism (specification — NOT yet implemented)

> ⚠️ Everything below describes **what must be built**. No step here is runnable today.
>
> **Superseded (do not use):** earlier versions of this file declared the primary tool as
> `mcp_open-pencil.diff_jsx(file_id, node_id, actual_dom_screenshot)`. That signature does not exist.
> The real `diff_jsx(from, to, document_id?, page_id?)` is a *structural* diff between two nodes of the
> same document — it reports added/removed children and changed props, never measurements, and it
> cannot see the DOM at all. The `figma-cli` fallback was equally fictional: Figma ships no official
> CLI, and the official integration is the MCP bridge.

The gate compares **numbers, not pictures**. §1's 13 categories are properties; both sides must be
reduced to the same property schema before any comparison happens.

### 3.1 Reference side → `design-facts.json`

| Backend | Tools | Output |
|---|---|---|
| `figma` | `mcp_Figma_AI_Bridge.get_figma_data(fileKey, nodeId)` for properties; `download_figma_images` for assets | one record per element |
| `openpencil` | `mcp_open-pencil.get_jsx(node)` + `node_bounds` + `analyze_spacing` / `analyze_typography` / `analyze_colors`; `export_svg` / `export_image` for assets | one record per element |

Per `DESIGN_BACKEND_CONTRACT.md`, the backend is resolved fail-closed and never converted between
engines. Schema (one entry per element per breakpoint):

```jsonc
{ "element": "cta-button",
  "design_node": "12:345",
  "selector": "[data-design-node='12:345']",
  "breakpoints": {
    "lg": { "w": 320, "h": 52,
            "padding": [12, 24, 12, 24],
            "radius": [8, 8, 8, 8],
            "border": { "width": 1, "color": "#E4E4E7" },
            "font": { "size": 18, "weight": 600, "lineHeight": 1.2, "tracking": "0" },
            "fg": "#18181B", "bg": "#FFFFFF",
            "shadow": [{ "x": 0, "y": 2, "blur": 8, "spread": 0, "alpha": 0.08 }],
            "box": { "x": 480, "y": 220 } } } }
```

Text and git-diffable on purpose: it is the artefact a PR reviewer can actually check.

### 3.2 Implementation side → `dom-facts.json`

Measure the live DOM — **never photograph it**. `mcp_Chrome_DevTools_MCP`:
`navigate_page` → `resize_page`(breakpoint) → `evaluate_script` returning `getBoundingClientRect()`
plus `getComputedStyle()` per selector, emitted in the §3.1 schema.

Determinism rules — without these the gate measures noise and the score is meaningless:

- fixed viewport per breakpoint, `deviceScaleFactor: 1`, one run each
- `await document.fonts.ready` **before** reading (otherwise you measure fallback-font metrics)
- animations / transitions / caret disabled; `prefers-reduced-motion` emulated
- element scrolled into view, then wait for two consecutive identical rects
- browser version and font files pinned — a font substitution invalidates every typography row
- non-deterministic subtrees excluded via the map (avatars, timestamps, maps, ads, user content)

### 3.3 Element map → `design-map.json`

Design node → DOM element cannot be inferred reliably, so it is declared once, approved by a human,
and frozen as regression. Add `data-design-node="12:345"` in the JSX so the map is self-documenting
in the code.

```jsonc
{ "cta-button": { "design_node": "12:345", "selector": "[data-design-node='12:345']" } }
```

### 3.4 Comparator → pure function, no LLM

`compare(design_facts, dom_facts, design_map) -> deviations[] + score`, applying §1's tolerances and
§2's weights and PASS conditions verbatim, then writing `pixel-check-report.json`. It must be code:
§2 permits no judgement call, and a model deciding whether 3px is "close enough" to 4px is exactly the
subjectivity this gate forbids.

### 3.5 Image diff (evidence only — never the verdict)

`export_image` (design) + `playwright_screenshot` (implementation) composited into
`pixel-visual-diff.png` for the reviewer's eye. Useful, and never the PASS/FAIL signal — see
`tool_evidence_only` in the frontmatter for why.


---

## 4. Retry Policy (same as A11y gate)
| Failure # | Action |
|---|---|
| **1st failure** | **FREE AUTOMATIC Retry**: Take the 3 measurements with HIGHEST deviation (top 3) and apply the obvious fix (padding: 12→16, radius: 4→8, color: #...). Re-run the gate ONE more time. |
| **2nd failure** (after automatic retry) | **HARD STOP ship §0.9.5 DOMAIN GATES.** Do not open PR. Message: "GATE G-UX-2 PIXEL FAIL after retry. Current score = {s} ≥8.0? N. Top 3 deviations: [...]. Manual fix or EXPLICIT_OVERRIDE VERBATIM user logged in decisions.log." |
| **EXPLICIT_OVERRIDE (ONLY user VERBATIM)** | `[EXPLICIT_OVERRIDE] domain=ux gate=pixel-check-gate old=8.0 new={x.y} reason="..."` |

---

## 5. What this gate DOES NOT do (delimited purpose, KISS)
- ❌ Does not evaluate "visual beauty" / personal taste → only numerical deviation.
- ❌ Does not validate animations / motion → motion stays in `domains/ux/gates/motion-gate.md` (future phase 2, not created today).
- ❌ Does not validate textual content copy → separate copywriting domain copy gate (future phase 2).
- ❌ Does not replace A11y validation → run A11y Gate BEFORE this one. Correct layout with inaccessible content = Fail.

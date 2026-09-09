---
gate_id: "ux-pixel-check-gate"
domain: "ux"
version: "0.1.0"
inspired_by_reference_skill: "Flockr official /figma-pixel-check skill (see domains/ux/profile.md cross-references)"
threshold_pass: "score_0_to_10 ≥ 8.0  AND  pct_elements_within_4px_tolerance ≥ 95%"
threshold_single_critical_fail: "Any single critical element (CTA button, hero heading) with deviation > 8px → FAIL, regardless of overall score."
tool_primary: "Official MCP mcp_open-pencil.diff_jsx (dev mode) + export_image + node_bounds"
tool_fallback: "Official npm CLI figma-cli export + pixelmatch npm library"
retry_policy: "1 free automatic retry (fixes top 3 deviations / padding / radius / font-size). 2nd failure → HUMAN REQUIRED hard stop ship."
log_format_decisions: "[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status={PASS|FAIL} score={x.y} within_4px_pct={0.xx} deviation_max_px={n} duration_ms={ms} traceId=..."
---

# Executable Gate — UX · Pixel Perfect (based on `/figma-pixel-check`)

> **Philosophy: Absolute measures per element (padding, radius, font size, EXACT hex color, X/Y position) are NUMERICAL — not a matter of taste. We don't evaluate "beauty" — we evaluate the absolute deviation of N pixels between the Figma/PenPot reference and the code implementation. 100% mathematical. 0% subjective.**

---

## 0. Prerequisites
- Valid design reference: Figma/PenPot file with specific node_id or frame. NOT "any image".
- Code implementation running locally (Next.js build or dev server).
- Authenticated MCP `mcp_open-pencil` connection OR logged-in `figma-cli` CLI.
- npm library fallback (if MCP unavailable):
  ```bash
  corepack pnpm add -D pixelmatch pngjs @playwright/browser-chromium
  ```

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

## 3. Practical Execution (step-by-step)

### 3.1 Recommended Method (fast, native MCP, same as `/figma-pixel-check` script)
```
1. Open implemented page in browser (Playwright / local dev server).
2. Identify exact Figma/PenPot reference node_id (same screen, same breakpoint).
3. run_mcp → mcp_open-pencil.diff_jsx(
     file_id: FIGMA_FILE_ID,
     node_id: REFERENCE_NODE_ID,
     actual_dom_screenshot: <current page screenshot>
   )
4. Result: diff lists each value (Figma X value vs Actual Y value, deviation N px, weight).
5. Calculate score using formula above. Structured JSON output + visual report.
```

### 3.2 Fallback (MCP unavailable, figma CLI + pixelmatch)
```bash
# [STEP 1/4] Export Figma REFERENCE screenshot
corepack pnpm figma export FILE_ID --node NODE_ID --format png --scale 2 --output /tmp/figma-ref.png
# [STEP 2/4] Screenshot code implementation in same viewport
npx playwright screenshot --viewport-size="1280,832" http://localhost:3000/<slug> /tmp/actual.png
# [STEP 3/4] pixelmatch quantifies pixel diff
corepack pnpm -e "import pixelmatch from 'pixelmatch'; ...match diff, return deviation JSON."
# [STEP 4/4] Parse → score. Same formula, same threshold.
```

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

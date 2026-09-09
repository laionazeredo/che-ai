---
gate_id: "ux-accessibility-gate"
domain: "ux"
version: "0.1.0"
threshold_hard_stop: "CRITICAL_count > 0 → HARD FAIL"
tool_official: "@axe-core/cli (npm package by Deque Systems, official WCAG maintainer)"
tool_package_manager: "npm"
retry_policy: "1 free automatic retry applying axe-core recommendations. 2nd failure = HUMAN REQUIRED hard stop ship."
log_format_decisions: "[DOMAIN-GATE-EXECUTED] domain=ux gate=accessibility-gate status={PASS|FAIL} critical_count={n} serious_count={m} duration_ms={ms} traceId=..."
wcag_level: "WCAG 2.2 AA (minimum level HARD STOP. AAA not mandatory, AAA points marked as optional bonus.)"
---

# Executable Gate — UX · Accessibility (axe-core CLI · WCAG 2.2 AA)

> **Same fail-fast engine as G1-G4 ship §0.9:** NUMERICAL threshold, 1 automatic retry, 2nd failure = HUMAN REQUIRED, EXPLICIT_OVERRIDE only via user VERBATIM logged in decisions.log. No subjective evaluation "we think it's accessible".

---

## 0. Prerequisites (install once per workspace)

```bash
# [STEP 0/2] Install official Deque @axe-core/cli (§20 = DO NOT use raw puppeteer, DO NOT use isolated Lighthouse without axe-core)
corepack pnpm add -D @axe-core/cli playwright
# [STEP 1/2] Install Playwright browsers for the CLI (if not global)
corepack pnpm exec playwright install chromium
```

---

## 1. MANDATORY Thresholds (fail = any violated)

### 1.1 axe-core Severity Levels (same as MDN / W3C standards)
| axe-core Severity | What it means | PASS condition |
|---|---|---|
| **CRITICAL** | Serious WCAG AA violation: blocks screen readers, prevents keyboard navigation, total inaccessibility. | `COUNT === 0` (ZERO). Any number ≥ 1 → **HARD FAIL after 1 retry.** |
| **SERIOUS** | Important WCAG AA violation: poor contrast, broken heading hierarchy, missing alt. | `COUNT ≤ 3`. Greater than 3 → WARNING, does not FAIL by default (but penalises final score). If ≥ 10 → FAIL. |
| **MODERATE / MINOR** | Best practices, improvements. | Do not influence PASS/FAIL, reported for log only. |

### 1.2 10 MANDATORY Automatic Checks
(All are part of the standard `wcag22aa` axe-core ruleset. None disabled.)
1. **color-contrast** — text/background contrast (profile table body ≥ 4.5:1 · large heading ≥ 3.0:1).
2. **document-title** — non-empty, unique, descriptive `<title>` per page.
3. **html-has-lang** — `<html lang="en">` or project-configured lang (§13 Language 4-axis).
4. **image-alt** — `<img>` tags have alt or alt="" (decorative). Never missing alt.
5. **button-name** — `<button>` has accessible name (visible text or aria-label / aria-labelledby).
6. **link-name** — `<a>` has accessible name (no "Click here" / "Read more" without context).
7. **aria-allowed-attr** — ARIA attributes used in allowed roles (no `aria-label` on generic `<div>` without role).
8. **label** — `<input>` has associated `<label>`, `aria-label` or is inside fieldset with legend. Never placeholder as label only.
9. **bypass** — "Skip to content" link before header (visually hidden, visible on focus). Unique H1 per page.
10. **focus-order-semantics** — focus order = visual reading order. No tab skipping sections. No `tabindex="> 0"` (positive tabindex = WCAG anti-pattern).

---

## 2. Execution (standard one-liner, same as CI)

```bash
# [STEP 1/3] Build app (Next.js) — required for static pages
corepack pnpm nx run @flockr/platform:build

# [STEP 2/3] Run @axe-core/cli pointing to page (URL or built HTML)
#     EXPLICIT ruleset = wcag22aa (never mixed with default "best practices")
#     Output: Structured JSON + visual HTML for humans
corepack pnpm axe --chromedriver-path $(corepack pnpm exec which playwright-chromium) \
  --rules wcag22aa \
  --tags wcag2a,wcag2aa,wcag22a,wcag22aa \
  --format json \
  --output-dir $CHE_SESSION_DIR/reports/ \
  --save accessibility-report.json \
  http://localhost:3000/<page-slug>

# Optional: generate pretty HTML report for stakeholders
corepack pnpm axe ...(same flags)... --format html --save accessibility-report.html

# [STEP 3/3] Parse JSON → log decisions.log entry and compare threshold
# (done automatically by che-ship §0.9.5 DOMAIN GATES)
#
# parse pseudo-code:
# critical_count = len([r for r in report.violations if r.impact === 'critical'])
# serious_count  = len([r for r in report.violations if r.impact === 'serious'])
# PASS = critical_count === 0 AND serious_count <= 3 AND (all 10 checks above with NONE violation)
```

---

## 3. Retry Policy (same as core G2 code-review)

| Failure Number | Action |
|---|---|
| **1st failure** (any reason) | **FREE AUTOMATIC Retry**: Execute `axe-core` recommendations for each CRITICAL violation (1-click axe-core fix when possible). E.g.: add missing alt, fix missing label, add `:focus-visible` outline. Re-run gate ONE more time. |
| **2nd failure** (CRITICAL_count ≥ 1 after automatic retry) | **HARD STOP ship**: DO NOT open any PR. Request human (designer / dev / accessibility expert). Standard error message: "GATE G-UX-1 A11Y FAIL after retry. Remaining CRITICAL issues = N. Manual fix or EXPLICIT_OVERRIDE VERBATIM user logged in decisions.log." |
| **EXPLICIT_OVERRIDE** (ONLY if user VERBATIM says "ignore a11y here" EXPLICITLY) | Mandatory log `[EXPLICIT_OVERRIDE] domain=ux gate=accessibility-gate old=CRITICAL_count=0 new=permit N reason="..."` → threshold changes, but audit trail remains forever. Agent NEVER decides alone. |

---

## 4. Additional Score (0–10) — does not influence PASS/FAIL, goes to final report
- `+2 pts` if passing optional AAA (not mandatory)
- `+1 pts` if MODERATE_count === 0
- `+1 pts` if run and reported on 4 breakpoints SM/MD/LG/XL (not just desktop)
- `score_final = base PASS 7.0 + extras`

---

## 5. Compatibility with §13 Language 4-axis
- Error messages for humans (LANG_CHAT): en
- Ruleset names / axe-core JSON output: always EN (LANG_CODE)
- HTML reports for stakeholders: LANG_DOCS (en)
- Structured logs decisions.log: always EN (LANG_REPORT)

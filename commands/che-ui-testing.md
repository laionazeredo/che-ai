---
description: "Helper skill ui-testing-contracts: delivers RTL Priority Order (Kent Dodds) snippets + Playwright byTestId Flockr boilerplate + 3-part data-testid convention regex lint (G8.3) + Category 8 UI Hygiene cross-reference (code-review gate ONDA1 + SbE Selector Contract ONDA2)."
arguments:
  - name: scope
    description: "Context: 'RTL' for Testing Library order, 'Playwright' for Flockr boilerplate, 'Convention' for G8.3 regex lint, 'Cat8' for Category 8 enforcement, 'Full' for all sections (default)."
    required: false
---

IMMEDIATELY invoke **`ui-testing-contracts`** Skill.

Expected output per section:
1. §1 — RTL Priority Order + ByTestId guard clause snippet (if scope=RTL or Full)
2. §2 — Playwright byTestId wrapper snippet verbatim Flockr 3-part convention (if scope=Playwright or Full)
3. §3 — Canonical regex + grep one-liner lint for G8.3 violation count (if scope=Convention or Full)
4. §4 — Category 8 Table: G8.1 HIGH / G8.2 HIGH / G8.3 MEDIUM / G8.4 LOW + SbE UI Selector Contract integration (if scope=Cat8 or Full)

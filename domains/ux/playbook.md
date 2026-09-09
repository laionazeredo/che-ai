---
domain: "ux"
version: "0.1.0"
status: "Active · Pilot"
gate_files_required:
  - "domains/ux/gates/pixel-check-gate.md"
  - "domains/ux/gates/accessibility-gate.md"
templates_required:
  - "domains/ux/templates/component-spec-template.md"
  - "domains/ux/templates/dev-handoff-template.md"
connectors_optional:
  - "domains/ux/connectors/figma.config.md"
  - "domains/ux/connectors/penpot.config.md"
cross_skills:
  - "/che-figma (build + implement)"
  - "/figma-pixel-check (pixel-perfect validation)"
  - "/che-ship §0.9.5 DOMAIN GATES (ship gate execution)"
---

# Playbook — UI/UX DesignOps (`ux`) · 5 Mandatory Stages (NO SKIPPING)

> **Quality Assurance:** This playbook has no optional stages. Skipping a stage = prior failure at Quality Gate (stage 3). All stages produce persistent workspace artifacts. 100% reuse of core §19 Logging Standard: Figma → JSON token export scripts use `[STEP N/M]` numbered anti-flood echo.

---

## Phase 0 — Preconditions & Brief / Discovery (JTBD, NOT visual design yet)

### Goal
Understand the PROBLEM before opening Figma/PenPot. "Design is problem solving. Without a defined problem, every wireframe is beautiful and useless."

### Mandatory inputs to start
- ✅ Approved Ticket / SPEC with: `user_story`, `persona_primary`, `success_metric` (1 number, not prose).
- ✅ Raw research (if any): user-interview notes, heatmaps, GA4/Hotjar analytics (DO NOT invent data).

### Stages 0.0 → 0.4 (no skipping)
**0.0 F0 Tracer Ping (UX — CANONICAL #0 VERTICAL SLICING, runs BEFORE 0.1):**
   > "Design is not beauty without structure. A beautiful UI that never ships to a real data endpoint is a throwaway prototype, not a Tracer." — Pragmatic Programmer canon.
   1. Create the SMALLEST POSSIBLE vertical structure (F0 UX tracer) that proves end-to-end flow. It MUST contain, at minimum, 3 artifacts together (≥2 "layers" of UX-to-implementation pipeline): (a) 1 mobile wireframe box (SM breakpoint, Phase 1 style — no colors yet), (b) 1 minmal functional component stub or dev-handoff placeholder entry, (c) 1 data flow node showing WHERE data comes FROM (e.g. "tRPC endpoint /private-events.enquire → returns JSON → renders in component"). All 3 refer to the SAME single minimum interaction (e.g. "Click Save button → POST → 201 → appears in list").
   2. F0 UX DONE criterion (literal observable string): "On SM breakpoint 390px, user can click Save button on wireframe placeholder, dev stub file <path> exists with props matching button, and Figma/PenPot component links to matching data flow node. Zero tokens, zero visual polish."
   3. Stamp rule: Set `F0_UX_STAMP = PENDING`. Before 0.1 JTBD is allowed to run, 3 artifacts above must exist AND be reviewed in a 1-sentence snapshot. Stamp transitions to COMPLETE only after the 3 items are linked in `docs/ux/<slug>-00-tracer-ping.md`.
   4. Anti-patterns blocked at 0.0: ❌ 0.0 = only visual design sketch (no dev-stub / no data-flow node) = FAIL stamp = loop back before 0.1. ❌ No SPEC §4.5 mapping to F0 row = fail unless EXPLICIT_OVERRIDE_HORIZONTAL_PLAN logged.
   5. Persistent artifact output: `docs/ux/<slug>-00-tracer-ping.md` with 3 links + F0_UX_STAMP = PENDING | COMPLETE header. Corresponding log entry `[UX-F0-TRACER-PING] slug=<slug> stamp=COMPLETE dataflow_node=X`.
0.1 **JTBD Framework:** Write literally:
   ```
   When <SITUATION>, I want to <USER_ACTION>, so I can <EXPECTED_OUTCOME>.
   ```
   Maximum 1 line per JTBD. Minimum 3 unique JTBDs per feature. No empty "improve UX".
0.2 **Canonical User Persona:** Link `domains/ux/profile.md` persona + add 1 paragraph specific screen context. If no persona in level 1.5 registry → create via `/che-onboarding --edit`.
0.3 **Canonical Mermaid User Flow:** `flowchart TD` diagram minimum 3 nodes (Entry → Action A → Success State + Error State). NO stadium shapes. `<br/>` HTML breaks.
0.4 **Human Approved Gate:** Brief + JTBD + Mermaid flow + F0 UX tracer (0.0) sent to user. **EXPLICIT approval (literal "Approved" reply) is mandatory.** Without approval → DO NOT PROCEED to stage 1.

### Generated Artifacts (persist in workspace)
- `docs/ux/<slug>-00-tracer-ping.md` — F0 UX tracer ping (Stage 0.0).
- `docs/ux/<slug>-01-brief-jtbd.md` — Consolidated stages 0.0 → 0.4.
- `decisions.log.jsonl` entry type `[UX-BRIEF-APPROVED] <slug>` with content hash.

---

## Phase 1 — Low-fidelity Wireframe (structure, NOT aesthetics)

### Goal
Validate informational STRUCTURE and hierarchy. No colors, no icons, no fancy typography. Just boxes + placeholder text + arrows.

### Stages 1.1 → 1.3 (no skipping)
1.1 **Mobile-first mandatory:** Wireframe starts at **SM (390px wide)** viewport. NEVER start on desktop and reduce. After mobile approved → MD (768), then LG (1024).
1.2 **Primitives-only wireframe:** Rectangles = sections. Lines = texts (3 lengths: short/medium/long). Small circles = icons. DO NOT use brand color in this phase. No shadows. No radius.
1.3 **Human Approved Gate:** 3-breakpoint wire sent to user. EXPLICIT "Wireframe Approved" literal approval → proceed to stage 2. If structural adjustments → back to 1.1 / 1.2 to redo wire.

### Hard Fail Rules in this phase
- ❌ Desktop-first wire (mobile-last) = Fail back to 0.
- ❌ Contains real icons / images / radius / brand color = Fail back to 1.
- ❌ Missing 3 breakpoints (SM / MD / LG) = Incomplete fail.

### Generated Artifacts
- `docs/ux/<slug>-02-wireframe-sm.md` + `md` + `lg` (3 files)
- PenPot/Figma "Wireframe Low-fi" page link.

---

## Phase 2 — Hi-fi Prototype (official Figma or PenPot MCP)

### Goal
Apply Design System tokens from `domains/ux/profile.md` (spacing/radius/color/typography/shadow/motion) to approved wireframe. Produce hi-fi artifact for stakeholders + dev handoff.

### Stages 2.1 → 2.5 (no skipping)
2.1 **Set official connector:** Choose 1 (one) official connector (NO RAW REST):
   - **Recommended:** Figma via `domains/ux/connectors/figma.config.md` (official `mcp_open-pencil` MCP + `figma-cli` npm).
   - **Open-source alternative:** PenPot via `domains/ux/connectors/penpot.config.md` (official PenPot MCP).
2.2 **Apply ALL Design System tokens:** Every value comes from profile table. No loose hex / px. If a token is missing → FIRST propose new token for design system, THEN use.
2.3 **Mandatory 7 states table per interactive component:**
   | State | Mandatory Appearance (see profile tokens) |
   |---|---|
   | Default | No user interaction |
   | Hover | `:hover` with elevation md (4dp) + pointer cursor |
   | Focus | `:focus-visible` ring 2px primary-500 + 2px offset |
   | Active | `:active` with 0.97~0.98 scale + elevation sm |
   | Disabled | `aria-disabled="true"` + 0.4 opacity + cursor: not-allowed |
   | Loading | `aria-busy="true"` + role="status" + standard 300ms motion token spinner |
   | Error | Danger border + alert icon + helper text + SR label |
2.4 **Complete 4 Breakpoints:** SM (640) · MD (768) · LG (1024) · XL (1280). Each breakpoint = exact layout.
2.5 **Validated link + resolved comments:** All Figma/PenPot comment threads = "Resolved". Public link/permissions granted.

### Generated Artifacts
- Figma File / PenPot Project link + hi-fi page.
- `docs/ux/<slug>-03-hifi-notes.md` (tokens used, non-trivial decisions, alternatives considered).

---

## Phase 3 — Mandatory Quality Gates (NUMERICAL thresholds, no subjective evaluation)

> **Executed by `/che-ship §0.9.5 DOMAIN GATES` automatically when shipping a feature with `domain: ux`.** Same fail-fast engine as core (threshold + 1 free retry + human required after 2nd failure).

### Execution order (alphabetical by filename)

| # | Gate | Physical File | Mandatory Threshold | Retry Policy | Hard Stop? |
|---|---|---|---|---|---|
| G-UX-1 | **A11y WCAG 2.2 AA** | `domains/ux/gates/accessibility-gate.md` | `CRITICAL_count === 0` (0 critical errors · any number > 0 → FAIL). 10 auto-checks via official `@axe-core/cli`. | 1st failure: free retry applying axe-core report recommendations. | ✅ Yes. 2nd failure → request human. Do not open PR. |
| G-UX-2 | **Pixel Perfect** | `domains/ux/gates/pixel-check-gate.md` | `score_0_to_10 ≥ 8.0` AND `pct_elements_within_4px_tolerance ≥ 95%`. Deviation > 8px in 1 single critical element → FAIL. | 1st failure: free retry applying recommendations (fix top-3 largest deviations first). | ✅ Yes. 2nd failure → request human. Do not open PR. |

### Mandatory log per execution (decisions.log.jsonl)
```
[DOMAIN-GATE-EXECUTED] domain=ux gate=accessibility-gate status=PASS score=9.3 critical_count=0 duration_ms=4217 traceId=...
[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status=FAIL score=6.7 within_4px_pct=0.82 duration_ms=12143 traceId=...
```

### Explicit override prohibited by default
Lowering a gate threshold (e.g. pixel 8.0 → 7.0) is ONLY allowed via user `EXPLICIT_OVERRIDE` verbatim in chat, **logged in decisions.log** with `[EXPLICIT_OVERRIDE] domain=ux gate=... old=8.0 new=7.0 reason="..."`. Agent NEVER lowers threshold alone.

---

## Phase 4 — Dev Handoff (structured final delivery for dev)

### Goal
**NOT just sending a Figma/PenPot link and hoping.** No "look in Figma" measures. Absolutely everything structured in Markdown and JSON.

### Stages 4.1 → 4.5 (no skipping)
4.1 **Fill `domains/ux/templates/dev-handoff-template.md` template COMPLETELY:** Mandatory fields = SPEC id + ticket id · absolute px measures per breakpoint · supported browsers list · assets export SVG/PNG 2x path · animations duration/easing tokens · final accessibility checklist (15 profile items).
4.2 **Auto JSON design token export:** Run Figma Variables / PenPot Design Tokens extraction script → category-structured `tokens.json` file. No hardcoded values.
4.3 **Run `/figma-pixel-check` (if `/che-figma` implementation used):** Attach report to handoff.
4.4 **Run official `@axe-core/cli` axe-core final accessibility:** Attach JSON + HTML reports to handoff.
4.5 **Final human Approved:** Dev (or user) confirms literal "Handoff Complete and Understood".

### FINAL deliverables checklist to close playbook
- [x] Phase 0 JTBD Brief Approved ✅
- [x] Phase 1 SM/MD/LG Wireframe Approved ✅
- [x] Phase 2 Hi-fi 4 breakpoints + 7 component states ✅
- [x] Phase 3 Gate G-UX-1 (A11y) PASS critical_count=0 ✅
- [x] Phase 3 Gate G-UX-2 (Pixel) PASS score≥8.0 AND ≥95% ≤4px ✅
- [x] Phase 4 `dev-handoff-template.md` 100% filled ✅
- [x] Phase 4 `tokens.json` exported ✅
- [x] Final decisions.log entry: `[UX-PLAYBOOK-COMPLETE] slug=... gate_results={a11y:PASS,pixel:PASS} handoff_path=...` ✅

> **End of playbook.** Now `/che-ship` executes §0.9 G1-G4 normally (scope / review / compliance / QA), then §0.9.5 G5 Domain Gates re-confirms G-UX-1 and G-UX-2 in generated artifacts, and opens Draft PR.

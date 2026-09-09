---
domain: "product"
playbook_version: "0.1"
gate_files_required:
  - "gates/first-gate-template.md"
  - "gates/second-gate-template.md"
---

# Playbook — product

## 0. Preconditions (run before anything in this domain)
- [ ] Session has **domain:** field set correctly in SPEC frontmatter or Scrum Master flag.
- [ ] Domain `profile.md` loaded successfully by Scrum Master Step 0.3.
- [ ] All required connectors in `connectors/` directory have config present (if used).
- [ ] **Provider Pointer Pattern (NON-NEGOTIABLE, per CHE_RULES Geral vs Específico rule)**: General delivery structure lives HERE (playbook). Framework-specific product rules → delegates to `skills/project-management-expert/SKILL.md` (if absent, Linear/ClickUp/Jira rules inline). NEVER copy the 15 IDs or LEAN score values here — reference "per CHE_RULES §X Sxx".

---

## 1. Phase 1 — Brief / Discovery / Intake (minimal skeletal)
0.1 **Problem + Hypothesis statement (1 line each)**: Write literally.
  > **Problem**: `<who> cannot <action> today, because <specific pain>.`. Measured today as: `<N baseline metric>`.
  > **Hypothesis**: We believe shipping `<scope>` will `<move metric>` from `<N>` to `<M>` in `<time>`.
0.2 **North-Star KPI + 2 guardrail KPIs (S09 CHE_RULES companion — measurable success, NOT prose)**:
  | KPI type | Name | Baseline | Target (per S09 CHE_RULES §X = 0 if not met) |
  |---|---|---|---|
  | North | `north_event_weekly_active` | 1247/wk | ≥ 3200/wk |
  | Guardrail #1 | `north_support_tickets_p0` | 47/wk | ≤ 10/wk |
  | Guardrail #2 | `north_rollback_count_30d` | 3.2 | ≤ 1 |
0.3 **RICE Prioritization (per S08 CHE_RULES §X)**: Reach × Impact × Confidence / Effort. Score < 4.0 goes to backlog.
0.4 **Stakeholder RACI matrix + approval sign-off** BEFORE moving to Phase 2.
0.5 **Human approved gate**: Brief + KPI + RICE + RACI sent to user. EXPLICIT "Product Brief Approved" literal required.

### Outputs persistent artifact:
- `docs/product/<slug>-01-brief.md`

---

## 2. Phase 2 — Design / Draft / Implementation Roadmap
0.1 **Milestone breakdown W0..W5** (per S10 CHE_RULES §X schedule realism, ≥ 1 release point per 2 weeks):
  | Milestone | Shipable slice | Estimated effort (FTE-weeks) | Depends on |
  |---|---|---|---|
  | W0-F0 (Tracer) | Minimal end-to-end slice validates data flow | 0.5 | N/A |
  | W1 | Core interaction works | 2.0 | W0 |
  | W2 | Edge cases + error states | 1.5 | W1 |
  | W3 | Admin tools + support tooling | 1.5 | W1 |
  | W4 | QA + polish + docs | 1.0 | W2 |
0.2 **User Story Mapping (6-pack)**: 6 stories (happy path ×1 + edge ×4 + admin ×1) written as "As <persona>, I want <action> so that <outcome>."
0.3 **Go-Live checklist stub**: Rollback procedure + oncall rotation + comms plan written (can be 3-line stub).

### Outputs:
- `docs/product/<slug>-02-roadmap.md`
- Linear/ClickUp tickets created → 6-pack linked

---

## 3. Phase 3 — Quality Gates (run EVERY gate in gates/ folder)
**Thresholds in this table REFERENCE CHE_RULES §X Sxx canonical values. Numbers live in CHE_RULES; product gates CONSUME the canonical threshold via Sxx refs.**

Required gates for product:
| Gate file | Threshold to PASS | CHE_RULES §X ref | Auto-retry allowed (max N) |
|---|---|---|---|
| `gates/first-gate-template.md` | Score ≥ 7.0 / 10 (per S11 GEOMEAN companion ≥ 7.0 minimum Excellent category) | S11 + S13 geometric mean | 1 |
| `gates/second-gate-template.md` | 0 CRITICAL + < 3 HIGH items | S12 Data-Freshness max HIGH | 1 |
| **[G-PROD-1] RICE + KPI gate** (embedded, product-specific) | RICE score ≥ 4.0 S08 COMPLIANT · NS KPI > 0 target written S09 COMPLIANT | S08 (RICE min) + S09 (KPI target) | 1 |

Gate failure process (same for every domain, non-negotiable):
1. First fail → ONE free auto-retriable apply recommendations of gate.
2. Second fail → STOP. Ask human (domain owner) before proceeding further.
3. Never skip a gate or lower threshold without decision.log entry + user VERBATIM.

---

## 4. Phase 4 — Delivery / Handoff / Ship integration
After ALL gates PASS:
- Write product changelog entry `docs/product/<slug>-CHANGELOG.md` (What / Why / Impact / Rollback)
- Attach KPI pre-launch baseline screenshot to PR description
- Call /che-ship if code/artifacts go to git repo.
- If pure docs-only or creative-only deliverable: write final report + save in `$CHE_SESSION_DIR/reports/` for audit.

---

## Provider Pointer Pattern summary (Geral vs Específico separation)
| General pattern (HERE, language-agnostic) | Specific implementation (skill expert location) |
|---|---|
| Prioritization RICE formula · Milestone realism · KPI targets | Linear → `domains/product/profile.md` connector / ClickUp → `skills/project-management-expert/SKILL.md` / Jira → provider |
| Ticket writing rules · Epics + stories acceptance criteria | Per connector above — no duplicated ticket prose here |
| Numerical scoring of success quality | CHE_RULES §X S01-S15 canonical numbers — NEVER duplicated |

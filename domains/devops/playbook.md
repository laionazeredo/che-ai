---
domain: "devops"
playbook_version: "0.1"
gate_files_required:
  - "gates/first-gate-template.md"
  - "gates/second-gate-template.md"
---

# Playbook — devops

## 0. Preconditions (run before anything in this domain)
- [ ] Session has **domain:** field set correctly in SPEC frontmatter or Scrum Master flag.
- [ ] Domain `profile.md` loaded successfully by Scrum Master Step 0.3.
- [ ] All required connectors in `connectors/` directory have config present (if used).

---

## 1. Phase 1 — Brief / Discovery / Intake

## 2. Phase 2 — Design / Draft / Implementation

## 3. Phase 3 — Quality Gates (run EVERY gate in gates/ folder)
Required gates for devops:
| Gate file | Threshold to PASS | Auto-retry allowed (max N) |
|---|---|---|
| `gates/first-gate-template.md` | Score ≥ 7.0 / 10 | 1 |
| `gates/second-gate-template.md` | 0 CRITICAL items | 1 |

Gate failure process (same for every domain, non-negotiable):
1. First fail → ONE free auto-retriable apply recommendations of gate.
2. Second fail → STOP. Ask human (domain owner) before proceeding further.
3. Never skip a gate or lower threshold without decision.log entry + user VERBATIM.

## 4. Phase 4 — Delivery / Handoff / Ship integration
After ALL gates PASS:
- Call /harness-ship if code/artifacts go to git repo.
- If pure docs-only or creative-only deliverable: write final report + save in `$HARNESS_SESSION_DIR/reports/` for audit.

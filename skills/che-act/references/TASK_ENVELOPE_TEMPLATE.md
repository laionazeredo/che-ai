# TASK ENVELOPE TEMPLATE

> Filled by Scrum Master. Handed to Developer. Developer fills the remaining sections during execution.

---

## Metadata

| Field | Value |
|---|---|
| Task ID | `T<NN>` |
| Title | `<short imperative title, English>` |
| domain: | `engineering \| product \| ux \| devops \| copywriting \| social \| seo-analytics` (default: engineering) |
| expert_skills: | `[skill-a, skill-b]` or `[]` (auto-loaded by domain + envelope) |
| Part of session (task-id slug) | `<slug>` |
| Worktree | `<absolute path>` |
| SM created on | `<ISO datetime>` |
| Depends on tasks | `T1, T3` or `-` |
| handoff_output: (must exist before dependents run) | `[tasks/T3/dev-handoff-dashboard.md, ...]` or `[]` |

## Goal / Business Value

<2-3 sentences: what does this task deliver. English.>

## What this task DOES NOT cover (explicit out-of-scope)

- ...
- ...

---

## Acceptance Criteria (MUST be testable)

Use Given / When / Then where possible:

1. **AC-1:**
   - GIVEN:
   - WHEN:
   - THEN:
2. **AC-2:**
   - GIVEN:
   - WHEN:
   - THEN:

## DONE Criteria (checklist — checked by SM)

- [ ] All ACs above are demonstrably met
- [ ] engineering-contracts skill invoked FIRST (check Dev pre-reporte)
- [ ] Repo onboarding Q1/Q2/Q3 answered in writing
- [ ] Public contracts defined (preconditions / postconditions / invariants)
- [ ] Unit/integration tests written FIRST (TDD)
- [ ] Implementation passes all tests
- [ ] Blast radius ≤ 10 files (or SM-approved exception logged)
- [ ] All touched files are on the "allowed files list" below (or SM-approved exception logged)
- [ ] No new dependencies added (or reuse-checked + SM-approved logged)
- [ ] Passes all QA gates (build / lint / typecheck / tests)
- [ ] Passes Compliance LIGHT (per-task stage)
- [ ] (domain != engineering only) Domain gates passed — che-ship §0.9.5
- [ ] handoff_output[] files written and SHA256 checksum logged (if this task is dependency for others)

---

## Blast Radius — Allowed Files / Directories

Developer MAY ONLY touch these files. If others are needed → back to SM for approval + decision.log entry.

```
ALLOWED (explicit list of files or parent directories):
  - path/to/fileA.ts (EDIT — function signature change)
  - path/to/fileB.test.ts (NEW — unit tests for fileA)
  - packages/moduleX/** (EDIT + NEW — related types + test)

FORBIDDEN:
  - packages/other-project/** (touching this = BLAST RADIUS VIOLATION)
  - Any file outside the workspace root, outside worktree
```

## Reuse Mandate (Rule 3 + 4 from engineering-contracts)

Specific existing symbols the code MUST reuse / extend (if any):
- `existingHelper(input)` in `src/utils/helper.ts` for the X calculation
- `Logger` from `packages/logger` — NO console.* calls

If you think you need a NEW dependency / NEW class: list why reuse is not viable, wait SM approval.

## Type / Level of Changes

- Change type: `domain-pure` | `api-route` | `ui-component` | `db-schema+migration` | `config` | `other`
- Test level expected: `unit-only` | `unit + integration` | `E2E added`
- Architectural pattern to follow: `functional-core/imperative-shell` | `repo existing: XXX`

---

## Developer Output (filled by Dev during execution)

### Dev Onboarding — Answers (MANDATORY, answered BEFORE coding)

**Q1. What is the established architectural pattern here?**
A:

**Q2. Where is similar code I can REUSE? (List 2+ specific symbols or "none found" + justification)**
A:

**Q3. What are the lint / build / test commands for this area?**
A:

### Public Contracts (Design by Contract — MANDATORY before coding)

**Module / function being created / modified:**

#### Function: `<name>(<args>)` → `<return type>`
- **Preconditions (input):**
  - args validated as: ...
- **Postconditions (output):**
  - Returns: ...
  - Side effects: ...
- **Invariants:**
  - ...

### Dev Pre-Relatório

**Summary:**

**Files Touched:**
- `<path>` (NEW / EDITED — lines XX-YY)
- ...

### Self-Checks performed

- [ ] engineering-contracts skill invoked FIRST
- [ ] Repo onboarding Q1/Q2/Q3 answered above
- [ ] Public contracts defined
- [ ] Tests written FIRST (TDD red phase — confirmed failing)
- [ ] Implementation (green phase — tests pass)
- [ ] Refactor pass applied
- [ ] Blast radius: files count = `N` ; N ≤ 10 OR SM exception logged
- [ ] All touched files in allowed list OR SM exception logged
- [ ] No new dependencies without reuse check + SM approval
- [ ] handoff_output files generated for dependents (if list non-empty)

**Risks / Open Questions:**
- ...

---

## History — Iterations (auto-managed by SM/Dev/QA loop)

| Iteration # | Stage | Actor | Result | Notes |
|------------|-------|-------|--------|-------|
| 0 | Handoff | SM → Dev | Task started | Envelope v1.0 |
| 1 | Scope validation | SM | PASS / FAIL (reason) | |
| 2 | QA | QA | PASS / FAIL (reason) | |
| 3 | Compliance (light) | Compliance | PASS / FAIL (reason) | |

---
name: "harness-spec"
description: "Generate or validate a Harness Execution Specification (SPEC). 4 inputs: existing spec file, ticket URL (Linear/ClickUp/GitHub), legacy-project PRD .md path, or inline brief. Produces 7 sections + machine-parsable YAML frontmatter, user-approved before save into $HARNESS_WORKSPACE_SHARED/spec_<slug>.md (DURABLE workspace area OUTSIDE user worktree code)."
---

# Harness Spec Generator (SPEC)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Full contracts (precedence 1-18, DbC, BDD incremental, etc): `engineering-contracts` skill
> - Path resolution (WORKSPACE_NAME, WORKTREE_SLUG, HARNESS_WORKSPACE_SHARED, HARNESS_SESSION_DIR): `source "${HARNESS_HOME:-$HOME/.trae}/contracts/harness_sessions_contract.sh"`, call `harness_compute_paths WT SID CWD`
> - Worktree binding 2-LEVEL (Level1 registry, Level2 sessions dir): engineering-contracts §19

Produces **1 file per feature/bug/refactor:** a compact, agent-optimised spec (~60–120 lines, 7 sections). Replaces project-specific legacy PRD artifacts. Gate before scope capture in `/harness-start` and standalone runnable via `/harness-spec`.

---

## §0 PURPOSE & INTEGRATION

When called:
1. **From `/harness-start` (embedded)**: runs AFTER binding §19 + ensure_dirs, BEFORE scope capture §1. User says which SPEC to use or generates new.
2. **Standalone** via `/harness-spec`: runs independently; performs binding if needed, then generates or edits spec.

On completion this skill **returns to the caller** two values printed in the last 2 lines of the transcript:
- `SPEC_PATH=<absolute-path-to-spec>` — used by harness-scrum-master
- `SPEC_STATUS=Approved|Draft` — only `Approved` unlocks subsequent execution in SM.

---

## §1 PREFLIGHT (Run FIRST)

Fail if any step fails. Stop before proceeding with user.

1. **Binding check:** Read `harness_registry_path`, find LAST entry with the effective session id from `harness_current_session_id` + `STATUS=BOUND`. If missing AND user did not provide `--worktree` → ASK for absolute worktree, perform full §19 binding (Level1 append + Level2 write + FRIENDLY_NAME prompt).
2. **Paths:**
   ```bash
   source "${HARNESS_HOME:-$HOME/.trae}/contracts/harness_sessions_contract.sh"
   harness_compute_paths "$WORKTREE_ROOT" "$(harness_current_session_id)" "$PWD"
   harness_ensure_session_dirs
   ```
3. **Slug:** If user passed `--slug`, use it as-is (sanitize to `[a-z0-9_-]+`). Otherwise derive from `ticket_ref` or `change_class+why`.

---

## §2 SOURCE SELECTION (4 inputs)

Present choices when input arg is missing or ambiguous. First match wins, never fallback silently.

| # | Source | User provides | Action before draft |
|---|---|---|---|
| A | **Existing SPEC file** | File path OR pick from glob `$HARNESS_WORKSPACE_SHARED/spec_*.md` | Read it; if `status=Approved` → jump straight to §5 (approval). If Draft → proceed to §3 editing with the existing content pre-filled. |
| B | **Ticket URL** (Linear FLO-XXX, ClickUp, GitHub issue) | Full URL | 1. Try to extract title + description + status via MCP tools (`mcp_flockr-linear`, `mcp_laion-clickup`, `mcp_github`). If MCP fails → fall back to user-provided inline description. 2. Populate frontmatter `ticket_ref:` + `spec_id:` from slug. 3. Seed §1 WHY bullets from ticket description. 4. Seed §4 MUST ACs = 3 bullets if ticket has Acceptance Criteria field. |
| C | **Legacy PRD** (.md legado do projeto) | Absolute path to `.md` file | Parse with headings, map: `Problem / Background` → §1 WHY; `Goals` → §4 MUST; `Non-Goals` → §1 Non-goals; `Data Model / Migration` → §6 Hints; `Acceptance Criteria` → §4 MUST AC, each prefixed `GWT` verbatim; `Risk` → §5 Rollback trigger. If section missing → leave empty and prompt user to fill during §4 review. |
| D | **Inline brief** (short text 2–5 sentences) | User typed description or typed nothing at all → walk through interactive prompts 1-by-1 | Prompt for: change_class (feature|bug|refactor|perf|ops); 3 bullets §1 WHY; 3 sections §2 (Can Touch ≤ 10 files, Can Create, Cannot Touch ≤ 5 lines); 3 PRE + 3 POST + 2 INVARIANTS in §3; 3 MUST + 1 SHOULD + 1 MAY §4 ACs (each AC must include GWT + TEST_METHOD literal). Defaults: `estimated_files_max=15`, `estimated_max_lines_add=400`, `new_dependencies=[]`, `pii_touch=none`, `supabase_rls_touch=false`, `currency_gbp_pence=false`, `domain=engineering`, `flags=LANG_PT_CHECK=ENABLED`. |

---

## §3 SPEC DRAFT STRUCTURE (7 sections, canonical)

Write the draft in-memory first. File starts with YAML frontmatter, THEN 7 markdown sections.

### §HEAD — YAML Frontmatter (REQUIRED fields — validate all present)
```yaml
---
spec_id: <slug-sanitized-alphanum-dash-underscore>
ticket_ref: <"FLO-745" or "NONE">
worktree_root: <absolute-path>
change_class: feature|bug|refactor|perf|ops
domain: engineering                  # valores aceitos: engineering | product | ux | devops | copywriting | social | seo-analytics
                                      # default = engineering (retrocompat total com specs/sessões/skills antigas sem esse campo)
                                      # se != engineering → SM §0.3 auto-carrega domains/<domain>/profile.md + playbook.md
                                      # se != engineering → ship §0.9.5 executa gates obrigatórios playbook
status: Draft
estimated_files_max: <integer; default 15; hard stop per §15>
estimated_max_lines_add: <integer; default 400; trigger for gh-stack>
new_dependencies: [ ]
pii_touch: none|read-only|write
supabase_rls_touch: true|false
currency_gbp_pence: true|false
bound_agent_lang: default|pt-BR|en
flags: LANG_PT_CHECK=ENABLED[, RLS_MANDATORY=NO]
approver: ""
approved_at: ""
---
```

### §1 WHY — Problem Statement (max 5 bullets)
Header: `## §1 WHY (Problem Statement)`
- 3–5 bullets only. Example structure:
  - Current: <what breaks today, 1 line concrete>
  - Risk: <security or business impact or UX pain>
  - Goal: <outcome in 1 line>
  - Success metric: <curl / behavioral assertion>
  - Non-goals: <what this SPEC does NOT do>

### §2 SCOPE — Blast Radius (3 lists, each ≤ 10 items)
Header: `## §2 SCOPE BOUNDARIES & BLAST RADIUS`
Three subsections EXACTLY:
- `### ✅ CAN TOUCH (<=10 files literal paths or glob patterns)` — ≤10 entries
- `### ✅ CAN CREATE (<=8 files/folders)` — new files; include folder path only if empty dir creation required
- `### ❌ CANNOT TOUCH (under any circumstances)` — list paths or packages; last bullet always: `Any worktree other than bound <WORKTREE_ROOT> (§19 scissor)`
- Optional bullet: `### External services touched:` (list services touched or `None`)

### §3 CONTRACTS (DbC — PRE / POST / INVARIANTS)
Header: `## §3 CONTRACTS (Design by Contract)`
- `### PREconditions (before start)` — ≥2 bullets, ≤5. Examples: bound worktree valid; HEAD snapshot taken; no uncommitted on §2 files; env var X set.
- `### POSTconditions (after all tasks DONE — assertion-ready)` — ≥3 bullets, ≤8. Each bullet = a statement you can run a single test against; use `==`, `∈ {x,y}`, or plain assert verbs.
- `### INVARIANTS (never break, even temporarily)` — ≥1, ≤5. Last INV if empty add: `INV-<N>: Files listed in CANNOT TOUCH §2 remain byte-for-byte unchanged git diff.`

### §4 ACCEPTANCE CRITERIA (MoSCoW + Given-When-Then + TEST_METHOD per line)
Header: `## §4 ACCEPTANCE CRITERIA (MoSCoW + GWT + HOW TO TEST)`
Format per bullet — ONE AC per line (strict):
```
- [MUST|SHOULD|MAY] AC-<id> GIVEN <setup> WHEN <action> THEN <assertion> | TEST=<Vitest unit|Playwright login+curl|curl local|manual QA visual|Postman collection|Vitest e2e|DB query|tRPC assert>
```
Rules:
- ≥3 MUST; ≥1 SHOULD; ≥0 MAY. ≤10 total.
- Every `THEN` assertion is **falsifiable in 1 operation** (no vague wording like "improve UX").
- TEST= must match one of the provided tokens above, followed by any 1-line qualifier. Do not invent new tokens without logging exception in decision.

### §5 TEST STRATEGY (layers + PASS/FAIL thresholds + Rollback)
Header: `## §5 TEST STRATEGY (QA orchestration)`
Four subsections, ≤3 bullets each:
- `### Execution order (FAIL FAST):` Phase 1 SMOKE (3 core MUSTs — run via `test_spec_smoke.md`); Phase 2 UNIT per task; Phase 3 API E2E or Playwright; Phase 4 REGRESSION GUARDS INVARIANTS.
- `### PASS/FAIL thresholds:` Dev handoff Vitest per MUST unit ≥1 pass; QA 100% MUST + ≥80% SHOULD; Ship gate INVARIANTS 2 runs.
- `### Rollback trigger (when to abort):` Single trigger sentence. E.g. "If INV-1 fails at ANY phase → revert last 1 commit, open follow-up SPEC for root cause."
- `### Evidence location:` — Reminder (auto-filled): `$HARNESS_SESSION_DIR/qa/screenshots/*` + `$HARNESS_SESSION_DIR/qa/logs/*`; manual_test_plan DURÁVEL em `$HARNESS_WORKSPACE_SHARED/manual_test_plan.md`.

### §6 IMPLEMENTATION HINTS (opt-in, only if re-use exists or gotchas)
Header: `## §6 IMPLEMENTATION HINTS`
- 2–5 bullets only. Empty section OK = skip. Each bullet: 1 reference to existing function/class/commit hash or 1 gotcha about runtime (Edge restrictions, build-time files, DI rules).

---

## §4 VALIDATION PASS (auto-run on draft)

Reject draft and loop back to §2 source if ANY fails:
1. YAML frontmatter all REQUIRED keys present; parseable as YAML.
2. `estimated_files_max ≤ 20` (§15 engineering-contracts KISS); if >20 → force user to reduce scope or trigger gh-stack immediately.
3. §1 WHY bullets ≤ 5.
4. §2 CAN TOUCH count ≤ 10 literal files or glob entries.
5. §3 ≥3 POSTconditions, ≥1 INVARIANT.
6. §4 ACs: ≥3 MUST. Every bullet contains literal `GIVEN` and `WHEN` and `THEN` and `| TEST=`.
7. §5 rollback trigger: exactly 1 trigger sentence, non-empty.
8. (OPTIONAL, só validar SE `domain:` fornecido DIFERENTE de default `engineering`) → value MUST be in enum EXATA os 7 slugs canônicos: `engineering | product | ux | devops | copywriting | social | seo-analytics`. Se digitado errado (typo, slug não reconhecido), valor vazio mas diferente de engineering, ou cross-domínio 2+ valores → **REJECT draft com mensagem clara**: "Campo `domain: <valor_invalido>` inválido. Valores aceitos: engineering | product | ux | devops | copywriting | social | seo-analytics. Default omissão = engineering (retrocompat). Corrija o frontmatter ou remova o campo para usar default." Loop back usuário corrigir antes de Approved gate.

---

## §5 APPROVAL LOOP (1 main pass, 1 edit pass MAX — KISS)

1. **Show draft** to user as compact markdown, WITH a legend at the top saying "Draft SPEC. Reply A = Approve as-is. Reply B = adjust <tell what to change>."
2. **If A (Approved verbatim):**
   - Update frontmatter → `status: Approved`
   - Set `approver: "user-verbatim: A"`
   - Set `approved_at: <ISO timestamp local tz>`
   - Jump to §6 SAVE.
3. **If B (adjust X):**
   - Apply edits literally to the sections user indicated (no scope creep beyond what the user typed).
   - Re-run §4 VALIDATION.
   - Re-show ONE TIME only.
   - User now either Approves → update frontmatter Approved → SAVE. OR says "more edits" → tell user to re-run `/harness-spec` fresh (avoid infinite loops).
4. **If user says "Cancel":** Write Draft (no Approved flag) → SAVE anyway for future work. Print warning: `SPEC_STATUS=Draft (not Approved — harness-start will re-prompt when you run it)`. End.

---

## §6 SAVE (atomic write)

1. **Final sanitize slug:** `slug = frontmatter.spec_id` sanitized `[^a-zA-Z0-9_-] → -`.
2. **Target path:** `$HARNESS_WORKSPACE_SHARED/spec_<slug>.md`
3. **Check existing overwrite:** If file already exists AND status in existing is Approved → ask "Overwrite Approved spec? Yes/No" before writing. Yes = overwrite. No = append suffix `-v2`, `-v3` to slug until unused.
4. Write file atomically: write to `$HARNESS_WORKSPACE_SHARED/.spec_<slug>.md.tmp` first, then `mv` on top of final path (never half-written file visible).
5. Append entry to `$HARNESS_WORKSPACE_SHARED/decisions.log.jsonl` (DURÁVEL): `[SPEC] <slug> <status> saved at <ISO ts>. Approver=<approver>`.

---

## §7 RETURN VALUES

Print LAST 2 lines of transcript in a fenced code block EXACTLY:

```
SPEC_PATH=<absolute path of saved spec, no quotes>
SPEC_STATUS=Approved|Draft
```

Scrum Master §0.5 parses these 2 lines to proceed.

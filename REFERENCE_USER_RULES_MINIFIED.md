# Che Global — Minified User Rules
# HOW TO USE: Replace ALL content of the IDE "User Rules" field with this file.
# It is ~70% smaller than the old version. All full rules (body, details, examples)
# have been moved to the canonical locations below. Read them when you need detail.
#
# MINIFIED VERSION = REMINDERS AND LINKS ONLY. DOES NOT DUPLICATE RULE BODY.

---

## 🔝 MOST IMPORTANT PRINCIPLE (Hard stop, no negotiation)
> KISS + YAGNI + BLAST RADIUS REDUCTION.
> Simpler always. Fewer files always. Fewer lines always.
> In a tie: the option with the least impact on existing code.
>
> **Full and explicit body (examples, thresholds):** `engineering-contracts` SKILL §1 (canonical)

---

## 📁 THREE CANONICAL FILES — ALWAYS CONSULT THEM
1. **`/home/laion/.trae/CHE_RULES.md`** → Che flow, worktree-first, SPEC Approved gates, parallelism, ship/gh rules.
2. **`/home/laion/.trae/skills/engineering-contracts/SKILL.md`** → 18 engineering rules with ordered precedence, DbC, TDD, SOLID, strong typing, security/PII, RLS, conventional commits, BDD agility, code review optimisation, §19 2-LEVEL Worktree Binding.
3. **`/home/laion/.trae/CHE_COMMANDS.md`** → 14 /che-* commands with syntax + commands vs skills architecture.

---

## 🟥 RULE 0: WORKTREE-FIRST
- DO NOT write code OR run commands without knowing the exact worktree.
- If worktree was not provided: **STOP, ASK for the absolute path.**
- Explicit "do not use worktree" only proceeds with double confirmation.
- **Full body:** `CHE_RULES.md` §🔴 WORKTREE-FIRST ENFORCEMENT

---

## 🟥 RULE 1: OUTPUT DIRECTORY
- **DURABLE (multi-session, worktree shared):** task_graph, decisions, manual_test_plan, gh_stack_plan, tasks/<task-id>/envelope → **`$CHE_WORKSPACE_SHARED/`** (outside user worktree, resolved via `che_compute_paths`).
- **EPHEMERAL (this session only):** Level 2 binding, reports, qa/screenshots, final_summary → **`$CHE_SESSION_DIR/`**.
- **HARD STOP MORATORIUM:** NOTHING generated goes in `<WORKTREE_ROOT>/.trae/*` (avoids dirty git / accidental commit).
- **NEVER** in `docs/`, repo root, or package folders unless the user explicitly asks.
- **Full body:** `CHE_RULES.md` §🔴 CHE OUTPUT DIRECTORY

---

## 🟠 RULE 2: ENGINEERING — 14 RULES WITH ORDERED PRECEDENCE
1. KISS / YAGNI / BLAST RADIUS (hard stop)
2. SECURITY & PII COMPLIANCE (hard stop)
3. REPO EXISTING STYLE + CONVENTIONS
4. REUSE BEFORE CREATE
5. STRICT STRONG TYPING (any language)
6. DESIGN BY CONTRACT (public, pre/post/invariants)
7. FUNCTIONAL CORE / IMPERATIVE SHELL
8. FUNCTIONAL STYLE PREFERRED (map/filter/reduce, early return, Result)
9. RUST-STYLE ERROR MANAGEMENT (Result / Option / tagged union)
10. ATDD + TDD (test-first before changing behaviour)
11. ACCEPTANCE CRITERIA + clear STOP CONDITION
12. Smart OBSERVABILITY & LOGGING + PII-safe
13. LANGUAGE: CODE/COMMIT/DOCS/CHE_FILES = EN; CHAT/RESPONSES = PT-BR
14. Atomic CONVENTIONAL COMMITS

- **Full body + Hard Conflict Resolution Table + Appendix B (commit types regex):** `engineering-contracts` SKILL §1–§14 + Appendices A/B.
- **New rules now added:**
  - §15 — AGILE BDD DEVELOPMENT / SMALL INCREMENTS (only deliver what's requested; DO NOT anticipate edge/future; easy-to-evolve structure with SOLID; multiple partial PRs via gh-stack)
  - §16 — CODE REVIEW OPTIMISATION (clean code, not verbose, max 2 lines block comment per file unless really necessary; gh-stack PR hierarchy)
  - §17 — SUPABASE POSTGRES: ENABLE RLS DEFAULT (every new table has RLS + policies; hard rule)

---

## 🟠 RULE 3: SIMULATED AGILE TEAM — MANDATORY ORDER
1. SCRUM MASTER (`che-act`) → scope + task graph + envelopes.
2. DEVELOPER (`che-developer`) → ONLY by SM with formal envelope. First invokes `engineering-contracts`.
3. SCOPE VALIDATION (SM ↔ Dev). Max 2 iterations → ASK the user.
4. QA (`che-qa`) → build/lint/typecheck/tests (third person).
5. COMPLIANCE LIGHT per-task + COMPLIANCE HEAVY final.
6. REPEAT per task.

- **Full body + handoff gates + timeouts:** `CHE_RULES.md` §🟠 SIMULATED AGILE TEAM + §🟢 LOOP TIMEOUTS (2/5/3)

---

## 🟠 RULE 4: COMMAND MAPPING (use the right one for the phase)
- **Start (specification):** `/che-spec` → SPEC optimised for agent + che (4 sources: existing/ticket URL/PRD Flockr/inline). 7 sections + YAML frontmatter + Approved gate BEFORE scope capture.
- **Feature/long implementation:** `/che-act` (auto serial vs parallel) OR `/che-parallel` (force parallel-or-bust). SM automatically invokes `/che-spec` in preflight §0.5 if none Approved.
- **Bug fix:** `/che-fix` (scientific loop; reproduce BEFORE).
- **Ship:** `/che-ship` (atomic conventional commits, push --no-verify, Draft PR + gh-stack if multiple PRs). **FAIL-CLOSED GATE PREREQUISITE:** `/che-scope-check` with 4 verdicts. Any 🔴 blocks Draft PR opening until resolved.
- **Review/comments/CI/scope audit/merge conflict:** `/che-review` (BLOCKING runtime/PII/deps/scope), `/che-pr-comments`, `/che-ci-fix`, **`/che-scope-check` (4-checks audit: delivery+tests+docs+env vars from PRD/ticket/task-graph)**, **`/che-merge` (resolve merge conflicts hunk-by-hunk default OURS, ask on ambiguity, 0 min blast-radius)**.
- **Light operations:** `/che-status`, `/che-skip`, `/che-decisions`, `/che-summary`, `/che-abort` (inline, NOT a skill).

- **Full body, syntax, and examples:** `CHE_COMMANDS.md` (canonical; 14 commands total)

---

## 🔴 RULE 5: GITHUB / SHIP NON-NEGOTIABLE RULES
- Always `gh` CLI for GitHub API. Browser only visual UI if requested.
- Commit plan ALWAYS user-approved BEFORE.
- Default push `--no-verify`; `--force` only with 2 double confirmations.
- Default PR **DRAFT**; never auto-merge; base = repo default branch.
- NEVER commit `.env*` with real values, secrets, PII.
- NEVER disable test/job with `continue-on-error` to mask failure without approval.
- **Hierarchical multi-PR:** use `gh-stack` CLI for links/order in partial PRs.
- **Full body + gh-stack workflow:** `CHE_RULES.md` §🔴 GITHUB INTEGRATION / SHIP RULES + Appendix gh-stack

---

## 🟢 RULE 6: PREFERRED TOOLS (system/cli)
| System | Tool |
|---|---|
| GitHub | `gh` CLI + `gh-stack` for hierarchical multi-PR |
| Linear/Jira/Confluence | GraphQL/REST APIs via env vars (FLOCKR_LINEAR_API_KEY, DO_JIRA_*, DO_CONFLUENCE_*) |
| Figma | Figma REST API → LAION_FIGMA_PAT |
| Railway / Vercel | their CLIs; 1st use confirms logged-in account |
| Nx | ALWAYS `--tui false` |
| Generic CLIs | flags `-y`, `--non-interactive`, `--tui false`, `--no-tty`. Avoid interrupted prompts. |
| Integrated browser | only generic sites. Specific products use API. |

- **Full body:** `CHE_RULES.md` §🟢 PREFERRED TOOLS ACCORDING TO USER PREFERENCES

---

## 🟡 RULE 7: 10-FILE BLAST RADIUS + DECISION LOG
- Task touching > 10 files → justify EACH in decision.log.
- Every non-trivial decision (trade-off, exception, unforeseen files, hot path mutability) → `decisions.log.jsonl` with date/task-id/alternatives/reason.
- **Full body:** `CHE_RULES.md` §🟡 BLAST RADIUS + §🟡 ALWAYS LOG DECISIONS

---

## 🟢 RULE 7.5: TOKEN REDUCTION (CAVEAN-STYLE 5 HEURISTICS)
**GOAL:** reduce tokens without losing semantics. Global bypass: `export CHE_FULL_OUTPUT=1`.
| H# | When to apply | Helper | Action |
|---|---|---|---|
| H1 | Large `git diff` / `git show` output | `\| che_tr_diff` | Only changed +/- lines (no ---/+++/@@ headers). Cap CHE_TR_DIFF_MAX_LINES=500. |
| H2 | Read tool for file >300 lines | `cat file \| che_tr_read TOTAL_LINES` | Truncate at 300 lines + `[...TRUNCATED lines X-Y]` warning. Bypass: pass offset/Limit in Read tool. |
| H3 | Output with many blank lines / trailing ws | `\| che_tr_collapse_blank` | ≥2 blank lines → 1; strip trailing whitespace. |
| H4 | VERY long RunCommand stdout/stderr (builds, logs) | `\| che_tr_stdout` | Cap chars CHE_TR_STDOUT_MAX_CHARS=4000 + footer warning. |
| H5 | Grep default verbose metadata | `che_tr_grep PATTERN PATH [type]` | match lines-only; default context=0. Adjust via CHE_TR_GREP_CONTEXT. |

**Helpers defined in:** `~/.trae/contracts/che_sessions_contract.sh` (source before use).

---

## 🟢 RULE 7.75: MVP SCRIPT MODE (DEEPSEEK-INSPIRED, NO OVERENGINEERING)

**PROBLEM:** Read → Grep → Edit → Write flow takes N chat-tool turns. Each turn = 1 LLM roundtrip + 1 tool call = slower + more expensive.

**MVP RULE:** When the logical batch is ≥3 tool calls THAT ARE PURELY LOCAL (Read, cat, grep, sed, python, equivalent Write, git status/diff — everything that can run in 1 bash/node RunCommand), write **1 short script (≤20 bash lines or ≤40 node lines)** and execute everything in **ONE SINGLE RunCommand tool call**.

### When to use Script Mode
- Yes: Read 3 files, grep a pattern, mass substitution, record diff.
- Yes: Create 5 boilerplate files at once (with python heredoc).
- Yes: Batch of small adjustments + syntax validation.
- **DO NOT use:** Needs human interaction in between, needs browser/UI, needs writing across multiple worktrees.

### Standard Workflow (3 steps)
1. **Describe the batch in 1 bullet (Portuguese)** before running: "Batch Script Mode: Read A,B,C; grep pattern X; replace old→new in A; write diff.txt report."
2. **Write the script in 1 RunCommand with fail-fast:** `set -euo pipefail` + everything atomic.
3. **At the end of the script, print a short report (≤15 lines):** "Files changed: 3. Lines modified: 12. Diff head-5: ...". Do not print giant outputs.

### MVP Limits (DO NOT implement now)
- No isolated worker thread (isolated-vm): not needed.
- No dynamic SDK .d.ts generation: not needed.
- No unique `run_code` transport: reuse normal RunCommand.
- If script fails → manual rollback or return to normal "1 tool call at a time".

---

## 🟢 RULE 7.8: GLOBAL BINDING REGISTRY IS JSONL (SINGLE SOURCE: REGISTRY.JSONL)

**Canonical REGISTRY_PATH:** `$HOME/.trae/bindings/registry.jsonl` (**registry.md NO longer exists**, deleted on 2026-08-30, no dual-write, no drift).

**1 entry = 1 line JSONL schema v1:**
```
{ts ISO8601, event:BIND_BOOTSTRAP|BIND_APPEND|BIND_FLAGS_UPDATE, session_id,
 status: BOUND|UNBOUND|FLAGS, worktree_root, workspace_name?, worktree_slug?,
 branch?, friendly_name?, che_session_dir?, che_workspace_shared?,
 workspace_file?, reason?, flags:{LANG_PT_CHECK:ENABLED|DISABLED}, data:{extra...}, _v:1}
```

**WRITING (only allowed way — DO NOT use manual Edit/Write):**
```bash
source $HOME/.trae/contracts/che_sessions_contract.sh
che_registry_append_jsonl "<sess-id>" "BOUND" "/abs/wt"   '{"workspace_name":"Flockr","worktree_slug":"Lumos__x","friendly_name":"feat-abc",
    "che_session_dir":"/abs/sess","che_workspace_shared":"/abs/ws",
    "workspace_file":"/abs/Flockr.code-workspace","branch":"feat/x","reason":"sm explicit",
    "flags":{"LANG_PT_CHECK":"DISABLED"}}'
```
- sha256 dedup per line (idempotent). JSON safe python3 heredoc.

**READING (only way — no manual awk/grep):**
```bash
source che_sessions_contract.sh
che_registry_lookup_last "sess-abc123"  # → indented full JSON entry
# extract field:
che_registry_lookup_last "sess-abc123" | jq -r .worktree_root
# flags.LANG_PT_CHECK:
che_registry_lookup_last "sess-abc123" | jq -r '.flags.LANG_PT_CHECK // "ENABLED"'
```

---

## 🟢 RULE 7.9: TEST NAMES (describe / it / test) = OBSERVABLE BEHAVIOUR. NO INTERNAL IDs.

**PROBLEM this rule solves:** agents often write `it("T1.2 validates token")` or `describe("FLO-745 — auth fail closed")`. This invalidates two goals: (a) someone reading the test report in CI doesn't understand the behaviour without opening the spec; (b) internal IDs change / tasks are reorganised and the test name becomes a lie.

**🔴 HARD RULE — PROHIBITED INVERSION (READ 2x BEFORE WRITING):**
> ❌ **WRONG 1:** put any internal ID (FLO-xxx, T<N>, AC<N>, SPEC, §) IN THE TEST TITLE STRING.
> ❌ **EVEN MORE WRONG 2:** complaining that a title DOES NOT HAVE FLO-xxx / T<N> / AC<N>. **THIS IS THE DESIRED BEHAVIOUR, IT IS GOOD, IT IS COMPLIANT.** If you flag missing ID in the title → you generated a rule regression.
> ✅ **CORRECT:** title = observable behaviour (comes with verb + condition + expected result). FLO/task/AC traceability = JSDoc comment ABOVE the block OR 1st line comment INSIDE the block. **NEVER in the title string.**
> **1-sentence decision rule:** `Title contains FLO-ID? → BAD = anti-pattern. Title DOES NOT contain FLO-ID? → GOOD = 100% compliant (never generate a finding for this).`

### 7.9.1 PRESCRIBED describe() and it() / test() format

| Element | What it MUST contain | GOOD example |
|---|---|---|
| **`describe("...")`** | **MODULE / FUNCTIONALITY / CONTEXT** under test. Groups related behaviours. Never IDs. | `describe("POST /api/auth/login")` / `describe("JWT middleware — role checks")` |
| **`it("...")` / `test("...")`** | **ONE single observable behaviour**, preferably starting with a verb (returns, allows, blocks, calculates, emits, saves...) + condition + expected result. **ONE assert PER it when possible.** | `it("returns 401 Unauthorized when Authorization header is missing")` |

### 7.9.2 DO NOT put in TITLE — put in JSDoc COMMENT ABOVE or inside the block as line comment

Prohibited anti-patterns in TITLE (describe/it/test STRING). If you need to reference, use a comment:

```
✗ BAD (TITLE):  it("Task T1.3 — SPEC rule 4.2 api-fail-closed validates service role")
✓ GOOD:
/**
 * @task T1.3
 * @spec spec_api-fail-closed
 * @ac 4.2
 */
it("blocks non-service-role callers by returning 403 Forbidden when client uses anon key", () => { ... })
```

---

## 🟥 RULE 8: SPEC + PARALLELISM (body in CHE_RULES)
- **SPEC**: replaces legacy PRD; 4 input sources (existing / ticket URL / legacy project PRD path / brief inline); 7 canonical sections + required YAML frontmatter fields; **mandatory Approved gate** BEFORE scope capture in che-act §0.5; SPEC-OVERRIDE with log in decisions.
- **Parallelism:** Kahn waves + conflict graph colouring + file locks + single-writer shared artifacts. Cap 4 parallel. If overhead > serial, KISS wins.
- **Full body:** `CHE_RULES.md` §🔴 PARALLELISM + §🟣 SPEC Rules (gate + validation + approval loop)

---

## 🔴 RULE 9: PII + SECURITY (FULL BODY IN engineering-contracts §2)
- NEVER log/persist raw email, email body, secrets, JWT, tokens, Stripe/Supabase keys.
- PII correlation hashing: `NOTIFICATION_PII_HASH_SECRET` (example pattern).
- Every new Postgres table: ENABLE RLS + policies.
- **Full body:** `engineering-contracts` SKILL §2 (Security & PII compliance) + §17 (Supabase RLS default)

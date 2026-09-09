---
name: "che-scope-checker"
description: "6-check scope audit persona (CANONICAL 2026-09: 4 legacy checks + 2 new). From PRD/ticket/task-graph + GitHub PR OR local worktree, validates: (1) every acceptance criteria / item DELIVERED in diff with file evidence, (2) unit/e2e tests exist matching behavioural names for expected behaviour, (3) required documentation is updated (AGENTS, README, runbooks, CLAUDE), (4) any NEW env var has corresponding declaration in infra/env parser (zod schema, .env.example, terraform/railway/vercel vars), (5) LEAN/KISS/YAGNI — overengineering scanner 12 categories L1-L12 + scope justifier, (6) FINAL SCORE 0-10 geometric mean of Scope x Lean. Invoked by /che-scope-check or as SHIP gate before PR draft (che-ship §0.9 GATES order 1)."
---

# Che — Scope Checker (6-check audit persona)

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
> - GitHub CLI gh auth + PR diff fetch: `../che-code-review/references/_shared_checklists/GITHUB_CLI_COMMON.md`
> - Stack auto-detection (test runners, doc files, env parsers): `../che-qa/references/_shared_checklists/NX_PNPM_COMMON.md`
> - Security/PII/RLS checklist: `../che-code-review/references/_shared_checklists/SECURITY_PII_COMMON.md`

Auditor persona with **2 mutually exclusive modes** (choose EXACTLY 1). **Always returns a structured report with per-line evidence and RULE 7.9 observable behaviour names.**

---

## 0. Preconditions — 2 modes + binding check

### 0.1 WORKTREE SESSION BINDING CHECK (engineering-contracts §19, NON-NEGOTIABLE)

Run BEFORE deciding the mode.

1. **Read Level 1 Global Index FIRST:** Read `che_registry_path`. Find LAST `STATUS=BOUND` entry using the effective session id from `che_current_session_id`. Use its `WORKTREE_ROOT` as the default session.
2. **Mode B mismatch check:** user passed `--worktree <path>` AND Level 1 registry WORKTREE_ROOT exists AND is DIFFERENT → BLOCK. Ask: "Scope check requested in `<path>` but Level 1 global registry BOUND in `<y>`. Options: (A) use `<path>` and override binding temporarily for this audit, (B) switch binding first, (C) cancel audit." **NEVER silent override.**
3. **Mode A PR URL binding conflict:** PR branch = worktree branch of an existing binding and user also passed `--worktree` pointing elsewhere → BLOCK. Ask which is the target.

### 0.2 How to decide which mode

- If user provides **BOTH PR URL AND --worktree** → prefer Mode A (PR URL). `--worktree` becomes an optional local path just for saving the report to disk.
- If user provides **`--worktree <path>` (or explicit worktree indicator) AND NO PR URL** → **FORCE Mode B (Local Worktree)**. DO NOT ask for PR URL.

---

### 0.3 Mandatory Scope Sources (1+ minimum; combination allowed; priority order)

NO scope source = ASK user. Do not proceed without scope.

| Order | Source | How to extract ACs/items |
|---|---|---|
| 1 | `--prd=/abs/path/prd.md` | Headings `## Acceptance Criteria`, `## ACs`, `## Goal`, `## Out of Scope`, bullets `* [ ]`, numbered list. |
| 2 | `--ticket=<Linear/Jira URL>` | Linear GraphQL `state,description,acceptanceCriteria,estimate,project,identifier,title,relationship:`; Jira REST `fields.summary,fields.description,fields.customfield_*_criteria`. |
| 3 | `--task-graph=/abs/path/task_graph.md` | All `## Task Tn` + status lines `[COMPLETED]` + subtasks bullets. |
| 4 | `--scope="free text"` | Split by bullets, numbered, or commas if inline list. |
| 5 | `PR body` (Mode A only) | Automatically extract AC sections, all `- [ ]` / `- [x]`, headings. |

Extraction produces a flat `AC[]` array = `{id: string, text: string, area?: string, oos?: boolean}`. OOS items = explicitly marked as out-of-scope DO NOT count as missing in the report.

### 0.4 SbE Spec AUTO-DETECTION (ONDA2 bilateral mode — if detected, runs MANDATORY §3.5 CHECK 2 EXTENSION)

Run AFTER §0.3 Scope Sources, BEFORE §1 Gather context.

**Input modes for bilateral SbE (any 1 = activates extension):**
1. User provides explicit flag: `--spec=/absolute/path/to/approved_spec.md`
2. Scope Source (PRD file / PR body / task graph) CONTAINS the literal heading `## §4 SPECIFICATION BY EXAMPLE` or `## §4.2 POSITIVE BEHAVIOR EXAMPLES`
3. Auto-scan workspace_shared specs: list `$CHE_WORKSPACE_SHARED/specs/<slug-matching-ticket-id>/*spec.md` files with `status: Approved` in frontmatter → if ONE match is FOUND, ask user: "Detected Approved SbE spec in <path>. Use as bilateral B-ID ↔ test ↔ diagrams scope? (Y/n)". Default = Yes.

**If SbE spec detected:**
- Set `SBE_SPEC_PATH = <absolute path>`
- Parse YAML frontmatter: extract `risk_level`, `b_count`, `ab_count`, `erd_required`, `mermaid_required`.
- Parse §4.2 Behavior Table: produces `SBE_BEHAVIORS[] = { b_id: "B-1", given: "...", when: "...", then_obs: "...", playwright_layer_checked: true|false, ui_selectors: ["id1","id2"]}`
- Parse §4.3 Anti-Behavior Table: produces `SBE_ANTI[] = { ab_id: "AB-1", ... }`
- Parse §4.4 Mermaid (if exists): produces `SBE_MERMAID_BIDS = set()` containing all `B-\d+` and `AB-\d+` extracted from nodes/edges of the 3 diagrams.
- **Control variable:** `SBE_EXTENSION_ENABLED = true`. If no method above → `false` and skips §3.5 (legacy mode).


---

## 1. Gather context — dependent mode

### Mode A (GitHub PR) → use `gh` CLI (NO browser)

```bash
gh pr view <PR_URL> --json \
  number,title,body,baseRefName,headRefName,additions,deletions,changedFiles,files
```

Record:
- `PR_ID`, `BASE_BRANCH`, `HEAD_BRANCH`
- `changedFiles_count`, diff stat
- `FILES[]` = changed files list + status (added/modified/deleted)
- `PR body` text → scope source #5 above

Full diff patches:
```bash
gh pr diff <PR_URL> > /tmp/pr-<id>-full.diff
```

### Mode B (Local Worktree) → git commands (no gh / no network)

All commands run INSIDE `<WORKTREE_ROOT>`. They never leave.

```bash
# Base branch detection (auto)
git remote show origin | grep 'HEAD branch' | awk '{print $NF}'  # default
# If ambiguous (main and dev exist and diff has both) → ASK user.

# Capture modified/staged/untracked files
git status --short                              # summary
git diff "$BASE_BRANCH"..HEAD --unified=3       # vs base (committed)
git diff --cached --unified=3                   # staged
git diff --unified=3                             # unstaged
cat /tmp/wt-full.diff                            # concat all above in 1 cumulative patch
```

Modification area empty check (WARN, not FAIL): if 0 files modified vs base, ask "continue auditing the entire repo vs scope or stop?"

---

## 2. CHECK 1 — 🔍 FULL SCOPE Delivery (every AC has file evidence)

### Step 2.1 — Parse ACs and keywords

For each `AC[i]`:
1. Canonical name RULE 7.9: `full_scope_delivery_for_ac_<slug>`
2. Extract **behavioural keywords** (business nouns + verbs) and **expected files/Areas** (heuristics: "auth" → `packages/auth/**`, "dashboard" → `**/dashboard/**`, "stripe" → stripe* files, "migration" → `**/migrations/**`, "README" → `README.md`, "AGENTS" → `**/AGENTS.md`).

### Step 2.2 — Map AC → diff file(s)

For each AC[i]:
- Match `behavioural keywords` against `full diff patch text` + changed paths.
- **Strong match:** `**/user-auth/**` path changed + words `login | session | JWT` appear in patch → 🟢 DELIVERED
- **Medium match:** path looks correct but content lacks keyword → 🟡 PARTIAL (explain what evidence was missing)
- **Weak match / none:** NOTHING in diff → 🔴 MISSING (point out which area + where code should be)
- **OOS items:** ⚪ SKIPPED (count for info, not for verdict)

### Step 2.3 — Per-AC report format

4-column table, RULE 7.9 NAMES:

| AC ID | Behavioural rule | Verdict | Evidence (file path:lines) |
|---|---|---|---|
| AC-1 | `full_scope_delivery_for_ac_login_google_oauth` | 🟢 DELIVERED | [auth.ts#L42-L88](file:///...) + [route.ts#L1-L40](file:///...) |
| AC-2 | `full_scope_delivery_for_ac_refund_stripe_connect` | 🟡 PARTIAL | [refund.ts#L20-L50](file:///...) implements api but **missing** connect account destination call |
| AC-3 | `full_scope_delivery_for_ac_qrcode_offline_scan` | 🔴 MISSING | No files in `packages/scanner/**` changed. Expected change in `scanner/lib/scan.ts` or `scanner/app/scan/page.tsx`. |

---

## 3. CHECK 2 — 🧪 TEST Coverage (unit/e2e cover expected behaviour)

### Step 3.1 — Auto-detect test stack

Same table as che-qa §1.4. Detects Vitest, Jest, Playwright, Cypress, pytest, cargo test, go test etc.

### Step 3.2 — Detect existing test files IN DIFF

From cumulative patch, filter:
- Files matching: `*.test.*`, `*.spec.*`, `**/__tests__/**`, `**/e2e/**`, `**/playwright/**/*.spec.*`, `*_test.go`, `tests/**/*.py`
- + NOT tests, but corresponding SUT (system under test) files.

### Step 3.3 — Map behavioural AC → describe()/it() behavioural names

RULE 7.9: Suite/test names MUST be observable behaviour. Poor names (FLO-123, test(), it1, shouldWork) do not count as evidence coverage.

**🔴 HARD RULE — PROHIBITED INVERSION: DO NOT PENALISE titles WITHOUT task-id:**
> ❌ **WRONG:** "Title does not have FLO-714 as prefix → invalid evidence / deduct points". **THIS IS A REGRESSION.**
> ✅ **CORRECT:** Title describes observable behaviour + DOES NOT have FLO/T/AC in the STRING → GOOD, compliant, counts as evidence.
>
> **What INVALIDATES evidence (bad):** title STRING contains anti-patterns `FLO-\d+` / `Task? T\d+` / `AC\d+` / `§\d+` / `SPEC_XXX`.
> **What VALIDATES evidence (good):** title contains AC keywords (behaviour verbs + nouns) + has no IDs. Traceability via `// @ac 2.1 | @ticket FLO-732` comment INSIDE the block = also GOOD and not penalised.

Reasoning per AC:
- For each behavioural AC like "user can apply stripe connect refund" → search tests for strings like: `refund`, `stripe connect`, `connected account`, `refund succeeded`, `refund failed`
- If it describes behaviour = 🟢 TESTED (even if it doesn't mention FLO/T/AC — it's the DESIRED behaviour)
- If there's a test file for the module BUT no case hits the AC keyword → 🟡 PARTIAL (which tests exist vs what specific behaviour is missing)
- If SUT was changed and ZERO test file changed for the area → 🔴 NOT TESTED (which behaviour, which test file to create)

### Step 3.4 — Report format

| Area / AC | Behavioural rule | Verdict | Evidence test (path:lines) |
|---|---|---|---|
| AC-1 refund | `unit_or_e2e_test_coverage_for_refund_connect_account` | 🟢 TESTED | [refund.test.ts#L102-L145](file:///...) it(`refunds_connected_account_destination_correctly`) |
| AC-2 qrcode offline | `unit_or_e2e_test_coverage_for_qrcode_offline_scan` | 🟡 PARTIAL | [scanner/scanner.test.ts#L5-L18](file:///…) suite exists, happy path online only. **Missing** offline case + cache fallback. |
| AC-3 login google | `unit_or_e2e_test_coverage_for_login_google_oauth_redirect` | 🔴 NOT TESTED | `packages/auth/src/google.ts` changed, NO `*.test.*` in `packages/auth/**` touched. Create `google-login.spec.ts` with cases: redirect_uri, state param, token exchange. |

### Step 3.5 — ⚡ CHECK 2 EXTENSION SbE BILATERAL ENFORCEMENT (3 sub-checks) — ONLY RUNS IF `SBE_EXTENSION_ENABLED = true` (§0.4)

> **ONDA2 bilateral verification loop pillar:** Spec §4 Behavior → Test anchor → Evidence SHA → Updated Spec §5. Scope-checker validates the reverse loop as well (which B-coverage vs reality).

**3.5.1 Bilateral 1/3 — Anchor @ac B-X → it() body coverage (traces each B-ID → real test file)**

Scanning rule:
1. **Anchor detection regex (exact che-code-review Category 7 G7.3):** `^\/\/\s*@(ac|ticket|task|bug)\s+(B-\d+|FLO-\d+|[A-Z]+-\d+)` — **MUST be the FIRST LINE INSIDE the `it(...) { ... }` or `test(...) { ... }` block**. Outside the block = DOES NOT count as bilateral evidence (could be a casual comment).
2. **Scan universe:** ALL test files detected in §3.2 (test/spec/__tests__/e2e/playwright files in diff) + corresponding SUTs if they have embedded tests. DO NOT scan entire repo — only current diff (blast radius).
3. **Anchor coverage calculation:**
   ```
   B_COUNT_SPEC = len(SBE_BEHAVIORS[])           // real §4.2 table
   B_COVERED_BY_ANCHOR = count(SBE_BEHAVIORS.b_id ∋ appears in at least 1 regex match)
   BILATERAL_ANCHOR_COVERAGE_PCT = B_COVERED_BY_ANCHOR ÷ max(1, B_COUNT_SPEC) × 100
   ```
4. **Severity / Verdict:**
   - **🔴 BLOCK (hard stop):** BILATERAL_ANCHOR_COVERAGE_PCT = 0% → NO SbE behaviour has bilateral anchor. **Require EXPLICIT_OVERRIDE_BILATERAL_SKIP with justification + decision.log entry.**
   - **🟡 WARN (action item):** BILATERAL_ANCHOR_COVERAGE_PCT < 70% OR ≥2 B-IDs missing individually even if global ≥70 → list missing B-IDs + expected test file(s) by keyword mapping.
   - **🟢 FULLY LINKED:** ≥70% AND <2 individual missing B-IDs → green. §7.1 bonus score applied if ≥90%.

**3.5.2 Bilateral 2/3 — SPEC §4.4 Mermaid B-ID refs set vs §4.2 real Behavior Table set (diagrams don't lie)**

> Common error in long specs: diagram gained B-11 but table only goes up to B-10 (orphan) OR table has B-3/B-4 but no diagram references even with mermaid_required=true.

Procedure:
1. Build sets:
   - `MERMAID_REF_SET = SBE_MERMAID_BIDS ∩ B` (B- only, ignore AB- for this check)
   - `TABLE_B_SET = { SBE_BEHAVIORS[].b_id }`
2. **Bidirectional diff:**
   - **Orphan refs (diagram has, table DOES NOT):** `MERMAID_REF_SET \ TABLE_B_SET` → WARN if non-empty. E.g.: "B-11, B-12 appear in sequenceDiagram but DO NOT exist in §4.2 Behavior Table — remove from diagram or add rows to table."
   - **Missing diagram refs (table has ≥2, NO diagram references):** (TABLE_B_SET \ MERMAID_REF_SET) ≥ 2 ENTRIES AND `mermaid_required === true` (frontmatter) → WARN. E.g.: "mermaid_required=true but table B-2, B-5, B-7 DO NOT appear in any of the 3 §4.4 diagrams — label nodes/edges with B-X to ensure bilaterality."
3. AB-IDs anti-behaviour in diagram is OPTIONAL by default; if frontmatter `ab_count ≥ 3` AND `erd_required=true` → soft WARN if 0 AB- in ERD (no block).

**3.5.3 Bilateral 3/3 — SPEC §4.4.3 ERDiagram ↔ Migration SQL + real TypeORM @Entity**

> **Hard gate only applies IF:** `erd_required === true` (frontmatter §0.4) AND diff has NEW/MODIFIED migration files (`**/migrations/*.sql`, `**/migrations/*.ts`) OR entity files (`*.entity.ts`, `@Entity()`). Otherwise → ⚪ N/A marked in summary.

Cross-check procedure:
1. **Does entity declared in ERD exist in code?** each entity name in erDiagram → grep `@Entity.*<name>` in diff. Missing → WARN "Entity `<X>` declared in ERD but TypeORM @Entity NOT found in diff."
2. **Do FK cardinality + ON DELETE rule match?** each FK in ERD (Mermaid cardinality `}|`/`o|` etc.) → cross-check with migration SQL `REFERENCES <target>(id) ON DELETE <CASCADE|SET NULL|RESTRICT|NO ACTION>` and with TypeORM `@ManyToOne({ onDelete: "CASCADE" })`. Cardinality or onDelete mismatch → WARN "ERD cardinality `Order }|--|{ OrderItem` differs from migration `ON DELETE RESTRICT` (CASCADE expected due to strong 1:N cardinality)."
3. **Do ERD declared constraints ≥3 really exist?** if ERD lists fields with `UK`/`CHECK`/`UNIQUE` explicitly → grep `ADD CONSTRAINT <name> UNIQUE` or `UNIQUE(col, col2)` or `@Index({ unique: true })` in diff. ≥1 constraint declared in ERD but missing in schema → WARN "UK `uk_order_stripe_pi_unique` exists in ERD but migration has no ADD CONSTRAINT nor unique @Index."
4. **Severity:** All ERD findings = **🟡 non-blocking WARN** by default (ERD is often "target state" and migration incremental). If ≥3 mismatches + high risk (wrong FK ON DELETE in payments/tickets table) → mark as upgrade: **🔴 BLOCK if 1 of the mismatches is FK cardinality of strong referential integrity (e.g. Order 1:N Ticket but ON DELETE CASCADE in Ticket would delete tickets when deleting Order — GDPR violation).**

---

#### §3.5 Report format — SbE Bilateral Extension (new, RULE 7.9)

| Anchor ID | Behavioural rule | Verdict | Evidence + Action item if 🟡/🔴 |
|---|---|---|---|
| SBE-B1 | `bilateral_anchor_coverage_for_spec_Behaviors_test_files` | 🟢 FULLY LINKED | 9/10 B-IDs have `// @ac B-X` on 1st line inside it() block. Coverage=90%. Files: [refundFlow.api.test.ts](file:///...) + [RefundService.unit.test.ts](file:///...). **+0.5 §7.1 SCOPE_score bonus applied.** |
| SBE-B2 | `bilateral_mermaid_bid_refs_real_table_behaviour` | 🟡 WARN ORPHAN | Orphan refs: `B-11` exists in §4.4.1 sequenceDiagram but has NO corresponding entry in Behavior Table. Add B-11 to table OR remove from diagram. Missing refs count = 0 (ok, mermaid_required=true). |
| SBE-B3 | `bilateral_erd_cardinalities_constraints_migration_and_typeorm` | 🟡 WARN MISMATCH | ERD `OrderItem → Order }|--|{` (ON DELETE CASCADE expected). Migration `20260415_refund.sql#L80` uses `ON DELETE RESTRICT`. Adjust migration to CASCADE (order without items = deleted without orphans risk). ERD declared UK `uk_refund_payment_id` → found in unique @Index ✅. |
| SBE-B2-alt | `(0% example — hard block)` | 🔴 BLOCK ZERO ANCHORS | 0/7 B-IDs have bilateral anchor. NO test file modified in this diff contains `// @ac B-X` pattern. Resolve: add anchors OR justified EXPLICIT_OVERRIDE_BILATERAL_SKIP + decision.log entry. |

---

## 4. CHECK 3 — 📘 UPDATED Documentation (AGENTS / README / runbooks / CLAUDE)

### 4.0 MANDATORY Pre-check (BEFORE using heuristics) — Relevance + Docstrings

This stage is NOT optional. Run on EVERY diff, even small ones.

| Mandatory Item | Question to answer (verification) | Verdict | Evidence |
|---|---|---|---|
| **Relevance Check 1** (engineering-contracts §22.1) | "Does this change alter public contract, new or changed commands, UX/UI, onboarding, architectural premises, deploy/runbook flows, or public APIs?" If YES → docs are mandatory. If NO → justify 1 line if diff >5 files or >150 lines. | 🟢 Answered | Justification line in decisions.log OR marked YES/NO in report |
| **Relevance Check 2** (engineering-contracts §22.1) | "Does a human or agent reading this code in 3 months benefit from an explanation?" If MAYBE or YES → docs are mandatory. | 🟢 Answered | Decision recorded in report |
| **Public Docstrings** (engineering-contracts §22.2) | Did diff add or change public functions/methods/classes, modules, difficult custom types? Does each new item have docstring/JSDoc/TSDoc with PURPOSE + intricate observations (NOT inputs/outputs if typed)? Intricate private functions should also have them. | 🟢 FULL / 🟡 PARTIAL / 🔴 ZERO | List files/fns missing docstring |

> **HARD FAIL:** If the 3 items above are NOT explicitly verified, CHECK 3 cannot be marked 🟢 under any circumstances.

### 4.1 Trigger heuristics (WHEN to document — after 4.0 pre-check)

| Change in diff | MANDATORY document to update |
|---|---|
| New `/commands/che-*.md` or `skills/*/SKILL.md` | **README.md §5 commands table** (count + new line) + top banner count. Optional: §6 cheatsheet if daily command. |
| New architecture premise, new hook, new contract | App or repo-level **AGENTS.md**, **CHE_RULES.md** if cross-cutting, **CLAUDE.md** |
| New environment variable (see also CHECK 4) | `.env.example` + README "env vars required" section + app-level config doc |
| New public endpoint / public API route / breaking change | **Package README**, docs/api/, **OpenAPI/Swagger** if any |
| Runbook changed, deploy command changed, new CI step | **`.github/workflows/*.yml` comments**, `docs/runbook-*.md` if any |
| Important architecture refactor | App-level **AGENTS.md** + decision log `docs/decisions.md` if any |

### 4.2 Step 4.2 — Cross-check .md/.yml diff against triggers

From cumulative patch:
1. List all changed `.md`, `.yml`, `.yaml`, `.json schema`, `.toml config`
2. For EACH applicable trigger, mark:
   - 🟢 DOCUMENTED if corresponding file appeared in diff and changed content matches trigger keyword
   - 🟡 PARTIAL if documented in only one place but missing another (e.g.: new skill was README §5 but missing top banner count)
   - 🔴 NOT DOCUMENTED if trigger applied and no doc was touched

### Step 4.3 — Report format, RULE 7.9 names

| Trigger / Item | Behavioural rule | Verdict | Evidence doc path |
|---|---|---|---|
| New `/che-scope-check` command added | `documentation_update_for_che_scope_check_command_in_readme_and_count` | 🟢 DOCUMENTED | [README.md#L244-L267](file:///...) §5 table line 18 + top banner updated count 17→18 |
| New `STRIPE_CONNECT_SECRET` env var (CHECK 4) | `documentation_update_for_stripe_connect_secret_env_var_in_dotenv_example_and_parser` | 🟡 PARTIAL | `.env.example` has the var but `packages/config/src/env.ts` zod schema DID NOT validate type (string required) |
| New offline scanner architecture | `documentation_update_for_offline_architecture_in_agents_md_and_claude_md` | 🔴 NOT DOCUMENTED | Diff changes 12 offline scanner files. `packages/scanner/AGENTS.md` + `CLAUDE.md` WITHOUT changes. Add §scanner offline architecture. |

---

## 5. CHECK 4 — 🔐 New environment variables = DECLARED in INFRA/ENV parser

### 5.1 Detect NEW env var usage in diff

Regex patterns (all languages, case-insensitive match whole words):
```
process\.env\.[A-Z0-9_]+
Deno\.env\.get\(["']([A-Z0-9_]+)
os\.environ\[["']([A-Z0-9_]+)
os\.getenv\(["']?([A-Z0-9_]+)
ENV\["?([A-Z0-9_]+)"?\]
env\(["']([A-Z0-9_]+)
z\.object\(\{\s*([A-Z0-9_]+)
```

Produces `ENV_USAGE[] = {var: string, file: path, line: n, lang: ts|py|rs|go|sh}`.

### 5.2 Cross-check with DECLARATIONS

Search in **ENTIRE REPO (not just diff)** for declarations of each ENV_USAGE[i]:

| Declaration type | Where to search |
|---|---|
| Zod schema env parser | `packages/config/src/env.ts`, `env.ts`, `config/env.ts`, `src/env/index.ts`, `app/env.ts`, next.config env |
| `.env.example`, `.env.local.sample`, `.env.dist` | repo root, apps/*, packages/* |
| Vercel (if project uses) | `vercel.json` env keys, OR Railway/Railway.tf |
| Terraform / AWS env | `*.tf` environment blocks, SSM parameter store names |
| Docker / K8s | `Dockerfile ENV`, k8s `ConfigMap`, `helm values.yaml` |
| CI GitHub Actions | `.github/workflows/*.yml` env blocks if CI only var |

Each NEW env var vs diff marked:
- 🟢 DECLARED: appears in ≥1 declaration **AND** (if zod schema) has validated type (z.string().min(1), z.number(), etc.)
- 🟡 WEAK DECLARATION: appears in .env.example BUT NOT in zod schema parser (no runtime validation). Or zod optional without default.
- 🔴 NOT DECLARED: No declaration found in repo. Point out: which var, what expected type, where to add (both packages/config/src/env.ts + .env.example)

### Step 5.3 — RULE 7.9 report format

| Variable | Behavioural rule | Verdict | Where to declare (if 🔴/🟡) |
|---|---|---|---|
| `ANALYTICS_S3_BUCKET` | `env_var_declaration_in_parser_for_analytics_s3_bucket` | 🟢 DECLARED | `packages/config/src/env.ts` z.string() + `.env.example` line 42 |
| `STRIPE_CONNECT_SECRET` | `env_var_declaration_in_parser_for_stripe_connect_secret` | 🟡 MISSING RUNTIME VALIDATION | `.env.example` line 37 OK. **Missing** `packages/config/src/env.ts` zod entry + default throw if absent in prod |
| `ETL_SENTRY_DSN` | `env_var_declaration_in_parser_for_etl_sentry_dsn` | 🔴 NOT DECLARED | Used in `etl/ingest.ts#L18` without declaration. Add in packages/config env schema zod.string().url() + .env.example. |

---

## 6. CHECK 5 — 🧩 LEAN / KISS / YAGNI — Overengineering Scanner (12 generic categories L1-L12 + 13 Ousterhout RED FLAGS Appendix D)

> **New pillar introduced 2026-09.** Combats LLM overengineering by default. Every line of new code must justify its existence against the explicit scope of the diff. NOT "clean code personal taste"; it is YAGNI + blast-radius reduction + reuse-before-create from engineering-contracts §1 §4.
>
> **Ousterhout integration (APoSD canonical Appendix D):** After running the 12 categories L1-L12, also apply the 13 RED FLAGS from Appendix D (D.1). Same finding format with same AC scope justifier downgrade. Default severity in scope-checker: HIGH (RF01-RF04), MEDIUM (RF05-RF13). Cross-reference with che-code-review findings in ship gate.

### 6.0 Pre-step — Automatic scope justifier (downgrade severity when abstraction is requested in scope)

Before applying the 12 categories, build:
- `SET_AC_SCOPED_KEYWORDS`: all behavioural keywords from CHECK 1 ACs that mention "extensibility / multiple backends / strategy / abstract X / replace Y with Z in the future" / items that EXPLICITLY request flexibility.
- For each L1-L12 finding:
  - IF finding matches ANY keyword in SET_AC_SCOPED_KEYWORDS → **DOWNGRADE 1 level of severity AUTOMATICALLY** (HIGH→MEDIUM, MEDIUM→LOW, LOW→INFO allowlisted in report). The abstraction was requested in the scope; it is not overengineering.
  - IF NOT matched → original severity.

### 6.1 Procedure per category — 12 mandatory checks

For EACH category below, apply steps on the cumulative diff (NEW + MODIFIED files, NOT entire repo).

| ID | Trigger (regex / heuristic) | Default severity | Detection procedure |
|---|---|---|---|
| L1 | Premature abstraction: Interface / abstract class with only 1 implementation | MEDIUM (HIGH if > 5 total indirections in same flow) | 1. List all new/modified interfaces: `interface\s+\w+` / `abstract class\s+\w+`. 2. For each, grep implementations: `implements\s+<InterfaceName>` / `extends\s+<AbstractName>`. 3. IF implementation count = 1 AND NOT an existing interface in repo history → flag L1. 4. Record: indirection path in call chain; if > 5 total interface/abstract hops → upgrade severity to HIGH. |
| L2 | Strategy / Factory / Dispatcher pattern with only 1 entry in switch/map | MEDIUM | 1. Find NEW `switch/case`, `Record<Enum, Handler>`, `Map<string, () => R>`. 2. Count effective entries (non-default cases / non-empty keys). 3. IF count = 1 AND NO TODO/FIXME attaching "next we add second strategy" → flag L2. |
| L3 | Wrapper/builder around lib with 1 method and zero extra logic | LOW (MEDIUM if > 3 wrapper files in same diff) | 1. Find NEW classes/funcs that only call lib deps directly: method body = just `return lib.f(args)` without validation/cache/retry/error mapping. 2. Name contains "Factory", "Wrapper", "Client", "Provider" but without extra implementation. 3. IF ≥ 3 of these in same diff → upgrade to MEDIUM. |
| L4 | createX() factory with body = 1 line return new ConcreteX() without any if/switch | LOW | 1. Grep `function\s+create\w+\s*\([^)]*\)\s*\{` / `static\s+create\w+\s*\(`. 2. Body AST/syntax = `return new <ConcreteClass>(same params without change)`. 3. Zero conditionals, zero fallback, zero cache. → flag L4. |
| L5 | Helper/utility with 1 SINGLE use in entire codebase | LOW (MEDIUM if > 20 helper lines) | 1. For each new EXPORTED function/const in `utils.*`, `helpers.*`, `*util*`: grep name. 2. Occurrence count = 2 (declaration + 1 use) OR 1 if default export. 3. IF body > 20 lines → upgrade to MEDIUM. |
| L6 | Env VAR declared in .env.example BUT NEVER read in code with process.env etc | HIGH if credential/secret; MEDIUM if feature flag/toggle | 1. List new vars in .env.example in diff. 2. For each VAR: grep `process.env.<VAR>` / Deno.env.get / os.environ / ENV[var] in ENTIRE REPO (not just diff, as it might be used in unchanged file). 3. ZERO matches → flag L6. Credentials = name contains (KEY/SECRET/TOKEN/DSN/PASSWORD/AUTH) → HIGH; rest MEDIUM. |
| L7 | React useHook/custom component ≤ 2 lines, called once | LOW | 1. NEW React hooks: `function use\w+` → body lines ≤ 2. 2. NEW Component: `export default function \w+` with JSX ≤ 2 lines and no children/props beyond hardcode. 3. Grep name finds exactly 1 call site (outside declaration file). → flag L7. |
| L8 | Generic `<T>` / Type parameter used for only 1 concrete type in all call sites | LOW | 1. Find NEW `function\s+\w+\s*<T[^>]*>` / `class\s+\w+\s*<T[^>]*>`. 2. Grep all call sites in diff + entire repo. 3. All pass EXACT SAME type (e.g.: all `invoke<Refund>` without any other variation). → flag L8. |
| L9 | Chain ≥ 3 indirection hops without real value (X → Y → Z → real db/network op) | MEDIUM (HIGH if 1 hop has lock tx held over network — che-code-review Category 0.3 cross-ref) | 1. For each public entrypoint (router handler / tRPC procedure / controller): trace call chain to real side effect (DB read/write / HTTP / FS). 2. ≥ 3 functions/class.methods in middle that ONLY pass args (zero validation/transform/branching). 3. If any stage has queryRunner START TRANSACTION FOR UPDATE not yet released and hop does await fetch/stripe → upgrade HIGH (same C0.3 code-review finding; linked). → flag L9. |
| L10 | Dead code comment-out / `// TODO` without #ticket number / `FIXME` without reference | MEDIUM if TODO/FIXME without ticket; LOW for commented dead code | 1. Regex `/\/\/\s*TODO(?!\s*[:(]?\s*[A-Z]{2,}-?\d+)/` (TODO without ticket). 2. Regex `\/\*[\s\S]*?\*\/` commented blocks with syntactically valid code (not docstring). 3. Commented blocks + TODO without id → flag L10. |
| L11 | Function parameter that ALL diff call sites pass the SAME hardcoded value | MEDIUM | 1. For each new/modified exported function: list params. 2. For each non-trivial param that is not last: grep all call sites in diff. 3. 100% of calls pass exact same literal value (e.g.: all `fn(..., "gbp")`). 4. No call site uses another value. → flag L11. |
| L12 | Lookup table / Record / Config table with only 1 ENTRY | LOW (except if 1 entry + >30 lines total block → MEDIUM) | 1. Regex `=\s*\{\s*\w+\s*:\s*` + close brace in < 5 lines AFTER → only 1 key. 2. `Record<K,V>` + initialization only 1 key. 3. No other key added in other diff files. → flag L12. |

### 6.2 CHECK 5 report format — 4-column RULE 7.9 table

| ID | Behavioural rule (verb_object_for_target) | Severity (after scope downgrade) | Evidence (path:lines) + Scope justifier if applied |
|---|---|---|---|
| L1 | `overengineering_interface_with_only_1_implementation_refund_repository` | MEDIUM | [RefundRepository.ts#L5-L30](file://...) IRefundRepository. No AC requests multiple backends. |
| L6 | `env_var_declared_without_usage_refund_timeout_ms` | MEDIUM | [.env.example#L41](file://...) REFUND_TIMEOUT_MS=3000. ZERO process.env.REFUND_TIMEOUT_MS occurrences in code. |
| L11 | `parameter_same_value_all_calls_currency_refund` | INFO allowlisted | [refundService.ts#L18](file://...) issueRefund(currency). Scope AC-1 said "single GBP currency for now". LOW→INFO downgrade applied. |

---

## 7. CHECK 6 — 🧮 FINAL SCORE 0-10 (geometric mean of Scope × Lean)

> **Canonical blocking gate used by che-ship §0.9.1. Combines delivery and lean quality into a comparable number.**

### 7.1 SCOPE sub-score calculation (0-10)

Use CHECK 1 table verdicts:
```
TOTAL_ACs          = (DELIVERED+PARTIAL+MISSING)   (OOS NOT counted)
DELIVERED_weighted = count(🟢 DELIVERED)
PARTIAL_weighted   = count(🟡 PARTIAL) × 0.5
SCOPE_score = 10 × (DELIVERED_weighted + PARTIAL_weighted) / max(1, TOTAL_ACs)
```

**⚡ SbE Bilateral Anchor Coverage adjustment (ONDA2 — only applies if SBE_EXTENSION_ENABLED=true):**
```
# §3.5.1 coverage (already calculated)
BILATERAL_ANCHOR_COVERAGE_PCT = (B_COVERED_BY_ANCHOR ÷ max(1, B_COUNT_SPEC)) × 100
if (BILATERAL_ANCHOR_COVERAGE_PCT >= 90):
    SCOPE_score = clamp(SCOPE_score + 0.5, 0, 10)   # Strong bilateral BONUS
elif (BILATERAL_ANCHOR_COVERAGE_PCT < 70 AND BILATERAL_ANCHOR_COVERAGE_PCT > 0):
    SCOPE_score = clamp(SCOPE_score - 1.0, 0, 10)   # Weak coverage PENALTY
# 0% anchors = BLOCK regardless of score (§8.1 verdict has 🔴 check item)
```

Example: 8🟢 + 1🟡 + 1🔴 → base SCOPE = 10 × (8 + 0.5)/10 = **8.5**
With 92% bilateral anchor coverage (SbE ON) → adjusted SCOPE = clamp(8.5 + 0.5, 0, 10) = **9.0**

### 7.2 LEAN sub-score calculation (0-10)

Use CHECK 5 findings severities:
```
LEAN_penalty =
    (count(🔴 HIGH_check5) × 2)
  + (count(🟡 MEDIUM_check5) × 1)
  + (count(🔵 LOW_check5) × 0.3)
LEAN_score = clamp(10 − LEAN_penalty ÷ 2, 0, 10)
```
Example: 1 HIGH + 5 MEDIUM + 7 LOW → penalty = 2 + 5 + 2.1 = 9.1 ÷ 2 = 4.55 → LEAN = 10 − 4.55 = **5.45**

### 7.3 FINAL Score (geometric mean — requires BOTH to be good)

```
FINAL_score = sqrt(SCOPE_score × LEAN_score)
```
Example: sqrt(8.5 × 5.45) = sqrt(46.3) = **6.80**

### 7.4 FINAL CLASSIFICATION rule used in gate

| FINAL_score threshold | Level | che-ship §0.9 Action |
|---|---|---|
| **≥ 9.0** | Excellent | Green + auto-proceed |
| **≥ 7.0** | Acceptable | Green + auto-proceed (DEFAULT THRESHOLD) |
| **5.0 – 6.9** | Attention | 🟡 CONDITIONS → show L-M action items → ask user to proceed? |
| **< 5.0** | Poor | 🔴 BLOCK SHIP → fix first |

In addition to the numerical score, **IF there is ANY 🔴 item in ANY of the 4 legacy checks (1-4), the final verdict automatically drops to 🔴 BLOCKED**, regardless of the score. This is the old §6.1 rule, preserved.

---

## 8. 🎯 Final Verdict + aggregated report (UPDATED 2026-09 for 6 checks)

### 8.1 Calculation rule

```
Verdict =
  🔴 BLOCKED  if (ANY check has ≥1 🔴 item)  OR  (FINAL_score < 5.0)
  🟡 CONDITIONS if (NO check has 🔴)  and  (ANY item has 🟡)  OR  (5.0 ≤ FINAL_score < 7.0)
  🟢 APPROVED if (FINAL_score ≥ 7.0) AND (ALL items are 🟢/⚪/INFO) AND (ZERO 🔴 items)
```

### 8.1 🔴 MANDATORY STORAGE PREFLIGHT (BEFORE WRITING REPORT)

> engineering-contracts §20 MORATORIUM: No assets in worktree. Everything in che-sessions via unique helper.

Run EXACTLY this block BEFORE constructing any path:
```bash
CHE_HOME="${CHE_HOME:-$HOME/.trae}"
CONTRACT="$CHE_HOME/contracts/che_sessions_contract.sh"
[ -f "$CONTRACT" ] && source "$CONTRACT" || { echo "❌ Contract $CONTRACT missing — exit 98"; exit 98; }
SESSION_ID="${CHE_CURRENT_SESSION_ID:-fallback-scope-session}"
if [ -n "${WORKTREE_ROOT:-}" ] && [ -d "$WORKTREE_ROOT" ]; then
  che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
  che_ensure_session_dirs "$WORKTREE_ROOT"
fi
```

### 8.2 Output header + report saved at

**Build path with helper — NEVER manual:**
```bash
# SCOPE = workspace-shared (durable, reusable in future sessions of this worktree)
# related_id = review slug (e.g.: pr-382 or feat-FLO-714 or task-T1)
SCOPE_CHECK_PATH="$(che_output_path "scope_check" "scope-check" "<related_id>" "workspace" "md")"
```
Example result: `$CHE_WORKSPACE_SHARED/scope_check/pr-382/20260902-140000-scope-check.md`
→ UTC timestamp in prefix = automatic sorting; related_id groups all scope-checks for the same entity.

First page of report (always at the TOP):

```markdown
# 🔍 Scope Check — <slug>

## 0. Meta
- **Scope source:** (PRD path / ticket URL / task-graph / scope free-text / PR body) — pick all that were used
- **Mode:** A=GitHub PR #<id> (url) | B=Local Worktree <path> vs base <branch>
- **Diff:** N files changed / +X additions / -Y deletions
- **Final Score 0-10:** `<FINAL>` (SCOPE: `<SCOPE>` · LEAN: `<LEAN>`)

## 1. SUMMARY Verdict 6+1 checks (SbE extension added ONDA2)

| # | Check | 🟢 | 🟡 | 🔴 | ⚪ |
|---|---|---|---|---|---|
| 1 | 🔍 Full scope delivery | 8 | 1 | 1 | 2 OOS |
| 2 | 🧪 Unit/e2e test coverage | 6 | 2 | 1 | 0 |
| 2-ext | ⚡ Bilateral SbE (anchors + diagrams + ERD) | 2 rows ok | 1 ERD mismatch | 0 | 1 N/A erd_required=false |
| 3 | 📘 Updated docs | 3 | 1 | 0 | 5 N/A |
| 4 | 🔐 Declared new env vars | 1 | 1 | 1 | 0 |
| 5 | 🧩 Lean/YAGNI Overengineering | — | 5 L (MED) | 1 H (L6) | 7 allowlisted |
| 6 | 🧮 Final Score 0-10 | **6.80** | 7.0 threshold | — | — |

**👉 Final Verdict:** 🔴 BLOCKED / 🟡 CONDITIONS / 🟢 APPROVED

## 2. Action items (sorted 🔴 first)
1. 🔴 [Check 1, AC-3] Deliver offline qrcode scanner in scanner/lib/scan.ts (#L40-L120 expected)
2. 🔴 [Check 2, AC-3] Create scanner.spec.ts for offline cache fallback case
3. 🔴 [Check 4] Declare ETL_SENTRY_DSN in packages/config zod + .env.example
4. 🔴 [Check 5 L6] Remove REFUND_TIMEOUT_MS env from .env.example or add real code usage
5. 🟡 [Check 1, AC-2] Add destination stripe connect API call in refund.ts
6. 🟡 [Check 3] Validate STRIPE_CONNECT_SECRET zod runtime in env parser
...

↓ Details of each check in §2..§7 (4-column tables, RULE 7.9 names)
```

At the end of the report: **how to fix quickly** for next audit to pass (1-2 commands or 1-2 files).

---

## 7. RULE 7.9 NAMING (enforced throughout report)

NOT allowed ANYWHERE in the report:
- ❌ `good_quality`, `works`, `well_implemented`, `sufficient_coverage`
- ❌ `AC-FLO-732-delivered`, `§4.2 reviewed`, `FLO-513 passing`
- ✅ **MANDATORY:** `<verb_object>_for_<behavioural_target>` in ALL rules of the 4 check tables.

E.g.:
```
full_scope_delivery_for_<ac_slug>
unit_or_e2e_test_coverage_for_<behaviour>
documentation_update_for_<change>_in_<doc>
env_var_declaration_in_parser_for_<VAR_NAME>
```

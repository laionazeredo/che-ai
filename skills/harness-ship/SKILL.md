---
name: "harness-ship"
description: "End-of-task ship command: atomic conventional commits on worktree, git push (creates remote branch if missing), opens DRAFT PR against default branch with structured description, assigns PR to user. Invoke ONLY after all harness tasks DONE + compliance heavy passed, or when user explicitly runs /harness-ship."
---

# Harness — Ship (commit + push + open PR)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Conventional Commits full types + regex + examples: engineering-contracts skill Appendix B
> - GitHub CLI gh auth + push + create PR commands: `_shared_checklists/GITHUB_CLI_COMMON.md`
> - gh-stack hierarchical PR workflow (multi-PR partial deliveries): engineering-contracts Appendix C
> - Light pre-ship security check: `_shared_checklists/SECURITY_PII_COMMON.md` (secrets leak, PII log scan)
> - QA run order local verification: `_shared_checklists/NX_PNPM_COMMON.md`

This skill handles the end-of-development workflow for a worktree.
It runs ONLY after the user says "I believe everything is OK" and is prepared to commit.

---

## 0. Preconditions — Non-negotiable (FAIL if any missing)

1. **Worktree confirmed.** Absolute path provided. If not — block.
2. **`gh` CLI is available and authenticated.** Run `gh auth status` silently. If not authenticated → guide user to `gh auth login` and stop.
3. **Worktree has uncommitted changes OR new commits ready to push.** `git status` is not clean OR branch is behind/ahead.
4. No uncommitted `.env` / secret files being committed.
5. (If the user ran via harness) all tasks are marked DONE in `task_graph.md` + compliance heavy report has 0 CRITICAL 0 HIGH.
   If harness skipped these gates: log to decision.log the user's explicit override.

If any precondition fails → report exactly which, stop execution, ask user.

### 0.6 gh-stack mode detection (N4 hierarchical PR stack)

1. Check if file exists: `$HARNESS_WORKSPACE_SHARED/gh_stack_plan.md` (via `source ~/.trae/contracts/harness_sessions_contract.sh`).
2. If it exists:
   - Read it. Validate it has a field `Status: APPROVED` at the top.
   - Check `gh` extension installed: run `gh extension list 2>/dev/null | grep -i "stack"` silently.
   - If gh-stack extension NOT installed → offer `gh extension install https://github.com/github/gh-stack` to user; wait for confirmation, install, then continue. If user declines → FALLBACK to single-PR mode (Steps 2–5 normal path).
   - Parse layers table bottom-up (first layer = lowest in the stack, merged first; last layer = top of stack). Extract per layer: `Layer ID`, `Branch Name` (slug like `PROJ-123-l1-refund-pipeline`), `Scope (files)`, `Depends on`.
   - Set boolean: `GH_STACK_MODE=true`. Record `LAYERS[]` array ordered bottom-up.
3. If file NOT exists OR status ≠ APPROVED → `GH_STACK_MODE=false`. Proceed with standard single-PR path (Steps 2–5 current).

### 0.7 WORKTREE SESSION BINDING PREFLIGHT (engineering-contracts §19, NON-NEGOTIABLE)

Run BEFORE any `git status / git add / git commit / git push`. PREVENTS wrong-worktree commits.

1. **Level 1 Global Index (AUTHORITY):** Read `$HOME/.trae/bindings/registry.jsonl`. Find LAST STATUS=BOUND entry for current `SESSION_ID`. Extract WORKTREE_ROOT from that entry.
   - If NO entry: SHIP BLOCKED NOW. Ask "No Level1 binding for this session. Create before ship? (A = Select worktree; B = Cancel ship)." NEVER ship unbound.
   - If found BOUND entry: confirm WORKTREE_ROOT from registry **MUST EQUAL** WORKTREE_ROOT precondition 1.
   - MISMATCH → **BLOCK SHIP NOW.** Ask: "Level 1 GLOBAL registry binding says worktree = X, ship was invoked on Y. Which one actually ships? (A = X per binding; B = Y override binding + rebind; C = Cancel ship)." Never silent-continue.
2. **Level 2 Detail File (optional audit):** Verify `$HARNESS_SESSION_DIR/binding.md` exists (via `source ~/.trae/contracts/harness_sessions_contract.sh`). If missing → warn decision.log entry (SM skipped Level 2 write). Do NOT block ship (Level 1 is the authority).
3. **Scissor check staging + file ops:**
   - EVERY file staged/committed → path MUST start with WORKTREE_ROOT from Level1 registry.
   - Generated files under `$HARNESS_SESSIONS_ROOT/**` are NEVER staged; they live outside user code by design.
   - File path outside WORKTREE_ROOT and not under HARNESS_SESSIONS_ROOT (symlinks, relative tricks, etc.) → UNSTAGE immediately, report, DO NOT commit.
4. **Cross-worktree safety during ship loop (gh-stack mode):**
   - After finishing layer's commit/push/PR, NEXT layer file ops → RE-RUN scissor check (3) against BOUND WORKTREE_ROOT registry entry.
   - Never silent cd another worktree during multi-layer ship. Layer says "use worktree B" → STOP. Ask user confirm re-binding §19.3 (old entry STATUS=RELEASED append new BOUND registry entry) before switching.

---

### 0.8 PLANNING ARTIFACTS BLACKLIST PREFLIGHT (NON-NEGOTIABLE)

**Purpose:** NEVER allow harness internal planning/decision files to end up in user-code PRs. These files MUST live under `$HARNESS_SESSIONS_ROOT/<workspace>/<worktree-slug>/workspace` (contracts/harness_sessions_contract.sh L9-L21). If any bug/legacy skill accidentally creates them inside the user worktree, detect, unstage, and DELETE them before any `git add` runs.

Source of truth of patterns = `~/.trae/contracts/harness-planning-artifacts-blacklist.gitignore` (single list — keep in sync across install-harness.sh §5.5 injection, .gitignore do harness, e este preflight).

**BLACKLIST (any depth inside WORKTREE_ROOT):**
```
.trae/**                                 (legacy layout: never inside user code)
decisions.log.jsonl  decisions.log.md  decisions.log
decision.log.jsonl   decision.log.md   decision.log
task_graph.md manual_test_plan.md final_summary.md
execution_batches.md batch_execution_report.md
merge_audit.md merge_audit.jsonl
scope-report.md scope-report.json scope_check_report.md scope_check_report.json
spec_*.md gh_stack_plan.md session.md envelope.md task_envelope.md
graphify-out/**
**/qa_evidence/** **/manual-test-screenshots/**
harness-review-report.md harness-compliance-report.md flockr-review-report.md
```

**Runs INSIDE $WORKTREE_ROOT, in this exact order:**

1. **Find all matching files (tracked OR untracked):** use find + patterns acima | sort -u. Call list `<FOUND_BLACKLIST>`.
2. **STAGE 1 — Unstage anything staged (ALWAYS):**
   ```bash
   cd "$WORKTREE_ROOT" && [ -n "<FOUND_BLACKLIST>" ] && git reset HEAD -- <FOUND_BLACKLIST> 2>/dev/null || true
   ```
3. **STAGE 2 — Delete UNTRACKED blacklist files (they never belong here):**
   - For each `f` in `<FOUND_BLACKLIST>` where `git ls-files --error-unmatch "$f"` exits non-zero → UNTRACKED.
   - **DELETE them.** Backup copy preserved FIRST to `$HARNESS_WORKSPACE_SHARED/artifact_cleanup_backup/<ISO-date>/` just in case, then `rm -f <file>`.
4. **STAGE 3 — TRACKED blacklist files = BLOCK SHIP, ask user.** They were committed by an older harness bug and are now in git history. Present EXACT options:
   ```
   🔴 PLANNING ARTIFACTS BLACKLIST — TRACKED FILES FOUND (committed before):
     · <path1>
     · <path2>
   These are harness internal files (decisions / task_graph / manual_test_plan / spec_*.md etc)
   and MUST NOT live in user-code git history.

   Options:
     A = Untrack them (git rm --cached each), KEEP local copies MOVED to
         $HARNESS_WORKSPACE_SHARED/legacy_artifact_backup/<basename>  (RECOMMENDED)
     B = I will handle manually. Cancel ship.
   ```
   If A → move file to backup dir → `git rm --cached <path>` → proceed.
   If B → abort ship cleanly, 0 exit.
5. **POST-CHECK:** Re-run find. Re-run `git status --porcelain --untracked-files=no`. ZERO blacklisted files must remain STAGED. If any remain → BLOCK SHIP.
6. **DECISION LOG:** Append 1 single `ARTIFACT_CLEANUP` entry to `$HARNESS_DECISIONS_LOG` with list of files auto-unstaged / auto-deleted / untracked.

---

## 1. STEP 1 — Git Housekeeping (inside WORKTREE_ROOT)

### 1.1 Git sanitization check (secret scan pre-commit, extra)

Run a quick grep BEFORE staging anything (use harness-compliance skill Category 1 + 2 patterns on the DIFF against default branch).
If any matches → block, report, offer to unstage / remove the problematic file, do NOT proceed.

### 1.2 Determine the following

Run these one by one and record results:
- **Current branch**: `git branch --show-current` → `<BRANCH_NAME>`
- **Default remote branch**: `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name` → usually `main` or `master`. Call it `<DEFAULT_BRANCH>`.
- **Remote tracking branch exists?**: `git ls-remote --heads origin <BRANCH_NAME>` → empty = does not exist yet; we'll create on push.
- **Staged vs unstaged files**: list both

### 1.3 Worktree path absolute guard

If any git command runs and it turns out the current directory is NOT the provided worktree root → fail immediately, do not run any commit/push against wrong directory.

---

## 2. STEP 2 — Build atomic conventional commits

This is the user's requested default: conventional commits + atomic.

### 2.1 Generate proposed commit plan

Look at the diff. `git diff --name-only <DEFAULT_BRANCH>...HEAD` (or vs staged).

**BLACKLIST FILTER — ALWAYS run BEFORE grouping:**
From the diff-name-only output, REMOVE all files matching the patterns in §0.8 BLACKLIST (`.trae/**`, `decisions.log*`, `decision.log*`, `task_graph.md`, `manual_test_plan.md`, `final_summary.md`, `execution_batches.md`, `batch_execution_report.md`, `merge_audit.*`, `scope-report.*`, `scope_check_report.*`, `spec_*.md`, `gh_stack_plan.md`, `session.md`, `envelope.md`, `task_envelope.md`, `graphify-out/**`, `*review-report.md`).
- If any of those files appear in the diff → §0.8 preflight SHOULD have cleaned them already. If still present → **DO NOT ADD TO ANY COMMIT.** Skip silently and add 1 note at the bottom of the commit plan: "Note: N planning-artifact files auto-skipped (never committed)."

Group the remaining (filtered) changes into atomic, logical commits:

- **feat(scope):** new functionality, new endpoints, new UI components
- **fix(scope):** bug fixes — include "Fixes #TICKET" if applicable
- **refactor(scope):** code move, rename, no behavior change
- **test(scope):** spec files, e2e, fixtures only
- **docs(scope):** markdown, README, docstrings, no runtime
- **chore(scope):** deps bump, config, CI file changes, migrations
- **perf(scope):** perf improvements with measurable impact
- **build(scope):** build scripts, nx config, package.json
- **style(scope):** Biome/format, indentation, CSS-only cosmetic
- **ci(scope):** GitHub Actions, workflows
- **revert(scope):** reverts prior commit

Rule for grouping:
- If a change can stand alone (migration separate from runtime code that uses it) → separate commits.
- Tests for a feature go WITH the feature commit, not in separate, unless the feature is already merged.
- Migrations: usually `chore(db): add migration for X` separate commit.
- Max 15 commits per ship. If > 15 → offer user option to squash into fewer + plan, or proceed with 15+.

Present commit plan to the user as a **numbered list**, in order of application. Add the "N planning artifacts skipped" note at the bottom if applicable.
Wait for explicit user APPROVAL before running any `git commit`.

### 2.2 Execution — apply the commits (AFTER USER APPROVES plan)

Run each commit:
```
# BEFORE every commit: unstage ANY blacklisted files that somehow re-entered the index.
git reset HEAD -- \
  .trae  decisions.log.jsonl  decisions.log.md  decisions.log \
        decision.log.jsonl   decision.log.md   decision.log \
  task_graph.md manual_test_plan.md final_summary.md \
  execution_batches.md batch_execution_report.md \
  merge_audit.md merge_audit.jsonl \
  scope-report.md scope-report.json scope_check_report.md scope_check_report.json \
  spec_*.md gh_stack_plan.md session.md envelope.md task_envelope.md \
  graphify-out harness-review-report.md harness-compliance-report.md flockr-review-report.md \
  2>/dev/null || true

git add <files for this commit>
git commit -m "type(scope): imperative description in English, lowercase, max 72 chars"
```
Rules:
- NEVER run `git add .` — always add per-file or per-directory explicitly.
- Before EVERY `git add`, run the `git reset HEAD -- <blacklist patterns>` line above. (Fail-closed — cost 1 ms per commit, prevents a whole class of PR-pollution bugs.)
- Every commit message in ENGLISH, strict conventional commit.
- After last commit → run `git log --oneline -20` to present final chain to user.
- **POST-COMMIT ASSERT (after all commits applied):** `git show --name-only --pretty=format: HEAD~10..HEAD` → scan file names for §0.8 blacklist patterns. If any commit contains a blacklisted file → **STOP, DO NOT PUSH.** Report to user, offer `git reset HEAD~N` + re-apply cleanly, then continue.

### 2.3 GH_STACK_MODE=true — Group commits PER LAYER (bottom-up)

**ONLY run when `GH_STACK_MODE=true`. Overrides 2.1/2.2 default flat plan; standard flat commits become per-layer grouped commits.**

For each layer `L[i]` in `LAYERS[]` (bottom-up order, starting with the lowest stack layer):

1. **Checkout / create layer branch**:
   ```bash
   git checkout -b <L[i].BranchName>   # if branch doesn't exist locally yet
   # or: git checkout <L[i].BranchName>  # if already exists
   ```
2. **Cherry-pick OR stage only files in layer scope**:
   - Strategy A (preferred when commit plan already aligns): cherry-pick only the commits relevant to this layer onto this branch from the consolidated work branch.
   - Strategy B (simpler fallback — use when scope-per-layer is clearly file-based): from worktree state, **FIRST run `git reset HEAD -- <blacklist patterns>` (same as §2.2)** then `git add <only files matching L[i].Scope (files)>`, then create 1 or more conventional commits scoped EXCLUSIVELY to this layer (no cross-layer files in same commit).
3. Present plan of "branch → commits → scope" to user as numbered list. **Wait for explicit user APPROVAL before applying any layer commit.**
4. After user approves: apply commits per layer. Record per-layer: final commit SHAs.
5. After all layers done: present to user summary "Layers bottom-up (N layers): L1 → 2 commits; L2 → 3 commits; L3 → 1 commit" etc.

Rule invariant for GH_STACK_MODE commits:
- **Every file in a given layer's commit MUST be listed in L[i].Scope (files).** If a file belongs to layer L[i+1] it MUST NOT appear in commits of L[i]. Any cross-layer file → block, ask user which layer gets it.
- **Additional GH-stack invariant:** Zero files from §0.8 BLACKLIST allowed in ANY layer's commit. If after building layer the index contains a blacklist file → `git reset HEAD -- <file>` and warn.

---

## 3. STEP 3 — Push with `--no-verify`

User's rule: default to `--no-verify` for push.

### Path A: GH_STACK_MODE=false (single branch, standard)

```bash
# Case 1: remote branch does NOT exist yet
git push --no-verify --set-upstream origin <BRANCH_NAME>

# Case 2: remote branch already exists (ahead/behind)
git push --no-verify
```

Wait for success. If push fails:
- Non-fast-forward → ask user: rebase or force push? NEVER force push without explicit confirmation.
- Auth failure → stop.

### Path B: GH_STACK_MODE=true (push each layer bottom-up)

Loop layers in bottom-up order:

For each layer `L[i]` in `LAYERS[]`:
```bash
git checkout <L[i].BranchName>
# Case 1: remote branch doesn't exist
git push --no-verify --set-upstream origin <L[i].BranchName>
# Case 2: remote branch exists
git push --no-verify
```

Push failure rule same as Path A (per layer; block on first failure, don't continue to upper layers).

---

## 4. STEP 4 — Open DRAFT PR(s) against default branch

### Common Step: 4.0 Detect Linear/Jira ticket reference (both paths)

Look in:
- `.trae/<task-id>/session.md` for field "Ticket URL/ID"
- Branch name pattern: `feat/PROJ-123-login`, `fix/PROJ-456`, `ticket PROJ-123` anywhere in session/task_graph/envelope files
- User command args: `/harness-ship ticket:PROJ-123`

If found ticket: extract `<TICKET-ID>` (full URL or just ID). Append `Refs: <TICKET-ID>` footer to EVERY PR body (single OR all layers in stack).

---

### Path A: GH_STACK_MODE=false (single PR, standard)

#### A-4.2 Build PR Description — READABLE 5 BLOCKS (ENGLISH by default, ≤50 lines TOTAL target)

> **Canonical body + FILLED real EXAMPLE (refund feature from screenshot, low-context readable version):** `references/PR_DESCRIPTION_TEMPLATE.md` (Layer 3 SOLE owner of structure/content + readability rules). Below only process gates + budget.
> **Copy the STYLE of the filled example in PR_DESCRIPTION_TEMPLATE.md, not only the section names.** The filled example shows exactly how to phrase bullets, acronym expansion, user impact, and risk consequence.

**LANGUAGE GATE (non-negotiable — #1 rule, before any writing):**
- **DEFAULT = ENGLISH (EN-US / EN-UK).** Write the ENTIRE PR body, headings, bullets, ticket refs, commands — EVERYTHING — in English.
- **Other language ONLY IF:** the user's message that invoked `/harness-ship` (or the explicit instruction) contains an EXPLICIT request for another language (e.g., "write PR body in Portuguese", "corpo PR em PT-BR").
- **Never guess / NEVER assume** "user speaks Portuguese so PR in Portuguese". Portuguese is for chat ONLY. Absent an explicit mention → PR body is ALWAYS English.

**PROCESS GATES (non-negotiable — readable for low-context reviewers, trim only the useless, never the clear context):**

1. **Block 1 — What was implemented:** bullets only, 3–8 items. No paragraphs. **MANDATORY pattern per bullet:** `feat|fix|chore(scope): <WHAT changed in plain English>. <1 short sentence WHY / end-user impact>.` **READABILITY sub-rules (from template §RULES 1-3):**
   - **Acronyms expanded on FIRST use** inside the bullet (example: "RLS (Row-Level Security — Postgres access control)"). After first use → acronym alone is OK.
   - **Avoid concatenating 5–10 micro-changes into 1 monster bullet.** Each `feat(scope)` line = ONE self-contained area (DB schema / entity / service / Stripe / API / UI / tests — 1 bullet each, not 8 changes jammed).
   - **Internal jargon gets ½-line context** (example: "reverse_transfer (Stripe Connect — money moves from the connected org account back to the platform, then to the buyer)" not just "reverse_transfer=true").
   - If >8 bullets → PR is too large (split into gh-stack, §Path B).
2. **Block 2 — 🔍 Attention points:** bullets only, 3 IDEAL, 5 MAX. **MANDATORY pattern per bullet:** `**Risk label:** \`path/or filename\` — <what is risky, plain English>. **If review misses this:** <plain-English consequence — what actually breaks for users/devs>.` Risk labels (rename jargon to the readable versions below):
   - ✅ Use: `Security-sensitive` · `Performance-sensitive` · `Schema change (DDL migration)` · `Cross-module change` · `Concurrency / race condition` · `Product decision`
   - ❌ Stop using: `Blast-radius` (too vague — say what it actually hits)
   - If >5 bullets → split gh-stack.
3. **Block 3 — 💥 Breaking changes:** **INCLUDE ONLY IF they EXIST.** If NONE → DELETE the ENTIRE "Breaking changes" section (do NOT write "NONE", do NOT leave an empty section). When including: 1 heading per breaking change + Before / After / Migration bullets.
4. **Block 4 — 🧪 How to verify:** bullets only, 1–3 items, IN THIS ORDER:
   - (a) **Automated tests:** CONCRETE COMMAND pointing to a SPECIFIC test + 1 sentence what is covered + 1 expected-result sentence ("Expected: 1/1 passing green").
   - (b) **Quick manual check:** 2–3 CONCRETE steps with numbered parens, NO assumed folder-structure knowledge, always state the EXPECTED VISIBLE outcome (not "test it works").
   - (c) **Full plan (optional):** link to `$HARNESS_WORKSPACE_SHARED/manual_test_plan.md`
5. **Block 5 — 🔗 Refs:** Linear/Jira ticket (ID + URL). Optionally 1 extra link (Figma, PRD .md path, related PR number).
6. **FORBIDDEN sections (always delete if they creep in):** Scope In/Out, Assumptions adopted, long What/Why intro paragraphs, Harness gates checklist, giant tables, 2-paragraph context intro. (The "why" lives INSIDE each Block 1 bullet, NOT as a preamble.)
7. **Body budget:** ≤50 lines TOTAL (all 5 blocks + headings summed). No breaking → target ~30 lines. With breaking → target ~45 lines. If over → move long migration/design details into a separate linked doc + keep 1 summary line in Block 2 or 3. **Do NOT butcher acronyms/user-impact sentences to save 2 lines — save by cutting forbidden prose instead.**

**Linear ticket auto-include (A-4.0 common step):** When a ticket is detected (A-4.0), ALWAYS include it in Block 5 "Refs". Do NOT duplicate the ref in a separate footer/comment.

#### A-4.3 Create PR (Draft, not ready for review)

```bash
gh pr create \
  --draft \
  --base <DEFAULT_BRANCH> \
  --head <BRANCH_NAME> \
  --title "<conventional commit style title, more descriptive: feat(auth): implement Stripe Connect onboarding>" \
  --body-file <tmpfile_with_pr_description.md>
```

Capture the created PR URL: `<PR_URL>`.

#### A-4.4 Assign to user + labels

```bash
gh pr edit <PR_URL> --add-assignee @me
# Optional: add existing labels (type: bug/feature, needs review, security, breaking-change)
# Only add labels that EXIST in repo.
```

---

### Path B: GH_STACK_MODE=true (hierarchical PR stack via gh-stack)

#### B-4.2 Per-layer PR body + Depends-on chain (bottom-up)

For each layer `L[i]` in `LAYERS[]` (bottom-up order):
1. Build a PR description SCOPED EXCLUSIVELY to `L[i]` — same **READABLE 5-block structure + readability rules from Path A §A-4.2** (acronym expansion, user-impact per bullet, risk-consequence explanation, non-jargon labels, plain-language How-to-verify). Body is SCOPED TO ONLY the layer's changes (no cross-layer leaks).
   - **Depends on header (CANONICAL gh-stack)**:
     - If `L[i].Depends on` is non-empty → PREPEND block to the **TOP of PR body** (before the 5 blocks):
       ```
       Depends on: #<PR-ID-of-L[i-1]>
       ---
       ```
       (Use the numeric PR ID, not the full URL.)
     - If first layer (base, no Depends on) → skip this header.
   - Append: related ticket footer `Refs: <TICKET-ID>` inside Block 5 (🔗 Refs).
   - NO assumptions paragraphs / NO harness checklists. **Body total ≤35 lines per layer** (relaxed vs single PR because stack layers are smaller). Still enforce the readable style from PR_DESCRIPTION_TEMPLATE.md filled example.
2. Write each layer body to `<tmp>_layer_<L[i].ID>_body.md`.

#### B-4.3 Create each layer PR individually + gh-stack link

Loop layers **bottom-up**:
For each layer `L[i]`:
```bash
# Ensure on correct layer branch:
git checkout <L[i].BranchName>

# Create DRAFT PR for THIS layer:
gh pr create \
  --draft \
  --base <if first layer: DEFAULT_BRANCH; else: L[i].Depends on layer's branch> \
  --head <L[i].BranchName> \
  --title "<L[i].ID>: <layer scope descriptive conventional title>" \
  --body-file <tmp>_layer_<L[i].ID>_body.md
```
- Capture each layer's PR URL: `L[i].PR_URL` AND numeric PR ID: `L[i].PR_NUMBER`.
- After PR created: self-assign: `gh pr edit <L[i].PR_URL> --add-assignee @me`.

After **all individual layer PRs are created + assigned**:
```bash
# Run gh-stack to formalize the Depends-on hierarchy:
gh-stack create --draft
```
This validates the chain; if errors → fix base/head references manually per layer.

#### B-4.4 Stack invariant check

After gh-stack create: verify the chain:
- Layer 1 (base) PR `base: DEFAULT_BRANCH` → correct.
- Layer N PR `base: L[N-1] branch` AND body has `Depends on: #<L[N-1].PR_NUMBER>` → correct.
If mismatch → report to user; offer to fix via `gh pr edit --base` or body edit; wait approval.

---

## 5. STEP 5 — Report to user (in Portuguese)

### Path A: GH_STACK_MODE=false (single PR report)

Final output to user chat:

```
✅ /harness-ship concluído com sucesso.

Resumo:
  • Worktree: <worktree path>
  • Branch remota: <branch> (criada se não existia)
  • Commits aplicados: N (lista resumida)
    - <sha1 curto> type(scope): message
    - ...
  • PR criada (DRAFT): <PR_URL>  [atribuída a você]
  • Assumptions, review points, breaking changes: veja corpo da PR
  • Manual test plan: referenciado no corpo e disponível em:
    $HARNESS_WORKSPACE_SHARED/manual_test_plan.md

Próximos passos:
  1. Rode um smoke test manual usando o plano acima.
  2. Revise o diff da PR para garantir que nenhum arquivo não intencional entrou.
  3. Quando tudo ok: abra a PR <PR_URL>, clique em "Ready for review" e atribua reviewers.
```

### Path B: GH_STACK_MODE=true (hierarchical PR stack report)

Final output to user chat:

```
✅ /harness-ship concluído com sucesso — MODO gh-stack HIERÁRQUICO.

Resumo Geral:
  • Worktree: <worktree path>
  • Número de PRs na stack (bottom-up): <N layers>
  • gh-stack chain criada. Todas as PRs DRAFT + atribuídas a você.
  • Plano original: consultar $HARNESS_WORKSPACE_SHARED/gh_stack_plan.md

Stack de PRs (ordem de merge = base primeiro para o topo):
───────────────────────────────────────────────
L1 (base, merged first) →
   branch: <L1.BranchName>
   commits: K1
      - <sha> type(scope): message
      - ...
   PR DRAFT: <L1.PR_URL>   [base: DEFAULT_BRANCH]
───────────────────────────────────────────────
L2 → depends on #<L1.PR_NUMBER>
   branch: <L2.BranchName>
   commits: K2
      - ...
   PR DRAFT: <L2.PR_URL>   [base: L1.BranchName]
───────────────────────────────────────────────
...
───────────────────────────────────────────────
LN (topo, merged last) → depends on #<L[N-1].PR_NUMBER>
   branch: <LN.BranchName>
   commits: KN
   PR DRAFT: <LN.PR_URL>   [base: L[N-1].BranchName]
───────────────────────────────────────────────

Manual test plan global: $HARNESS_WORKSPACE_SHARED/manual_test_plan.md
(Valide o comportamento de cada layer individualmente antes de marcar a stack como pronta.)

Próximos passos (ordem de review = mesma ordem de merge bottom-up):
  1. Rode smoke test individual em cada layer começando por L1 (base).
  2. Revise diffs uma PR de cada vez — sempre L[i] PR review ANTES de L[i+1].
  3. Quando L[i] aprovada + merged: gh-stack atualiza automaticamente a base de L[i+1] → repita até LN.
  4. Só depois que LN merged: clique em "Ready for review" da top-level, ou siga o fluxo normal por layer.
```

---

## Appendix A: Hard stops / What we will NEVER do

- Commit files with `.env` in name OR any file matching secrets regex patterns.
- Push against a branch you are NOT currently on.
- Commit directly to `main` / `master` / default branch. Block. Always: feature branch → PR.
- Force push without explicit user confirmation.
- Merge the PR. Ship stops at DRAFT PR creation + assign.

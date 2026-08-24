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

1. Check if file exists: `<WORKTREE_ROOT>/.trae/<task-id>/gh_stack_plan.md`.
2. If it exists:
   - Read it. Validate it has a field `Status: APPROVED` at the top.
   - Check `gh` extension installed: run `gh extension list 2>/dev/null | grep -i "stack"` silently.
   - If gh-stack extension NOT installed → offer `gh extension install https://github.com/github/gh-stack` to user; wait for confirmation, install, then continue. If user declines → FALLBACK to single-PR mode (Steps 2–5 normal path).
   - Parse layers table bottom-up (first layer = lowest in stack, merged first; last layer = top of stack). Extract per layer: `Layer ID`, `Branch Name` (slug like `FLO-513-l1-refund-pipeline`), `Scope (files)`, `Depends on`.
   - Set boolean: `GH_STACK_MODE=true`. Record `LAYERS[]` array ordered bottom-up.
3. If file NOT exists OR status ≠ APPROVED → `GH_STACK_MODE=false`. Proceed with standard single-PR path (Steps 2–5 current).

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
Group changes into atomic, logical commits:

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

Present commit plan to the user as a **numbered list**, in order of application.
Wait for explicit user APPROVAL before running any `git commit`.

### 2.2 Execution — apply the commits (AFTER USER APPROVES plan)

Run each commit:
```
git add <files for this commit>
git commit -m "type(scope): imperative description in English, lowercase, max 72 chars"
```
Rules:
- NEVER run `git add .` — always add per-file or per-directory explicitly.
- Every commit message in ENGLISH, strict conventional commit.
- After last commit → run `git log --oneline -20` to present final chain to user.

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
   - Strategy B (simpler fallback — use when scope-per-layer is clearly file-based): from worktree state, `git add <only files matching L[i].Scope (files)>`, then create 1 or more conventional commits scoped EXCLUSIVELY to this layer (no cross-layer files in same commit).
3. Present plan of "branch → commits → scope" to user as numbered list. **Wait for explicit user APPROVAL before applying any layer commit.**
4. After user approves: apply commits per layer. Record per-layer: final commit SHAs.
5. After all layers done: present to user summary "Layers bottom-up (N layers): L1 → 2 commits; L2 → 3 commits; L3 → 1 commit" etc.

Rule invariant for GH_STACK_MODE commits:
- **Every file in a given layer's commit MUST be listed in L[i].Scope (files).** If a file belongs to layer L[i+1] it MUST NOT appear in commits of L[i]. Any cross-layer file → block, ask user which layer gets it.

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
- Branch name pattern: `feat/FLO-123-login`, `fix/FLO-456`, `ticket FLO-123` anywhere in session/task_graph/envelope files
- User command args: `/harness-ship ticket:FLO-123`

If found ticket: extract `<TICKET-ID>` (full URL or just ID). Append `Refs: <TICKET-ID>` footer to EVERY PR body (single OR all layers in stack).

---

### Path A: GH_STACK_MODE=false (single PR, standard)

#### A-4.2 Build structured PR Description (English)

Follow template at `references/PR_DESCRIPTION_TEMPLATE.md`.
Fields to fill:
- **What this PR does / why we need it** (1-3 lines, English)
- **Assumptions adopted** (key decisions from decision.log → select top 3-5)
- **Key review points** (places the reviewer should really scrutinize — tricky logic, performance, security-sensitive)
- **Breaking changes (if any)** — list each. NONE is a valid value.
- **How to test manually** — link the in-tree `.trae/<task-id>/manual_test_plan.md`
  AND reproduce 2-3 core steps inline inside the PR description.
- **Related ticket / links** — Linear ticket link, Jira link, or mark "N/A"
- **Checklist** — marks our gates: lint/typecheck/tests/compliance/decisions-log

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
1. Build a PR description scoped EXCLUSIVELY to `L[i]` scope:
   - **What this PR (layer <L[i].ID>) does**: 1–3 lines scoped to this layer's files.
   - **Depends on footer (CANONICAL gh-stack)**:
     - If `L[i].Depends on` is non-empty → append block to **TOP of PR body**:
       ```
       Depends on: #<PR-ID-of-L[i-1]>
       ---
       ```
       (Use the numeric PR ID, not the full URL.)
     - If first layer (base, no Depends on) → skip this block.
   - Include: assumptions scoped to layer, review points scoped to layer, related ticket footer (TICKET-ID), checklist for just that layer.
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
    <worktree>/.trae/<task-id>/manual_test_plan.md

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
  • Plano original: consultar <worktree>/.trae/<task-id>/gh_stack_plan.md

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

Manual test plan global: <worktree>/.trae/<task-id>/manual_test_plan.md
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

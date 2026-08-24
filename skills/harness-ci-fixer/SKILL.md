---
name: "harness-ci-fixer"
description: "Diagnoses and fixes failing CI runs on GitHub Actions (or a PR). Takes a PR URL or Actions run URL, identifies failing jobs/steps with logs, classifies root cause (build/lint/typecheck/infra/flaky/dependency), implements fixes, re-runs locally to confirm. Invoke when user reports CI failure or pastes a PR/Run URL and asks to fix it, or when /harness-ci-fix is called."
---

# Harness — CI Fixer

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - GitHub CLI gh auth + CI logs pull commands: `_shared_checklists/GITHUB_CLI_COMMON.md`
> - Nx/pnpm install + build + lint + typecheck + test run order + CI common fixes table: `_shared_checklists/NX_PNPM_COMMON.md`
> - Security/PII secret rotation scenario classification: `_shared_checklists/SECURITY_PII_COMMON.md`

Given a failing GitHub Actions run (or a PR whose latest checks are failing), this role:
1. Identifies WHICH jobs/steps are failing.
2. Reads logs.
3. Classifies root cause category.
4. Implements a minimal fix (per engineering-contracts precedence rules).
5. Confirms locally / re-triggers.

Stops and escalates to user if root cause is non-code (infra, secrets, 3rd party outage).

---

## 0. Preconditions & environment

1. **Input from user**: OR
   - A URL to a PR: `https://github.com/owner/repo/pull/123` OR
   - A URL to a specific Actions run: `https://github.com/owner/repo/actions/runs/456`
2. **Worktree path** (for local fix). If not provided → ASK user which worktree to make fixes in.
3. **`gh auth status` OK**. If not → guide user login first.

---

## 1. STEP 1 — Identify failing jobs / steps

### Case A: Input is a PR URL.

```bash
# Get all check runs / status checks for PR HEAD commit
gh pr checks <PR_URL>
```
Record: names, status (fail / pass / pending), conclusion, started_at, run_id for each failed check.

### Case B: Input is an Actions run URL.

Extract run_id from URL.
```bash
gh run view <RUN_ID> --json jobs,name,status,conclusion,url
```
Inspect `.jobs[]` — each has `.steps[]` with `.conclusion`.

### Final structure: build FAILING_JOBS[]

```
FAILING_JOBS[] = [
  {
    job_name: "Build / Platform (lint-build-test)",
    run_id: "456789",
    failed_steps: [
      { name: "Run corepack pnpm lint", exit_code: 1, log_url: "..." },
      { name: "Run Playwright E2E", exit_code: 2, log_url: "..." }
    ]
  }
]
```

---

## 2. STEP 2 — Extract error logs & classify each failure

For EACH failed step:

```bash
gh run view <RUN_ID> --log-failed | grep -A 40 -B 5 "<job name>" > /tmp/job-X.log
```
Or get per-step log via `gh run view <RUN_ID> -i <step-index> --log` style if available.

### 2.1 Root Cause Classification Framework

Classify EACH failure into EXACTLY ONE of these categories (priority order — match first applicable):

| # | Category | Signals in log | Typical fixes |
|---|---|---|---|
| R1 | **🔴 BUILD / TYPECHECK FAILURE** | `tsc error TS2307`, `Could not resolve`, `Module not found`, `SyntaxError`, Java/Kotlin/groovyc/`rustc compile error`, `webpack/rollup/vite build error` | Fix broken imports, types, missing dependencies, TS strict errors. |
| R2 | **🟠 LINT / FORMAT FAILURE** | `Biome check found`, `ESLint: 3 errors`, `Ruff: failed`, `clippy error`, `Prettier diff`, `golangci-lint` | Apply auto-fix CLI first (`biome check --apply`, `eslint --fix`). For manual: rename vars, remove unused, fix format. |
| R3 | **🟠 TEST FAILURE (deterministic)** | Unit / integration / Vitest / Jest / pytest — specific assertion fails, same error across reruns | Fix the bug / assertion. If our change broke it: minimal fix. TDD style: confirm test failure → implement minimal fix → confirm pass. |
| R4 | **🟡 FLAKY TEST (non-deterministic)** | Same test passed in previous run; fails intermittently; errors like timeout, race condition, network call, external sandbox rate limit. NOT reproducible locally first try. | First: rerun failed jobs via `gh run rerun <RUN_ID> --failed-only`. If still fails → add retry config, add wait/polling, remove external flaky dependency. |
| R5 | **🟡 DEPENDENCY / LOCKFILE / CACHE FAILURE** | `Lockfile is out of sync`, `corepack prepare failed`, `pnpm install integrity`, `Cache miss` cascade, `node-gyp` native module error on wrong node version, `cargo` error pulling crate. | Re-run install with correct engine version. `corepack pnpm install` + commit lockfile changes. Match Node/pnpm version from `.nvmrc` / `package.json engines`. |
| R6 | **🟡 SCRIPT FAILURE (CI config / yml bug)** | `yaml: line X: mapping values are not allowed`, `runs-on:` invalid runner label, missing `uses:` action version, missing env var required by action, shell bash line with syntax error in CI step inline `run:`. | Fix `.github/workflows/*.yml` — validate yml indentation, references, runner. |
| R7 | **⚠️ INFRA / OPS / EXTERNAL (do NOT code)** | `No space left on device`, runner OOM killed, 500 from GitHub internal, `Error: Network error from docker.io`, `npm registry 5xx`, Actions outage, `secrets.*` variable undefined (secret was rotated/deleted), `rate limit` from external API. | **STOP and report to user:** "This failure is not fixable by modifying source code. Root cause: <explanation> — Action: (1) ask ops to fix secrets, (2) wait / rerun later, (3) check GitHub status page." NEVER guess secrets or hardcode to bypass. |
| R8 | **🟠 MIGRATION FAILURE** | `Migration down`, `relation "X" does not exist` migration order wrong, `duplicate key value violates unique constraint`, DROP on protected table in env with guard `NODE_ENV=production`. | Fix migration order / SQL / add missing NODE_ENV guard; match dev seed expectations. |
| R9 **(NEW — P2.12)** | **🟣 TEST MISMATCH — INTENTIONAL ACCEPTANCE CRITERIA CHANGE** | **Failure pattern:** failing tests are deterministically failing AND the user/TASK ENVELOPE/PRD explicitly CHANGED the behavior that the test was asserting (confirmed by you reading the new ACs). **NOT** a bug in implementation — instead test encodes OLD behavior). | **FIRST:** confirm with user IN WRITING (chat, Portuguese): "Os testes falham PORQUE os ACs mudaram? confirma que quer atualizar os testes e NAO reverter o código? [S/N + explicação curta]". **IF USER CONFIRMS S:** Update the tests to match NEW ACs (donotrevert implementation code). Add commit type: `test(scope): align <feature> tests after AC change (FLO-XXX)`. If user says NO → go back to R3 category (treat as a code bug), fix the code, NOT the tests. USER MUST EXPLICITLY CONFIRM; never do R9 on guesswork. |

---

## Classification priority rule for R9 (to avoid misuse): **only apply R9 after R1-R8 all checked and ruled out.**

---

## 3. STEP 3 — Propose minimal fix plan (per job)

For each failed step:
1. **If category R7 (infra/external):** STOP. Report to user — do not touch code.
2. **Otherwise:** produce a numbered minimal fix plan:
   ```
   Job: "<name>" — failed step: "<step-name>"
   Classification: R1 (BUILD / TYPECHECK FAILURE)
   Evidence excerpt (first 10 lines of log):
     > ...
   Root cause hypothesis:
     Import from `@flockr/logger` fails because new file `logger.ts` was added but
     package exports field in packages/logger/package.json still only lists `index.ts`.
   Fix plan:
     - File: `packages/logger/package.json` — edit `exports` → add `./logger` pointing to `dist/logger.js` and types
     - Estimated blast radius: 1 file
   ```

Present ALL fix plans to the user for APPROVAL before writing ANY code.
Wait explicit user APPROVAL (or for trivial lint fixes where user said "fix lint you can go").

---

## 4. STEP 4 — Implement fixes locally (in worktree)

Per user-approved plan:
- Work ONLY in approved worktree.
- Minimal changes only (Rule 1 engineering-contracts — KISS + blast radius).
- After each fix category:
  - R2 lint: run `corepack pnpm biome check <files>` locally → confirm 0 errors (or equivalent runner)
  - R1 build: run build command locally → confirm green
  - R3 test: run SINGLE failing test spec → confirm it passes
  - R6 CI YML: validate YAML syntax with `yamllint` or `python -c "import yaml; yaml.safe_load(open('.github/workflows/X.yml'))"`

---

## 5. STEP 5 — Verification loop

Goal: confirm failure is fixed BEFORE we commit.
- For each previously failing job/step:
  - Rerun locally equivalent command
  - If equivalent is impossible (full CI environment): do our best local equivalent + log "Cannot run full CI locally; equivalent local command passes. Need to push for GitHub to rerun."

---

## 6. STEP 6 — Ship & CI re-trigger

User approves fix → use `harness-ship` flow for commits:
- Conventional commits: `fix(ci): ...`, `fix(build): ...`, `fix(lint): ...`, `chore(deps): ...`
- Atomic
- Push with `--no-verify` to the branch.

After push, if user wants:
```bash
# Optionally trigger a fresh rerun of previously failed jobs (if run still exists)
gh run rerun <RUN_ID> --failed-only   # OR: new commit will auto-trigger new checks anyway
```

Wait for user or show them status: `gh pr checks <PR_URL>` to watch.

---

## 7. Final report to user (Portuguese)

```
✅ Diagnóstico + plano de fix para CI aplicados.

Jobs que estavam falhando: N (total).
Fix aplicado via:
  • Classificação:
      - R1 Build/typecheck: corrigido em <file>
      - R2 Lint: corrigido biome auto apply + manual em <file-list>
      - R3 Test failing: fix em <function>
      - R5 Lockfile sync: corepack pnpm install → lockfile atualizado
      - R7 Infra (1 job): NÃO foi código. Ação: reportado ao usuário.

Push realizado para branch: <branch>
Status dos checks agora: use `gh pr checks <pr_url>` para acompanhar ou abrir a URL no Actions.

Caso ainda falhe algo não previsto, me avise e reinvestigo com logs do novo run.
```

---

## Appendix A: Things we NEVER do

- Never commit secrets to fix `secrets.X undefined` (that's ops; flag to user).
- Never modify CI to `continue-on-error: true` just to make it green. We FIX the cause.
- Never skip a failing test with `.skip` unless we explicitly log why + follow-up issue. Only allowed if the test itself is broken AND user approves exception.
- Never guess at package versions. Pin versions exactly like repo conventions (exact / caret / tilde).

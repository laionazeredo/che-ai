# Gate G-ENG-1: Lint · Typecheck · Test Pass Rate (100% mandatory)

Run AUTOMATICALLY by ship §0.9.5 DOMAIN GATES when `domain=engineering` (default).

---

## Numerical Thresholds (MANDATORY, without numbers it becomes a HUMAN ONLY gate)

| Metric | HARD PASS Threshold | What it measures |
|---|---|---|
| Lint errors | **`0`** | Biome check --error-on-warnings=false, eslint max-warnings 0 |
| Lint warnings | `N` (allowed, but HIGH review comment automatically) | Code review §0.9.2 suggests fix if warnings ≥5. Does not fail the gate |
| Typecheck errors | **`0`** | tsc --noEmit / cargo check / mypy strict |
| Typecheck warnings | `N` (allowed) | HIGH if ≥10 |
| Test pass rate (unit + integration) | **`100.0%`** (0 FAIL, 0 ERROR) | No test can be FAILING in CI. Flaky = retry seed 2x |
| Test total count ≥ | `1` per AC defined in SPEC | Absolute minimum. Not a substitute for coverage G-ENG-2. |

---

## Detection & Retry Policy

### 1st FAIL:
- 1 FREE automatic retry with same seed.
- If 2nd run PASSES = marked as "FLAKY" in log, gate = PASS with warning.
- If 2nd still FAILS = report top 3 FAILURES with stack trace.

### 2nd FAIL (after retry or deterministic fail):
→ **HARD STOP HUMAN REQUIRED**.
Agent does not fix broken architecture tests or large refactors WITHOUT updated SPEC. User chooses: (A) fix manually (B) logged user EXPLICIT_OVERRIDE (only in extreme cases, like obsolete test removed) (C) cancel ship.

---

## How to execute manually (if you want to run before ship)
Each project defines `lint`, `typecheck`, `test` via Nx targets / package scripts.

```bash
# Example monorepo pnpm + nx:
corepack pnpm nx run-many --all --target=lint --tui false
corepack pnpm nx run-many --all --target=typecheck --tui false
corepack pnpm nx run-many --all --target=test --tui false
```

---

## Generated Artifacts (mandatory to attach to PR description if shipping)

```
reports/domain-gates/
└── G-ENG-1--lint-typecheck-test_<timestamp>.json
    {
      "gate_id": "G-ENG-1",
      "timestamp": "...",
      "lint_errors": 0, "lint_warnings": 4,
      "typecheck_errors": 0, "typecheck_warnings": 0,
      "test_total": 137, "test_pass_rate": 100.0, "test_failures": [],
      "retry_applied": false,
      "result": "PASS | FAIL"
    }
```

---

## Special Cases

| Scenario | Action |
|---|---|
| Multi-package monorepo | Run G1 separately per package. 1 failure = general failure. Aggregated report. |
| Worktree-only changed markdown/docs | Automatic skip of typecheck/lint/TEST (but not if .ts/.rs/.py changed) — detected via diff. |
| Project without tests defined in SPEC? | 1st gate FAIL. Require user EXPLICIT_OVERRIDE ALWAYS. Cannot pass gate without override. |

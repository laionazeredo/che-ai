# Gate G-ENG-2: Coverage (Lines · Branches · New Code)

Run AUTOMATICALLY by ship §0.9.5 DOMAIN GATES when `domain=engineering`.

---

## Numerical Thresholds (Defaults)

| Metric | Threshold | What is excluded from calculation |
|---|---|---|
| **OVERALL Lines coverage** (entire package) | `≥ 70.0%` | `*.{test,spec}.{ts,rs,py}`, `**/migrations/**`, `**/*.config.*`, `**/vendor/**` |
| **New code coverage** (only lines changed in current diff vs base branch main) | `≥ 80.0%` | Same |
| **OVERALL Branch coverage** | `≥ 65.0%` | Same |
| **Critical paths** defined in SPEC as mandatory to cover | `100%` (or EXPLICIT_OVERRIDE) | Payment flow, auth gate, RLS, refund. |

> 💡 **Override rule**: NUMERICAL thresholds are NEVER altered by the agent without user EXPLICIT_OVERRIDE logged in decisions.log. Above values are reasonable defaults.

---

## Example tools per stack

| Stack | Canonical coverage command | Output format |
|---|---|---|
| Vitest (TS/JS) | `vitest run --coverage` | `coverage/cobertura.xml` + `json-summary` |
| Jest | `jest --coverage` | `coverage/lcov.info` |
| Pytest (Python) | `pytest --cov=src --cov-report=xml:coverage/cobertura.xml --cov-report=term-missing` | cobertura.xml |
| Cargo tarpaulin (Rust) | `cargo tarpaulin --out Xml` | cobertura.xml |

---

## Retry + 2nd failure

### 1st FAIL:
- 1 automatic retry re-runs coverage report (same seed). If diff in workspace changed, run diff coverage only on new lines.
- Report top 5 files with lowest coverage + 10 most critical uncovered lines.

### 2nd FAIL → HARD STOP (3 user options):
(A) Fix by adding tests to missing lines. **Recommended.**
(B) **EXPLICIT_OVERRIDE** user literal logged in decisions.log with exact format:

```
[EXPLICIT_OVERRIDE] GATE=G-ENG-2
  original_thresholds={lines=70, new_code=80, branches=65}
  new_thresholds={lines=60, new_code=70, branches=55}
  reason="<user verbatim literal 3 sentences minimum explaining WHY it was lowered>"
  approver="<user_login>"
```

(C) Cancel ship.

---

## Artifacts

```
reports/domain-gates/
└── G-ENG-2--coverage_<timestamp>.json
    {
      "gate_id": "G-ENG-2",
      "lines_total_pct": 76.4, "lines_pass": true,
      "new_code_pct": 83.2, "new_code_pass": true,
      "branches_pct":   67.0, "branches_pass": true,
      "uncovered_top5": [ {"file":"src/db.ts","lines_missing":14} ],
      "diff_size_added_lines": 187, "diff_covered_lines": 154,
      "retry_applied": false, "override_applied": null,
      "result": "PASS | FAIL"
    }
```

---

## Special Cases

| Scenario | Action |
|---|---|
| Giant refactor without new features | Overall coverage may drop slightly. Requires EXPLICIT_OVERRIDE. |
| Only docs / markdown changed | Skip GATE, report `SKIPPED` with justification in JSON. |
| 1 entire file "not testable" (e.g. automatically generated binding) | Add to paths excluded from coverage in tool config. Log decision. |

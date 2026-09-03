---
description: "Bug fix che. Scientific debug loop: Hypothesize → Instrument → Reproduce → Analyze → Fix → Verify."
arguments:
  - name: worktree
    description: "Absolute worktree path. If missing, ASK first."
    required: false
  - name: expected
    description: "Expected correct behavior (VERBATIM). If missing, Skill asks."
    required: false
  - name: actual
    description: "Actual bug behavior (VERBATIM). If missing, Skill asks."
    required: false
  - name: repro
    description: "Exact numbered reproduction steps (1. ... 2. ...). If missing, Skill asks."
    required: false
---

IMMEDIATELY invoke **`che-debugger-bugfix`** Skill.

Preflight:
1. If worktree missing → ASK.
2. If ANY of the 4 required inputs (expected behavior / actual bug / exact repro steps / ticket ref) is missing → Skill captures from user.
3. Skill proceeds with baseline repro → 5-iteration debug loop → minimal fix + regression test → demo.

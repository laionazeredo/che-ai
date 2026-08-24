# DECISION LOG TEMPLATE

> Append-only log. Each entry = one non-obvious decision / trade-off / exception to rules.
> File location: `<WORKTREE_ROOT>/.trae/<task-id>/decision.log.md`
> Format for each entry:

---

```markdown
## [YYYY-MM-DD HH:MM] [TASK-ID] <Title of the decision>

### Context
<1-2 lines of what situation triggered this — English>

### Options considered
1. **Option A:** <what was it>
   - Pros:
   - Cons:
2. **Option B:** <what was it>
   - Pros:
   - Cons:
3. **Option C (if any):** ...

### Decision: Option <X>

### Rationale
<clear, short, English. Reference which engineering-contracts rule was weighed>

### Trade-offs acknowledged (what we accept for this choice)
- ...

### If this goes wrong, we should revisit and consider:
<back-out or alternative path>

---
```

**WHEN to write an entry (not exhaustive, but mandatory for these):**
- Touched a file OUTSIDE the TASK ENVELOPE blast radius list
- Task will touch > 10 files (list each file, why justified)
- Violates KISS/YAGNI (Rule 1) — and you know it — but needed to follow a HIGHER rule (e.g. security, Rule 2)
- Used mutation / mutable loops when pure functional was possible (performance rationale)
- Added a NEW dependency / NEW class instead of reusing existing
- Skipped a test for a specific reason (document reason, what regression guard exists instead)
- Added a TODO / FIXME / tech debt to production code
- Made an architectural choice in a fresh repo where no pattern existed
- Trade-off between performance and readability
- Any SM override / skip of a gate (QA or Compliance light) — who approved, why
- Chose one of multiple equally valid implementations — explain why this one

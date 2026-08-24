# BUGFIX SESSION TEMPLATE

> Used by harness-debugger-bugfix for a bug fix session.
> Location: `<WORKTREE_ROOT>/.trae/<bug-slug>/bugfix_session.md`
> Append-only across iterations.

---

# 🐛 Bugfix Session — `<bug-slug>`

## Metadata

| Field | Value |
|---|---|
| Started at | `<ISO datetime>` |
| Worktree | `<absolute path>` |
| Branch | `<name>` |
| Ticket (if any) | `<Linear/Jira URL or ID or N/A>` |

## Inputs provided by user

### Expected behavior
```
<copy user's expected behavior here>
```

### Actual / bug behavior
```
<stack trace, error message, screenshots description>
```

### Original reproduction steps from user
1. ...
2. ...
3. ...

---

## Phase 0 — Baseline

### Step 1.1 Reproducibility result

```
✅ COULD REPRODUCE / ❌ COULD NOT REPRODUCE  (circle one)

Evidence captured:
  • Server logs:
    <excerpt around the error>
  • HTTP response:
    <status, body preview — NO secrets>
  • Stack trace (first 40 lines):
    ...
```

### Step 1.2 Minimal reproduction case

(Smallest set of steps that still triggers the bug. Unit test snippet if possible.)

```
Minimal steps:
1. ...
2. ...
3. Actual: ... ; Expected: ...

Minimal test (if possible):
it('should <correct behavior>', () => {
  const result = buggyFn(<minimal input>)
  expect(result).toBe(<expected>)   // FAILS before fix, PASSES after
})
```

### Step 1.3 Initial ranked hypotheses

```
H1 (Likelihood HIGH): <hypothesis>
  - Why this is HIGH: <evidence>
  - Test to confirm/refute: <what instrument + what we look for>

H2 (MEDIUM): <hypothesis>
  - ...

H3 (LOW): <hypothesis>
  - ...
```

---

## Phase 1 — Debug Loop iterations

### Iteration 1 — Date: `<ISO>` — Hypothesis: `<Hn>`

#### Instrumentation
- Added debug logger at `<file>:<line>`: `logger.debug({ suspect_var })`
- No code changes this iteration

#### Reproduction captured output
```
<log output / stack / assertion message>
```

#### Analysis
- Decision: **CONFIRMED** / **REFUTED**
- Rationale: `<conclusion>`

#### If CONFIRMED — Root cause + proposed fix
**Root cause (1 sentence):**

**Fix options:**
1. Option A — ...
   - Files touched: `<files>`
   - Pros:
   - Cons:
2. Option B — ...

Decision: Option `<X>` — because:

---

### Iteration 2 — Date: `<ISO>` — Hypothesis: `<Hn>`
(Repeat same structure as Iteration 1)

---

## Phase 2 — Engineering of the fix

### TDD: regression test

- Test file path:
- Before fix: PASSES / FAILS ❌ (cross out)
- After fix:  PASSES ✅ / FAILS ❌ (cross out)

### Minimal diff (the fix itself)

Files changed:
- `<path1>` — `<1 line summary>`
- `<path2>` — ...

Patch snippet:
```diff
--- a/file.ts
+++ b/file.ts
@@ -XX,Y +XX,Y @@
 <context lines>
-<old bad line>
+<new fixed line>
 <context lines>
```

### Related tests — no regressions

| Command | Result (0 fails / N fails) |
|---|---|
| `corepack pnpm test src/module-under-test` | ✅ 0 fails |
| `corepack pnpm lint` | ✅ 0 errors |

### Manual verification evidence

```
BEFORE FIX:
  Steps: <minimal repro>
  Result: <actual bad behavior>

AFTER FIX:
  Steps: <same minimal repro>
  Result: <expected good behavior>

Before/after comparison (screenshots / HTTP response diffs if applicable):
  • ...
```

---

## Final outcome

- [ ] ✅ Fixed and verified via automated test + manual
- [ ] ⚠️ Blocked after N iterations — next session needed

### Decision log entries during this session

(Reference decisions appended to `<WORKTREE_ROOT>/.trae/<bug-slug>/decision.log.md`)

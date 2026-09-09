# Template · Engineering Bug Report (scientific, reproducible)

The standard for Scientific Debugging (che-fix skill). **Always fill this BEFORE starting to fix.**

---

## 1. 🔴 Metadata
| Field | Value |
|---|---|
| ID | `bug-YYYYMMDD-NNN` |
| Reported By | |
| Report Date | DD/MM/YYYY |
| Environment | Local · Dev · Staging · Prod |
| Severity | 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low |
| Domain | engineering |
| Ticket / Issue URL | |

---

## 2. Expected Behavior
Describe in 1 sentence what should happen + 1 literal AC from the SPEC/PRODUCT if it exists:

## 3. Actual Behavior
Attach screenshot, error message, stack trace, logs:
```
<paste actual error here with full --stacktrace>
```

## 4. Reproduction Steps (MINIMUM 5 steps, reproducible 3x consecutively)
Exact step-by-step. DO NOT skip steps. Must work on any machine:
1. Log in as user `admin@acme.com` password `...` (mask if necessary)
2. Navigate to `/events/123/manage/refunds`
3. Click "Refund" button on order #832
4. Fill value 10.00 GBP, reason "duplicate"
5. Click Confirm → ERROR: ...

## 5. Initial Hypotheses (Top 3)
Scientific Debug: 3 plausible hypotheses, probability ranking:
| # | Hypothesis | Probability | How to instrument | Status |
|---|---|---|---|---|
| H1 | `isPlatformAdmin` returns false due to wrong worktree binding | HIGH | log function args + authz context | |
| H2 | ... | MEDIUM | | |
| H3 | ... | LOW | | |

## 6. Evidence Collection (each hypothesis → instrumentation → output)
```
H1 Instrumentation: console.log(user_id, role, worktree binding)
Output:
{ user_id: 1, role: 'admin', binding_wt: 'feat-FLO-513', actual_wt: 'main' }
→ Conclusion H1 CONFIRMED: binding_wt mismatch
```

## 7. Root Cause (FINAL, 1 sentence)
Once all hypotheses are resolved, write the Root Cause here.

## 8. Technical Fix Description
| File | Change | Approx. Line | Why does it resolve? |
|---|---|---|---|
| `packages/platform/server/services/RefundService.ts` | Replace worktree binding resolver helper | 795 | Uses canonical contracts official helper instead of hardcoded path |

## 9. Additional Tests to prevent regression
| Type | Case Name | What it validates |
|---|---|---|
| Unit | `refund.binding.worktree.mismatch → throws authz error` | Sends wrong worktree and blocks access |

## 10. Manual verification after fix applied
Reproduction steps from step 4 run again, RESULT: expected behavior.

---

## 11. Sign-off
| Name | Role | Date | Status |
|---|---|---|---|
| | Reporter | | Bug Report created |
| | SWE who fixed | | Bug fixed + tests pass |
| | QA who validated | | Verified in staging |

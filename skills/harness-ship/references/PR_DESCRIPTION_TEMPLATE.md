# PR DESCRIPTION TEMPLATE

> Used by `harness-ship` when creating a GitHub DRAFT PR.
> Language: ENGLISH (per harness rules).

---

## 📋 What this PR does / why we need it

<1-3 clear sentences. English. Include user/business value.>

Example:
```
Adds Stripe Connect onboarding flow for event creators. This lets organizers
sign up as Stripe connected accounts and start receiving payments for ticket
sales. Part of FLO-123.
```

---

## 🎯 Scope (In / Out)

### In scope (this PR covers):
- ...
- ...

### Out of scope (deliberately NOT done here — will be follow-up):
- ...
- ...

---

## 🧠 Assumptions adopted

(Top 3-5 key decisions / trade-offs extracted from `decision.log.md`)

1. **Assumption A:** <short explanation + why we chose this way>
2. **Assumption B:** ...
3. **Assumption C:** ...

---

## 🔍 Key review points

(Places the reviewer MUST pay attention. NOT cosmetic/formatting.)

- [ ] **Security-sensitive:** `path/to/file.ts` — contains auth check for X boundary
- [ ] **Performance-sensitive:** loop with N² potential in `path/to/other.ts`
- [ ] **Blast-radius risky:** migration `YYYYMMDD-name.sql` — DDL on large table `orders`
- [ ] **Cross-module:** touches `packages/db` entity + `packages/platform` service together — confirm coupling is acceptable

---

## 💥 Breaking changes (if any)

**NONE.**

OR — list each with migration guide:
```
### Breaking change 1: POST /orders now requires `customer_id` in body
- Old behavior: customer inferred from JWT when omitted
- New behavior: 400 if missing
- Migration: clients sending request must now include `customer_id`
```

---

## 🧪 How to test manually

**Full plan → `./.trae/<task-id>/manual_test_plan.md` (in-worktree file).**

Quick sanity steps (inline for the reviewer):

### Core happy path
```bash
# 1. Checkout this branch
git checkout <branch>

# 2. Install + start
corepack pnpm install
corepack pnpm nx run platform:dev --tui false

# 3. Navigate → login as creator role → navigate /dashboard/earnings
# Expected: "Connect Stripe" CTA visible, no console errors

# 4. Click CTA → complete Stripe onboarding (test mode)
# Expected: returns to Flockr; account status shows "Pending"
```

### Edge cases to try
- Submit form with invalid Stripe test data
- Refresh mid-flow; confirm state recovery
- Log out; log back in; confirm onboarding status persisted

---

## 🔗 Related tickets / references

- **Linear ticket:** `FLO-123` — <https://linear.app/flockr/issue/FLO-123/...>  **(or) Jira / N/A**
- **Related docs / designs:** Figma link, PRD path

---

## ✅ Harness gates checklist

(Automatically verified — marked at ship time.)

- [ ] Build passes (TS typecheck + package builds) — QA Stage A
- [ ] Lint passes (Biome/ESLint) — QA Stage B
- [ ] Typecheck passes — QA Stage C
- [ ] Unit + Integration tests pass — QA Stage D
- [ ] Compliance LIGHT (per-task): 0 CRITICAL, 0 HIGH
- [ ] Compliance HEAVY (full session): 0 CRITICAL, 0 HIGH
- [ ] `decision.log.md` written for non-obvious trade-offs
- [ ] Commits: atomic + conventional commits only

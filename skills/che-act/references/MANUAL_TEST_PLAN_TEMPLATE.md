# MANUAL TEST PLAN TEMPLATE

> Created by Scrum Master after all tasks are DONE and both Compliance stages passed.
> Resolve ALL paths via the `che` CLI: `eval "$(che compute_paths WORKTREE_ROOT SESSION_ID)"`. NEVER inside `<WORKTREE_ROOT>/.trae/*`.
> File location: printed by `che manual-plan sync "$WORKTREE_ROOT"` (durable, shared across sessions for the same worktree). Never hardcode it.
> Gate before shipping: `che manual-plan validate <path>` must exit 0. Authoring rules: `che-manual-plan` skill.
> Purpose: step-by-step human or automated verification of every acceptance criterion — prose for the human, an executable contract for the agent.
> Language: English (per che rules). User communication about this plan is in Portuguese.

---

# Manual Test Plan — `<task-id-slug>`

- **Created:** `<ISO datetime>`
- **Worktree:** `<absolute path>`
- **Branch / PR:** `<branch name> | (if applicable: PR URL)`
- **Requires access to:** staging environment / local dev / test user credentials / DB seed — specify

## Header (plain language — engineering-contracts §23)

| Field | Content |
|---|---|
| What this is | `<1 sentence, no jargon>` |
| Why it matters | `<1 sentence — what breaks for the user if this is not verified>` |
| I need from you | `<who runs it + how long, or "none">` |
| Read next | `<1 link, or "nothing — informational">` |
| Confidence | `<high \| medium \| low> — <1 clause on why>` |

---

## 0. Environment Setup — Preconditions

```bash
# Clone / checkout
git checkout <branch>

# Install deps (use what the repo actually uses)
corepack pnpm install      # OR npm ci / cargo build / pip install

# Environment variables needed (NAMES ONLY — never values):
#   - STRIPE_PUBLISHABLE_KEY (test mode)
#   - DATABASE_URL  (point to local / test DB, NOT PROD)
#   - APP_URL       (http://localhost:3000)

# Start services in order
corepack pnpm nx run platform:dev --tui false
# ... etc.

# Seed (if applicable)
corepack pnpm db:seed:test
```

### Test accounts / test data

- Username / role 1: `<describe — NO passwords>`
- Username / role 2: `<describe — NO passwords>`
- Stripe test card (if payments): `4242 4242 4242 4242` + any future expiry + any CVC

---

## 1. Per Acceptance Criterion — Scenario Test Cases

Every AC from the PRD / task_graph must have a section here.
Format for EACH AC:

```markdown
### AC-<N>: <Title of AC from PRD>

**GIVEN:** <preconditions in natural language — setup state>
**WHEN:** <user action or system trigger — step-by-step>
**THEN:** <observable expected result — must be verifiable WITHOUT reading source code>

#### Manual Steps

1. Navigate to `http://localhost:3000/...`
2. Log in as role `<X>`
3. Click `<button name>`
4. Fill the form with:
   - Field A: `valid value`
   - Field B: `valid value`
5. Submit
6. Check page:
   - Expected visible text: `"<exact expected>"`
   - URL changed to `/success`
   - (If email/sms sent: check sandbox / logs)

#### Executable contract (MANDATORY — one per AC)

`che manual-plan sync` inserts this skeleton; fill every `TODO`. The gate rejects anything outside
this vocabulary.

| Field | Allowed values |
|---|---|
| `driver` | `ui` · `api` · `db` · `manual` |
| `lane` | `local` · `preview` · `remote` |
| `severity` | `BLOCKER` · `HIGH` · `MEDIUM` · `LOW` |
| `evidence` | `screenshot` · `video` · `console_log` · `network_log` · `api_response` · `log_file` |
| `action` | `goto` · `click` · `fill` · `press` · `wait` · `assert` · `api` · `manual` |
| locator | `role` + `name`, or `label`, or `text` — **CSS/XPath are rejected** |

```yaml
# --- executable contract (AC-<N>) ---
id: AC-<N>
driver: ui
lane: local
base_url: http://localhost:3000
evidence: [screenshot, console_log]
severity: HIGH
steps:
  - action: goto
    url: /path
    expect_visible: Exact text
  - action: click
    role: button
    name: Exact button label
  - action: fill
    label: Field label
    value: "value"
  - action: assert
    expect_visible: Exact result text
    expect_api: GET /api/resource 200
```

Assertions must be literal (`Refunded`, not `works`). One action per step. Never a secret.

#### Automated equivalent (if known)
- Command: `corepack pnpm test path/to/spec.ts`
- Vitest/Playwright test file: `packages/platform/src/__tests__/...`

#### Rollback / Undo
- DB: revert the order created in step 4: `DELETE FROM orders WHERE id = ...`
- Cache: clear browser localStorage for origin

#### Severity if FAILS
- BLOCKER / HIGH / MEDIUM / LOW
```

---

## 2. Smoke Test Checklist — general platform not broken

Even if ACs pass, check nothing else broke.

| # | Area | Check | Expected | PASS / FAIL | Notes |
|---|------|-------|----------|-------------|-------|
| S1 | Build | `corepack pnpm build` completes | 0 errors | | |
| S2 | Lint | `corepack pnpm lint` / `biome check` | 0 errors, ≤5 warnings | | |
| S3 | Login | User can log in with known credentials | Dashboard renders | | |
| S4 | Nav | Top-level pages load without 500 / WSOD | | | |
| S5 | Logs | Check server logs during smoke run | No CRITICAL / ERROR entries | | |

---

## 3. Security / Compliance Spot-checks (for human reviewer)

Not automated — done once before PR merge:

- [ ] Review all env var references in diff: no secrets committed (confirmed via git grep patterns)
- [ ] Review PII handling: no raw email / phone in logger output in code or server logs
- [ ] All new URLs with DB hosts: confirm they point to dev/staging (blocked patterns: `rds.amazonaws`, `supabase.co`, `neon.tech`)
- [ ] Destructive SQL (DROP/TRUNCATE/DELETE): confirm `NODE_ENV` guard + explicit consent check or migration-only

---

## 4. Rollback Plan

If we deploy and find issues, how to undo:

```
# Git: revert merged PR commit
git revert <commit-hash>
git push

# DB: if migration was destructive
- Run down-migration / restore backup snapshot from before deploy.

# Config / env vars:
- Revert to prior values in Vercel/Railway dashboards.
```

---

## 5. Sign-off

| Role | Who | Date | Comments |
|------|-----|------|----------|
| Dev who implemented | — | — | |
| SM orchestrated | — | — | |
| QA ran gates | — | — | |
| Final human manual tester | — | — | |

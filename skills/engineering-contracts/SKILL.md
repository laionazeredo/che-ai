---
name: "engineering-contracts"
description: "HIGHEST-PRECEDENCE engineering rulebook for ALL tasks (CANONICAL — DO NOT duplicate pure engineering rules anywhere else). Formal precedence 1-17 of KISS/YAGNI/blast-radius over everything else; forces strict typing, Design by Contract, TDD/ATDD, functional-core/imperative-shell, Rust-style Result/Option, observability, conventional commits, Supabase Postgres ENABLE RLS default, agile BDD incremental delivery with SOLID, code-review optimization (max 2 lines comment block + gh-stack multi-PR reference). Invoked FIRST by harness-developer before any code. Respected by all harness skills. Appendices: A Hard Conflict Resolution Table, B Conventional Commits types + regex + examples, C gh-stack Workflow Reference."
---

# Engineering Contracts (Highest Precedence Rules — CANONICAL)

This is the **authoritative rulebook** for every coding task in the harness.
It is invoked by `harness-developer` FIRST, and its rules **trump local repo conventions when they conflict** — except for Rule 3 ("repo style wins unless undefined").

> **DUPLICATION POLICY:**
> Pure engineering rules (precedence order, DbC, TDD, strong typing, security, conventional commits, RLS, agile BDD, SOLID, code review optimization) LIVE EXCLUSIVELY HERE.
> They MUST NOT be duplicated in `HARNESS_RULES.md`, `user_rules`, `AGENTS.md` or any other location. Those files may only REFERENCE (link) this skill, never reproduce full bodies.
> `HARNESS_RULES.md` owns ONLY process/flow (worktree ask, gate order, parallelism algorithm, PRD G1-G10, gh-stack planning triggers, GitHub integration UX).

> When two rules seem to conflict: the rule higher in this precedence list wins.
> When this rulebook and a repo's local `AGENTS.md` conflict: **THIS rulebook wins** because it is global user policy. Local `AGENTS.md` can only ADD rules, not OVERRIDE these.

---

## PRECEDENCE ORDER (1 = highest, hard stop; 17 = lowest)

### 1. 🔴 KISS + YAGNI + BLAST RADIUS REDUCTION (above ALL other rules)

> These are not "nice to have". They are hard constraints. If any other rule on this list would force you to violate one of these — **VIOLATE THE LOWER RULE, NOT THESE.**

- **KISS (Keep It Simple, Stupid):** If there are two ways and one is simpler (less indirection, fewer files, fewer abstractions), **pick the simpler one always.**
- **YAGNI (You Ain't Gonna Need It):** Do NOT add infrastructure, abstraction, configuration, module, parameter, feature, OR extensibility point "because future use will need it." Only code what the current, explicit Acceptance Criteria DEMAND.
- **Blast radius reduction:** Change as few files and as few lines as strictly necessary. Prefer editing 1 function in 1 file to creating 3 files + a pattern. If a PR has >10 files touched → STOP and re-evaluate.

### 2. 🔴 SECURITY & PII COMPLIANCE (hard stop)

If you detect a security or PII leak risk:
1. **DO NOT write that code** in that form.
2. Stop and design a safer version.
3. If unsure → log to `decision.log.md` + escalate.

- Never log secrets, API keys, raw passwords, JWTs, session tokens.
- Never persist or log raw recipient email addresses or email bodies. Use hashing for correlation.
- Never log full environment variables, especially with keys/secrets.
- **Supabase Postgres DEFAULT RULE (see also §17):** Every NEW table created MUST have Row Level Security (RLS) enabled + explicit policies defined. Tables without RLS are blocked unless explicit exception logged + user approved in `decision.log.md` + Non-Goals of PRD.

### 3. 🟠 REPO EXISTING STYLE & CONVENTIONS (win unless undefined)

- If the repo has a **clear, established pattern** for something (testing framework, DI style, folder structure, naming conventions), **follow it exactly.**
- If the repo has `AGENTS.md`, `docs/`, `CONTRIBUTING.md`, `docs/architecture-decisions`, read them FIRST.
- If the codebase has **existing instances** of what you need → **REUSE / EXTEND, never create anew.**
- Only apply "default Engineering style" (Rules 4-13) when the repo is FRESH (no code yet) or genuinely ambiguous (2+ conflicting patterns with no clear majority).

### 4. 🟠 REUSE BEFORE CREATE

Before adding:
- a new **class**
- a new **module / file**
- a new **dependency** (npm/pip/cargo/go mod)

**MANDATORY check (must be answered in writing as part of task):**
1. Does a function/class/service already in the codebase that does ≥80% of this job exist? → Yes/No
2. If yes: Can I extend / wrap / parameterize it instead of creating new code? → Yes/No
3. If no: write a 1-line justification why reuse is not viable.

**New dependency threshold:** Adding a dependency requires explicit user/SM approval unless it was already listed in the TASK ENVELOPE.

### 5. 🟡 STRICT STRONG TYPING (any language)

- **No `any` / `void*` / `Variant` without explicit casting + type guard.** Prefer `unknown` in TS; prefer generics; in Rust use `dyn Trait` carefully, etc.
- Validate ALL data coming **from outside the system boundary** — DB rows, API responses, JSON parse, form inputs, env vars. Type guard + narrow to a strict type before use.
- Use type guards, `Record<K,V>`, utility types, and `satisfies` operator when they strengthen the contract without verbosity.

### 6. 🟡 DESIGN BY CONTRACT (public functions)

For every **public** (exported / module boundary) function:
- **Preconditions** (input requirements): written as runtime validation + strong type. If violated: return Error / Result::Err — never proceed with invalid input.
- **Postconditions** (output guarantees): documented via return type. If a function can fail in multiple ways → use discriminated union (not exceptions).
- **Invariants**: what must remain true (state is consistent, domain rule preserved).

### 7. 🟡 FUNCTIONAL CORE / IMPERATIVE SHELL (architecture default)

- **Core = pure functions**: business logic, rules, calculations, transformations. No IO, no side effects, deterministic.
- **Shell = imperative thin layer**: reads env, DB, files, HTTP, logger. Composes pure functions from the core; contains all the "wiring".
- If architecture is unclear for a new module: default to FC/IS unless repo has another pattern (Rule 3).

### 8. 🟡 FUNCTIONAL STYLE PREFERRED (when fits)

When the language/stack allows it AND it improves readability (Rule 1):
- **Pure functions:** no mutation, no IO, same input → same output.
- **1-2 arguments max per function.** If more needed → wrap in a single typed `options` / `input` object.
- **Return a Result value over void.** If nothing to return, return `Ok<void>` or equivalent so caller can chain.
- **Early return / flat functions:** avoid nested if / try-catch pyramids. Validate inputs FIRST → bail out. Happy path is flat.
- **`throw` only for truly unrecoverable** states. Expected error paths → use Result / Either / discriminated error types.
- **Immutable data when possible.** Prefer `.toSorted()`, `.slice().sort()`, spread `{...obj, field: new}`, over mutation.
- **Declarative data transforms: `.map() / .filter() / .reduce() / .sort() / .flatMap()`**, when readable, over for/mutable-accumulator loops.
- **Function composition** via pipes / helpers, when the language supports.

### 9. 🟢 RUST-STYLE ERROR MANAGEMENT (when applicable)

When the task needs richer error handling than a simple boolean / nullable:
- **Result type:** `Result<T, E>` or discriminated union `{ ok: true, value: T } | { ok: false, error: E }`
- **Option type:** `Option<T>` or `T | null` with explicit narrowing (not nullable + optional together)
- **Discriminated error variants:** use a tagged union for each error path so caller can match and handle specifically

Use for: service boundaries, validation functions, IO operations (DB, HTTP, file).
Don't overuse for trivial pure helpers.

### 10. 🟢 ATDD + TDD (test-first before behavior changes)

**Behavior change = test first.** If you are about to:
- change existing behavior (function signature, return value, ACs)
- add new behavior (new feature)
then **WRITE THE TEST THAT CAPTURES THE DESIRED BEHAVIOR FIRST.**
Run it. Confirm it FAILS. Then implement. Only then the test must PASS.

Granularity:
- **Pure domain logic / pure functions:** Unit tests covering each behavior / precondition / postcondition / invariant.
- **Public application boundary (API endpoint, server action, UI form submit):** E2E-style integration tests per acceptance criteria (Given/When/Then scenarios).
- **Follow existing repo test framework** (Rule 3). If none → ask user before adding one.

### 11. 🟢 ACCEPTANCE CRITERIA & STOP CONDITION

- Every task has defined Acceptance Criteria (ACs). If you finish the ACs → **STOP.** Do not keep polishing / refactoring / adding features "while I'm here."
- If ACs are not clearly defined → **STOP coding** and go back to Scrum Master / ask user for clarification.
- Know exactly "when am I done" before writing line 1.

### 12. 🟢 OBSERVABILITY & LOGGING

Establish logging points for every flow that has:
- IO (HTTP request, DB read/write, file system)
- Long running / complex pipeline
- State transitions that could fail

Logging conventions (use what the repo exposes):
- `info` — start/end of flow
- `debug` — important inputs, decisions, branching paths
- `warn` — handled but unusual state (not failure, but noteworthy)
- `error` — truly unrecoverable / escalation-needed (with structured context, NOT full stack dump to stdout by default)

Always sanitize PII: hash, mask, or omit. Never log raw email/phone/PII fields.

### 13. 🟢 LANGUAGE & CONTENT FORMAT

- **All source code:** English identifiers, English comments, English string literals for messages.
- **All git commit messages:** English only, conventional commits (see §14).
- **All conversational responses to the user:** Portuguese.
- **Internal harness docs (task_graph, envelopes, decisions, summaries, gh_stack_plan):** English.

### 14. 🟢 ATOMIC COMMITS + CONVENTIONAL COMMITS (default; override only if repo defines own)

- Break large implementations into **atomic, meaningful commits** (one logical change each with a clear diff intent).
- Follow conventional commits pattern:
  `type(scope): imperative description`
- **FULL types list + regex + examples:** Appendix B (canonical).
- **Important:** If repo already defines its own commit convention (Rule 3) → repo convention WINS. This is the DEFAULT only when undefined.

### 15. 🔴 AGILE BDD INCREMENTAL DELIVERY WITH SOLID (NEW — HARD RULE)

> **Problem this rule fights:**
> LLMs + overly-complex PRDs → "kitchen sink" implementations anticipating 50 edge cases NOT in the AC → late delivery, overengineered, hard-to-review, fragile.

This rule turns "agilidade" from vague talk into enforceable checkpoints:

1. **YAGNI on steroids — think "smallest shippable increment".**
   - Deliver the MINIMUM unit of value that validates EXACTLY the current ACs.
   - DO NOT anticipate edge cases, generic abstractions, future-use parameters "because we will need this later."
   - ONLY implement what BDD behavior (Given/When/Then scenarios) explicitly demands.
2. **BDD mindset — behavior over structure.**
   - Deeply understand the expected behavior (what the SYSTEM should do, for which persona, with which side-effect).
   - Always start from BDD scenarios. Code structure is a consequence of behavior, not the other way around.
3. **Small increments = multiple PRs when useful.**
   - When scope is large (more than ~15 files, or more than ~6 independent ACs):
     - **BREAK scope into multiple self-contained PRs.**
     - **PLAN the hierarchy via `gh-stack` CLI** (Appendix C) to maintain order and links between dependent PRs.
     - Each PR must have own ACs, own tests, and pass CI individually.
     - The goal here is **to facilitate code review.** PRs ≤ 400 diff lines + 15 files = human reviewable. >800 lines = superficial review → risk.
4. **SOLID as guardrails for evolvability (NOT over-abstract).**
   - Single Responsibility: each module/function has 1 reason to change.
   - Open/Closed: open for extension (clear entry point) BUT closed for modification of what already works. DO NOT break existing behavior.
   - Liskov: subtypes substitutable.
   - Interface Segregation: small interfaces per client.
   - Dependency Inversion: depend on abstractions (contracts), not concretes.
   - **But KISS always wins.** DO NOT create 3 interfaces just "to be SOLID" if one pure function solves it.
5. **Behavior golden rule:**
   - NEVER break existing behavior without an EXPLICIT AC asking for the break.
   - If you need behavior breaking: NON-GOALS, Data Model + Migration with rollback plan, and explicit user approval.

### 16. 🔴 CODE REVIEW OPTIMIZATION + COMMENT LINE LIMIT (NEW — HARD RULE)

> **Goal:** Write code that a senior engineer can review in 5 minutes per 150 diff lines, with near-zero back-and-forth on style/verbosity.

Rules enforced on EVERY implementation:

1. **Clean, non-verbose code.**
   - Clear names, small functions, single responsibility.
   - Dead code (commented or not) is NOT committed.
   - Log statements only where meaningful (§12). DO NOT log "got here" in every function.
2. **Max 2 consecutive lines of comment block per file.** (HARD LIMIT, with explicit exceptions)
   - **Allowed comments (count toward limit):**
     - Non-obvious trade-off explanations (e.g. `// Using linear scan here because N <= 16 always and preallocated hashmap overhead wins for hot path`).
     - TODO/FIXME flags with issue/ticket: `// TODO(FLO-789): Refactor to batch writes once the upstream API supports it.`
   - **Exceptions that DO NOT count toward the 2-line limit:**
     - Docstrings/JSDoc/TSDoc of PUBLIC functions (API boundary) — describe pre/post-conditions (§6 DbC).
     - 1-line isolated inline comments not forming a contiguous block.
   - **If you need 3+ consecutive comment lines to explain something:**
     - That is a *code smell*. The code is too complex. Refactor into smaller, clearly-named functions.
     - If still needed (e.g. workaround for a very specific library bug): **LOG an exception in `decision.log.md`, with justification.**
3. **Code review mindset — write comments as if you're the reviewer.**
   - What questions would a reviewer ask? Answer them in the function name, not in a comment.
   - Ship PR body explains WHAT and WHY, not HOW (how = code).
4. **gh-stack hierarchy for PR chains (see Appendix C).**
   - When multiple PRs: harness uses gh-stack and each PR body shows "Depends on: #PR" — reviewer knows the correct order.

### 17. 🟠 SUPABASE POSTGRES — ENABLE RLS BY DEFAULT (GLOBAL SECURITY RULE)

> This is now a GLOBAL engineering rule, not just Flockr-specific. Any repo that uses Supabase / Postgres MUST follow this.

Rule:
1. **For EVERY new table:** immediately add `ALTER TABLE <schema>.<table> ENABLE ROW LEVEL SECURITY;` in the migration.
2. **Define explicit read/write policies per role** (e.g. `organizer_select_policy`, `admin_all_policy`). A table with RLS enabled but ZERO policies = no rows can be read/written (default deny) — good.
3. **Add an Acceptance Criteria in the PRD spec (if using harness-prd) specifically for RLS:** e.g. `AC-RLS: Organizer A cannot read or write tickets/events owned by Organizer B (403 or 404 as appropriate).` This is validated during QA.
4. **ONLY exception (allowed logged + user approved double confirmation):**
   - Pure lookup tables (enum reference tables, immutable public seed data for everyone) → RLS not needed, BUT:
     - Explicitly mark in Non-Goals / Data Model notes.
     - Log exception + user approval in `decision.log.md`
     - Table name + reason documented in migration notes.

---

## Appendix A — Hard Conflict Resolution Table (CANONICAL)

If you face a trade-off where two rules seem to pull opposite directions:

| Conflict | Winner | Rationale |
|---|---|---|
| KISS (§1) vs Functional Composition (§8) | KISS | Reduce complexity even if a "beautiful" composition is possible. |
| YAGNI (§1) vs Extensibility pattern (§8) | YAGNI | Don't build extension hooks today just because. |
| New abstraction vs Reuse (§3 + §4) | Reuse | Wrap/extend existing; only new abstraction as last resort. |
| DbC strictness (§6) vs KISS (§1) on a tiny 5-line internal helper | KISS | DbC is mandatory ONLY at public boundaries. Internal tiny helpers can be relaxed — but never safety. |
| Pure function (§8) vs performance — hot loop needs mutation | Performance + decision.log entry | Mutability OK inside the core if measured faster. Log the trade-off. |
| TDD (§10) vs tiny bugfix of obvious typo | Either — but verify test exists or add one. | For 1-char typo fix: fine to patch, but ensure afterward a regression test exists for that path. |
| Security (§2) vs KISS | Security | Never trade security for simplicity. Simplify in a SAFER way. |
| Conventional Commits (§14) vs repo uses different commit format | Repo format (§3) | §3 says repo convention wins when defined. §14 is the DEFAULT when no convention exists. |
| Agile BDD smallest increment (§15) vs "I can add this extra nice-to-have in 2 lines" | BDD smallest (§15 = YAGNI in action) | DO NOT add. Nice-to-have = separate PR. Scope = scope. |
| Code Review Opt max 2 lines comment (§16) vs trade-off explanation | May do 3+ LINES ONLY with logged exception in decision.log | No log = violation. Usually a more clearly-named function is enough. |
| Supabase RLS default (§17) vs "table is tiny, public enum only" | RLS default (§17). Skip ONLY with TWO approvals: Non-Goals + decision.log user approval. | See §17 exceptions. |

---

## Appendix B — Conventional Commits: Types + Regex + Examples (CANONICAL)

> This is the DEFAULT convention. If the repo defines another (Rule 3), REPO WINS.

### B.1 Syntax regex (strict)
```regex
/^(feat|fix|docs|style|refactor|test|chore|perf|build|ci|revert)(\([a-z0-9._-]+\))?: [a-z0-9][A-Za-z0-9 _.,'"()\/:@#=-]{0,88}$/
```
Rules:
- type: lowercase, one of the 11 below.
- scope: optional, lowercase with allowed separators `._-`, between parens.
- colon + space after type/scope.
- description: imperative, starts lowercase, max 88 characters (keep under 100 for terminal wrap). Max total line ≤ 100 chars.

### B.2 Types (11) + when to use each
| Type | Semantic version | When to use |
|---|---|---|
| `feat` | minor (x.y.z → x.Y.0) | New feature for the user. Shipped behavior change ACs. |
| `fix` | patch (x.y.z → x.y.Z) | Bug fix for the user. Ex.: checkout double-click duplicate order, 500 on null. |
| `docs` | - | Documentation only changes: README, docs/, inline docstrings public APIs (docstring-only commits with no code change). |
| `style` | - | White-space, formatting (Biome/Prettier apply), missing semi-colons, quoting style change. NO code behavior change. |
| `refactor` | - | Code change that NEITHER fixes a bug NOR adds a feature. Rename, extract fn, simplify, dead-code-remove. Behavior preserved. |
| `test` | - | Adding missing tests or correcting existing tests. |
| `chore` | - | Updating grunt tasks etc; no production code change. Dependency bumps (lockfile) without behavior change, tooling config, CI scripts (if trivial; complex CI = `ci`). |
| `perf` | patch | Code change that improves performance (ex: hot path cache, O(n²)→O(n)). |
| `build` | - | Changes that affect the build system or external dependencies (ex: Vite/tsconfig major change, Webpack config, Dockerfile build stage). |
| `ci` | - | Changes to CI configuration files and scripts (ex: GitHub Actions, CircleCI config YAML, Nx workspace target changes). |
| `revert` | - | Reverts a previous commit. Convention: `revert: feat(payments): add apple pay` then in the body the commit hash being reverted. |

### B.3 Examples
```
feat(auth): add password hashing with argon2id
fix(checkout): prevent duplicate orders on retry (double click 500ms)
test(user): cover register endpoint with malformed email edge cases
perf(dashboard): cache organizer event list for 60s
refactor(checkout): extract tax calculation pure fn
build: upgrade next.js 15 → 16
ci: add typecheck step to platform nx job
docs: add architecture decision 7 — idempotency keys
chore(deps): bump stripe-sdk 18.4 → 18.5 (patch)
```

---

## Appendix C — gh-stack Workflow Reference (CANONICAL — new)

### C.1 What is `gh-stack`
`gh-stack` (https://github.com/github/gh-stack) = official gh CLI extension that:
1. Creates a chain/stack of DRAFT PRs each depending on the previous one (base branch hierarchy).
2. Updates PR bodies with "Depends on: #123 · Stacks against main" links so reviewers understand order.
3. Supports rebasing the whole stack when lower PRs get fixes.

### C.2 Preconditions to use gh-stack (harness-scrum-master validates in planning)
1. Task Graph ≥ 3 tasks OR one task > 15 files blast radius.
2. Tasks can be semantically grouped into "PR layers" (ex: PR1=types/contracts, PR2=service layer + unit tests, PR3=API + e2e tests).
3. User did NOT explicitly say "single PR please".
4. Worktree is clean of uncommitted changes OUTSIDE the envelope (standard check).

### C.3 Stack planning (Scrum Master step — gh_stack_plan.md structure)
```
# GH STACK PLAN — <slug>
Status: DRAFT (approved by user: YYYY-MM-DD HH:MM)

| Order | PR# (placeholder) | Title conventional commit | Base branch | Head branch | Tasks/ACs covered | Approx files |
|---|---|---|---|---|---|---|
| 1 (bottom) | — | feat(contracts): add refund data model + enums | main | feat/refund-contracts | T1 (contracts), AC-1/2/3 | ≤6 |
| 2 | — | feat(payments): implement refund service with Stripe API | feat/refund-contracts | feat/refund-service | T2/T3 (service + unit tests), AC-4–9 | ≤14 |
| 3 (top) | — | feat(admin): refund dashboard UI + tRPC routes | feat/refund-service | feat/refund-admin-ui | T4 (UI), AC-10–13, smoke | ≤12 |

Notes:
- If PR2 needs a fix after review: fix on feat/refund-service, then `gh-stack rebase` auto-rebases PR3 on top of the new PR2 head.
- After PR1 merged to main: `gh-stack update` rebases PR2→main, PR3→new PR2.
```

### C.4 Standard gh-stack commands (harness-ship reference)
```bash
# Install (1x per machine)
gh extension install github/gh-stack

# Create full stack after all local branches created + commits
gh-stack create --draft  # opens ALL PRs as DRAFT with dependency links in body

# Update stack after commit on a middle branch (rebase everything)
gh-stack rebase

# Check stack status
gh-stack status

# After PR1 merged → rebase remaining stack on main
gh-stack update --base main
```

### C.5 Harness rules enforced on gh-stack
- Stack ALWAYS starts DRAFT. Single "ready for review" = user explicitly asks.
- Each individual PR passes CI individually (QA + light compliance per PR).
- If any PR in the stack has blast radius > 20 files → SM goes back to planning and re-breaks it.
- Body of each non-base PR MUST open with `Depends on: #<previous-pr-number>` (gh-stack does this automatically, but harness validates).

---

## Final Reminder

These rules are **intentionally strict.** They exist because:
- LLMs love over-engineering. §1 + §15 fight that.
- LLMs love creating new abstractions. §3+4 fight that.
- LLMs skip tests until after. §10 fixes that.
- LLMs leak secrets/PII accidentally. §2 + §17 prevent that.
- LLMs write overly-commented/verbose code hard to review. §16 forces clean/concise code.
- LLMs anticipate future and deliver giant PRs. §15 + gh-stack Appendix C forces small incrementals.

If any rule feels wrong for a specific case → **log the exception + rationale to `decision.log.md` under `.trae/<task-id>/`**, and proceed.

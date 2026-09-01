---
name: "engineering-contracts"
description: "HIGHEST-PRECEDENCE engineering rulebook for ALL tasks (CANONICAL — DO NOT duplicate pure engineering rules anywhere else). Formal precedence 1-18 of KISS/YAGNI/blast-radius over everything else; forces strict typing, Design by Contract, TDD/ATDD, functional-core/imperative-shell, Rust-style Result/Option, observability, conventional commits, Supabase Postgres ENABLE RLS default, agile BDD incremental delivery with SOLID, code-review optimization (max 2 lines comment block + gh-stack multi-PR reference), agent response verbosity budget (concise by default with optional deep-dive prompts). Invoked FIRST by harness-developer before any code. Respected by all harness skills. Appendices: A Hard Conflict Resolution Table, B Conventional Commits types + regex + examples, C gh-stack Workflow Reference."
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

## PRECEDENCE ORDER (1 = highest, hard stop; 18 = lowest)

### 1. 🔴 KISS + YAGNI + BLAST RADIUS REDUCTION (above ALL other rules)

> These are not "nice to have". They are hard constraints. If any other rule on this list would force you to violate one of these — **VIOLATE THE LOWER RULE, NOT THESE.**

- **KISS (Keep It Simple, Stupid):** If there are two ways and one is simpler (less indirection, fewer files, fewer abstractions), **pick the simpler one always.**
- **YAGNI (You Ain't Gonna Need It):** Do NOT add infrastructure, abstraction, configuration, module, parameter, feature, OR extensibility point "because future use will need it." Only code what the current, explicit Acceptance Criteria DEMAND.
- **Blast radius reduction:** Change as few files and as few lines as strictly necessary. Prefer editing 1 function in 1 file to creating 3 files + a pattern. If a PR has >10 files touched → STOP and re-evaluate.

### 2. 🔴 SECURITY & PII COMPLIANCE (hard stop)

If you detect a security or PII leak risk:
1. **DO NOT write that code** in that form.
2. Stop and design a safer version.
3. If unsure → log to `decisions.log.jsonl` + escalate.

- Never log secrets, API keys, raw passwords, JWTs, session tokens.
- Never persist or log raw recipient email addresses or email bodies. Use hashing for correlation.
- Never log full environment variables, especially with keys/secrets.
- **Supabase Postgres DEFAULT RULE (see also §17):** Every NEW table created MUST have Row Level Security (RLS) enabled + explicit policies defined. Tables without RLS are blocked unless explicit exception logged + user approved in `decisions.log.jsonl` + Non-Goals of PRD.

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
6. **Test-suite naming = behavior observable ONLY (REGRA 7.9 do harness).**
   - **`describe("...")`** = module/feature/context UNDER TEST (domain grouping, not task IDs).
     ✅ `describe("POST /api/payments/refund")`
     ❌ `describe("FLO-513 T2 — process refund ACs 3.1-3.4")`
   - **`it("...")` / `test("...")`** = ONE observable behavior, starts with verb (returns/allows/blocks/calculates/emits/saves…) + condition + expected outcome. ONE assert when possible.
     ✅ `it("returns 409 Conflict when refunding an already-refunded payment")`
     ❌ `it("Task T2.3 valida regra do §4.2 se pagamento ja foi estornado")`
   - **NEVER embed internal IDs (FLO-XXX / task T\d+ / AC\d+ / SPEC-\w+ / §N) in the TITLE STRING.** If you need traceability to an AC/ticket/spec: use a 1-line JSDoc comment ABOVE the block OR a single `// @ac 3.1 | @task T2 | @ticket FLO-513` comment as FIRST LINE INSIDE the test block body.
   - Suite organization: group tests BY DOMAIN / CONTEXT. Nested `describe()` = more specific context (e.g. `describe("POST /refund").describe("with currency GBP")`).

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
     - If still needed (e.g. workaround for a very specific library bug): **LOG an exception in `decisions.log.jsonl`, with justification.**
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
3. **Add an Acceptance Criteria in the SPEC (if using harness-spec standalone or /harness-start SM §0.5 SPEC gate) specifically for RLS:** e.g. `- [MUST] AC-RLS GIVEN Organizer A authenticated WHEN querying tickets/events owned by Organizer B THEN HTTP 403 or 404 returned | TEST=qa_integration` literal format in §4. This is validated during QA.
4. **ONLY exception (allowed logged + user approved double confirmation):**
   - Pure lookup tables (enum reference tables, immutable public seed data for everyone) → RLS not needed, BUT:
     - Explicitly mark in Non-Goals / Data Model notes.
     - Log exception + user approval in `decisions.log.jsonl`
     - Table name + reason documented in migration notes.

---

### 18. 🟢 AGENT RESPONSE STYLE — Concise by Default + Deep-dive Prompt Gate

> **This rule controls the verbosity and shape of agent responses to the user. It is the CONTROLLED by user preference feedback. It has lower precedence than code quality rules (1–17), BUT it is higher priority over "be helpful" defaults. If violating this rule makes a code change in the output does not affect function correctness only; it affects UX of the agent. THIS IS A HARD RULE to avoid reading fatigue for the user.

Canonical output:
1. **Default response budget = MAX 6–12 sentences / 250–500 words CONCISE.
   - If you need more words to explain something, YOU ARE THINKING WRONG. Simplify. Cut edge cases. Cut examples. Focus ONLY on what user needs to make decision now.
   - Any answer longer than this budget → STOP. Prune. Remove everything not directly related to user's immediate question or immediate actionable next step.

2. **FORMATTING RULES FOR DIAGONAL READABILITY (non-negotiable, applies to ALL default outputs — not just code. This is the STYLE layer on top of verbosity budget.):**
   a. **Logical sectioning = `###` or `##` headings.** Break answers into 2-4 logical sections MAX. Each section clearly labeled. Never a single unbroken wall of text.
   b. **One bullet per line = always use `-` / `•` lists.** Almost never write 3+ consecutive sentences of body prose without a bullet break. Paragraph blocks (3+ sentences without a bullet) = code smell → refactor to bullets.
   c. **Emphasis on the most important 2-5 words.** Bold (**`**word**`**) every key noun/decision. Italics (**`_word_`**) for nuance/caveat. Underline (**`<u>word</u>`**) for the single MOST critical call-to-action or CRITICAL consequence. Maximum 1 underline per output.
   d. **1 thought per bullet.** Each bullet = ≤2 lines. If a bullet needs 3+ lines → split into sub-bullets.
   e. **Code references always formatted as links.** Use the clickable `[display_name](file:///absolute#LLx-Ly)` format (per workspace rules). Never raw file paths plain text.
   f. **When listing tasks/changes done:** Each bullet starts with a VERB or bolded scope label (e.g. **`• 🔧 Contracts §18:` updated X + Y**). Visual scanning > grammar perfection.

3. **Four allowed sections ONLY (use exactly what's needed; omit empty sections if not applicable):
   - ✅ **(A) 📍 Status / Exec Summary (1–2 sentences):** Exactly what DONE / current state.
   - ✅ **(B) 🧩 Key Changes (3 bullets MAX, 1 thought each):** Most important outputs. Each = `• **Label**: <1 line detail>` format.
   - ✅ **(C) 🔗 References (optional):** Link 2–5 most important files touched, with #Lx-Ly ranges only where section matters.
   - ✅ **(D) ❓ 1 Deep-dive Offer (only ONE topic):** "Quer aprofundar em **<X>`** (Yes/No)?". Never a menu.
   - ❌ NO long introductions, NO "como foi bom trabalhar com você" fluff, NO 8 bullets of 20 options, NO explanations of "why the tool was chosen" unless EXPLICITLY ASKED.
   - ❌ NO as a general rule, every time you spend more than 2 paragraphs explaining background context and the user hasn't asked for context → you violated.
   - ❌ NO 5 alternate options list to the user. Only offer choice. Maximum TWO choices maximum (either A or B). If >2 → STOP, stop yourself, pick best guess / default), OR just do it and tell them what you chose + ask "ok if they don't agree.

4. **Plans / Paths Options offering = bullet points / choices:
   - Minimum viable plan bullets: MAX 3 steps shown first. If there are more — offer "quer o restantes podem ser adicionados se aprofundar later.
   - Edge cases: Mention ONLY P0 / CRITICAL ones (≤2 max). Everything else → "Se surgirem edge cases intermediários durante a implementação, voltamos aqui." Do NOT list all 8 edge cases upfront.
   - NO giant tables of everything that could go wrong. Behaves like: only list "C critical

5. **Deep-dive gate (this is the only place longform lives):
   - WHEN user says "explain deeper" / "mais detalhes sobre X" → THEN you can write full explanation on THAT TOPIC ONLY. Formatting rules (sectioning, bullets, emphasis) STILL APPLY even in deep-dives. Never relax format just because it's longform.
   - Each deep-dive response respects: ONE topic per response. If user wants multiple → iterate.
   - NEVER anticipate deep-dives are always driven USER. Not agent writes first.

6. **User profile enforcement (default rules embody):**
   - "Altamente objetivo, conciso e orientado a tarefas." This + diagonal readability = this rule.
   - Violation examples NOT allowed. Always think before you write. Trim, trim, trim again.
   - If you write a draft response that: (a) has 3+ consecutive sentences no bullet, (b) no headings, (c) no bold on key words, (d) more than 1 underline → STOP, delete half, reformat SHAPE per 2a–2f BEFORE sending.

---

### 19. 🔴 WORKTREE SESSION BINDING — One Session = One Worktree. Doubt = Ask.

> **This rule controls worktree scoping during a chat session. It is a HARD SCISSORS rule — violating it causes wrong-code commits on wrong worktrees (data loss). Higher precedence than "be helpful / be efficient" defaults. Lower precedence only than safety rules (§2 Security / §6 DbC). It applies to ALL harness skills and direct chat file operations.**

#### 19.1 HARNESS SESSIONS ROOT (PATH CONTRACT — all mutable/generated data lives here)

**Immutable harness code (skills, commands, hooks, rules, references) STAYS in `$HOME/.trae/`.** Never put generated output there.  
**Generated output (session bindings, task graphs, decisions, QA evidence, design docs, summaries) MUST LIVE under `$HARNESS_SESSIONS_ROOT` (default: `$HOME/code/harness-sessions`).** One flat parent folder per user.

Path layout (CANONICAL — all skills/commands MUST build paths by calling the contract script `$HOME/.trae/contracts/harness_sessions_contract.sh`; NEVER hardcode):
```
$HARNESS_SESSIONS_ROOT/
└── <WORKSPACE_NAME>/                            # Ex: Flockr  (from Flockr.code-workspace)
    └── <WORKTREE_SLUG>/                         # CANONICAL <repo>__<branch-or-worktree-basename>  (2 underscores)
        │                                        #   Lumos worktree pattern: parent dir Lumos.worktrees/<slug> → slug = Lumos__<slug>
        │                                        #   Plain repo pattern: git dir Lumos, branch feat/X → slug = Lumos__feat--X
        ├── workspace/                           # DURÁVEL / per-worktree. Compartilhado entre múltiplas sessões. NUNCA apaga.
        │   ├── task_graph.md                    # (OBSOLETE per-task layout: agora um task_graph compartilhado por worktree por task-id)
        │   ├── decisions.log.jsonl                 # trade-offs / exceções / non-obvious decisions
        │   ├── gh_stack_plan.md                 # se ≥3 tasks ou >15 arquivos
        │   ├── manual_test_plan.md              # plano manual de smoke/QA
        │   ├── design/                          # (seu item 4:) documentos de design do harness, ADRs, figures
        │   └── tasks/<TASK_ID>/                 # arquivos PER-TASK duráveis (envelope, scope, acceptance criteria)
        │
        └── sessions/
            └── <SESSION_ID>/                    # EFÊMERO / per-sessão. Apagável após sessão fechar (exceto binding history audit).
                ├── binding.md                   # Level 2 DETAIL (§19.3) — audit/rebind chain
                ├── qa/                          # evidências de /harness-manual-test
                │   ├── screenshots/*.png
                │   └── logs/*.jsonl
                ├── reports/                     # PR review reports, diff reports, batch reports
                └── summary.md                   # re-summaries / milestones da sessão

RESOLVER (authoritative): `$HOME/.trae/contracts/harness_sessions_contract.sh`
  - source harness_sessions_contract.sh
  - harness_compute_paths <WORKTREE_ROOT> <SESSION_ID> <current-cwd>
  - exports: HARNESS_WORKSPACE_NAME / HARNESS_WORKTREE_SLUG / HARNESS_WORKSPACE_SHARED / HARNESS_SESSION_DIR / HARNESS_LEVEL2_BINDING
  - ensure dirs: harness_ensure_session_dirs
```

MORATÓRIA (hard stop): NENHUM arquivo `.md` ou `.json` ou `.png` gerado pelo harness é escrito em `<WORKTREE_ROOT>/.trae/*` a partir de agora. Isso evita git status sujo / commit acidental de evidências de QA / decisions / etc.

Binding contract:

1. **1 session ↔ 1 WORKTREE_ROOT by default.**
   - The very first operation of a harness flow (or first file access in a worktree scoped session) MUST produce a binding decision: which absolute worktree path is this session attached to?
   - **MOVE FORWARD: O usuário deve ser perguntado qual o FRIENDLY_NAME da pasta desta sessão imediatamente após binding ser criado. Regra: Pergunta 1 única, no momento em que binding é criado: "Qual o nome amigável dessa pasta (slug short)?". Resposta user é salva em Level1 campo FRIENDLY_NAME e vira sub-papel de SESSION_DIR se definido. NÃO é obrigatório.**
   - **2-LEVEL LAYOUT (resolves chicken-and-egg + multi-session parallelism + zero race condition + per-session FLAGS + never pollutes worktree git status:**
     - **Level 1 (GLOBAL INDEX / CHICKEN-AND-EGG SOLVER):** 1 unique per user, outside worktrees + sessions dir. Path: `$HOME/.trae/bindings/registry.jsonl`. One entry per SESSION_ID, append-only (never overwrite, just add new lines).
       ```
       SESSION_ID: <session-identifier-from-ide>
       WORKTREE_ROOT: <absolute path>
       TASK_ID: <slug or manual>
       FRIENDLY_NAME: <optional slug-for-user, pergunta na hora do binding>
       BOUND_AT: <ISO timestamp>
       STATUS: BOUND
       FLAGS: LANG_PT_CHECK=DISABLED   (optional line — OMIT line entirely when default ENABLED)
       ---
       ```
       Optional fields (OMIT when defaults suffice — keep registry minimal):
       - `LANG_PT_CHECK=DISABLED`: Disables the PostToolUse Portuguese-text detector hook for THIS SESSION ONLY. When line omitted → default ENABLED (hook runs normally). Hook 3 reads this flag per SESSION_ID from Level 1.
       - `FRIENDLY_NAME`: short slug. Se user forneceu no momento do binding, HARNESS_SESSION_DIR vira `<WORKTREE>/sessions/<SESSION_ID>--<FRIENDLY_NAME>/` (facilita navegação humana).
     - **Level 2 (PER-SESSION DETAIL / SESSIONS DIR — NUNCA DENTRO DA WORKTREE DO USUÁRIO):** 1 file per session, **inside the sessions dir da worktree DENTRO DE $HARNESS_SESSIONS_ROOT.** Canonical path:
       ```
       $HARNESS_SESSIONS_ROOT/<WORKSPACE>/<WORKTREE_SLUG>/sessions/<SESSION_ID>[--<FRIENDLY_NAME>]/binding.md
       ```
       Stores re-binding chain history & audit (PREV/NEXT only if worktree switched)+ FLAGS mirror for human readability. Not used for hook scissor checks (only SM/Ship/Dev read it for re-binding audit).
       ```
       SESSION_ID: <session-identifier>
       WORKTREE_ROOT: <absolute path>
       TASK_ID: <slug>
       FRIENDLY_NAME: <same as Level 1 if provided; omit if default>
       BOUND_AT: <ISO timestamp>
       STATUS: BOUND
       FLAGS: LANG_PT_CHECK=DISABLED   (same value as Level 1 if set; omit line if default)
       WORKSPACE_NAME: <canonical from .code-workspace>
       WORKTREE_SLUG: <canonical repo__branch>
       HARNESS_SESSION_DIR: <absolute>  (facilita debug)
       HARNESS_WORKSPACE_SHARED: <absolute>
       # PREV_BINDING: <old detail md path> (after first switch)
       # NEXT_BINDING: <new detail md path> (after switch)
       ```
   - Write once into BOTH during initial binding decision:
     1. Append Level 1 entry via HELPER OFICIAL: `source harness_sessions_contract.sh && harness_registry_append_jsonl <sid> BOUND <wt_root> <payload_json>`. Add Level 2 file inside `$HARNESS_SESSIONS_ROOT/...` (use resolver contract `harness_compute_paths`). Idempotência built-in: helper deduplica por conteúdo sha256, não duplica mesma entry SESSION_ID+STATUS=BOUND já existente. NÃO use Edit/Write manual no registry.jsonl.
   - Scissor checks (hook 1) ONLY use Level 1 registry index; never enter sessions dir to lookup. If SESSION_ID not in Level 1 → binding doesn't exist yet (agent proceeds to binding decision flow §19.2).

2. **Initial binding decision rules (order of precedence — STOP at first match):**
   a. **Explicit user mention:** User said "worktree X" or gave a path → BIND TO X. Confirm once.
   b. **Open files / context window:** User has 1+ files open that are all inside the same worktree → BIND to that worktree. (If files span 2+ worktrees → fall to c.)
   c. **Working directories in <env>:** If there is a single most-relevant working directory (check recent session memory / prior messages) → propose it; else GO TO (2e).
   d. **Binding file exists in sessions dir matched via contract resolver:** Use that.
   e. **Ambiguous (≥2 candidates or 0 clear matches):** STOP. Do NOT guess. Use AskUserQuestion with ≤2 concrete options + "other (type path)".

3. **Re-binding (switching worktree in same session):**
   - Switching is ONLY allowed after EXPLICIT user confirmation: "Yes, switch to worktree X now."
   - When switching (update BOTH levels atomically + contract resolver re-run):
     1. **Level 1 registry update**: Find the SESSION_ID entry, set `STATUS: RELEASED | RELEASED_AT: <ts> | NEXT_WORKTREE_ROOT: <newpath>`, then append NEW BOUND entry for the same SESSION_ID pointing to new worktree.
     2. **Level 2 detail file update**: OLD detail file inside OLD `HARNESS_SESSION_DIR/binding.md` → `STATUS: RELEASED | RELEASED_AT: <ts> | NEXT_BINDING: <new-detail-md-path>`. Create NEW detail file inside NEW worktree sessão dir → `STATUS: BOUND + PREV_BINDING: <old-detail-md-path>`
     3. Announce the switch in the next Status section output.
   - Agent-initiated switches (without user saying so) = violation. Never "oh, this code is in worktree B so let me touch it" without asking first.

4. **Per-operation scissor check (MANDATORY before any git/Glob/Grep/file-write):**
   - Before any file-system write or git command: LOOKUP SESSION_ID in **Level 1 registry $HOME/.trae/bindings/registry.jsonl** (ONLY). Use WORKTREE_ROOT from that entry.
   - If target path is a **USER CODE** file (ou seja, está dentro de WORKTREE_ROOT mas NÃO é um arquivo gerado em $HARNESS_SESSIONS_ROOT) E fica FORA WORKTREE_ROOT → BLOCK. Two outcomes:
     a. User confirms "yes, write outside worktree scope this one user code file" → log decision.log.
     b. Otherwise abort and ask: "This target is outside worktree <X>. Switch first? (A = switch, B = cancel)"
   - Exception to scissor check for HARNESS_GENERATED paths: Arquivos que ficam em **$HARNESS_SESSIONS_ROOT/** são explicitamente FORA do worktree e SEMPRE podem ser escritos após binding criado; não precisa de pergunta por operação.
   - No silent cross-worktree reads without user made aware.

5. **Doubt / ambiguity → ask. Never guess.**
   - "User said refund feature; ≥2 worktrees have refund branches → list ≤2 concrete options AskUserQuestion.
   - Binding Level1 says X but context hints Y → ASK. Never silent switch.
   - User não forneceu FRIENDLY_NAME ainda → perguntar 1 única vez antes de criar arquivos na HARNESS_SESSION_DIR.

6. **Pre-send self-check for scoping:**
   - If draft response contains references to files in ≥2 different worktrees (without user explicitly asking cross-worktree comparison): STOP. Trim. Either focus on 1 worktree, or ask which one first.
   - References (code links) in the output must NOT mix worktree paths unless the user explicitly asked for a cross-worktree diff/comparison.

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
| Worktree §19 binding vs "worktree B seems to have the code I want so let me just touch it" | §19 wins. ASK before switching. Never silent cross-worktree file ops. | AskUserQuestion. User confirms → §19.3 re-binding steps. |

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

If any rule feels wrong for a specific case → **log the exception + rationale to `decisions.log.jsonl` under `.trae/<task-id>/`**, and proceed.

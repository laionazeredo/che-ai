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

### 1. 🔴 KISS + YAGNI + BLAST RADIUS REDUCTION + NO ACCIDENTAL COMPLEXITY (above ALL other rules)

> These are not "nice to have". They are hard constraints. If any other rule on this list would force you to violate one of these — **VIOLATE THE LOWER RULE, NOT THESE.**

- **KISS (Keep It Simple, Stupid):** If there are two ways and one is simpler (less indirection, fewer files, fewer abstractions), **pick the simpler one always.**
- **YAGNI (You Ain't Gonna Need It):** Do NOT add infrastructure, abstraction, configuration, module, parameter, feature, OR extensibility point "because future use will need it." Only code what the current, explicit Acceptance Criteria DEMAND.
- **Blast radius reduction:** Change as few files and as few lines as strictly necessary. Prefer editing 1 function in 1 file to creating 3 files + a pattern. If a PR has >10 files touched → STOP and re-evaluate.
- **🔴 NO ACCIDENTAL COMPLEXITY HARD RULE (aplica-se ANTES de escrever 1ª linha):**
  - **Definição:** Complexidade = Essencial (do domínio, inevitável) vs Acidental (nossa culpa — abstração desnecessária, indireção inútil, configuração genérica prematura, framework X só porque "mundo usa", wrapper por wrapper, etc).
  - **Hard stop processo:** Antes de criar QUALQUER nova abstração / classe / módulo / dependência / CLI flag, você deve se perguntar e responder (registrado mentalmente ou 1 linha em decisions se task for complexa):
    1. "Isso resolve complexidade ESSENCIAL do domínio do negócio / problema atual?"
    2. "Consigo resolver o problema atual SEM isso, com 1 wrapper simples / função inline / parâmetro a mais na função existente?"
    3. "Se eu não fizer isso AGORA, quanto trabalho vai dar para adicionar DEPOIS quando REALMENTE precisar? (≤3 linhas → SEMPRE faça depois; ≤1 dia trabalho → provavelmente também depois)"
  - **Lista VERMELHA de complexidade acidental (qualquer 1 item é motivo para STOP + re-design):**
    - ✋ Interface / Protocol / Abstract class com APENAS 1 implementação concreta HOJE (se não tem 2 implementações hoje, não precisa da abstração ainda)
    - ✋ Dependency Injection container / IoC para ≤5 services (construa manualmente — fábrica de 3 linhas)
    - ✋ Strategy pattern com ≤2 estratégias E a 2ª é "default que quase nunca muda"
    - ✋ Event bus / PubSub interno com ≤2 subscribers (chame direto)
    - ✋ Config / yaml / toml de ambiente para ≤3 flags fixas (env var única basta)
    - ✋ Micro-serviço splitado sem necessidade de deploy independente provada (monólito modular primeiro)
    - ✋ Framework novo inteiro só para 1 feature (ex: instalar LangGraph só para loop que já existe via contracts + gates)
    - ✋ N camadas a mais de indireção "porque arquitetura limpa manda" sem que nenhuma delas resolva um problema real do produto
    - ✋ Função genérica `<T>` quando só existe 1 tipo concreto sendo passado hoje

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

### 12. 🟢 OBSERVABILITY & LOGGING (Pointer)

> **Regras completas expandidas (HARD RULE):** Veja **§19 🔴 LOGGING & OBSERVABILITY STANDARD** nesta mesma skill (depois de §18 GitHub).
> Este §12 é um pointer p/ evitar forward-reference chaos. NÃO DUPLIQUE regras aqui.
> TL;DR rápido daqui: (1) repo pattern first NÃO invente roda; (2) wiring existente primeiro (OTel/pino singleton); (3) 5 níveis (trace/debug/info/warn/error); (4) SEM PII raw; (5) scripts bash = echo prefixado expressivo. Detalhes + volume heurística + anti-patterns em §19.

### 13. 🟢 LANGUAGE CONFIGURATION — 4 EIXOS INDEPENDENTES (por projeto/sessão, NUNCA MISTURAR)

> **HARD RULE VERBATIM USER (contractual):** "nunca misturar linguagens". Cada eixo abaixo tem EXATAMENTE 1 idioma configurado por arquivo/sessão/projeto. Strings UI traduzidas = artefato de i18n em JSON separado (não conta como LANG_CODE).

**Precedência de configuração (HIGH → LOW):**
1. **Override sessão Level 1 registry flags** (`harness_registry_append_jsonl … FLAGS … '{"flags":{"LANG_DOCS":"pt-BR"}}'`) — temporário, só esta sessão.
2. **Project registry Level 1.5** `.registry/projects/<slug>/product_context.md` frontmatter `lang_code:` + `lang_docs:` — durável por projeto, compartilhado worktrees × sessões.
3. **Defaults ABAIXO** se nenhum dos dois acima definiu.

**Os 4 eixos:**

| Eixo | Flag | Default | O que controla — 1 idioma TODO o eixo, sem mistura |
|---|---|---|---|
| **CÓDIGO** | `LANG_CODE` | `en` (INGLÊS OBRIGATÓRIO default) | Identificadores: variables, classes, functions, methods, constants, file names, folder names, enum members, type names, exported symbols, i18n keys. **SÓ MUDE se usuário EXPLICITLY pedir por projeto.** Não confundir com strings UI traduzidas (arquivos JSON i18n separados). |
| **DOCUMENTAÇÃO CÓDIGO + PR/COMMITS** | `LANG_DOCS` | `en` (default) | Comments inline non-docstring no source, JSDoc/TSDoc, PR titles + body, conventional commit scope + description, repo docs / ADRs / README / SPEC body + YAML. **CONFIGURAÇÃO MAIS COMUM override = `LANG_DOCS = pt-BR`** → comentários/PR/commits/docs em PT-BR mas variáveis de código SEMPRE em EN (LANG_CODE stays `en`). |
| **CHAT COM USUÁRIO** | `LANG_CHAT` | `pt-BR` (default hoje) | Respostas textuais no chat direto com o usuário. |
| **REPORTS ESTRUTURADOS** | `LANG_REPORT` | `en` (default) | Reports harness: code-review, scope-checker, QA report, merge-audit, spec YAML frontmatter. |

**Backward compat legacy:** Flag binária antiga `LANG_PT_CHECK=ENABLED|DISABLED` é migrada automaticamente: `LANG_PT_CHECK=DISABLED → LANG_DOCS=pt-BR`. Usuário NÃO precisa fazer migration manual.

**Exemplos corretos:**
```typescript
// ✅ BOM — LANG_CODE=en + LANG_DOCS=pt-BR (nunca mistura)
// Calcula o valor do cashback em GBP usando regra progressiva por tier de comprador.
function calculateLoyaltyCashback(orderTotalPence: number, tier: BuyerTier): number {
  const basePct = tier === "GOLD" ? 0.05 : tier === "SILVER" ? 0.02 : 0.01;
  return Math.floor(orderTotalPence * basePct);
}

// ❌ RUIM — MISTURA: comentário PT mas nome variável PT também (viola LANG_CODE=en)
// calcula cashback...
function calculaCashbackFidelidade(valorTotalCentavos: number, nivel: NivelComprador): number {...}
```

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

### 18. 🔴 GITHUB ACCESS — gh CLI ONLY (HARD STOP. Single allowed path.)

> **Motivation:** Uniform authentication, scopes, rate-limiting, 2FA token flow, Enterprise SSO, private-repo access, audit trail, `gh auth status` single-truth. Every alternative (HTTP curl/fetch to api.github.com, direct `git clone https://github.com/...`, octokit/SDK-js/python, raw PAT in Authorization header) causes leaks, wrong auth, 403s on private repos, PAT rotation fragility.

This rule applies to **every operation the harness does that touches GitHub (clone, PRs, diffs, comments, reviews, checks, releases, issues, search, repo metadata, branch listing, tag listing, file content, Actions logs)**. It applies to ALL skills (code-review, scope-checker, diff-context, ship, pr-comments, ci-fix, harness-git-ops, direct chat ops) and direct user requests ("pega a PR #123 pra mim").

**6 NON-NEGOTIABLES:**

1. **UNIQUE ENTRYPOINT.** Every GitHub access goes through the official `gh` CLI.
   - ✅ Allowed: `gh pr view <url> --json ...`, `gh pr diff <url>`, `gh pr view --json comments,reviews`, `gh pr checks`, `gh pr create`, `gh pr review`, `gh run view`, `gh release view`, `gh repo clone <owner>/<name>`, `gh issue list`, `gh api repos/<o>/<r> --jq ...` (REST wrapper com auth herdada do gh).
   - ❌ NEVER: `curl https://api.github.com/... -H "Authorization: Bearer $PAT"` ou qualquer variante HTTP manual.
   - ❌ NEVER: `git clone https://github.com/<o>/<r>.git` direto (sem passar por `gh repo clone`). Fallback por HTTPS público NÃO EXISTE mais; se gh não logar → erro + instruções `gh auth login`.
   - ❌ NEVER: octokit.js / octokit.py / PyGithub / github3.py em código de script do harness ou em implementação de skills. Se você precisar de uma operação que `gh` não tem built-in → use `gh api <rest-endpoint>` (que herda auth/scopes corretos).
2. **PREFLIGHT EM TODA OPERAÇÃO.** Antes de 1ª chamada gh em uma skill/etapa:
   ```bash
   command -v gh >/dev/null 2>&1 || { echo "❌ gh CLI (GitHub) não instalado. Instale: https://cli.github.com/  → depois: gh auth login --scopes repo,read:org,workflow" >&2; exit 6; }
   gh auth status >/dev/null 2>&1 || { echo "❌ gh CLI não autenticado. Rode: gh auth login --scopes repo,read:org,workflow  (verifique com gh auth status)." >&2; exit 7; }
   ```
   Skills internas (chamadas de dentro de um comando já validado) podem pular se o chamador garantiu o preflight; mas na dúvida, repetir é leve.
3. **SCOPES MÍNIMOS RECOMENDADOS no `gh auth login`:** `repo`, `read:org`, `workflow`. Escopo `admin:org` / `delete_repo` NÃO são necessários e NÃO DEVEM ser pedidos por padrão.
4. **PRIVATE REPOS / ENTERPRISE / SSO.** Funciona automaticamente se gh estiver logado na org correta. Não crie workarounds com PAT bruto em env var.
5. **RATE LIMIT HANDLING.** Se um comando gh retornar erro "API rate limit exceeded" → NÃO retente busy-loop. Avisar user com: (a) `gh api rate_limit` output curto; (b) sugestão esperar ou usar `GH_HOST=github.<enterprise>.com` se aplicável.
6. **EXCEÇÕES (ZERO por default).** A única exceção permitida é se user escrever VERBATIM "ignore a regra gh-cli-unico e use esse PAT pra chamar curl aqui". Nenhuma inferência.

**Common patterns — sempre use gh, NÃO invente:**

| Operation | Canonical gh command (substitua angled placeholders) |
|---|---|
| PR metadata + files | `gh pr view <PR_URL> --json number,title,body,state,isDraft,baseRefName,headRefName,additions,deletions,changedFiles,commits,labels,reviewDecision,mergeable,files,author,reviews` |
| PR full unified diff | `gh pr diff <PR_URL>` |
| PR diff name-only list | `gh pr diff <PR_URL> --name-only` |
| PR reviews + comments (inline + general) | `gh pr view <PR_URL> --json comments,reviews,reviewComments`  (reviewComments = inline code comments) |
| Post inline reply to review thread | `gh pr reply <review_comment_db_id> --body "<text>"` |
| Post official PR review + approve/request-changes | `gh pr review <PR_URL> --[approve\|request-changes\|comment] --body-file <path.md>` |
| PR checks / CI status | `gh pr checks <PR_URL>` |
| Actions run view + failed logs | `gh run view <RUN_ID> --log-failed > /tmp/run-<id>.log` |
| Open DRAFT PR + self-assign | `gh pr create --draft --title "..." --body-file body.md --base main --head <branch>` then `gh pr edit <url> --add-assignee @me` |
| Default branch remote | `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name` |
| Clone repo (private or public, unique way) | `gh repo clone <owner>/<repo> <target_dir> -- --depth 1`  (NÃO fallback `git clone https://`) |
| Release latest | `gh release view --repo <owner>/<repo> --json tagName,assets` |
| Raw REST endpoint when no built-in subcommand | `gh api repos/<o>/<r>/contents/<path> --jq .content \| base64 -d` |

---

### 19. 🔴 LOGGING & OBSERVABILITY STANDARD (HARD RULE — win over generic defaults; repo convention wins over THIS rule se repo define)

> **Pedido VERBATIM USER contractual:** "todo codigo produzido tenha uma boa pratica de log. Nao deve logar demais, nem de menos. … entender o que esta acontecendo em runtime, mas sem ser floodado."
> Esta seção substitui o §12 (que é só pointer). Anti-patterns de logging em PR/code-review são auditados em **harness-code-review Category 6 (L6.x)** com severidades.

#### 19.0 Princípio Hierárquico — REPO PRIMEIRO (sempre)

```
REPO CONVENTION (se existir e estiver documentada em AGENTS.md / logger.ts / app.ts)
    ↓ WINS 100%
WIRING EXISTENTE DE OBSERVABILIDADE (OTel SDK, pino singleton, winston, structlog, sentry SDK)
    ↓ WINS se #1 vazio
ESTE §19 ENGINEERING CONTRACTS STANDARD (fallback universal)
    ↓ WINS se #1 e #2 vazios
console.log / console.info / echo (nivel mais basico, ultima ratio)
```

**O que fazer SEMPRE antes de escrever sua primeira linha de log:**
1. **Detect padrões do repo:** `grep -r "logger\." | head -20`; veja se existe `packages/logger/src`, `lib/logger.ts`, `logging.ts`, `app.config.ts` entries, `AGENTS.md` observabilidade section, `utils/log.ts`. Se existe → **segue fielmente. NÃO invente seu próprio logger wrapper.**
2. **Detect wiring OTel / tracing:** procure `@opentelemetry`, `traceId`, `spanId`, `otel-sdk`, `Sentry.init()`. Se tem OTel → SEMPRE propague `traceId` / `spanId` em seus logs estruturados.
3. **Detect PII helpers:** procure `hashPII()`, `maskEmail()`, `obfuscate()`, `PII_HASH_SECRET`. Se existir → USE OBRIGATORIAMENTE. NÃO logue raw email/phone/JWT/secret (nem mesmo em DEBUG level).
4. **Se NADA existir:** fallback seguro. Use `console.info/warn/error/debug` nativo (não crie arquivo novo `my-logger.ts` a menos que task seja "adicionar logger" em SPEC).

#### 19.1 5 Níveis de Log — quando usar CADA um (NUNCA use nível errado)

| Nível | Quando usar (regra rígida) | Exemplo correto | Volume esperado |
|---|---|---|---|
| **trace** (ou `silly`/`verbose`) | Detalhes de implementação interna: valores intermediários, iteração item-a-item, steps de loop. **NUNCA em produção sem feature flag.** Apagado/`silent` por default em prod. | `log.trace({ itemId }, "Processing cart item 3/12")` | 100+/request (não padrão) |
| **debug** | Decisões, branching, inputs chave, threshold cruzado. Útil para investigar bug sem precisar ler código. Ligado em dev + staging; OFF default prod (LIGA só para debugging sessão). | `log.debug({ tier, basePct, orderTotal }, "Applying loyalty cashback rule")` | 5–25/request (máx.) |
| **info** | Eventos de negócio SIGNIFICATIVOS: start/end de fluxo (com `duration_ms`), IO externo (Stripe/DB/HTTP call) success, state transition, auth, login/logout. Você lê um log de info e entende o QUE aconteceu sem ler o código. **ONDE IDEAL PRODUÇÃO DEFAULT.** | `log.info({ paymentIntentId, customerHash, amountPence, duration_ms }, "Stripe payment intent confirmed OK")` | 3–15/request/job (REGRA HEURÍSTICA Ouro) |
| **warn** | Estado INCOMUM mas HANDLED (não é falha). Retry 1/N, timeout em 1 tentativa mas retried OK, dado faltante opcional substituído por default, deprecated API chamada. **Aqui merece atenção humana SEM bloqueio imediato.** | `log.warn({ sku, fallback_price_used: true }, "Product price tier missing; using default catalog price")` | 0–2/request (picos incomuns) |
| **error** | Falha REAL / escalável / não recuperável. Sempre acompanhado de contexto estruturado. NÃO FAÇA dump completo de stack trace para stdout por default (use `error.cause` ou structured `stack` field). ERROR = pagerduty/alerta ligado = **ação humana necessária AGORA.** | `log.error({ paymentIntentId, stripeErrorCode, httpStatus: 402, correlationId }, "Stripe charge declined — cannot proceed")` | 0–1/error event (muito raro) |

#### 19.2 Campos OBRIGATÓRIOS em TODO log estruturado (não negocia)

Sempre que possível (logger JSON/structured), inclua **TODO CAMPO QUE SE APLICAR** abaixo. Campos N/A são omitidos (não coloque `null` só pra preencher):

| Campo | Quando obrigatório | Exemplo |
|---|---|---|
| `op` / `event` / `msg` | SEMPRE (1º campo, nome humano legível operação) | `op: "stripe.refund.create"` |
| `traceId` / `spanId` | SEMPRE se OTel ou tracing existir no repo | `traceId: "4bf92f3577b34da6a3ce929d0e0e4736"` |
| `correlationId` / `idempotencyKey` | Operações externas / financeiras / retentativas | `idempotencyKey: "refund_${orderId}_${attempt}"` |
| `userId` / `orgId` / `customerId` | Qualquer contexto autenticado (use HASH se PII) | `customerHash: hashPII(email)` |
| `duration_ms` | Start/end timing, IO externo | `duration_ms: 142` |
| `error` / `err_code` / `httpStatus` | Apenas ERROR/WARN | `err_code: "card_declined"` |
| `path` / `file` / `line` | Falhas localizáveis | `path: "src/refund/service.ts:142"` |

NÃO FAÇA string concatenada `logger.info("Done processing " + orderId + " customer " + email)`. SEMPRE structured object primeiro, mensagem humana segundo:
```typescript
// ✅ BOM — structured, correlação, sem PII raw
logger.info({ op: "refund.completed", refundId, orderId, customerHash: hashPII(email), duration_ms }, "Refund processed OK")
// ❌ RUIM — texto solto, PII raw, sem correlação
logger.info(`Refund completed, refundId=${refundId} customerEmail=${email}`)
```

#### 19.3 Scripts bash / Makefile / GitHub Actions `run:` blocks / CLI commands — LOGS EXPRESSIVOS SÃO OBRIGATÓRIOS

> **USER VERBATIM:** "Principalmente em scripts e workflows, logs expressivos sao fundamentais. Adicone 'echo' sempre que fizer sentido."

**Regra NÃO NEGOCIÁVEL scripts:**
1. **Prefixo obrigatório por nível:** `[INFO]` / `[WARN]` / `[ERROR]` / `[STEP 1/5]` (pipeline numerado é ouro). Não dependa só de `set -x` (debug super floodado, útil só p/ debugging).
2. **Todo step com IO externo (clone, download, backup, apply, migrate, deploy, curl HTTP)** = echo **START** + echo **END (OK/failed)**. Humanos lêem `[INFO] Fetching gh CLI repo (laionazeredo/trae-config)...` e sabem o que está acontecendo SEM olhar código.
3. **Branching / condicionais:** se caiu num fallback, se usou A ou B, avise `[WARN] gh not detected in PATH, fallback skipped (error expected) → exit 6`.
4. **NÃO flood com `set -x` global ligado sempre.** Use `set -x` APENAS em blocos pequenos e específicos debugging. Desligue depois.
5. **Erro = sempre exit code diferente:** `echo "[ERROR] ..." >&2; exit N`. Use fd 2 para stderr.

Exemplo script GOLDEN STANDARD (harness self-update header style):
```bash
#!/usr/bin/env bash
set -euo pipefail
echo "[STEP 1/4] Preflight: verificar gh CLI autenticado..."
if ! command -v gh >/dev/null 2>&1; then
  echo "[ERROR] gh CLI não instalado. Rode: (brew|apt|dnf|winget) install gh" >&2
  exit 6
fi
echo "[INFO] gh detected OK, $(gh --version | head -1). [OK 1/4]"

echo "[STEP 2/4] Fetch repo laionazeredo/trae-config via gh repo clone..."
gh repo clone laionazeredo/trae-config /tmp/src -- --depth 1 --quiet || {
  echo "[ERROR] gh clone failed. Diagnostico: gh auth status; gh repo view laionazeredo/trae-config" >&2
  exit 8
}
echo "[INFO] Fetch OK (depth 1). [OK 2/4]"
```

#### 19.4 Volume de Logs — REGRA DO OURO HEURÍSTICA (não flood, não carente)

> **USER VERBATIM:** "sem floodar. A ideia é trazer claridade numa situação de debugging e entender o fluxo de execucao."

| Cenário | Range logs esperado TOTAL (info+warn+error+debug se ligado) | Fora do range = problema |
|---|---|---|
| API endpoint handler HTTP / tRPC procedure | 3–15 lines info/warn/error + 5–25 debug se ligado | >25 info = provável flood, <3 = carente |
| Script bash / CLI command | 1 line por STEP (número) + 1 line start + 1 line end OK/failed (≈5–20 total) | Nenhum echo expressivo = ilegível |
| Long-running ETL / job batch | 1 log info por batch de 100 itens, NÃO 1 log por item dentro de loop | 1 log / item = 100k logs = flood SIEM |
| Hot path (<1ms por operação, 10k+/s) | ZERO info/debug dentro do hot loop. MÁXIMO 1 log START + 1 END com aggregates (count, duration_ms). | Qualquer log individual dentro hot loop = degradação performance 20–80%. |
| Deploy / pipeline CI | 1 echo por stage (build/lint/typecheck/test/deploy). | Nada = não sabe onde travou; tudo = 500 linhas inúteis. |

**Anti-flood CHECKLIST — marque ANTES de commitar código novo:**
- [ ] Dentro de `for/while/map/forEach` com N>100 itens → removi info/debug que loga CADA iteração?
- [ ] Payload request/response > 2KB → trunquei em vez de dump completo? `JSON.stringify(body).slice(0,500)+"...[truncated]"`
- [ ] DEBUG level → só em lugares realmente úteis p/ debugging? Não usei debug como "goto printf"?
- [ ] Retry loop com N tentativas → 1 warn com `{attempt: 2/3, backoff_ms: 200}` por retry, NÃO 1 log por milissegundo busy wait?
- [ ] Objeto gigante/DB row completo → logue SÓ os campos que importam pro flow (ids, timestamps, status). NÃO logue a row inteira.

#### 19.5 PII / Secrets — PROIBIÇÃO ABSOLUTA (nem DEBUG, nem TRACE)

- NÃO logar JWTs, API keys, Stripe sk_live / sk_test, Supabase service_role, passwords (mesmo hasheadas inseguras).
- NÃO logar raw email / telefone / endereço / CPF. Use `hashPII(email)` / `maskPhone("+44...")` se tiver. Se não tiver helper → OMITA o campo.
- NÃO logar sessões cookies raw, Authorization headers raw, tokens de refresh.
- Aviso em code-review Category 6 L6.1 = **HIGH severity por default (CRITICAL se campo for super sensível: Stripe key, password).**

#### 19.6 Error Handling — NÃO deixe `catch` vazio, NÃO swallou erro

Sempre que você escrever `try { ... } catch`:
```typescript
// ✅ BOM — 3 propriedades no catch: (1) contexto operação, (2) identificador, (3) struct erro fields
try {
  await stripe.refunds.create({...})
} catch (err) {
  // Aqui: op + id campos + err.code + err.message (não precisa dump stack todo por default)
  logger.error({ op: "stripe.refund.create", paymentIntentId, err_code: (err as any)?.code, err_msg: (err as any)?.message }, "Refund Stripe API call failed")
  // re-throw if this is not handled: throw err
}

// ❌ RUIM — 3 anti-patterns clássicos
try { ... } catch { /* NADA. SILENCIOU ERRO = RUNTIME BUG ESCONDIDO */ }
try { ... } catch(e) { console.log(e) /* structurado? contexto? */ }
try { ... } catch(e) { throw new Error("failed") /* PERDEU stack e causa raiz */ }
```

---

### 20. 🔴 WORKTREE SESSION BINDING — One Session = One Worktree. Doubt = Ask.

> **This rule controls worktree scoping during a chat session. It is a HARD SCISSORS rule — violating it causes wrong-code commits on wrong worktrees (data loss). Higher precedence than "be helpful / be efficient" defaults. Lower precedence only than safety rules (§2 Security / §6 DbC). It applies to ALL harness skills and direct chat file operations.**

#### 20.1 HARNESS SESSIONS ROOT (PATH CONTRACT — all mutable/generated data lives here)

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

## Appendix D — A Philosophy of Software Design (John Ousterhout — CANONICAL Quick-Ref)

> **Fonte original:** John Ousterhout, _A Philosophy of Software Design_, 2ª Ed. (2018, 2021).
> **Mapa de integração no harness:**
> - **§1 No Accidental Complexity (hard rule acima)** = fundação 3 primeiros capítulos (complexity is greatest risk).
> - **harness-scope-checker CHECK 5 (LEAN/YAGNI scanner)** = lê 13 RED FLAGS abaixo + atribui Lean findings (com justificador AC se necessário).
> - **harness-code-review (gate 0.9.2 no ship)** = cada finding abaixo que aparece no diff ganha severidade: **HIGH** (4 itens em negrito abaixo, quebram deep modules), **MEDIUM** (restantes 9).
> - **harness-spec antes de escrever código** = checklist "Before You Code" abaixo obrigatório se task ≥ 8 arquivos.
> - **harness-ship gate 0.9.2 antes de commitar** = checklist "Before You Commit" abaixo obrigatório.

### D.1 13 RED FLAGS DE COMPLEXIDADE (qualquer 1 = aviso; 2+ no mesmo módulo = refatorar antes de PR)

| # | Red flag | O que é | Severidade no code-review |
|---|---|---|---|
| RF01 | **Shallow Module** (Módulo Raso) | Interface `public` grande / complexa que entrega pouca funcionalidade útil. Ex: classe com 12 métodos públicos que faz só CRUD simples numa tabela. | **HIGH** |
| RF02 | **Information Leakage** (Vazamento de Informação) | Detalhe interno de um módulo aparece FORA dele. Ex: consumers de `OrderService` têm que saber `order.discounts[0].raw_percent` em vez de `order.totalAfterDiscounts()`. | **HIGH** |
| RF03 | **Pass-Through Method** (Método "Repassa") | Método que não faz nada exceto chamar outro método com os mesmos parâmetros (zero valor agregado). Sinal de camada rasa. | **HIGH** |
| RF04 | **Overexposure / Temporal Decomposition** (Super-Exposição / Decomposição Temporal) | Abstração dividida pelo "passo a passo do tempo" em vez de por conhecimento. Ex: `OrderStep1Create`, `OrderStep2ValidateAddress`, `OrderStep3Charge` em classes separadas (só existe a ordem correta de chamar — não são módulos independentes). | **HIGH** |
| RF05 | **Repetition** (Duplicação Verdadeira) | Mesma lógica ≥ 3 lugares com ≥ 5 linhas parecidas. Não confundir com "acidentalmente parecido" (esses podem ficar). | MEDIUM |
| RF06 | **Special-General Mixture** (Mistura Especial-Geral) | Código geral (ex: helper `httpClient`) contém branches de caso especial (`if url == "/checkout/payment"`) que só existem para 1 consumer. | MEDIUM |
| RF07 | **Conjoined Methods** (Métodos Conjuntos) | Dois métodos que SEMPRE são chamados juntos na mesma ordem. Se A sempre vem depois de B, pertencem ao mesmo método / mesmo módulo. | MEDIUM |
| RF08 | **Comment Repeats Code** (Comentário Repete Código) | Comentário de linha `// incrementa contador` seguido de `counter++`. Se comentário só traduz o código, apague. | MEDIUM |
| RF09 | **Implementation Documentation Interface Doc** | Docstring da função pública fala de detalhes internos ("chama Stripe API v1 com idempotency key de 30 chars") em vez de falar do CONTRATO ("dado PaymentIntent id, retorna status + valor autorizado"). | MEDIUM |
| RF10 | **Too Obscure / Hard to Guess** (Muito Obscuro) | Nome de função ou parâmetro que você não sabe o que faz SEM ler o corpo. Ex: `process(obj, flag)` (flag = boolean 0/1, sem enum). | MEDIUM |
| RF11 | **Hard to Extend** (Difícil de Estender) | Para adicionar 1 novo caso válido (ex: novo payment method, novo status) você tem que editar ≥ 4 arquivos diferentes e lembrar de todos os lugares. | MEDIUM |
| RF12 | **Choice not Restriction** (Escolha em vez de Restrição) | API tem 12 parâmetros opcionais e o consumer tem que saber combinação correta. Módulos bons RESTRINGEM o espaço de escolhas do caller. | MEDIUM |
| RF13 | **Obvious / Easy gotcha** (Pegadinha Óbvia) | Uso normal correto do módulo, mas 1 caso padrão se você se esquecer → bug sutil (ex: `client.send(data)` — se caller não chamar `client.init()` 1 vez antes → silenciosamente falha em produção, sem warning em dev). | MEDIUM |

### D.2 15 PRINCÍPIOS DE DESIGN DO LIVRO (aplicar em ordem)

1. **Complexidade is the Greatest Enemy.** Maior risco em software = complexidade, não bugs isolados. Complexidade cresce exponencialmente com tamanho.
2. **Make Deep Modules.** O melhor módulo = **pequena interface pública simples** que entrega **grande quantidade de funcionalidade / esconde MUITA complexidade.** Bom ≠ pequeno. Bom = baixa razão (interface / funcionalidade).
3. **Abstraction = Eliminate Everything Obvious + Preserve Everything Important.** Quando você abstrai, remove tudo o que é óbvio (caller não precisa saber) e deixa visível só o que é ESSENCIAL para usar bem.
4. **Modules Should be Deep, not Shallow.** Shallow = muitos arquivos, pouca redução de complexidade. Deep = menos arquivos, cada um remove muita dor do resto do sistema.
5. **Information Hiding + Information Leakage are opposites.** Hiding = detalhe interno existe em 1 lugar só e ninguém sabe. Leakage = detalhe interno aparece em ≥ 2 lugares (qualquer mudança agora é multipla).
6. **General-Purpose modules are deeper than Special-Purpose ones.** Quando dúvida entre fazer módulo "genérico com caso especial em 1 lugar" vs "especializado", escolha genérico (profundidade maior a longo prazo).
7. **Different Layer, Different Abstraction.** Camadas devem ter ABSTRAÇÕES DIFERENTES. Se camada HTTP repete exatamente os mesmos campos/parâmetros da camada Service → é pass-through → shallow → joga fora.
8. **Pull Complexity Downwards.** Sempre que possível, mova complexidade para DENTRO do módulo (abaixo) e deixe a interface (cima) mais simples. NÃO faça caller lidar com casos especiais do módulo.
9. **Better Together than Apart.** Se duas peças de código compartilham estado / sempre são usadas juntas / uma não faz sentido sem a outra → ELAS PERTENCEM AO MESMO MÓDULO.
10. **Define Errors out of Existence.** Melhor tratamento de erro = projetar a interface de forma que o erro NÃO POSSA existir / não precise ser tratado por quem chama. Ex: retornar `Option<T>`/`null` semântico em vez de lançar exceção.
11. **Design it Twice.** Para decisões arquiteturais não óbvias, desenhe 2 abordagens COMPLETAMENTE DIFERENTES no papel (5-10 linhas cada), compare trade-offs, só então escolha. Evita viés de primeira ideia.
12. **Comments Should Describe Things that aren't Obvious from Code.** Comentar NÃO é "documentar". Comentário bom = explica INTENÇÃO, CONTEXTO, PORQUÊ, CASO ESPECIAL QUE NÃO APARECE NO CÓDIGO. Comentário ruim = traduz sintaxe.
13. **Write Comments First.** Escreva primeiro a docstring pública / comentários de intenção, SÓ DEPOIS escreva o corpo do código. Se você não consegue explicar sem escrever o código → design ruim.
14. **Incremental / Agile Development Works for Design Too.** Não precisa desenhar tudo no dia 1. Escreva primeira versão → encontre complexidade acidental → refatore para ficar mais profundo → repita.
15. **Consistency Reduces Cognitive Load.** Mesmos nomes, mesmos padrões de erro, mesmos formatos de retorno por todo canto. Poder de previsibilidade = redução de complexidade.

### D.3 CHECKLIST BEFORE YOU CODE (obrigatório se task ≥ 8 arquivos / ≥ 300 linhas)

```
□ (1) Entendi QUAL complexidade ESSENCIAL este módulo resolve?
□ (2) Já olhei se existe MÓDULO EXISTENTE que resolve 80%+? (Rule 4 REUSE BEFORE CREATE)
□ (3) Projetei a INTERFACE PÚBLICA PRIMEIRO (antes do corpo)? Ela é MENOR que o corpo esperado?
□ (4) Interface pública NÃO vaza detalhes internos (storage, framework usado, estrutura de dado)?
□ (5) Existe NO MÍNIMO 2 casos de uso diferentes para essa abstração hoje? (se 1 = reconsiderar — talvez seja raso)
□ (6) Defini ERROS FORA DA EXISTÊNCIA onde pude? (retornar Option em vez de throw, etc)
□ (7) Nome da função / parâmetros = obvio sem ler o corpo? (se não = renomeie)
□ (8) Comentário público / docstring descreve CONTRATO (o que faz, entrada, saída, side effects), NÃO implementação?
□ (9) Complexidade foi PUXADA PARA DENTRO do módulo (caller não sabe de casos especiais)?
```

### D.4 CHECKLIST BEFORE YOU COMMIT (obrigatório antes de `/harness-ship`)

```
□ (1) Nenhum dos 13 RED FLAGS (D.1) aparece NO DIF que vou commitar?
      → Se RF01,RF02,RF03,RF04 aparecerem: HIGH severity no code-review (≤ 2 HIGHs com 0 CRITICAL = auto-fix no ship; >2 HIGHs = pare e refatore antes).
□ (2) Cada novo módulo / classe tem interface PÚBLICA pequena comparada ao valor entregue?
□ (3) Nenhum método Pass-Through (repasse sem valor) novo?
□ (4) Nenhum Information Leakage (detalhe interno de arquivo A aparece em arquivo B consumer)?
□ (5) Comentários novos = explicam intenção/porquê/contexto (não repetem sintaxe)?
□ (6) Adicionei complexidade ESSENCIAL (do domínio) ou ACIDENTAL? (Se acidental → remova ANTES do commit.)
□ (7) Se mudei interface pública: atualizei / escrevi docstring contrato primeiro?
□ (8) Consistência: este código segue os mesmos nomes / padrões / erro handling do resto do módulo?
```

### D.5 MAPA: Quando usar qual princípio (8 situações canônicas)

| Situação | Princípios chave | Harness integration |
|---|---|---|
| Criando NOVA classe / módulo do zero | D.2 #2 (deep), #3 (abstraction), #6 (general-purpose), #13 (comments first) | harness-spec §6 hints + Before-You-Code (D.3) |
| Refatorando módulo existente que está "ruim" | D.2 #1 (enemy complexity), #4 (not shallow), #9 (together), #10 (errors out) | harness-code-review HIGH findings → auto-fix |
| Criando interface pública / API tRPC / REST | D.2 #5 (no leakage), #8 (pull down), #12 (restriction, not choice), #15 (consistency) | scope-checker CHECK4 env + design doc |
| Tratamento de erros / edge cases | D.2 #10 (define erros fora existência) + §2 security | code-review MEDIUM findings |
| Nomeando funções / parâmetros / variáveis | D.1 RF10 (não obscuro) + D.2 #15 (consistência) | code-review nit auto-fix |
| Escrevendo comentários / docs | D.1 RF08,RF09 (não repete código / não doc interna) + D.2 #12, #13 (comments first) | code-review comments guideline §16 |
| Decisão arquitetural grande (nova layer, nova lib) | D.2 #11 (design twice) + §1 No Accidental Complexity | ADR skill (adr-architecture) obrigatório |
| Planejando feature grande / épico (antes SPEC) | D.2 #1 (complexity é enemy #1) + #7 (different abstraction por layer) | harness-project-knowledge + xray arquitetura |

---

## Final Reminder

These rules are **intentionally strict.** They exist because:
- LLMs love over-engineering. §1 + §15 fight that.
- LLMs love creating new abstractions. §3+4 fight that.
- LLMs skip tests until after. §10 fixes that.
- LLMs leak secrets/PII accidentally. §2 + §17 prevent that.
- LLMs write overly-commented/verbose code hard to review. §16 forces clean/concise code.
- LLMs anticipate future and deliver giant PRs. §15 + gh-stack Appendix C forces small incrementals.

If any rule feels wrong for a specific case → **log the exception + rationale to `$HARNESS_WORKSPACE_SHARED/decisions.log.jsonl` (NEVER under `<WORKTREE_ROOT>/.trae/`; use `harness_compute_paths` from `$HOME/.trae/contracts/harness_sessions_contract.sh` to resolve the correct path outside the user worktree)**, and proceed.

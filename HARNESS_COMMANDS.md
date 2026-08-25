# 🌍 Harness — Global Slash Commands Reference

These are slash commands the user can type in the chat to interact with the harness.
The agent MUST recognize these and react immediately.

> Convention: `/harness-*` commands are global and work on ANY repo / worktree.
> All commands first validate: "is the worktree confirmed?" If not, block and ask for worktree path.

---

## 🏗 ARCHITECTURE: Commands vs Skills (CANONICAL — TOP LEVEL — NÃO DUPLICAR)

> **Diferença conceitual:** Commands = UX entry point (slash `/harness-X`) ↔ Skills = conteúdo/executor do trabalho.
> NÃO transformar TODOS os commands em skills. A separação abaixo é intencional (KISS).

### Categoria A — 9 "heavy" commands = PREFLIGHT VALIDATION WRAPPER → invocam Skill correspondente:
| Command | Skill invocada | Por que wrapper separado? |
|---|---|---|
| `/harness-prd` | `harness-prd-generator` | Preflight worktree + input (Linear/Jira/scope) + output location ask → then skill faz o trabalho pesado. |
| `/harness-start` | `harness-scrum-master` | Preflight worktree → skill executa scope capture + TASK GRAPH. |
| `/harness-parallel` | `harness-scrum-master` → `harness-executor-dispatcher` | Preflight worktree + force_parallel flag + error if not parallelizable. |
| `/harness-ship` | `harness-ship` | Preflight worktree + `gh auth` + no-secret-staged check → skill commits/push/PR. |
| `/harness-fix` | `harness-debugger-bugfix` | Preflight worktree + capture 4 required inputs → skill roda scientific debug loop. |
| `/harness-review` | `harness-code-review` | Preflight `gh auth` + PR URL parseable → skill puxa diff + metadata + 4-category review. |
| `/harness-pr-comments` | `harness-pr-comments` | Preflight `gh auth` + PR URL → skill baixa comentários + classification + triage. |
| `/harness-ci-fix` | `harness-ci-fixer` | Preflight `gh auth` + worktree → skill classifica R1-R9 + aplica minimal fix. |
| `/harness-design` / `/harness-figma` | `harness-social-ui-designer` | Pergunta modo (A Social Media / B UI-UX / C Design System) + path save arquivo → skill usa open-pencil MCP p/ construir tudo localmente. |

### Categoria B — 5 "light" commands = inline leves (5 linhas ler/escrever markdown) → **NÃO viram skills (KISS)**:
| Command | Implementação inline | Por que NÃO é skill? |
|---|---|---|
| `/harness-status` | Lê `task_graph.md` → conta buckets → print status PT-BR | Skill seria 10 linhas, overhead > valor. |
| `/harness-skip` | Append `decision.log.md` (SKIP GATE entry) + mark `task_graph.md` gate como skipped | 3 linhas de escrita de arquivos. |
| `/harness-decisions` | Lê `decision.log.md` → sumariza PT-BR | 2 linhas read + summarize. |
| `/harness-summary` | Usa SM logic p/ gerar interim summary structure | 8 linhas assembly summary object. |
| `/harness-abort` | Escreve ABORTED em `session.md` + `task_graph.md` | 2 writes + confirm. |

### Regra rígida (KISS):
- Se um "light" command NÃO ultrapassa ~15 linhas de lógica → inline.
- Se crescer além → extraia para skill.
- NÃO criar skill de 5 linhas.

---

## `/harness-start`

**What it does:** Triggers the full harness flow from Phase 0.
**When to invoke:** User wants to start implementing a feature/bugfix through the simulated Agile team.
**Agent action on this command:**
1. IMMEDIATELY call `harness-scrum-master` skill.
2. Scrum Master executes Pre-Flight (worktree path + task-id dir creation).
3. Scrum Master proceeds to Scope Capture.
4. If user provided args inline (PRD path, task slug), pass them as context.
**Syntax examples:**
```
/harness-start "Implement Stripe Connect onboarding flow"
/harness-start --spec=docs/prd/stripe-connect.md --slug=feat-stripe-connect
```

---

## `/harness-status`

**What it does:** Prints a concise status report of the CURRENT harness session.
**When to invoke:** User wants to see where we are in the TASK GRAPH progress.
**Agent action:**
1. Look for `task_graph.md` inside `<WORKTREE_ROOT>/.trae/<task-id>/`.
2. If not found → "Nenhuma sessão do harness ativa nesta worktree. Use `/harness-start`."
3. If found → print in Portuguese:
   - Qual task está IN_PROGRESS e em qual fase (scope/qa/compliance)
   - Contagem: Total / TODO / SCOPE_OK / QA_OK / DONE / BLOCKED
   - Lista de tasks bloqueadas, se houver
   - Avisos: tasks perto de estourar 2 iterações
   - Caminho completo da pasta `.trae/<task-id>/`

---

## `/harness-skip <gate> <task-id or "ALL"> <reason>`

**What it does:** Override gate (use with EXTREME CAUTION). Logs the skip with reason and user consent.
**When to invoke:** User explicitly wants to skip a quality/compliance gate (e.g., urgency patch, SM decides scope validation already done manually).
**Valid `<gate>` values (exact):**
- `scope` — skip SM scope validation for a task
- `qa` — skip QA (build/lint/typecheck/tests) stage
- `compliance-light` — skip per-task compliance stage
- `compliance-heavy` — skip FINAL heavy compliance stage (EXTREMELY RISKY — disallow unless user insists TWICE)
**Agent action:**
1. Confirm user wants to skip this gate (ASK if reason was not provided).
2. For `compliance-heavy`: require EXPLICIT confirmation TWICE. Print a huge warning in Portuguese: "Isso vai liberar sem checagem de segurança profunda. Continuar mesmo assim?"
3. Append to `decision.log.md`:
   - `[<date>] [SKIP GATE] <gate> — reason: <reason> — user-approved`
4. Proceed flow as if the gate passed (mark in TASK GRAPH: `QA_OK (SKIPPED — see decision.log)`.

Syntax examples:
```
/harness-skip qa T3 reason:"hotfix para staging - testes de unidade quebrados por infra não relacionada"
/harness-skip compliance-light ALL reason:"revisando manualmente um PR enorme; refaço compliance no final"
```

---

## `/harness-decisions`

**What it does:** Reads and prints (summarized) all entries from `decision.log.md` for the current session.
**When to invoke:** User wants to review trade-offs made so far.

---

## `/harness-summary`

**What it does:** Generates an immediate interim summary (even if not all tasks are done) using the final_summary structure.
**When to invoke:** User wants a status dump before the harness finishes naturally.

---

## `/harness-abort`

**What it does:** Marks session as ABORTED. Writes a final aborted status to session.md and task_graph.md. Does NOT delete any files. Changes to code so far remain in worktree.
**When to invoke:** User wants to abandon this session before completion.
Agent action: ask confirmation first.

---

## `/harness-parallel <optional worktree> [--max-parallel=3] [--serial]`

**What it does:** Explicit trigger for the parallel execution mode of the harness. Different from `/harness-start`: `/harness-start` auto-picks serial vs parallel based on preconditions and asks you to confirm; `/harness-parallel` explicitly ENABLES parallel mode and errors out early (instead of falling back) if parallel preconditions can't be satisfied.
**When to invoke:** You KNOW your tasks in task_graph.md are parallel-safe (independent files) and you want to force fan-out of 2-4 Devs at once instead of sequential. Or if auto-detection in /harness-start passed but you want to override `max_parallel` cap.
**Agent action:**
1. Invoke `harness-scrum-master` with flag `force_parallel=true`.
2. If any task envelope's `Blast Radius` still has globs → ERROR + demand user enumerates files (NO serial fallback). Parallel-or-bust when command is explicitly `/harness-parallel`.
3. Otherwise: user confirm → call `harness-executor-dispatcher`.
4. Same outputs as harness-start (execution_batches.md, merge_audit, batch_execution_report, manual_test_plan, final_summary).
**Flags:**
- `--serial`: Forces sequential, one task at a time. Use when parallel causes issues and you want debug single-task mode.
- `--max-parallel=N`: Overrides concurrency cap. Max allowed value 4; if user passes >4, clamp to 4 + warning.
- `--purge-stale-locks`: Auto-purges `.trae/_locks/*.lock.json` from aborted runs (asks confirm unless this flag present).
**Syntax examples:**
```
/harness-parallel --max-parallel=4
/harness-parallel /abs/path/to/worktree
/harness-parallel --serial     # force sequential for debugging
```

---

## `/harness-prd <--link LINEAR_OR_JIRA_URL or --scope "text description"> [--worktree /abs/path] [--output PATH]`

**What it does:** Evidence-based PRD (Product Requirements Document) generator. Different from generic PRD writers: it first runs a CRITICAL deep repo analysis (4 dimensions: Performance / Security+PII / Scalability+Data / Maintainability) against the confirmed worktree to ground the questionnaire in reality with file references, then runs a structured 4-batch questionnaire mapped 1-to-1 to the 15 sections of the repo-native PRD template (Overview, Problem, Goals/Non-Goals, User Stories, FRs, NFRs, Data Model, System Interactions, Dedup, Normalisation, ACs, Open Questions). Outputs the PRD in STRICT template format to the chosen path (default: .trae/<task-id>/prd-<slug>.md; alternative: docs/prd/<area>/<slug>.md if repo has docs/prd folder).
**When to invoke:** You want a feature/spec/PRD written for an idea or for an existing ticket (Linear/Jira). Run BEFORE `/harness-start` / `/harness-parallel` so the harness loop has the spec to build the TASK GRAPH against.
**Agent action:**
1. Invoke `harness-prd-generator` skill.
2. Preflight: confirm worktree path (ASK if missing).
3. Preflight: collect input (linear/jira link via APIs, or free text scope).
4. Ask user: output location (default: `.trae/<task-id>/prd-<slug>.md` vs `docs/prd/<area>/<slug>.md` vs custom).
5. Step 1 CRITICAL REPO ANALYSIS (4 dimensions) → present evidence to user BEFORE questions.
6. Step 2 Iterative questionnaire: 4 batches of questions (Batch 1 Strategy/Problem, Batch 2 Users/FR, Batch 3 NFR/Data/Systems, Batch 4 Dedup/Normalisation/AC/OpenQ). Wait for answers per batch.
7. Step 3 Auto-check GAPs (G1-G10: GDPR retention, GBP pence, RLS declared, PII never raw logged, Non-Goals ≥2, permission denied AC exists, double-click AC exists, etc.). Flag P0 to user until answered.
8. Step 4 Write PRD to chosen path in EXACT 15-section template format (never omit sections; write "N/A + why" if not applicable).
9. Step 5 Executive review menu: edit section / answer P0 open Qs / move status from Draft → Review / save to canonical docs/prd + prep for ship.
**Syntax examples:**
```
/harness-prd --link https://linear.app/flockr/issue/FLO-789
/harness-prd --scope "Adicionar botão 1-click no dashboard do organizador para abrir Stripe Connect Dashboard, sem precisar navegar 3 telas." --worktree /abs/worktree/path
/harness-prd --link <url> --output docs/prd/payments/stripe-dashboard-button.md
```

---

## `/harness-ship`

**What it does:** End-of-development ship: atomic conventional commits, push (creates remote branch if missing), opens a DRAFT PR against the default branch with a structured PR description, assigns the PR to you (the user).
**When to invoke:** You finish a feature/bugfix, you're confident the worktree is correct, and you want commit + push + open PR. Can run AFTER the harness loop ends, or standalone for any worktree.
**Agent action:**
1. Invoke `harness-ship` skill.
2. Preflight: worktree confirmed; `gh auth status` OK; no secret files staged.
3. Propose a numbered atomic commit plan grouping the diff into conventional commits.
4. Wait for your explicit APPROVAL of the commit plan.
5. Apply each commit individually.
6. `git push --no-verify --set-upstream origin <branch>` (creates remote if missing).
7. Build structured PR description (in English) from: `.trae/<task-id>/manual_test_plan.md`, PR_DESCRIPTION_TEMPLATE, top assumptions/decisions.
8. Open DRAFT PR against default branch → assign to `@me` → print PR URL.
**Syntax examples:**
```
/harness-ship
/harness-ship --ticket FLO-123 --slug feat-stripe-connect
/harness-ship --draft-pr-title "feat(payments): Stripe Connect onboarding"
```

---

## `/harness-fix <optional worktree>`

**What it does:** Bug fix harness (DIFFERENT from feature harness). Scientific debug loop: user provides expected behavior + reproduction steps. Debugger expert builds hypotheses, instruments, reproduces, analyzes, applies minimal fix + regression test, demonstrates it to you with clear steps to verify or shows the failing→passing test run.
**When to invoke:** You want to report an existing bug / wrong runtime behavior and have it fixed. NOT for feature work.
**Agent action:**
1. Invoke `harness-debugger-bugfix` skill.
2. Preflight: worktree path confirmed (ASK if missing).
3. Capture REQUIRED inputs from you: (a) expected behavior, (b) actual bug behavior, (c) exact numbered reproduction steps, (d) ticket reference if any.
4. Baseline: REPRODUCE the bug fresh → capture evidence (logs, stacks, HTTP).
5. Debug loop (max 5 iterations per bug): HYPOTHESIZE → INSTRUMENT → REPRODUCE → CONFIRM/REFUTE root cause.
6. Once root cause confirmed: write failing test → apply minimal fix → confirm test passes.
7. Deliver to you: (i) demo how to manually verify by running reproduction steps (before bad → after good), (ii) which files changed, (iii) where regression test file lives.
8. If stuck 5 iterations: stop, report what hypotheses were REFUTED, ask next steps.
**Syntax examples:**
```
/harness-fix "HTTP 500 when submit order without customer_id"
/harness-fix expected:"Dashboard shows £0.00 always even with sales" actual:"shows 0" repro:"1. login ...
```

---

## `/harness-review <PR_URL> --ticket <LINEAR_OR_JIRA_URL or --scope "text description">`

**What it does:** High-impact focused code review of a GitHub PR. Only flags BLOCKING issues — never bikeshed style/formatting. Focus areas: (1) runtime breakage / silent incorrect behavior, (2) security / PII / compliance, (3) unjustified new dependencies / huge PR scope, (4) scope deviation from ticket/description.
**When to invoke:** You paste a link of a PR you want a fast, meaningful review for.
**Agent action:**
1. Invoke `harness-code-review` skill.
2. Preflight: `gh auth status` OK. Confirm PR URL is reachable and parseable.
3. Pull PR metadata + diff + files list via `gh pr view --json`.
4. Pull ticket context / scope description from your args.
5. Run the 4-category review framework (Runtime / Security / Deps-blast-radius / Scope deviation).
6. Structured review report saved to disk: `.trae/review_PR-<N>_<YYYYMMDD>.md`.
7. Verdict delivered to chat (Portuguese): 🔴 REQUEST CHANGES / 🟡 APPROVE WITH COMMENTS / 🟢 APPROVE, with numbered blocking issues.
8. If user says "suba essa review oficial": use `gh pr review` with the report as body + request-changes / comment / approve flag.
**Syntax examples:**
```
/harness-review https://github.com/myorg/myrepo/pull/42 --ticket https://linear.app/team/issue/FLO-123
/harness-review https://github.com/myorg/myrepo/pull/42 --scope "fix checkout 500 when empty cart"
```

---

## `/harness-pr-comments <PR_URL>`

**What it does:** Scans every comment on a PR, classifies each one (human vs bot; valid actionable vs question vs nit vs outdated vs praise vs discussion). Produces a triage report with 3 outputs: (1) numbered implementation plan for comments we should act on, (2) pre-written ENGLISH polite responses for comments we decline/question, (3) comments we resolve silently. User approves the report → we implement + optionally post replies via gh.
**When to invoke:** PR has many review comments pending and you want a structured plan of what to fix vs how to reply.
**Agent action:**
1. Invoke `harness-pr-comments` skill.
2. Pull ALL comments via `gh pr view --json comments,reviews` → flatten.
3. Classification framework: BOT vs HUMAN, then HUMAN → (CORRECTNESS, SECURITY, ARCHITECTURE, SCOPE CREEP, QUESTION, NIT, PRAISE, DISCUSSION, OUTDATED, DUPLICATE).
4. Triage report saved to `.trae/pr-<N>-comments_<YYYYMMDD>.md`.
5. Deliver to user chat: summary buckets count, Section 1 (TO IMPLEMENT) sorted by severity, Section 2 (DRAFT RESPONSES) English polite non-argumentative, Section 3 DISCUSSION PENDING USER, Section 4 NIT optional, Section 5 RESOLVED SILENTLY.
6. Aggregated implementation plan as atomic commits batches.
7. If user says: implement → apply fixes in worktree. If user says: post replies → `gh pr reply` each drafted comment.
**Syntax examples:**
```
/harness-pr-comments https://github.com/myorg/myrepo/pull/42
```

---

## `/harness-ci-fix <ACTIONS_RUN_URL_or_PR_URL>`

**What it does:** Diagnoses and fixes failing CI (GitHub Actions). Pulls failed jobs/steps, extracts error logs, classifies root cause (build / lint / typecheck / deterministic-test / flaky / dependency-lockfile / CI-YAML-script / migration / INFRA-EXTERNAL — do not code). Proposes minimal fix plan per job. User approves plan → implements fixes in worktree locally → pushes. For INFRA/EXTERNAL (secrets rotated, GitHub outage, npm registry 5xx): stops and reports to user without touching code.
**When to invoke:** CI goes red on a PR or Actions run and you want a diagnosis + fix.
**Agent action:**
1. Invoke `harness-ci-fixer` skill.
2. Preflight: `gh auth status` OK; worktree path confirmed (ASK if missing).
3. Pull failing jobs / steps via `gh run view` / `gh pr checks`.
4. For each failed step: pull logs → classify into R1-R9 categories (R9: intentional AC/spec changed → fix tests, not code; user confirm required).
5. Fix plan per job, grouped by category. Present to user for APPROVAL before coding.
6. For R7 (infra/external): IMMEDIATELY report to user — NO code changes.
7. User-approved plan → implement minimal fixes in worktree. Verify local equivalents.
8. Ship via same conventional-commit rules: `fix(ci):`, `fix(lint):`, `fix(build):`, `chore(deps):`, `chore(ci):`.
9. Push branch → optionally rerun failed jobs.
**Syntax examples:**
```
/harness-ci-fix https://github.com/myorg/myrepo/actions/runs/987654
/harness-ci-fix https://github.com/myorg/myrepo/pull/42
```

---

## `/harness-design` <modo: A|B|C opcional> [--path /abs/path/to/save.pen] [--palette #HEX1,#HEX2] [--tone "Tom de Voz"]

## Alias: `/harness-figma`

**What it does:** Full design harness: 3 modos. (A) Social Media: 6 criativos (Feed/Stories/Reels) + copy profissional + imagens geradas por IA + export PNG 2×. (B) UI/UX Feature: wireframes → high-fidelity → dev-spec (tokens Tailwind exportáveis). (C) Design System atômico: Tailwind tokens ↔ variáveis (Light/Dark mode) + 12 componentes (Button/Card/Input etc.) 4 variants + export CSS/JSON/Tailwind. Uses **local** `mcp_open-pencil` MCP (140+ tools equivalente a Figma desktop).
**When to invoke:** Você quer designs profissionais prontos para produção direto por aqui: criativos de rede sociais com copy, telas de produto, ou um design system atômico sincronizado com Tailwind.
**Agent action (PREFLIGHT obrigatório se parâmetros faltarem):**
1. Invocar **`harness-social-ui-designer`** skill IMEDIATAMENTE.
2. Preflight pergunta #1 (se `--mode` omitido): "Qual modo? A) Social Media / B) UI-UX / C) Design System" (AskUserQuestion 1 pergunta, 3 opções).
3. Preflight pergunta #2 (equivalente a "qual projeto figma trabalhar", user-asked): qual caminho ABSOLUTO para salvar o arquivo de design (`.pen` = OpenPencil / Figma-equivalente). Default `/home/laion/.trae/designs/<modo>-<slug>-YYYYMMDD.pen`.
4. Preflight pergunta #3 (se faltar): paleta / tipografia / tom de voz (copy).
5. Skill executa o modo selecionado §A/B/C com fail-fast + quality gates WCAG AA.
6. Entrega final sempre com: arquivos exportados PNG 2× / tokens / source `.pen` + 1 ÚNICA oferta de aprofundar (§18 contracts).

**Syntax examples:**
```
/harness-design A                                # Social Media batch completo (2 feed + 2 stories + 2 reels templates + copy + imagens)
/harness-design B --path /home/laion/designs/dashboard-creator.pen  # UI-UX feature dashboard
/harness-design C --palette "#6D28D9,#F59E0B,#111827,#F9FAFB" --tone "Luxo minimalista"
/harness-figma A slug:"lancamento-festival-UK"   # alias igual
```

---

## Relationship between commands and skills (UPDATED)

| Command | Primary skill invoked |
|---|---|
| `/harness-prd` | `harness-prd-generator` (critical repo analysis → 4-batch questionnaire → strict 15-section PRD template) |
| `/harness-start` | `harness-scrum-master` (auto-detects serial vs parallel; falls back serial if any precondition fails) |
| `/harness-parallel` | `harness-scrum-master` → `harness-executor-dispatcher` (explicit parallel; ERROR if can't parallelize; no serial fallback) |
| `/harness-ship` | `harness-ship` (commits → push → DRAFT PR → assign) |
| `/harness-fix` | `harness-debugger-bugfix` (scientific debug loop, different from features) |
| `/harness-review` | `harness-code-review` (HIGH / CRITICAL + scope only) |
| `/harness-pr-comments` | `harness-pr-comments` (triage, implementation plan, reply drafts) |
| `/harness-ci-fix` | `harness-ci-fixer` (classify CI failure + minimal fix) |
| `/harness-design` | `harness-social-ui-designer` (3 modos: Social Media / UI-UX / Design System — local open-pencil MCP equivalente Figma) |
| `/harness-status` | Reads `task_graph.md` directly, no skill invocation needed |
| `/harness-skip` | Updates `decision.log.md` + `task_graph.md`; tells SM to treat gate as passed |
| `/harness-decisions` | Reads `decision.log.md` |
| `/harness-summary` | Uses SM logic to generate interim final_summary |
| `/harness-abort` | SM writes ABORTED metadata |

---

## Rules for the AGENT when user issues a command

1. **Worktree check FIRST.** If `/harness-*` is called but worktree is not yet confirmed → **ASK FOR WORKTREE before executing anything else.** Even if the command is just `/harness-status`.
2. **English for files, Portuguese for chat.** The reports printed to the user (status, decisions, warnings) are in Portuguese. The files written to disk are in English.
3. **Do NOT invent new commands.** Only those listed above, plus any repo-local `/flockr-*` commands already defined per-worktree.
4. **Logging.** Every command execution results in a new entry to `session.md` under `.trae/<task-id>/`.

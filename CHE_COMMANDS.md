# 🌍 Che — Global Slash Commands Reference

These are slash commands the user can type in the chat to interact with the che.
The agent MUST recognize these and react immediately.

> Convention: `/che-*` commands are global and work on ANY repo / worktree.
> All commands first validate: "is the worktree confirmed?" If not, block and ask for worktree path.

---

## 🏗 ARCHITECTURE: Commands vs Skills (CANONICAL — TOP LEVEL — NÃO DUPLICAR)

> **Diferença conceitual:** Commands = UX entry point (slash `/che-X`) ↔ Skills = conteúdo/executor do trabalho.
> NÃO transformar TODOS os commands em skills. A separação abaixo é intencional (KISS).

### Categoria A — 9 "heavy" commands = PREFLIGHT VALIDATION WRAPPER → invocam Skill correspondente:
| Command | Skill invocada | Por que wrapper separado? |
|---|---|---|
| `/che-spec [input] [worktree] [slug]` | `che-spec` | Preflight binding §19 (worktree confirmado + nível 2 criado) → skill gera/valida SPEC em $CHE_WORKSPACE_SHARED. 4 fontes input. Gate Approved. **NÃO depende de /che-start — roda sozinho.** |
| `/che-start` | `che-scrum-master` | Preflight worktree → skill executa §0.5 SPEC GATE (auto-invoca che-spec se não houver Approved) → scope capture + TASK GRAPH. |
| `/che-parallel` | `che-scrum-master` → `che-executor-dispatcher` | Preflight worktree + force_parallel flag + error if not parallelizable. |
| `/che-ship` | `che-ship` | Preflight worktree + `gh auth` + no-secret-staged check → skill commits/push/PR. |
| `/che-fix` | `che-debugger-bugfix` | Preflight worktree + capture 4 required inputs → skill roda scientific debug loop. |
| `/che-review` | `che-code-review` | Preflight `gh auth` + PR URL parseable → skill puxa diff + metadata + 4-category review. |
| `/che-diff` | `che-diff-context` | Preflight worktree (Modo B) / gh auth (Modo A) → relatório leve CONTEXTO p/ conversar sobre diff (PR URL ou worktree local vs branch default). DIFERENTE de /che-review (review blocking vs contexto). |
| `/che-manual-test` | `che-manual-test-executor` | Preflight worktree + session binding §19 + encontra manual_test_plan.md via --task-id ou --plan-path → GATE de setup approval obrigatório → executa steps via Playwright MCP + evidências screenshots + report final 8 seções. DIFERENTE de /che-qa (QA = só comandos automatizados build/lint/test; Manual = browser step-a-step c/ evidências). |
| `/che-pr-comments` | `che-pr-comments` | Preflight `gh auth` + PR URL → skill baixa comentários + classification + triage. |
| `/che-ci-fix` | `che-ci-fixer` | Preflight `gh auth` + worktree → skill classifica R1-R9 + aplica minimal fix. |
| `/che-design` / `/che-figma` | `che-social-ui-designer` | Pergunta modo (A Social Media / B UI-UX / C Design System) + path save arquivo → skill usa open-pencil MCP p/ construir tudo localmente. |

### Categoria B — 5 "light" commands = inline leves (5 linhas ler/escrever markdown) → **NÃO viram skills (KISS)**:
| Command | Implementação inline | Por que NÃO é skill? |
|---|---|---|
| `/che-status` | Lê `task_graph.md` → conta buckets → print status PT-BR | Skill seria 10 linhas, overhead > valor. |
| `/che-skip` | Append `decisions.log.jsonl` (SKIP GATE entry) + mark `task_graph.md` gate como skipped | 3 linhas de escrita de arquivos. |
| `/che-decisions` | Lê `decisions.log.jsonl` → sumariza PT-BR | 2 linhas read + summarize. |
| `/che-summary` | Usa SM logic p/ gerar interim summary structure | 8 linhas assembly summary object. |
| `/che-abort` | Escreve ABORTED em `session.md` + `task_graph.md` | 2 writes + confirm. |

### Regra rígida (KISS):
- Se um "light" command NÃO ultrapassa ~15 linhas de lógica → inline.
- Se crescer além → extraia para skill.
- NÃO criar skill de 5 linhas.

---

## `/che-spec [input_type:ticket|prd-flockr|desc|existing] [input_value] [worktree] [slug]`

**What it does:** Standalone entry-point for generating or validating a **Che Execution Specification (SPEC)** — artefato de planejamento anti-alucinação/anti-scope-drift que substitui o PRD Flockr legado. Salva DURÁVEL em `$CHE_WORKSPACE_SHARED/spec_<slug>.md` (fora sessions/, fora worktree user). 4 fontes input aceitas: (A) SPEC Approved existente; (B) Ticket URL (Linear FLO-XXX / ClickUp / GitHub Issue); (C) PRD Flockr legado path (.md); (D) Descrição breve inline com prompts iterativos.
**When to invoke:** User quer redigir/atualizar um SPEC **antes** do /che-start, ou standalone para documento de planejamento, ou quando /che-start SM §0.5 o invoca automaticamente por não haver Approved.
**Agent action on this command:**
1. IMMEDIATELY call `che-spec` skill.
2. Preflight: verifica binding §19 Level1 existente; se não houver, pergunta worktree + cria binding 2-LEVEL antes.
3. Skill executa fluxo 4 fontes → valida §4 7 checks → loop aprovação 1-pass → save atômico temp+mv.
4. **Retorna 2 últimas linhas parseável para SM:**
   ```
   SPEC_PATH=<absoluto sem quotes>
   SPEC_STATUS=Approved|Draft
   ```
5. Append `[SPEC] <slug> <status> saved at <ISO>` em `$CHE_WORKSPACE_SHARED/decisions.log.jsonl`.
**Syntax examples:**
```
/che-spec input=ticket https://linear.app/flockr/issue/FLO-745 slug=api-fail-closed
/che-spec input=prd-flockr docs/prd/payments/refunds.md slug=refund-flow
/che-spec input=desc slug=fix-qr-scan "QR scanner nao valida ticket ja usado"
/che-spec input=existing slug=api-fail-closed
```

---

## `/che-start [input_type:ticket|prd-flockr|desc] [input_value] [--slug=slug]`

**What it does:** Triggers the full che flow from Phase 0. **SM §0.5 auto-invoca `/che-spec` automaticamente se não houver SPEC Approved na worktree**, aceitando os mesmos args de input (ticket/prd/desc) e passando-os para che-spec.
**When to invoke:** User wants to start implementing a feature/bugfix through the simulated Agile team.
**Agent action on this command:**
1. IMMEDIATELY call `che-scrum-master` skill.
2. Scrum Master executes Pre-Flight (worktree path + `che_compute_paths` → ensure_dirs + Level2 binding).
3. **SM §0.5 SPEC GATE (antes scope capture):** Glob `$CHE_WORKSPACE_SHARED/spec_*.md` → parse Approved. Se 0 OU usuário forneceu input → **invoca che-spec Skill automaticamente**, passando args de entrada do usuário (ticket/prd/desc).
4. Captura 2 linhas retorno: `SPEC_PATH` + `SPEC_STATUS`. Gate: Approved → libera Scope Capture; Draft → oferece (A) Override `[SPEC-OVERRIDE]` logado em decisions / (B) Parar, terminar SPEC depois via `/che-spec` standalone.
5. Scrum Master proceeds to Scope Capture.
**Syntax examples:**
```
/che-start "Implement Stripe Connect onboarding flow"
/che-start --slug=feat-stripe-connect input=ticket https://linear.app/flockr/issue/FLO-123
/che-start input=prd-flockr docs/prd/stripe-connect.md --slug=feat-stripe-connect
```

---

## `/che-status`

**What it does:** Prints a concise status report of the CURRENT che session.
**When to invoke:** User wants to see where we are in the TASK GRAPH progress.
**Agent action:**
1. Source `$HOME/.trae/contracts/che_sessions_contract.sh` → `che_compute_paths WORKTREE_ROOT` → look for `task_graph.md` at `$CHE_WORKSPACE_SHARED/task_graph.md` (FORA worktree).
2. If not found → "Nenhuma sessão do che ativa nesta worktree. Use `/che-start`."
3. If found → print in Portuguese:
   - Qual task está IN_PROGRESS e em qual fase (scope/qa/compliance)
   - Contagem: Total / TODO / SCOPE_OK / QA_OK / DONE / BLOCKED
   - Lista de tasks bloqueadas, se houver
   - Avisos: tasks perto de estourar 2 iterações
   - Caminhos dos artefatos (todos FORA worktree): `$CHE_WORKSPACE_SHARED/` (durável) + `$CHE_SESSION_DIR/` (efêmero)

---

## `/che-skip <gate> <task-id or "ALL"> <reason>`

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
3. Append to `decisions.log.jsonl`:
   - `[<date>] [SKIP GATE] <gate> — reason: <reason> — user-approved`
4. Proceed flow as if the gate passed (mark in TASK GRAPH: `QA_OK (SKIPPED — see decision.log)`.

Syntax examples:
```
/che-skip qa T3 reason:"hotfix para staging - testes de unidade quebrados por infra não relacionada"
/che-skip compliance-light ALL reason:"revisando manualmente um PR enorme; refaço compliance no final"
```

---

## `/che-decisions`

**What it does:** Reads and prints (summarized) all entries from `decisions.log.jsonl` for the current session.
**When to invoke:** User wants to review trade-offs made so far.

---

## `/che-summary`

**What it does:** Generates an immediate interim summary (even if not all tasks are done) using the final_summary structure.
**When to invoke:** User wants a status dump before the che finishes naturally.

---

## `/che-abort`

**What it does:** Marks session as ABORTED. Writes a final aborted status to session.md and task_graph.md. Does NOT delete any files. Changes to code so far remain in worktree.
**When to invoke:** User wants to abandon this session before completion.
Agent action: ask confirmation first.

---

## `/che-parallel <optional worktree> [--max-parallel=3] [--serial]`

**What it does:** Explicit trigger for the parallel execution mode of the che. Different from `/che-start`: `/che-start` auto-picks serial vs parallel based on preconditions and asks you to confirm; `/che-parallel` explicitly ENABLES parallel mode and errors out early (instead of falling back) if parallel preconditions can't be satisfied.
**When to invoke:** You KNOW your tasks in task_graph.md are parallel-safe (independent files) and you want to force fan-out of 2-4 Devs at once instead of sequential. Or if auto-detection in /che-start passed but you want to override `max_parallel` cap.
**Agent action:**
1. Invoke `che-scrum-master` with flag `force_parallel=true`.
2. If any task envelope's `Blast Radius` still has globs → ERROR + demand user enumerates files (NO serial fallback). Parallel-or-bust when command is explicitly `/che-parallel`.
3. Otherwise: user confirm → call `che-executor-dispatcher`.
4. Same outputs as che-start (execution_batches.md, merge_audit, batch_execution_report, manual_test_plan, final_summary).
**Flags:**
- `--serial`: Forces sequential, one task at a time. Use when parallel causes issues and you want debug single-task mode.
- `--max-parallel=N`: Overrides concurrency cap. Max allowed value 4; if user passes >4, clamp to 4 + warning.
- `--purge-stale-locks`: Auto-purges `$CHE_SESSION_DIR/_locks/*.lock.json` from aborted runs — resolve path via `che_compute_paths` (asks confirm unless this flag present; NEVER inside worktree).
**Syntax examples:**
```
/che-parallel --max-parallel=4
/che-parallel /abs/path/to/worktree
/che-parallel --serial     # force sequential for debugging
```

---

## `/che-ship`

**What it does:** End-of-development ship: atomic conventional commits, push (creates remote branch if missing), opens a DRAFT PR against the default branch with a **readable PR body for low-context reviewers** (5 canonical sections, acronyms expanded first use, every change includes user impact, risks explain consequences, default English), assigns the PR to you (the user).
**When to invoke:** You finish a feature/bugfix, you're confident the worktree is correct, and you want commit + push + open PR. Can run AFTER the che loop ends, or standalone for any worktree.
**Agent action:**
1. Invoke `che-ship` skill.
2. Preflight: worktree confirmed; `gh auth status` OK; no secret files staged.
3. Propose a numbered atomic commit plan grouping the diff into conventional commits.
4. Wait for your explicit APPROVAL of the commit plan.
5. Apply each commit individually.
6. `git push --no-verify --set-upstream origin <branch>` (creates remote if missing).
7. Build readable PR body (default English; PT only if YOU explicitly request) from: `$CHE_WORKSPACE_SHARED/manual_test_plan.md` + `PR_DESCRIPTION_TEMPLATE.md` (filled style reference, follow it strictly) + relevant decisions from `$(che_decisions_path)`. Resolve paths via `che_compute_paths`; NEVER read from `<WORKTREE_ROOT>/.trae/*`. Enforce §A-4.2 process gates (acronyms expanded, 1 bullet = 1 change + why, risk→consequence, plain steps to verify, ≤50 lines total).
8. Open DRAFT PR against default branch → assign to `@me` → print PR URL.
**Syntax examples:**
```
/che-ship
/che-ship --ticket PROJ-123 --slug feat-stripe-connect
/che-ship --draft-pr-title "feat(payments): Stripe Connect onboarding"
```

---

## `/che-fix <optional worktree>`

**What it does:** Bug fix che (DIFERENTE de feature che). Scientific debug loop: user provides expected behavior + reproduction steps. Debugger expert builds hypotheses, instruments, reproduces, analyzes, applies minimal fix + regression test, demonstrates it to you with clear steps to verify or shows the failing→passing test run.
**When to invoke:** You want to report an existing bug / wrong runtime behavior and have it fixed. NOT for feature work.
**Agent action:**
1. Invoke `che-debugger-bugfix` skill.
2. Preflight: worktree path confirmed (ASK if missing).
3. Capture REQUIRED inputs from you: (a) expected behavior, (b) actual bug behavior, (c) exact numbered reproduction steps, (d) ticket reference if any.
4. Baseline: REPRODUCE the bug fresh → capture evidence (logs, stacks, HTTP).
5. Debug loop (max 5 iterations per bug): HYPOTHESIZE → INSTRUMENT → REPRODUCE → CONFIRM/REFUTE root cause.
6. Once root cause confirmed: write failing test → apply minimal fix → confirm test passes.
7. Deliver to you: (i) demo how to manually verify by running reproduction steps (before bad → after good), (ii) which files changed, (iii) where regression test file lives.
8. If stuck 5 iterations: stop, report what hypotheses were REFUTED, ask next steps.
**Syntax examples:**
```
/che-fix "HTTP 500 when submit order without customer_id"
/che-fix expected:"Dashboard shows £0.00 always even with sales" actual:"shows 0" repro:"1. login ...
```

---

## `/che-review <PR_URL> --ticket <LINEAR_OR_JIRA_URL or --scope "text description">`

**What it does:** High-impact focused code review of a GitHub PR. Only flags BLOCKING issues — never bikeshed style/formatting. Focus areas: (1) runtime breakage / silent incorrect behavior, (2) security / PII / compliance, (3) unjustified new dependencies / huge PR scope, (4) scope deviation from ticket/description.
**When to invoke:** You paste a link of a PR you want a fast, meaningful review for.
**Agent action:**
1. Invoke `che-code-review` skill.
2. Preflight: `gh auth status` OK. Confirm PR URL is reachable and parseable.
3. Pull PR metadata + diff + files list via `gh pr view --json`.
4. Pull ticket context / scope description from your args.
5. Run the 4-category review framework (Runtime / Security / Deps-blast-radius / Scope deviation).
6. Structured review report saved to disk: `.trae/review_PR-<N>_<YYYYMMDD>.md`.
7. Verdict delivered to chat (Portuguese): 🔴 REQUEST CHANGES / 🟡 APPROVE WITH COMMENTS / 🟢 APPROVE, with numbered blocking issues.
8. If user says "suba essa review oficial": use `gh pr review` with the report as body + request-changes / comment / approve flag.
**Syntax examples:**
```
/che-review https://github.com/myorg/myrepo/pull/42 --ticket https://linear.app/team/issue/PROJ-123
/che-review https://github.com/myorg/myrepo/pull/42 --scope "fix checkout 500 when empty cart"
```

---

## `/che-diff <PR_URL OR --worktree /abs/path> [--base origin/dev]`

**What it does:** Leve "conversa preparada" sobre um diff. **DIFERENTE de `/che-review`** (que dá verdict de approve/request-changes com issues CRITICAL + HIGH only). Este entrega um relatório 5 seções p/ VOCÊ TER CONTEXTO pra conversar sobre o diff com alguém: (1) o que implementa (alto nível), (2) principais mudanças por módulo, (3) CI checks status (Modo A) ou buckets JáCommitado/PorCommitar/Untracked (Modo B), (4) riscos leves, (5) 3 pontos de atenção pra pautar na call/comentário. Modo A = PR URL via gh CLI. Modo B = worktree local, compara com branch default (pergunta qual base se ambíguo).

**When to invoke:** Você colou um link de PR OU apontou pra worktree e quer "entender o que aconteceu aqui" + pontos de conversa, sem o rigor formal de review. Quando quiser review blocking issues → use `/che-review`.

**Agent action:**
1. Invoke `che-diff-context` skill.
2. Preflight Modo A (PR URL): `gh auth status` OK; URL parseável e reachable.
3. Preflight Modo B (--worktree): worktree confirmada, session binding §19 lido (pergunta mismatch). Base branch: tenta auto-detect (origin/main ou origin/dev), se ambíguo → AskUserQuestion 2 opções + "outro".
4. Coleta 3 fontes contexto Modo A: PR descr/metadata via gh pr view --json, diff names/stat, CI checks gh pr checks.
5. Coleta 4 buckets Modo B: Já Commitado (base..HEAD), Por Commitar (staged + unstaged tracked), Untracked, Branch metadata.
6. Estrutura relatório nas 5 seções CANÔNICAS (contexto alto / áreas mudança / CI ou buckets / riscos leves / 3 pontos conversa).
7. Salva arquivo em `.trae/diff-context_PR-<N>_<ts>.md` (Modo A) ou `.trae/diff-context_LOCAL_<ts>.md` (Modo B).
8. Entrega no chat resumo condensado §18 contracts (250–500w + 4 seções). Full report salvo em disco.

**Syntax examples:**
```
/che-diff https://github.com/myorg/myrepo/pull/42
/che-diff --worktree /abs/path/to/worktree
/che-diff --worktree /abs/path --base origin/dev
```

---

## `/che-manual-test <--worktree /abs/path> [--task-id <slug> OR --plan-path <abs/path/to/manual_test_plan.md>]`

**What it does:** Executa passo-a-passo o `manual_test_plan.md` do Scrum Master via **Playwright MCP** (browser real: navigate/click/fill/submit + screenshot evidências) e HTTP driver para API calls. DIFERENTE de `/che-qa` (QA = só comandos automatizados build/lint/test sem browser). Este che Abre navegador, passo-a-passo com plano, grava evidências (PNG, visible_text, console_log) por step, e entrega report final 8 seções com verdict global. Safety: NÃO toca prod URLs sem 2 confirmações, setup approval gate OBRIGATÓRIO antes de qualquer comando shell setup.

**When to invoke:** Scrum Master finalizou o `manual_test_plan.md` (todas ACs do plano escritas, ambiente pronto) e você quer o AGENTE EXECUTAR os testes manuais (abrir browser, clicar, preencher formulários, tirar prints) ao invés de você manualmente. Se só quer build/lint/test automáticos → use `/che-qa`.

**Agent action:**
1. Invoke `che-manual-test-executor` skill IMEDIATAMENTE.
2. Preflight #1: confirmar worktree path + validar session binding §19 (mismatch = block pergunta).
3. Preflight #2: resolver path manual_test_plan.md → (a) `--plan-path` dado → use; (b) default (nenhum flag): `source $HOME/.trae/contracts/che_sessions_contract.sh && che_compute_paths $WORKTREE_ROOT && echo $CHE_WORKSPACE_SHARED/manual_test_plan.md`; (c) nenhum binding criado → AskUserQuestion qual opção.
4. Preflight #3: parse do plano (§0 Setup env, AC-N steps com GWT, Smoke S1..S5, HUMAN_ONLY items §3).
5. **GATE setup approval OBRIGATÓRIO (antes qualqeur comando shell setup):** perguntar usuário (A=Executar setup, B=Pular app já roda, C=Cancelar).
6. Criar evidence dir: `$CHE_SESSION_DIR/manual_test_evidence/` (FORA worktree) com subdirs AC-1, AC-2, ... + `execution.log`.
7. **AC Execution Loop:** Para cada AC-N → classificação step pattern → driver Playwright/HTTP. Step por step com evidência cada. THEN assertion final → veredict ✅/⚠️/❌/⏭️ → close playwright session isolation.
8. **Smoke S1..S5:** S1=build, S2=lint via comandos; S3=Login scenario Playwright; S4=top-level 3 pages Nav; S5=log grep CRITICAL/ERROR.
9. Build report final 8 seções conforme references/MANUAL_TEST_EXECUTION_REPORT.md → save em `$CHE_SESSION_DIR/reports/MANUAL_TEST_EXECUTION_REPORT.md` (FORA worktree, `che_assert_outside_worktree`).
10. Entrega chat resumo condensado §18 contracts (≤500w, 4 seções: status + ACs pass/fail counts + key failures ≤3 bullets + links report/evidence/plan + 1 oferta deep-dive).

**Syntax examples:**
```
/che-manual-test --worktree /abs/path/to/worktree --task-id feat-PROJ-123-Process-a-refund
/che-manual-test --worktree /abs/path --plan-path /abs/.trae/some-other/manual_test_plan.md
```

---

## `/che-pr-comments <PR_URL>`

**What it does:** Scans every comment on a PR, classifies each one (human vs bot; valid actionable vs question vs nit vs outdated vs praise vs discussion). Produces a triage report with 3 outputs: (1) numbered implementation plan for comments we should act on, (2) pre-written ENGLISH polite responses for comments we decline/question, (3) comments we resolve silently. User approves the report → we implement + optionally post replies via gh.
**When to invoke:** PR has many review comments pending and you want a structured plan of what to fix vs how to reply.
**Agent action:**
1. Invoke `che-pr-comments` skill.
2. Pull ALL comments via `gh pr view --json comments,reviews` → flatten.
3. Classification framework: BOT vs HUMAN, then HUMAN → (CORRECTNESS, SECURITY, ARCHITECTURE, SCOPE CREEP, QUESTION, NIT, PRAISE, DISCUSSION, OUTDATED, DUPLICATE).
4. Triage report saved to `$CHE_WORKSPACE_SHARED/pr_comments/pr-<N>_<YYYYMMDD>.md` (resolve via `che_compute_paths`; NEVER inside `<WORKTREE_ROOT>/.trae/`).
5. Deliver to user chat: summary buckets count, Section 1 (TO IMPLEMENT) sorted by severity, Section 2 (DRAFT RESPONSES) English polite non-argumentative, Section 3 DISCUSSION PENDING USER, Section 4 NIT optional, Section 5 RESOLVED SILENTLY.
6. Aggregated implementation plan as atomic commits batches.
7. If user says: implement → apply fixes in worktree. If user says: post replies → `gh pr reply` each drafted comment.
**Syntax examples:**
```
/che-pr-comments https://github.com/myorg/myrepo/pull/42
```

---

## `/che-ci-fix <ACTIONS_RUN_URL_or_PR_URL>`

**What it does:** Diagnoses and fixes failing CI (GitHub Actions). Pulls failed jobs/steps, extracts error logs, classifies root cause (build / lint / typecheck / deterministic-test / flaky / dependency-lockfile / CI-YAML-script / migration / INFRA-EXTERNAL — do not code). Proposes minimal fix plan per job. User approves plan → implements fixes in worktree locally → pushes. For INFRA/EXTERNAL (secrets rotated, GitHub outage, npm registry 5xx): stops and reports to user without touching code.
**When to invoke:** CI goes red on a PR or Actions run and you want a diagnosis + fix.
**Agent action:**
1. Invoke `che-ci-fixer` skill.
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
/che-ci-fix https://github.com/myorg/myrepo/actions/runs/987654
/che-ci-fix https://github.com/myorg/myrepo/pull/42
```

---

## `/che-design` <modo: A|B|C opcional> [--path /abs/path/to/save.pen] [--palette #HEX1,#HEX2] [--tone "Tom de Voz"]

## Alias: `/che-figma`

**What it does:** Full design che: 3 modos. (A) Social Media: 6 criativos (Feed/Stories/Reels) + copy profissional + imagens geradas por IA + export PNG 2×. (B) UI/UX Feature: wireframes → high-fidelity → dev-spec (tokens Tailwind exportáveis). (C) Design System atômico: Tailwind tokens ↔ variáveis (Light/Dark mode) + 12 componentes (Button/Card/Input etc.) 4 variants + export CSS/JSON/Tailwind. Uses **local** `mcp_open-pencil` MCP (140+ tools equivalente a Figma desktop).
**When to invoke:** Você quer designs profissionais prontos para produção direto por aqui: criativos de rede sociais com copy, telas de produto, ou um design system atômico sincronizado com Tailwind.
**Agent action (PREFLIGHT obrigatório se parâmetros faltarem):**
1. Invocar **`che-social-ui-designer`** skill IMEDIATAMENTE.
2. Preflight pergunta #1 (se `--mode` omitido): "Qual modo? A) Social Media / B) UI-UX / C) Design System" (AskUserQuestion 1 pergunta, 3 opções).
3. Preflight pergunta #2 (equivalente a "qual projeto figma trabalhar", user-asked): qual caminho ABSOLUTO para salvar o arquivo de design (`.pen` = OpenPencil / Figma-equivalente). Default `/home/laion/.trae/designs/<modo>-<slug>-YYYYMMDD.pen`.
4. Preflight pergunta #3 (se faltar): paleta / tipografia / tom de voz (copy).
5. Skill executa o modo selecionado §A/B/C com fail-fast + quality gates WCAG AA.
6. Entrega final sempre com: arquivos exportados PNG 2× / tokens / source `.pen` + 1 ÚNICA oferta de aprofundar (§18 contracts).

**Syntax examples:**
```
/che-design A                                # Social Media batch completo (2 feed + 2 stories + 2 reels templates + copy + imagens)
/che-design B --path /home/laion/designs/dashboard-creator.pen  # UI-UX feature dashboard
/che-design C --palette "#6D28D9,#F59E0B,#111827,#F9FAFB" --tone "Luxo minimalista"
/che-figma A slug:"lancamento-festival-UK"   # alias igual
```

---

## Relationship between commands and skills (UPDATED)

| Command | Primary skill invoked |
|---|---|
| `/che-spec` | `che-spec` (4 input sources: existing / ticket URL / PRD Flockr path / brief description; YAML frontmatter + 7 canonical sections; Approved gate; saves DURÁVEL workspace-shared; standalone ou invocado automaticamente por /che-start SM §0.5) |
| `/che-start` | `che-scrum-master` (§0.5 auto-invokes che-spec if no Approved SPEC; auto-detects serial vs parallel; falls back serial if any precondition fails) |
| `/che-parallel` | `che-scrum-master` → `che-executor-dispatcher` (explicit parallel; ERROR if can't parallelize; no serial fallback) |
| `/che-ship` | `che-ship` (commits → push → DRAFT PR → assign) |
| `/che-fix` | `che-debugger-bugfix` (scientific debug loop, different from features) |
| `/che-review` | `che-code-review` (HIGH / CRITICAL + scope only) |
| `/che-diff` | `che-diff-context` (contexto conversa leve — NO verdict) |
| `/che-manual-test` | `che-manual-test-executor` (Playwright MCP + HTTP driver, steps de manual_test_plan.md c/ evidências screenshot + report 8 seções. Setup approval gate OBRIGATÓRIO. Fronteira vs che-qa: QA = build/lint/test automatizados; Manual = browser/interativo real.) |
| `/che-pr-comments` | `che-pr-comments` (triage, implementation plan, reply drafts) |
| `/che-ci-fix` | `che-ci-fixer` (classify CI failure + minimal fix) |
| `/che-design` | `che-social-ui-designer` (3 modos: Social Media / UI-UX / Design System — local open-pencil MCP equivalente Figma) |
| `/che-status` | Reads `task_graph.md` directly, no skill invocation needed |
| `/che-skip` | Updates `decisions.log.jsonl` + `task_graph.md`; tells SM to treat gate as passed |
| `/che-decisions` | Reads `decisions.log.jsonl` |
| `/che-summary` | Uses SM logic to generate interim final_summary |
| `/che-abort` | SM writes ABORTED metadata |

---

## Rules for the AGENT when user issues a command

1. **Worktree check FIRST.** If `/che-*` is called but worktree is not yet confirmed → **ASK FOR WORKTREE before executing anything else.** Even if the command is just `/che-status`. EXCEÇÃO: `/che-spec` roda binding preflight se não houver (auto-cria Level 1+2).
2. **English for files, Portuguese for chat.** The reports printed to the user (status, decisions, warnings) are in Portuguese. The files written to disk are in English.
3. **Do NOT invent new commands.** Only those listed above, plus any repo-local `/flockr-*` commands already defined per-worktree.
4. **Logging.** Every command execution results in a new entry to `session.md` under `$CHE_SESSION_DIR/` (resolvido via contract `che_compute_paths`; NÃO mais em worktree/.trae — MORATÓRIA §19.1).
5. **SPEC GATE ordem de precedência para planejamento:**
   - `/che-spec` standalone = apenas documento (sem scope-capture / dev), roda antes do che-start.
   - `/che-start` = SM §0.5 auto-chama che-spec SE não houver SPEC Approved, passando args input (ticket/prd/desc) do usuário; Approved libera scope-capture.

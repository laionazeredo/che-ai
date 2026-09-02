---
name: "harness-debugger-bugfix"
description: "Scientific debugging harness for bug fixes: user provides expected behavior + reproduction steps; the Debugger expert loops through hypothesize→instrument→reproduce→analyze→fix→verify until expected behavior is met. Demonstrates the fix or provides clear manual reproduction guide. Invoke when user describes a bug/incorrect runtime behavior and wants it fixed, or when /harness-fix is called."
---

# Harness — Debugger / Bugfix Expert (Scientific Debug Loop)

This is the **specialized harness for bug fixes**, NOT for features.
The developer mindset here is **hypothesis-driven + evidence-collecting**, not feature-building.

> **Why a different loop for bugs?** Feature harness is plan-first, deterministic. Bug harness is observation-first: you must REPRODUCE before you understand, then iterate hypotheses until the root cause is found. Evidence beats plan.

---

## 0. Pre-flight — Worktree + inputs

### 0.1 Worktree-first enforcement

Same as the global rules: if worktree path is NOT provided by the user → **ASK immediately** before proceeding to any other step. No code runs, no files opened.

### 0.2 Required inputs from user (block until provided)

User MUST provide:
1. **Expected behavior**: What SHOULD happen? (English in files, PT from user is OK we translate)
2. **Actual behavior / Bug description**: What IS happening? Include stack traces, error messages, screenshots if available.
3. **Reproduction steps**: Minimum, clear numbered steps (1, 2, 3, ...) to trigger the bug reliably. Include:
   - Which route / endpoint / URL?
   - Credentials / role required (admin? regular user? logged out?)
   - Environment (staging? local dev? which branch? which worktree?)
   - Sample payload / form input / seed data if any
4. **Ticket reference** (if any): Linear/Jira URL/ID — optional

If user fails to provide ANY of 1, 2, or 3 → **ASK with specific questions** before starting debug loop. Do NOT guess reproduction steps.

### 0.3 Session artifacts dir + 🔴 STORAGE PREFLIGHT (MORATÓRIA §20)

Rode **exatamente este bloco ANTES** de escrever qualquer arquivo (logs, traces, screenshots, session md, decisions append):

```bash
HARNESS_HOME="${HARNESS_HOME:-$HOME/.trae}"
CONTRACT="$HARNESS_HOME/contracts/harness_sessions_contract.sh"
if [ -f "$CONTRACT" ]; then
  # shellcheck disable=SC1090
  source "$CONTRACT"
else
  echo "❌ FATAL: $CONTRACT não encontrado. HARD STOP — zero arquivos escritos sem storage boundary. exit 98"
  exit 98
fi

SESSION_ID="${HARNESS_CURRENT_SESSION_ID:-fallback-debugger-session}"
harness_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
harness_ensure_session_dirs "$WORKTREE_ROOT"

# Double-guard: asserts fail-fast se qualquer diretório de output cai DENTRO worktree (exit 99)
harness_assert_outside_worktree "$HARNESS_SESSION_DIR" "$WORKTREE_ROOT" "HARNESS_SESSION_DIR (efêmero debug)"
harness_assert_outside_worktree "$HARNESS_WORKSPACE_SHARED" "$WORKTREE_ROOT" "HARNESS_WORKSPACE_SHARED (durável decisions)"

# Construir TODOS os paths UMA VEZ aqui via helper ÚNICO. Depois reuse só estas variáveis:
BUGFIX_SESSION_MD="$(harness_output_path "debugger" "bugfix-session" "${BUG_SLUG:-generic-bug}" "session" "md")"
# Hypothesis log (jsonl append via atomic helper):
HYPOTHESIS_LOG="$(harness_output_path "debugger" "hypotheses" "${BUG_SLUG:-generic-bug}" "session" "jsonl")"
# Evidence dir = HARNESS_SESSION_DIR/qa/evidence/<related_id>/ (já criado pelo helper quando necessário)
```

**Arquitetura de storage (TODOS estritamente FORA worktree do usuário):**
```
$HARNESS_SESSION_DIR/                       ← ephemeral per-session
  └── debugger/<BUG_SLUG>/                  ← related_id agrupa tudo deste bug
        ├── 20260902-133000-bugfix-session.md   (append por loop iteration)
        └── 20260902-133000-hypotheses.jsonl    (cada hipótese uma linha)
$HARNESS_WORKSPACE_SHARED/                  ← durable: decisions.log.jsonl (único por worktree)
```

**NUNCA escreva em `<WORKTREE_ROOT>/.trae/` nem `<WORKTREE_ROOT>/reports/` nem qualquer path relativo dentro worktree.** MORATÓRIA §20. Se por qualquer motivo você precisar salvar algo dentro worktree (exceção rara), pare e peça confirmação VERBATIM EXPLÍCITA do usuário em texto.

Append to `$BUGFIX_SESSION_MD` on every loop iteration using `harness_write_file_atomic` (pipe append) ou `>>` redirection (seguro pois o path já passou por assert outside).

---

## 1. Phase 0 — Baseline (once per bug)

### Step 1.1 Reproduce the bug FRESH (evidence #1)

1. Start the relevant services using the repo's documented way (follow repo AGENTS/docs/patterns).
2. Execute reproduction steps EXACTLY as user wrote.
3. **Capture evidence:**
   - Stack traces (copy first 40 lines)
   - HTTP request/response (status, body preview — never secrets)
   - Server logs excerpt (first ERROR and ~20 lines around it)
   - Screenshots if UI/visual bug
   - DB state (relevant rows / queries if DB-backed bug)
4. Record to session file: `✅ REPRODUCED` or `❌ FAILED TO REPRODUCE`.

**If FAILED TO REPRODUCE (blocker):**
- Do NOT start fixing.
- Go back to user with: "Não consegui reproduzir. Checklist do que diverge: (1) versão X vs Y? (2) usuário/role? (3) dados de seed? (4) branch errada?". Ask user clarifying questions + suggest pair steps until we get a clean repro.

### Step 1.2 Minimize the reproduction

Once reproduced: try to make reproduction steps even shorter.
- Remove unnecessary steps.
- Create a minimal test case (unit test snippet) that triggers the error path if possible.
- This minimal case becomes the **regression test at the end.**

### Step 1.3 Build the initial hypothesis list

From the evidence:
- State the **symptoms clearly** (what breaks, at what line, on which data shape).
- Write **3 candidate root causes** as numbered hypotheses, ranked by likelihood:
  ```
  Hypothesis H1 (Likelihood: HIGH): <explanation>
  Hypothesis H2 (Likelihood: MEDIUM): <explanation>
  Hypothesis H3 (Likelihood: LOW): <explanation>
  ```
- NEVER start editing code before hypotheses are written.

---

## 2. Phase 1 — Debug Loop (repeat per hypothesis, max 5 iterations per bug)

```
    ┌─────────────────────────────────────┐
    │  HYPOTHESIZE (pick next ranked Hn) │
    └────────────────────┬────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  INSTRUMENT — add targeted logs /   │
    │  breakpoints / assertions           │
    └────────────────────┬────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  REPRODUCE — run the minimal case   │
    │  + capture new evidence             │
    └────────────────────┬────────────────┘
                         │
                         ▼
    ┌─────────────────────────────────────┐
    │  ANALYZE evidence                   │
    │  Hypothesis CONFIRMED / REFUTED?    │
    └──────┬───────────────────┬──────────┘
           ▼                   ▼
      REFUTED              CONFIRMED
           │                   │
           │ rank next Hn      ▼
           │               FIX — minimal code change
           │                   │
           │                   ▼
           │             VERIFY fix:
           │             repro steps now show EXPECTED behavior
           │                   │
           ▼                   ▼
  > 5 total iterations? ──▶ YES → FIX DONE
           │
           ▼ NO
  Loop user: "estamos em N iterações. Parece que a causa raiz é X. Próximos passos? (Y/N)"
```

### Mandatory per-iteration evidence in bugfix_session.md

Every loop iteration appends a section:
```
## Iteration N — Hypothesis H<X>

### Instrumentation
- Added: <file:line> debug_log
- Changed: <none — this iteration was observability only>

### Reproduction output (captured)
<stack trace / assertion / log lines>

### Analysis — CONFIRMED or REFUTED?
- Decision: CONFIRMED / REFUTED
- Why: <evidence-based rationale>

### If CONFIRMED:
- Root cause (1 sentence): ...
- Proposed minimal fix (what EXACTLY will change, and why this fix, not alternatives):
  - Option 1: <what files change>
  - Option 2: <alternative>
  - DECISION: Option X — <rationale>
```

### Forbidden patterns during debugging

- **No shotgun edits:** Changing 5 files "hoping it helps" is FORBIDDEN. One hypothesis → targeted instrumentation or one single minimal fix.
- **No `console.log` left in production code at end.** Remove ALL debug logging after verification. Clean up.
- **No refactoring alongside the bugfix.** The bugfix = the minimal code change. If a refactor is needed → separate commit, separate PR, after the fix is verified and merged.

---

## 3. Phase 2 — Engineering of the fix (after root cause CONFIRMED)

### Step 3.1 TDD for the bug

Write a test (unit preferred, integration if needed) that:
1. Fails before the fix (confirms bug reproduction via test)
2. Passes after the fix (confirms fix)

The test SHOULD test behavior (input/output, state transition), not implementation details.

### Step 3.2 Apply MINIMAL fix

- Apply only the lines that actually fix the root cause.
- If adjacent code "also looks wrong" → note in decision.log for follow-up PR, do NOT fold into this bugfix.

### Step 3.3 Run: fix + regression test

1. Confirm the new test now PASSES.
2. Run **related tests** (files in the same module, affected) to confirm no regressions.
3. Optional: full test suite if task size is small or repo supports it quickly.

### Step 3.4 Manual verification

Demonstrate to yourself via the REPRODUCTION steps that:
- Before fix: actual behavior (BAD) — confirm you can trigger it
- After fix: expected behavior (GOOD) — confirm you now see it

Record before/after evidence to the session file.

---

## 4. Phase 3 — Handoff to user

Two possible outcomes:

### Outcome A — ✅ FIX CONFIRMED

Report to user (in Portuguese):
```
✅ Bug identificado e corrigido.

📋 Resumo técnico:
  • Sintoma: <1 frase em PT>
  • Causa raiz: <1 frase em PT>
  • Arquivos alterados:
      - <path> (EDIT — linhas XX-YY)
  • Teste de regressão adicionado: <path/to/spec>

🔬 Como eu demonstrei que funciona:
  1. Antes do fix: <steps> → <mensagem de erro / comportamento ruim>
  2. Depois do fix: <mesmos steps> → <comportamento esperado>
  3. Teste unitário `describe(...)` falha sem o fix, passa com.

🧪 Como VOCÊ pode verificar:
  <passo a passo em PT, exatamente igual à sessão de reprodução inicial do usuário>
  1. git checkout <branch>
  2. corepack pnpm install
  3. ...
  4. Expected: ...

📎 Artefatos (todos FORA worktree, resolvidos via `harness_compute_paths`):
  - bugfix_session.md completo: `$HARNESS_SESSION_DIR/bugfix_session.md`
  - Decisions: `$HARNESS_WORKSPACE_SHARED/decisions.log.jsonl`
  - Se houver ticket: recomendo colar link lá.
```

### Outcome B — ⚠️ NOT FIXED YET (after 5 iterations or blocked)

Report:
```
⚠️ Não consegui chegar no fix nesta sessão.

Progresso feito:
  • 5 iterações executadas. Cada hipótese H1-H5 REFUTADA.
  • O que eu já DESCARTAMOS como causa raiz:
      - H1: ... (evidence: ...)
      - H2: ...
      ...
  • Minha hipótese mais forte atual para a próxima sessão:
      - H6: ...

Próximos passos recomendados:
  Opção 1) Eu continuo a investigação por mais 3 iterações (vai gastar +tokens)
  Opção 2) Você me dá mais contexto: (1) histórico do bug (2) prints extras (3) exact data seed
  Opção 3) Pair programming / passo a passo guiado por você
```

---

## Appendix A: Observability toolbox (prefer these — order matters; repo-contextual)

| Tool | Use when | Command hints (if repo-agnostic) |
|---|---|---|
| Repo logger (preferred) | Add debug-level line during instrument phase | Use the project logger; remove after |
| Structured logs (OTel, pino, winston) | Trace request path | Look for traceId in headers |
| HTTP curl/HTTPie | API bug repro | Reproduce request offline in .http scratch file |
| Node inspect | Node.js runtime bug | `NODE_OPTIONS="--inspect" ...` then chrome://inspect |
| Python pdb | Python bug | `breakpoint()` at suspected line |
| Pry / byebug | Ruby bug | `binding.pry` |
| Delve | Go bug | `dlv debug` |
| Rust dbg! macro + lldb/gdb | Rust bug | Wrap suspected: `dbg!(&var);` |
| Browser devtools | UI bug | Network tab + break on XHR; Console log filter for errors |
| Postgres `EXPLAIN ANALYZE` | DB perf bug | Run query with analyze |
| tRPC query trace | tRPC specific | enable `tRPC logger link` with level=debug for this request |

Always prefer repo-native tooling first. Never add a new observability package just to debug — use what's installed.

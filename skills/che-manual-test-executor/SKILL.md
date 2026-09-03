---
name: "che-manual-test-executor"
description: "Executes the manual_test_plan.md step-by-step using Playwright MCP (browser interactions + screenshots) or HTTP/curl requests for API-only scenarios, generates evidence files (PNG screenshots, JSON logs), and delivers a structured pass/fail report per AC. Call this AFTER manual_test_plan.md is written by che-scrum-master and BEFORE che-ship, or standalone when user passes a worktree + task-id or a manual test plan path explicitly."
---

# Che — Manual Test Executor (step-by-step Playwright + HTTP)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Manual Test Plan canonical format (AC structure with GWT / Manual Steps / Severity): che-scrum-master `references/MANUAL_TEST_PLAN_TEMPLATE.md`
> - Nx/pnpm build/dev service startup commands: `_shared_checklists/NX_PNPM_COMMON.md`
> - Worktree Session Binding (one session = one worktree, doubt = ask): engineering-contracts §19
> - Output shape rules (concise 4 sections, diagonal readability, deep-dive gate): engineering-contracts §18

## What this skill does (vs QA automated)

| Concern | `che-qa` | This skill `che-manual-test-executor` |
|---|---|---|
| Scope | lint / typecheck / build / unit / E2E commands (CI-style) | **Manual Test Plan steps** written in `$CHE_WORKSPACE_SHARED/manual_test_plan.md` (via `source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"`) — DURÁVEL, compartilhado entre sessões nesta worktree. |
| Driver | Shell commands (pnpm/vitest/playwright CLI) | **Playwright MCP** (open tab, navigate, click, fill, screenshot) + **HTTP driver** (curl-style via playwright_get/post/put/patch/delete). |
| Evidence | Command exit codes + stdout/stderr | **PNG screenshots per step**, visible text assertions, HTTP response bodies, browser console logs. |
| Output | Per-pass/fail command line summary | **Per-AC pass/fail report** with evidence links + environment checks pass/fail + smoke check summary. |

> **Rule:** If user says "rodar testes unitários/E2E" → use `che-qa`. If user says "executar o plano de testes manual / abrir navegador e testar / checar o comportamento visual" → use THIS skill. Never mix.

---

## 0. Preconditions (non-negotiable)

1. **WORKTREE_ROOT absolute path** provided (by SM or user via command).
2. **Task ID or explicit path to `manual_test_plan.md`** — one of the two:
   - Option A (from che session): `$CHE_WORKSPACE_SHARED/manual_test_plan.md` (via contract) exists (DURÁVEL workspace-shared).
   - Option B (standalone): user passes explicit file path to a Markdown file containing the AC sections below.
3. If neither exists → STOP. Ask user to provide task-id or the manual_test_plan.md path.
4. **Worktree Session Binding preflight + 🔴 STORAGE BOUNDARY (engineering-contracts §19 + §20 MORATÓRIA — NON-NEGOTIABLE):**
   ```bash
   # (a) Source contrato + resolver paths CANÔNICOS
   CHE_HOME="${CHE_HOME:-$HOME/.trae}"
   CONTRACT="$CHE_HOME/contracts/che_sessions_contract.sh"
   [ -f "$CONTRACT" ] || { echo "❌ FATAL: $CONTRACT não existe. Zero writes permitidos sem storage boundary. exit 98"; exit 98; }
   # shellcheck disable=SC1090
   source "$CONTRACT"
   SESSION_ID="${CHE_CURRENT_SESSION_ID:-fallback-manual-test-session}"
   che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
   che_ensure_session_dirs "$WORKTREE_ROOT"

   # (b) Double-guard: assert NENHUM dos diretórios de output cai DENTRO da worktree
   che_assert_outside_worktree "$CHE_SESSION_DIR" "$WORKTREE_ROOT" "CHE_SESSION_DIR (efêmero QA evidence)"
   che_assert_outside_worktree "$CHE_WORKSPACE_SHARED" "$WORKTREE_ROOT" "CHE_WORKSPACE_SHARED (durável plans)"

   # (c) PATHS CANÔNICOS PARA TODOS OS OUTPUTS DESTA SKILL — construa UMA VEZ aqui, reuse everywhere
   # Report final (session-scope — efêmero, esta execução apenas):
   MANUAL_TEST_REPORT_PATH="$(che_output_path "qa" "manual-test-execution-report" "${TASK_ID:-standalone}" "session" "md")"
   # Evidence directory helper: todo screenshot/log deve usar che_output_path type=qa scope=session related_id=TASK_ID suffix="AC-<id>"
   # Exemplo screenshot AC-2:  "SCREENSHOT_AC2_PATH=$(che_output_path "qa" "screenshot" "${TASK_ID:-standalone}" "session" "png" "AC-002")"
   # Exemplo log env setup:    "ENV_SETUP_LOG_PATH=$(che_output_path "qa" "env-setup" "${TASK_ID:-standalone}" "session" "log")"
   ```
   - Check `$CHE_SESSION_DIR/binding.md` Level2 entry if present (EFÊMERO per-session).
   - Mismatch with provided WORKTREE_ROOT → BLOCK. Ask override/switch/cancel.
   - Missing binding → follow §19 canonical binding flow (global registry Level1 + Level2), ask user confirm once.
   - **HARD RULE A PARTIR DAQUI:** NUNCA construa path manualmente. Todo screenshot, todo log, todo report = obrigatoriamente via `che_output_path "qa" ...`. Nenhum arquivo PNG/LOG/MD cai dentro worktree. MORATÓRIA.

### 0.1 EVIDENCE RETENTION POLICY (ONDA4 — DOIS LOCAIS, NUNCA NA WORKTREE USUÁRIO)

```bash
# =============================================================
# POLÍTICA DUPLO LOCAL — MORATÓRIA §20 engineering-contracts:
# NENHUM evidence/manifest é escrito dentro de WORKTREE_ROOT/*
# por padrão. Override = usuário pedir VERBATIM.
# =============================================================

# --- LOCAL 1 — EFÊMERO / SESSION-SCOPE (pesados, TTL 30 dias) ---
# Screenshots FULL-size CADA step, logs brutos browser console,
# HTTP response bodies, get_visible_text capture. Fica na sessão.
# Handoff limpeza: sessões mais antigas que 30 dias = TTL.
MANUAL_SESSION_EVIDENCE_DIR="$CHE_SESSION_DIR/qa"
mkdir -p "$MANUAL_SESSION_EVIDENCE_DIR/screenshots" "$MANUAL_SESSION_EVIDENCE_DIR/logs" "$MANUAL_SESSION_EVIDENCE_DIR/api"

# --- LOCAL 2 — DURÁVEL / WORKSPACE-SHARED (audit trail LEVE) ---
# Path canonico via contract helper type=qa scope=workspace related_id=commit_7char.
# SÓ CONTÉM:
#   (i)   evidence_manifest_<SHA16_MANIFEST>.json
#   (ii)  1 thumbnail JPEG/PNG FINAL por AC PASS ≤200KB
CURRENT_COMMIT_7CHAR="${CURRENT_COMMIT_7CHAR:-$(cd "$WORKTREE_ROOT" && git rev-parse --short=7 HEAD 2>/dev/null || echo "HEAD-detached")}"
MANUAL_WORKSPACE_AUDIT_DIR="$(che_output_path "qa" "audit" "commit-${CURRENT_COMMIT_7CHAR}" "workspace" "tmp")"
MANUAL_WORKSPACE_AUDIT_DIR="$(dirname -- "$MANUAL_WORKSPACE_AUDIT_DIR")"
mkdir -p "$MANUAL_WORKSPACE_AUDIT_DIR"
che_assert_outside_worktree "$MANUAL_WORKSPACE_AUDIT_DIR" "$WORKTREE_ROOT" "MANUAL_WORKSPACE_AUDIT_DIR (durable hash manifest)"
```

**Manifest JSON Schema OBRIGATÓRIO (mesmo schema che-qa):** mesmas keys `generated_at_utc / commit_7char / session_id / qa_run_passed / per_test_file_sha256 / per_evidence_sha256 / per_behavior_result / thumbnail_path` (ver che-qa §-0.1.1 para formato canônico). Para esta skill, `per_behavior_result` mapeia AC-IDs manual (ex: `AC-001 → PASS`).

**Per-AC Screenshot Rules (HARD):**
1. **Cada screenshot FULL via playwright_screenshot** → sempre salvo em `LOCAL1 Session` (Session TTL30). Calcula SHA256 do arquivo → insere em `per_evidence_sha256`.
2. **Após THEN verificado (último step da AC):** gerar thumbnail width=800px JPEG quality=75%. **SALVA SÓ O THUMBNAIL em LOCAL2 Workspace.** Se PNG → reduzir dimensões até ≤200KB. Se não couber → thumbnail=null.
3. **NÃO salva screenshot FULL em LOCAL2 (moratória tamanho).** Apenas SHA256 dele no manifest.

---

## 1. STEP 0 — Parse the Manual Test Plan into executable steps

Open and parse `$CHE_WORKSPACE_SHARED/manual_test_plan.md` (DURÁVEL workspace-shared, via contract) or user-provided custom path.

Extract into an in-memory `PLAN_DATA` object with these sections:

### 1.1 Environment Setup (§0 do plano)
- Commands from the ```bash``` block under `## 0. Environment Setup — Preconditions`
- Test accounts / test data list (names only — never values)
- App URLs / base URLs present (extract ALL URL strings like `http://localhost:3000`)

### 1.2 Acceptance Criteria list (§1 Scenario Test Cases)
For every `### AC-<N>:` block:
- Extract AC-ID, Title, GIVEN, WHEN, THEN
- Extract the numbered list under `#### Manual Steps` (step numbers + action text)
- Extract Severity if FAILS field (BLOCKER / HIGH / MEDIUM / LOW)
- If Automated equivalent command present → note it (but this skill still executes MANUAL steps; automated is extra run if user asks).

### 1.3 Smoke Test Checklist (§2)
Extract table rows S1..S5. Mark which ones this skill CAN execute (S3/S4 via browser; S1/S2 via shell commands; S5 via server log grep if accessible). §3 Security/Compliance is **human-only per plan**, this skill skips it (explicitly note in report "HUMAN_REVIEW_NEEDED" for §3). §4 Rollback Plan = informational only, do not execute.

### 1.4 Error if no ACs found
If zero `### AC-` headers → STOP. Report: "manual_test_plan.md doesn't have AC sections. Need at least 1 AC-<N> block with Manual Steps numbered list."

---

## 2. STEP 1 — Evidence directory pre-creation

Create this directory structure immediately after parsing succeeds (before any browser/curl). Use `source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"` + `che_ensure_session_dirs` first.

```
$CHE_SESSION_DIR/qa/              ← EFÊMERO per-session (generated evidence, never in user code)
├── ENVIRONMENT_SETUP.log             # stdout/stderr de setup commands executados
├── screenshots/
│   ├── AC-<N>_<slug>/
│   │   ├── step_<K>_screenshot.png   # um PNG por step que faz interação browser / verificação visual
│   │   ├── step_<K>_visible_text.txt # conteúdo get_visible_text() após step K
│   │   ├── step_<K>_api_response.json# resposta HTTP se step fez get/post/etc
│   │   ├── step_<K>_console.log      # playwright_console_logs() se houver erros/warnings
│   │   └── FINAL_ASSERT_<X>.png      # screenshot final do THEN expected verificado
│   └── SMOKE_<Sx>_<slug>.*           # evidências smoke tests S1..S5 (png/log)
├── logs/
│   └── execution.log                 # timeline global: cada step timestamp + ação + resultado
```

---

## 3. STEP 2 — Environment Setup Execution (§0 do plano)

Goal: make the target app reachable so browser steps can run.

1. **User approval gate first BEFORE running setup commands.** Present the setup plan to the user:
   > `Vou executar estes passos de setup em <WORKTREE_ROOT>. Confirmar? (A = Sim, executar todos) (B = Pular setup, app já está rodando em <URL>) (C = Cancelar)`
   - If user chooses B → ask user to provide base URL (e.g., `http://localhost:3000`) + skip setup block run.
   - If C → stop entirely.
2. **Run each command from §0 bash block sequentially** inside `WORKTREE_ROOT`.
3. Record stdout+stderr to `ENVIRONMENT_SETUP.log`.
4. **Hard-fail rule:** If any setup command returns non-zero exit (pnpm install fail / build error / port in use):
   - STOP before any AC step runs. Report which command failed + 20 last lines of log.
   - Ask: "Setup comando <N> falhou: (A = Tentar comando alternativo <sugestao>) (B = Skip setup, app acessível em <URL>) (C = Cancelar)".
5. After setup OK: confirm base URL(s) are reachable (HTTP GET to root should return 200 or 302 via playwright_get). If not → warn but proceed with ACs; user may have custom URL.

---

## 4. STEP 3 — AC Execution Loop (per AC-N in order)

For each AC block in extracted PLAN_DATA.AC_LIST:

### 4.1 AC Header
Append to `execution.log`:
```
[<ISO ts>] === START AC-<N>: <TITLE> ===
```

### 4.2 Per-Step Driver Dispatch (how to convert natural language steps into Playwright MCP calls)

Each numbered step under Manual Steps is classified into ONE driver type (decision rules below). **Execute ONE step at a time. Never batch.** After each step → write evidence to disk. Append PASS/FAIL/SKIP to timeline.

#### Driver classification rules (match in order):
| Step pattern says | Driver used | MCP tool / action |
|---|---|---|
| "Navigate to `URL`" / "Open `URL`" / "Acessar URL" | Playwright (browser) | `playwright_navigate` with URL + default viewport + headless default |
| "Click `<button name or CSS selector>`" | Playwright | `playwright_click` using `selector` (prefer CSS `button:has-text("...")` if natural-language name; fallback to ask user selector if ambiguous) |
| "Fill the form with Field A: `value` Field B: `value`" / "Type X" | Playwright | `playwright_fill` — one call per field. Selector = `input[name="<field>"]` or `label:has-text("Field A") + input` etc. If selector ambiguous → ASK user (§19 doubt). |
| "Select `<option>` from `<dropdown>`" | Playwright | `playwright_select` |
| "Submit" / "Click Submit" | Playwright | `playwright_click` on `button[type=submit]` + wait 2s after for nav |
| "Upload file `<path>`" | Playwright | `playwright_upload_file` |
| `curl` mention or explicit "call API <METHOD> <URL>" / "request GET" | HTTP Driver | `playwright_get / playwright_post / playwright_put / playwright_patch / playwright_delete` with URL + headers if any. |
| "Check page: expected visible text `XYZ`" / "URL changed to `/path`" | Assertion Playwright | After any driver call above → run: (a) `playwright_get_visible_text()` and grep for `XYZ`; (b) check current page URL if step requires URL match. Record result as assertion. |
| "Check server logs / email sandbox / external system" | **Cannot execute → SKIP with HUMAN_REVIEW_NEEDED note** | Do not fake. Write to report "Step K: requires human verification (external system)". |
| Step is completely ambiguous / no driver pattern matches | **STOP → ASK user.** | Do not guess an action. Example: "proceed with checkout" without UI flow described → ask clarification. |

### 4.3 Evidence capture rules (MANDATORY per step)
After EACH step run (regardless of pass/fail):
1. **Browser step:**
   - `playwright_screenshot` with `name="AC-<N>_step_<K>"` + `savePng=true`, saved into evidence dir.
   - `playwright_get_visible_text()` → save as `step_<K>_visible_text.txt`.
   - `playwright_console_logs()` → if any ERROR/WARN entries → save `step_<K>_console.log`.
2. **HTTP step:**
   - Save full response body (if JSON pretty-printed) as `step_<K>_api_response.json`.
   - If `assert_response` was used → save assertion result in file name.
3. **Assertion check step:**
   - Screenshot FINAL_ASSERT named `FINAL_ASSERT_<short_desc>.png`.
   - Record pass/fail based on THEN expected text / URL match.

### 4.4 Then-Block Final Verification
When all numbered steps of an AC have been executed:
- Run explicit verification against the `THEN` extracted text.
- Classification:
  - ✅ **PASS**: All THEN conditions found in visible_text / HTTP response / URL. At least one screenshot per visual THEN.
  - ⚠️ **PARTIAL**: Some THENs pass, others SKIPPED (external system / human-only checks).
  - ❌ **FAIL**: At least one THEN not matched; or step K threw exception/timeout; or console shows CRITICAL error + THEN mismatch.
  - ⏭️ **SKIP**: ALL steps are HUMAN_REVIEW_NEEDED (no executable step).
- Append final verdict for AC-<N> into `execution.log` + to report data structure.
- Close playwright session explicitly (`playwright_close`) to free resources if opening next AC needs a fresh session (AC isolation rule).

---

## 5. STEP 4 — Smoke Test Checks (§2 do plano, light)

After all ACs pass/partial/fail (do NOT abort if ACs failed — smoke still runs so we know scope of breakage):

| Smoke ID | How this skill executes |
|---|---|
| S1 Build | Shell command equivalent (from QA stack detection profile): run build → capture exit code + last 10 lines. |
| S2 Lint | Same: lint command. ≤5 warnings is PASS per plan. |
| S3 Login | If plan contains a login AC or has login steps in test accounts → execute a login-only scenario via Playwright + screenshot landing page. Else: HUMAN_REVIEW_NEEDED note. |
| S4 Nav top-level pages | Collect nav links from base page footer/header (after login if S3 succeeded) → playwright_navigate 3 top-level pages. 500 / WSOD = FAIL. Screenshot each. |
| S5 Server logs | Best-effort: grep CRITICAL/ERROR from last 50 lines of platform dev output (if service was started in this session). Not accessible → HUMAN_REVIEW_NEEDED. |

Save each evidence file: `SMOKE_<Sx>_<name>.log` or `.png`.

---

## 6. STEP 5 — Build Final Structured Report

Canonical sections (match references/MANUAL_TEST_EXECUTION_REPORT.md). Use language **English for file content, Portuguese when delivering chat summary §18**.

Report saved to: a variável **`$MANUAL_TEST_REPORT_PATH`** (já construída durante o STORAGE PREFLIGHT no §0 item 4c usando `che_output_path`). Resultado exemplo:
```
$CHE_SESSION_DIR/qa/evidence/T123-refund/20260902-130000-manual-test-execution-report.md
```
⚠️ NÃO use path hardcoded `reports/MANUAL_TEST_EXECUTION_REPORT.md`. Reutilize sempre a variável do preflight. Se por algum motivo a variável estiver vazia → RE-RUN o preflight §0 item 4 ANTES de salvar qualquer coisa.

Report sections:
1. Header (task-id, worktree, timestamps start/end duration, target base URLs)
2. Environment Setup result (PASS / FAIL + short note + link to ENVIRONMENT_SETUP.log)
3. Per AC summary table:
   | AC-ID | Title | Verdict (✅/⚠️/❌/⏭️) | Severity se falhou | Evidência dir link | Notas |
4. Detailed per AC (one sub-section each):
   - GIVEN/WHEN/THEN original
   - Step-by-step executed action + verdict per step + evidence file links
   - Final assertion notes
5. Smoke Tests §2 result table (S1..S5)
6. Human-only items remaining:
   - §3 Security/Compliance Spot-checks → must be done by a human
   - Any steps marked HUMAN_REVIEW_NEEDED during execution
7. Rollback Plan reference (link to original manual_test_plan.md §4)
8. Overall Verdict line (top-line single sentence):
   - Overall: ✅ All BLOCKER/HIGH ACs PASS → go / ship-ready
   - Overall: ❌ ≥1 BLOCKER or ≥2 HIGH FAIL → not ship-ready
   - Overall: ⚠️ Some PARTIAL + low-severity FAIL → conditional (human review pending items)
9. **Evidence retention (ONDA4 — MANIFEST + THUMBNAIL RULES):**
   - Workspace audit manifest SHA256  = <MANUAL_EVIDENCE_MANIFEST_SHA>
   - Manifest JSON path              = <MANUAL_EVIDENCE_MANIFEST_PATH>
   - Session full evidence (TTL 30d) = $CHE_SESSION_DIR/qa/

### 6.1 STEP FINAL OBRIGATÓRIO — Gerar Evidence Manifest SHA256 (Local2 Workspace Audit)

Após salvar o report final (§6), **antes de retornar**, gere o manifest usando o MESMO algoritmo de che-qa §0.2:
- SHA256 de CADA evidence salvo em Local1 (Session) → entry em `per_evidence_sha256`.
- SHA256 de CADA screenshot FINAL_ASSERT por AC PASS → thumbnail ≤200KB em Local2 (Workspace) usando convert width=800 quality=75.
- `per_behavior_result` mapeia cada AC-ID → PASS/FAIL/PARTIAL/SKIP.
- `per_test_file_sha256` = vazio `{}` para esta skill (não executa spec files).
- Calcula SHA256 do manifest → nome arquivo `evidence_manifest_<SHA16>.json`; salva via `che_write_file_atomic`.
- Decision log entry: `MANUAL_TEST_EVIDENCE_MANIFEST` com commit_7char, manifest_sha256, manifest_path, workspace_audit_dir, session_evidence_dir.

### Chat delivery rule (§18 contracts)
The chat message user sees uses condensed §18 shape. It DOES NOT dump the full report. Chat summary contains:
- 📍 Status: overall verdict line + how many ACs PASS/FAIL
- 🧩 Key failures (if any): 3 bullets max (AC-ID + failed condition)
- 🔗 Refs: 2-3 links: path to report + to evidence dir + to original manual_test_plan.md
- ❓ Offer 1 deep-dive: "Quer abrir a primeira evidência de falha (screenshot do THEN que não bateu)?" or "Quer retry do setup com flag X?"

---

## 7. General execution rules / safety

1. **NEVER interact with production URLs**: If URL in plan contains `.prod.` / `.production.` / known production TLD+domain without explicit `test`/`staging`/`dev` subdomain, or user says explicitly "this is prod" → BLOCK. Ask for confirmation TWICE before proceeding to touch a production-looking URL. Use `NODE_ENV=test` guard. Detect via heuristic: `/(^|\.)prod(uction)?\./` or match against production domains listed in `$CHE_PROJECT_DIR/product_context.md` (if registry exists).
2. **Never log secrets**: If login requires credentials → user provides them via chat (or the skill uses environment variables loaded into Playwright header if known). **Never echo credentials in execution.log / screenshots (redact if form field visible? Best-effort; default: do not screenshot password fields filled).**
3. **AC Isolation**: After last step of each AC → `playwright_close` + new `playwright_navigate` to clean base URL on next AC. Do not share browser session state between ACs unless steps explicitly say "continue logged in from previous AC".
4. **Ambiguity rule (engineering-contracts §19 doubt = ask)**: If step text is ambiguous / selector not clear / which button? → ASK user. Never guess CSS selector.
5. **One SKIP per AC is OK; ≥5 SKIP total → warn user**: "Este plano tem muitos HUMAN_REVIEW_NEEDED. Quer parar ou continuar?"
6. **Per operation scissor check (§19)**: All screenshot PNG / log files written MUST be under `$CHE_SESSION_DIR/qa/`. If write path somehow escapes → block before saving. Evidence is NEVER written to the user worktree (MORATÓRIA .trae/ worktree, engineering-contracts §19.1).
7. **Response budget active (§18):** Chat summary = always ≤500 words. Full report and evidence → on disk only.

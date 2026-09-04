---
name: "che-compliance"
description: "Two-stage security & compliance review: LIGHT per-task diff scan and HEAVY final full-session scan. Checks for secrets, PII leaks, SQL injection patterns, auth/RLS bypasses, dangerous URLs. Invoke ONLY by che-act. NEVER fixes code directly — only reports findings."
---

# Che — Compliance & Security

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Security + PII + RLS full checklist: see `_shared_checklists/SECURITY_PII_COMMON.md`
> - GitHub CLI auth preflight + operations: see `_shared_checklists/GITHUB_CLI_COMMON.md` (final ship PR checks)
> - Nx/pnpm run order for local verification: see `_shared_checklists/NX_PNPM_COMMON.md`

Security/PII/security pattern scanner. Two stages:
- **Stage `per-task` (LIGHT)**: scans only files changed in the current task only.
- **Stage `final` (HEAVY)**: scans the FULL cumulative diff of the entire session + global patterns that per-task might have missed across files.

**CRITICAL RULE: This skill MUST NEVER modify source code directly. It only produces a structured FINDINGS report. Developer fixes, SM validates.

---

## -0.1 STORAGE BOUNDARY PREFLIGHT (CANONICAL, NON-NEGOTIABLE — run BEFORE §0 e ANTES DO PRIMEIRO WRITE)

NENHUM compliance report é escrito NA WORKTREE DO USUÁRIO por padrão. Todo report cai em che-sessions via helper centralizado. Única exceção: usuário pede VERBATIM EXPLICITAMENTE salvar um report específico lá.

```bash
# 1. Source contrato (se não herdado de SM/ship)
source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"

# 2. SESSION_ID + RELATED_ID (per-task = T<id>; final = worktree slug)
SESSION_ID="${SESSION_ID:-$(che_current_session_id 2>/dev/null || echo "compliance-$(date -u +%Y%m%d-%H%M%S)")}"
if [[ "${stage}" == "final" ]]; then
  COMPLIANCE_RELATED_ID="compliance-final-${WORKTREE_SLUG_CANONICAL:-$(basename "$WORKTREE_ROOT" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g; s/--*/-/g; s/^-//; s/-$//')}"
else
  COMPLIANCE_RELATED_ID="T${TASK_ID:-0000}-${TASK_SLUG:-per-task}"
fi

# 3. Paths canônicos + dirs (se não herdado)
if [[ -z "${CHE_SESSION_DIR}" ]]; then
  che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$(pwd)"
  che_ensure_session_dirs "$WORKTREE_ROOT"
fi

# 4. Double-guard outside worktree
che_assert_outside_worktree "${CHE_SESSION_DIR}"      "$WORKTREE_ROOT" "CHE_SESSION_DIR"
che_assert_outside_worktree "${CHE_WORKSPACE_SHARED}" "$WORKTREE_ROOT" "CHE_WORKSPACE_SHARED"

# ==== OUTPUT PATH DESTA SKILL (construído UMA VEZ) ====
# stage = final     → scope=workspace (durable: comparação entre sessões)
# stage = per-task  → scope=session   (ephemeral: só esta sessão)
COMPLIANCE_SCOPE="session"
[[ "${stage}" == "final" ]] && COMPLIANCE_SCOPE="workspace"
COMPLIANCE_REPORT_PATH="$(che_output_path "report" "compliance-${stage}" "${COMPLIANCE_RELATED_ID}" "${COMPLIANCE_SCOPE}" "md")"
# → Exemplo per-task:  $CHE_SESSION_DIR/reports/T2-refund/20260902-143000-compliance-per-task.md
# → Exemplo final:     $CHE_WORKSPACE_SHARED/report/compliance-final-wt-feat-X/20260902-143000-compliance-final.md
# → Ordenação intrínseca por prefixo timestamp UTC. Write atômico via: che_write_file_atomic "$COMPLIANCE_REPORT_PATH" stdin
```

---

## 0. Preconditions

Must receive:
- `WORKTREE_ROOT`
- `stage`: `"per-task"` OR `"final"`
- If `per-task`: list of changed files for that task
- If `final`: list of ALL files changed in the session so far
- Che session task-id (to know where to write report; usa `$COMPLIANCE_REPORT_PATH` do preflight acima)

---

## 1. SCAN CATEGORY 1 — Secrets & Credentials (CRITICAL / HARD BLOCK)

Run ALL of these checks. A match = SEVERITY:CRITICAL.

### 1.1 Generic secret regex patterns

Scan changed files (grep / content scan) for these patterns:

| Pattern | Matches |
|---|---|
| `sk-[a-zA-Z0-9]{20,}` | Stripe live/test secret keys |
| `pk_live_[a-zA-Z0-9]{20,} / pk_test_[a-zA-Z0-9]{20,}` | Stripe publishable live/test keys (live = BLOCK; test = WARN) |
| ` Bearer [A-Za-z0-9\-._~+/]+=*` | Bearer tokens in code strings |
| `-----BEGIN (RSA|EC|OPENSSH|PGP|PRIVATE) KEY-----` | Private key material |
| `ghp_[A-Za-z0-9]{20,} \| gho_\| ghs_\| ghu_` | GitHub PATs |
| `xox[baprs]-[A-Za-z0-9-]{10,}` | Slack tokens |
| `AIza[0-9A-Za-z\-_]{35}` | Google API keys |
| `AKIA[0-9A-Z]{16}` | AWS Access Key ID |
| `(?i)(password\s*[:=]\s*["'][^"']{8,}["']` | Password hardcoded in strings |
| `(?i)(api[_-]?key\|secret[_-]?key\|access[_-]?token\|client[_-]?secret)\s*[:=]\s*["'][^"']{6,}["']` | Generic API keys assigned to string literals |

### 1.2 `.env` files and leaking

- Check if `.env*` files were ADDED or EDITED:
  - `.env` → CRITICAL if tracked by git (must be in .gitignore)
  - `.env.example` → OK, but verify no real values in it
- Check if any code does:
  - `console.log(process.env)` or similar logger output of full env objects
  - Passing env vars to frontend bundles (Next.js public env leaking secrets)

---

## 2. SCAN CATEGORY 2 — PII / Personal Data (CRITICAL / HARD BLOCK when leaked)

### 2.1 Logging & persistence patterns

Scan for:
- `console.log(email)` / `logger.*email`, `logger.*password` — any raw PII field being logged. (Must use hashing / correlation secret, never raw)
- Direct storage of: credit card numbers (PAN), CVV, SSN equivalents
- Email addresses / phone numbers persisted without explicit PII hash / masking
- Any logger.info/debug lines containing: username + password together

### 2.2 Known PII fields (heuristic — match any occurrence then contextual review

If found in NEW code: flag and REQUIRE a rationale for each instance:
```
<file>:<line>: contains assignment of <field> — flagged as possible PII
Context: <3 lines before, 3 lines after
Rationale required: is this hashed? masked? needed?
```

---

## 3. SCAN CATEGORY 3 — Injection & Input Validation (HIGH severity)

### 3.1 SQL injection patterns

Scan for:
- String concatenation / template literals building SQL:
  ```
  `SELECT * FROM users WHERE id = ${userId}`
  `"SELECT * FROM users WHERE id = " + userId
  ```
  Except when inside a well-known ORM parameterized builder (Knex `.whereRaw` only when params array provided).
- `.whereRaw / .raw / queryRaw with string template without parameter array
- Dynamically concatenating table names / column names from user input (whitelist needed)

### 3.2 Command injection patterns

Scan for:
- `child_process.exec` / `execSync` with unsanitized user input in the command string (use `execFile` or `spawn` + args array)
- Shell commands with `;`, `&&`, `|`, backticks interpolated from external input
- `system()` / `os.popen()` / `Runtime.getRuntime().exec()` in other languages with tainted args

### 3.3 XSS patterns (web projects)

Scan for:
- `dangerouslySetInnerHTML` without sanitization
- `.innerHTML =` user_input
- `document.write(user_input)`
- `<script>user_input</script>` in SSR output
- eval() / new Function() with user-controlled strings

---

## 4. SCAN CATEGORY 4 — Auth & Authorization (HIGH severity)

### 4.1 Auth check (web / API projects

Scan changed auth-related files for:
- Open routes defined without authentication checks missing (`@deprecated` / `@Public()` auth
- Skipping auth intentionally without explicit `// eslint-disable-next-line` comments
- Hard bypass of RLS policies if Postgres+Supabase:
  - `.select().then(result => result)` — rows returned from Supabase without RLS enforced
  - usage of service_role key client on the client-side (service_role MUST be server only)

### 4.2 Permission checks

- Any endpoint / route:
  - Does it check ownership / roles BEFORE database read/write operation?
  - Is the check EARLY RETURN on request lifecycle? (fail-early)

---

## 5. SCAN CATEGORY 5 — Dangerous URLs (CRITICAL when pointing to prod-looking destinations

Check ALL new URLs introduced. Block any new AWS / RDS / Supabase / Neon / production DB:

- Hostname patterns to block (case-insensitive):
- `*.rds.amazonaws.com`
- `*.supabase.co`
- `*.neon.tech`
- `*.cockroachlabs.cloud`
- `*.azure.com` + `/sql` or `/db`

If such URL is used in NEW code → flag SEVERITY:HIGH + ask: is this DEV or PROD? correct env?

---

## 6. SCAN CATEGORY 6 — Destructive operations (HIGH / medium/low depending)

Scan for NEW code:
- DROP TABLE / TRUNCATE / DELETE FROM without WHERE
- `fs.rm(force:true, recursive:true)`
- destructive migration that doesNOT have NODE_ENV check + consent string checks
- destructive script

---

## 6.5 SCAN CATEGORY 7 — Test Naming Behavioral Conventions (REGRA 7.9 do che)

**Aplica-se APENAS a:** arquivos novos/editados que batem `*.test.*`, `*.spec.*`, ou estão dentro de pasta `__tests__/`. Se task não mexeu com testes → SKIP essa categoria.

**Objetivo:** evitar nomes de `describe()` / `it()` / `test()` que contenham APENAS IDs internos, forçando que o título descreva COMPORTAMENTO OBSERVÁVEL (válido por meses, não só enquanto a task aberta).

**🔴 HARD RULE — INVERSÃO PROIBIDA (NUNCA faça isso):**
> ❌ **ERRADO:** Reclamar / reportar finding por um teste NÃO TER `FLO-xxx` / `T<N>` / `AC<N>` na string de título.
> ✅ **CORRETO:** Ter essas referências NO TÍTULO é ANTI-PADRÃO (ruim = finding). Não tê-los e descrever comportamento observável é BOM / COMPLIANT.
>
> **Decisão 1-sentence:** `title contains FLO-ID? → BAD = FINDING. title does NOT contain FLO-ID? → GOOD = NUNCA gere finding por ausência de ID.`

**Scan pattern:** procurar por strings dentro de `describe("...")`, `it("...")`, `test("...")` (com aspas simples ou duplas). Para cada título encontrado, verificar anti-padrões:

| Anti padrão (regex case-insensitive) | Motivo | Severidade |
|---|---|---|
| `FLO-\d+` / `[A-Z]{2,}-\d+` | Ticket IDs Linear/Jira no TÍTULO. Válidos só enquanto ticket aberto; invalida relatório CI em 6 meses. | WARN |
| `Task?\s*T\d+(\.\d+)?` / `Item\s*\d+` | Task IDs do task graph do che no TÍTULO. Rearranjo de tasks quebra nome. | WARN |
| `AC\s*\d+` / `Critério\s*\d+` | IDs de acceptance criteria de SPEC/PRD no TÍTULO. | WARN |
| `§\s*\d+(\.\d+)?` / `REGRA\s*\d+` / `SPEC[_-]\w+` / `PRD\s*§` | Referências a seções de doc planejamento NO TÍTULO. | WARN |
| `Fase\s*\d+` / `Story\s*#?\d+` | Phase/story IDs temporários no TÍTULO. | WARN |

**Traceabilidade correta (NÃO gera finding, NÃO é anti-padrão — use estas):**
1. JSDoc comentário ACIMA do bloco: `/** @ticket FLO-714 · @ac 3.2 · @task T1.4 */`
2. Linha comentário DENTRO bloco 1ª linha: `// @ticket FLO-714 | @ac 3.2 | @task T1.4`

**Regra de severidade (FINDING só se BAD patterns ACIMA presentes no TÍTULO):**
- 1–9 títulos ruins → **WARN** (não blocking; lista detalhada no report)
- ≥10 títulos ruins no mesmo diff → **HIGH** (blocking; engineering-contracts deixa de ser review-friendly)
- Títulos bons = contêm verbo de ação + condição + resultado; NÃO têm regexes acima. Um título BOM não ter FLO-xxx nem Task-id. ISSO É O ESPERADO.

**❌ NUNCA gere finding por ausência de FLO/T/AC no título** → isso é default correto. Se seu relatório tem linha tipo "missing FLO prefix in title" é REGRESSÃO desta categoria, descarte a linha antes do output.

**Como reportar:**
```
## Scan 7 — Test naming (REGRA 7.9)
Total spec files modified: 3 | Test titles inspected: 24
Good (behavioral, NO internal IDs): 20 | Bad (contains internal IDs in TITLE STRING): 4
  1. /src/__tests__/auth.test.ts:88 — it("Task T2.3 valida AC 4.2 service role") → BAD in title: "Task T2.3" + "AC 4.2"
     Suggest rename: it("blocks non-service-role callers with 403 Forbidden when anon key used")
     Keep traceability: inside block line 1: // @ac 4.2 | @task T2.3 | @ticket FLO-745
  2. ...
```

---

## 7. REPORT FORMAT — Stage: findings)

### Findings report structure

```markdown
# Compliance Report — <TASK-ID> — Stage: <per-task | final>

Scan date: <ISO datetime>Files scanned: N

## Summary
Total findings: <count
CRITICAL: N  |  HIGH: N  | MEDIUM: N  | LOW: N  | WARN: N

## Table of findings

| # | Severity | Category | File:Line | Finding | Status |
|---|----------|----------|-----------|---------|--------|
| 1 | CRITICAL | Secrets | /path:42 | Hardcoded Stripe live sk_* | OPEN |
| 2 | HIGH | PII | /path:8 | Raw email in logger | OPEN |
| 3 | MEDIUM | Injection | ... | ... | OPEN |

## Detailed findings

### #1 — CRITICAL — Secrets leak
**File:** <path><line context 3 before, the finding line, 3 lines after context
**Recommendation:** <step the recommended

### #2 — HIGH — PII leak
**File:** ...
**Recommendation:** ...

## Appendix: passed checks
- [x] No private keys
- [x] No AWS keys
- [x] Supabase service_role not in client bundles
- [ ] PII hash/masking (1 instance reviewed)
```

Severity definitions:
- **CRITICAL**: immediate prod breach potential or credential leak. Hard block: cannot move task/final. FIX before next step. → back to Dev
- **HIGH**: vulnerability with clear exploit path in realistic scenario. Hard block. → back to Dev
- **MEDIUM**: plausible but requires unlikely preconditions. Soft block: if task is tiny patch release or justification; or explicit user override.
- **LOW**: best-practice violations, readability / smell. Non-blocking logged.
- **WARN**: cosmetic / informational. Non-blocking.

### Como escrever o report para disco (NÃO cai dentro da worktree)

Use sempre o path e write atômico do PREFLIGHT. NUNCA construa `$CHE_*` manualmente, nunca use `./reports`, nunca escreva em `<WORKTREE_ROOT>/.trae/`.

```bash
# Gera o report markdown em memória e escreve atômico:
cat <<'EOF' | che_write_file_atomic "$COMPLIANCE_REPORT_PATH"
# Compliance Report — <TASK-ID> — Stage: <per-task | final>
... (estrutura §7 acima completa)
EOF

# Printa ao usuário (PT-BR):
#   Compliance <stage> concluído. 0 CRITICAL. 0 HIGH.
#   Report completo salvo em: $COMPLIANCE_REPORT_PATH (fora da sua worktree).
#   Nenhum arquivo untracked/modified adicionado em git status.
```

Se stage=`final` (cross-session durable): decision-log via helper para audit trail:
```bash
che_append_decision_jsonl "COMPLIANCE_HEAVY_RUN" \
  '{"report_path":"'"${COMPLIANCE_REPORT_PATH}"'","total_findings":<N>,"critical":<N>,"high":<N>}'
```
NÃO escreva este decision append como `cat >> $CHE_DECISIONS_PATH` (risco não-atomic + corrompimento JSONL).

---

## 8. FINAL STAGE extras (only when `stage: final`)

Same scans, plus:

### 8.1 Cross-file consistency

- Scan the FULL diff session. If secret was moved from file A to file B in different tasks. Per-task scans each separately — final catches cross-task.
- Architecture boundary violations: Does the diff introduce cross-layer violations onion/clean.
- Circular imports / dependency direction (if language supports.

### 8.2 ENV check / environment-specific code

Look for:
- `NODE_ENV === 'production'` checks that are inverted or missing
- Hardcoded `localhost` or staging/dev hostnames left in paths that go to production
- Timezone / currency hardcoded vs env-driven

### 8.3 Result

Final stage produces 1 additional overall verdict:

```
Final Compliance verdict:
- CRITICAL found: 0
HIGH found:0
MEDIUM: 2 (Dev+1 logged)
LOW: 3
WARN: 5
OVERALL: PASS / FAIL
Blocking issues remain → back to SM → → to Dev for fixes.
```

---

## A: What Compliance must **NEVER**

- Fix source code / files directly. Compliance = reviewer, never execut
- Run tests, build, lint. That's QA's job.

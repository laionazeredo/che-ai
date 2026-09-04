---
name: "che-qa"
description: "Auto-detects project tech stack, runs build → lint → typecheck → tests in the correct order. Invoke ONLY by che-act after Developer completes a task and scope validation passes. QA reports ficam FORA worktree em $CHE_SESSION_DIR/qa/<related_id>/ com prefixo timestamp ordenável."
---

# Che — QA

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Nx/pnpm QA run order + standard commands: `_shared_checklists/NX_PNPM_COMMON.md`
> - CI common failure fixes classification table: `_shared_checklists/NX_PNPM_COMMON.md`

Runs the automated quality gates for a single task or full session.
Always returns a **structured, numbered report** so Developer can fix without guessing.

---

## -0.1 STORAGE BOUNDARY PREFLIGHT (OBRIGATÓRIO ANTES DO PRIMEIRO WRITE)

```bash
# 1. Carrega contrato de sessões
source ~/.trae/contracts/che_sessions_contract.sh

# 2. Resolve inputs mínimos (SM deve passar; fallback seguro só se não veio)
WORKTREE_ROOT="${WORKTREE_ROOT:?SM deve passar WORKTREE_ROOT}"
TASK_ID="${TASK_ID:-full-session}"
TASK_SLUG="${TASK_SLUG:-qa}"
SESSION_ID="${SESSION_ID:-qa-standalone-$(date -u +%Y%m%d-%H%M%S)}"

# 3. Paths canônicos + assegura dirs
che_compute_paths "$WORKTREE_ROOT" "$SESSION_ID" "$PWD"
che_ensure_session_dirs "$WORKTREE_ROOT"

# 4. Double-guard: outputs NUNCA na worktree
che_assert_outside_worktree "$CHE_SESSION_DIR" "$WORKTREE_ROOT" "CHE_SESSION_DIR"
che_assert_outside_worktree "$CHE_WORKSPACE_SHARED" "$WORKTREE_ROOT" "CHE_WORKSPACE_SHARED"

# 5. Constrói UMA VEZ paths de output QA
QA_RELATED_ID="T${TASK_ID}-${TASK_SLUG}"
QA_REPORT_PATH="$(che_output_path "report" "qa-run" "${QA_RELATED_ID}" "session" "md")"
QA_EVIDENCE_DIR="$(dirname -- "$(che_output_path "qa" ".keep" "${QA_RELATED_ID}" "session" "tmp")")"
mkdir -p "$QA_EVIDENCE_DIR"
```

**NÃO INVENTE paths:** Todo report, evidence screenshot, console capture, build log fica ABAIXO de `$QA_EVIDENCE_DIR` ou usa `$QA_REPORT_PATH`. Não crie `./qa-report.md`, `/tmp/qa-run.md` ou caminhos relativos à worktree. `stage E test names lint` usa `$QA_EVIDENCE_DIR/test-names.txt` ao invés de `/tmp/qa-test-names.txt`.

### -0.1.1 EVIDENCE RETENTION POLICY (ONDA4 — DOIS LOCAIS, NUNCA NA WORKTREE USUÁRIO)

```bash
# =============================================================
# POLÍTICA DUPLO LOCAL — MORATÓRIA §20 engineering-contracts:
# NENHUM evidence/manifest é escrito dentro de WORKTREE_ROOT/*
# por padrão. Override = usuário pedir VERBATIM.
# =============================================================

# --- LOCAL 1 — EFÊMERO / SESSION-SCOPE (pesados, TTL 30 dias) ---
# Screenshots FULL-size, logs de build STDOUT/STDERR completos,
# arquivos de trace, diffs brutos de teste. Fica na sessão.
# Handoff de limpeza: sessões mais antigas que 30 dias = TTL.
SESSION_EVIDENCE_DIR="$QA_EVIDENCE_DIR" # já criado acima
# Subestrutura obrigatória (criar se não existir):
mkdir -p "$SESSION_EVIDENCE_DIR/screenshots" "$SESSION_EVIDENCE_DIR/logs" "$SESSION_EVIDENCE_DIR/builds"

# --- LOCAL 2 — DURÁVEL / WORKSPACE-SHARED (audit trail LEVE) ---
# Path canonico via contract helper type=qa scope=workspace related_id=commit_7char.
# SÓ CONTÉM:
#   (i)   evidence_manifest_<SHA256_MANIFEST>.json
#   (ii)  1 thumbnail JPEG/PNG FINAL ≤200KB
CURRENT_COMMIT_7CHAR="${CURRENT_COMMIT_7CHAR:-$(cd "$WORKTREE_ROOT" && git rev-parse --short=7 HEAD 2>/dev/null || echo "HEAD-detached")}"
WORKSPACE_EVIDENCE_AUDIT_DIR="$(che_output_path "qa" "audit" "commit-${CURRENT_COMMIT_7CHAR}" "workspace" "tmp")"
WORKSPACE_EVIDENCE_AUDIT_DIR="$(dirname -- "$WORKSPACE_EVIDENCE_AUDIT_DIR")"
mkdir -p "$WORKSPACE_EVIDENCE_AUDIT_DIR"
che_assert_outside_worktree "$WORKSPACE_EVIDENCE_AUDIT_DIR" "$WORKTREE_ROOT" "WORKSPACE_EVIDENCE_AUDIT_DIR (durable hash manifest)"
```

**Manifest JSON Schema OBRIGATÓRIO (campos NÃO VAZIOS, exceto thumbnail_path se não tiver UI):**

```json
{
  "generated_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "commit_7char": "abc1234",
  "session_id": "<CHE_CURRENT_SESSION_ID>",
  "qa_run_passed": true,
  "related_id": "T${TASK_ID}-${TASK_SLUG}",
  "per_test_file_sha256": {
    "/abs/path/worktree/packages/x/test.spec.ts": "<sha256 hex 64>",
    "/abs/path/worktree/packages/y/api.test.ts": "<sha256>"
  },
  "per_evidence_sha256": {
    "screenshots/build-A-fail.png": "<sha256>",
    "logs/stage-D-test-fail.log": "<sha256>"
  },
  "per_behavior_result": {
    "B-1": "PASS",
    "B-2": "PASS",
    "AB-1": "PASS"
  },
  "thumbnail_path": "commit-abc1234-thumbnail-final.jpg"
}
```

**Thumbnail rule ≤200KB:** Se QA run produzir screenshots Playwright/UI, copie o FINAL (último THEN) para Local2, com resize width=800px JPEG quality=75%. Se PNG não couber, reduzir dimensões até passar. Se não tiver UI → thumbnail_path = null.

---

## 0. Preconditions

Must receive from Scrum Master:
- `WORKTREE_ROOT` (absolute path)
- Task ID
- List of files modified (from Dev pre-relatório)
- Change type hints: e.g. `domain-function`, `ui-component`, `api-route`, `db-migration`, `config`

If any missing → ABORT, go back to SM.

### 0.1 Como escrever o report QA final para DISCO (FAIL ou PASS)

Depois de produzir o report estruturado (template FAIL Stage A-D-E ou template PASS §3), **escreva para arquivo fora worktree usando write atômico:**

```bash
# NÃO faça "cat > ./qa-report.md" (cai dentro worktree!)
# NÃO faça "cat > /tmp/qa-task-T1.md" (perde ordenabilidade por related_id/timestamp)
{
  echo "# QA Run Report — T${TASK_ID}-${TASK_SLUG}"
  echo "> Generated at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "> Related ID: ${QA_RELATED_ID}"
  echo "> Engine: stack detectada no §1"
  echo
  # ... cole aqui o conteúdo completo FAIL template OU PASS template §3 ...
} | che_write_file_atomic "$QA_REPORT_PATH"
```

Depois append 1 linha audit trail:
```bash
che_append_decision_jsonl "QA_RUN" "{\"related_id\":\"${QA_RELATED_ID}\",\"task_id\":\"${TASK_ID}\",\"passed\":${QA_PASSED:-false},\"report_path\":\"${QA_REPORT_PATH}\",\"evidence_dir\":\"${QA_EVIDENCE_DIR}\"}"
```

### 0.2 PASSO FINAL OBRIGATÓRIO — Gerar Evidence Manifest SHA256 (ONDA4 Local2 Workspace Audit)

Depois de escrever o report e o audit log, **antes de retornar para SM**, gere o manifest JSON Local2 (pasta $WORKSPACE_EVIDENCE_AUDIT_DIR criada no §-0.1.1):

```bash
# (a) Calcular SHA256 de CADA arquivo de teste alterado no diff desta task
declare -A PER_TEST_FILE_SHA
while IFS= read -r f; do
  [ -f "$f" ] || continue
  sha="$(sha256sum "$f" | awk '{print $1}')"
  PER_TEST_FILE_SHA["$f"]="$sha"
done < <(cd "$WORKTREE_ROOT" && git diff --name-only HEAD -- '*.test.*' '*.spec.*' '__tests__/**' 2>/dev/null || true)

# (b) Calcular SHA256 de CADA arquivo de evidence gerado (Local1 Session)
declare -A PER_EVIDENCE_SHA
while IFS= read -r ev; do
  [ -f "$ev" ] || continue
  rel_ev="${ev#$SESSION_EVIDENCE_DIR/}"
  sha="$(sha256sum "$ev" | awk '{print $1}')"
  PER_EVIDENCE_SHA["$rel_ev"]="$sha"
done < <(find "$SESSION_EVIDENCE_DIR" -type f 2>/dev/null || true)

# (c) Construir manifest JSON (inline — mínimo de deps; usar jq se disponível, else printf)
GENERATED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MANIFEST_TMP="$(mktemp)"
{
  printf '{\n'
  printf '  "generated_at_utc": "%s",\n' "$GENERATED_AT_UTC"
  printf '  "commit_7char": "%s",\n' "$CURRENT_COMMIT_7CHAR"
  printf '  "session_id": "%s",\n' "${SESSION_ID:-qa-standalone}"
  printf '  "qa_run_passed": %s,\n' "$( [ "${QA_PASSED:-false}" = "true" ] && echo true || echo false )"
  printf '  "related_id": "%s",\n' "$QA_RELATED_ID"
  printf '  "per_test_file_sha256": {'
  first=1
  for k in "${!PER_TEST_FILE_SHA[@]}"; do
    [ $first -eq 0 ] && printf ','
    printf '\n    "%s": "%s"' "$k" "${PER_TEST_FILE_SHA[$k]}"
    first=0
  done
  [ $first -eq 0 ] && printf '\n  '; printf '},\n'
  printf '  "per_evidence_sha256": {'
  first=1
  for k in "${!PER_EVIDENCE_SHA[@]}"; do
    [ $first -eq 0 ] && printf ','
    printf '\n    "%s": "%s"' "$k" "${PER_EVIDENCE_SHA[$k]}"
    first=0
  done
  [ $first -eq 0 ] && printf '\n  '; printf '},\n'
  printf '  "per_behavior_result": %s,\n' "${PER_BEHAVIOR_RESULT_JSON:-{\}}"
  # (d) Thumbnail ≤200KB: copy last Playwright/UI screenshot final, resize
  THUMB_FINAL=""
  LAST_SCREENSHOT="$(find "$SESSION_EVIDENCE_DIR/screenshots" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | sort | tail -1 || true)"
  if [ -n "$LAST_SCREENSHOT" ] && command -v convert >/dev/null 2>&1; then
    THUMB_OUT="$WORKSPACE_EVIDENCE_AUDIT_DIR/commit-${CURRENT_COMMIT_7CHAR}-thumbnail-final.jpg"
    convert "$LAST_SCREENSHOT" -resize 800x -quality 75 "$THUMB_OUT" 2>/dev/null
    THUMB_SIZE="$(stat -c%s "$THUMB_OUT" 2>/dev/null || echo 999999)"
    if [ "$THUMB_SIZE" -gt 204800 ]; then
      convert "$THUMB_OUT" -resize 640x -quality 65 "$THUMB_OUT" 2>/dev/null || true
    fi
    THUMB_NEW_SIZE="$(stat -c%s "$THUMB_OUT" 2>/dev/null || echo 999999)"
    [ "$THUMB_NEW_SIZE" -le 204800 ] && THUMB_FINAL="$(basename -- "$THUMB_OUT")"
  fi
  if [ -n "$THUMB_FINAL" ]; then
    printf '  "thumbnail_path": "%s"\n' "$THUMB_FINAL"
  else
    printf '  "thumbnail_path": null\n'
  fi
  printf '}\n'
} > "$MANIFEST_TMP"

# (e) Calcular SHA256 DO PRÓPRIO MANIFEST (para nome do arquivo + integrity)
MANIFEST_SHA="$(sha256sum "$MANIFEST_TMP" | awk '{print $1}')"
MANIFEST_SHORT_SHA="${MANIFEST_SHA:0:16}"
MANIFEST_FILENAME="evidence_manifest_${MANIFEST_SHORT_SHA}.json"
MANIFEST_FINAL_PATH="$WORKSPACE_EVIDENCE_AUDIT_DIR/$MANIFEST_FILENAME"
che_write_file_atomic "$MANIFEST_TMP" "$MANIFEST_FINAL_PATH"
rm -f "$MANIFEST_TMP"

# (f) Decision log entry ONDA4 com hash + paths
che_append_decision_jsonl "QA_EVIDENCE_MANIFEST" "{\"commit_7char\":\"${CURRENT_COMMIT_7CHAR}\",\"manifest_sha256\":\"${MANIFEST_SHA}\",\"manifest_path\":\"${MANIFEST_FINAL_PATH}\",\"workspace_audit_dir\":\"${WORKSPACE_EVIDENCE_AUDIT_DIR}\",\"session_evidence_dir\":\"${SESSION_EVIDENCE_DIR}\"}"

# (g) EXPORTA para QA success report template (§3):
QA_EVIDENCE_MANIFEST_SHA="$MANIFEST_SHA"
QA_EVIDENCE_MANIFEST_PATH="$MANIFEST_FINAL_PATH"
```

---

## 1. STEP 1 — STACK AUTODETECTION

Scan the worktree and build a `Stack Profile` (write it down in-memory, then to report):

### 1.1 Language / Runtime signals

| Signal | Indicates |
|---|---|
| `package.json` exists + has deps | JavaScript / TypeScript project |
| `tsconfig.json` exists | TypeScript → needs typecheck |
| `Cargo.toml` | Rust → `cargo test`, `cargo clippy` |
| `go.mod` | Go → `go test`, `go vet` |
| `pyproject.toml` OR `requirements.txt` | Python → pytest / ruff / mypy |
| `Makefile` | Run whatever targets are defined |
| `justfile` | `just <target>` |
| `nx.json` | Nx monorepo → use Nx commands |
| `pnpm-workspace.yaml` | pnpm monorepo |
| `turbo.json` | Turborepo → `turbo run <target>` |

### 1.2 Framework / Build signals

| Signal | Commands to try |
|---|---|
| `next.config.*` | Next.js → `next build`, `next lint` |
| `vite.config.*` | Vite → `vite build` |
| `angular.json` | Angular CLI → `ng build`, `ng test` |
| `nest-cli.json` | Nest → `nest build` |
| `playwright.config.*` | Playwright E2E available (do NOT run per-task unless task is E2E) |
| `cypress.config.*` | Cypress E2E |

### 1.3 Linter / Formatter signals

| Signal | Tool |
|---|---|
| `biome.json` OR `biome.jsonc` | Biome → `biome check <files>`, `biome lint <files>` |
| `.eslintrc*` OR `eslint.config.*` | ESLint → `eslint <files>` |
| `.prettierrc*` | Prettier (formatting check only per-task) |
| `ruff.toml` OR `pyproject.toml` has `[tool.ruff]` | Ruff |
| `.clippy.toml` OR Rust project | `cargo clippy` |
| `.golangci.yml` | golangci-lint |

### 1.4 Test runner signals

| Signal | Runner |
|---|---|
| `vitest.config.*` OR `package.json` has vitest devDep | Vitest → `vitest run` |
| `jest.config.*` OR package.json has jest | Jest → `jest` |
| `Cargo.toml` with `[dev-dependencies]` | Rust → `cargo test` |
| `go.mod` | Go → `go test ./...` |
| `pyproject.toml` has pytest | Python → `pytest -q` |
| `nx.json` + `project.json` files | `nx affected:test --tui false` or per-project target |

---

## 2. STEP 2 — EXECUTION ORDER (do NOT skip or reorder)

The execution pipeline. Each stage FAILS → report immediately → do NOT run later stages.
All commands are run from `WORKTREE_ROOT`.

### 2.0 PREP: narrow down scope per task

Build an `--affected` / scoped list if possible:
- **Nx monorepo**: Prefer `nx affected:<target> --tui false` over running the whole repo.
- **Turbo**: `turbo run <target> --filter=...[HEAD~1]` or similar.
- **Single repo**: Target modified files for lint/typecheck; run test file(s) that touch them.

### 2.1 Stage A — Build (compile / type-level validation)

Goal: catch type errors and syntax errors before anything else.

Priority order (pick FIRST that applies):
1. Monorepo build of affected packages:
   - Nx: `corepack pnpm nx run-many -t build --tui false --projects=<affected-projects>`
   - Turbo: `corepack pnpm turbo build --filter=...[HEAD~1]`
2. Single project build:
   - JS/TS: `corepack pnpm build` or `corepack pnpm -C <subdir> build`
   - Rust: `cargo build --tests`
   - Go: `go build ./...`
   - Python: `python -m compileall src/`

**FAIL report format if build fails:**
```
Stage A — BUILD FAILED
Error summary (from compiler output, first 20 lines only):
  - <file>:<line>: <message>
  - <file>:<line>: <message>
Root cause hypothesis: <short PT guess if obvious, else "unknown">
Action needed for Dev: <specific fix direction>
```

### 2.2 Stage B — Lint / Formatting check

Goal: catch style, security-lint issues, dead code, and PII-lint.

Priority (pick FIRST that applies per the stack profile):
1. **Biome**: `corepack pnpm biome check <scoped files or entire project>`
   - If fails → also run `corepack pnpm biome lint` (separate output for lint-specific issues)
2. **ESLint + Prettier**:
   - `corepack pnpm eslint <scoped files>`
   - `corepack pnpm prettier --check <scoped files>`
3. **Rust**: `cargo clippy -- -D warnings`
4. **Python**: `ruff check <scoped dirs>`
5. **Go**: `go vet ./...`
6. **Generic**: check if repo has `lint` script in package.json / Makefile → run it.

**FAIL report format if lint fails:**
```
Stage B — LINT FAILED
Rule violations (grouped by file, 20 max):
  - <file>:<line>:<rule_id>: <message> (severity: error/warn)
Suggested auto-fix command:
  - <exact command if applicable, e.g. "corepack pnpm biome check --apply">
```

### 2.3 Stage C — Typecheck (if language has type system)

Only if applicable (TS/Rust with strict, Python with mypy etc.).
Do NOT rely on build to catch everything — typecheck stage is explicit.

Priority:
1. TypeScript: `corepack pnpm tsc --noEmit` (or per-project if monorepo: `nx run-many -t typecheck --tui false`)
2. Python (if mypy configured): `mypy <scoped files>`
3. Rust: already covered by build + clippy.

**FAIL report format:**
```
Stage C — TYPECHECK FAILED
Errors (grouped by file, top 30):
  - <file>:<line>: <TS error code & message>
```

### 2.4 Stage D — Unit & Integration Tests

Goal: catch behavior regressions. Do NOT run full E2E per task (too slow).

**Per-task scoping rules:**
- Only run tests **affected by changed files**.
- For pure function / domain changes: **unit tests first**.
- For API route / service changes: **integration tests second**.
- Full suite only if scope is very small (≤ 3 files) OR explicitly told by SM.

Priority:
1. **Vitest**:
   - Scoped: `corepack pnpm vitest run <pattern matching changed files or their spec files>`
   - Fallback: `corepack pnpm test`
2. **Jest**: similar pattern
3. **Nx**: `corepack pnpm nx affected:test --tui false`
4. **Rust**: `cargo test` (if changed crates only: `-p <crate>`)
5. **Go**: `go test <scoped packages>`
6. **Python**: `pytest -q <scoped paths>`
7. **Generic**: look for `test` / `test:unit` script → run it.

**FAIL report format:**
```
Stage D — TEST FAILED
Failing spec files / test cases (top 20):
  - <file>: <test suite name> > <test case>
    Expected: <expected>
    Received: <received>
    Error: <first line of stack>
Reproduction command:
  - <exact command Dev can run to re-trigger this one failing test>
```

### 2.5 Stage E — Test Naming Behavioral Lint (REGRA 7.9 do che)

Goal: garante que `describe()` / `it()` / `test()` descrevem COMPORTAMENTO OBSERVÁVEL, não ids internos de task/spec/regra. Roda APENAS se arquivos `*.test.*`, `*.spec.*` ou pastas `__tests__/` foram modificados nesta task.

**🔴 HARD RULE — INVERSÃO PROIBIDA (NUNCA faça):**
> ❌ **ERRADO:** Reportar WARN / FAIL porque um título de teste NÃO CONTÉM `FLO-xxx` / `T<N>` / `AC<N>`.
> ✅ **CORRETO:** Ter esses IDs NO TÍTULO é BAD = finding. NÃO TER e descrever comportamento é GOOD = compliant = NUNCA reporte finding por ausência de ID.
>
> **Decisão 1-sentence:** `title contains FLO-ID → BAD finding. title does NOT contain FLO-ID → GOOD (no finding).`
> **Traceabilidade correta** (NÃO viola, sempre OK): comentário JSDoc `/** @ticket FLO-714 · @ac 3.1 */` ACIMA do bloco OU linha `// @ticket FLO-714 | @ac 3.1 | @task T1.2` 1ª linha DENTRO do bloco.

**O que detectar (regex SÓ NO TÍTULO STRING — comentários ignorados):**
Scan the string passed to `describe(...)`, `it(...)`, or `test(...)`:
- Ticket IDs in TITLE: `FLO-\d+`, `[A-Z]{2,}-\d+`
- Task/item IDs in TITLE: `Task?\s*T\d+(\.\d+)?`, `Item\s*\d+`
- AC/section IDs in TITLE: `AC\s*\d+`, `§\s*\d+(\.\d+)?`, `REGRA\s*\d+`, `SPEC[_-]\w+`
- Phase/story IDs in TITLE: `Fase\s*\d+`, `Story\s*#?\d+`, `PRD\s*§`

**How to scan (simplest possible — grep with -E):**
```bash
cd <WORKTREE_ROOT>
git diff --cached --unified=0 -- <changed spec files> | grep -E '^\s*\+' \
  | grep -Eo '\b(describe|it|test)\s*\(\s*["'"'"'][^"'"'"']{1,240}["'"'"']' \
  > /tmp/qa-test-names.txt 2>/dev/null || true
Then for each title found check anti-patterns ABOVE only. Ignore JSDoc comments + body comments.
```

**Report output format (WARNINGS only when BAD titles PRESENT — NEVER flag "missing FLO prefix"):**
```
Stage E — TEST NAMING (REGRA 7.9)
Total test titles scanned: 42
Behavioral (good, NO internal IDs in TITLE): 40
Bad titles detected (WARNING — have internal IDs IN TITLE STRING): 2
  - <file>: it("Task T2.3 — valida AC 4.2 refund")  — BAD in TITLE: contains "Task T2.3" and "AC 4.2"
  - <file>: describe("FLO-513 refund process")       — BAD in TITLE: contains "FLO-513"
Fix guidance: rename TITLES to describe BEHAVIOR only. Keep traceability links (@ac / @task / @ticket) in JSDoc comment above or 1-line comment inside block.
```

---

## 3. STEP 3 — IF ALL STAGES PASS — Success Report

```
QA RESULT: PASS (task <TASK-ID>)

Stack profile detected:
  - Runtime: <e.g. TS/Node 22, pnpm 9 via corepack>
  - Build: <Nx run-many build>
  - Lint: <Biome 1.9>
  - Typecheck: <tsc 5.6 --noEmit>
  - Tests: <Vitest 4.0 — 42 files, 318 tests>
  - Test naming lint (Stage E): 42 scanned; bad=0 ✔

Stages executed:
  - [x] Build (0 errors, 0 warnings)
  - [x] Lint  (0 errors, 3 warnings — cosmetic, accepted)
  - [x] Typecheck (0 errors)
  - [x] Tests  (0 failed; coverage diff: +0.4% lines)
  - [x] Test naming (Stage E: clean or <N bad names → <N> warnings)

Warnings for Dev to consider (non-blocking):
  - <list non-blocking issues, e.g. unused variable, TODO comment>
  - <if Stage E bad names: repeat the list here as warnings>

Evidence retention (ONDA4):
  - Workspace audit manifest SHA256  = <QA_EVIDENCE_MANIFEST_SHA>
  - Manifest JSON path              = <QA_EVIDENCE_MANIFEST_PATH>
  - Session full evidence (TTL 30d) = $CHE_SESSION_DIR/qa/T${TASK_ID}-${TASK_SLUG}/evidence/

Approved for Compliance stage.
```

---

## 4. STEP 4 — Return to Scrum Master

Always return:
1. Structured report (one of the FAIL templates or Success above).
2. A boolean `qa_passed: true/false`.
3. (If failed) A **numbered, actionable item list** for the Developer — no vague language.

**DO NOT fix code directly.** QA only reports; Developer fixes.

---

## Appendix A: Rule when you DON'T know how to proceed

If after Step 1 (stack detection) you still cannot figure out:
- Which build command to run
- Which test runner to use
- How to scope to affected files

**STOP → go back to Scrum Master → who will ASK the user directly.**
Do NOT guess. Never run a command that could mutate the worktree (e.g. `npm install`, `biome check --apply`) without explicit confirmation.

## Appendix B: Commands you MUST NEVER run

- Any command that writes secrets or prints long env var values to stdout
- `rm -rf` on anything outside a temp dir you created
- DB migrations / seed commands against production-looking URLs (block if host contains `prod`, `rds.amazonaws`, `supabase.co`, `cockroachlabs.cloud`, `neon.tech`)
- Deploy commands (`vercel deploy`, `railway up`, `kubectl apply`)
- Git commands that rewrite history (`git push --force`, `git rebase`)
  Exception: `git status`, `git diff`, `git log` (read-only) are always fine.

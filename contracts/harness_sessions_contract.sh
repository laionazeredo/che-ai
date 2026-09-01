#!/usr/bin/env bash
# HARNESS SESSIONS PATH CONTRACT (CANÔNICO, DETERMINÍSTICO)
#
# Esse arquivo é um contrato: todo script/hook/skill do harness que PRECISAR
# resolver paths de sessão/workspace/worktree DEVE fazer source nessas funções.
# NENHUM componente do harness deve construir esses paths hardcoded manualmente
# fora daqui — causa colisão e migrações quebradas.
#
# Produz paths ABAIXO de $HARNESS_SESSIONS_ROOT (default: $HOME/code/harness-sessions)
# NUNCA coloca nada de sessão dentro de $WORKTREE_ROOT/.trae — evita commits acidentais.
#
# VARIÁVEIS DE SAÍDA PADRONIZADAS (export quando sourced):
#   HARNESS_SESSIONS_ROOT  = dir raiz de tudo mutável/gerado
#   HARNESS_WORKSPACE_NAME = nome canônico do workspace (ex: Flockr)
#   HARNESS_WORKTREE_SLUG  = slug canônico repo__branch (ex: Lumos__feat--FLO-513)
#   HARNESS_WORKSPACE_DIR  = $HARNESS_SESSIONS_ROOT/$HARNESS_WORKSPACE_NAME
#   HARNESS_WORKTREE_DIR   = $HARNESS_WORKSPACE_DIR/$HARNESS_WORKTREE_SLUG
#   HARNESS_WORKSPACE_SHARED  = $HARNESS_WORKTREE_DIR/workspace  (dados duráveis per-worktree)
#   HARNESS_SESSION_DIR        = $HARNESS_WORKTREE_DIR/sessions/<effective-session-id>  (efêmero per-session)
#   HARNESS_LEVEL2_BINDING     = $HARNESS_SESSION_DIR/binding.md  (§19 Level 2 detail)
#   HARNESS_DECISIONS_LOG      = $HARNESS_WORKSPACE_SHARED/decisions.log.jsonl  (single source of truth, append-only JSONL)
#
# FUNÇÕES EXTRA (DECISIONS.JSONL):
#   harness_decisions_path  [cwd_override]
#       Imprime path absoluto decisions.log.jsonl do worktree (sem criar arquivo).
#
#   harness_append_decision_jsonl <worktree_root> <event_type> <payload_json> [timestamp_override]
#       Helper OFICIAL para append 1 entry no decisions.log.jsonl.
#       - Cria o arquivo se não existir.
#       - Garante JSON válido por linha (JSONL schema canônico).
#       - NÃO DUPLICA entradas (se mesma ts+event_type+payload sha256 idempotência).
#       - payload_json = {"key":"val", ...}  (com ou sem chaves externas).
#       - Schema de saída por linha (JSONL 1 line = 1 entry):
#           { "ts": "<ISO8601 UTC>", "event": "<event_type>",
#             "spec_id": "SPEC-XXX or null", "session_id": "sess-... or null",
#             "worktree_root": "/abs/path", "data": { <payload_json expandido aqui> },
#             "_v": 1 }
#       - Usa python3 embutido para JSON escaping seguro (sem cair em quoting shell frágil).
#
#   harness_migrate_decisions_md_to_jsonl <old_md_path> <new_jsonl_path> <worktree_root>
#       Migra LEGADO decisions.log.md (formato "[ts] [TIPO] texto livre") para decisions.log.jsonl.
#       One-shot migration helper. Não deleta o .md antigo; chamador decide.

set -euo pipefail

# Runtime-neutral harness root.
# Trae compatibility: default continua sendo $HOME/.trae.
# Outros consumidores (ex: Codex) podem definir HARNESS_HOME explicitamente.
export HARNESS_HOME="${HARNESS_HOME:-$HOME/.trae}"

# Session ID resolver.
# HARNESS_SESSION_ID tem precedência para runtimes neutros.
# SESSION_ID permanece como fallback compatível com a IDE Trae.
harness_current_session_id() {
  printf '%s\n' "${HARNESS_SESSION_ID:-${SESSION_ID:-}}"
}

export HARNESS_SESSIONS_ROOT="${HARNESS_SESSIONS_ROOT:-$HOME/code/harness-sessions}"

# =========================================================
# HARD STOP GUARDS — NUNCA permita criar artifacts DENTRO de WORKTREE_ROOT
# =========================================================
# Qualquer path resolvido que comece com $WORKTREE_ROOT (ou seja, que cai
# dentro da pasta do projeto do usuário) causa FAIL IMEDIATO com mensagem
# clara. Isso é o enforcer real: se não é criado dentro da worktree, nunca
# vai aparecer em git status e muito menos em PR.

harness_assert_outside_worktree() {
  local candidate_path="$1"
  local worktree_root="$2"
  local label="${3:-path}"

  [ -n "$candidate_path" ] || return 0
  [ -n "$worktree_root"  ] || return 0

  # Normaliza trailing slashes
  worktree_root="${worktree_root%/}"
  candidate_path_abs="$candidate_path"
  case "$candidate_path_abs" in
    /*) : ;;
    *)  candidate_path_abs="$(cd "$(dirname "$candidate_path_abs")" 2>/dev/null && pwd)/$(basename "$candidate_path_abs")" ;;
  esac

  # Check starts-with worktree_root/ OR exatamente igual worktree_root
  if [ "$candidate_path_abs" = "$worktree_root" ] ||
     [ "${candidate_path_abs#$worktree_root/}" != "$candidate_path_abs" ]; then
    cat >&2 <<ERR

\
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 🔴 HARNESS SESSIONS CONTRACT VIOLATION — HARD STOP                       │
  ├──────────────────────────────────────────────────────────────────────────┤
  │                                                                          │
  │   $label está caindo DENTRO da worktree do usuário.                      │
  │   Isso NUNCA pode acontecer — causa commit acidental de                 │
  │   decisions.log, task_graph, manual_test_plan, spec_*.md etc em PRs.     │
  │                                                                          │
  │   label        : $label                                                  │
  │   candidato    : $candidate_path_abs                                     │
  │   worktree_root: $worktree_root                                          │
  │                                                                          │
  │  Como corrigir:                                                          │
  │   - NÃO construa paths com \$PWD/.trae/ nem \$WORKTREE_ROOT/.trae/.      │
  │   - Sempre use:                                                          │
  │       source \$HARNESS_HOME/contracts/harness_sessions_contract.sh     │
  │       harness_compute_paths \$WORKTREE_ROOT "$(harness_current_session_id)" │
  │   - Depois use \$HARNESS_WORKSPACE_SHARED (garantido FORA worktree).     │
  │                                                                          │
  │   Se foi um script/harness que chegou aqui, aborte imediatamente.        │
  └──────────────────────────────────────────────────────────────────────────┘

ERR
    exit 99
  fi
}

# =========================================================
# IMPLEMENTAÇÃO
# =========================================================

harness_resolve_workspace_name() {
  local cwd="${1:-$PWD}"
  cwd="$(cd "$cwd" && pwd)"

  if [ -n "${HARNESS_WORKSPACE_NAME_OVERRIDE:-}" ]; then
    echo "$HARNESS_WORKSPACE_NAME_OVERRIDE"
    return 0
  fi

  if [ -n "${HARNESS_WORKSPACE_NAME:-}" ]; then
    echo "$HARNESS_WORKSPACE_NAME"
    return 0
  fi

  local code_workspace_global="${HARNESS_CODE_WORKSPACES_DIR:-$HOME/code/code_workspaces}"
  if [ -d "$code_workspace_global" ]; then
    local f
    for f in "$code_workspace_global"/*.code-workspace; do
      [ -f "$f" ] || continue
      # Verifica se alguma entry "path" no JSON, quando resolvida relativamente ao dir do workspace,
      # é prefixo de $cwd ou igual.
      local wfdir
      wfdir="$(dirname "$f")"
      # Extrai entradas "path" via sed/grep (jq would be nice but keep it dependency-free).
      local paths
      paths="$(grep -oE '"path"[[:space:]]*:[[:space:]]*"[^"]+"' "$f" 2>/dev/null | sed -E 's/.*"path"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' || true)"
      local p
      while IFS= read -r p; do
        [ -z "$p" ] && continue
        local abs
        # Caminhos começando com / são absolutos; senão resolvemos relativos ao dir do arquivo .code-workspace
        case "$p" in
          /*) abs="$p" ;;
          *)  abs="$(cd "$wfdir" && cd "$(dirname "$p")" && pwd)/$(basename "$p")"
              # Normaliza se der cd de dirname resultou em / mesmo
              abs="$(cd "$(dirname "$abs")" && pwd)/$(basename "$abs")"
              ;;
        esac
        if [ "$abs" = "$cwd" ] || [ "${cwd#$abs/}" != "$cwd" ]; then
          basename "$f" .code-workspace
          return 0
        fi
      done <<<"$paths"
    done
  fi

  echo "default"
}

harness_resolve_worktree_slug() {
  local worktree_root="$1"
  [ -n "$worktree_root" ] || { echo "harness_resolve_worktree_slug: worktree_root vazio" >&2; return 2; }

  worktree_root="${worktree_root%/}"
  local parent_dir
  parent_dir="$(dirname "$worktree_root")"
  local basename_dir
  basename_dir="$(basename "$worktree_root")"

  # Caso especial Lumos pattern: <repo>.worktrees/<branch-slug-worktree>
  # Ex: .../Lumos.worktrees/feat-FLO-513--Process-a-refund -> slug = Lumos__<safe-branch>
  local parent_base
  parent_base="$(basename "$parent_dir")"

  local repo_part=""
  local branch_part="$basename_dir"

  case "$parent_base" in
    *.worktrees)
      repo_part="${parent_base%.worktrees}"
      # branch_part = basename_dir (já é o slug do branch do worktree)
      ;;
    *)
      # Caso normal (não worktree isolada): usar git repo root name + branch
      repo_part="$basename_dir"
      local branch="main"
      if command -v git >/dev/null 2>&1; then
        if [ -d "$worktree_root/.git" ] || [ -f "$worktree_root/.git" ]; then
          local b
          b="$(git -C "$worktree_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
          if [ -n "$b" ] && [ "$b" != "HEAD" ]; then branch="$b"; fi
        fi
      fi
      branch_part="$branch"
      ;;
  esac

  local safe_repo safe_branch
  safe_repo="$(echo "$repo_part" | sed 's/[^a-zA-Z0-9_-]/--/g')"
  safe_branch="$(echo "$branch_part" | sed 's/[^a-zA-Z0-9_-]/--/g')"

  echo "${safe_repo}__${safe_branch}"
}

harness_compute_paths() {
  local worktree_root="${1:-$WORKTREE_ROOT}"
  local session_id="${2:-$(harness_current_session_id)}"
  session_id="${session_id:-unknown-session}"
  local cwd_override="${3:-$PWD}"

  [ -n "$worktree_root" ] || { echo "harness_compute_paths: WORKTREE_ROOT not set" >&2; return 2; }

  export HARNESS_WORKSPACE_NAME="$(harness_resolve_workspace_name "$cwd_override")"
  export HARNESS_WORKTREE_SLUG="$(harness_resolve_worktree_slug "$worktree_root")"
  export HARNESS_WORKSPACE_DIR="$HARNESS_SESSIONS_ROOT/$HARNESS_WORKSPACE_NAME"
  export HARNESS_WORKTREE_DIR="$HARNESS_WORKSPACE_DIR/$HARNESS_WORKTREE_SLUG"
  export HARNESS_WORKSPACE_SHARED="$HARNESS_WORKTREE_DIR/workspace"
  export HARNESS_SESSION_DIR="$HARNESS_WORKTREE_DIR/sessions/$session_id"
  export HARNESS_LEVEL2_BINDING="$HARNESS_SESSION_DIR/binding.md"

  # HARD STOP (NON-NEGOTIABLE): nenhum desses paths pode cair DENTRO da worktree.
  # Se HARNESS_SESSIONS_ROOT por engano estiver apontando pra dentro de worktree_root,
  # por exemplo USER setou HARNESS_SESSIONS_ROOT=/home/.../Lumos.worktrees/.sess,
  # daqui a nada artifacts começam a aparecer no diff. Trava imediatamente.
  harness_assert_outside_worktree "$HARNESS_WORKSPACE_DIR"   "$worktree_root" "HARNESS_WORKSPACE_DIR"
  harness_assert_outside_worktree "$HARNESS_WORKTREE_DIR"    "$worktree_root" "HARNESS_WORKTREE_DIR"
  harness_assert_outside_worktree "$HARNESS_WORKSPACE_SHARED" "$worktree_root" "HARNESS_WORKSPACE_SHARED"
  harness_assert_outside_worktree "$HARNESS_SESSION_DIR"     "$worktree_root" "HARNESS_SESSION_DIR"
  harness_assert_outside_worktree "$HARNESS_LEVEL2_BINDING"  "$worktree_root" "HARNESS_LEVEL2_BINDING"
}

harness_ensure_session_dirs() {
  # Hard stop extra por redundância: se paths passaram mas algo mudou, trava antes do mkdir.
  local wt_root="${1:-${WORKTREE_ROOT:-}}"
  if [ -n "$wt_root" ]; then
    harness_assert_outside_worktree "$HARNESS_WORKSPACE_SHARED" "$wt_root" "HARNESS_WORKSPACE_SHARED (ensure)"
    harness_assert_outside_worktree "$HARNESS_SESSION_DIR"      "$wt_root" "HARNESS_SESSION_DIR (ensure)"
  fi
  mkdir -p "$HARNESS_WORKSPACE_DIR" \
           "$HARNESS_WORKTREE_DIR" \
           "$HARNESS_WORKSPACE_SHARED" \
           "$HARNESS_WORKSPACE_SHARED/design" \
           "$HARNESS_WORKSPACE_SHARED/tasks" \
           "$HARNESS_SESSION_DIR" \
           "$HARNESS_SESSION_DIR/qa" \
           "$HARNESS_SESSION_DIR/qa/screenshots"
}

harness_level2_binding_path() {
  local session_id="$1"
  local worktree_root="$2"
  local cwd_override="${3:-$PWD}"
  HARNESS_WORKSPACE_NAME="$(harness_resolve_workspace_name "$cwd_override")" \
  HARNESS_WORKTREE_SLUG="$(harness_resolve_worktree_slug "$worktree_root")" \
  echo "$HARNESS_SESSIONS_ROOT/$HARNESS_WORKSPACE_NAME/$HARNESS_WORKTREE_SLUG/sessions/$session_id/binding.md"
}

harness_decisions_path() {
  local worktree_root="${1:-${WORKTREE_ROOT:-}}"
  local cwd_override="${2:-$PWD}"
  [ -n "$worktree_root" ] || { echo "harness_decisions_path: WORKTREE_ROOT empty" >&2; return 2; }
  local hwn sl out_path
  hwn="$(harness_resolve_workspace_name "$cwd_override")"
  sl="$(harness_resolve_worktree_slug "$worktree_root")"
  out_path="$HARNESS_SESSIONS_ROOT/$hwn/$sl/workspace/decisions.log.jsonl"
  harness_assert_outside_worktree "$out_path" "$worktree_root" "HARNESS_DECISIONS_LOG"
  echo "$out_path"
}

harness_append_decision_jsonl() {
  local worktree_root="$1"
  local event_type="$2"
  local payload_json="$3"
  local ts_override="${4:-}"

  [ -n "$worktree_root" ] || { echo "harness_append_decision_jsonl: worktree_root empty" >&2; return 2; }
  [ -n "$event_type" ]   || { echo "harness_append_decision_jsonl: event_type empty" >&2; return 2; }
  [ -n "$payload_json" ] || payload_json="{}"

  local out_path
  out_path="$(harness_decisions_path "$worktree_root")"
  # Redundância extra: decisions_path JÁ roda o assert, mas repetimos aqui por
  # se alguém passar um out_path hardcoded de fora (caso que nunca deve existir,
  # mas custo de rodar de novo é 0).
  harness_assert_outside_worktree "$out_path" "$worktree_root" "HARNESS_DECISIONS_LOG (append)"
  mkdir -p "$(dirname "$out_path")"

  local ts_iso
  if [ -n "$ts_override" ]; then
    ts_iso="$ts_override"
  else
    ts_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  fi

  local spec_id_val="${SPEC_ID:-null}"
  local session_id_val
  session_id_val="$(harness_current_session_id)"
  session_id_val="${session_id_val:-null}"
  [ "$spec_id_val" = "NONE" ] && spec_id_val="null"

  python3 - "$out_path" "$ts_iso" "$event_type" "$worktree_root" "$spec_id_val" "$session_id_val" "$payload_json" <<'PYEOF'
import json, sys, hashlib, os

out_path, ts, event, wt_root, spec_id_s, session_id_s, payload_s = sys.argv[1:8]

def parse_nullable(s):
    if s in ("null", "None", "", "NONE"):
        return None
    return s

try:
    payload = json.loads(payload_s)
except Exception:
    payload = {"raw": payload_s}

if not isinstance(payload, dict):
    payload = {"value": payload}

entry = {
    "ts": ts,
    "event": event,
    "spec_id": parse_nullable(spec_id_s),
    "session_id": parse_nullable(session_id_s),
    "worktree_root": wt_root,
    "data": payload,
    "_v": 1
}

line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
dedup_key = hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]

if os.path.exists(out_path):
    with open(out_path, "rb") as f:
        existing = f.read()
    needle = dedup_key.encode("utf-8")  # Not actually in the file; we use content hash via full line comparison instead
    # Simpler dedup: compare exact line with trailing newlines
    needle_line = (line + "\n").encode("utf-8")
    if needle_line in (b"\n" + existing).replace(b"\n", b"\n", 1):  # too naive; fallback: just check if raw entry exists verbatim
        if (line + "\n").encode() in existing:
            sys.exit(0)

with open(out_path, "a", encoding="utf-8") as f:
    f.write(line + "\n")
PYEOF
}

# ---------------------------------------------------------------------------
# LIMPEZA DE LEGACY ARTIFACTS DENTRO DA WORKTREE (BIND TIME)
# ---------------------------------------------------------------------------
# Por bugs harness antigos, pode existir .trae/ ou decisions.log.jsonl /
# task_graph etc DENTRO da worktree. Ao criar um NOVO binding BOUND,
# identificamos TUDO isso, movemos para $HARNESS_WORKSPACE_SHARED/legacy_binding_cleanup/
# como backup seguro, e DELETAMOS da worktree.
#
# NÃO É git rm --cached (deixa história intacta); só limpa da cópia de
# trabalho atual. Se arquivos já estavam no git history, o problema aparece
# em diff do harness-ship? NÃO — porque harness-ship só faz diff vs
# DEFAULT_BRANCH, e arquivos que estão ambos lado vs diff sem mudança são
# irrelevantes. A limpeza é só do working tree.

harness_cleanup_legacy_artifacts_in_worktree() {
  local worktree_root="$1"
  local shared_outside="$2"   # HARNESS_WORKSPACE_SHARED já resolvido FORA worktree

  [ -n "$worktree_root" ] || return 0
  [ -d "$worktree_root" ]   || return 0
  [ -n "$shared_outside" ]  || return 0

  harness_assert_outside_worktree "$shared_outside" "$worktree_root" "cleanup_backup_target"

  local backup_dir="$shared_outside/legacy_binding_cleanup/$(date -u +"%Y%m%dT%H%M%SZ")"
  local total_found=0
  local -a found_list=()

  # Lista de patterns EXATOS (find name patterns). Igual a blacklist anterior mas
  # agora usada apenas find + delete worktree copy, NÃO mais usada pra gitignore.
  local -a patterns=(
    ".trae"                              # diretorio inteiro
    "decisions.log.jsonl"
    "decisions.log.md"
    "decisions.log"
    "decision.log.jsonl"
    "decision.log.md"
    "decision.log"
    "task_graph.md"
    "task_graph.yaml"
    "manual_test_plan.md"
    "final_summary.md"
    "execution_batches.md"
    "batch_execution_report.md"
    "merge_audit.md"
    "merge_audit.jsonl"
    "scope-report.md"
    "scope-report.json"
    "scope_check_report.md"
    "scope_check_report.json"
    "gh_stack_plan.md"
    "task_envelope.md"
    "graphify-out"
    "harness-review-report.md"
    "harness-compliance-report.md"
    "flockr-review-report.md"
  )

  # Construindo find args.
  local -a find_args=()
  local p
  for p in "${patterns[@]}"; do
    find_args+=( -o -name "$p" )
  done
  # Remove o primeiro -o (bug do inicio da cadeia):
  unset 'find_args[0]'

  # find retorna arquivos OU diretórios que batam os patterns, DENTRO da worktree:
  # Usamos -print0 / read -d '' pra segurar paths com spaces/newlines.
  while IFS= read -r -d '' match; do
    total_found=$(( total_found + 1 ))
    found_list+=( "$match" )
  done < <(cd "$worktree_root" && find . \( "${find_args[@]}" \) -print0 2>/dev/null | sed -z 's@^\./@@' | while IFS= read -r -d '' x; do printf '%s\0' "$worktree_root/$x"; done)

  if [ "$total_found" -eq 0 ]; then
    return 0
  fi

  # Tem legado: cria pasta backup e move tudo pra lá preservando caminhos.
  mkdir -p "$backup_dir"

  local rel target_dir
  local -a report=()
  for match in "${found_list[@]}"; do
    # Relativo a worktree_root
    rel="${match#$worktree_root/}"
    [ "$rel" = "$match" ] && continue   # segurança nunca deve acontecer

    # Target no backup_dir
    target="$backup_dir/$rel"
    target_dir="$(dirname "$target")"
    mkdir -p "$target_dir"

    if mv -f "$match" "$target" 2>/dev/null; then
      report+=( "$rel -> backup $target" )
    else
      # se não mover por qualquer motivo (arquivo foi deletado/lock/nfs falhou etc),
      # tenta rm -f anyway se for UNTRACKED mas deixa quieto.
      rm -rf "$match" 2>/dev/null || true
      report+=( "$rel (deleted fallback, mv failed)" )
    fi
  done

  # Reporta em stderr p/ agente verificar. O path backup fica em
  # $HARNESS_WORKSPACE_SHARED/legacy_binding_cleanup/<ts>/ .
  {
    echo "🧹 harness_cleanup_legacy_artifacts: movidos $total_found arquivos/diretórios LEGACY de dentro de $worktree_root."
    echo "   backup_dir = $backup_dir"
    local r
    for r in "${report[@]}"; do
      echo "    · $r"
    done
  } >&2
}

# ---------------------------------------------------------------------------
# LEVEL 1 BINDING REGISTRY + CLEANUP HOOK
# ---------------------------------------------------------------------------
# Sempre que houver BIND_APPEND / BIND_BOOTSTRAP com STATUS=BOUND, o cleanup
# roda antes de escrever no registry.

harness_migrate_decisions_md_to_jsonl() {
  local old_md="$1"
  local new_jsonl="$2"
  local worktree_root="$3"

  [ -f "$old_md" ] || return 0
  mkdir -p "$(dirname "$new_jsonl")"

  python3 - "$old_md" "$new_jsonl" "$worktree_root" <<'PYEOF'
import json, re, sys, os

md_path, out_path, wt_root = sys.argv[1:4]

with open(md_path, encoding="utf-8") as f:
    lines = [ln.rstrip("\n") for ln in f]

entries = []
entry_re = re.compile(r"^\[(?P<ts>[^\]]+)\]\s+\[(?P<event>[^\]]+)\]\s*(?P<rest>.*)$")

for ln in lines:
    m = entry_re.match(ln)
    if not m:
        if ln.strip() and entries:
            entries[-1]["data"]["raw_rest"] = (entries[-1]["data"].get("raw_rest") or "") + "\n" + ln
        continue
    ts = m.group("ts").strip()
    event = m.group("event").strip().replace(" ", "_").upper()
    rest = m.group("rest").strip()
    entries.append({
        "ts": ts,
        "event": event,
        "spec_id": None,
        "session_id": None,
        "worktree_root": wt_root,
        "data": {"legacy_text": rest},
        "_v": 1
    })

with open(out_path, "a", encoding="utf-8") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
PYEOF
}

# ---------------------------------------------------------------------------
# CAVEAN-STYLE TOKEN REDUCTION WRAPPERS (5 heurísticas, opt-in via call site)
# Preserva semântica: NUNCA remove informação sem marcar [TRUNCADO ...] explicitamente.
# Todas suportam bypass via env HARNESS_FULL_OUTPUT=1 (volta saída original completa).
# ---------------------------------------------------------------------------
: "${HARNESS_TR_READ_MAX_LINES:=300}"        # H2 Read truncation
: "${HARNESS_TR_STDOUT_MAX_CHARS:=4000}"      # H4 RunCommand stdout/stderr cap
: "${HARNESS_TR_DIFF_MAX_LINES:=500}"         # H1 Diff trim (± lines)
: "${HARNESS_TR_GREP_CONTEXT:=0}"             # H5 Grep default context lines
: "${HARNESS_TR_COLLAPSE_BLANK:=1}"           # H3 Blank/ws collapse (0 or 1)

# H1 + H4: wrap `git diff` → only +/- changed lines (no metadata headers like ---, +++, @@ index), collapse blanks, cap chars.
harness_tr_diff() {
  local tmp
  tmp="$(cat || true)"
  if [ "${HARNESS_FULL_OUTPUT:-}" = "1" ]; then printf '%s\n' "$tmp"; return 0; fi
  local filtered
  set +o pipefail
  filtered="$(printf '%s\n' "$tmp" | grep -E '^[+-][^+-]' 2>/dev/null | head -n "$HARNESS_TR_DIFF_MAX_LINES" 2>/dev/null || true)"
  set -o pipefail || true
  if [ "$HARNESS_TR_COLLAPSE_BLANK" = "1" ]; then
    filtered="$(printf '%s\n' "$filtered" | awk 'NF {print; blank=0; next} !blank {print; blank=1}' || true)"
  fi
  local total_chars="${#filtered}"
  local msg=""
  if [ "$total_chars" -gt "$HARNESS_TR_STDOUT_MAX_CHARS" ]; then
    msg=$'\n[...TRUNCADO no CHAR '"$HARNESS_TR_STDOUT_MAX_CHARS"' de '"$total_chars"'; set HARNESS_FULL_OUTPUT=1 para saída completa]'
    filtered="${filtered:0:$HARNESS_TR_STDOUT_MAX_CHARS}"
  fi
  printf '%s%s\n' "$filtered" "$msg"
}

# H2: wrap file content (stdout of Read tool) → cap lines, mark truncation.
harness_tr_read() {
  local total_lines="${1:-0}"
  local tmp
  tmp="$(cat)"
  if [ "${HARNESS_FULL_OUTPUT:-}" = "1" ]; then printf '%s\n' "$tmp"; return 0; fi
  local actual_lines
  actual_lines="$(printf '%s\n' "$tmp" | wc -l)"
  if [ "$actual_lines" -gt "$HARNESS_TR_READ_MAX_LINES" ]; then
    local remaining=$(( actual_lines - HARNESS_TR_READ_MAX_LINES ))
    local headcap
    headcap="$(printf '%s\n' "$tmp" | head -n "$HARNESS_TR_READ_MAX_LINES")"
    printf '%s\n[...TRUNCADO lines %s-%s (restam %s linhas); use offset/Limit Read tool ou HARNESS_FULL_OUTPUT=1]\n' \
      "$headcap" "$(( HARNESS_TR_READ_MAX_LINES + 1 ))" "$actual_lines" "$remaining"
  else
    printf '%s\n' "$tmp"
  fi
}

# H3: collapse sequential blank lines (≥2 → 1) + strip trailing whitespace per line.
harness_tr_collapse_blank() {
  local tmp
  tmp="$(cat)"
  if [ "${HARNESS_FULL_OUTPUT:-}" = "1" ] || [ "$HARNESS_TR_COLLAPSE_BLANK" != "1" ]; then printf '%s\n' "$tmp"; return 0; fi
  printf '%s\n' "$tmp" | sed 's/[[:space:]]*$//' | awk 'NF {print; blank=0; next} !blank {print; blank=1}'
}

# H4: cap stdout/stderr output chars (default 4000). Use after RunCommand.
harness_tr_stdout() {
  local tmp
  tmp="$(cat)"
  if [ "${HARNESS_FULL_OUTPUT:-}" = "1" ]; then printf '%s\n' "$tmp"; return 0; fi
  local total="${#tmp}"
  if [ "$total" -le "$HARNESS_TR_STDOUT_MAX_CHARS" ]; then printf '%s\n' "$tmp"; return 0; fi
  local cap=$HARNESS_TR_STDOUT_MAX_CHARS
  printf '%s\n[...TRUNCADO no CHAR %s de %s; verifique output completo ou HARNESS_FULL_OUTPUT=1]\n' \
    "${tmp:0:$cap}" "$cap" "$total"
}

# H5: compact grep output — show matching lines only; default no -C context (override via HARNESS_TR_GREP_CONTEXT).
# Usage: harness_tr_grep "<pattern>" "<path>" [type_filter] → returns lines: "path:line:content" (no filename-only metadata).
harness_tr_grep() {
  local pattern="$1" path="$2" type_filter="${3:-}"
  shift 3 || true
  if [ "${HARNESS_FULL_OUTPUT:-}" = "1" ]; then
    local grep_args=("-nH" "--" "$pattern")
    [ -n "$type_filter" ] && grep_args=("--include=*.$type_filter" "${grep_args[@]}")
    grep "${grep_args[@]}" "$path" 2>/dev/null || true
    return 0
  fi
  local ctx="$HARNESS_TR_GREP_CONTEXT"
  local grep_args=("-nH")
  [ "$ctx" -gt 0 ] && grep_args+=("-C" "$ctx")
  [ -n "$type_filter" ] && grep_args+=("--include=*.$type_filter")
  grep_args+=("--" "$pattern")
  set +o pipefail
  ( grep "${grep_args[@]}" "$path" 2>/dev/null || true ) | ( harness_tr_collapse_blank || true ) | ( harness_tr_stdout || true )
  set -o pipefail || true
}

# ---------------------------------------------------------------------------
# LEVEL 1 BINDING REGISTRY (GLOBAL INDEX, append-only JSONL)
# Single source of truth = $HARNESS_HOME/bindings/registry.jsonl (NÃO .md, sem dual)
# Schema v1 por linha:
#   {ts, event: BIND_BOOTSTRAP|BIND_APPEND|BIND_FLAGS_UPDATE, session_id,
#    status: BOUND|UNBOUND|FLAGS, worktree_root, workspace_name|null, worktree_slug|null,
#    branch|null, friendly_name|null, harness_session_dir|null, harness_workspace_shared|null,
#    workspace_file|null, reason|null, flags:{LANG_PT_CHECK: "ENABLED"|"DISABLED"}, _v:1}
# ---------------------------------------------------------------------------
harness_registry_path() {
  echo "$HARNESS_HOME/bindings/registry.jsonl"
}

harness_registry_append_jsonl() {
  local session_id="$1"
  local status="$2"
  local worktree_root="$3"
  local payload_json="${4:-{\}}"
  local ts_override="${5:-}"

  [ -n "$session_id" ]   || { echo "harness_registry_append_jsonl: session_id empty" >&2; return 2; }
  [ -n "$status" ]       || { echo "harness_registry_append_jsonl: status empty" >&2; return 2; }
  [ -n "$worktree_root" ] || { echo "harness_registry_append_jsonl: worktree_root empty" >&2; return 2; }

  # ── HOOK: on first BIND_BOOTSTRAP / BIND_APPEND de STATUS=BOUND, limpa artifacts
  #    legados que PODEM estar DENTRO da worktree (bugs harness antigos).
  #    Fazemos isso ANTES de escrever a entry no registry, e usamos o próprio
  #    HARNESS_WORKSPACE_SHARED (já resolvido FORA worktree via harness_compute_paths)
  #    como destino do backup. Se shared ainda não estiver definido, computamos.
  if [ "$status" = "BOUND" ]; then
    local wt_shared
    wt_shared="${HARNESS_WORKSPACE_SHARED:-}"
    if [ -z "$wt_shared" ] || [ "$wt_shared" = "/" ]; then
      local tmp_hwn tmp_sl
      tmp_hwn="$(harness_resolve_workspace_name "$PWD")"
      tmp_sl="$(harness_resolve_worktree_slug "$worktree_root")"
      wt_shared="${HARNESS_SESSIONS_ROOT:-$HOME/code/harness-sessions}/$tmp_hwn/$tmp_sl/workspace"
    fi
    # Garante que o backup directory não cai dentro da worktree.
    harness_assert_outside_worktree "$wt_shared" "$worktree_root" "wt_shared cleanup root"
    mkdir -p "$wt_shared"
    harness_cleanup_legacy_artifacts_in_worktree "$worktree_root" "$wt_shared"
  fi

  local out_path
  out_path="$(harness_registry_path)"
  mkdir -p "$(dirname "$out_path")"

  local ts_iso
  if [ -n "$ts_override" ]; then
    ts_iso="$ts_override"
  else
    ts_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  fi

  python3 - "$out_path" "$ts_iso" "$session_id" "$status" "$worktree_root" "$payload_json" <<'PYEOF'
import json, sys, os

out_path, ts, sid, status, wt_root, payload_s = sys.argv[1:7]

try:
    payload = json.loads(payload_s)
except Exception:
    payload = {"raw": payload_s}
if not isinstance(payload, dict):
    payload = {"value": payload}

entry = {
    "ts": ts,
    "event": payload.pop("event", (
        "BIND_FLAGS_UPDATE" if status == "FLAGS" else
        "BIND_UNBOUND"    if status == "UNBOUND" else
        "BIND_APPEND"
    )),
    "session_id": sid,
    "status": status,
    "worktree_root": wt_root,
    "workspace_name": payload.pop("workspace_name", None),
    "worktree_slug":  payload.pop("worktree_slug", None),
    "branch":         payload.pop("branch", None),
    "friendly_name":  payload.pop("friendly_name", None),
    "harness_session_dir":      payload.pop("harness_session_dir", None),
    "harness_workspace_shared": payload.pop("harness_workspace_shared", None),
    "workspace_file": payload.pop("workspace_file", None),
    "reason":         payload.pop("reason", None),
    "flags": {
        "LANG_PT_CHECK": payload.pop("LANG_PT_CHECK",
                          (payload.get("flags") or {}).get("LANG_PT_CHECK", "ENABLED"))
    },
    "data": payload,
    "_v": 1
}

line = json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

if os.path.exists(out_path):
    with open(out_path, "rb") as f:
        existing = f.read()
    if (line + "\n").encode() in existing:
        sys.exit(0)

with open(out_path, "a", encoding="utf-8") as f:
    f.write(line + "\n")
PYEOF
}

harness_registry_lookup_last() {
  local session_id="${1:-$(harness_current_session_id)}"
  [ -n "$session_id" ] || { echo "harness_registry_lookup_last: session_id empty" >&2; return 2; }
  local out_path
  out_path="$(harness_registry_path)"
  [ -f "$out_path" ] || return 1
  python3 - "$out_path" "$session_id" <<'PY'
import json, sys
p, sid = sys.argv[1:3]
last = None
with open(p) as f:
    for ln in f:
        ln = ln.strip()
        if not ln: continue
        try: e = json.loads(ln)
        except Exception: continue
        if e.get("session_id") == sid:
            last = e
if last is None:
    sys.exit(1)
print(json.dumps(last, ensure_ascii=False, indent=2))
PY
}

harness_registry_migrate_md_to_jsonl() {
  local old_md="$1"
  local new_jsonl="$2"
  [ -f "$old_md" ] || return 0
  mkdir -p "$(dirname "$new_jsonl")"

  python3 - "$old_md" "$new_jsonl" <<'PY'
import json, re, sys
md_path, out_path = sys.argv[1:3]

def parse_kv(line_text):
    d = {}
    for m in re.finditer(r"(?P<k>[A-Z_][A-Z0-9_]*)=(?P<v>(?:\"[^\"]*\"|'[^']*'|\S+))", line_text):
        v = m.group("v")
        if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
            v = v[1:-1]
        d[m.group("k")] = v
    return d

entries = []
header_re = re.compile(r"^\[(?P<ts>[^\]]+)\]\s*(?:\[(?P<tag>[^\]]*)\]\s*)?(?P<rest>.*)$")

with open(md_path, encoding="utf-8") as f:
    lines = [ln.rstrip("\n") for ln in f]

for raw in lines:
    if not raw.strip():
        continue
    if raw.strip() == "---":
        continue
    m = header_re.match(raw)
    if not m:
        continue
    ts = m.group("ts").strip()
    tag = (m.group("tag") or "").strip()
    rest = m.group("rest").strip()
    kv = parse_kv(" " + rest + " ")

    sid = kv.get("SESSION_ID")
    status = kv.get("STATUS", "BOUND")
    wt_root = kv.get("WORKTREE_ROOT", "")
    if not sid or not wt_root:
        continue

    payload = {
        "workspace_name": kv.get("WORKSPACE_NAME"),
        "worktree_slug":  kv.get("WORKTREE_SLUG"),
        "branch":         kv.get("BRANCH"),
        "friendly_name":  kv.get("FRIENDLY_NAME"),
        "harness_session_dir":      kv.get("HARNESS_SESSION_DIR"),
        "harness_workspace_shared": kv.get("HARNESS_WORKSPACE_SHARED"),
        "workspace_file": kv.get("WORKSPACE_FILE"),
        "reason":         kv.get("REASON"),
        "event_from_tag": tag or None,
    }
    entries.append({
        "ts": ts if ts.endswith("Z") or "+" in ts else ts + "Z",
        "event": (tag.replace("BIND-BOOTSTRAP", "BIND_BOOTSTRAP").replace(" ", "_").replace("-","_") if "BIND" in tag else "BIND_APPEND") if tag else "BIND_APPEND",
        "session_id": sid,
        "status": status,
        "worktree_root": wt_root,
        "workspace_name": payload["workspace_name"],
        "worktree_slug":  payload["worktree_slug"],
        "branch":         payload["branch"],
        "friendly_name":  payload["friendly_name"],
        "harness_session_dir":      payload["harness_session_dir"],
        "harness_workspace_shared": payload["harness_workspace_shared"],
        "workspace_file": payload["workspace_file"],
        "reason":         payload["reason"],
        "flags": {"LANG_PT_CHECK": "ENABLED"},
        "data": {k:v for k,v in payload.items() if v is not None},
        "_v": 1
    })

with open(out_path, "a", encoding="utf-8") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
PY
}

# When executed directly (not sourced), run a self-test smoke.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  echo "== harness_sessions_contract.sh self-test smoke =="
  echo "HARNESS_SESSIONS_ROOT = $HARNESS_SESSIONS_ROOT"
  echo "resolve_workspace_name($PWD) = $(harness_resolve_workspace_name "$PWD")"

  echo
  echo "== Runtime-neutral session smoke =="

  unset HARNESS_SESSION_ID SESSION_ID
  [ "$(harness_current_session_id)" = "" ] || {
    echo "SESSION empty fallback = FAIL"
    exit 1
  }

  export SESSION_ID="sess-trae-smoke"
  [ "$(harness_current_session_id)" = "sess-trae-smoke" ] || {
    echo "SESSION_ID Trae fallback = FAIL"
    exit 1
  }
  echo "SESSION_ID Trae fallback = PASS"

  export HARNESS_SESSION_ID="sess-codex-smoke"
  [ "$(harness_current_session_id)" = "sess-codex-smoke" ] || {
    echo "HARNESS_SESSION_ID precedence = FAIL"
    exit 1
  }
  echo "HARNESS_SESSION_ID precedence = PASS"

  unset HARNESS_SESSION_ID
  export SESSION_ID="sess-smoke"

  # Slug smoke:
  testdir="$(mktemp -d)"
  trap 'rm -rf "$testdir"' EXIT
  (cd "$testdir" && git init -q -b feat/FOO-123--Hello && echo "slug($testdir) = $(harness_resolve_worktree_slug "$testdir")")

  # Decisions helper smoke (temp file):
  DEC_TEST_DIR="$(mktemp -d)"
  WORKTREE_TEST="$DEC_TEST_DIR/wt"
  mkdir -p "$WORKTREE_TEST"
  export SPEC_ID="SPEC-SMOKE-1"
  export SESSION_ID="sess-smoke"
  harness_append_decision_jsonl "$WORKTREE_TEST" "TEST_EVENT" '{"key":"value","approver":"user"}'
  DEC_PATH="$(harness_decisions_path "$WORKTREE_TEST")"
  echo "decisions_path = $DEC_PATH"
  echo "decisions_jsonl content = $(cat "$DEC_PATH")"
  echo "json valid? = $(python3 -c "import json; [json.loads(l) for l in open('$DEC_PATH')]; print('PASS')")"
  rm -rf "$DEC_TEST_DIR"

  echo
  echo "== Registry smoke (JSONL global) =="
  REG_TMPDIR=$(mktemp -d)
  REG_TMP="$REG_TMPDIR/registry_test.jsonl"
  # use overrides to not pollute real registry: create via helper override? Simpler: just migrate inline synthetic md → smoke parse.
  # Write synthetic md file with 2 formats:
  printf '[2026-08-27T02:19:04-03:00] SESSION_ID=sess-test-1 STATUS=BOUND WORKTREE_ROOT=/tmp/wt1 BRANCH=feat/x REASON=test1\n' > "$REG_TMPDIR/reg.md"
  printf '[2026-08-30T19:03:15Z] [BIND-BOOTSTRAP standalone] SESSION_ID=sess-test-2 STATUS=BOUND WORKSPACE_NAME=Flockr WORKTREE_SLUG=Lumos__test WORKTREE_ROOT=/tmp/wt2 FRIENDLY_NAME=teste2 HARNESS_SESSION_DIR=/tmp/sess2 HARNESS_WORKSPACE_SHARED=/tmp/ws2 WORKSPACE_FILE=/tmp/Flockr.code-workspace\n' >> "$REG_TMPDIR/reg.md"
  harness_registry_migrate_md_to_jsonl "$REG_TMPDIR/reg.md" "$REG_TMP"
  N=$(wc -l < "$REG_TMP")
  echo "Migrated $N entries from md → jsonl"
  python3 -c "
import json
with open('$REG_TMP') as f:
    lines = f.readlines()
for i, ln in enumerate(lines):
    e = json.loads(ln)
    print(f'  entry{i}: ts={e[\"ts\"]} sid={e[\"session_id\"]} status={e[\"status\"]} wt={e[\"worktree_root\"]} friendly={e.get(\"friendly_name\")}')
print('REGISTRY parse ALL OK')
"
  # helper append + lookup
  harness_registry_append_jsonl "sess-smoke-reg-$$" "BOUND" "/tmp/test-wt" '{"workspace_name":"Flockr","friendly_name":"smoketest"}'
  harness_registry_lookup_last "sess-smoke-reg-$$" | head -3
  echo "registry_path real (not polluted with test above via file override - tests above used REG_TMP; last append below writes to ACTUAL global path):"
  echo "real registry path = $(harness_registry_path) (we wrote sess-smoke-reg-$$ there, will delete for cleanup)"
  # cleanup entry we just appended to the REAL global registry: re-write filter the sess-smoke-reg entry out.
  REAL_REG=$(harness_registry_path)
  if [ -f "$REAL_REG" ]; then
    python3 - "$REAL_REG" <<PY
import json, sys
p = sys.argv[1]
with open(p) as f:
    lines = [ln for ln in f if "sess-smoke-reg-" not in ln]
with open(p,"w") as f:
    f.writelines(lines)
PY
  fi
  rm -rf "$REG_TMPDIR"

  echo
  echo "== Token reduction smoke (5 heurísticas, defaults) =="
  # H3 collapse blank
  printf 'a\n\n\nb\n  \nc\n\n\n' | harness_tr_collapse_blank | cat -A
  # H4 stdout cap
  python3 -c "print('x'*5000)" | harness_tr_stdout | wc -c
  # H2 read trim
  python3 -c "[print(f'line{i}') for i in range(400)]" | harness_tr_read 400 | wc -l
fi


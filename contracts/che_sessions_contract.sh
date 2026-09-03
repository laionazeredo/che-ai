#!/usr/bin/env bash
# CHE SESSIONS PATH CONTRACT (CANÔNICO · DETERMINÍSTICO)
#
# ⚠️ BACKWARD COMPAT 1 RELEASE · DUPLO FALLBACK ENV
# Todo ENV CHE_* = ${CHE_*:-${HARNESS_*:-<default_literal>}}
# Sessões antigas que só definem HARNESS_* continuam funcionando 100%.
#
# Esse arquivo é um contrato: todo script/hook/skill do che que PRECISAR
# resolver paths de sessão/workspace/worktree DEVE fazer source nessas funções.
# NENHUM componente do che deve construir esses paths hardcoded manualmente
# fora daqui — causa colisão e migrações quebradas.
#
# AGNÓSTICO IDE (hosteia em TRAE hoje, mas portável p/ Cursor · CODEX · Claude Code · OpenCode)
#   CHE_HOST_IDE = trae | codex | cursor | claude-code | opencode  (default: "trae")
#   CHE_HOME     = onde está o repo che/.trae instalado (default: $HOME/.trae)
#   CHE_SESSION_ID · CHE_SESSION_DIR · CHE_WORKSPACES_ROOT = resolvidos pelos helpers abaixo
#
# VARIÁVEIS DE SAÍDA PADRONIZADAS (export quando sourced):
#   CHE_WORKSPACES_ROOT   = dir raiz de tudo mutável/gerado (default: $HOME/.che-workspaces)
#   CHE_WORKSPACE_NAME    = nome canônico do workspace (ex: Flockr)
#   CHE_WORKTREE_SLUG     = slug canônico repo__branch (ex: Lumos__feat--FLO-513)
#   CHE_WORKSPACE_DIR     = $CHE_WORKSPACES_ROOT/$CHE_WORKSPACE_NAME
#   CHE_WORKTREE_DIR      = $CHE_WORKSPACE_DIR/$CHE_WORKTREE_SLUG
#   CHE_WORKSPACE_SHARED  = $CHE_WORKTREE_DIR/.wt  (↙️ NOVO: dado durável compartilhado worktree)
#   CHE_SESSION_DIR       = $CHE_WORKTREE_DIR/sessions/<effective-session-id>  (efêmero per-session)
#   CHE_LEVEL2_BINDING    = $CHE_SESSION_DIR/binding.md  (§19 Level 2 detail)
#   CHE_DECISIONS_LOG     = $CHE_WORKSPACE_SHARED/decisions.log.jsonl  (single source, append-only JSONL)
#   ——— NÍVEL 1.5 · PROJETO (compartilhado worktrees × sessões do MESMO projeto) ———
#   CHE_PROJECT_SLUG  = slug canônico do PROJETO (derivado git remote origin URL)
#   CHE_PROJECT_DIR   = $CHE_WORKSPACES_ROOT/.registry/projects/$CHE_PROJECT_SLUG
#   CHE_PROJECT_PROFILE    = $CHE_PROJECT_DIR/project_profile.md   (auto: che-xray)
#   CHE_PRODUCT_CONTEXT    = $CHE_PROJECT_DIR/product_context.md   (humano: che-project-knowledge)
#   CHE_ARCHITECTURE_DOC   = $CHE_PROJECT_DIR/architecture.md      (hybrid auto+manual)
#   CHE_ROADMAP_DOC        = $CHE_PROJECT_DIR/roadmap.md           (humano)
#   CHE_PROJECT_REGISTRY   = $CHE_PROJECT_DIR/registry.jsonl       (append-only audit)
#
# FUNÇÕES EXPORT (CHE_* = oficial novo · HARNESS_* = alias legacy compat 1 release):
#   che_decisions_path  [cwd_override]  →  HARNESS_DECSSIONS_PATH alias
#       Imprime path absoluto decisions.log.jsonl do worktree.
#
#   che_append_decision_jsonl <worktree_root> <event_type> <payload_json> [ts]
#   harness_append_decision_jsonl (...)  → alias legacy
#
#   che_migrate_decisions_md_to_jsonl <old_md> <new_jsonl> <wt_root>
#       Migra LEGADO decisions.log.md → decisions.log.jsonl (one-shot)

set -euo pipefail

# ================================================================
# 1. IDE-NEUTRAL CORE ENVS (DUPLO FALLBACK · COMPAT HARNESS 1 release)
# ================================================================
# Host IDE (adaptadores futuros em adapters/<host_ide>/)
export CHE_HOST_IDE="${CHE_HOST_IDE:-${HARNESS_HOST_IDE:-trae}}"
# Root do próprio che (onde vive skills/, contracts/, CHE_RULES.md…)
export CHE_HOME="${CHE_HOME:-${HARNESS_HOME:-$HOME/.trae}}"
# Root de TODOS os artefatos gerados (workspaces, projetos, sessões).
# ANTES: $HOME/code/harness-sessions.  AGORA (padrão): $HOME/.che-workspaces
# Fallback triplo: CHE → HARNESS → se antigo dir existir usa ele senão NOVO default.
_che_old_default="$HOME/code/harness-sessions"
_che_new_default="$HOME/.che-workspaces"
if [ -n "${CHE_WORKSPACES_ROOT:-}" ]; then
  :
elif [ -n "${HARNESS_SESSIONS_ROOT:-}" ]; then
  export CHE_WORKSPACES_ROOT="$HARNESS_SESSIONS_ROOT"
elif [ -d "$_che_old_default" ] && [ ! -d "$_che_new_default" ]; then
  # Migration suave: se o usuário tem a pasta antiga e NÃO tem a nova → reuse antiga.
  # Quando o usuário rodar a migration G3 (manifesto48 etc) explicitamente, esse fallback some.
  export CHE_WORKSPACES_ROOT="$_che_old_default"
else
  export CHE_WORKSPACES_ROOT="$_che_new_default"
fi
# Alias legacy HARNESS_SESSIONS_ROOT (sempre aponta pro mesmo lugar CHE)
export HARNESS_SESSIONS_ROOT="$CHE_WORKSPACES_ROOT"

# ================================================================
# 2. SESSION RESOLVER (ide-neutral: CHE_SESSION_ID → SESSION_ID → adapter)
# ================================================================
che_current_session_id() {
  printf '%s\n' "${CHE_SESSION_ID:-${HARNESS_SESSION_ID:-${SESSION_ID:-}}}"
}
harness_current_session_id() { che_current_session_id "$@"; }  # alias legacy

# ================================================================
# 3. HARD STOP GUARDS — NUNCA artifacts DENTRO de WORKTREE_ROOT
# ================================================================
che_assert_outside_worktree() {
  local candidate_path="$1"
  local worktree_root="$2"
  local label="${3:-path}"

  [ -n "$candidate_path" ] || return 0
  [ -n "$worktree_root"  ] || return 0

  worktree_root="${worktree_root%/}"
  candidate_path_abs="$candidate_path"
  case "$candidate_path_abs" in
    /*) : ;;
    *)  candidate_path_abs="$(cd "$(dirname "$candidate_path_abs")" 2>/dev/null && pwd)/$(basename "$candidate_path_abs")" ;;
  esac

  if [ "$candidate_path_abs" = "$worktree_root" ] ||
     [ "${candidate_path_abs#$worktree_root/}" != "$candidate_path_abs" ]; then
    cat >&2 <<ERR

  ┌──────────────────────────────────────────────────────────────────────────┐
  │ 🔴 CHE SESSIONS CONTRACT VIOLATION — HARD STOP                           │
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
  │   - NÃO construa paths com \$PWD/.che/ nem \$WORKTREE_ROOT/.che/.        │
  │   - Sempre use:                                                          │
  │       source \$CHE_HOME/contracts/che_sessions_contract.sh               │
  │       che_compute_paths \$WORKTREE_ROOT "\$(che_current_session_id)"     │
  │   - Depois use \$CHE_WORKSPACE_SHARED (garantido FORA worktree).         │
  │                                                                          │
  │   Se foi um script/che que chegou aqui, aborte imediatamente.            │
  └──────────────────────────────────────────────────────────────────────────┘

ERR
    exit 99
  fi
}
harness_assert_outside_worktree() { che_assert_outside_worktree "$@"; }  # alias legacy

# ================================================================
# 4. IMPLEMENTAÇÃO HELPERS
# ================================================================

# ----- Resolve workspace name (.code-workspace / override / default)
che_resolve_workspace_name() {
  local cwd="${1:-$PWD}"
  cwd="$(cd "$cwd" && pwd)"

  if [ -n "${CHE_WORKSPACE_NAME_OVERRIDE:-${HARNESS_WORKSPACE_NAME_OVERRIDE:-}}" ]; then
    echo "${CHE_WORKSPACE_NAME_OVERRIDE:-$HARNESS_WORKSPACE_NAME_OVERRIDE}"
    return 0
  fi
  if [ -n "${CHE_WORKSPACE_NAME:-${HARNESS_WORKSPACE_NAME:-}}" ]; then
    echo "${CHE_WORKSPACE_NAME:-$HARNESS_WORKSPACE_NAME}"
    return 0
  fi

  local code_workspace_global="${CHE_CODE_WORKSPACES_DIR:-${HARNESS_CODE_WORKSPACES_DIR:-$HOME/code/code_workspaces}}"
  if [ -d "$code_workspace_global" ]; then
    local f
    for f in "$code_workspace_global"/*.code-workspace; do
      [ -f "$f" ] || continue
      local wfdir
      wfdir="$(dirname "$f")"
      local paths
      paths="$(grep -oE '"path"[[:space:]]*:[[:space:]]*"[^"]+"' "$f" 2>/dev/null | sed -E 's/.*"path"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' || true)"
      local p
      while IFS= read -r p; do
        [ -z "$p" ] && continue
        local abs
        case "$p" in
          /*) abs="$p" ;;
          *)  abs="$(cd "$wfdir" && cd "$(dirname "$p")" && pwd)/$(basename "$p")"
              abs="$(cd "$(dirname "$abs")" && pwd)/$(basename "$abs")" ;;
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
harness_resolve_workspace_name() { che_resolve_workspace_name "$@"; }

# ----- Slug worktree canônico: repo__<branch-safe> (inclui *.worktrees Flockr)
che_resolve_worktree_slug() {
  local worktree_root="$1"
  [ -n "$worktree_root" ] || { echo "che_resolve_worktree_slug: worktree_root vazio" >&2; return 2; }

  worktree_root="${worktree_root%/}"
  local parent_dir
  parent_dir="$(dirname "$worktree_root")"
  local basename_dir
  basename_dir="$(basename "$worktree_root")"

  local parent_base
  parent_base="$(basename "$parent_dir")"

  local repo_part=""
  local branch_part="$basename_dir"

  case "$parent_base" in
    *.worktrees)
      repo_part="${parent_base%.worktrees}"
      ;;
    *)
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
harness_resolve_worktree_slug() { che_resolve_worktree_slug "$@"; }

# ================================================================
# 5. NÍVEL 1.5 · PROJECT REGISTRY HELPERS
# ================================================================
che_project_slug_from_git_origin() {
  local worktree_root="${1:-${WORKTREE_ROOT:-}}"
  [ -n "$worktree_root" ] || { echo "che_project_slug_from_git_origin: WORKTREE_ROOT empty" >&2; return 2; }

  local origin_url=""
  if command -v git >/dev/null 2>&1; then
    origin_url="$(git -C "$worktree_root" remote get-url origin 2>/dev/null || echo "")"
  fi

  local raw=""
  if [ -n "$origin_url" ]; then
    raw="$(echo "$origin_url" \
      | sed -E 's#^(https?://|git@|ssh://|git://)##' \
      | sed -E 's#\.git$##' \
      | sed -E 's#^[^:]+:#/#')"
  else
    raw="local/$(basename "$worktree_root")"
  fi

  echo "$raw" \
    | sed -E 's#[^a-zA-Z0-9_-]#--#g' \
    | sed -E 's#--+#--#g' \
    | sed -E 's#^--|--$##g'
}
harness_project_slug_from_git_origin() { che_project_slug_from_git_origin "$@"; }

che_project_registry_dir() {
  local project_slug="${1:-${CHE_PROJECT_SLUG:-${HARNESS_PROJECT_SLUG:-}}}"
  [ -n "$project_slug" ] || { echo "che_project_registry_dir: project_slug empty" >&2; return 2; }
  echo "$CHE_WORKSPACES_ROOT/.registry/projects/$project_slug"
}
harness_project_registry_dir() { che_project_registry_dir "$@"; }

che_project_profile_path()  { che_project_registry_dir "$@" | xargs -I{} echo "{}/project_profile.md"; }
che_product_context_path()  { che_project_registry_dir "$@" | xargs -I{} echo "{}/product_context.md"; }
che_architecture_doc_path() { che_project_registry_dir "$@" | xargs -I{} echo "{}/architecture.md"; }
che_roadmap_doc_path()      { che_project_registry_dir "$@" | xargs -I{} echo "{}/roadmap.md"; }
che_project_registry_path() { che_project_registry_dir "$@" | xargs -I{} echo "{}/registry.jsonl"; }
harness_project_profile_path()  { che_project_profile_path "$@"; }
harness_product_context_path()  { che_product_context_path "$@"; }
harness_architecture_doc_path() { che_architecture_doc_path "$@"; }
harness_roadmap_doc_path()      { che_roadmap_doc_path "$@"; }
harness_project_registry_path() { che_project_registry_path "$@"; }

# ----- Compute ALL paths + asserts (MAIN ENTRY POINT PARA HOOKS E SKILLS)
che_compute_paths() {
  local worktree_root="${1:-${WORKTREE_ROOT:-}}"
  local session_id="${2:-$(che_current_session_id)}"
  session_id="${session_id:-unknown-session}"
  local cwd_override="${3:-$PWD}"

  [ -n "$worktree_root" ] || { echo "che_compute_paths: WORKTREE_ROOT not set" >&2; return 2; }

  export CHE_WORKSPACE_NAME="$(che_resolve_workspace_name "$cwd_override")"
  export HARNESS_WORKSPACE_NAME="$CHE_WORKSPACE_NAME"
  export CHE_WORKTREE_SLUG="$(che_resolve_worktree_slug "$worktree_root")"
  export HARNESS_WORKTREE_SLUG="$CHE_WORKTREE_SLUG"
  export CHE_PROJECT_SLUG="$(che_project_slug_from_git_origin "$worktree_root")"
  export HARNESS_PROJECT_SLUG="$CHE_PROJECT_SLUG"
  export CHE_PROJECT_DIR="$(che_project_registry_dir "$CHE_PROJECT_SLUG")"
  export HARNESS_PROJECT_DIR="$CHE_PROJECT_DIR"
  export CHE_WORKSPACE_DIR="$CHE_WORKSPACES_ROOT/$CHE_WORKSPACE_NAME"
  export HARNESS_WORKSPACE_DIR="$CHE_WORKSPACE_DIR"
  export CHE_WORKTREE_DIR="$CHE_WORKSPACE_DIR/$CHE_WORKTREE_SLUG"
  export HARNESS_WORKTREE_DIR="$CHE_WORKTREE_DIR"
  # ↙️ NOVO: duráveis da worktree ficam em .wt/ (será documentado em G3 path canonicity)
  export CHE_WORKSPACE_SHARED="$CHE_WORKTREE_DIR/.wt"
  export HARNESS_WORKSPACE_SHARED="$CHE_WORKSPACE_SHARED"
  export CHE_SESSION_DIR="$CHE_WORKTREE_DIR/sessions/$session_id"
  export HARNESS_SESSION_DIR="$CHE_SESSION_DIR"
  export CHE_LEVEL2_BINDING="$CHE_SESSION_DIR/binding.md"
  export HARNESS_LEVEL2_BINDING="$CHE_LEVEL2_BINDING"
  export CHE_PROJECT_PROFILE="$CHE_PROJECT_DIR/project_profile.md"
  export HARNESS_PROJECT_PROFILE="$CHE_PROJECT_PROFILE"
  export CHE_PRODUCT_CONTEXT="$CHE_PROJECT_DIR/product_context.md"
  export HARNESS_PRODUCT_CONTEXT="$CHE_PRODUCT_CONTEXT"
  export CHE_ARCHITECTURE_DOC="$CHE_PROJECT_DIR/architecture.md"
  export HARNESS_ARCHITECTURE_DOC="$CHE_ARCHITECTURE_DOC"
  export CHE_ROADMAP_DOC="$CHE_PROJECT_DIR/roadmap.md"
  export HARNESS_ROADMAP_DOC="$CHE_ROADMAP_DOC"
  export CHE_PROJECT_REGISTRY="$CHE_PROJECT_DIR/registry.jsonl"
  export HARNESS_PROJECT_REGISTRY="$CHE_PROJECT_REGISTRY"

  che_assert_outside_worktree "$CHE_PROJECT_DIR"      "$worktree_root" "CHE_PROJECT_DIR"
  che_assert_outside_worktree "$CHE_WORKSPACE_DIR"    "$worktree_root" "CHE_WORKSPACE_DIR"
  che_assert_outside_worktree "$CHE_WORKTREE_DIR"     "$worktree_root" "CHE_WORKTREE_DIR"
  che_assert_outside_worktree "$CHE_WORKSPACE_SHARED" "$worktree_root" "CHE_WORKSPACE_SHARED"
  che_assert_outside_worktree "$CHE_SESSION_DIR"      "$worktree_root" "CHE_SESSION_DIR"
  che_assert_outside_worktree "$CHE_LEVEL2_BINDING"   "$worktree_root" "CHE_LEVEL2_BINDING"
}
harness_compute_paths() { che_compute_paths "$@"; }

che_ensure_session_dirs() {
  local wt_root="${1:-${WORKTREE_ROOT:-}}"
  if [ -n "$wt_root" ]; then
    che_assert_outside_worktree "${CHE_PROJECT_DIR:-}"         "$wt_root" "CHE_PROJECT_DIR (ensure)"
    che_assert_outside_worktree "${CHE_WORKSPACE_SHARED:-}"    "$wt_root" "CHE_WORKSPACE_SHARED (ensure)"
    che_assert_outside_worktree "${CHE_SESSION_DIR:-}"         "$wt_root" "CHE_SESSION_DIR (ensure)"
  fi
  mkdir -p "$CHE_WORKSPACES_ROOT/.registry/projects/$CHE_PROJECT_SLUG"
  [ -f "$CHE_PROJECT_REGISTRY" ] || : > "$CHE_PROJECT_REGISTRY"
  mkdir -p "$CHE_WORKSPACE_DIR" \
           "$CHE_WORKTREE_DIR" \
           "$CHE_WORKSPACE_SHARED" \
           "$CHE_WORKSPACE_SHARED/design" \
           "$CHE_WORKSPACE_SHARED/tasks" \
           "$CHE_WORKSPACE_SHARED/specs" \
           "$CHE_WORKSPACE_SHARED/reports" \
           "$CHE_WORKSPACE_SHARED/architecture" \
           "$CHE_WORKSPACE_SHARED/gh_stack" \
           "$CHE_WORKSPACE_SHARED/legacy_binding_cleanup" \
           "$CHE_SESSION_DIR" \
           "$CHE_SESSION_DIR/reports" \
           "$CHE_SESSION_DIR/reviews" \
           "$CHE_SESSION_DIR/qa" \
           "$CHE_SESSION_DIR/qa/screenshots" \
           "$CHE_SESSION_DIR/qa/evidence" \
           "$CHE_SESSION_DIR/specs" \
           "$CHE_SESSION_DIR/design" \
           "$CHE_SESSION_DIR/tasks" \
           "$CHE_SESSION_DIR/diff_contexts" \
           "$CHE_SESSION_DIR/pr_comments" \
           "$CHE_SESSION_DIR/merge_audits" \
           "$CHE_SESSION_DIR/execution" \
           "$CHE_SESSION_DIR/graph" \
           "$CHE_SESSION_DIR/debugger"
}
harness_ensure_session_dirs() { che_ensure_session_dirs "$@"; }

che_level2_binding_path() {
  local session_id="$1"
  local worktree_root="$2"
  local cwd_override="${3:-$PWD}"
  CHE_WORKSPACE_NAME="$(che_resolve_workspace_name "$cwd_override")" \
  CHE_WORKTREE_SLUG="$(che_resolve_worktree_slug "$worktree_root")" \
  echo "$CHE_WORKSPACES_ROOT/$CHE_WORKSPACE_NAME/$CHE_WORKTREE_SLUG/sessions/$session_id/binding.md"
}
harness_level2_binding_path() { che_level2_binding_path "$@"; }

# ----- decisions.log.jsonl (append-only, idempotente sha256)
che_decisions_path() {
  local worktree_root="${1:-${WORKTREE_ROOT:-}}"
  local cwd_override="${2:-$PWD}"
  [ -n "$worktree_root" ] || { echo "che_decisions_path: WORKTREE_ROOT empty" >&2; return 2; }
  local hwn sl out_path
  hwn="$(che_resolve_workspace_name "$cwd_override")"
  sl="$(che_resolve_worktree_slug "$worktree_root")"
  out_path="$CHE_WORKSPACES_ROOT/$hwn/$sl/.wt/decisions.log.jsonl"
  che_assert_outside_worktree "$out_path" "$worktree_root" "CHE_DECISIONS_LOG"
  echo "$out_path"
}
harness_decisions_path() { che_decisions_path "$@"; }

che_append_decision_jsonl() {
  local worktree_root="$1"
  local event_type="$2"
  local payload_json="$3"
  local ts_override="${4:-}"

  [ -n "$worktree_root" ] || { echo "che_append_decision_jsonl: worktree_root empty" >&2; return 2; }
  [ -n "$event_type" ]   || { echo "che_append_decision_jsonl: event_type empty" >&2; return 2; }
  [ -n "$payload_json" ] || payload_json="{}"

  local out_path
  out_path="$(che_decisions_path "$worktree_root")"
  che_assert_outside_worktree "$out_path" "$worktree_root" "CHE_DECISIONS_LOG (append)"
  mkdir -p "$(dirname "$out_path")"

  local ts_iso
  if [ -n "$ts_override" ]; then
    ts_iso="$ts_override"
  else
    ts_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  fi

  local spec_id_val="${SPEC_ID:-null}"
  local session_id_val
  session_id_val="$(che_current_session_id)"
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

if os.path.exists(out_path):
    with open(out_path, "rb") as f:
        existing = f.read()
    if (line + "\n").encode() in existing:
        sys.exit(0)

with open(out_path, "a", encoding="utf-8") as f:
    f.write(line + "\n")
PYEOF
}
harness_append_decision_jsonl() { che_append_decision_jsonl "$@"; }

# ---------------------------------------------------------------------------
# OUTPUT PATH HELPER · SINGLE SOURCE OF TRUTH PARA TODO WRITE DO CHE
# ---------------------------------------------------------------------------
che_output_path() {
  local type="$1"
  local slug="$2"
  local related_id="$3"
  local scope="$4"
  local ext="$5"
  local suffix="${6:-}"

  [ -n "$type" ] || { echo "che_output_path: type is required" >&2; return 2; }
  [ -n "$slug" ] || { echo "che_output_path: slug is required" >&2; return 2; }
  [ -n "$ext"  ] || { echo "che_output_path: ext is required" >&2; return 2; }
  [ "$scope" = "session" ] || [ "$scope" = "workspace" ] || { echo "che_output_path: scope must be 'session' or 'workspace'" >&2; return 2; }

  local ts_prefix
  ts_prefix="$(date -u +"%Y%m%d-%H%M%S")"

  local subfolder=""
  case "$type" in
    report)        subfolder="reports" ;;
    review)        subfolder="reviews" ;;
    qa)            subfolder="qa/evidence" ;;
    spec)          subfolder="specs" ;;
    design)        subfolder="design" ;;
    task)          subfolder="tasks" ;;
    diff_context)  subfolder="diff_contexts" ;;
    pr_comments)   subfolder="pr_comments" ;;
    merge_audit)   subfolder="merge_audits" ;;
    execution)     subfolder="execution" ;;
    graph)         subfolder="graph" ;;
    debugger)      subfolder="debugger" ;;
    architecture)  subfolder="architecture" ;;
    adr)           subfolder="architecture" ;;
    gh_stack)      subfolder="gh_stack" ;;
    other)         subfolder="other" ;;
    *)             subfolder="$type" ;;
  esac

  local root_dir=""
  if [ "$scope" = "session" ]; then
    root_dir="${CHE_SESSION_DIR:-${HARNESS_SESSION_DIR:-${CHE_HOME:-$HOME/.trae}/outputs/fallback-session}}"
  else
    root_dir="${CHE_WORKSPACE_SHARED:-${HARNESS_WORKSPACE_SHARED:-${CHE_HOME:-$HOME/.trae}/outputs/fallback-workspace}}"
  fi

  local parent_dir="$root_dir/$subfolder"
  if [ -n "$related_id" ]; then
    parent_dir="$parent_dir/$related_id"
  fi

  local filename="${ts_prefix}-${slug}"
  if [ -n "$suffix" ]; then
    filename="${filename}_${suffix}"
  fi
  filename="${filename}.${ext}"

  local final_path="$parent_dir/$filename"
  mkdir -p "$parent_dir"

  local wt_for_assert="${WORKTREE_ROOT:-}"
  if [ -n "$wt_for_assert" ]; then
    che_assert_outside_worktree "$final_path" "$wt_for_assert" "che_output_path: type=$type related=$related_id scope=$scope"
  fi

  printf '%s\n' "$final_path"
}
harness_output_path() { che_output_path "$@"; }

# ---------------------------------------------------------------------------
# ATOMIC FILE WRITE
# ---------------------------------------------------------------------------
che_write_file_atomic() {
  local target="$1"
  [ -n "$target" ] || { echo "che_write_file_atomic: target path required" >&2; return 2; }
  local tmp_path="${target}.tmp.$$"
  local dir
  dir="$(dirname "$target")"
  mkdir -p "$dir"
  if [ -n "${WORKTREE_ROOT:-}" ]; then
    che_assert_outside_worktree "$target" "$WORKTREE_ROOT" "atomic_write: $target"
  fi
  cat > "$tmp_path"
  mv -f "$tmp_path" "$target"
  rm -f "$tmp_path" 2>/dev/null || true
  return 0
}
harness_write_file_atomic() { che_write_file_atomic "$@"; }

# ---------------------------------------------------------------------------
# LIMPEZA LEGACY ARTIFACTS DENTRO DA WORKTREE (BIND TIME)
# ---------------------------------------------------------------------------
che_cleanup_legacy_artifacts_in_worktree() {
  local worktree_root="$1"
  local shared_outside="$2"

  [ -n "$worktree_root" ] || return 0
  [ -d "$worktree_root" ]   || return 0
  [ -n "$shared_outside" ]  || return 0

  che_assert_outside_worktree "$shared_outside" "$worktree_root" "cleanup_backup_target"
  local backup_dir="$shared_outside/legacy_binding_cleanup/$(date -u +"%Y%m%dT%H%M%SZ")"
  local total_found=0
  local -a found_list=()

  local -a patterns=(
    ".trae" ".che" "decisions.log.jsonl" "decisions.log.md" "decisions.log"
    "decision.log.jsonl" "decision.log.md" "decision.log"
    "task_graph.md" "task_graph.yaml" "manual_test_plan.md" "final_summary.md"
    "execution_batches.md" "batch_execution_report.md"
    "merge_audit.md" "merge_audit.jsonl"
    "scope-report.md" "scope-report.json"
    "scope_check_report.md" "scope_check_report.json"
    "gh_stack_plan.md" "task_envelope.md" "graphify-out"
    "che-review-report.md" "che-compliance-report.md"
    "harness-review-report.md" "harness-compliance-report.md"
    "flockr-review-report.md"
    "reports" "HCR-*.md" "HCR-*.json" "REVIEW-*.md" "REVIEW-*.json"
    "review-*.md" "review-*.json" "summary.md" "summary.json"
    "seo_report.md" "seo_report.json"
    "spec_*.md" "spec_*.yaml" "SPEC-*.md"
    "diff-context_*.md" "diff-context_*.json"
    "pr_comments" "pr-comments-*.md" "pr-comments-*.json"
    "qa_evidence" "qa-evidence" "screenshots"
    "*.qa-report.md"
    "scope-check_*.md" "scope-check_*.json"
    "*.adr.md" "ADR-*.md"
  )

  local -a find_args=()
  local p
  for p in "${patterns[@]}"; do find_args+=( -o -name "$p" ); done
  unset 'find_args[0]'

  while IFS= read -r -d '' match; do
    total_found=$(( total_found + 1 ))
    found_list+=( "$match" )
  done < <(cd "$worktree_root" && find . \( "${find_args[@]}" \) -print0 2>/dev/null | sed -z 's@^\./@@' | while IFS= read -r -d '' x; do printf '%s\0' "$worktree_root/$x"; done)

  if [ "$total_found" -eq 0 ]; then
    return 0
  fi

  mkdir -p "$backup_dir"
  local rel target_dir target
  local -a report=()
  for match in "${found_list[@]}"; do
    rel="${match#$worktree_root/}"
    [ "$rel" = "$match" ] && continue
    target="$backup_dir/$rel"
    target_dir="$(dirname "$target")"
    mkdir -p "$target_dir"
    if mv -f "$match" "$target" 2>/dev/null; then
      report+=( "$rel -> backup $target" )
    else
      rm -rf "$match" 2>/dev/null || true
      report+=( "$rel (deleted fallback, mv failed)" )
    fi
  done

  {
    echo "🧹 che_cleanup_legacy_artifacts: movidos $total_found arquivos/diretórios LEGACY de dentro de $worktree_root."
    echo "   backup_dir = $backup_dir"
    local r
    for r in "${report[@]}"; do echo "    · $r"; done
  } >&2
}
harness_cleanup_legacy_artifacts_in_worktree() { che_cleanup_legacy_artifacts_in_worktree "$@"; }

# ---------------------------------------------------------------------------
# DECISIONS MD → JSONL MIGRATION HELPER
# ---------------------------------------------------------------------------
che_migrate_decisions_md_to_jsonl() {
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
    entries.append({"ts": ts, "event": event, "spec_id": None, "session_id": None,
                    "worktree_root": wt_root, "data": {"legacy_text": rest}, "_v": 1})
with open(out_path, "a", encoding="utf-8") as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
PYEOF
}
harness_migrate_decisions_md_to_jsonl() { che_migrate_decisions_md_to_jsonl "$@"; }

# ---------------------------------------------------------------------------
# CAVEAN-STYLE TOKEN REDUCTION WRAPPERS (5 heurísticas)
# Bypass total: CHE_FULL_OUTPUT=1
# ---------------------------------------------------------------------------
: "${CHE_TR_READ_MAX_LINES:=${HARNESS_TR_READ_MAX_LINES:-300}}"
: "${CHE_TR_STDOUT_MAX_CHARS:=${HARNESS_TR_STDOUT_MAX_CHARS:-4000}}"
: "${CHE_TR_DIFF_MAX_LINES:=${HARNESS_TR_DIFF_MAX_LINES:-500}}"
: "${CHE_TR_GREP_CONTEXT:=${HARNESS_TR_GREP_CONTEXT:-0}}"
: "${CHE_TR_COLLAPSE_BLANK:=${HARNESS_TR_COLLAPSE_BLANK:-1}}"
export CHE_TR_READ_MAX_LINES CHE_TR_STDOUT_MAX_CHARS CHE_TR_DIFF_MAX_LINES CHE_TR_GREP_CONTEXT CHE_TR_COLLAPSE_BLANK
# Legacy HARNESS_TR_* são alias (readonly refletem CHE)
export HARNESS_TR_READ_MAX_LINES="$CHE_TR_READ_MAX_LINES"
export HARNESS_TR_STDOUT_MAX_CHARS="$CHE_TR_STDOUT_MAX_CHARS"
export HARNESS_TR_DIFF_MAX_LINES="$CHE_TR_DIFF_MAX_LINES"
export HARNESS_TR_GREP_CONTEXT="$CHE_TR_GREP_CONTEXT"
export HARNESS_TR_COLLAPSE_BLANK="$CHE_TR_COLLAPSE_BLANK"

_che_full() { [ "${CHE_FULL_OUTPUT:-${HARNESS_FULL_OUTPUT:-}}" = "1" ]; }

che_tr_diff() {
  local tmp; tmp="$(cat || true)"
  if _che_full; then printf '%s\n' "$tmp"; return 0; fi
  local filtered
  set +o pipefail
  filtered="$(printf '%s\n' "$tmp" | grep -E '^[+-][^+-]' 2>/dev/null | head -n "$CHE_TR_DIFF_MAX_LINES" 2>/dev/null || true)"
  set -o pipefail || true
  if [ "$CHE_TR_COLLAPSE_BLANK" = "1" ]; then
    filtered="$(printf '%s\n' "$filtered" | awk 'NF {print; blank=0; next} !blank {print; blank=1}' || true)"
  fi
  local total_chars="${#filtered}"
  local msg=""
  if [ "$total_chars" -gt "$CHE_TR_STDOUT_MAX_CHARS" ]; then
    msg=$'\n[...TRUNCADO no CHAR '"$CHE_TR_STDOUT_MAX_CHARS"' de '"$total_chars"'; set CHE_FULL_OUTPUT=1 para saída completa]'
    filtered="${filtered:0:$CHE_TR_STDOUT_MAX_CHARS}"
  fi
  printf '%s%s\n' "$filtered" "$msg"
}
harness_tr_diff() { che_tr_diff "$@"; }

che_tr_read() {
  local total_lines="${1:-0}"
  local tmp; tmp="$(cat)"
  if _che_full; then printf '%s\n' "$tmp"; return 0; fi
  local actual_lines
  actual_lines="$(printf '%s\n' "$tmp" | wc -l)"
  if [ "$actual_lines" -gt "$CHE_TR_READ_MAX_LINES" ]; then
    local remaining=$(( actual_lines - CHE_TR_READ_MAX_LINES ))
    local headcap
    headcap="$(printf '%s\n' "$tmp" | head -n "$CHE_TR_READ_MAX_LINES")"
    printf '%s\n[...TRUNCADO lines %s-%s (restam %s linhas); use Read tool offsets ou CHE_FULL_OUTPUT=1]\n' \
      "$headcap" "$(( CHE_TR_READ_MAX_LINES + 1 ))" "$actual_lines" "$remaining"
  else
    printf '%s\n' "$tmp"
  fi
}
harness_tr_read() { che_tr_read "$@"; }

che_tr_collapse_blank() {
  local tmp; tmp="$(cat)"
  if _che_full || [ "$CHE_TR_COLLAPSE_BLANK" != "1" ]; then printf '%s\n' "$tmp"; return 0; fi
  printf '%s\n' "$tmp" | sed 's/[[:space:]]*$//' | awk 'NF {print; blank=0; next} !blank {print; blank=1}'
}
harness_tr_collapse_blank() { che_tr_collapse_blank "$@"; }

che_tr_stdout() {
  local tmp; tmp="$(cat)"
  if _che_full; then printf '%s\n' "$tmp"; return 0; fi
  local total="${#tmp}"
  if [ "$total" -le "$CHE_TR_STDOUT_MAX_CHARS" ]; then printf '%s\n' "$tmp"; return 0; fi
  local cap=$CHE_TR_STDOUT_MAX_CHARS
  printf '%s\n[...TRUNCADO no CHAR %s de %s; CHE_FULL_OUTPUT=1]\n' "${tmp:0:$cap}" "$cap" "$total"
}
harness_tr_stdout() { che_tr_stdout "$@"; }

che_tr_grep() {
  local pattern="$1" path="$2" type_filter="${3:-}"
  shift 3 || true
  if _che_full; then
    local grep_args=("-nH" "--" "$pattern")
    [ -n "$type_filter" ] && grep_args=("--include=*.$type_filter" "${grep_args[@]}")
    grep "${grep_args[@]}" "$path" 2>/dev/null || true
    return 0
  fi
  local ctx="$CHE_TR_GREP_CONTEXT"
  local grep_args=("-nH")
  [ "$ctx" -gt 0 ] && grep_args+=("-C" "$ctx")
  [ -n "$type_filter" ] && grep_args+=("--include=*.$type_filter")
  grep_args+=("--" "$pattern")
  set +o pipefail
  ( grep "${grep_args[@]}" "$path" 2>/dev/null || true ) | ( che_tr_collapse_blank || true ) | ( che_tr_stdout || true )
  set -o pipefail || true
}
harness_tr_grep() { che_tr_grep "$@"; }

# ---------------------------------------------------------------------------
# LEVEL 1 BINDING REGISTRY (GLOBAL INDEX · append-only JSONL)
# ---------------------------------------------------------------------------
che_registry_path() { echo "$CHE_HOME/bindings/registry.jsonl"; }
harness_registry_path() { che_registry_path "$@"; }

che_registry_append_jsonl() {
  local session_id="$1" status="$2" worktree_root="$3"
  local payload_json="${4:-{\}}" ts_override="${5:-}"
  [ -n "$session_id" ]   || { echo "che_registry_append_jsonl: session_id empty" >&2; return 2; }
  [ -n "$status" ]       || { echo "che_registry_append_jsonl: status empty" >&2; return 2; }
  [ -n "$worktree_root" ] || { echo "che_registry_append_jsonl: worktree_root empty" >&2; return 2; }

  if [ "$status" = "BOUND" ]; then
    local wt_shared="${CHE_WORKSPACE_SHARED:-${HARNESS_WORKSPACE_SHARED:-}}"
    if [ -z "$wt_shared" ] || [ "$wt_shared" = "/" ]; then
      local tmp_hwn tmp_sl
      tmp_hwn="$(che_resolve_workspace_name "$PWD")"
      tmp_sl="$(che_resolve_worktree_slug "$worktree_root")"
      wt_shared="${CHE_WORKSPACES_ROOT:-$HOME/.che-workspaces}/$tmp_hwn/$tmp_sl/.wt"
    fi
    che_assert_outside_worktree "$wt_shared" "$worktree_root" "wt_shared cleanup root"
    mkdir -p "$wt_shared"
    che_cleanup_legacy_artifacts_in_worktree "$worktree_root" "$wt_shared"
  fi

  local out_path; out_path="$(che_registry_path)"
  mkdir -p "$(dirname "$out_path")"
  local ts_iso
  if [ -n "$ts_override" ]; then ts_iso="$ts_override"
  else ts_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"; fi

  python3 - "$out_path" "$ts_iso" "$session_id" "$status" "$worktree_root" "$payload_json" <<'PYEOF'
import json, sys, os
out_path, ts, sid, status, wt_root, payload_s = sys.argv[1:7]
try: payload = json.loads(payload_s)
except Exception: payload = {"raw": payload_s}
if not isinstance(payload, dict): payload = {"value": payload}

legacy_pt_check = payload.pop("LANG_PT_CHECK", None)
incoming_flags = payload.pop("flags", None) or {}
if legacy_pt_check is None:
    legacy_pt_check = incoming_flags.pop("LANG_PT_CHECK", None)
flags = {
    "LANG_CODE":   incoming_flags.pop("LANG_CODE",   "en"),
    "LANG_DOCS":   incoming_flags.pop("LANG_DOCS",
                ("pt-BR" if legacy_pt_check == "DISABLED" else "en")),
    "LANG_CHAT":   incoming_flags.pop("LANG_CHAT",   "pt-BR"),
    "LANG_REPORT": incoming_flags.pop("LANG_REPORT", "en"),
}
for k, v in incoming_flags.items():
    if k not in flags: flags[k] = v
if legacy_pt_check is not None: flags["LANG_PT_CHECK"] = legacy_pt_check

entry = {
    "ts": ts,
    "event": payload.pop("event", (
        "BIND_FLAGS_UPDATE" if status == "FLAGS" else
        "BIND_UNBOUND"    if status == "UNBOUND" else "BIND_APPEND")),
    "session_id": sid,
    "status": status,
    "worktree_root": wt_root,
    "workspace_name": payload.pop("workspace_name", None),
    "worktree_slug":  payload.pop("worktree_slug", None),
    "branch":         payload.pop("branch", None),
    "friendly_name":  payload.pop("friendly_name", None),
    "che_session_dir":      payload.pop("che_session_dir", payload.pop("harness_session_dir", None)),
    "che_workspace_shared": payload.pop("che_workspace_shared", payload.pop("harness_workspace_shared", None)),
    "workspace_file": payload.pop("workspace_file", None),
    "reason":         payload.pop("reason", None),
    "flags": flags,
    "data": payload,
    "_v": 2
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
harness_registry_append_jsonl() { che_registry_append_jsonl "$@"; }

che_registry_lookup_last() {
  local session_id="${1:-$(che_current_session_id)}"
  [ -n "$session_id" ] || { echo "che_registry_lookup_last: session_id empty" >&2; return 2; }
  local out_path; out_path="$(che_registry_path)"
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
        if e.get("session_id") == sid: last = e
if last is None: sys.exit(1)
print(json.dumps(last, ensure_ascii=False, indent=2))
PY
}
harness_registry_lookup_last() { che_registry_lookup_last "$@"; }

che_registry_migrate_md_to_jsonl() {
  local old_md="$1" new_jsonl="$2"
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
    if not raw.strip() or raw.strip() == "---": continue
    m = header_re.match(raw)
    if not m: continue
    ts = m.group("ts").strip()
    tag = (m.group("tag") or "").strip()
    rest = m.group("rest").strip()
    kv = parse_kv(" " + rest + " ")
    sid = kv.get("SESSION_ID"); status = kv.get("STATUS", "BOUND")
    wt_root = kv.get("WORKTREE_ROOT", "")
    if not sid or not wt_root: continue
    payload = {
        "workspace_name": kv.get("WORKSPACE_NAME"),
        "worktree_slug":  kv.get("WORKTREE_SLUG"),
        "branch":         kv.get("BRANCH"),
        "friendly_name":  kv.get("FRIENDLY_NAME"),
        "che_session_dir":      kv.get("CHE_SESSION_DIR", kv.get("HARNESS_SESSION_DIR")),
        "che_workspace_shared": kv.get("CHE_WORKSPACE_SHARED", kv.get("HARNESS_WORKSPACE_SHARED")),
        "workspace_file": kv.get("WORKSPACE_FILE"),
        "reason":         kv.get("REASON"),
        "event_from_tag": tag or None,
    }
    entries.append({
        "ts": ts if ts.endswith("Z") or "+" in ts else ts + "Z",
        "event": (tag.replace("BIND-BOOTSTRAP","BIND_BOOTSTRAP").replace(" ","_").replace("-","_") if "BIND" in tag else "BIND_APPEND") if tag else "BIND_APPEND",
        "session_id": sid, "status": status, "worktree_root": wt_root,
        "workspace_name": payload["workspace_name"],
        "worktree_slug":  payload["worktree_slug"],
        "branch":         payload["branch"],
        "friendly_name":  payload["friendly_name"],
        "che_session_dir":      payload["che_session_dir"],
        "che_workspace_shared": payload["che_workspace_shared"],
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
harness_registry_migrate_md_to_jsonl() { che_registry_migrate_md_to_jsonl "$@"; }

# ---------------------------------------------------------------------------
# DIRECT RUN · SELF-TEST SMOKE
# ---------------------------------------------------------------------------
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  echo "== che_sessions_contract.sh self-test smoke (compat legacy harness alias inclusos) =="
  echo "CHE_WORKSPACES_ROOT = $CHE_WORKSPACES_ROOT   (HARNESS alias = $HARNESS_SESSIONS_ROOT)"
  echo "CHE_HOME = $CHE_HOME   CHE_HOST_IDE = $CHE_HOST_IDE"
  echo "resolve_workspace_name($PWD) = $(che_resolve_workspace_name "$PWD")"
  echo
  echo "== Runtime-neutral session smoke =="

  unset CHE_SESSION_ID HARNESS_SESSION_ID SESSION_ID
  [ "$(che_current_session_id)" = "" ] || { echo "SESSION empty fallback = FAIL"; exit 1; }
  export SESSION_ID="sess-trae-smoke"
  [ "$(che_current_session_id)" = "sess-trae-smoke" ]    || { echo "SESSION_ID Trae fallback = FAIL"; exit 1; }
  [ "$(harness_current_session_id)" = "sess-trae-smoke" ] || { echo "HARNESS alias session id = FAIL"; exit 1; }
  echo "SESSION_ID Trae fallback + alias legacy = PASS"

  export HARNESS_SESSION_ID="sess-harness-alias-precedence-should-NOT-win"
  export CHE_SESSION_ID="sess-che-smoke"
  [ "$(che_current_session_id)" = "sess-che-smoke" ] || { echo "CHE_SESSION_ID highest precedence = FAIL"; exit 1; }
  echo "CHE_SESSION_ID precedence > HARNESS_* > SESSION_ID = PASS"
  unset CHE_SESSION_ID HARNESS_SESSION_ID
  export SESSION_ID="sess-smoke"

  # Slug smoke
  testdir="$(mktemp -d)"
  trap 'rm -rf "$testdir"' EXIT
  (cd "$testdir" && git init -q -b feat/FOO-123--Hello && echo "slug($testdir) = $(che_resolve_worktree_slug "$testdir")")

  # Decisions smoke
  DEC_TEST_DIR="$(mktemp -d)"
  WORKTREE_TEST="$DEC_TEST_DIR/wt"
  mkdir -p "$WORKTREE_TEST"
  export SPEC_ID="SPEC-SMOKE-1"
  export SESSION_ID="sess-smoke"
  che_append_decision_jsonl "$WORKTREE_TEST" "TEST_EVENT" '{"key":"value","approver":"user"}'
  DEC_PATH="$(che_decisions_path "$WORKTREE_TEST")"
  echo "decisions_path = $DEC_PATH"
  python3 -c "import json; [json.loads(l) for l in open('$DEC_PATH')]; print('decisions JSONL parse = PASS')"
  rm -rf "$DEC_TEST_DIR"

  echo
  echo "== Registry smoke (JSONL global) =="
  REG_TMPDIR=$(mktemp -d)
  REG_TMP="$REG_TMPDIR/registry_test.jsonl"
  printf '[2026-08-27T02:19:04-03:00] SESSION_ID=sess-test-1 STATUS=BOUND WORKTREE_ROOT=/tmp/wt1 BRANCH=feat/x REASON=test1\n' > "$REG_TMPDIR/reg.md"
  printf '[2026-08-30T19:03:15Z] [BIND-BOOTSTRAP standalone] SESSION_ID=sess-test-2 STATUS=BOUND WORKSPACE_NAME=Flockr WORKTREE_SLUG=Lumos__test WORKTREE_ROOT=/tmp/wt2 FRIENDLY_NAME=teste2 CHE_SESSION_DIR=/tmp/sess2 CHE_WORKSPACE_SHARED=/tmp/ws2 WORKSPACE_FILE=/tmp/Flockr.code-workspace\n' >> "$REG_TMPDIR/reg.md"
  che_registry_migrate_md_to_jsonl "$REG_TMPDIR/reg.md" "$REG_TMP"
  N=$(wc -l < "$REG_TMP")
  echo "Migrated $N entries md → jsonl"
  python3 -c "
import json
with open('$REG_TMP') as f: lines = f.readlines()
for i, ln in enumerate(lines):
    e = json.loads(ln)
    print(f'  entry{i}: ts={e[\"ts\"]} sid={e[\"session_id\"]} status={e[\"status\"]} wt={e[\"worktree_root\"]} friendly={e.get(\"friendly_name\")}')
print('REGISTRY parse ALL OK')
"
  che_registry_append_jsonl "sess-smoke-reg-$$" "BOUND" "/tmp/test-wt" '{"workspace_name":"Flockr","friendly_name":"smoketest"}'
  che_registry_lookup_last "sess-smoke-reg-$$" | head -3
  REAL_REG=$(che_registry_path)
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
  echo "== Token reduction smoke (defaults CHE_TR · alias HARNESS_TR refletem mesmo valor) =="
  printf 'a\n\n\nb\n  \nc\n\n\n' | che_tr_collapse_blank | cat -A
  python3 -c "print('x'*5000)" | che_tr_stdout | wc -c
  python3 -c "[print(f'line{i}') for i in range(400)]" | che_tr_read 400 | wc -l
  echo
  echo "== self-test ALL PASSED =="
fi

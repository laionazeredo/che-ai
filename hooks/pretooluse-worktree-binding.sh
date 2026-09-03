#!/usr/bin/env bash
# Hook 1 (GLOBAL OBRIGATÓRIO §19): PreToolUse — Worktree Session Binding Guard
# 2-LEVEL LAYOUT:
#   Level 1 = GLOBAL INDEX (AUTHORITY): $HOME/.trae/bindings/registry.jsonl
#     entry per SESSION_ID. Resolves chicken-and-egg: lookup WORKTREE_ROOT from SESSION_ID
#     WITHOUT knowing worktree first. 1 session = 1 BOUND entry active (last STATUS=BOUND wins)
#     NÃO use Edit/Write direto. Sempre source che_sessions_contract.sh + che_registry_append_jsonl.
#   Level 2 = PER-SESSION DETAIL (FORA WORKTREE USER — NUNCA commitado):
#     $CHE_SESSION_DIR/binding.md (resolvido via che_sessions_contract.sh).
#     Not used by this hook for scissor checks; only SM/Ship/Dev read level 2 for audit chain.
#
# This hook exits 2 (BLOCK) only when:
#   (a) SESSION_ID FOUND in Level1 registry AND target path outside BOUND WORKTREE_ROOT active STATUS=BOUND
#       AND target path is NOT inside $CHE_SESSIONS_ROOT (exceção paths gerados).
# Otherwise allow (allow unknown sessions proceed to binding-decision flow §19.2).
#
# Input  stdin JSON: {event, sessionId, toolName, toolArgs: {...}}
# Output stdout JSON: {decision allow/block + reason}
# Exit code 0=allow / 2=block

set -euo pipefail

CHE_ROOT="${CHE_HOME:-${HARNESS_HOME:-$HOME/.trae}}"
CONTRACTS_SH="$CHE_ROOT/contracts/che_sessions_contract.sh"
if [ -f "$CONTRACTS_SH" ]; then
  # shellcheck disable=SC1090
  source "$CONTRACTS_SH"
fi

INPUT_JSON="$(cat)"

TRAE_SESSION_ID=$(jq -r '.sessionId // empty' <<<"$INPUT_JSON" 2>/dev/null || echo "")
TOOL_NAME=$(jq -r '.toolName // ""' <<<"$INPUT_JSON" 2>/dev/null || echo "")

TOOLS_TO_GUARD="Read|Glob|Grep|Edit|Write|RunCommand|DeleteFile|LS|SearchCodebase"
if [[ ! "$TOOL_NAME" =~ ^($TOOLS_TO_GUARD)$ ]]; then
  echo '{"decision":"allow","reason":"Tool not in guarded list (Glob/Grep/Read/Edit/Write/RunCommand/DeleteFile/LS/SearchCodebase)"}'
  exit 0
fi

# --- CHE_SESSIONS_ROOT EXCEPTION (explicit, by design) ---
# Paths de dados gerados (plans, reports, qa, Level2 binding) são SEMPRE permitidos.
# Eles estão fora do código do usuário → não há risco cross-worktree de código.
CHE_SESSIONS_ROOT="${CHE_SESSIONS_ROOT:-${HARNESS_SESSIONS_ROOT:-$HOME/.che-workspaces}}"

extract_paths() {
  jq -r '[.toolArgs.file_path // empty,
         (.toolArgs.target_directories // [] | .[]),
         .toolArgs.path // empty,
         (.toolArgs.file_paths // [] | .[]),
         .toolArgs.cwd // empty,
         (.toolArgs.ignore // [] | .[])]
         | map(select(. != null and type == "string")) | .[]' 2>/dev/null <<<"$INPUT_JSON"
}

mapfile -t CANDIDATE_PATHS < <(extract_paths)

# Early allow: qualquer path candidato começa com CHE_SESSIONS_ROOT → permitido
for p in "${CANDIDATE_PATHS[@]}"; do
  if [[ "$p" == "$CHE_SESSIONS_ROOT"/* ]]; then
    echo '{"decision":"allow","reason":"§19 EXCEÇÃO CHE_SESSIONS_ROOT: path alvo é pasta de dados gerados/efêmeros che (fora código usuário). Scissor bypassed by design."}'
    exit 0
  fi
done

# --- LEVEL 1 LOOKUP JSONL (chicken-and-egg solved: lookup by SESSION_ID) ---
REGISTRY_FILE=""
if declare -F che_registry_path >/dev/null 2>&1; then
  REGISTRY_FILE="$(che_registry_path)"
fi
BOUND_ROOT=""
if [ -n "$TRAE_SESSION_ID" ] && [ -f "$REGISTRY_FILE" ] && command -v python3 >/dev/null 2>&1; then
  PY_SCRIPT='import json,sys
p, sid = sys.argv[1:3]
last = None
with open(p) as f:
    for ln in f:
        ln = ln.strip()
        if not ln: continue
        try: e = json.loads(ln)
        except Exception: continue
        if e.get("session_id") == sid and e.get("status") == "BOUND":
            last = e
if last is None:
    sys.exit(1)
print(last.get("worktree_root") or "")'
  BOUND_ROOT=$(python3 -c "$PY_SCRIPT" "$REGISTRY_FILE" "$TRAE_SESSION_ID" 2>/dev/null) || true
fi

if [ -z "$BOUND_ROOT" ]; then
  echo '{"decision":"allow","reason":"§19: Nenhuma entrada BOUND para SESSION_ID no Level 1 registry.jsonl (ainda não houve binding decision nesta sessão). Prossiga para §19.2 binding decision flow. Scissor check permitido."}'
  exit 0
fi

git_worktree_root_for_path() {
  local candidate="$1"
  local probe="$candidate"

  [ -n "$probe" ] || return 1
  if [ -f "$probe" ]; then
    probe="$(dirname "$probe")"
  fi
  while [ ! -d "$probe" ]; do
    local parent
    parent="$(dirname "$probe")"
    [ "$parent" != "$probe" ] || return 1
    probe="$parent"
  done

  git -C "$probe" rev-parse --show-toplevel 2>/dev/null
}

BOUND_NORMALIZED="$(git_worktree_root_for_path "$BOUND_ROOT" || true)"
[ -n "$BOUND_NORMALIZED" ] || BOUND_NORMALIZED="${BOUND_ROOT%/}"

VIOLATIONS=()
PROJECT_PATHS=0
SESSION_ARTIFACT_PATHS=0
for p in "${CANDIDATE_PATHS[@]}"; do
  if [ "$p" = "$CHE_SESSIONS_ROOT" ] || [[ "$p" == "$CHE_SESSIONS_ROOT"/* ]]; then
    SESSION_ARTIFACT_PATHS=$((SESSION_ARTIFACT_PATHS + 1))
    continue
  fi

  project_root="$(git_worktree_root_for_path "$p" || true)"
  if [ -z "$project_root" ]; then
    continue
  fi

  PROJECT_PATHS=$((PROJECT_PATHS + 1))
  if [ "${project_root%/}" != "$BOUND_NORMALIZED" ]; then
    VIOLATIONS+=("${project_root%/}")
  fi
done

if [ ${#VIOLATIONS[@]} -gt 0 ]; then
  UNIQ=$(printf "%s\n" "${VIOLATIONS[@]}" | sort -u | paste -sd "," -)
  REASON_BLOCK="§19 WORKTREE SESSION BINDING VIOLATION (Level 1 Registry). sessionId=$TRAE_SESSION_ID is BOUND in Level 1 registry ($REGISTRY_FILE) to WORKTREE_ROOT=$BOUND_NORMALIZED. Tool=$TOOL_NAME tentou acessar paths FORA worktree vinculada: $UNIQ. Action: (1) cancelar; (2) AskUserQuestion re-bind explícito (old entry STATUS=RELEASED + new BOUND append registry); (3) confirmação one-off opção A."
  jq -nc --arg r "$REASON_BLOCK" '{decision:"block", reason: $r}'
  exit 2
fi

REASON_ALLOW="§19 OK Level 1 Registry: all detected project paths match BOUND_WORKTREE_ROOT=$BOUND_NORMALIZED (project_paths=$PROJECT_PATHS session_artifact_paths=$SESSION_ARTIFACT_PATHS)"
jq -nc --arg r "$REASON_ALLOW" '{decision:"allow", reason: $r}'
exit 0

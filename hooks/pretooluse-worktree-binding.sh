#!/usr/bin/env bash
# Hook 1 (GLOBAL OBRIGATÓRIO §19): PreToolUse — Worktree Session Binding Guard
# 2-LEVEL LAYOUT:
#   Level 1 = GLOBAL INDEX (AUTHORITY): $HOME/.trae/bindings/registry.md
#     entry per SESSION_ID. Resolves chicken-and-egg: lookup WORKTREE_ROOT from SESSION_ID
#     WITHOUT knowing worktree first. 1 session = 1 BOUND entry active (last STATUS=BOUND wins)
#   Level 2 = PER-SESSION DETAIL (per-worktree inside worktree): not used by this hook for scissor checks;
#     only SM/Ship/Dev read level 2 for re-binding audit chain.
#
# This hook exits 2 (BLOCK) only when:
#   (a) SESSION_ID FOUND in Level1 registry AND target path outside BOUND WORKTREE_ROOT active STATUS=BOUND
# Otherwise allow (allow unknown sessions proceed to binding-decision flow §19.2.
#
# Input  stdin JSON: {event, sessionId, toolName, toolArgs: {...}}
# Output stdout JSON: {decision allow/block + reason}
# Exit code 0=allow / 2=block

set -euo pipefail

INPUT_JSON="$(cat)"

SESSION_ID=$(jq -r '.sessionId // empty' <<<"$INPUT_JSON" 2>/dev/null || echo "")
TOOL_NAME=$(jq -r '.toolName // ""' <<<"$INPUT_JSON" 2>/dev/null || echo "")

TOOLS_TO_GUARD="Read|Glob|Grep|Edit|Write|RunCommand|DeleteFile|LS|SearchCodebase"
if [[ ! "$TOOL_NAME" =~ ^($TOOLS_TO_GUARD)$ ]]; then
  echo '{"decision":"allow","reason":"Tool not in guarded list (Glob/Grep/Read/Edit/Write/RunCommand/DeleteFile/LS/SearchCodebase)"}'
  exit 0
fi

# --- LEVEL 1 LOOKUP (registry.md, chicken-and-egg solved: lookup by SESSION_ID ---
REGISTRY_FILE="$HOME/.trae/bindings/registry.md"
BOUND_ROOT=""
if [ -n "$SESSION_ID" ] && [ -f "$REGISTRY_FILE" ]; then
  # Split entries separated by '---' delimiters, find last entry matching this session with STATUS=BOUND
  SESSION_ENTRIES=$(awk -v RS='---' -v sid="SESSION_ID: $SESSION_ID" '$0 ~ sid {print $0}' "$REGISTRY_FILE" 2>/dev/null || true)
  if [ -n "$SESSION_ENTRIES" ]; then
    # SESSION_ENTRIES já contém SÓ blocos desta sessão (split RS='---' + filter SESSION_ID).
    # Ordem cronológica: primeira entrada = mais antiga, última = mais recente.
    # Pegar ÚLTIMA ocorrência de WORKTREE_ROOT (binding ativo mais novo).
    BOUND_ROOT=$(echo "$SESSION_ENTRIES" | grep -E '^WORKTREE_ROOT:' | tail -1 | cut -d: -f2- | tr -d '[:space:]' || true)
  fi
fi

if [ -z "$BOUND_ROOT" ]; then
  echo '{"decision":"allow","reason":"§19: Nenhuma entrada BOUND para SESSION_ID no Level 1 registry (ainda não houve binding decision nesta sessão). Prossiga para §19.2 binding decision flow. Scissor check permitido."}'
  exit 0
fi

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
WORKTREE_PREFIXES=()
for p in "${CANDIDATE_PATHS[@]}"; do
  if [[ "$p" == */Lumos || "$p" == */Lumos/* || "$p" == */Lumos.worktrees/* ]]; then
    prefix=$(sed -E 's|^(.*/Lumos\.worktrees/[^/]+)(/.*)?$|\1|; t; s|^(.*/Lumos)(/.*)?$|\1|' <<<"$p")
    WORKTREE_PREFIXES+=("$prefix")
  fi
done

if [ ${#WORKTREE_PREFIXES[@]} -eq 0 ]; then
  echo '{"decision":"allow","reason":"Nenhum path de worktree nos tool args (fora Lumos/Lumos.worktrees escopo). Scissor check allow."}'
  exit 0
fi

VIOLATIONS=()
BOUND_NORMALIZED="${BOUND_ROOT%/}"
for p in "${WORKTREE_PREFIXES[@]}"; do
  normalized="${p%/}"
  if [ "$normalized" != "$BOUND_NORMALIZED" ]; then
    VIOLATIONS+=("$normalized")
  fi
done

if [ ${#VIOLATIONS[@]} -gt 0 ]; then
  UNIQ=$(printf "%s\n" "${VIOLATIONS[@]}" | sort -u | paste -sd "," -)
  REASON_BLOCK="§19 WORKTREE SESSION BINDING VIOLATION (Level 1 Registry). sessionId=$SESSION_ID is BOUND in Level 1 registry ($REGISTRY_FILE) to WORKTREE_ROOT=$BOUND_NORMALIZED. Tool=$TOOL_NAME tentou acessar paths FORA worktree vinculada: $UNIQ. Action: (1) cancelar; (2) AskUserQuestion re-bind explícito (old entry STATUS=RELEASED + new BOUND append registry); (3) confirmação one-off opção A."
  jq -nc --arg r "$REASON_BLOCK" '{decision:"block", reason: $r}'
  exit 2
fi

REASON_ALLOW="§19 OK Level 1 Registry: tool args worktree paths match BOUND_WORKTREE_ROOT=$BOUND_NORMALIZED"
jq -nc --arg r "$REASON_ALLOW" '{decision:"allow", reason: $r}'
exit 0

#!/usr/bin/env bash
# Hook 2 (GLOBAL OBRIGATÓRIO): PostToolUse — 3-Layer Non-Duplication Guard
# Rodando APÓS Edit/Write em user_rules/*.md (Layer 1) ou HARNESS_RULES.md (Layer 2).
# Garante HARD STOP: "nenhum corpo de regra >=4 linhas aparece em >1 camada."
# Layer 3 skills/*/SKILL.md é DONO do corpo. Layer 1/2 = só title + link + curto gate.
#
# Input  (stdin JSON):  {event:"PostToolUse", toolName:"Edit|Write", toolArgs:{file_path,new_string?,content?}, toolOutput:{...}, sessionId:"..."}
# Output (stdout JSON): {decision:"allow", additionalContext:"... warning"} (PostToolUse não block, mas avisa)
# Exit code: sempre 0 (allow), com warnings em additionalContext se detectar duplicação.
# Não bloqueia pós-fato, mas injeta contexto CLARE WARNING pro agente não repetir.

set -euo pipefail

HARNESS_ROOT="${HARNESS_HOME:-$HOME/.trae}"
CONTRACTS_SH="$HARNESS_ROOT/contracts/harness_sessions_contract.sh"
if [ -f "$CONTRACTS_SH" ]; then
  # shellcheck disable=SC1090
  source "$CONTRACTS_SH"
fi
HARNESS_HOME="${HARNESS_HOME:-$HARNESS_ROOT}"
TRAE_ROOT="$HARNESS_HOME"
SKILLS_DIR="$HARNESS_HOME/skills"

INPUT_JSON="$(cat)"
TOOL_NAME=$(jq -r '.toolName // ""' <<<"$INPUT_JSON" 2>/dev/null || echo "")
FILE_PATH=$(jq -r '.toolArgs.file_path // ""' <<<"$INPUT_JSON" 2>/dev/null || echo "")

if [[ ! "$TOOL_NAME" =~ ^(Edit|Write)$ ]]; then
  echo '{"decision":"allow"}'
  exit 0
fi

FILENAME=$(basename "$FILE_PATH")
DIRNAME=$(dirname "$FILE_PATH")

# Só ativar se for Layer 1 (user_rules/*.md) ou Layer 2 (HARNESS_RULES.md / HARNESS_COMMANDS.md)
IS_LAYER1=false
IS_LAYER2=false
case "$DIRNAME" in
  *"/user_rules") [[ "$FILENAME" == *.md ]] && IS_LAYER1=true ;;
esac
case "$FILENAME" in
  HARNESS_RULES.md|HARNESS_COMMANDS.md) [[ "$DIRNAME" == "$TRAE_ROOT" ]] && IS_LAYER2=true ;;
esac

if [ "$IS_LAYER1" = "false" ] && [ "$IS_LAYER2" = "false" ]; then
  echo '{"decision":"allow"}'
  exit 0
fi

NEW_CONTENT=""
if [ -f "$FILE_PATH" ]; then
  NEW_CONTENT="$(cat "$FILE_PATH")"
else
  NEW_CONTENT=$(jq -r '.toolArgs.content // ""' <<<"$INPUT_JSON" 2>/dev/null || echo "")
fi

if [ -z "$NEW_CONTENT" ]; then
  echo '{"decision":"allow"}'
  exit 0
fi

TMP_NEW=$(mktemp)
TMP_FILTERED_NEW=$(mktemp)
trap 'rm -f "$TMP_NEW" "$TMP_FILTERED_NEW"' EXIT

printf "%s\n" "$NEW_CONTENT" > "$TMP_NEW"

# Filtrar: remover heading lines #, links isolados, linhas vazias, table dividers ---
grep -v '^[[:space:]]*$' "$TMP_NEW" \
  | grep -v '^[[:space:]]*#\{1,6\}[[:space:]]' \
  | grep -v '^[[:space:]]*[-|]{3,}[[:space:]]*$' \
  | grep -v 'file:///' \
  | grep -vE '^[[:space:]]*\|[[:space:]]*---' > "$TMP_FILTERED_NEW" || true

if [ ! -s "$TMP_FILTERED_NEW" ]; then
  echo '{"decision":"allow"}'
  exit 0
fi

# Checar cada linha do conteúdo novo (filtered) contra todos SKILL.md em Layer 3
DUP_HITS=$(grep -R -x -F -f "$TMP_FILTERED_NEW" "$SKILLS_DIR" --include="SKILL.md" 2>/dev/null || true)

if [ -z "$DUP_HITS" ]; then
  echo '{"decision":"allow"}'
  exit 0
fi

HIT_COUNT=$(echo "$DUP_HITS" | sed '/^$/d' | wc -l)
HIT_COUNT="${HIT_COUNT// /}"

if [ "$HIT_COUNT" -lt 4 ]; then
  echo '{"decision":"allow"}'
  exit 0
fi

TOP_HITS=$(echo "$DUP_HITS" | head -6 | jq -R -s 'split("\n") | map(select(. != ""))' 2>/dev/null || echo "[]")

CAMADA=""
[ "$IS_LAYER1" = "true" ] && CAMADA="Layer 1 (user_rules/$FILENAME)"
[ "$IS_LAYER2" = "true" ] && CAMADA="Layer 2 ($FILENAME)"

LAYER_DESCRIPTION="$CAMADA contém conteúdo que já existe em Layer 3 skills/*/SKILL.md."
ACTION_NEEDED="Arquitetura 3 camadas HARD STOP: Layer 3 é DONO do corpo de regra. Mova o corpo duplicado para a skill; deixe em $CAMADA APENAS título + link para SKILL.md. Duplicates >=4 linhas detectadas: $HIT_COUNT linhas idênticas já presentes em skills/"

WARNING_MSG="$LAYER_DESCRIPTION | $ACTION_NEEDED | Top hits: $TOP_HITS"

jq -n --arg ctx "$WARNING_MSG" '{"decision":"allow","additionalContext":$ctx}'

exit 0

#!/usr/bin/env bash
# Hook 3 (GLOBAL WARN-only): PostToolUse — Portuguese Text Detector in written code/content
# Behavior: NEVER blocks (exit code always 0, decision=allow or warn).
#   - Watches Edit/Write tool operations (file writes).
#   - Reads Level 1 registry ($HOME/.trae/bindings/registry.jsonl):
#       if SESSION_ID has flags.LANG_PT_CHECK == DISABLED -> SKIP entirely (allow, no warn).
#       NÃO use Edit/Write direto. Sempre source harness_sessions_contract.sh + harness_registry_append_jsonl.
#   - Otherwise: scans the WRITTEN file (toolArgs.file_path or cwd-written) for:
#       (a) 3+ PT-BR stopwords on same file (comment/string/MD content lines), OR
#       (b) combination of 2+ PT diacritics (ç ã õ é ê á à ó ô ú â î û ñ) with PT stopwords pattern
#   - If DETECTED -> decision="warn", adicionalContext=human-readable message listing path + sample lines,
#       instructing AGENT to AskUserQuestion: "Texto em português detectado. Traduzir para inglês? (A = Sim traduzir, B = Manter PT, C = Desabilitar checagem nesta sessão)"
#   - Never modifies the file (no auto-translate, no auto-fix). SIGNAL ONLY.
#
# Input stdin JSON: {event, sessionId, toolName, toolArgs: {...}}
# Output stdout JSON: {decision allow/warn, reason, adicionalContext?: string}
# Exit code 0 ALWAYS (never blocks; warn is a signal, not a failure).

set -euo pipefail

CONTRACTS_SH="${HOME}/.trae/contracts/harness_sessions_contract.sh"
if [ -f "$CONTRACTS_SH" ]; then
  # shellcheck disable=SC1090
  source "$CONTRACTS_SH"
fi

INPUT_JSON="$(cat)"

SESSION_ID=$(jq -r '.sessionId // empty' <<<"$INPUT_JSON" 2>/dev/null || echo "")
TOOL_NAME=$(jq -r '.toolName // ""' <<<"$INPUT_JSON" 2>/dev/null || echo "")

# Skip for non-write tools
TOOLS_TO_WATCH="Edit,Write"
if [[ ",$TOOLS_TO_WATCH," != *",$TOOL_NAME,"* ]]; then
  jq -nc '{decision:"allow", reason: "Hook3 lang-pt: tool not Edit/Write, skip."}'
  exit 0
fi

# Extract the target file path we just wrote
FILE_PATH=$(jq -r '.toolArgs.file_path // empty' <<<"$INPUT_JSON" 2>/dev/null || echo "")
if [ -z "$FILE_PATH" ]; then
  jq -nc '{decision:"allow", reason: "Hook3 lang-pt: no file_path in toolArgs, skip."}'
  exit 0
fi

# Step 1: Check session-level disable flag from Level 1 registry JSONL
REGISTRY_FILE="$HOME/.trae/bindings/registry.jsonl"
PT_CHECK_ENABLED=true
if [ -n "$SESSION_ID" ] && [ -f "$REGISTRY_FILE" ] && command -v python3 >/dev/null 2>&1; then
  PY_SCRIPT='import json,sys
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
    print("true"); sys.exit(0)
flags = last.get("flags") or {}
enabled = flags.get("LANG_PT_CHECK", "ENABLED") == "ENABLED"
print("true" if enabled else "false")'
  PT_CHECK_ENABLED=$(python3 -c "$PY_SCRIPT" "$REGISTRY_FILE" "$SESSION_ID" 2>/dev/null || echo true)
fi

if [ "$PT_CHECK_ENABLED" != "true" ]; then
  jq -nc --arg sess "$SESSION_ID" \
        '{decision:"allow", reason: ("Hook3 lang-pt: SKIP per session Level1 registry.jsonl flags.LANG_PT_CHECK=DISABLED for sessionId=" + $sess)}'
  exit 0
fi

# Step 2: If file not readable or not exist (shouldn't happen post Edit/Write), skip
if [ ! -r "$FILE_PATH" ]; then
  jq -nc '{decision:"allow", reason: "Hook3 lang-pt: target file not readable post-write, skip."}'
  exit 0
fi

# Step 3: Heuristic PT-BR detection KISS
# Dictionaries
PT_STOPWORDS=" não | sim | que | de | do | da | dos | das | para | com | sem | por | per | este | esta | estes | estas | esse | essa | esses | essas | nós | você | vocês | tem | têm | são | foi | fui | ser | estar | estou | é | e | ou | mas | porém | todavia | contudo | portanto | logo | já | até | mais | menos | muito | pouco | hoje | ontem | amanhã | trabalho | trabalhar | projeto | ticket | tarefa | sessão | usuário | arquivo | código | erro | sucesso | falha | mudança | alteração | implementação | verificação | validação | execução | criar | criado | remover | removido | adicionar | adicionado | atualizar | atualizado | corrigir | corrigido | testar | testado | aprovar | aprovado | rejeitar | rejeitado | problema | solução | resultado | esperado | obtido | função | método | classe | variável | parâmetro | retorno | entrada | saída "

# (a) Count PT stopword hits across the file (word boundaries, case-insensitive)
# NOTE: Keep PIPES | as ERE alternation separators (do NOT replace with commas — grep -E uses |)
PT_REGEX="$PT_STOPWORDS"
PT_HITS=$({ grep -oiE "$PT_REGEX" "$FILE_PATH" 2>/dev/null | wc -l; } | tr -d '[:space:]')
[ -z "$PT_HITS" ] && PT_HITS=0

# (b) Diacritic score (lines containing PT-only chars: ç ã õ plus any word that looks PT)
DIACRITIC_LINES=$({ grep -cE '[çãõÇÃÕáàâéêíóôúÁÀÂÉÊÍÓÔÚ]' "$FILE_PATH" 2>/dev/null || true; } | tr -d '[:space:]')
[ -z "$DIACRITIC_LINES" ] && DIACRITIC_LINES=0

# Threshold: 4+ stopword hits OR (2+ diacritic lines AND 2+ stopword hits)
PT_DETECTED=false
SAMPLE_LINES=""
if [ "$PT_HITS" -ge 4 ] || { [ "$DIACRITIC_LINES" -ge 2 ] && [ "$PT_HITS" -ge 2 ]; }; then
  PT_DETECTED=true
  # Grab up to 3 sample lines containing PT content (with line numbers)
  SAMPLE_LINES=$({ grep -niE "($PT_REGEX)|[çãõáàâéêíóôú]" "$FILE_PATH" 2>/dev/null || true; } | head -3 | sed 's/^/  L/' | tr '\n' '; ' | sed 's/; $//')
fi

if [ "$PT_DETECTED" = false ]; then
  jq -nc --arg path "$FILE_PATH" --arg hits "$PT_HITS" --arg dia "$DIACRITIC_LINES" \
        '{decision:"allow", reason: ("Hook3 lang-pt: OK no PT-BR content detected in " + $path + " (stopword_hits=" + ($hits|tonumber|tostring) + " diacritic_lines=" + ($dia|tonumber|tostring) + ")")}'
  exit 0
fi

# Step 4: WARN the agent (never block)
REASON="PT-BR text detected in written file (stopword_hits=$PT_HITS, diacritic_lines=$DIACRITIC_LINES). Signal only — NO auto-correction performed."
ADDL="ACTION REQUIRED by AGENT: AskUserQuestion to user BEFORE PROCEEDING further: Texto em português detectado no arquivo $FILE_PATH.
Padrão Flockr: código/docs/PR body em inglês por padrão. O que deseja fazer?
(A) Traduzir conteúdo detectado para inglês (recomendado)
(B) Manter em português (justificar e confirmar)
(C) Desabilitar checagem de PT NESTA SESSÃO (adiciona via helper `harness_registry_append_jsonl` com `"flags":{"LANG_PT_CHECK":"DISABLED"}` no Level 1 registry.jsonl + Level 2 detail file)
Sample lines: $SAMPLE_LINES
File analyzed: $FILE_PATH"

jq -nc --arg r "$REASON" --arg a "$ADDL" \
      '{decision:"warn", reason: $r, adicionalContext: $a}'
exit 0

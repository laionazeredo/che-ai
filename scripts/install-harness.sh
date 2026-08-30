#!/usr/bin/env bash
#
# install-harness.sh — Copia um harness Flockr (este .trae) para uma instalação nova.
#
# USO (dentro da pasta fonte .trae ou --source=/custom/.trae):
#   ./scripts/install-harness.sh                  # DRY-RUN padrão (mostra o que faria)
#   ./scripts/install-harness.sh --apply          # EXECUTA de verdade
#   ./scripts/install-harness.sh --target ~/.trae  # default = $HOME/.trae
#   ./scripts/install-harness.sh --source ~/Downloads/dot-trae-exportado --apply
#
# O que faz (whitelist):
#   - Copia commands/, contracts/, skills/, hooks/, scripts/, permission/ + arquivos raiz essenciais
#   - Cria bindings/ vazio com README se não existir (NÃO copia registry.jsonl existente no target)
#   - Faz backup automático de ~/.trae se já existir
#
# O que NÃO copia (blacklist user-specific):
#   - memory/, user_rules/, bindings/registry.jsonl
#   - node_modules/, pnpm-lock.yaml (exceto se forçado)

set -euo pipefail

APPLY=0
SOURCE=""
TARGET="${HOME}/.trae"

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --source)
      SOURCE="${2:-}"
      shift 2
      ;;
    --source=*)
      SOURCE="${1#--source=}"
      shift
      ;;
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --target=*)
      TARGET="${1#--target=}"
      shift
      ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERRO: opção desconhecida: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

# Resolve SOURCE: se vazio, assume pasta que contém este script, sobe um nível (dentro de .trae/scripts/).
if [ -z "$SOURCE" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  SOURCE="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

# Validações mínimas.
if [ ! -f "${SOURCE}/HARNESS_RULES.md" ]; then
  echo "ERRO: SOURCE não parece ser um diretório .trae válido (faltando HARNESS_RULES.md): ${SOURCE}" >&2
  echo "Tente: $0 --source=/caminho/para/.trae" >&2
  exit 2
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
MODE_LABEL="[dry-run]"
[ "$APPLY" -eq 1 ] && MODE_LABEL="[apply]"

echo "==> Install harness ${MODE_LABEL}"
echo "    Source: ${SOURCE}"
echo "    Target: ${TARGET}"

# Passo 1: backup se target já existir.
if [ -e "$TARGET" ]; then
  BKP="${TARGET}.bak-${TIMESTAMP}"
  echo "    Backup existing: ${BKP}"
  if [ "$APPLY" -eq 1 ]; then
    mv "$TARGET" "$BKP"
    echo "    ✔ Backup feito"
  else
    echo "    [dry-run] será feito"
  fi
fi

# Passo 2: cria estrutura básica vazia e o que precisa existir (deps se não existir.
ensure_dir() {
  local p="$1"
  if [ "$APPLY" -eq 1 ]; then
    mkdir -p "$p"
  fi
}

ensure_dir "$TARGET"
ensure_dir "${TARGET}/bindings"

WHITELIST_ROOT_FILES=(
  README.md
  HARNESS_RULES.md
  HARNESS_COMMANDS.md
  REFERENCE_USER_RULES_MINIFIED.md
  package.json
  pnpm-lock.yaml
  tsconfig.json
  hooks.json
)
WHITELIST_DIRS=(
  commands
  contracts
  skills
  hooks
  scripts
  permission
)

# Passo 3: copia whitelist (arquivos raiz.
for f in "${WHITELIST_ROOT_FILES[@]}"; do
  SRC="${SOURCE}/${f}"
  DST="${TARGET}/${f}"
  if [ -e "$SRC" ]; then
    echo "    cp root: $f"
    if [ "$APPLY" -eq 1 ]; then
      cp -R "$SRC" "$DST"
    fi
  fi
done

# Passo 4: copia whitelist diretórios (exceto skills/_shared_checklists se existir segredo user não).
for d in "${WHITELIST_DIRS[@]}"; do
  SRC="${SOURCE}/${d}"
  DST="${TARGET}/${d}"
  if [ -d "$SRC" ]; then
    echo "    cp dir : $d/"
    if [ "$APPLY" -eq 1 ]; then
      cp -R "$SRC" "$DST"
    fi
  fi
done

# Passo 5: BLACKLIST remove/garante que registry.jsonl USER existente é preservado (não copiamos da source;
# também garantimos bindings/README explicativo se não existir nenhum.
BINDINGS_README="${TARGET}/bindings/README.md"
if [ "$APPLY" -eq 1 ] && [ ! -f "$BINDINGS_README" ]; then
  cat > "$BINDINGS_README" <<'EOF'
Nível 1 — registry.jsonl.
NÃO editar manualmente. Escritor único = contracts helper `harness_registry_append_jsonl`.
EOF
fi

# Passo 6: rodar pnpm install se tiver package.json (instala tsx/typescript dependencies).
if [ -f "${TARGET}/package.json" ]; then
  echo "    pnpm install target..."
  if [ "$APPLY" -eq 1 ]; then
    (cd "$TARGET" && (corepack enable >/dev/null 2>&1 || true) && corepack pnpm install --prefer-offline 2>&1 | tail -5)
  fi
fi

# Passo 7: criar user_rules e memory (nunca copiamos da source;
# apenas garantimos vazios ou avisamos se não existem.
for d in user_rules memory; do
  FULL="${TARGET}/${d}"
  if [ ! -d "$FULL" ] && [ "$APPLY" -eq 1 ]; then
    mkdir -p "$FULL"
  fi
done

echo ""
echo "=== INSTALL ${MODE_LABEL} concluído."
if [ "$APPLY" -eq 0 ]; then
  echo "⚠ dry-run. Para aplicar: $0 --apply"
else
  echo "✔ target pronto em $TARGET"
  echo ""
  echo " Checklist pós-instalação:"
  echo "  1. Abrir Trae de novo (ou recarregar)."
  echo "  2. Confirmar ~/.trae/README.md existe."
  echo "  3. Smoke rápido: bash $TARGET/scripts/install-harness.sh -h"
  echo "  4. Decisions CLI: corepack pnpm --dir $TARGET decisions --help 2>&1 | head"
fi

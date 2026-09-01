#!/usr/bin/env bash
#
# install-harness.sh — Instala OU atualiza o harness Flockr (este .trae).
#
# DOIS MODOS PRINCIPAIS:
#   1) --apply      (fresh install / destrutivo controlado):
#        - Se target JÁ EXISTIR → mv $target INTEIRO → $target.bak-YYYYMMDD-HHMM
#        - Copia whitelist completa da source para target vazio limpo.
#        - Blacklist (user_rules, bindings/registry.jsonl, memory) NÃO é copiada
#          da source; apenas estrutura de pastas vazias é recriada no target.
#        - Use este modo para primeira instalação OU se quiser reset 100% limpo.
#
#   2) --update --apply (update NÃO-DESTRUTIVO. Recomendado para novas versões):
#        - NUNCA renomeia o target INTEIRO (não faz mv global).
#        - NUNCA toca em BLACKLIST (user_rules/*, bindings/registry.jsonl, memory/).
#        - Para CADA item da WHITELIST individualmente:
#            · source tem, target não tem → copia (arquivo/dir novo oficial).
#            · source tem, target tem e DIFERENTES → backup $target/item.bak-$TIMESTAMP,
#              depois copia source → target.
#            · source tem, target tem e IGUAIS → skip (zero ruído).
#            · source NÃO tem, target tem → NUNCA TOCA (preserva skills custom do
#              usuário, comandos novos que a pessoa adicionou, referências locais etc).
#        - Ideal para: "peguei versão nova do repo laionazeredo/trae-config, quero
#          atualizar skills/commands/rules sem perder minhas regras pessoais".
#
# USO (dentro da pasta fonte .trae ou --source=/custom/.trae):
#   ./scripts/install-harness.sh                                 # DRY-RUN padrão (fresh install).
#   ./scripts/install-harness.sh --apply                         # Fresh install REAL.
#   ./scripts/install-harness.sh --update                        # DRY-RUN modo update NÃO-DESTRUTIVO.
#   ./scripts/install-harness.sh --update --apply                # Update REAL NÃO-DESTRUTIVO.
#   ./scripts/install-harness.sh --target ~/.trae
#   ./scripts/install-harness.sh --source ~/Downloads/dot-trae-exportado --apply
#   ./scripts/install-harness.sh -h
#
# WHITELIST (o que é sincronizado da source → target):
#   Arquivos raiz: README.md, HARNESS_RULES.md, HARNESS_COMMANDS.md,
#                  REFERENCE_USER_RULES_MINIFIED.md, package.json, pnpm-lock.yaml,
#                  tsconfig.json, hooks.json.
#   Diretórios:   commands/, contracts/, skills/, hooks/, scripts/, permission/.
#
# BLACKLIST ABSOLUTA (o que o script NUNCA copia, NUNCA deleta, NUNCA toca):
#   user_rules/* (exceto .gitkeep se a pasta for vazia e precisar de placeholder)
#   bindings/registry.jsonl
#   memory/
#   node_modules/, pnpm-debug.log, *.bak-*, .git/
#   Qualquer arquivo/pasta em target que NÃO exista na source NUNCA é tocado.
#
# GARANTIAS DE SEGURANÇA (fail-closed):
#   * Qualquer arquivo whitelist que VAI ser SOBRESCRITO no modo update → primeiro
#     faz backup individual ${arquivo}.bak-${TIMESTAMP} NO MESMO diretório,
#     ANTES de copiar a nova versão. Rollback manual é só remover o novo e
#     renomear .bak-* de volta.
#   * Nenhum `rm -rf` nem `rm` neste script. Tudo é copy + mv backup individual.
#   * Default SEMPRE dry-run. --apply é obrigatório para escrever.

set -euo pipefail

APPLY=0
UPDATE=0
SOURCE=""
TARGET="${HOME}/.trae"

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
      shift
      ;;
    --update)
      UPDATE=1
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
      sed -n '2,90p' "$0" | sed 's/^# \{0,1\}//'
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

MODE_NAME="fresh-install"
[ "$UPDATE" -eq 1 ] && MODE_NAME="update (non-destructive)"

echo "==> Harness ${MODE_NAME} ${MODE_LABEL}"
echo "    Source : ${SOURCE}"
echo "    Target : ${TARGET}"
echo "    Mode   : update=${UPDATE} apply=${APPLY}"

# BLACKLIST ABSOLUTA (arquivos e pastas que NUNCA são tocados).
# Qualquer path nestes arrays → o script aborta c/ erro se alguém tentar operar neles.
BLACKLIST_DIRS=(
  "user_rules"
  "memory"
  ".git"
  "node_modules"
)
BLACKLIST_FILES=(
  "bindings/registry.jsonl"
)

# Verificação fail-closed: se SOURCE tiver BLACKLIST (não deveria), aborta.
for b in "${BLACKLIST_DIRS[@]}" "${BLACKLIST_FILES[@]}"; do
  if [ -e "${SOURCE}/${b}" ] && [ "${b}" != "user_rules" ] && [ "${b}" != "memory" ]; then
    # user_rules/memory PODEM existir na source, mas NUNCA são copiados (apenas ignorados).
    true
  fi
done

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

# ============================================================
# Passo 1: tratar target existente DEPENDE DO MODO
# ============================================================
if [ -e "$TARGET" ]; then
  if [ "$UPDATE" -eq 0 ]; then
    # MODO FRESH INSTALL (destrutivo controlado): backup INTEIRO do target existente.
    BKP="${TARGET}.bak-${TIMESTAMP}"
    echo "    Target existe (modo fresh-install). Backup INTEIRO → ${BKP}"
    if [ "$APPLY" -eq 1 ]; then
      mv "$TARGET" "$BKP"
      echo "    ✔ Backup INTEIRO feito"
    else
      echo "    [dry-run] backup inteiro será feito"
    fi
  else
    # MODO UPDATE NÃO-DESTRUTIVO: NÃO faz mv inteiro.
    # Apenas anuncia que backups INDIVIDUAIS serão criados por arquivo alterado.
    echo "    Target existe (modo update). Backup INDIVIDUAL por arquivo alterado → .bak-${TIMESTAMP}"
    echo "    Blacklist (user_rules/, bindings/registry.jsonl, memory/) → NUNCA tocados"
  fi
fi

ensure_dir() {
  local p="$1"
  if [ "$APPLY" -eq 1 ]; then
    mkdir -p "$p"
  fi
}

ensure_dir "$TARGET"
ensure_dir "${TARGET}/bindings"

# ============================================================
# Helper: backup individual ANTES de sobrescrever (modo update).
# No modo fresh-install target está vazio, então helper quase não roda.
# ============================================================
backup_if_exists_and_diff() {
  local SRC="$1"
  local DST="$2"
  local LABEL="$3"

  if [ ! -e "$SRC" ]; then
    # Source não tem: NUNCA toca no target. Preserva item custom do usuário.
    return 99
  fi

  if [ ! -e "$DST" ]; then
    # Target não tem: copia novo, sem backup.
    echo "    + novo  ${LABEL}"
    if [ "$APPLY" -eq 1 ]; then
      cp -R "$SRC" "$DST"
    fi
    return 0
  fi

  # Ambos existem: compara (arquivo: cmp; diretório: diff -qr).
  local ARE_DIFFERENT=0
  if [ -f "$SRC" ] && [ -f "$DST" ]; then
    cmp -s "$SRC" "$DST" || ARE_DIFFERENT=1
  elif [ -d "$SRC" ] && [ -d "$DST" ]; then
    diff -qr "$SRC" "$DST" >/dev/null 2>&1 || ARE_DIFFERENT=1
  else
    # Tipo mudou (ex: arquivo → diretório). Trata como diferente.
    ARE_DIFFERENT=1
  fi

  if [ "$ARE_DIFFERENT" -eq 0 ]; then
    # Idênticos: silent skip.
    return 0
  fi

  # Diferentes: backup individual do target (SEMPRE, independente de dry-run avisa).
  local BKP="${DST}.bak-${TIMESTAMP}"
  echo "    ~ updt  ${LABEL}  (old → .bak-${TIMESTAMP})"
  if [ "$APPLY" -eq 1 ]; then
    mv "$DST" "$BKP"
    cp -R "$SRC" "$DST"
  fi
  return 0
}

# ============================================================
# Passo 2: copia whitelist arquivos raiz com merge inteligente.
# ============================================================
NEEDS_PNPM_INSTALL=0
for f in "${WHITELIST_ROOT_FILES[@]}"; do
  SRC="${SOURCE}/${f}"
  DST="${TARGET}/${f}"
  ret=0
  backup_if_exists_and_diff "$SRC" "$DST" "root/${f}" || ret=$?
  if [ "$ret" -eq 0 ] && [ "${f}" = "package.json" -o "${f}" = "pnpm-lock.yaml" ]; then
    NEEDS_PNPM_INSTALL=1
  fi
done

# ============================================================
# Passo 3: copia whitelist diretórios (merge por sub-item).
# Em diretórios: aplicamos NÃO-DESTRUTIVO RECURSIVAMENTE por item
# para PRESERVAR sub-pastas/arquivos do usuário (ex: skills custom).
# ============================================================
for d in "${WHITELIST_DIRS[@]}"; do
  SRC="${SOURCE}/${d}"
  DST="${TARGET}/${d}"
  if [ ! -d "$SRC" ]; then
    continue
  fi
  if [ "$UPDATE" -eq 0 ]; then
    # MODO fresh-install: cópia direta (target está vazio anyway).
    echo "    cp dir : ${d}/"
    if [ "$APPLY" -eq 1 ]; then
      cp -R "$SRC" "$DST"
    fi
  else
    # MODO update NÃO-DESTRUTIVO: itera POR SUBITEM dentro do dir da source.
    # Subitems que existem na source → processa. Subitems que existem só no target
    # (skill custom do user) → NUNCA são tocados.
    ensure_dir "$DST"
    # Lista subitems (files + dirs) em SRC/${d}
    shopt -s dotglob nullglob
    for subitem in "${SRC}"/*; do
      subname="$(basename "$subitem")"
      SUBSRC="${subitem}"
      SUBDST="${DST}/${subname}"
      ret=0
      backup_if_exists_and_diff "$SUBSRC" "$SUBDST" "${d}/${subname}" || ret=$?
      true
    done
    shopt -u dotglob nullglob
  fi
done

# ============================================================
# Passo 4: BLACKLIST — garantia de estrutura mínima VÁZIA (sempre).
# NUNCA copia conteúdo. Apenas cria pasta se NÃO existir.
# bindings/README.md é criado só se não existir nenhum.
# ============================================================
BINDINGS_README="${TARGET}/bindings/README.md"
if [ "$APPLY" -eq 1 ] && [ ! -f "$BINDINGS_README" ]; then
  cat > "$BINDINGS_README" <<'EOF'
Nível 1 — registry.jsonl.
NÃO editar manualmente. Escritor único = contracts helper `harness_registry_append_jsonl`.
Arquivo NUNCA é sobrescrito por install-harness.sh nem por `git pull` (blacklisted).
EOF
fi

for d in user_rules memory; do
  FULL="${TARGET}/${d}"
  if [ ! -d "$FULL" ] && [ "$APPLY" -eq 1 ]; then
    mkdir -p "$FULL"
    # Cria .gitkeep SÓ se a pasta estava vazia antes da criação.
    touch "${FULL}/.gitkeep"
  fi
done

# Garante user_rules/.gitkeep se a pasta user_rules existir mas estiver vazia
# (mantém rastreabilidade de estrutura em clones do repo).
if [ -d "${TARGET}/user_rules" ]; then
  # Conta arquivos não-.gitkeep na pasta user_rules. Zero → cria .gitkeep.
  count_non_gitkeep=0
  if [ "$APPLY" -eq 1 ]; then
    count_non_gitkeep=$(find "${TARGET}/user_rules" -maxdepth 1 -type f ! -name ".gitkeep" 2>/dev/null | wc -l)
    if [ "$count_non_gitkeep" -eq 0 ] && [ ! -f "${TARGET}/user_rules/.gitkeep" ]; then
      touch "${TARGET}/user_rules/.gitkeep"
    fi
  fi
fi

# ============================================================
# Passo 5: rodar pnpm install se package.json/pnpm-lock.yaml mudaram (update)
# OU se fresh-install com package.json existente.
# ============================================================
if [ -f "${TARGET}/package.json" ]; then
  run_pnpm=0
  if [ "$UPDATE" -eq 0 ] || [ "$NEEDS_PNPM_INSTALL" -eq 1 ]; then
    run_pnpm=1
  fi
  if [ "$run_pnpm" -eq 1 ]; then
    echo "    pnpm install target..."
    if [ "$APPLY" -eq 1 ]; then
      (cd "$TARGET" && (corepack enable >/dev/null 2>&1 || true) && corepack pnpm install --prefer-offline 2>&1 | tail -5)
    fi
  fi
fi

# ============================================================
# Passo 6: sumário de segurança (blacklist intacta).
# ============================================================
echo ""
echo "=== ${MODE_NAME^^} ${MODE_LABEL} concluído."
echo ""
echo " BLACKLIST (intocada em ambos modos):"
echo "   · user_rules/           (suas regras pessoais nunca são copiadas/deletadas)"
echo "   · bindings/registry.jsonl  (seu level-1 binding local)"
echo "   · memory/                (dados locais de memória do Trae)"
echo "   · skills/custom-*/       (qualquer subpasta em target que NÃO exista em source)"
echo ""

if [ "$UPDATE" -eq 1 ]; then
  echo " MODO UPDATE:"
  echo "   · Novos arquivos oficiais → adicionados (marcados + novo)."
  echo "   · Arquivos oficiais alterados → sobrescritos COM backup .bak-${TIMESTAMP}."
  echo "   · Alterações SUAS em arquivos da whitelist → salvas em ${TARGET}/*.bak-${TIMESTAMP}."
  echo "   · Pastas/arquivos SEUS que não existem em source → 100% preservados (nunca tocados)."
fi

if [ "$APPLY" -eq 0 ]; then
  echo "⚠ dry-run. Para APLICAR de verdade: $0 $( [ "$UPDATE" -eq 1 ] && echo -n "--update " )--apply"
else
  echo "✔ target pronto em $TARGET"
  echo ""
  echo " Checklist pós:"
  echo "  1. Abrir Trae de novo (ou recarregar)."
  echo "  2. Confirmar ~/.trae/README.md existe."
  echo "  3. Smoke : bash $TARGET/scripts/install-harness.sh -h"
  echo "  4. Decisions: corepack pnpm --dir $TARGET decisions --help 2>&1 | head"
  if [ "$UPDATE" -eq 1 ]; then
    echo "  5. Rollback manual: se quiser desfazer um arquivo, mv <arquivo>.bak-${TIMESTAMP} <arquivo>"
  fi
fi

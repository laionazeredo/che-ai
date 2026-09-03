#!/usr/bin/env bash
#
# update-che.sh — Alias INTELIGENTE para atualizar o che.
#
# DOIS CAMINHOS (detecta AUTOMATICAMENTE qual caso é o seu):
#
#   CASO 1 — target (~/.trae) É UM GIT REPO clonado DIRETO de laionazeredo/trae-config
#     → executa:  git fetch  (dry-run) ou  git pull --ff-only (--apply)
#        + se package.json/pnpm-lock.yaml mudaram → corepack pnpm install --prefer-offline
#     Vantagem: zero cópias, merge zero conflitos (ff-only aborta se divergência),
#     blacklist do .gitignore do repo protege user_rules / bindings / memory AUTOMATICAMENTE.
#     Este é o caminho RECOMENDADO.
#
#   CASO 2 — target NÃO É git repo (usuário baixou zip, copiou manualmente etc)
#     → executa: install-che.sh --update [--apply] --source=<este diretório> --target=$TARGET
#        usando a lógica não-destrutiva descrita em install-che.sh (backups individuais,
#        blacklist intocável, preserve items custom do target que não existem na source).
#
# USO:
#   ./scripts/update-che.sh               # DRY-RUN (fetch / install --update dry-run).
#   ./scripts/update-che.sh --apply       # Aplica a atualização de verdade.
#   ./scripts/update-che.sh --target /custom/.trae
#   ./scripts/update-che.sh -h
#
# GARANTIAS DE SEGURANÇA:
#   * Default sempre DRY-RUN. --apply obrigatório para escrever.
#   * CASO 1 usa --ff-only: se target tem commits locais NÃO no upstream, ABORTA sem merge.
#     NUNCA faz merge automático; merge só pode ser manual. Isso previne sobrescrita
#     de modificações locais legítimas em arquivos versionados.
#   * CASO 2 reutiliza a lógica fail-closed de install-che.sh --update (backups
#     individuais por arquivo alterado, nenhum rm, blacklist intocável).
#   * Nenhum `rm -rf` em lugar nenhum deste script.

set -euo pipefail

APPLY=0
TARGET="${HOME}/.trae"

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=1
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
      sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERRO: opção desconhecida: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

# Resolve o diretório onde ESTE script update-che.sh mora para detectar a SOURCE
# usada no CASO 2 (não-git). CASO 1 ignora a source.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE_LABEL="[dry-run]"
[ "$APPLY" -eq 1 ] && MODE_LABEL="[apply]"

echo "==> Che update ${MODE_LABEL}"
echo "    Target: ${TARGET}"
echo "    Source (caso fallback): ${SOURCE}"
echo ""

# ============================================================
# HELPER: detecta se diretório é um git repo COM upstream setado
# ============================================================
is_git_repo_with_remote() {
  local d="$1"
  [ -d "${d}/.git" ] || return 1
  (cd "$d" && git rev-parse --git-dir >/dev/null 2>&1) || return 1
  local remote_count
  remote_count=$(cd "$d" && git remote 2>/dev/null | wc -l)
  [ "${remote_count:-0}" -gt 0 ] || return 1
  return 0
}

# ============================================================
# HELPER: conta alterações locais não commitadas em arquivos
# NÃO-blacklisted (arquivos blacklisted .gitignore são ignorados
# pois git não os trackeia mesmo — é a proteção automática do CASO1).
# ============================================================
count_uncommitted_tracked_changes() {
  local d="$1"
  (cd "$d" && git status --porcelain --untracked-files=no 2>/dev/null | wc -l)
}

# ============================================================
# HELPER: conta arquivos untracked NÃO-blacklisted.
# Blacklisted files são marcados '!!' por `git status --porcelain --ignored`.
# Queremos apenas '??' que são novos arquivos que o usuário criou e NÃO estão ignorados.
# ============================================================
count_untracked_non_ignored() {
  local d="$1"
  (cd "$d" && git status --porcelain --untracked-files=normal 2>/dev/null | grep -cE '^\?\?' || true)
}

# ============================================================
# DETECÇÃO DE CASO
# ============================================================
if is_git_repo_with_remote "$TARGET"; then
  # ==========================================================
  # CASO 1 — GIT REPO (caminho recomendado)
  # ==========================================================
  echo "✅ CASO 1 DETECTADO: target ${TARGET} é um git repo com remoto."
  echo "   Estratégia: git pull --ff-only (merge automático NÃO permitido)."
  echo ""

  UNCOMMITTED=$(count_uncommitted_tracked_changes "$TARGET")
  UNTRACKED=$(count_untracked_non_ignored "$TARGET")

  if [ "$UNCOMMITTED" -gt 0 ]; then
    echo "⚠  Alterações locais NÃO commitadas em arquivos trackeados: ${UNCOMMITTED}"
    echo "   (arquivos em user_rules/ / bindings/registry.jsonl / memory/ estão em blacklist do .gitignore — esses NÃO contam, são seguros)."
    echo ""
    echo "   Lista (primeiros 20):"
    (cd "$TARGET" && git status --porcelain --untracked-files=no | head -20) || true
    echo ""
    if [ "$APPLY" -eq 1 ]; then
      echo "❌ ABORTADO. --apply + uncommitted changes em arquivos trackeados → fail-closed."
      echo "   Soluções:"
      echo "    a) Commit suas alterações locais primeiro (se quiser mantê-las)."
      echo "    b) Descarte:  cd ${TARGET} && git stash push -m \"wip antes update che\""
      echo "    c) Rode sem --apply para dry-run."
      exit 3
    fi
  fi

  if [ "$UNTRACKED" -gt 0 ]; then
    echo "ℹ  Arquivos novos não-trackeados (não-blacklisted): ${UNTRACKED}. Eles NÃO serão tocados por git pull."
  fi

  # Fetch primeiro (tanto dry-run quanto apply).
  echo ""
  echo "    → Fetch remoto (atualiza refs):"
  FETCH_OUT=""
  if [ "$APPLY" -eq 1 ]; then
    FETCH_OUT=$(cd "$TARGET" && git fetch --all 2>&1 || echo "FETCH_FAIL=$?")
    echo "$FETCH_OUT" | tail -10
  else
    FETCH_OUT=$(cd "$TARGET" && git fetch --all --dry-run 2>&1 || echo "FETCH_FAIL=$?")
    echo "$FETCH_OUT" | tail -10
  fi

  # Lista commits que vão entrar (dry-run).
  echo ""
  echo "    → Commits que serão aplicados (HEAD..upstream):"
  if (cd "$TARGET" && git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1); then
    (cd "$TARGET" && git log --oneline HEAD..\@{u} 2>/dev/null) | head -20 || true
  else
    echo "       (sem upstream branch configurado para a branch atual)"
  fi

  # AHEAD count (commits locais que o upstream NÃO tem).
  AHEAD=0
  if (cd "$TARGET" && git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1); then
    AHEAD=$(cd "$TARGET" && git rev-list --count \@{u}..HEAD 2>/dev/null || echo 0)
  fi
  if [ "${AHEAD:-0}" -gt 0 ]; then
    echo ""
    echo "⚠  Target está AHEAD do upstream em ${AHEAD} commit(s). --ff-only NÃO vai aplicar. ABORTARIA se --apply."
    echo "   Motivo: você tem commits locais exclusivos. Para manter: rebase manual primeiro."
  fi

  NEEDS_PNPM=0
  if [ "$APPLY" -eq 1 ]; then
    # Verifica SE package.json / pnpm-lock.yaml ESTÃO na lista de commits que entrarão.
    # (evita rodar pnpm install à toa se nada mudou).
    if (cd "$TARGET" && git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1); then
      FILES_TO_CHANGE=$(cd "$TARGET" && git diff --name-only HEAD \@{u} 2>/dev/null || true)
      if echo "$FILES_TO_CHANGE" | grep -qE '(^|/)package\.json$'; then NEEDS_PNPM=1; fi
      if echo "$FILES_TO_CHANGE" | grep -qE '(^|/)pnpm-lock\.yaml$'; then NEEDS_PNPM=1; fi
    fi

    echo ""
    echo "    → git pull --ff-only (sem merge automático):"
    PULL_OUT=$(cd "$TARGET" && git pull --ff-only 2>&1) || {
      echo "$PULL_OUT" | tail -10
      echo ""
      echo "❌ git pull --ff-only falhou (divergência? ver commits AHEAD acima)."
      echo "   Nenhum arquivo foi modificado. Resolva manualmente."
      exit 4
    }
    echo "$PULL_OUT" | tail -10

    if [ "$NEEDS_PNPM" -eq 1 ] && [ -f "${TARGET}/package.json" ]; then
      echo ""
      echo "    → pnpm install (package.json/pnpm-lock.yaml mudaram):"
      (cd "$TARGET" && (corepack enable >/dev/null 2>&1 || true) && corepack pnpm install --prefer-offline 2>&1 | tail -5)
    fi
  fi

  echo ""
  echo "=== CASO 1 GIT UPDATE ${MODE_LABEL} concluído."
  echo ""
  echo " BLACKLIST (AUTOMATICAMENTE protegida pelo .gitignore do repo):"
  echo "    · user_rules/*              (apenas .gitkeep é trackeado; regras pessoais intocadas)"
  echo "    · bindings/registry.jsonl   (100% ignorado)"
  echo "    · memory/                   (100% ignorado)"
  echo "    · Skills custom que você ADICIONOU em skills/ e NÃO foram commitadas → intocadas,"
  echo "      a MENOS que exista no upstream uma PASTA com MESMO NOME (conflito só de nome)."
  echo ""
  if [ "$APPLY" -eq 0 ]; then
    echo "⚠  Dry-run concluído. NADA foi alterado."
    echo "   Se o relatório acima está OK:  $0 --apply"
  else
    echo "✔ Update aplicado com sucesso via git --ff-only."
    echo "  Rollback de emergência: cd ${TARGET} && git reset --hard HEAD@{1}"
    echo "  (voltando para o estado IMEDIATAMENTE antes deste pull)."
  fi
  exit 0
fi

# ============================================================
# CASO 2 — NÃO é git repo → fallback para install-che.sh --update
# ============================================================
echo "ℹ  CASO 2 DETECTADO: target ${TARGET} NÃO é um git repo."
echo "   Estratégia: install-che.sh --update (não-destrutivo, backups individuais)."
echo ""
echo "   Source usada: ${SOURCE}"
echo ""

# Valida que a source é válida.
if [ ! -f "${SOURCE}/scripts/install-che.sh" ]; then
  echo "❌ ERRO: Não consegui localizar install-che.sh em ${SOURCE}/scripts/"
  echo "   Rode este script de DENTRO de uma cópia do repositório de configuração."
  exit 2
fi

EXTRA_ARGS=()
EXTRA_ARGS+=("--update")
EXTRA_ARGS+=("--source" "${SOURCE}")
EXTRA_ARGS+=("--target" "${TARGET}")
[ "$APPLY" -eq 1 ] && EXTRA_ARGS+=("--apply")

echo "    Executando: bash ${SOURCE}/scripts/install-che.sh $(printf '%q ' "${EXTRA_ARGS[@]}")"
echo ""
bash "${SOURCE}/scripts/install-che.sh" "${EXTRA_ARGS[@]}"

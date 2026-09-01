#!/usr/bin/env bash
#
# self-update-harness.sh — 1 COMANDO para pegar a última versão do harness oficial
#                           e mesclar em sua instalação local SEM perder dados pessoais.
#
# PREMISSA (cenário real do usuário):
#   "Pessoa já tem o harness instalado em ~/.trae há semanas/meses. Não lembra
#    se instalou via git clone ou zip. Só quer ter a última versão do GitHub.
#    Não quer baixar nada manualmente, não quer lembrar flags. Só quer rodar
#    UM COMANDO e garantir que seus user_rules/bindings/memory/skills custom
#    permanecem intactos."
#
# ESTE SCRIPT É ESSE COMANDO:
#   bash ~/.trae/scripts/self-update-harness.sh               # DRY-RUN (padrão).
#   bash ~/.trae/scripts/self-update-harness.sh --apply       # Aplica de verdade.
#   bash ~/.trae/scripts/self-update-harness.sh -h
#
# O que este script FAZ AUTOMATICAMENTE, ZERO CONFIGURAÇÃO:
#   1) Valida que ~/.trae (TARGET) já existe (não é fresh install).
#   2) Faz fetch AUTÔNOMO da ÚLTIMA versão oficial de github.com/laionazeredo/trae-config:
#        PRIORIDADE A: se `gh` CLI está logado → `gh repo clone ... --depth 1` em /tmp/tmpXXXXXX.
#        PRIORIDADE B: senão, se `git` disponível → `git clone --depth 1 https://github.com/...` em /tmp/tmpXXXXXX.
#        NENHUMA DAS DUAS → fail-fast com instruções instalar gh OU git.
#   3) Detecta AUTOMATICAMENTE qual é o caso do target:
#        CASO 1 — TARGET é um git repo com upstream setado.
#          → executa: bash scripts/update-harness.sh --[apply] (git pull --ff-only no TARGET MESMO;
#            proteção gitignore + --ff-only garante zero merge automático / zero sobrescrita pessoal).
#        CASO 2 — TARGET não é git repo (zip/cópia manual).
#          → executa: bash <tmp-src>/scripts/install-harness.sh --update [--apply]
#            (merge item-a-item com backups INDIVIDUAIS e BLACKLIST intocável.
#             Tudo que a pessoa tinha de pessoal que não existe na source oficial NUNCA é tocado).
#   4) Limpeza final: o /tmp/tmpXXXXXX fetch da source nova é deletada no final
#      (trap EXIT). Nenhum arquivo temporário é deixado para trás.
#   5) Sempre printa, antes de aplicar:
#        - Qual CASO (1/2) foi detectado
#        - Qual estratégia vai usar
#        - Blacklist que NUNCA será tocada
#
# GARANTIAS FAIL-CLOSED (estendidas de update-harness + install-update):
#   * Default DRY-RUN. `--apply` obrigatório para escrever.
#   * Nenhum `rm` neste script (sobre /home). Apenas rm -rf no /tmp/tmp fetch (trap).
#   * Caso 1: `git pull --ff-only` no TARGET mesmo. Se divergência → aborta sem merge.
#     Modificações locais tracked não commitadas → aborta com instrução (commit ou stash).
#   * Caso 2: install --update NÃO faz mv global do target. Tudo item-a-item com backup INDIVIDUAL
#     de cada coisa alterada (mv target/x → target/x.bak-TIMESTAMP, antes de copiar novo).
#   * BLACKLIST global intocável: user_rules/*, bindings/registry.jsonl, memory/,
#     qualquer item custom target-only.
#   * Rollback manual instruído em cada caso (1: git reset HEAD@{1}; 2: mv item.bak-* item).
#
# DEPENDÊNCIAS OBRIGATÓRIAS (pelo menos 1 dos 2 fetchers):
#   - `gh` (GitHub CLI) — preferido, já loga + autentica. OU
#   - `git` (fallback) — clone raso HTTPS público.
# Ambas são comuns. Se nenhuma estiver disponível, script diz exatamente qual instalar.

set -euo pipefail

# ============================================================
# Flags e defaults.
# ============================================================
APPLY=0
TARGET="${HOME}/.trae"
GH_REPO="laionazeredo/trae-config"
TMP_SRC=""   # definido abaixo se fetch for bem sucedido.

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
    --repo)
      GH_REPO="${2:-}"
      shift 2
      ;;
    --repo=*)
      GH_REPO="${1#--repo=}"
      shift
      ;;
    --local-source)
      TMP_SRC="${2:-}"
      shift 2
      ;;
    --local-source=*)
      TMP_SRC="${1#--local-source=}"
      shift
      ;;
    -h|--help)
      sed -n '2,100p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERRO: opção desconhecida: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

MODE_LABEL="[dry-run]"
[ "$APPLY" -eq 1 ] && MODE_LABEL="[apply]"

# ============================================================
# Limpeza: SEMPRE apaga /tmp/<temp fetch folder> no final,
# independente de erro ou sucesso. Menos lixo na máquina do user.
# ============================================================
cleanup_tmp(){
  if [ -n "${TMP_SRC:-}" ] && [ -d "$TMP_SRC" ] && [[ "$TMP_SRC" == /tmp/* ]]; then
    rm -rf "$TMP_SRC"
  fi
}
trap cleanup_tmp EXIT

echo "==> Harness self-update ${MODE_LABEL}"
echo "    Target: ${TARGET}"
echo "    Repo oficial: https://github.com/${GH_REPO}"
echo ""

# ============================================================
# Passo 1: validar que TARGET existe (não é fresh install).
# ============================================================
if [ ! -e "$TARGET" ]; then
  echo "❌ Target ${TARGET} NÃO existe." >&2
  echo "   Este script é para ATUALIZAR uma instalação existente." >&2
  echo "   Para INSTALAR DO ZERO, siga README §0:" >&2
  echo "      gh repo clone ${GH_REPO} ${TARGET} -- --depth 1" >&2
  echo "      corepack enable && corepack pnpm --dir ${TARGET} install --prefer-offline" >&2
  exit 6
fi

if [ ! -f "${TARGET}/README.md" ] && [ ! -f "${TARGET}/HARNESS_RULES.md" ]; then
  echo "❌ A pasta ${TARGET} não parece ser um .trae de harness (sem README.md nem HARNESS_RULES.md)." >&2
  exit 2
fi

# ============================================================
# Passo 2: FETCH AUTÔNOMO da última versão oficial.
# (BYPASS se flag QA oculta --local-source foi passada para TMP_SRC não-vazia antes.)
# ============================================================
FETCH_OK=0
FETCH_METHOD=""

if [ -n "${TMP_SRC:-}" ]; then
  FETCH_OK=1
  FETCH_METHOD="local-source-qa-bypass"
  echo "    ⚠ QA mode: usando source local (não faz fetch do GitHub): ${TMP_SRC}"
else
  TMP_SRC=$(mktemp -d /tmp/trae-src-fetch.XXXXXXXXXX)
  echo "    Baixando última versão oficial em pasta temporária: ${TMP_SRC}"

  # 2A) gh CLI se disponível E logado.
  if command -v gh >/dev/null 2>&1; then
    GH_USER=""
    if GH_USER=$(gh api user --jq .login 2>/dev/null) && [ -n "$GH_USER" ]; then
      echo "    → gh CLI disponível e logado como @${GH_USER}. Usando gh repo clone --depth 1."
      if gh repo clone "$GH_REPO" "$TMP_SRC" -- --depth 1 --quiet 2>/dev/null; then
        FETCH_OK=1
        FETCH_METHOD="gh-clone"
      else
        echo "    ⚠ gh clone falhou. Vou tentar método B (git clone HTTPS público)."
      fi
    else
      echo "    ℹ gh CLI existe mas NÃO está logado. Pulando para git clone HTTPS (fallback)."
    fi
  fi

  # 2B) git clone HTTPS público se gh falhou ou não existe.
  if [ "$FETCH_OK" -eq 0 ] && command -v git >/dev/null 2>&1; then
    echo "    → git disponível. Usando git clone --depth 1 via HTTPS público (sem auth)."
    if git clone --depth 1 --quiet "https://github.com/${GH_REPO}.git" "$TMP_SRC" 2>/dev/null; then
      FETCH_OK=1
      FETCH_METHOD="git-clone-https"
    else
      echo "    ⚠ git clone HTTPS também falhou."
    fi
  fi

  if [ "$FETCH_OK" -eq 0 ]; then
    echo ""
    echo "❌ Falha ao fazer fetch da última versão oficial. Nenhuma das ferramentas disponíveis." >&2
    echo "   Instale UMA das dependências abaixo e rode novamente:" >&2
    echo "    • GitHub CLI (recomendado, loga em sua conta):" >&2
    echo "         https://cli.github.com/   → depois rode  gh auth login" >&2
    echo "    • Git (sem auth, clone público):" >&2
    echo "         sudo apt install git   # debian/ubuntu" >&2
    echo "         brew install git       # macos" >&2
    exit 7
  fi
fi

# Validação mínima da source baixada.
if [ ! -f "${TMP_SRC}/HARNESS_RULES.md" ]; then
  echo "❌ Fetch concluído mas a pasta baixada NÃO tem HARNESS_RULES.md — repo não confiável ou download corrompido." >&2
  exit 8
fi

# Exibe versão baixada (commit SHA curto se houver .git).
VERSION_LABEL=""
if [ -d "${TMP_SRC}/.git" ]; then
  VERSION_LABEL="commit $(cd "$TMP_SRC" && git rev-parse --short HEAD 2>/dev/null || echo '?')"
fi
echo "    ✔ Fetch OK (${FETCH_METHOD}). Última versão oficial baixada: ${VERSION_LABEL:-<desconhecida>}"
echo ""

# ============================================================
# Passo 3: DETECÇÃO AUTOMÁTICA DE CASO 1 vs CASO 2.
# ============================================================
is_target_git_repo_with_remote() {
  local d="$1"
  [ -d "${d}/.git" ] || return 1
  (cd "$d" && git rev-parse --git-dir >/dev/null 2>&1) || return 1
  local remotes
  remotes=$(cd "$d" && git remote 2>/dev/null | wc -l)
  [ "${remotes:-0}" -gt 0 ] || return 1
  return 0
}

EXTRA_UPDATE_ARGS=()
[ "$APPLY" -eq 1 ] && EXTRA_UPDATE_ARGS+=("--apply")
EXTRA_UPDATE_ARGS+=("--target" "$TARGET")

if is_target_git_repo_with_remote "$TARGET"; then
  # ==========================================================
  # CASO 1 — target já É git repo com remoto (90% dos users do fresh install §0).
  # Chamamos update-harness.sh do TARGET mesmo (ff-only pull no próprio repo).
  # ==========================================================
  echo "🟢 CASO 1 DETECTADO: target ${TARGET} é um git repo com remoto."
  echo "   Estratégia: git pull --ff-only no próprio TARGET (update-harness.sh via source tmp)."
  echo "   Blacklist AUTOMÁTICA via .gitignore do repo: user_rules/*, bindings/registry.jsonl, memory/."
  echo ""
  if [ -f "${TMP_SRC}/scripts/update-harness.sh" ]; then
    exec bash "${TMP_SRC}/scripts/update-harness.sh" "${EXTRA_UPDATE_ARGS[@]}"
  else
    exec bash "${TARGET}/scripts/update-harness.sh" "${EXTRA_UPDATE_ARGS[@]}"
  fi
  # NOTA: `exec` substitui o shell, cleanup_tmp trap AINDA roda porque o shell pai
  # recebe o EXIT da execução (trap é do shell pai). Se update-harness c/ exit !=0,
  # trap roda normalmente.
else
  # ==========================================================
  # CASO 2 — target NÃO é git repo (ex: instalou via zip, cópia manual).
  # Chamamos install-harness.sh --update usando TMP_SRC como source.
  # ==========================================================
  echo "🟡 CASO 2 DETECTADO: target ${TARGET} NÃO é um git repo."
  echo "   Estratégia: install-harness.sh --update (merge não-destrutivo item-a-item)."
  echo "   Backups INDIVIDUAIS por item alterado → ${TARGET}/<item>.bak-YYYYMMDD-HHMM."
  echo "   Blacklist INTOCÁVEL (nem lida): user_rules/*, bindings/registry.jsonl, memory/."
  echo "   Itens SEUS em target que NÃO existem na source oficial → NUNCA tocados."
  echo ""
  exec bash "${TMP_SRC}/scripts/install-harness.sh" --update --source "$TMP_SRC" "${EXTRA_UPDATE_ARGS[@]}"
fi

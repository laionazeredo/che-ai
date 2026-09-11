#!/usr/bin/env bash
#
# Installs / upgrades Che's local Git hooks (pre-commit, pre-push) into the
# current repository's `.git/hooks/` directory.
#
# Idempotent: can be re-run safely. Existing hooks with the CHE_MARKER
# signature are overwritten; unrelated hooks are left alone.
#
# Usage:
#   scripts/install-git-hooks.sh              # install
#   scripts/install-git-hooks.sh --remove     # uninstall (reverts to backup)
#
# Runs automatically at the tail of scripts/install-che.sh when the target
# is THIS repo (i.e. when an agent bootstraps the Che repo itself).

set -euo pipefail

RED=$'\033[0;31m'; YEL=$'\033[1;33m'; GRN=$'\033[0;32m'; DIM=$'\033[2m'; RST=$'\033[0m'
info() { printf '%s[install-git-hooks]%s %s\n'  "${DIM}" "${RST}" "$*"; }
ok()   { printf '%s[install-git-hooks] %sOK%s %s\n' "${DIM}" "${GRN}" "${RST}" "$*"; }
warn() { printf '%s[install-git-hooks] %sWARN%s %s\n' "${DIM}" "${YEL}" "${RST}" "$*"; }
fail() { printf '%s[install-git-hooks] %sFAIL%s %s\n' "${DIM}" "${RED}" "${RST}" "$*" >&2; exit 1; }

REMOVE=0
for a in "$@"; do
  case "${a}" in
    --remove|-r) REMOVE=1 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      fail "Unknown arg: ${a}. Use --remove to uninstall."
      ;;
  esac
done

# Resolve repo root (works when invoked from inside scripts/ too).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="${REPO_ROOT}/.git/hooks"
SRC_DIR="${REPO_ROOT}/scripts/git-hooks"

cd "${REPO_ROOT}"

if [[ ! -d ".git" ]]; then
  fail "Not in a git repo — .git not found at ${REPO_ROOT}"
fi
mkdir -p "${HOOK_DIR}"

CHE_MARKER="# CHESIGNAL do not edit manually — managed by scripts/install-git-hooks.sh"

install_one() {
  local name="$1"
  local src="${SRC_DIR}/${name}"
  local dst="${HOOK_DIR}/${name}"
  local bak="${dst}.pre-che.bak"

  if (( REMOVE == 1 )); then
    if [[ -f "${dst}" ]] && grep -qF "${CHE_MARKER}" "${dst}" 2>/dev/null; then
      if [[ -f "${bak}" ]]; then
        mv -f "${bak}" "${dst}"
        chmod +x "${dst}"
        ok "restored ${name} from pre-che backup"
      else
        rm -f "${dst}"
        ok "removed ${name}"
      fi
    else
      info "no Che-managed ${name} present — nothing to remove"
    fi
    return 0
  fi

  if [[ ! -f "${src}" ]]; then
    fail "source hook missing: ${src}"
  fi

  # Back up pre-existing hook if present AND not already ours.
  if [[ -f "${dst}" ]] && ! grep -qF "${CHE_MARKER}" "${dst}" 2>/dev/null; then
    cp -f "${dst}" "${bak}"
    warn "pre-existing ${name} hook backed up to  ${bak}"
  fi

  # Inject marker so we know this is ours + version source dir.
  # CRITICAL: keep the shebang on LINE 1 — kernel ignores shebangs on any other
  # line, and without #!/usr/bin/env bash this file gets run via /bin/sh (dash
  # on Ubuntu) which lacks 'set -o pipefail'.
  {
    head -n 1 "${src}" | grep -q '^#!' && head -n 1 "${src}"
    echo "${CHE_MARKER}"
    echo "# source: ${src}"
    echo ""
    if head -n 1 "${src}" | grep -q '^#!'; then
      tail -n +2 "${src}"
    else
      cat "${src}"
    fi
  } > "${dst}"
  chmod +x "${dst}"
  chmod +x "${src}"
  ok "installed ${name} -> ${dst}"
}

install_one pre-commit
install_one pre-push

echo ""
if (( REMOVE == 1 )); then
  info "Che Git hooks removed. Restore with:  scripts/install-git-hooks.sh"
else
  info "Che Git hooks installed."
  echo "  • pre-commit (~3 s): ruff lint+format on staged Python + regex secret scan + md lint canonical docs + smoke pytest if core changed"
  echo "  • pre-push  (~30 s): ruff lint+format full repo + full pytest 39 tests + markdownlint-cli2 (CI globs) + push-diff regex secret scan"
  echo "  • Bypass once if needed:   git commit/push --no-verify"
  echo "  • Skip env var shortcut:   CHE_SKIP_PRE_COMMIT=1  or  CHE_SKIP_PRE_PUSH=1"
fi

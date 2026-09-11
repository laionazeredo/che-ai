#!/usr/bin/env bash
#
# Che — Check local development dependencies for contributors.
#
# Verifies that the tools required to run the Git hooks (pre-commit + pre-push)
# and GitHub Actions CI are present on the contributor's machine.
#
# Two modes:
#   (1) STRICT (default): exits non-zero if any REQUIRED tool is missing.
#       Used by pre-commit / pre-push hooks so they fail FAST with actionable
#       copy-pasteable install instructions — never with a cryptic
#       "command not found" halfway through some gate.
#   (2) WARN mode (--warn): never exits non-zero. Used by one-shot
#       installers or CI-config-only changes where skipping gates is fine.
#
# Usage:
#   bash scripts/check-dev-dependencies.sh           # STRICT (default)
#   bash scripts/check-dev-dependencies.sh --warn    # WARN only, no exit code
#   bash scripts/check-dev-dependencies.sh --help    # show this header
#
# Exit codes:
#   0 — all REQUIRED tools present (or WARN mode)
#   1 — ≥ 1 REQUIRED tool missing (STRICT mode)
#   2 — bad CLI argument

set -euo pipefail

CHE_DEPS_STRICT=1
for a in "$@"; do
  case "${a}" in
    --warn|-w)   CHE_DEPS_STRICT=0 ;;
    --help|-h)
      sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "[check-dev-deps] ERROR: unknown arg '${a}'. Use --warn for non-fatal mode, -h for help." >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers (self-contained on purpose: this file is also called standalone
# before the hooks' helpers are loaded, and from install-che.sh too).
# ---------------------------------------------------------------------------

RED=$'\033[0;31m'; YEL=$'\033[1;33m'; GRN=$'\033[0;32m'; DIM=$'\033[2m'; RST=$'\033[0m'

inf()   { printf '%s[check-dev-deps]%s %s\n'    "${DIM}"  "${RST}" "$*"; }
ok()    { printf '%s[check-dev-deps] %sOK%s  %s\n' "${DIM}"  "${GRN}" "${RST}" "$*"; }
warn()  { printf '%s[check-dev-deps] %sWARN%s %s\n' "${DIM}"  "${YEL}" "${RST}" "$*"; }
miss()  { printf '%s[check-dev-deps] %sMISS%s  %s\n'   "${DIM}"  "${RED}" "${RST}" "$*"; }
die()   { printf '%s[check-dev-deps] %sFAIL%s  %s\n'   "${DIM}"  "${RED}" "${RST}" "$*" >&2; exit 1; }

# Two counters so we can summarise the tail of the report.
MISSING_REQUIRED=0
MISSING_OPTIONAL=0

if (( CHE_DEPS_STRICT == 1 )); then
  inf "Running STRICT check (missing REQUIRED → block commit / push)."
else
  inf "Running WARN check (missing tools → skip related gates, no block)."
fi

# ---------------------------------------------------------------------------
# Per-tool checker. Prints install indented after the missing line so a
# contributor can literally copy/paste the line block into their shell.
#   $1 kind       — REQUIRED or OPTIONAL
#   $2 bin        — binary name passed to `command -v`
#   $3 label      — human-friendly title
#   $4 install    — multi-line install instructions (use $'line1\nline2')
# ---------------------------------------------------------------------------
check_tool() {
  local kind="$1"
  local bin="$2"
  local label="$3"
  local install="$4"
  local version=""

  if command -v "${bin}" >/dev/null 2>&1; then
    case "${bin}" in
      python3)
        version="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo "")"
        if [[ -n "${version}" ]]; then
          # Also enforce >= 3.9 for REQUIRED because that's pyproject.toml.
          local major minor
          major="${version%%.*}"
          minor="${version#*.}"; minor="${minor%%.*}"
          if (( CHE_DEPS_STRICT == 1 )) && (( (major * 100 + minor) < 309 )); then
            MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
            miss "${label} — found ${version} but REQUIRED >= 3.9."
            printf '          Upgrade your Python 3 to 3.9+ or install alongside:\n'
            printf '            Ubuntu/Debian: sudo apt install -y python3.11 python3.11-venv\n'
            printf '            macOS:         brew install python@3.11\n'
            return 1
          fi
        fi
        ;;
      ruff)    version="$(ruff --version 2>/dev/null | head -n 1 || echo "")" ;;
      npx)     version="$(node --version 2>/dev/null || echo "") (npx)" ;;
    esac
    if [[ -n "${version}" ]]; then
      ok "${label} (${version})"
    else
      ok "${label}"
    fi
    return 0
  fi

  if [[ "${kind}" == "REQUIRED" ]]; then
    MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
    miss "${label} — REQUIRED to contribute to Che (blocks commit / push locally)."
  else
    MISSING_OPTIONAL=$((MISSING_OPTIONAL + 1))
    warn "${label} — OPTIONAL (related gates will be SKIPPED locally; GitHub CI still runs them)."
  fi
  while IFS= read -r line; do
    [[ -z "${line}" ]] && { printf '          \n'; continue; }
    printf '          %s\n' "${line}"
  done <<<"${install}"
  printf '\n'
  return 1
}

# ---------------------------------------------------------------------------
# REQUIRED tools — missing any → block commit/push in STRICT mode.
# ---------------------------------------------------------------------------
inf "—— REQUIRED tools —"

check_tool REQUIRED python3 "python3" $'Install system Python 3.9+:\n  Ubuntu/Debian : sudo apt install -y python3 python3-venv python3-pip\n  macOS         : brew install python\n  Universal     : https://www.python.org/downloads/'

# pytest is a Python package (not a global binary on fresh systems). Check
# via `python3 -m pytest` because that's exactly what the hooks / CI call.
if command -v python3 >/dev/null 2>&1; then
  PYTEST_VERSION=""
  if PYTEST_VERSION="$(python3 -m pytest --version 2>/dev/null | head -n 1)"; then
    ok "pytest module (${PYTEST_VERSION})"
  else
    MISSING_REQUIRED=$((MISSING_REQUIRED + 1))
    miss "pytest module (invoked as \`python3 -m pytest\`) — REQUIRED to contribute to Che."
    cat <<'EOF'
          Install ONE of:

            (A) Local virtual env (RECOMMENDED — isolated, no sudo):
                cd /path/to/che-ai
                python3 -m venv .venv
                . .venv/bin/activate
                pip install pytest ruff

            (B) User-level site-packages (global-ish for your user):
                python3 -m pip install --user pytest ruff

            (C) Pipx-into-project (if you already installed Che via `pipx install -e .`):
                pipx inject -e . pytest ruff

EOF
  fi
fi

check_tool REQUIRED ruff "ruff (lint + formatter)" $'Install ONE of:\n  (A) Pipx (recommended):      pipx install ruff\n  (B) Python user install:     python3 -m pip install --user ruff\n  (C) Inside a venv:            pip install ruff'

# ---------------------------------------------------------------------------
# OPTIONAL tools — missing → warn only, gates are skipped locally.
# ---------------------------------------------------------------------------
inf "—— OPTIONAL tools —"

check_tool OPTIONAL npx "Node.js + npx (for markdownlint-cli2)" $'Install Node.js LTS:\n  Ubuntu/Debian : curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install -y nodejs\n  macOS         : brew install node\n  Universal     : https://nodejs.org/  (LTS)\n  (or use nvm / asdf / volta for version management)\n\nWithout it the markdownlint gates are SKIPPED on your machine but still\nrun in GitHub Actions markdown-ci job — you will not block review but you\nwill waste a CI run. Installing Node LTS takes ~30 s and avoids that loop.'

# ---------------------------------------------------------------------------
# Tail summary + early fail.
# ---------------------------------------------------------------------------
echo ""
if (( MISSING_REQUIRED > 0 )); then
  if (( CHE_DEPS_STRICT == 1 )); then
    die "Found ${MISSING_REQUIRED} REQUIRED dev tool(s). Quick copy/paste to fix most dev boxes in one go:\n\n        python3 -m venv .venv && . .venv/bin/activate && pip install pytest ruff\n        pipx install ruff                     # optional: global ruff outside venv\n        pipx ensurepath                       # run if pipx commands aren't on PATH\n\n        # Now re-try your git commit / push — or, for midnight hotfix only:\n        #   git commit --no-verify\n        #   git push   --no-verify"
  else
    warn "${MISSING_REQUIRED} REQUIRED tool(s) missing (WARN mode — not blocking). Gates that need them will be SKIPPED."
  fi
fi

if (( MISSING_OPTIONAL > 0 )); then
  warn "${MISSING_OPTIONAL} OPTIONAL tool(s) missing — related gates skipped locally (CI still runs them)."
fi

ok "All REQUIRED development dependencies present."

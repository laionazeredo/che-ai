#!/usr/bin/env bash
#
# install-che.sh — Installs OR updates Che (this source checkout) PLUS the
#                  standalone `che-ai` / `che` CLI binaries via pipx.
#
# ###########################################################################
# # PLATFORM COMPATIBILITY (fail-fast check below):                          #
# #   ✅ Linux  (any distro with GNU coreutils + bash ≥ 4.4 + python3 ≥ 3.9) #
# #   ✅ macOS  (Monterey / 12+, homebrew strongly recommended for pipx/git) #
# #   ❌ Windows PowerShell / CMD: NOT SUPPORTED natively.                   #
# #      Use WSL2 (Ubuntu 22.04 LTS recommended) inside Windows instead.    #
# ###########################################################################
#
# SYMLINK-BASED INSTALL (Sep 2026 rebrand): the source-of-truth (SSoT) checkout
# lives at ~/.che-ai. IDE homes (e.g. ~/.trae, ~/.claude, ~/.codex, ~/.cursor)
# are wired as SYMLINK SURFACES into it by scripts/setup-adapters.sh and the
# adapters/*/install.sh scripts. This installer therefore NEVER copies content
# when SOURCE and TARGET are the same folder (the normal case): it validates the
# checkout, installs the CLI and delegates the IDE wiring to the adapters.
#
# THREE SYNC MODES (auto-detected):
#   0) in-place  (SOURCE == TARGET, the normal case): the checkout IS the SSoT.
#        - No file copy and no symlink: the content is already where it belongs.
#        - Only blacklist structure + CLI install + adapter wiring run.
#
#   1) --apply (fresh install FROM an external SOURCE checkout):
#        - If target ALREADY EXISTS → mv entire $target → $target.bak-YYYYMMDD-HHMMSS
#        - Copies the whitelist from source to a clean empty target (real checkout).
#        - Blacklist (user_rules, bindings/registry.jsonl, memory) is NOT copied
#          from source; only empty folder structure is recreated in target.
#        - Installs `che-ai` + `che` CLI globally via `pipx install -e <target>`
#          (fallback `pip3 install --user -e <target>` if pipx missing, with warning).
#        - Use this mode for first installation OR for a 100% clean reset.
#
#   2) --update --apply (NON-DESTRUCTIVE, symlink-based update. Recommended):
#        - NEVER renames the entire target (no global mv).
#        - NEVER touches BLACKLIST (user_rules/*, bindings/registry.jsonl, memory/).
#        - For EACH whitelist item: `ln -sfn` source → target (per item), so a
#          later `git pull` on SOURCE is reflected immediately, no re-install.
#        - An existing REAL file/dir that would be replaced is FIRST moved to
#          <item>.bak-<TIMESTAMP> in the same directory (manual rollback = rename back).
#        - Items that exist ONLY in target (user's custom skills) → NEVER touched.
#        - Re-installs / upgrades CLI binaries in place (`pipx install -e <target> --force`).
#
# USAGE (inside the Che source checkout folder, or --source=/custom/che-source):
#   ./scripts/install-che.sh                                        # Default DRY-RUN (fresh install).
#   ./scripts/install-che.sh --apply                                # REAL fresh install.
#   ./scripts/install-che.sh --update                               # DRY-RUN NON-DESTRUCTIVE update mode.
#   ./scripts/install-che.sh --update --apply                       # REAL NON-DESTRUCTIVE update.
#   ./scripts/install-che.sh --apply --no-cli                       # Skip the pipx CLI install step.
#   ./scripts/install-che.sh --target ~/.che-ai                     # New default (Sep 2026+).
#   # Legacy installs (pre-Sep 2026 originally in ~/.trae):
#   ./scripts/install-che.sh --target ~/.trae                       # Explicit legacy path.
#   ./scripts/install-che.sh --source ~/Downloads/che-ai-export --apply
#   ./scripts/install-che.sh -h
#
# WHAT ABOUT THE IDE SLASH COMMANDS (/che-workspace, /che-spec, /che-act, /che-ship, ...)?
#   THEY CONTINUE TO EXIST AND ARE THE RECOMMENDED ENTRY POINT FOR AGENTIC / CREATIVE WORK.
#   The `che-ai` CLI is the structural ADMINISTRATIVE SIDECAR for team bootstrap, workspace setup,
#   trash-safe removal, structural ops (workspace/project/config/state/task/rag/export/eject), CI
#   wiring, and offline work.
#   You use IDE slash-commands inside Claude Code for agent-driven creative tasks (LLM calls, spec
#   writing, code review, PR bodies) and the terminal `che-ai` CLI for team admin, workspace setup,
#   listings/exports, and structural operations (deterministic, works offline).
#
# WHITELIST (what is synchronised from source → target):
#   Root files: README.md, CHE_RULES.md, CHE_COMMANDS.md,
#               REFERENCE_USER_RULES_MINIFIED.md, package.json, pnpm-lock.yaml,
#               tsconfig.json, hooks.json, pyproject.toml, .gitignore.
#   Directories: che_core/, commands/, contracts/, skills/, hooks/, scripts/,
#                permission/, tests/, docs/.
#   NOTE: hooks.json is a TEMPLATE holding the __HARNESS_TARGET__ placeholder.
#         Each IDE surface renders its own copy (see adapters/*/install.sh).
#
# ABSOLUTE BLACKLIST (what the script NEVER copies, NEVER deletes, NEVER touches):
#   user_rules/* (except .gitkeep if folder is empty and needs placeholder)
#   bindings/registry.jsonl
#   memory/
#   node_modules/, pnpm-debug.log, *.bak-*, .git/, __pycache__/, *.egg-info/
#   Any file/folder in target that DOES NOT exist in source is NEVER touched.
#
# SECURITY GUARANTEES (fail-closed):
#   * Update mode NEVER destroys data: any whitelist item that WOULD be replaced
#     is first moved to <item>.bak-<TIMESTAMP> in the SAME directory, BEFORE the
#     new symlink is created. Manual rollback is just renaming .bak-* back.
#   * No `rm -rf` of user content in this script. Copy + individual backup move only.
#   * Default ALWAYS dry-run. --apply is mandatory to write.
#   * CLI install step never runs unless you pass --apply. If pipx is missing,
#     the fallback pip3 step prints a L-OUD yellow warning telling you to install pipx.

set -euo pipefail

APPLY=0
UPDATE=0
NO_CLI=0
SOURCE=""
TARGET="${HOME}/.che-ai"
REPO_URL="https://github.com/laionazeredo/che-ai.git"
# Backward-compat auto-detect (Sep 2026 rebrand: ~/.trae → ~/.che-ai).
# If the new default does NOT exist yet AND the user originally installed Che
# inside the legacy ~/.trae (historical accident: Che was born inside the Trae
# IDE home folder before becoming a standalone multi-agent harness), silently
# reuse the legacy path so existing installations keep working after upgrade.
# Only triggers if legacy is a valid Che checkout (avoids collision with a
# real/empty Trae IDE home folder that happens to share the same name).
if [ ! -e "$TARGET" ] && [ -f "${HOME}/.trae/CHE_RULES.md" ]; then
  TARGET="${HOME}/.trae"
fi

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
    --no-cli)
      NO_CLI=1
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
      sed -n '2,/^set -euo pipefail$/p' "$0" | sed '/^set -euo pipefail$/d; s/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

# ==========================================================================
# PLATFORM COMPATIBILITY (fail-fast: native Windows shells must use WSL2)
# ==========================================================================
OS_NAME="$(uname -s 2>/dev/null || true)"
case "${OS_NAME}" in
  Linux|Darwin)
    : # Supported platform.
    ;;
  MINGW*|MSYS*|CYGWIN*)
    cat >&2 <<'WSL_HELP'
ERROR: Native Windows shells (PowerShell / CMD / Git-Bash) are NOT supported.

Che requires a POSIX userland. Install WSL2 and run this script from inside it:

    wsl --install -d Ubuntu-22.04
    # then inside the Ubuntu shell:
    sudo apt update && sudo apt install -y python3 python3-pip pipx git
    cd ~/.che-ai && ./scripts/install-che.sh --apply
WSL_HELP
    exit 5
    ;;
  *)
    echo "WARNING: unrecognised OS '${OS_NAME}'. Che targets Linux and macOS." >&2
    echo "         Continuing in best-effort mode; expect pipx/git issues." >&2
    ;;
esac

# ==========================================================================
# CLEANUP (temporary clones + rendered files)
# ==========================================================================
CLEANUP_PATHS=""
cleanup() {
  # shellcheck disable=SC2086
  [ -n "$CLEANUP_PATHS" ] && rm -rf $CLEANUP_PATHS
  return 0
}
trap cleanup EXIT

# ==========================================================================
# RESOLVE SOURCE (the checkout we synchronise FROM)
# ==========================================================================
if [ -z "$SOURCE" ]; then
  if [ -f "CHE_RULES.md" ]; then
    SOURCE="$(pwd | sed 's:/*$::')"
  else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "${SCRIPT_DIR}/../CHE_RULES.md" ]; then
      SOURCE="$(cd "${SCRIPT_DIR}/.." && pwd)"
    else
      TMP_SOURCE="$(mktemp -d)"
      CLEANUP_PATHS="${CLEANUP_PATHS} ${TMP_SOURCE}"
      echo "→ Cloning Che source from ${REPO_URL} ..."
      git clone --depth 1 "$REPO_URL" "$TMP_SOURCE"
      SOURCE="$TMP_SOURCE"
    fi
  fi
fi
SOURCE="$(cd "$SOURCE" && pwd)"

if [ ! -f "${SOURCE}/CHE_RULES.md" ]; then
  echo "ERROR: '${SOURCE}' is not a Che checkout (CHE_RULES.md missing)." >&2
  echo "       Pass --source=<che-checkout>, or run this script from inside the checkout." >&2
  exit 2
fi

# ==========================================================================
# NORMALISE TARGET + DETECT SYNC MODE
# ==========================================================================
case "$TARGET" in
  /*) : ;;
  *) TARGET="${PWD}/${TARGET}" ;;
esac
TARGET="${TARGET%/}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
if [ "$APPLY" -eq 1 ]; then MODE_LABEL="[apply]"; else MODE_LABEL="[dry-run]"; fi

IN_PLACE=0
if [ "$SOURCE" = "$TARGET" ]; then IN_PLACE=1; fi

if [ "$IN_PLACE" -eq 1 ]; then
  MODE_NAME="in-place (source == target)"
elif [ "$UPDATE" -eq 1 ]; then
  MODE_NAME="update (symlink-based, non-destructive)"
else
  MODE_NAME="fresh-install (copy)"
fi

echo "──────────────────────────────────────────────────────────────"
echo " Che installer ${MODE_LABEL}"
echo " source : ${SOURCE}"
echo " target : ${TARGET}"
echo " mode   : ${MODE_NAME}"
echo "──────────────────────────────────────────────────────────────"

# ==========================================================================
# WHITELIST / BLACKLIST
# ==========================================================================
BLACKLIST_DIRS=( "user_rules" "memory" ".git" "node_modules" )
BLACKLIST_FILES=( "bindings/registry.jsonl" )
WHITELIST_ROOT_FILES=(
  README.md
  CHE_RULES.md
  CHE_COMMANDS.md
  REFERENCE_USER_RULES_MINIFIED.md
  package.json
  pnpm-lock.yaml
  tsconfig.json
  hooks.json
  pyproject.toml
  .gitignore
)
WHITELIST_DIRS=(
  che_core
  commands
  contracts
  skills
  hooks
  scripts
  permission
  tests
  docs
)

# Fail-closed: a single item may never be whitelisted AND blacklisted.
for b in "${BLACKLIST_DIRS[@]}" "${BLACKLIST_FILES[@]}"; do
  for w in "${WHITELIST_ROOT_FILES[@]}" "${WHITELIST_DIRS[@]}"; do
    if [ "$b" = "$w" ]; then
      echo "ERROR: '${b}' is BOTH whitelisted and blacklisted — refusing to run." >&2
      exit 3
    fi
  done
done

# ==========================================================================
# ITEM SYNC HELPERS
# ==========================================================================
# sync_file <rel-path> [src-override]
#   fresh-install → copy source → target (real file).
#   update        → symlink target → source (per item, live after `git pull`).
sync_file() {
  local rel="$1"
  local src="${2:-${SOURCE}/${rel}}"
  local dst="${TARGET}/${rel}"

  if [ ! -e "$src" ]; then
    echo "  ${rel}: missing in source → SKIP"
    return 0
  fi

  if [ -L "$dst" ]; then
    if [ "$(readlink "$dst")" = "$src" ]; then
      echo "  ${rel}: symlink already correct"
      return 0
    fi
    echo "  ${rel}: replacing stale symlink"
    [ "$APPLY" -eq 1 ] && ln -sfn "$src" "$dst"
    return 0
  fi

  if [ -e "$dst" ]; then
    echo "  ${rel}: backing up → ${rel}.bak-${TIMESTAMP}"
    [ "$APPLY" -eq 1 ] && mv "$dst" "${dst}.bak-${TIMESTAMP}"
  else
    echo "  ${rel}: + new"
  fi

  if [ "$APPLY" -eq 1 ]; then
    if [ "$UPDATE" -eq 1 ]; then ln -sfn "$src" "$dst"; else cp -R "$src" "$dst"; fi
  fi
}

# sync_dir <rel-dir>
#   fresh-install → recursive copy.
#   update        → target dir stays REAL, each child becomes its own symlink
#                   (per-item granularity; extra children in target untouched).
sync_dir() {
  local rel="$1"
  local src="${SOURCE}/${rel}"
  local dst="${TARGET}/${rel}"

  if [ ! -d "$src" ]; then
    echo "  ${rel}/: missing in source → SKIP"
    return 0
  fi

  if [ "$UPDATE" -eq 0 ]; then
    echo "  ${rel}/: copy"
    [ "$APPLY" -eq 1 ] && cp -R "$src" "$dst"
    return 0
  fi

  if [ -L "$dst" ]; then
    echo "  ${rel}/: replacing stale symlink with real dir"
    [ "$APPLY" -eq 1 ] && { rm -f "$dst"; mkdir -p "$dst"; }
  elif [ ! -e "$dst" ]; then
    echo "  ${rel}/: + new dir"
    [ "$APPLY" -eq 1 ] && mkdir -p "$dst"
  fi

  shopt -s dotglob nullglob
  local child
  for child in "$src"/*; do
    local name; name="$(basename "$child")"
    sync_file "${rel}/${name}"
  done
  shopt -u dotglob nullglob
}

# ==========================================================================
# STEP 1 — Prepare target
# ==========================================================================
if [ "$IN_PLACE" -eq 0 ] && [ -e "$TARGET" ]; then
  if [ "$UPDATE" -eq 1 ]; then
    echo "→ update mode: any replaced item is first moved to <item>.bak-${TIMESTAMP}."
  else
    echo "→ fresh-install: moving existing target → ${TARGET}.bak-${TIMESTAMP}"
    [ "$APPLY" -eq 1 ] && mv "$TARGET" "${TARGET}.bak-${TIMESTAMP}"
  fi
fi

if [ "$APPLY" -eq 1 ]; then
  mkdir -p "$TARGET" "${TARGET}/bindings"
fi

# ==========================================================================
# STEP 2 — Sync whitelist root files (hooks.json is RENDERED, not copied raw)
# ==========================================================================
NEEDS_PNPM_INSTALL=0
RENDERED_HOOKS_JSON="$(mktemp)"
CLEANUP_PATHS="${CLEANUP_PATHS} ${RENDERED_HOOKS_JSON}"
python3 - "${SOURCE}/hooks.json" "$RENDERED_HOOKS_JSON" "$TARGET" <<'PY'
import json
import sys
from pathlib import Path

source_path, output_path, target = map(Path, sys.argv[1:])
config = json.loads(source_path.read_text())
for event_hooks in config.get("hooks", {}).values():
    for hook in event_hooks:
        command = hook.get("command")
        if isinstance(command, str):
            hook["command"] = command.replace("__HARNESS_TARGET__", str(target))
Path(output_path).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
PY

if [ "$IN_PLACE" -eq 1 ]; then
  echo " (in-place: content already at target — item sync skipped)"
else
  for f in "${WHITELIST_ROOT_FILES[@]}"; do
    SRC="${SOURCE}/${f}"
    [ "$f" = "hooks.json" ] && SRC="$RENDERED_HOOKS_JSON"
    sync_file "$f" "$SRC"
    if [ "$f" = "package.json" ] || [ "$f" = "pnpm-lock.yaml" ]; then
      [ -e "$SRC" ] && NEEDS_PNPM_INSTALL=1
    fi
  done
fi

# ==========================================================================
# STEP 3 — Sync whitelist directories (per item)
# ==========================================================================
if [ "$IN_PLACE" -eq 0 ]; then
  for d in "${WHITELIST_DIRS[@]}"; do
    sync_dir "$d"
  done
fi

# Hook scripts must be executable (they are .py, invoked directly by the IDE).
if [ "$APPLY" -eq 1 ] && [ -d "${TARGET}/hooks" ]; then
  chmod +x "${TARGET}"/hooks/*.py 2>/dev/null || true
fi

# ==========================================================================
# STEP 4 — BLACKLIST: guarantee minimum EMPTY structure (never copies content)
# ==========================================================================
BINDINGS_README="${TARGET}/bindings/README.md"
if [ "$APPLY" -eq 1 ] && [ ! -f "$BINDINGS_README" ]; then
  cat > "$BINDINGS_README" <<'EOF'
Level 1 — registry.jsonl.
DO NOT edit manually. Sole writer = contracts helper `che_registry_append_jsonl`.
File is NEVER overwritten by install-che.sh or `git pull` (blacklisted).
EOF
fi

for d in user_rules memory; do
  FULL="${TARGET}/${d}"
  if [ ! -d "$FULL" ] && [ "$APPLY" -eq 1 ]; then
    mkdir -p "$FULL"
    touch "${FULL}/.gitkeep"
  fi
done

# Ensure user_rules/.gitkeep if user_rules folder exists but is empty.
if [ "$APPLY" -eq 1 ] && [ -d "${TARGET}/user_rules" ]; then
  if [ ! -f "${TARGET}/user_rules/.gitkeep" ]; then
    count_non_gitkeep=$(find "${TARGET}/user_rules" -maxdepth 1 -type f ! -name ".gitkeep" 2>/dev/null | wc -l)
    if [ "$count_non_gitkeep" -eq 0 ]; then
      touch "${TARGET}/user_rules/.gitkeep"
    fi
  fi
fi

# ==========================================================================
# STEP 5 — pnpm install (external source only; in-place keeps its own install)
# ==========================================================================
if [ "$IN_PLACE" -eq 0 ] && [ -f "${TARGET}/package.json" ]; then
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

# ==========================================================================
# STEP 6 — security summary (blacklist intact)
# ==========================================================================
echo ""
echo "=== ${MODE_NAME^^} ${MODE_LABEL} completed."
echo ""
echo " BLACKLIST (untouched in both modes):"
echo "   · user_rules/              (your personal rules are never copied/deleted)"
echo "   · bindings/registry.jsonl  (your local level-1 binding)"
echo "   · memory/                  (local memory data)"
echo "   · any target-only folder   (custom skills are never touched)"
echo ""

if [ "$UPDATE" -eq 1 ]; then
  echo " UPDATE MODE:"
  echo "   · New official items → symlinked (marked + new)."
  echo "   · Modified official items → old real file saved as <item>.bak-${TIMESTAMP}."
  echo "   · YOUR folders/files that don't exist in source → 100% preserved (never touched)."
  echo ""
fi

# ==========================================================================
# STEP 7 — Install standalone `che-ai` / `che` CLI binaries (pipx, pip fallback)
# ==========================================================================
install_cli_if_requested() {
  if [ "$APPLY" -eq 0 ]; then
    if [ "$NO_CLI" -eq 1 ]; then
      echo "    [dry-run] --no-cli: CLI install step SKIPPED by user."
    else
      echo "    [dry-run] Would install che-ai CLI (binaries: che-ai, che) globally via:"
      echo "              pipx install -e $TARGET --force"
      echo "              (fallback pip3 install --user -e $TARGET if pipx missing)"
    fi
    return 0
  fi

  if [ "$NO_CLI" -eq 1 ]; then
    echo "    ℹ --no-cli passed. Skipping CLI install step (IDE slash-commands still work)."
    return 0
  fi

  echo ""
  echo "==> Installing standalone CLI binaries: che-ai, che"

  if command -v pipx >/dev/null 2>&1; then
    echo "    pipx detected — installing CLI via: pipx install -e \"${TARGET}\" --force"
    local pipx_rc=0
    pipx install -e "${TARGET}" --force 2>&1 | tail -6 || pipx_rc=$?
    if [ "${pipx_rc}" -ne 0 ]; then
      echo ""
      echo "    ⚠ pipx install failed. Trying fallback (pip3 --user) instead."
      _install_cli_pip_fallback "$TARGET"
    else
      echo "    ✔ CLI installed globally. Run:  che --help   or   che-ai --help"
    fi
  else
    echo "    ⚠ pipx not found on PATH. pipx is RECOMMENDED for CLI Python apps."
    echo "      To install pipx (retry after this command completes):"
    echo "        Debian/Ubuntu:  sudo apt-get install -y pipx  &&  pipx ensurepath"
    echo "        macOS/Homebrew: brew install pipx  &&  pipx ensurepath"
    echo "      Falling back to pip3 install --user ..."
    _install_cli_pip_fallback "$TARGET"
  fi
}

_install_cli_pip_fallback() {
  local tgt="$1"
  local py
  py="$(command -v python3 2>/dev/null || true)"
  if [ -z "$py" ]; then
    echo "    ❌ python3 not on PATH. CLI NOT installed."
    echo "       Install python3 ≥ 3.9, then re-run:  pipx install -e \"${tgt}\" --force"
    return 4
  fi
  local pip_rc=0
  "$py" -m pip install --user -e "${tgt}" 2>&1 | tail -4 || pip_rc=$?
  if [ "${pip_rc}" -ne 0 ]; then
    # PEP 668 externally-managed environment? Retry with --break-system-packages.
    "$py" -m pip install --user -e "${tgt}" --break-system-packages 2>&1 | tail -4 || pip_rc=$?
  fi
  if [ "${pip_rc}" -eq 0 ]; then
    local user_bin
    user_bin="$("$py" -c 'import site, os; print(os.path.join(site.getuserbase(), "bin"))' 2>/dev/null || true)"
    echo "    ⚠ Installed via pip --user. If \$PATH doesn't include '${user_bin}', run:"
    echo "         export PATH=\"\${PATH}:${user_bin}\"    # (add to ~/.bashrc or ~/.zshrc to persist)"
    echo "    Then run:  che --help"
    echo ""
    echo "    Strongly recommend installing pipx and re-running this script for a clean install."
  else
    echo ""
    echo "    ❌ CLI install FAILED. You can manually install later:"
    echo "         pipx install -e \"${tgt}\" --force"
  fi
}

if [ "$APPLY" -eq 0 ]; then
  echo "⚠ dry-run. To APPLY for real, use the --apply flag."
  echo "Example: curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply"
  install_cli_if_requested
else
  echo "✔ target ready at $TARGET"
  install_cli_if_requested
  echo ""
  echo " Post-check checklist:"
  echo "  1. Open Claude Code again (or reload)."
  echo "  2. Confirm ${TARGET}/README.md exists."
  echo "  3. Smoke : bash $TARGET/scripts/install-che.sh -h"
  echo "  4. CLI   : che --help   (or che-ai --help)"
  echo "  5. IDE slash-commands (/che-workspace, /che-project, /che-spec, /che-act,"
  echo "     /che-ship, /che-review, [examples of community custom skills:"
  echo "     /figma-pixel-check, /flockr-*, /my-company-*, etc.])"
  echo "     → CONTINUE TO EXIST inside the IDE as the primary path for agentic/creative work."
  echo "     They are NOT removed or deprecated — the terminal CLI is the structural administrative sidecar."
  if [ "$UPDATE" -eq 1 ]; then
    echo "  6. Manual rollback: to undo a file, mv <file>.bak-${TIMESTAMP} <file>"
  fi

  # FINAL STEP: wire the IDE surfaces (Claude Code, Codex, Cursor, Trae).
  if [ -f "$TARGET/scripts/setup-adapters.sh" ]; then
    bash "$TARGET/scripts/setup-adapters.sh"
  fi

  # FINAL FINAL STEP: install local Git hooks when TARGET is the Che repo itself.
  if [ -d "$TARGET/.git" ] && [ -f "$TARGET/scripts/install-git-hooks.sh" ]; then
    echo ""
    echo "  7. Git hooks (pre-commit / pre-push): installing into $TARGET/.git/hooks/"
    bash "$TARGET/scripts/install-git-hooks.sh" || true
  fi
fi

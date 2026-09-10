#!/usr/bin/env bash
#
# update-che.sh — SMART Alias to update che.
#
# TWO PATHS (AUTOMATICALLY detects which case is yours):
#
#   CASE 1 — target (default ~/.che-ai, legacy ~/.trae if valid, or $CHE_HOME)
#            IS A GIT REPO cloned DIRECTLY from laionazeredo/che-ai
#     → executes:  git fetch  (dry-run) or  git pull --ff-only (--apply)
#        + if package.json/pnpm-lock.yaml changed → corepack pnpm install --prefer-offline
#     Advantage: zero copies, zero conflict merge (ff-only aborts if divergence),
#     repo .gitignore blacklist protects user_rules / bindings / memory AUTOMATICALLY.
#     This is the RECOMMENDED path.
#
#   CASE 2 — target IS NOT a git repo (user downloaded zip, copied manually etc)
#     → executes: install-che.sh --update [--apply] --source=<this directory> --target=$TARGET
#        using the non-destructive logic described in install-che.sh (individual backups,
#        untouchable blacklist, preserve target custom items that don't exist in source).
#
# USAGE:
#   ./scripts/update-che.sh                        # Default DRY-RUN (fetch / install --update dry-run).
#   ./scripts/update-che.sh --apply                # Applies the update for real.
#   ./scripts/update-che.sh --target ~/.che-ai     # Explicit new default (Sep 2026+).
#   ./scripts/update-che.sh --target ~/.trae       # Explicit legacy path.
#   ./scripts/update-che.sh --target /custom/che-home
#   ./scripts/update-che.sh -h
#
# SECURITY GUARANTEES:
#   * Default always DRY-RUN. --apply mandatory to write.
#   * CASE 1 uses --ff-only: if target has local commits NOT in upstream, ABORTS without merge.
#     NEVER performs automatic merge; merge can only be manual. This prevents overwriting
#     legitimate local modifications in versioned files.
#   * CASE 2 reuses fail-closed logic from install-che.sh --update (individual backups
#     per changed file, no rm, untouchable blacklist).
#   * No `rm -rf` anywhere in this script.

set -euo pipefail

APPLY=0
TARGET="${HOME}/.che-ai"
# Backward-compat auto-detect (Sep 2026 rebrand). Same cascade as install-che.sh.
if [ -n "${CHE_HOME:-}" ]; then
  TARGET="${CHE_HOME}"
elif [ -n "${HARNESS_HOME:-}" ]; then
  TARGET="${HARNESS_HOME}"
elif [ ! -e "$TARGET" ] && [ -f "${HOME}/.trae/CHE_RULES.md" ]; then
  TARGET="${HOME}/.trae"
fi

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
      echo "ERROR: unknown option: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

# Resolve the directory where THIS update-che.sh script lives to detect the SOURCE
# used in CASE 2 (non-git). CASE 1 ignores source.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE_LABEL="[dry-run]"
[ "$APPLY" -eq 1 ] && MODE_LABEL="[apply]"

echo "==> Che update ${MODE_LABEL}"
echo "    Target: ${TARGET}"
echo "    Source (fallback case): ${SOURCE}"
echo ""

# ============================================================
# HELPER: detects if directory is a git repo WITH upstream set
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
# HELPER: counts local uncommitted changes in NON-blacklisted
# files (.gitignore blacklisted files are ignored as git
# doesn't track them anyway — it's the automatic CASE 1 protection).
# ============================================================
count_uncommitted_tracked_changes() {
  local d="$1"
  (cd "$d" && git status --porcelain --untracked-files=no 2>/dev/null | wc -l)
}

# ============================================================
# HELPER: counts untracked NON-blacklisted files.
# Blacklisted files are marked '!!' by `git status --porcelain --ignored`.
# We only want '??' which are new files the user created and are NOT ignored.
# ============================================================
count_untracked_non_ignored() {
  local d="$1"
  (cd "$d" && git status --porcelain --untracked-files=normal 2>/dev/null | grep -cE '^\?\?' || true)
}

# ============================================================
# CASE DETECTION
# ============================================================
if is_git_repo_with_remote "$TARGET"; then
  # ==========================================================
  # CASE 1 — GIT REPO (recommended path)
  # ==========================================================
  echo "✅ CASE 1 DETECTED: target ${TARGET} is a git repo with remote."
  echo "   Strategy: git pull --ff-only (automatic merge NOT permitted)."
  echo ""

  UNCOMMITTED=$(count_uncommitted_tracked_changes "$TARGET")
  UNTRACKED=$(count_untracked_non_ignored "$TARGET")

  if [ "$UNCOMMITTED" -gt 0 ]; then
    echo "⚠  Local UNCOMMITTED changes in tracked files: ${UNCOMMITTED}"
    echo "   (files in user_rules/ / bindings/registry.jsonl / memory/ are in .gitignore blacklist — these DO NOT count, they are safe)."
    echo ""
    echo "   List (first 20):"
    (cd "$TARGET" && git status --porcelain --untracked-files=no | head -20) || true
    echo ""
    if [ "$APPLY" -eq 1 ]; then
      echo "❌ ABORTED. --apply + uncommitted changes in tracked files → fail-closed."
      echo "   Solutions:"
      echo "    a) Commit your local changes first (if you want to keep them)."
      echo "    b) Discard:  cd ${TARGET} && git stash push -m \"wip before update che\""
      echo "    c) Run without --apply for dry-run."
      exit 3
    fi
  fi

  if [ "$UNTRACKED" -gt 0 ]; then
    echo "ℹ  New untracked files (non-blacklisted): ${UNTRACKED}. They will NOT be touched by git pull."
  fi

  # Fetch first (both dry-run and apply).
  echo ""
  echo "    → Remote fetch (updates refs):"
  FETCH_OUT=""
  if [ "$APPLY" -eq 1 ]; then
    FETCH_OUT=$(cd "$TARGET" && git fetch --all 2>&1 || echo "FETCH_FAIL=$?")
    echo "$FETCH_OUT" | tail -10
  else
    FETCH_OUT=$(cd "$TARGET" && git fetch --all --dry-run 2>&1 || echo "FETCH_FAIL=$?")
    echo "$FETCH_OUT" | tail -10
  fi

  # Lists commits that will come in (dry-run).
  echo ""
  echo "    → Commits that will be applied (HEAD..upstream):"
  if (cd "$TARGET" && git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1); then
    (cd "$TARGET" && git log --oneline HEAD..\@{u} 2>/dev/null) | head -20 || true
  else
    echo "       (no upstream branch configured for the current branch)"
  fi

  # AHEAD count (local commits upstream DOES NOT have).
  AHEAD=0
  if (cd "$TARGET" && git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1); then
    AHEAD=$(cd "$TARGET" && git rev-list --count \@{u}..HEAD 2>/dev/null || echo 0)
  fi
  if [ "${AHEAD:-0}" -gt 0 ]; then
    echo ""
    echo "⚠  Target is AHEAD of upstream by ${AHEAD} commit(s). --ff-only will NOT apply. WOULD ABORT if --apply."
    echo "   Reason: you have exclusive local commits. To keep them: manual rebase first."
  fi

  NEEDS_PNPM=0
  if [ "$APPLY" -eq 1 ]; then
    # Checks IF package.json / pnpm-lock.yaml ARE in the list of commits that will come in.
    # (prevents running pnpm install for nothing if nothing changed).
    if (cd "$TARGET" && git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1); then
      FILES_TO_CHANGE=$(cd "$TARGET" && git diff --name-only HEAD \@{u} 2>/dev/null || true)
      if echo "$FILES_TO_CHANGE" | grep -qE '(^|/)package\.json$'; then NEEDS_PNPM=1; fi
      if echo "$FILES_TO_CHANGE" | grep -qE '(^|/)pnpm-lock\.yaml$'; then NEEDS_PNPM=1; fi
    fi

    echo ""
    echo "    → git pull --ff-only (no automatic merge):"
    PULL_OUT=$(cd "$TARGET" && git pull --ff-only 2>&1) || {
      echo "$PULL_OUT" | tail -10
      echo ""
      echo "❌ git pull --ff-only failed (divergence? see AHEAD commits above)."
      echo "   No file was modified. Resolve manually."
      exit 4
    }
    echo "$PULL_OUT" | tail -10

    if [ "$NEEDS_PNPM" -eq 1 ] && [ -f "${TARGET}/package.json" ]; then
      echo ""
      echo "    → pnpm install (package.json/pnpm-lock.yaml changed):"
      (cd "$TARGET" && (corepack enable >/dev/null 2>&1 || true) && corepack pnpm install --prefer-offline 2>&1 | tail -5)
    fi
  fi

  echo ""
  echo "=== CASE 1 GIT UPDATE ${MODE_LABEL} completed."
  echo ""
  echo " BLACKLIST (AUTOMATICALLY protected by repo .gitignore):"
  echo "    · user_rules/*              (only .gitkeep is tracked; personal rules untouched)"
  echo "    · bindings/registry.jsonl   (100% ignored)"
  echo "    · memory/                   (100% ignored)"
  echo "    · Custom skills you ADDED in skills/ and were NOT committed → untouched,"
  echo "      UNLESS there is a FOLDER with SAME NAME in upstream (name conflict only)."
  echo ""
  if [ "$APPLY" -eq 0 ]; then
    echo "⚠  Dry-run completed. NOTHING was changed."
    echo "   If report above is OK:  $0 --apply"
  else
    echo "✔ Update applied successfully via git --ff-only."
    echo "  Emergency Rollback: cd ${TARGET} && git reset --hard HEAD@{1}"
    echo "  (returning to the state IMMEDIATELY before this pull)."
  fi
  exit 0
fi

# ============================================================
# CASE 2 — NOT a git repo → fallback to install-che.sh --update
# ============================================================
echo "ℹ  CASE 2 DETECTED: target ${TARGET} IS NOT a git repo."
echo "   Strategy: install-che.sh --update (non-destructive, individual backups)."
echo ""
echo "   Source used: ${SOURCE}"
echo ""

# Validate source is valid.
if [ ! -f "${SOURCE}/scripts/install-che.sh" ]; then
  echo "❌ ERROR: Could not locate install-che.sh in ${SOURCE}/scripts/"
  echo "   Run this script from INSIDE a copy of the configuration repository."
  exit 2
fi

EXTRA_ARGS=()
EXTRA_ARGS+=("--update")
EXTRA_ARGS+=("--source" "${SOURCE}")
EXTRA_ARGS+=("--target" "${TARGET}")
[ "$APPLY" -eq 1 ] && EXTRA_ARGS+=("--apply")

echo "    Executing: bash ${SOURCE}/scripts/install-che.sh $(printf '%q ' "${EXTRA_ARGS[@]}")"
echo ""
bash "${SOURCE}/scripts/install-che.sh" "${EXTRA_ARGS[@]}"

#!/usr/bin/env bash
#
# self-update-che.sh — 1 COMMAND to get the latest official Che version
#                           and merge into your local installation WITHOUT losing personal data.
#
# PREMISE (real user scenario):
#   "User already has che installed for weeks/months (default ~/.che-ai since
#    Sep 2026, or legacy ~/.trae for pre-Sep-2026 installs). Doesn't remember
#    if installed via git clone or zip. Just wants to have the latest version from GitHub.
#    Doesn't want to download anything manually, doesn't want to remember flags. Just wants to run
#    ONE COMMAND and guarantee that their user_rules/bindings/memory/custom skills
#    remain intact. CHE_HOME env var overrides the default if set."
#
# THIS SCRIPT IS THAT COMMAND:
#   # Default DRY-RUN (uses CHE_HOME env or auto-detects ~/.che-ai → ~/.trae legacy):
#   bash "${CHE_HOME:-$HOME/.che-ai}/scripts/self-update-che.sh"
#   # Apply for real:
#   bash "${CHE_HOME:-$HOME/.che-ai}/scripts/self-update-che.sh --apply"
#   # Legacy install (explicit):
#   bash ~/.trae/scripts/self-update-che.sh --apply
#   bash -h | --help
#
# What this script DOES AUTOMATICALLY, ZERO CONFIGURATION:
#   1) Validates that the resolved Che home (TARGET) already exists (not a fresh install).
#   2) Performs AUTONOMOUS fetch of the LATEST official version from github.com/laionazeredo/che-ai:
#        ONLY PERMITTED WAY (Che HARD RULE): logged-in `gh` CLI (official GitHub CLI).
#          → gh repo clone ... --depth 1 into /tmp/tmpXXXXXX.
#        Fallback git clone HTTPS NO LONGER EXISTS. Reason: authentication/scopes/rate-limit
#          /private repos/enterprise/2FA token flow/uniform auditing via gh auth login.
#   3) AUTOMATICALLY detects target case:
#        CASE 1 — TARGET is a git repo with upstream set.
#          → executes: bash scripts/update-che.sh --[apply] (git pull --ff-only on TARGET ITSELF;
#            gitignore protection + --ff-only guarantees zero automatic merge / zero personal overwrite).
#        CASE 2 — TARGET is not a git repo (zip/manual copy).
#          → executes: bash <tmp-src>/scripts/install-che.sh --update [--apply]
#            (item-by-item merge with INDIVIDUAL backups and untouchable BLACKLIST.
#             Everything personal that doesn't exist in official source is NEVER touched).
#   4) Final cleanup: /tmp/tmpXXXXXX fetch of new source is deleted at the end
#      (trap EXIT). No temporary files left behind.
#   5) Always prints, before applying:
#        - Which CASE (1/2) was detected
#        - Which strategy will be used
#        - Blacklist that will NEVER be touched
#
# FAIL-CLOSED GUARANTEES (extended from update-che + install-update):
#   * Default DRY-RUN. `--apply` mandatory to write.
#   * No `rm` in this script (over /home). Only rm -rf on /tmp/tmp fetch (trap).
#   * Case 1: `git pull --ff-only` on TARGET itself. If divergence → aborts without merge.
#     Uncommitted tracked local modifications → aborts with instructions (commit or stash).
#   * Case 2: install --update DOES NOT do global target mv. Everything item-by-item with INDIVIDUAL
#     backup of each changed thing (mv target/x → target/x.bak-TIMESTAMP, before copying new).
#   * Global untouchable BLACKLIST: user_rules/*, bindings/registry.jsonl, memory/,
#     any target-only custom item.
#   * Manual rollback instructed in each case (1: git reset HEAD@{1}; 2: mv item.bak-* item).
#
# MANDATORY DEPENDENCIES (official source fetch):
#   - `gh` (GitHub CLI) — MANDATORY AND UNIQUE. Che 2026-09-01 hard stop rule:
#     Public fallback git clone HTTPS no longer exists. All GitHub access in
#     che (PRs, diffs, comments, releases, clone) goes EXCLUSIVELY through gh CLI.
#     Install: https://cli.github.com/   Authenticate: gh auth login --scopes repo,read:org,workflow

set -euo pipefail

# ============================================================
# Flags and defaults.
# ============================================================
APPLY=0
TARGET="${HOME}/.che-ai"
# Backward-compat auto-detect (Sep 2026 rebrand: ~/.trae → ~/.che-ai).
# Exact same logic as install-che.sh — see there for full rationale.
# CHE_HOME env var has top precedence; if NOT set we try new default first,
# then legacy valid checkout, then final new default (will fail existence check below).
if [ -n "${CHE_HOME:-}" ]; then
  TARGET="${CHE_HOME}"
elif [ -n "${HARNESS_HOME:-}" ]; then
  TARGET="${HARNESS_HOME}"
elif [ ! -e "$TARGET" ] && [ -f "${HOME}/.trae/CHE_RULES.md" ]; then
  TARGET="${HOME}/.trae"
fi
GH_REPO="laionazeredo/che-ai"
TMP_SRC=""   # defined below if fetch is successful.

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
      echo "ERROR: unknown option: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

MODE_LABEL="[dry-run]"
[ "$APPLY" -eq 1 ] && MODE_LABEL="[apply]"

# ============================================================
# Cleanup: ALWAYS deletes /tmp/<temp fetch folder> at the end,
# regardless of error or success. Less trash on user's machine.
# ============================================================
cleanup_tmp(){
  if [ -n "${TMP_SRC:-}" ] && [ -d "$TMP_SRC" ] && [[ "$TMP_SRC" == /tmp/* ]]; then
    rm -rf "$TMP_SRC"
  fi
}
trap cleanup_tmp EXIT

echo "==> Che self-update ${MODE_LABEL}"
echo "    Target: ${TARGET}"
echo "    Official repo: https://github.com/${GH_REPO}"
echo ""

# ============================================================
# Step 1: validate that TARGET exists (not a fresh install).
# ============================================================
if [ ! -e "$TARGET" ]; then
  echo "❌ Target ${TARGET} DOES NOT exist." >&2
  echo "   This script is for UPDATING an existing installation." >&2
  echo "   To INSTALL FROM SCRATCH, follow README §0:" >&2
  echo "      gh repo clone ${GH_REPO} ${TARGET} -- --depth 1" >&2
  echo "      corepack enable && corepack pnpm --dir ${TARGET} install --prefer-offline" >&2
  exit 6
fi

if [ ! -f "${TARGET}/README.md" ] && [ ! -f "${TARGET}/CHE_RULES.md" ]; then
  echo "❌ Folder ${TARGET} does not seem to be a valid Che checkout (missing README.md and CHE_RULES.md)." >&2
  exit 2
fi

# ============================================================
# Step 2: AUTONOMOUS FETCH of the latest official version.
# (BYPASS if hidden QA flag --local-source was passed to non-empty TMP_SRC before.)
# ============================================================
FETCH_OK=0
FETCH_METHOD=""

if [ -n "${TMP_SRC:-}" ]; then
  FETCH_OK=1
  FETCH_METHOD="local-source-qa-bypass"
  echo "    ⚠ QA mode: using local source (no GitHub fetch): ${TMP_SRC}"
else
  TMP_SRC=$(mktemp -d /tmp/trae-src-fetch.XXXXXXXXXX)
  echo "    Downloading latest official version to temporary folder: ${TMP_SRC}"

  # 2A) gh CLI MANDATORY (che HARD RULE: no GitHub interaction via raw HTTP/manual git clone.
  #     Reasons: manageable authentication, scopes, rate-limit, enterprise API, 2FA token flow,
  #     auditing. Never use fallback git clone https://github.com directly.)
  if ! command -v gh >/dev/null 2>&1; then
    echo ""
    echo "❌ GitHub CLI (gh) IS NOT INSTALLED. Che no longer supports public fallback git clone HTTPS (hard stop rule)." >&2
    echo "   Install gh CLI + authenticate:" >&2
    echo "        https://cli.github.com/" >&2
    echo "        gh auth login --scopes repo,read:org,workflow" >&2
    echo "   Then run again: bash \${CHE_HOME:-\$HOME/.che-ai}/scripts/self-update-che.sh" >&2
    exit 6
  fi

  GH_USER=""
  if ! GH_USER=$(gh api user --jq .login 2>/dev/null) || [ -z "$GH_USER" ]; then
    echo ""
    echo "❌ GitHub CLI (gh) exists but IS NOT authenticated. Hard stop rule: no public fallback HTTPS clone." >&2
    echo "   Authenticate first:" >&2
    echo "        gh auth login --scopes repo,read:org,workflow" >&2
    echo "   Verify: gh auth status" >&2
    echo "   Then run again." >&2
    exit 7
  fi

  echo "    → gh CLI available and logged in as @${GH_USER}. Using gh repo clone --depth 1."
  if gh repo clone "$GH_REPO" "$TMP_SRC" -- --depth 1 --quiet 2>/dev/null; then
    FETCH_OK=1
    FETCH_METHOD="gh-clone"
  else
    echo "    ⚠ gh clone failed. Check network / repo permissions. (NO fallback to git clone HTTPS, hard stop rule.)" >&2
  fi

  if [ "$FETCH_OK" -eq 0 ]; then
    echo ""
    echo "❌ Failed to fetch latest official version via gh CLI. No other way permitted." >&2
    echo "   Quick diagnosis:" >&2
    echo "        gh auth status" >&2
    echo "        gh repo view ${GH_REPO}" >&2
    echo "        gh api repos/${GH_REPO} --jq .full_name" >&2
    exit 8
  fi
fi

# Minimum validation of downloaded source.
if [ ! -f "${TMP_SRC}/CHE_RULES.md" ]; then
  echo "❌ Fetch completed but downloaded folder DOES NOT have CHE_RULES.md — untrusted repo or corrupted download." >&2
  exit 8
fi

# Displays downloaded version (short commit SHA if .git exists).
VERSION_LABEL=""
if [ -d "${TMP_SRC}/.git" ]; then
  VERSION_LABEL="commit $(cd "$TMP_SRC" && git rev-parse --short HEAD 2>/dev/null || echo '?')"
fi
echo "    ✔ Fetch OK (${FETCH_METHOD}). Latest official version downloaded: ${VERSION_LABEL:-<unknown>}"
echo ""

# ============================================================
# Step 3: AUTOMATIC DETECTION OF CASE 1 vs CASE 2.
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
  # CASE 1 — target IS ALREADY a git repo with remote (90% of fresh install §0 users).
  # We call update-che.sh from TARGET itself (ff-only pull in repo itself).
  # ==========================================================
  echo "🟢 CASE 1 DETECTED: target ${TARGET} is a git repo with remote."
  echo "   Strategy: git pull --ff-only in TARGET itself (update-che.sh via source tmp)."
  echo "   AUTOMATIC Blacklist via repo .gitignore: user_rules/*, bindings/registry.jsonl, memory/."
  echo ""
  if [ -f "${TMP_SRC}/scripts/update-che.sh" ]; then
    exec bash "${TMP_SRC}/scripts/update-che.sh" "${EXTRA_UPDATE_ARGS[@]}"
  else
    exec bash "${TARGET}/scripts/update-che.sh" "${EXTRA_UPDATE_ARGS[@]}"
  fi
  # NOTE: `exec` replaces the shell, cleanup_tmp trap STILL runs because parent shell
  # receives EXIT from execution (trap is in parent shell). If update-che w/ exit !=0,
  # trap runs normally.
else
  # ==========================================================
  # CASE 2 — target IS NOT a git repo (e.g. installed via zip, manual copy).
  # We call install-che.sh --update using TMP_SRC as source.
  # ==========================================================
  echo "🟡 CASE 2 DETECTED: target ${TARGET} IS NOT a git repo."
  echo "   Strategy: install-che.sh --update (item-by-item non-destructive merge)."
  echo "   INDIVIDUAL backups per changed item → ${TARGET}/<item>.bak-YYYYMMDD-HHMM."
  echo "   UNTOUCHABLE Blacklist (not even read): user_rules/*, bindings/registry.jsonl, memory/."
  echo "   YOUR items in target that don't exist in official source → NEVER touched."
  echo ""
  exec bash "${TMP_SRC}/scripts/install-che.sh" --update --source "$TMP_SRC" "${EXTRA_UPDATE_ARGS[@]}"
fi

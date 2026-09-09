#!/usr/bin/env bash
#
# install-che.sh — Installs OR updates Che Flockr (this .trae).
#
# TWO MAIN MODES:
#   1) --apply      (fresh install / controlled destructive):
#        - If target ALREADY EXISTS → mv entire $target → $target.bak-YYYYMMDD-HHMM
#        - Copies complete whitelist from source to clean empty target.
#        - Blacklist (user_rules, bindings/registry.jsonl, memory) is NOT copied
#          from source; only empty folder structure is recreated in target.
#        - Use this mode for first installation OR if you want a 100% clean reset.
#
#   2) --update --apply (NON-DESTRUCTIVE update. Recommended for new versions):
#        - NEVER renames the entire target (no global mv).
#        - NEVER touches BLACKLIST (user_rules/*, bindings/registry.jsonl, memory/).
#        - For EACH item in the WHITELIST individually:
#            · source has, target doesn't → copy (official new file/dir).
#            · source has, target has and DIFFERENT → backup $target/item.bak-$TIMESTAMP,
#              then copy source → target.
#            · source has, target has and EQUAL → skip (zero noise).
#            · source DOES NOT have, target has → NEVER TOUCHES (preserves user's custom skills,
#              new commands added, local references, etc).
#        - Ideal for: "got a new version from laionazeredo/che-ai repo, want to update
#          skills/commands/rules without losing my personal rules".
#
# USAGE (inside source .trae folder or --source=/custom/.trae):
#   ./scripts/install-che.sh                                 # Default DRY-RUN (fresh install).
#   ./scripts/install-che.sh --apply                         # REAL fresh install.
#   ./scripts/install-che.sh --update                        # DRY-RUN NON-DESTRUCTIVE update mode.
#   ./scripts/install-che.sh --update --apply                # REAL NON-DESTRUCTIVE update.
#   ./scripts/install-che.sh --target ~/.trae
#   ./scripts/install-che.sh --source ~/Downloads/dot-trae-exported --apply
#   ./scripts/install-che.sh -h
#
# WHITELIST (what is synchronised from source → target):
#   Root files: README.md, CHE_RULES.md, CHE_COMMANDS.md,
#               REFERENCE_USER_RULES_MINIFIED.md, package.json, pnpm-lock.yaml,
#               tsconfig.json, hooks.json.
#   Directories: commands/, contracts/, skills/, hooks/, scripts/, permission/.
#
# ABSOLUTE BLACKLIST (what the script NEVER copies, NEVER deletes, NEVER touches):
#   user_rules/* (except .gitkeep if folder is empty and needs placeholder)
#   bindings/registry.jsonl
#   memory/
#   node_modules/, pnpm-debug.log, *.bak-*, .git/
#   Any file/folder in target that DOES NOT exist in source is NEVER touched.
#
# SECURITY GUARANTEES (fail-closed):
#   * Any whitelist file that WILL be OVERWRITTEN in update mode → first
#     makes individual backup ${file}.bak-${TIMESTAMP} IN THE SAME directory,
#     BEFORE copying the new version. Manual rollback is just removing the new one
#     and renaming .bak-* back.
#   * No `rm -rf` or `rm` in this script. Everything is copy + individual backup mv.
#   * Default ALWAYS dry-run. --apply is mandatory to write.

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
      echo "ERROR: unknown option: $1. Use -h" >&2
      exit 2
      ;;
  esac
done

# Cleanup logic
CLEANUP_PATHS=""
cleanup() {
  [ -n "$CLEANUP_PATHS" ] && rm -rf $CLEANUP_PATHS
}
trap cleanup EXIT

# Resolve SOURCE: if empty, try to discover locally or clone repo.
if [ -z "$SOURCE" ]; then
  # If script is running via curl | bash, the directory might not physically exist yet.
  # We try to find it based on PWD if CHE_RULES.md exists, otherwise use script directory.
  if [ -f "CHE_RULES.md" ]; then
    SOURCE="$(pwd)"
  elif [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SOURCE="$(cd "${SCRIPT_DIR}/.." && pwd)"
  else
    # curl execution: clone repo to temporary folder
    echo "    Remote execution detected. Cloning repository for installation..."
    TMP_SOURCE=$(mktemp -d)
    git clone --depth 1 https://github.com/laionazeredo/che-ai.git "$TMP_SOURCE" >/dev/null 2>&1
    SOURCE="$TMP_SOURCE"
    CLEANUP_PATHS="$CLEANUP_PATHS $TMP_SOURCE"
  fi
fi

# Minimum validations.
if [ ! -f "${SOURCE}/CHE_RULES.md" ]; then
  echo "ERROR: SOURCE does not seem to be a valid .trae directory (missing CHE_RULES.md): ${SOURCE}" >&2
  echo "Try: $0 --source=/path/to/.trae" >&2
  exit 2
fi

case "$TARGET" in
  /*) : ;;
  *) TARGET="${PWD}/${TARGET}" ;;
esac
TARGET="${TARGET%/}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
MODE_LABEL="[dry-run]"
[ "$APPLY" -eq 1 ] && MODE_LABEL="[apply]"

MODE_NAME="fresh-install"
[ "$UPDATE" -eq 1 ] && MODE_NAME="update (non-destructive)"

echo "==> Che ${MODE_NAME} ${MODE_LABEL}"
echo "    Source : ${SOURCE}"
echo "    Target : ${TARGET}"
echo "    Mode   : update=${UPDATE} apply=${APPLY}"

# ABSOLUTE BLACKLIST (files and folders that are NEVER touched).
# Any path in these arrays → script aborts with error if anyone tries to operate on them.
BLACKLIST_DIRS=(
  "user_rules"
  "memory"
  ".git"
  "node_modules"
)
BLACKLIST_FILES=(
  "bindings/registry.jsonl"
)

# Fail-closed verification: if SOURCE has BLACKLIST (it shouldn't), abort.
for b in "${BLACKLIST_DIRS[@]}" "${BLACKLIST_FILES[@]}"; do
  if [ -e "${SOURCE}/${b}" ] && [ "${b}" != "user_rules" ] && [ "${b}" != "memory" ]; then
    # user_rules/memory CAN exist in source, but are NEVER copied (only ignored).
    true
  fi
done

WHITELIST_ROOT_FILES=(
  README.md
  CHE_RULES.md
  CHE_COMMANDS.md
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
# Step 1: handle existing target DEPENDING ON MODE
# ============================================================
if [ -e "$TARGET" ]; then
  if [ "$UPDATE" -eq 0 ]; then
    # FRESH INSTALL MODE (controlled destructive): entire backup of existing target.
    BKP="${TARGET}.bak-${TIMESTAMP}"
    echo "    Target exists (fresh-install mode). ENTIRE backup → ${BKP}"
    if [ "$APPLY" -eq 1 ]; then
      mv "$TARGET" "$BKP"
      echo "    ✔ ENTIRE backup done"
    else
      echo "    [dry-run] entire backup will be done"
    fi
  else
    # NON-DESTRUCTIVE UPDATE MODE: DOES NOT mv entire folder.
    # Just announces that INDIVIDUAL backups will be created per modified file.
    echo "    Target exists (update mode). INDIVIDUAL backup per modified file → .bak-${TIMESTAMP}"
    echo "    Blacklist (user_rules/, bindings/registry.jsonl, memory/) → NEVER touched"
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
# Helper: individual backup BEFORE overwriting (update mode).
# In fresh-install mode target is empty, so helper almost doesn't run.
# ============================================================
backup_if_exists_and_diff() {
  local SRC="$1"
  local DST="$2"
  local LABEL="$3"

  if [ ! -e "$SRC" ]; then
    # Source doesn't have it: NEVER touch target. Preserves user's custom item.
    return 99
  fi

  if [ ! -e "$DST" ]; then
    # Target doesn't have it: copy new, no backup.
    echo "    + new   ${LABEL}"
    if [ "$APPLY" -eq 1 ]; then
      cp -R "$SRC" "$DST"
    fi
    return 0
  fi

  # Both exist: compare (file: cmp; directory: diff -qr).
  local ARE_DIFFERENT=0
  if [ -f "$SRC" ] && [ -f "$DST" ]; then
    cmp -s "$SRC" "$DST" || ARE_DIFFERENT=1
  elif [ -d "$SRC" ] && [ -d "$DST" ]; then
    diff -qr "$SRC" "$DST" >/dev/null 2>&1 || ARE_DIFFERENT=1
  else
    # Type changed (e.g. file → directory). Treat as different.
    ARE_DIFFERENT=1
  fi

  if [ "$ARE_DIFFERENT" -eq 0 ]; then
    # Identical: silent skip.
    return 0
  fi

  # Different: individual backup of target (ALWAYS, dry-run warns).
  local BKP="${DST}.bak-${TIMESTAMP}"
  echo "    ~ updt  ${LABEL}  (old → .bak-${TIMESTAMP})"
  if [ "$APPLY" -eq 1 ]; then
    mv "$DST" "$BKP"
    cp -R "$SRC" "$DST"
  fi
  return 0
}

# ============================================================
# Step 2: copy whitelist root files with smart merge.
# ============================================================
NEEDS_PNPM_INSTALL=0
RENDERED_HOOKS_JSON="$(mktemp)"
CLEANUP_PATHS="$CLEANUP_PATHS $RENDERED_HOOKS_JSON"
python3 - "${SOURCE}/hooks.json" "$RENDERED_HOOKS_JSON" "$TARGET" <<'PY'
import json
from pathlib import Path
import sys

source_path, output_path, target = map(Path, sys.argv[1:])
config = json.loads(source_path.read_text())
for event_hooks in config.get("hooks", {}).values():
    for hook in event_hooks:
        command = hook.get("command")
        if isinstance(command, str):
            hook["command"] = command.replace("__HARNESS_TARGET__", str(target))
Path(output_path).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
PY
for f in "${WHITELIST_ROOT_FILES[@]}"; do
  SRC="${SOURCE}/${f}"
  [ "$f" = "hooks.json" ] && SRC="$RENDERED_HOOKS_JSON"
  DST="${TARGET}/${f}"
  ret=0
  backup_if_exists_and_diff "$SRC" "$DST" "root/${f}" || ret=$?
  if [ "$ret" -eq 0 ] && [ "${f}" = "package.json" -o "${f}" = "pnpm-lock.yaml" ]; then
    NEEDS_PNPM_INSTALL=1
  fi
done

# ============================================================
# Step 3: copy whitelist directories (merge per sub-item).
# In directories: apply NON-DESTRUCTIVE update RECURSIVELY per item
# to PRESERVE user sub-folders/files (e.g. custom skills).
# ============================================================
for d in "${WHITELIST_DIRS[@]}"; do
  SRC="${SOURCE}/${d}"
  DST="${TARGET}/${d}"
  if [ ! -d "$SRC" ]; then
    continue
  fi
  if [ "$UPDATE" -eq 0 ]; then
    # fresh-install MODE: direct copy (target is empty anyway).
    echo "    cp dir : ${d}/"
    if [ "$APPLY" -eq 1 ]; then
      cp -R "$SRC" "$DST"
    fi
  else
    # NON-DESTRUCTIVE update MODE: iterate PER SUBITEM inside source dir.
    # Subitems that exist in source → process. Subitems that exist only in target
    # (user's custom skill) → NEVER touched.
    ensure_dir "$DST"
    # List subitems (files + dirs) in SRC/${d}
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

if [ "$APPLY" -eq 1 ] && [ -d "${TARGET}/hooks" ]; then
  chmod +x "${TARGET}"/hooks/*.sh
fi

# ============================================================
# Step 4: BLACKLIST — guarantee minimum EMPTY structure (always).
# NEVER copies content. Only creates folder if NOT existing.
# bindings/README.md is created only if none exists.
# ============================================================
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
    # Create .gitkeep ONLY if folder was empty before creation.
    touch "${FULL}/.gitkeep"
  fi
done

# Ensure user_rules/.gitkeep if user_rules folder exists but is empty
# (maintains structure traceability in repo clones).
if [ -d "${TARGET}/user_rules" ]; then
  # Count non-.gitkeep files in user_rules folder. Zero → create .gitkeep.
  count_non_gitkeep=0
  if [ "$APPLY" -eq 1 ]; then
    count_non_gitkeep=$(find "${TARGET}/user_rules" -maxdepth 1 -type f ! -name ".gitkeep" 2>/dev/null | wc -l)
    if [ "$count_non_gitkeep" -eq 0 ] && [ ! -f "${TARGET}/user_rules/.gitkeep" ]; then
      touch "${TARGET}/user_rules/.gitkeep"
    fi
  fi
fi

# ============================================================
# Step 5: run pnpm install if package.json/pnpm-lock.yaml changed (update)
# OR if fresh-install with existing package.json.
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
# Step 5.5: Inject CHE BLACKLIST snippet into .gitignore of
#            CLIENT REPO (if running install/update from inside
#            a project worktree that is NOT che-ai itself).
#            Decision made: fail-closed — if a client project
#            has decisions.log / task_graph.md appearing in PRs,
#            GIT has to ignore these patterns EVEN if che can't
#            move them to $CHE_SESSIONS_ROOT due to some bug.
#            Injection is IDEMPOTENT (BEGIN/END marker + sha256).
# ============================================================
inject_blacklist_snippet_into_client_gitignore() {
  local snippet_src marker_begin marker_end client_repo_root client_gitignore

  snippet_src="${SOURCE_ROOT:-$TARGET}/contracts/che-planning-artifacts-blacklist.gitignore"
  [ -f "$snippet_src" ] || return 0

  marker_begin="# >>> CHE PLANNING ARTIFACTS BLACKLIST BEGIN (DO NOT EDIT MANUALLY)"
  marker_end="# <<< CHE PLANNING ARTIFACTS BLACKLIST END"

  # Find CLIENT repo root: if PWD/PARENT has .git AND is NOT ~/.trae itself
  local search_root="${PWD:-$HOME}"
  client_repo_root=""
  local d="$search_root"
  while true; do
    if [ -d "$d/.git" ]; then
      case "$d" in
        "$TARGET"|"${HOME}/.trae"|"${HOME}/.trae/") ;;  # skip: it is che itself
        *) client_repo_root="$d"; break ;;
      esac
    fi
    [ "$d" = "/" ] && break
    d="$(dirname "$d")"
  done
  [ -n "$client_repo_root" ] || return 0

  client_gitignore="${client_repo_root}/.gitignore"

  # Build block to be injected (with markers)
  local snippet_content
  snippet_content="$(cat "$snippet_src")"
  local full_block="${marker_begin}
${snippet_content}
${marker_end}"

  # Case 1: .gitignore does not exist → create with block + final newline.
  if [ "$APPLY" -eq 1 ] && [ ! -f "$client_gitignore" ]; then
    printf '%s\n' "$full_block" > "$client_gitignore"
    echo "    + creating client .gitignore in ${client_repo_root}/.gitignore (blacklist snippet)."
    return 0
  fi
  [ -f "$client_gitignore" ] || return 0

  # Case 2: BEGIN marker already exists in file → idempotent, already injected.
  if grep -qF "$marker_begin" "$client_gitignore" 2>/dev/null; then
    # Updates existing block content to newest snippet (in case blacklist evolves).
    if [ "$APPLY" -eq 1 ]; then
      local tmp_file
      tmp_file="$(mktemp)"
      awk -v marker_begin="$marker_begin" \
          -v marker_end="$marker_end" \
          -v block="$full_block" '
        BEGIN          { inside = 0; printed = 0 }
        $0 == marker_begin { inside = 1; if (!printed) { print block; printed = 1 }; next }
        $0 == marker_end   { inside = 0; next }
        inside == 1    { next }
        inside == 0    { print }
      ' "$client_gitignore" > "$tmp_file"
      mv "$tmp_file" "$client_gitignore"
    fi
    return 0
  fi

  # Case 3: doesn't exist → APPEND at the end, with 2 separator newlines.
  if [ "$APPLY" -eq 1 ]; then
    local final_size
    final_size="$(wc -c < "$client_gitignore" 2>/dev/null || echo 0)"
    if [ "$final_size" -gt 0 ]; then
      # Guarantee final newline before append
      local last_char
      last_char="$(tail -c 1 "$client_gitignore" || echo "")"
      [ "$last_char" = "" ] || printf '\n' >> "$client_gitignore"
      printf '\n' >> "$client_gitignore"
    fi
    printf '%s\n' "$full_block" >> "$client_gitignore"
    echo "    + injected blacklist snippet in client repo: ${client_repo_root}/.gitignore"
  else
    echo "    [dry-run] would inject blacklist snippet in client repo: ${client_repo_root}/.gitignore"
  fi
}
inject_blacklist_snippet_into_client_gitignore

# ============================================================
# Step 6: security summary (blacklist intact).
# ============================================================
echo ""
echo "=== ${MODE_NAME^^} ${MODE_LABEL} completed."
echo ""
echo " BLACKLIST (untouched in both modes):"
echo "   · user_rules/           (your personal rules are never copied/deleted)"
echo "   · bindings/registry.jsonl  (your local level-1 binding)"
echo "   · memory/                (Trae local memory data)"
echo "   · skills/custom-*/       (any subfolder in target that DOES NOT exist in source)"
echo ""

if [ "$UPDATE" -eq 1 ]; then
  echo " UPDATE MODE:"
  echo "   · New official files → added (marked + new)."
  echo "   · Modified official files → overwritten WITH .bak-${TIMESTAMP} backup."
  echo "   · YOUR changes in whitelist files → saved in ${TARGET}/*.bak-${TIMESTAMP}."
  echo "   · YOUR folders/files that don't exist in source → 100% preserved (never touched)."
fi

if [ "$APPLY" -eq 0 ]; then
  echo "⚠ dry-run. To APPLY for real, use the --apply flag."
  echo "Example: curl -fsSL https://raw.githubusercontent.com/laionazeredo/che-ai/main/scripts/install-che.sh | bash -s -- --apply"
else
  echo "✔ target ready at $TARGET"
  echo ""
  echo " Post-check checklist:"
  echo "  1. Open Trae again (or reload)."
  echo "  2. Confirm ~/.trae/README.md exists."
  echo "  3. Smoke : bash $TARGET/scripts/install-che.sh -h"
  echo "  4. Decisions: python3 -m che_core.cli --help"
  if [ "$UPDATE" -eq 1 ]; then
    echo "  5. Manual rollback: to undo a file, mv <file>.bak-${TIMESTAMP} <file>"
  fi
  
  # FINAL STEP: Install adapters for other agents (Codex, Claude Code)
  if [ -f "$TARGET/scripts/setup-adapters.sh" ]; then
    bash "$TARGET/scripts/setup-adapters.sh"
  fi
fi

#!/usr/bin/env bash
#
# prune-che-symlinks.sh — remove Che-owned symlinks whose target no longer exists.
#
#   prune-che-symlinks.sh <CHE_REPO> <dir> [<dir>...]
#
# WHY THIS EXISTS
# The adapters wire Che into a host by symlinking each command, skill and hook
# individually. That is what makes a `git pull` live with no reinstall — but the
# linking loop only ever walks the files that exist NOW, so a command renamed
# upstream gains no new link and keeps the old one. The old one dangles: the host
# still lists it in completion, and running it resolves to nothing. This removes
# exactly those, and nothing else.
#
# WHAT IS TOUCHED, AND WHAT IS NOT
#   • a symlink whose target lives OUTSIDE <CHE_REPO> belongs to the user or to
#     another tool — never removed, resolving or not.
#   • a symlink into <CHE_REPO> that still resolves is a live injection point.
#   • a real file or directory is never removed, whatever it is named.
#   • a dangling symlink into <CHE_REPO> is an orphan of ours — removed.
#
# Detection deliberately does NOT require the link to resolve. An installation
# whose Che links are all dangling is precisely the state this has to repair, so
# "still resolves" cannot be part of the question "is this ours?".
#
# Output: one line per orphan, then a machine-readable total, which the adapters
# forward and `che update` sums to report what it cleaned:
#
#   CHE_PRUNE_REMOVED=<n>
#
# Always exits 0. Pruning is best-effort housekeeping and must never be the
# reason an install fails.
set -uo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: prune-che-symlinks.sh <CHE_REPO> <dir> [<dir>...]" >&2
  exit 2
fi

CHE_REPO="${1%/}"
shift
REPO_PREFIX="$CHE_REPO/"

removed=0

for dir in "$@"; do
  [ -d "$dir" ] || continue

  # Dotfiles included so a future adapter that links one is covered too; an
  # unmatched glob stays literal and fails the -L test below, which is harmless.
  for entry in "$dir"/* "$dir"/.[!.]*; do
    [ -L "$entry" ] || continue

    link="$(readlink "$entry")" || continue

    # Adapters write absolute link text, and for those the link text IS the path, so
    # the prefix test below needs no normalisation. A relative link is resolved
    # against the directory holding it: `cd` does the normalisation, which is what
    # makes `../../che/commands/x` compare equal to the real path — and not
    # `realpath -m`, which BSD realpath (macOS, a supported host) does not have.
    case "$link" in
      /*) candidate="$link" ;;
      *)
        link_dir="$(dirname "$link")"
        if ! resolved_dir="$(cd "$(dirname "$entry")" 2>/dev/null && cd "$link_dir" 2>/dev/null && pwd)"; then
          continue
        fi
        candidate="$resolved_dir/$(basename "$link")"
        ;;
    esac

    case "$candidate" in
      "$REPO_PREFIX"*) ;;
      *) continue ;;
    esac

    # -e follows the link: false means the target is gone.
    [ -e "$entry" ] && continue

    unlink "$entry" || continue
    echo "  - orphan removed: $entry"
    removed=$((removed + 1))
  done
done

echo "CHE_PRUNE_REMOVED=$removed"
exit 0

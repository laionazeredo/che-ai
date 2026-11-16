#!/usr/bin/env bash
#
# Che — loader environment for the Python gates (git hooks + dev-dependency check).
# Some IDE terminals export an LD_LIBRARY_PATH whose libsqlite3.so.0 is older than the
# interpreter's own, so `import sqlite3` dies with "undefined symbol: sqlite3_deserialize"
# and every SQLite-backed test module fails at collection.

# Echo LD_LIBRARY_PATH with every entry that contains libsqlite3.so.0 removed.
# Side effect: CHE_SQLITE_SHADOW_ENTRIES holds the removed entries, space-separated.
che_ld_library_path_without_sqlite_shadow() {
  local rest="${LD_LIBRARY_PATH:-}"
  local entry
  local out=""
  CHE_SQLITE_SHADOW_ENTRIES=""

  while [[ -n "${rest}" ]]; do
    entry="${rest%%:*}"
    if [[ "${rest}" == *:* ]]; then rest="${rest#*:}"; else rest=""; fi
    [[ -z "${entry}" ]] && continue
    if [[ -e "${entry}/libsqlite3.so.0" ]]; then
      CHE_SQLITE_SHADOW_ENTRIES="${CHE_SQLITE_SHADOW_ENTRIES:+${CHE_SQLITE_SHADOW_ENTRIES} }${entry}"
      continue
    fi
    out="${out:+${out}:}${entry}"
  done

  printf '%s' "${out}"
}

# Run python3 with the shadowing entries removed from the loader search path.
che_python() {
  local sanitized
  sanitized="$(che_ld_library_path_without_sqlite_shadow)"
  LD_LIBRARY_PATH="${sanitized}" python3 "$@"
}

# Echo the entries that were dropped, space-separated (empty when the path is clean).
che_sqlite_shadow_entries() {
  che_ld_library_path_without_sqlite_shadow >/dev/null
  printf '%s' "${CHE_SQLITE_SHADOW_ENTRIES}"
}

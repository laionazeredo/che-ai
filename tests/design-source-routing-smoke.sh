#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT_DIR/skills/harness-social-ui-designer/references/DESIGN_BACKEND_CONTRACT.md"
OPENPENCIL_DRIVER="$ROOT_DIR/skills/harness-social-ui-designer/references/backends/OPENPENCIL.md"
WORKFLOW="$ROOT_DIR/.github/workflows/smoke.yml"
FIXTURE_DIR="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_DIR"' EXIT

touch "$FIXTURE_DIR/source.pen" "$FIXTURE_DIR/source.openpencil"

route_design_source() {
  local source_ref="$1"
  local requested_backend="$2"
  local figma_available="$3"
  local openpencil_available="$4"
  local source_kind="unknown"
  local effective_backend="none"
  local capability_status="not-checked"
  local reason=""

  if [ -z "$source_ref" ]; then
    source_kind="none"
  elif [[ "$source_ref" =~ ^https://(www\.)?figma\.com/(design|file)/.+ ]]; then
    source_kind="figma"
  elif [[ "$source_ref" =~ ^https://(www\.)?figma\.com/ ]]; then
    source_kind="figma"
    reason="figma_reference_not_supported"
  elif [[ "$source_ref" =~ ^https://(app\.)?openpencil\.dev/ ]]; then
    source_kind="openpencil"
    capability_status="$openpencil_available"
    reason="openpencil_reference_not_supported"
  elif [[ "$source_ref" =~ \.(pen|openpencil)$ ]]; then
    source_kind="openpencil"
    [ -f "$source_ref" ] || reason="openpencil_file_not_found"
  fi

  if [ -n "$source_ref" ] && [ -z "$reason" ] && [ "$source_kind" = "unknown" ]; then
    reason="unknown_design_source"
  elif [ -n "$source_ref" ] && [ -n "$requested_backend" ] &&
       [ "$source_kind" != "unknown" ] && [ "$requested_backend" != "$source_kind" ]; then
    reason="source_backend_conflict"
  fi

  if [ -z "$reason" ] && [ "$source_kind" = "figma" ]; then
    capability_status="$figma_available"
    if [ "$figma_available" = "available" ]; then
      effective_backend="figma"
    else
      reason="figma_capability_unavailable"
    fi
  elif [ -z "$reason" ] && [ "$source_kind" = "openpencil" ]; then
    capability_status="$openpencil_available"
    if [ "$openpencil_available" = "available" ]; then
      effective_backend="openpencil"
    else
      reason="openpencil_capability_unavailable"
    fi
  elif [ "$source_kind" = "none" ]; then
    if [ "$requested_backend" = "figma" ]; then
      capability_status="$figma_available"
      [ "$figma_available" = "available" ] && effective_backend="figma" || reason="figma_capability_unavailable"
    elif [ "$requested_backend" = "openpencil" ]; then
      capability_status="$openpencil_available"
      [ "$openpencil_available" = "available" ] && effective_backend="openpencil" || reason="openpencil_capability_unavailable"
    elif [ "$openpencil_available" = "available" ]; then
      capability_status="available"
      effective_backend="openpencil"
    elif [ "$figma_available" = "available" ]; then
      capability_status="available"
      effective_backend="figma"
    else
      capability_status="unavailable"
      effective_backend="spec-only"
    fi
  fi

  printf 'source_ref=%s\nsource_kind=%s\nrequested_backend=%s\neffective_backend=%s\ncapability_status=%s\nreason=%s\n' \
    "$source_ref" "$source_kind" "${requested_backend:-none}" "$effective_backend" "$capability_status" "$reason"
}

assert_contains() {
  local result="$1"
  local expected="$2"
  printf '%s\n' "$result" | grep -Fqx "$expected" || {
    echo "[ERROR] Expected '$expected' in routing result:" >&2
    printf '%s\n' "$result" >&2
    exit 1
  }
}

echo "[STEP 1/3] Exercising design-source routing fixtures..."
result="$(route_design_source 'https://www.figma.com/design/abc/App' '' available unavailable)"
assert_contains "$result" 'source_kind=figma'
assert_contains "$result" 'effective_backend=figma'

result="$(route_design_source 'https://figma.com/file/abc/App' '' unavailable available)"
assert_contains "$result" 'effective_backend=none'
assert_contains "$result" 'reason=figma_capability_unavailable'

result="$(route_design_source "$FIXTURE_DIR/source.pen" '' unavailable available)"
assert_contains "$result" 'effective_backend=openpencil'

result="$(route_design_source "$FIXTURE_DIR/source.openpencil" '' unavailable unavailable)"
assert_contains "$result" 'reason=openpencil_capability_unavailable'

result="$(route_design_source "$FIXTURE_DIR/missing.pen" '' unavailable available)"
assert_contains "$result" 'source_kind=openpencil'
assert_contains "$result" 'reason=openpencil_file_not_found'

result="$(route_design_source 'https://app.openpencil.dev/share/example' '' available available)"
assert_contains "$result" 'source_kind=openpencil'
assert_contains "$result" 'effective_backend=none'
assert_contains "$result" 'reason=openpencil_reference_not_supported'

result="$(route_design_source 'https://example.com/design/abc' '' available available)"
assert_contains "$result" 'source_kind=unknown'
assert_contains "$result" 'reason=unknown_design_source'

result="$(route_design_source 'https://figma.com/design/abc/App' openpencil available available)"
assert_contains "$result" 'requested_backend=openpencil'
assert_contains "$result" 'reason=source_backend_conflict'
result="$(route_design_source "$FIXTURE_DIR/source.pen" figma available available)"
assert_contains "$result" 'reason=source_backend_conflict'

result="$(route_design_source '' figma available available)"
assert_contains "$result" 'effective_backend=figma'
result="$(route_design_source '' '' available available)"
assert_contains "$result" 'effective_backend=openpencil'
result="$(route_design_source '' '' unavailable unavailable)"
assert_contains "$result" 'effective_backend=spec-only'
echo "[OK 1/3] Routing fixtures passed"

echo "[STEP 2/3] Checking fail-closed and no-conversion contract..."
grep -Fq 'reason=openpencil_reference_not_supported' "$CONTRACT"
grep -Fq 'reason=source_backend_conflict' "$CONTRACT"
grep -Fq 'reason=unknown_design_source' "$CONTRACT"
grep -Fq 'never converted into one another' "$CONTRACT"
grep -Fq 'No OpenPencil URL import or remote-reference resolver is documented' "$OPENPENCIL_DRIVER"
echo "[OK 2/3] Contract guards passed"

echo "[STEP 3/3] Checking GitHub Actions wiring..."
grep -Fq 'bash tests/design-source-routing-smoke.sh' "$WORKFLOW"
echo "[OK 3/3] GitHub Actions runs the design-source smoke"

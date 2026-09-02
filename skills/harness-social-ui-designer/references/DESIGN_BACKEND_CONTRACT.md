# Design Backend Contract

The Harness design workflow is backend-neutral.

## Canonical lifecycle

1. Bind session/worktree.
2. Resolve durable Harness paths.
3. Write complete design SPEC.
4. Obtain explicit user approval.
5. Select an available design backend.
6. Execute one stage at a time.
7. Review every stage against the approved SPEC.
8. Export and validate final deliverables.

No backend may bypass the SPEC approval gate.

## Backend selection

Select by capability, not by IDE name.

Priority:

1. User explicitly requested a backend and it is available.
2. OpenPencil capability is available -> openpencil.
3. Figma capability is available -> figma.
4. No writable design capability -> spec-only.

spec-only may create the SPEC/dev-spec, but MUST STOP before pixel/design execution.

## Runtime paths

Before durable writes:

    source "${HARNESS_HOME:-$HOME/.trae}/contracts/harness_sessions_contract.sh"
    harness_compute_paths "$WORKTREE_ROOT" "$(harness_current_session_id)" "$PWD"
    harness_ensure_session_dirs "$WORKTREE_ROOT"

Design artifacts live under:

    HARNESS_DESIGN_ROOT="${HARNESS_DESIGN_ROOT:-$HARNESS_WORKSPACE_SHARED/design}"
    HARNESS_DESIGN_DIR="$HARNESS_DESIGN_ROOT/<mode>-<slug>-YYYYMMDD"

Never hardcode a user's home directory or create Harness artifacts inside the
project worktree.

## Driver isolation

Backend-specific instructions apply ONLY when that backend is active.

OpenPencil instructions MUST NOT be executed against Figma.
Figma instructions MUST NOT assume OpenPencil tools or .pen files.

Shared SPEC approval, WCAG, dimensions, stage gates, copy checks and visual
review remain canonical regardless of backend.

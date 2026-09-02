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

### Design source

Normalize every user-provided design reference before selecting a backend:

    design_source:
      source_ref: <verbatim user reference>
      source_kind: figma | openpencil | unknown
      requested_backend: figma | openpencil | none
      effective_backend: figma | openpencil | spec-only | none
      capability_status: available | unavailable | not-checked
      reason: <required when effective_backend=none>

Classification and consumability are separate. A recognizable OpenPencil
reference remains `source_kind=openpencil` even when this runtime cannot open it.

Classify supported sources as follows:

- Figma: `https://figma.com/design/...`, `https://www.figma.com/design/...`,
  `https://figma.com/file/...`, and `https://www.figma.com/file/...`.
- OpenPencil local reference: a path ending in `.pen` or `.openpencil`; it is
  consumable only when it resolves to an existing regular file.
- OpenPencil unsupported reference: an `https://openpencil.dev/...` or
  `https://app.openpencil.dev/...` URL that the active driver cannot consume.
- Recognizable Figma reference: another `figma.com` URL that does not identify a
  consumable design/file resource.
- Unknown: every reference that cannot be classified without guessing.

Do not infer a backend from an IDE. Do not infer a source kind from a generic URL,
and do not treat a recognized source as consumable until its driver confirms it.

### Routing precedence

Apply these checks in order:

1. Record an explicit `requested_backend`, when provided.
2. Classify `source_ref` into `source_kind`.
3. Reject a mismatch between `requested_backend` and a classified source with
   `effective_backend=none` and `reason=source_backend_conflict`.
4. Validate that the selected backend can consume the reference.
5. Validate the selected backend capability.
6. Set `effective_backend` only after all checks pass.

| Input | Capability | Result |
|---|---|---|
| Figma source | Figma available | `effective_backend=figma` |
| Figma source | Figma unavailable | `effective_backend=none`, `reason=figma_capability_unavailable` |
| Recognizable unsupported Figma reference | any | `source_kind=figma`, `effective_backend=none`, `reason=figma_reference_not_supported` |
| Existing OpenPencil file | OpenPencil available | `effective_backend=openpencil` |
| Existing OpenPencil file | OpenPencil unavailable | `effective_backend=none`, `reason=openpencil_capability_unavailable` |
| Missing OpenPencil file | any | `source_kind=openpencil`, `effective_backend=none`, `reason=openpencil_file_not_found` |
| Recognizable unsupported OpenPencil reference | any | `source_kind=openpencil`, `effective_backend=none`, `reason=openpencil_reference_not_supported` |
| Unknown source | any | `source_kind=unknown`, `effective_backend=none`, `reason=unknown_design_source` |
| Classified source + incompatible explicit backend | any | `effective_backend=none`, `reason=source_backend_conflict` |

A classified source never falls back to the other backend. Figma and OpenPencil
sources are never converted into one another.

### Source-less compatibility

When `source_ref` is absent, preserve the V4 priority:

1. User explicitly requested a backend and it is available.
2. OpenPencil capability is available -> openpencil.
3. Figma capability is available -> figma.
4. No writable design capability -> spec-only.

spec-only may create the SPEC/dev-spec, but MUST STOP before pixel/design execution.
An explicitly requested unavailable backend fails closed; it does not fall through
to the next backend.

## SPEC recording

When `source_ref` exists, record a `Design Source` section containing:

- `source_ref` verbatim;
- `source_kind`;
- `requested_backend` or `none`;
- `effective_backend`;
- `capability_status`;
- `reason` whenever routing fails closed.

For Figma, additionally record the file key, page and node/frame only when they
are present in the reference or returned by the integration. For OpenPencil,
record only the resolved local file path and identifiers actually exposed by the
driver. Never invent identifiers.

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

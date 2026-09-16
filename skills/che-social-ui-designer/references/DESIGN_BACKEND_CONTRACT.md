# Design Backend Contract (R7 — fails closed)

> Canonical resolution rules for the `design_source` object. Classification
> precedes capability validation. A Figma source is NEVER silently converted to
> OpenPencil, and an OpenPencil source is NEVER silently converted to Figma.

## Inputs

- `source_ref` (optional): a Figma file/key/page/node, an OpenPencil `.op` path, or nothing.
- `requested_backend` (optional): `figma` | `openpencil` | `spec-only` | none.

## Resolution

| `source_ref` present? | `requested_backend` | `effective_backend` |
|---|---|---|
| no | none | `spec-only` |
| no | `figma` / `openpencil` / `spec-only` | `spec-only` (no source to drive it) |
| yes (`.op` path) | none / `openpencil` | `openpencil` |
| yes (`.op` path) | `figma` | FAIL CLOSED (`reason=source_kind_mismatch`) |
| yes (Figma ref) | none / `figma` | `figma` |
| yes (Figma ref) | `openpencil` | FAIL CLOSED (`reason=source_kind_mismatch`) |

## Fail-closed contract

When resolution fails closed, report `source_kind`, `capability_status`, and
`reason`, plus the supported input forms, then STOP before design execution.
Never attempt a cross-engine conversion.

## Driver dispatch

- `openpencil` → `skills/che-social-ui-designer/references/backends/OPENPENCIL.md`
- `figma` → `skills/che-social-ui-designer/references/backends/FIGMA.md`
- `spec-only` → SPEC/dev-spec only; STOP before pixel execution.

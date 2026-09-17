# Design Backend Contract (R7 — fails closed)

> Canonical resolution rules for the `design_source` object. Classification
> precedes capability validation. A Figma source is NEVER silently converted to
> OpenPencil, and an OpenPencil source is NEVER silently converted to Figma.

## Inputs

- `source_ref` (optional): a Figma file/key/page/node, an OpenPencil `.op` path, or nothing.
- `requested_backend` (optional): `figma` | `openpencil` | `penpot` | `spec-only` | none.

## Resolution

| `source_ref` present? | `requested_backend` | `effective_backend` |
|---|---|---|
| no | none | `spec-only` |
| no | `figma` / `openpencil` / `spec-only` | `spec-only` (no source to drive it) |
| yes (`.op` path) | none / `openpencil` | `openpencil` |
| yes (`.op` path) | `figma` | FAIL CLOSED (`reason=source_kind_mismatch`) |
| yes (Figma ref) | none / `figma` | `figma` |
| yes (Figma ref) | `openpencil` | FAIL CLOSED (`reason=source_kind_mismatch`) |
| any | `penpot` | FAIL CLOSED (`reason=backend_not_implemented`) |

## Declared but not implemented — `penpot`

`penpot` is a **declared** backend, not an unknown one: `domains/ux/connectors/penpot.config.md` presents
it as a first-class alternative to Figma, and the domain layer genuinely is tool-agnostic. What does not
exist is the extractor. The official `@penpot/mcp` server exposes `execute_code` (JavaScript against the
Plugin API) and no fact-export tool, so a Penpot fact bag has to be produced by a script — and its
response shape has to be recorded from a real session and pinned by a fixture before any number it
produces can be trusted. Writing the parser against a guessed shape is the failure §4 of the gate records.

So the refusal is by **name**, and it is deliberately distinct from `source_kind_mismatch` and from a
misspelling:

- Unimplemented backend → `backend_not_implemented`, with what has to exist first.
- Typo → the generic unknown-backend message.
- Wrong shape for a supported backend → `source_kind_mismatch`.

Collapsing the first into the third would tell a caller to convert their source, which is the one thing
this contract forbids. Collapsing it into the second sends them looking for a spelling error they did not
make.

A fact bag built by hand from an `execute_code` session is a legitimate input, and it is labelled
`penpot`: on the pre-keyed path the engine reads no design source at all, so the field is provenance. Do
not relabel it `figma` to reach an extractor — that records a backend the numbers did not come from.

## Fail-closed contract

When resolution fails closed, report `source_kind`, `capability_status`, and
`reason`, plus the supported input forms, then STOP before design execution.
Never attempt a cross-engine conversion.

## Driver dispatch

- `figma` → `skills/che-social-ui-designer/references/backends/FIGMA.md`
- `openpencil` → `skills/che-social-ui-designer/references/backends/OPENPENCIL.md`
- `penpot` → none. STOP at the refusal above; there is no driver reference to dispatch to yet.
- `spec-only` → SPEC/dev-spec only; STOP before pixel execution.

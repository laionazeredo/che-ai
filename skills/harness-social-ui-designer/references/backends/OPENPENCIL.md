# OpenPencil Design Driver

Use only when the active backend is openpencil.

Existing OpenPencil-specific lessons in the canonical design skill remain
authoritative for this backend, including text templates, headless image
limitations, variables, components, vector operations and exports.

Store local source files under:

    $HARNESS_DESIGN_DIR/source.pen
    $HARNESS_DESIGN_DIR/source.openpencil

Never use a hardcoded user home path.

## Supported references

The currently documented runtime can consume an existing local `.pen` or
`.openpencil` file. Resolve the path and verify that it is a regular file before
selecting this backend. A missing matching path retains
`source_kind=openpencil` but returns `reason=openpencil_file_not_found`.

No OpenPencil URL import or remote-reference resolver is documented in the
current driver. Treat URLs on `openpencil.dev` and `app.openpencil.dev` as
recognizable OpenPencil references, but not as consumable sources. Return:

    source_kind=openpencil
    effective_backend=none
    reason=openpencil_reference_not_supported

Report the detected OpenPencil capability and tell the user that an existing
local `.pen` or `.openpencil` file is supported. Do not download, translate, or
silently recreate the remote source.

## Capability detection

Select this driver only when the OpenPencil capability required to open the local
file is available. Otherwise return `reason=openpencil_capability_unavailable`.
Never fall back to Figma for an OpenPencil source.

# Figma Design Driver

Use only when the active backend is figma.

## Capability detection

Use only capabilities actually exposed by the current Figma integration.
Do not invent tool names.

Classify capability as:

- read-only
- read + export
- read + write

The requested operation determines the required capability. Reading a supplied
source requires at least read-only access; export and write operations require
their corresponding detected capability. An unavailable required capability is
`figma_capability_unavailable` and MUST NOT fall back to OpenPencil.

## Supported references

The driver accepts cloud-backed Figma URLs whose path identifies a `design` or
legacy `file` resource on `figma.com`, with an optional `node=`, page selection,
or `node-id`/node or node frame reference when exposed by Figma.

Generic Figma URLs without a design/file resource are not consumable design
sources. Keep the source classification when recognizable, but fail closed rather
than guessing a file or node.

## Read-only or export capability

Allowed:

- inspect frames and hierarchy;
- inspect components and variants;
- inspect colors, typography and spacing;
- derive frontend/dev-spec;
- export supported assets;
- implement frontend from approved Figma source.

Never claim that Figma nodes were modified.

## Writable capability

When actually supported, it may additionally create or update frames,
text, properties, variables and components.

All writes remain behind the canonical SPEC approval and stage gates.

## Source metadata

Figma is cloud-backed. Do not invent a local .fig source file.

Record source information under:

    $HARNESS_DESIGN_DIR/figma-source.md

Include file/project reference, page, frames or node identifiers,
source reference and detected capability mode when available.

Never create a local `.fig` file and never copy the source into OpenPencil.

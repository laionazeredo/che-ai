# Figma Design Driver

Use only when the active backend is figma.

## Capability detection

Use only capabilities actually exposed by the current Figma integration.
Do not invent tool names.

Classify capability as:

- read-only
- read + export
- read + write

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

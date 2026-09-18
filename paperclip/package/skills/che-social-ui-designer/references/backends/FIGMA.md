# Figma Backend Driver (backend=`figma`)

> Applies ONLY when `effective_backend=figma` (see
> `../DESIGN_BACKEND_CONTRACT.md`). Figma execution uses the official MCP or
> official CLI — never raw HTTP to the Figma REST API (engineering-contracts §20).

## Source registration

Figma has no local `.op` source; register metadata only:

- Write `figma-source.md` inside `$CHE_DESIGN_DIR` (or `design/<sub_product>/`)
  containing `file_key`, `page`, `node_id`, and `effective_backend=figma`.

## Read / export

- `get_node` / `node_children` / `node_tree` to read exact measurements.
- `export_svg` + `export_image` (scale 2) to handoff artifacts.
- `list_variables` / `get_variable` for design tokens.

## Fail closed

Never convert a Figma source to OpenPencil. If the requested backend is
`openpencil` but the source is Figma, fail closed with
`reason=source_kind_mismatch` (see the backend contract).

## Tool reference

Full tool list and auth flow: `domains/ux/connectors/figma.config.md`.

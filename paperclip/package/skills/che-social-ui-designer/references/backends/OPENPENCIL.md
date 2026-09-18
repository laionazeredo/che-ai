# OpenPencil Backend Driver (backend=`openpencil`)

> Applies ONLY when `effective_backend=openpencil` (see
> `../DESIGN_BACKEND_CONTRACT.md`). OpenPencil is the local MCP that produces
> git-able `.op` source files plus exported `.svg`/`.png` artifacts.

## Source authoring

- Create/open the active document, then `save_file` to
  `design/<sub_product>/source/home.op` (path inside the bound worktree).
- Keep an identical `source.pen` copy so downstream agents have a stable name.

## Export

- `export_svg` → `design/<sub_product>/exports/<name>.svg` (pure vector, `viewBox` present, no `<image>`/base64 for logo work).
- `export_image` (scale 2) → `design/<sub_product>/exports/<name>@2x.png`.

## Stock / icons

- `stock_photo` (query + orientation) for real photography fallback.
- `search_icons` / `fetch_icons` / `insert_icon` for official Lucide icons.

## Hard-won lesson (TEXT nodes)

Never create a `TEXT` node manually via `create_shape`/`I(null,{type:text,...})`
— it renders with width=height=0. Use the built-in `knowledge-card-square`
template, then overwrite copies/fills/fonts via `set_text` + `set_font`, and
always `save_document(filePath)` after changing text.

## Tool reference

Full tool list: `domains/ux/connectors/openpencil.config.md`.

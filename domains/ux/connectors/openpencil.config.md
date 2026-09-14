---
connector_type: "local-mcp"
domain: "ux"
vendor: "OpenPencil"
vendor_official_site: "https://openpencil.dev"
mcp_identifier: "mcp_open-pencil"
hard_rule_external_connector_ref: "engineering-contracts §20 EXTERNAL CONNECTORS ONLY OFFICIAL CLI/MCP"
forbidden_access_patterns:
  - "Hardcoded absolute paths outside the bound worktree"
  - "Writing .op source outside <wt>/design/<sub_product>/"
---

# Connector Config — UX · OpenPencil (Local MCP)

> **OpenPencil is the git-able source of truth for the Che design domain.** Its
> `.op` source files and exported `.svg`/`.png` artifacts are plain/git-able
> files that MUST live inside the bound worktree under `design/<sub_product>/`,
> never in `$CHE_WORKSPACE_SHARED`.

## Authoring targets (R1 + B-7)

| Operation | MCP tool | Target (inside `<wt>`) |
|---|---|---|
| Create/open document | `new_document` / `open_file` | `design/<sub_product>/source/home.op` |
| Save the active document | `save_file` | `design/<sub_product>/source/home.op` |
| Export vector | `export_svg` | `design/<sub_product>/exports/` |
| Export raster 2× | `export_image` | `design/<sub_product>/exports/` |
| Stock photo fallback | `stock_photo` | `design/<sub_product>/assets/` |
| Icon search | `search_icons` / `fetch_icons` / `insert_icon` | n/a (in-memory) |

All target paths resolve under the bound worktree `<wt>/design/<sub_product>/`.
`git status --porcelain` must report them under `design/<sub_product>/`.

## Driver details

Full OpenPencil tool reference lives in
`skills/che-social-ui-designer/references/backends/OPENPENCIL.md`.
Backend selection rules live in
`skills/che-social-ui-designer/references/DESIGN_BACKEND_CONTRACT.md`.

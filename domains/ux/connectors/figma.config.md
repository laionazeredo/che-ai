---
connector_type: "official-mcp-plus-cli"
domain: "ux"
vendor: "Figma"
vendor_official_site: "https://www.figma.com/developers"
mcp_identifier: "mcp_open-pencil"
cli_package: "figma-cli"
cli_package_manager: "npm"
hard_rule_external_connector_ref: "engineering-contracts §20 EXTERNAL CONNECTORS ONLY OFFICIAL CLI/MCP"
forbidden_access_patterns:
  - "curl / fetch / HTTP raw request to Figma REST API"
  - "Hardcoded FIGMA_PERSONAL_ACCESS_TOKEN in code or inline variables"
  - "SDK without official CLI wrapper"
---

# Connector Config — UX · Figma (Official MCP + Official CLI)

> **Complies with §20 engineering-contracts: NEVER raw HTTP. Always official MCP first, official CLI fallback, or nothing.** Outside of these 2 channels = contract violation. No exceptions.

---

## Channel 1 (PRIORITY · recommended): Official MCP `mcp_open-pencil`

MCP already available in the TRAE ecosystem. No additional installation. Covers 95% of DesignOps operations: reading nodes, exporting SVG/PNG, reading variables (tokens), applying values, diffing dev-mode design vs implemented code.

### Supported Operations (examples of tool calls for agents)
| DesignOps Operation | MCP Tool `mcp_open-pencil.*` |
|---|---|
| List Figma documents in workspace | `list_documents` |
| Open specific Figma file by file_id | `open_file` + `get_page_tree` |
| Get specific node by id (Frame, Component, Instance) | `get_node` |
| Recursively get children nodes from a Page | `node_children` + `node_tree` |
| **Pixel / layout deviation differences** (Pixel Perfect Gate base) | `diff_jsx` (dev-mode) + comparative `export_image` |
| Get Design Tokens / Variables (collections) | `list_variables` + `get_variable` |
| Set design tokens in existing collection (update value) | `set_variable` |
| Export SVG component (dev handoff) | `export_svg` |
| Export PNG 2x / PDF | `export_image` + `export_pdf` |
| Create new basic node / rectangle / text / shape | `create_shape` + `create_vector` + `insert_icon` (Official Lucide) |
| Colors / typography / spacing analysis in design (tokens audit) | `analyze_colors`, `analyze_typography`, `analyze_spacing` |
| Query nodes by criteria (e.g.: "all buttons radius xs") | `query_nodes` + `find_nodes` |

### Usage Flow Example (practical for pilot)
```
1. Figma link: https://www.figma.com/design/<FILE_ID>/Flockr-Platform?node-id=<NODE_ID>
2. Extract FILE_ID manually or via URL parsing
3. run_mcp → mcp_open-pencil.get_node(node-id=<NODE_ID>)
4. Result: exact layout (padding 16/24, radius md, primary-500 color token, weight 600)
5. Handover: copy absolute values to dev-handoff-template.md WITHOUT needing to open Figma.
```

---

## Channel 2 (Fallback if MCP is unavailable): Official npm CLI `figma-cli`

Official community-maintained Figma CLI. One-shot installation via Corepack pnpm:

```bash
corepack pnpm add -D figma-cli
```

### CLI Authentication (§18 pattern same as GitHub gh-only = NEVER hardcode tokens)
1. Run `figma login` — browser opens, OAuth flow, saves token in `~/.config/figma/credentials.json` (not versioned).
2. **DO NOT export `FIGMA_TOKEN` directly in shell.** If CI needed: use platform SECRET MANAGER (Vercel Env Crypt, GitHub Actions Encrypted Secrets) with `FIGMA_PAT_` prefix — NEVER commit in `.env` or code.

### Useful CLI Commands for Handoff
```bash
# [STEP 1/3] List team files (same as MCP list_documents permission)
figma team list --team-id <TEAM_ID>

# [STEP 2/3] Export hi-fi 2x PNG + SVG component to handoff folder
figma export <FILE_ID> --node <NODE_ID> --format png --scale 2 --output docs/ux/<slug>/assets/
figma export <FILE_ID> --node <NODE_ID> --format svg --output docs/ux/<slug>/assets/icons/

# [STEP 3/3] Extract variables (tokens) to JSON for engineering to import
figma variables export <FILE_ID> --output docs/ux/<slug>/tokens.json --format json
```

---

## Compatibility with §13 Language 4-axis
- Variable names / export filenames = always EN (LANG_CODE).
- Labels inside design = project-defined LANG_DOCS (e.g.: pt-BR for Flockr Brazil).
- Diff / tokens audit reports = LANG_REPORT = en (for cross-company CI).
- Conversation with user designer = LANG_CHAT (default en).

---

## Anti-patterns = Fail Gate A11y / Compliance Heavy
1. ❌ `fetch('https://api.figma.com/v1/files/...', headers:{Authorization:'Bearer '+token})` — raw HTTP banned (§20).
2. ❌ Committed FIGMA_TOKEN in `.env.example`.
3. ❌ Exporting SVG with hardcoded inline `fill="#2563eb"` instead of `fill="currentColor"` → violates profile Forbidden Pattern #6.
4. ❌ Implementing design without running `diff_jsx` or at least `get_node` to get exact measurements → "eyeballed" measurements = Gate Pixel Perfect Fail.

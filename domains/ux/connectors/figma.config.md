---
connector_type: "official-mcp"
domain: "ux"
vendor: "Figma"
vendor_official_site: "https://www.figma.com/developers"
mcp_identifier: "mcp_Figma_AI_Bridge"
cli_package: ""
cli_package_manager: ""
hard_rule_external_connector_ref: "engineering-contracts §20 EXTERNAL CONNECTORS ONLY OFFICIAL CLI/MCP"
forbidden_access_patterns:
  - "curl / fetch / HTTP raw request to Figma REST API"
  - "Hardcoded FIGMA_PERSONAL_ACCESS_TOKEN in code or inline variables"
  - "SDK without official CLI wrapper"
---

# Connector Config — UX · Figma (Official MCP only)

> **Complies with §20 engineering-contracts: NEVER raw HTTP. The official MCP, or nothing.** There is
> no CLI fallback for Figma (see Channel 2). Anything outside the MCP channel is a contract violation.

---

## Channel 1 (the only channel): official MCP `mcp_Figma_AI_Bridge`

MCP already available in the ecosystem. No installation step.

> **Superseded (do not use):** earlier revisions of this file declared `mcp_identifier: mcp_open-pencil`
> and listed an `mcp_open-pencil.*` surface (`get_node`, `node_tree`, `list_variables`, `diff_jsx`,
> `export_image`, `analyze_*`, …) as the way to read Figma. That is the *OpenPencil* connector's
> surface, not Figma's — it lives in `openpencil.config.md`. `diff_jsx` in particular never meant what
> this file claimed: the real `diff_jsx(from, to, document_id?, page_id?)` is a *structural* diff
> between two nodes of the same document, reporting added/removed children and changed props. It never
> returns measurements and it cannot see the DOM. Kept as a warning, because a plausible-looking tool
> signature that nothing can execute is how a connector gets believed and never run.

### The actual tool surface

| DesignOps operation | Tool |
|---|---|
| Read a file or a node subtree — layout, dimensions, padding, gap, radius, strokes, fills, effects, text styles, opacity, component properties | `get_figma_data(fileKey, nodeId?, depth?)` |
| Download the SVG/PNG assets a node references | `download_figma_images(fileKey, nodes[], localPath, pngScale?)` |

`nodeId` is **optional**, and omitting it returns the whole file — pass the frame you are implementing.
`depth` stays unset unless a bounded response is explicitly needed.

That is the entire surface. There is no token/variable setter, no node creator, no `analyze_*`, and no
diff. Those operations do not exist for Figma over MCP and must **not** be improvised with raw HTTP.

### Usage flow (practical for pilot)

```
1. Figma link: https://www.figma.com/design/<FILE_ID>/<name>?node-id=<NODE_ID>&m=dev
2. Take FILE_ID and NODE_ID from the URL (URL uses '-', the API uses ':')
3. run_mcp → mcp_Figma_AI_Bridge.get_figma_data(fileKey=<FILE_ID>, nodeId=<NODE_ID>)
4. Save the RAW response: `che pixel check --design-source` re-parses it on every run, so the
   numbers it scores can never drift from the file they came from.
5. Handover: copy absolute values to dev-handoff-template.md WITHOUT needing to open Figma.
```

The response is an indented *rendering*, not a schema. `che_core/pixel_sources.py` parses it and is
pinned by a recorded fixture, so a vendor format change breaks a test instead of quietly turning into
wrong numbers.

---

## Channel 2 (no fallback — Figma ships no official CLI)

There is no fallback. Figma publishes no official CLI, and earlier revisions of this file named an npm
package `figma-cli` with a `figma login` / `figma export` / `figma variables export` command set. None
of it exists. If the bridge is unavailable, the Figma side of the task is blocked: report that, do not
substitute a workaround.

### Credential rule (§18 pattern — same as GitHub `gh`: NEVER hardcode tokens)

1. The bridge reads its token from the environment (`LAION_FIGMA_PAT`). It is provisioned by the
   platform, not by an interactive login flow.
2. **DO NOT export the token inline in a shell command, and never commit it.** For CI, use the platform
   SECRET MANAGER (Vercel Env Crypt, GitHub Actions Encrypted Secrets) with the `FIGMA_PAT_` prefix.
3. A token's file access is its owner's access. A `404` on a file you can open in a browser is the
   expected failure mode of a token that cannot see it — confirm file access before blaming the
   tooling, and never work around it with an unauthenticated request.

---

## Compatibility with §13 Language 4-axis

- Variable names / export filenames = always EN (LANG_CODE).
- Labels inside design = project-defined LANG_DOCS (e.g.: pt-BR for Flockr Brazil).
- Tokens audit reports = LANG_REPORT = en (for cross-company CI).
- Conversation with user designer = LANG_CHAT (default en).

---

## Anti-patterns = Fail Gate A11y / Compliance Heavy

1. ❌ `fetch('https://api.figma.com/v1/files/...', headers:{Authorization:'Bearer '+token})` — raw HTTP banned (§20).
2. ❌ Committed FIGMA_TOKEN in `.env.example`.
3. ❌ Exporting SVG with hardcoded inline `fill="#2563eb"` instead of `fill="currentColor"` → violates profile Forbidden Pattern #6.
4. ❌ Implementing a design without reading the node first (`get_figma_data`) and then running the pixel gate → "eyeballed" measurements = Gate Pixel Perfect fail.
5. ❌ Naming a Figma tool the bridge does not expose, or describing a structural diff as a measurement. If a capability is missing, say so — a fabricated tool signature is worse than a missing one.

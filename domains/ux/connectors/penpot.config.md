---
connector_type: "official-mcp"
domain: "ux"
vendor: "PenPot"
vendor_official_site: "https://penpot.app/"
vendor_official_open_source: "https://github.com/penpot/penpot (MPL-2.0 license)"
mcp_identifier: "@penpot/mcp — official, shipped from the Penpot monorepo (https://help.penpot.app/mcp/)"
hard_rule_external_connector_ref: "engineering-contracts §20 EXTERNAL CONNECTORS ONLY OFFICIAL CLI/MCP"
forbidden_access_patterns:
  - "curl / fetch raw HTTP for PenPot self-hosted API"
  - "Hardcoded PENPOT_ACCESS_TOKEN / MCP userToken inline or in committed .env"
  - "Using third-party SaaS intermediaries between the agent and PenPot"
wiring_status: "PARTIAL — the design pipeline can drive Penpot; the `ux-pixel-check-gate` design side cannot read it yet (no extractor). See 'Wiring status' below."
---

# Connector Config — UX · PenPot (Official Open-Source MCP)

> **Complies with §20 engineering-contracts: Official MCP channel only. No raw REST.** PenPot is the
> first-class open-source alternative to Figma for teams that prefer self-hosting. What it shares with the
> Figma path is the *domain* — same profile, playbook, gates and templates, same numeric thresholds,
> because none of those name a tool. What it does **not** share is the tooling that feeds the pixel gate.
> Read "Wiring status" before promising a Penpot source to a reviewer.

---

## Wiring status (read this before quoting the parity claim)

| Consumer | Penpot support today |
|---|---|
| `domains/ux/` profile, playbook, gates, templates | ✅ tool-agnostic by design — same files, same thresholds |
| `che-social-ui-designer` pipeline (screens, tokens, handoff) | ✅ reachable via `execute_code` / `high_level_overview` |
| **`che pixel check` design side (`--design-backend`)** | ❌ **no extractor.** `figma` and `openpencil` only. |

The gate scores numbers from a fact bag (§4.1) and nothing in this MCP returns that bag:

- **There is no fact-export tool.** The server exposes five tools (below), and the only one that can read
  exact geometry, fills and typography is **`execute_code`** — JavaScript run against the Plugin API inside
  the open file. A Penpot fact bag therefore has to be *produced* by a script the caller writes.
- That script's response shape must be **recorded from a real session and pinned by a fixture** before a
  run can be trusted. Writing the parser against a guessed shape is the mistake gate §4 records
  (`diff_jsx`, `figma-cli`): a plausible-looking tool signature nothing can execute, which is how that gate
  came to be declared "executable" while being impossible to run.
- Until the recording exists, the CLI refuses the **name**, not the shape — because a caller who asked for
  Penpot is not mistaken, only early:
  - `che pixel check --design-source … --design-backend penpot` → exit `2`, `no extractor`
  - `che pixel paths --backend penpot` → exit `2`, `no capture convention` (the flag picks a raw-capture
    filename, and no session has ever been recorded to establish one)
  - Both refusals come from `che_core.pixel_sources.BACKENDS_WITHOUT_EXTRACTOR`. A typo keeps its own
    message (`unknown design backend`), so the two failures never collapse into one.
  - Implementing the extractor removes both refusals by removing `"penpot"` from that set.
- A bag built by hand from an `execute_code` session is **legitimate**, and it goes in through `--design`
  with `--design-backend penpot`: the engine reads no design source on that path, so the label is
  provenance. Do not label it `figma` to route around the refusal — the report would then be wrong about
  its own origin, which is the one thing a gate's provenance field must not be.

**Two operations earlier revisions of this file listed as tools do not exist:** a design-token
export/import pair, and a dev-mode diff against the DOM. Token round-trips go through `execute_code`, and
there is no diff tool at all — which is why the pixel gate does the comparing itself, in
`che_core/pixel.py`.

---

## Reasons for First-Class PenPot Support

- 100% open-source MPL-2.0 — no vendor lock-in, auditable.
- Native **Design Tokens** support (no paid plugins).
- One-line self-hosting via Docker: ideal for Flockr enterprise security policies.
- Same abstraction as our `domains/ux/` = SAME profile.md / playbook.md / gates / templates. Only the
  connector changes. If it works for PenPot → it proves the Domain Layer is tool-agnostic — a claim this
  file exists to test, and the pixel gate's design side is the part of it still false.

---

## MCP Installation (official server)

Local mode:

```bash
npx @penpot/mcp@stable
```

Then in Penpot: open the design file → **File → MCP Server → Connect**. The server drives the file
through that plugin over a WebSocket; only one browser tab can hold the connection at a time.

Remote mode (the vendor's recommended path): enable **Integrations → MCP Server** in your Penpot account,
generate an MCP key (shown once), and point the client at
`https://<your-penpot-domain>/mcp/stream?userToken=<MCP_KEY>`. The key is a secret — same rule as
`PENPOT_ACCESS_TOKEN` in the forbidden patterns above.

Local-mode defaults: MCP server `4401`, plugin WebSocket `4402`, plugin page `4400` (overridable with
`PENPOT_MCP_SERVER_PORT` / `PENPOT_MCP_WEBSOCKET_PORT`).

> The `penpot/penpot-mcp` repository is archived; the source now lives in the Penpot monorepo under `mcp/`.

---

## Supported Operations (the real tool set — five tools)

| Tool | What it gives the domain |
|---|---|
| `high_level_overview` | structure of the file/page — frames, components, nesting. Orientation, **not** measurements. |
| `penpot_api_info` | the Plugin API surface available, so `execute_code` can be written correctly. |
| `execute_code` | **the only source of exact design values** — run JS against the Plugin API to read geometry, fills, typography, tokens. |
| `export_shape` | render a shape as an image — handoff, and §4.5-style visual evidence. Reduced capability in remote mode. |
| `import_image` | import an image into the file. Local mode only. |

| DesignOps Operation | How it is actually done |
|---|---|
| List projects / files / pages | `high_level_overview` for the current file/page; broader enumeration is an API concern |
| Get a specific node's values | `execute_code` against the Plugin API |
| Export SVG / PNG for handoff | `export_shape` |
| Read / write **Design Tokens** | `execute_code` — there is no token tool |
| Create components / frames / shapes | `execute_code` |
| Colour / spacing / typography audit | `execute_code` |
| Produce the pixel gate's fact bag (§4.1) | **not available** — see "Wiring status" |

---

## Cross-tool Flow: PenPot → Figma (if client uses both)

1. Design created in PenPot.
2. Read the tokens with `execute_code` (there is no export tool) and write the JSON yourself.
3. Import that JSON into Figma through its variables path.
4. A11y and pixel gates run IDENTICALLY — because their thresholds are numeric and tool-independent. The
   *feeding* step is where the tools differ: step 2 is a script today, not a command.

> **Key Rule:** Domain artifacts (profile, playbook, gates, templates) NEVER depend on a specific tool.
> They only depend on numerical thresholds. Switching Figma ↔ PenPot requires zero core refactoring.

**Amended, deliberately:** that rule is about the thresholds, and it is exactly why the tooling gap above
is survivable — the gate's numbers do not move when the design tool does. It is **not** a claim that the
tooling is already at parity. "Wiring status" exists to say so out loud, because the earlier wording
("100% compatible with the same gates") read as the second claim while only the first was true.

---

## Anti-patterns = Fail

1. ❌ `curl -X POST https://design.penpot.app/api/rpc/command/...` raw HTTP → §20 banned.
2. ❌ Sharing "public editable by anyone" links without SSO — violates the access Forbidden Pattern.
3. ❌ Switching to PenPot and "lowering thresholds because the tool is new": thresholds belong to the
   design, not the tool. If the tool doesn't meet the threshold → don't use it. Do not lower thresholds.
4. ❌ Labelling a hand-built fact bag `figma` or `openpencil` to route around the `penpot` refusal. Pass
   `--design --design-backend penpot` and let the report state where the numbers actually came from.

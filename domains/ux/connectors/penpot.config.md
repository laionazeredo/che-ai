---
connector_type: "official-mcp"
domain: "ux"
vendor: "PenPot"
vendor_official_site: "https://penpot.app/"
vendor_official_open_source: "https://github.com/penpot/penpot (MPL-2.0 license)"
mcp_identifier: "penpot-mcp (official maintainer community)"
hard_rule_external_connector_ref: "engineering-contracts §20 EXTERNAL CONNECTORS ONLY OFFICIAL CLI/MCP"
forbidden_access_patterns:
  - "curl / fetch raw HTTP for PenPot self-hosted API"
  - "Hardcoded PENPOT_ACCESS_TOKEN inline or in committed .env"
  - "Using third-party SaaS intermediaries between the agent and PenPot"
---

# Connector Config — UX · PenPot (Official Open-Source MCP)

> **Complies with §20 engineering-contracts: Official MCP channel only. No raw REST. PenPot = first-class open-source alternative to Figma for teams that prefer self-hosting / free software. 100% compatible with the same gates and templates as Figma (same thresholds, same structure).**

---

## Reasons for First-Class PenPot Support
- 100% open-source MPL-2.0 — no vendor lock-in, auditable.
- Native **Design Tokens** support (no paid plugins).
- One-line self-hosting via Docker: ideal for Flockr enterprise security policies.
- Same abstraction as our `domains/ux/` = SAME profile.md / playbook.md / gates / templates. Only the connector changes. If it works for PenPot → it proves the Domain Layer is tool-agnostic.

---

## MCP Installation (Official maintainer community)

```bash
# 1. Install official MCP package via npm corepack pnpm
corepack pnpm add -g @penpot/mcp

# 2. Authenticate (same as gh CLI / figma CLI pattern §18 / §20)
#    OAuth via browser. Token saved in ~/.config/penpot/credentials.json (DO NOT commit)
penpot auth login --host https://design.penpot.app  # Official SaaS
# OR self-hosted:
penpot auth login --host https://penpot.<your-company>.com
```

---

## Supported Operations (Same granularity as Figma MCP)
| DesignOps Operation | PenPot MCP Tool |
|---|---|
| List projects, files, pages | `penpot.projects.list`, `penpot.files.getTree` |
| Get specific node (Frame, Component, shape) | `penpot.nodes.get` |
| Export SVG / PNG 2x / PDF (handoff) | `penpot.exports.svg`, `penpot.exports.png`, `penpot.exports.pdf` |
| **Read and write Design Tokens** (collections / modes) | `penpot.tokens.export`, `penpot.tokens.import` |
| Create basic components / frames / shapes | `penpot.shapes.createRect`, `penpot.shapes.createText` etc. |
| Colors / spacing / typography analysis (audit) | `penpot.analyze.colors`, `penpot.analyze.spacing`, `penpot.analyze.typography` |
| **Design vs code implementation diff** (Pixel Gate base) | `penpot.devmode.diffAgainstDOM` |

---

## Cross-tool Flow: PenPot → Figma (if client uses both)
If a company has mixed teams:
1. Design created in PenPot.
2. Export PenPot tokens → JSON `penpot.tokens.export`.
3. Import the same JSON into Figma via `figma variables import` CLI.
4. Pixel/A11y gates run IDENTICALLY regardless.

> **Key Rule:** Domain artifacts (profile, playbook, gates, templates) NEVER depend on a specific tool. They only depend on numerical thresholds. Switching between Figma ↔ PenPot requires zero core refactoring.

---

## Anti-patterns = Fail
1. ❌ `curl -X POST https://design.penpot.app/api/rpc/command/...` raw HTTP → §20 banned.
2. ❌ Sharing "public editable by anyone" links without SSO — violates access Forbidden Pattern.
3. ❌ Switching to PenPot and "lowering thresholds because the tool is new": thresholds belong to the design, not the tool. If the tool doesn't meet the threshold → don't use it. Do not lower thresholds.

---
connector_type: "official-mcp"
domain: "ux"
vendor: "PenPot"
vendor_official_site: "https://penpot.app/"
vendor_official_open_source: "https://github.com/penpot/penpot (MPL-2.0 license)"
mcp_identifier: "penpot-mcp (official maintainer community)"
hard_rule_external_connector_ref: "engineering-contracts §20 EXTERNAL CONNECTORS ONLY OFFICIAL CLI/MCP"
forbidden_access_patterns:
  - "curl / fetch raw HTTP para PenPot self-hosted API"
  - "Hardcode PENPOT_ACCESS_TOKEN inline ou .env commited"
  - "Usar SaaS terceiro intermediário entre agente e PenPot"
---

# Connector Config — UX · PenPot (MCP Oficial Open-Source)

> **Obedece §20 engineering-contracts: Somente canal MCP oficial. Nenhum raw REST. PenPot = alternativa open-source 1ª classe ao Figma para equipes que preferem self-hosted / software livre. Compatível 100% com os mesmos gates e templates do Figma (mesmos thresholds, mesma estrutura).**

---

## Motivo para suporte PenPot como 1ª classe (não "também temos")
- 100% open-source MPL-2.0 — sem vendor lock-in, auditável.
- Suporte nativo a **Design Tokens** (sem plugins pagos).
- Self-hosted via Docker uma linha: bom para clientes Flockr enterprise security policy.
- Mesma abstração do nosso `domains/ux/` = profile.md / playbook.md / gates / templates IGUAIS. Só muda o connector. Se aguenta PenPot → prova que a Domain Layer é agnóstica de ferramenta.

---

## Instalação MCP (PenPot oficial maintainer community)

```bash
# 1. Instalar package oficial MCP via npm corepack pnpm
corepack pnpm add -g @penpot/mcp

# 2. Autenticar (igual gh CLI / figma CLI pattern §18 / §20)
#    OAuth via browser. Token salvo em ~/.config/penpot/credentials.json (NÃO commitar)
penpot auth login --host https://design.penpot.app  # SaaS oficial
# OU self-hosted:
penpot auth login --host https://penpot.<sua-empresa>.com
```

---

## Operações suportadas (mesma granularidade Figma MCP)
| Operação DesignOps | Ferramenta PenPot MCP |
|---|---|
| Listar projetos, arquivos, pages | `penpot.projects.list`, `penpot.files.getTree` |
| Get node específico (Frame, Component, shape) | `penpot.nodes.get` |
| Export SVG / PNG 2x / PDF (handoff) | `penpot.exports.svg`, `penpot.exports.png`, `penpot.exports.pdf` |
| **Ler e escrever Design Tokens** (coleções / modes) | `penpot.tokens.export`, `penpot.tokens.import` |
| Criar componentes / frames / shapes básicos | `penpot.shapes.createRect`, `penpot.shapes.createText` etc. |
| Análise colors / spacing / typography (auditoria) | `penpot.analyze.colors`, `penpot.analyze.spacing`, `penpot.analyze.typography` |
| **Diff design vs implementação código** (base Pixel Gate) | `penpot.devmode.diffAgainstDOM` |

---

## Fluxo cross-tool PenPot → Figma (se cliente usar os 2)
Se empresa tiver equipes mistas:
1. Design criado em PenPot.
2. Exportar tokens PenPot → JSON `penpot.tokens.export`.
3. Importar mesmo JSON em Figma via `figma variables import` CLI.
4. Gates Pixel/A11y rodam IGUAL independente.

> **Regra chave:** Artefatos de domínio (profile, playbook, gates, templates) NUNCA dependem de uma ferramenta específica. Só dependem de thresholds numéricos. Se trocar Figma ↔ PenPot, zero refactor no core.

---

## Anti-patterns = Fail
1. ❌ `curl -X POST https://design.penpot.app/api/rpc/command/...` raw HTTP → §20 banido.
2. ❌ Compartilhar link "público qualquer pode editar" sem SSO — viola Forbidden Pattern de acesso.
3. ❌ Trocar para PenPot e "diminuir thresholds porque a ferramenta é nova": thresholds são do design, não da ferramenta. Se ferramenta não entrega threshold → não use. Não abaixa threshold.

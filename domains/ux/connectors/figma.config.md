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
  - "curl / fetch / HTTP raw request para REST API Figma"
  - "Hardcode FIGMA_PERSONAL_ACCESS_TOKEN em código ou variáveis inline"
  - "SDK sem wrapper CLI oficial"
---

# Connector Config — UX · Figma (MCP Oficial + CLI Oficial)

> **Obedece §20 engineering-contracts: NUNCA raw HTTP. Sempre MCP oficial primeiro, CLI oficial fallback, ou nada.** Fora desses 2 canais = violação de contrato. Sem exceção.

---

## Canal 1 (PRIORITY · recomendado): MCP oficial `mcp_open-pencil`

MCP já disponível no ecossistema TRAE. Nenhuma instalação adicional. Cobre 95% das operações DesignOps: ler nodes, exportar SVG/PNG, ler variables (tokens), aplicar valores, diff entre dev-mode design vs código implementado.

### Operações suportadas (exemplos de tool calls para agentes)
| Operação DesignOps | Ferramenta MCP `mcp_open-pencil.*` |
|---|---|
| Listar documentos Figma na workspace | `list_documents` |
| Abrir arquivo Figma específico pelo file_id | `open_file` + `get_page_tree` |
| Get node específico por id (Frame, Component, Instance) | `get_node` |
| Get children nodes recursivo uma Page | `node_children` + `node_tree` |
| **Diferenças pixel / layout desvio** (base do Gate Pixel Perfect) | `diff_jsx` (dev-mode) + `export_image` comparativo |
| Get Design Tokens / Variables (coleções) | `list_variables` + `get_variable` |
| Set design tokens em coleção existente (atualizar valor) | `set_variable` |
| Export SVG component (handoff dev) | `export_svg` |
| Export PNG 2x / PDF | `export_image` + `export_pdf` |
| Criar novo node / rectangle / text / shape básico | `create_shape` + `create_vector` + `insert_icon` (Lucide oficial) |
| Análise colors / typography / spacing no design (auditoria tokens) | `analyze_colors`, `analyze_typography`, `analyze_spacing` |
| Query nodes por critério (ex: "todos buttons radius xs") | `query_nodes` + `find_nodes` |

### Exemplo fluxo de uso (prático para o piloto)
```
1. Figma link: https://www.figma.com/design/<FILE_ID>/Flockr-Platform?node-id=<NODE_ID>
2. Extrair FILE_ID manualmente ou via parse URL
3. run_mcp → mcp_open-pencil.get_node(node-id=<NODE_ID>)
4. result: layout exato (padding 16/24, radius md, color token primary-500, weight 600)
5. Handover: copiar valores absolutos para dev-handoff-template.md SEM precisar abrir o Figma.
```

---

## Canal 2 (Fallback MCP indisponível): CLI npm Oficial `figma-cli`

Community maintained oficial Figma. Instalação one-shot via Corepack pnpm:

```bash
corepack pnpm add -D figma-cli
```

### Autenticação CLI (§18 pattern igual GitHub gh-only = NUNCA token hardcode)
1. Rodar `figma login` — browser abre, OAuth flow, salva token em `~/.config/figma/credentials.json` (não versionado).
2. **NÃO exportar `FIGMA_TOKEN` no shell diretamente.** Se precisar CI: usar SECRET MANAGER da plataforma (Vercel Env Crypt, GitHub Actions Encrypted Secrets), com prefixo `FIGMA_PAT_` — NUNCA commitar em `.env` ou código.

### Comandos CLI úteis para Handoff
```bash
# [STEP 1/3] Listar arquivos da team (mesma permissão MCP list_documents)
figma team list --team-id <TEAM_ID>

# [STEP 2/3] Export PNG hi-fi 2x + SVG component para pasta handoff
figma export <FILE_ID> --node <NODE_ID> --format png --scale 2 --output docs/ux/<slug>/assets/
figma export <FILE_ID> --node <NODE_ID> --format svg --output docs/ux/<slug>/assets/icons/

# [STEP 3/3] Extrair variáveis (tokens) para JSON para engineering importar
figma variables export <FILE_ID> --output docs/ux/<slug>/tokens.json --format json
```

---

## Compatibilidade com §13 Language 4-axis
- Nomes variáveis / nomes arquivos export = sempre EN (LANG_CODE).
- Labels dentro do design = LANG_DOCS definido no projeto (ex: pt-BR Flockr Brasil).
- Reports diff / auditoria tokens = LANG_REPORT = en (para CI cross-company).
- Conversa com designer user = LANG_CHAT (default pt-BR Brasil).

---

## Anti-patterns = Fail Gate A11y / Compliance Heavy
1. ❌ `fetch('https://api.figma.com/v1/files/...', headers:{Authorization:'Bearer '+token})` — raw HTTP banido §20.
2. ❌ Colocar FIGMA_TOKEN em `.env.example` commited.
3. ❌ Exportar SVG com `fill="#2563eb"` hardcoded inline sem `fill="currentColor"` → viola Forbidden Pattern #6 do profile.
4. ❌ Implementar design sem rodar `diff_jsx` ou pelo menos `get_node` para pegar medidas exatas → medidas "olhadas" = Gate Pixel Perfect Fail.

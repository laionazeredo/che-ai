---
domain: "ux"
version: "0.1.0"
status: "Active · Pilot"
gate_files_required:
  - "domains/ux/gates/pixel-check-gate.md"
  - "domains/ux/gates/accessibility-gate.md"
templates_required:
  - "domains/ux/templates/component-spec-template.md"
  - "domains/ux/templates/dev-handoff-template.md"
connectors_optional:
  - "domains/ux/connectors/figma.config.md"
  - "domains/ux/connectors/penpot.config.md"
cross_skills:
  - "/che-figma (build + implement)"
  - "/figma-pixel-check (validação pixel-perfect)"
  - "/che-ship §0.9.5 DOMAIN GATES (execução gates no ship)"
---

# Playbook — UI/UX DesignOps (`ux`) · 5 Etapas Obrigatórias (NÃO PULA)

> **Garantia de qualidade:** Este playbook NÃO tem etapas opcionais. Pular etapa = Fail prévio no Gate de Quality (etapa 3). Todas etapas produzem artifacts persistentes no workspace. Reuso 100% §19 Logging Standard core: scripts de export tokens Figma → JSON usam echo `[STEP N/M]` numerado anti-flood.

---

## Fase 0 — Preconditions & Brief / Discovery (JTBD, NÃO design visual ainda)

### Objetivo
Entender o PROBLEMA antes de abrir o Figma/PenPot. "Design é solução de problema. Sem problema definido, todo wireframe é belo e inútil."

### Input obrigatórios para começar
- ✅ Ticket / SPEC aprovado com: `user_story`, `persona_primary`, `success_metric` (1 número, não prose).
- ✅ Research bruta (se houver): notes de user-interview, heatmaps, analytics GA4/Hotjar (NÃO inventamos dados).

### Etapas 0.1 → 0.4 (não pula)
0.1 **Framework JTBD:** Escrever literalmente:
   ```
   When <SITUACAO>, I want to <ACAO_USUARIO>, so I can <RESULTADO_ESPERADO>.
   ```
   Máximo 1 linha por JTBD. Mínimo 3 JTBDs únicos por feature. Sem "melhorar UX" (vazio).
0.2 **User Persona canônica:** Linkar `domains/ux/profile.md` persona + acrescentar 1 parágrafo contexto específico dessa tela. Se não existir persona no registry level 1.5 → criar via `/che-project-knowledge --edit` (não só inline).
0.3 **User flow canônico Mermaid:** Diagrama `flowchart TD` mínimo 3 nodes (Entry → Action A → Success State + Error State). NÃO stadium shapes. Quebras com `<br/>` HTML.
0.4 **Approved Gate humano:** Brief + JTBD + flow Mermaid enviados para usuário. **Aprovação EXPLÍCITA (reply "Approved" literal) é obrigatória.** Sem aprovação → NÃO AVANÇA etapa 1.

### Artifacts gerados (persistir no workspace)
- `docs/ux/<slug>-01-brief-jtbd.md` — Etapas 0.1 → 0.4 tudo consolidado.
- Entry no `decisions.log.jsonl` tipo `[UX-BRIEF-APPROVED] <slug>` com hash do conteúdo.

---

## Fase 1 — Wireframe baixa fidelidade (estrutura, NÃO estética)

### Objetivo
Validar ESTRUTURA informacional e hierarquia. Nenhuma cor, nenhum ícone, nenhum typography fancy. Só caixas + texto placeholder + setas.

### Etapas 1.1 → 1.3 (não pula)
1.1 **Mobile-first obrigatório:** Wireframe começa no viewport **SM (390px wide)**. NUNCA começa em desktop e reduz. Depois de mobile aprovado → MD (768), depois LG (1024).
1.2 **Wireframe somente primitivas:** Retângulos = sections. Linhas = textos (3 comprimentos: curto/medio/longo). Círculos pequenos = ícones. NÃO usam a cor brand nesta fase. Nenhuma sombra. Nenhum radius.
1.3 **Approved Gate humano:** Wire 3 breakpoints enviados para usuário. Aprovação EXPLÍCITA "Wireframe Approved" literal → avança etapa 2. Se ajustes estruturais → volta 1.1 / 1.2 refaz wire.

### Regras Hard Fail nesta fase
- ❌ Desktop-first wire (mobile-last) = Fail volta 0.
- ❌ Contém ícones reais / imagens / radius / cor brand = Fail volta 1.
- ❌ NÃO tem 3 breakpoints (SM / MD / LG) = Fail incompleta.

### Artifacts gerados
- `docs/ux/<slug>-02-wireframe-sm.md` + `md` + `lg` (3 arquivos)
- Link PenPot/Figma "Wireframe Low-fi" page.

---

## Fase 2 — Hi-fi Protótipo (Figma MCP oficial ou PenPot MCP oficial)

### Objetivo
Aplicar Design System tokens do `domains/ux/profile.md` (spacing/radius/color/typography/shadow/motion) no wireframe aprovado. Produzir artefato hi-fi para stake-holders + handoff dev.

### Etapas 2.1 → 2.5 (não pula)
2.1 **Set official connector:** Escolher 1 (um) connector oficial (NÃO RAW REST):
   - **Recomendado:** Figma via `domains/ux/connectors/figma.config.md` (MCP `mcp_open-pencil` oficial + npm `figma-cli`).
   - **Alternativa open-source:** PenPot via `domains/ux/connectors/penpot.config.md` (MCP PenPot oficial).
2.2 **Aplicar Design System tokens TODOS:** Todo valor vem de tabela do profile. Nenhum hex / px solto. Se falta um token → PRIMEIRO propõe novo token para o design system, DEPOIS usa.
2.3 **Tabela 7 states obrigatórios por componente interativo:**
   | State | Aparência obrigatória (ver profile tokens) |
   |---|---|
   | Default | Sem interação do usuário |
   | Hover | `:hover` com elevation md (4dp) + pointer cursor |
   | Focus | `:focus-visible` ring 2px primary-500 + offset 2px |
   | Active | `:active` com escala 0.97~0.98 + elevation sm |
   | Disabled | `aria-disabled="true"` + opacity 0.4 + cursor: not-allowed |
   | Loading | `aria-busy="true"` + role="status" + spinner token motion 300ms standard |
   | Error | Borda danger + ícone alert + texto helper + SR label |
2.4 **Breakpoints 4 completos:** SM (640) · MD (768) · LG (1024) · XL (1280). Cada breakpoint = layout exato, não "parecido".
2.5 **Link validado + comentários resolved:** Todas threads de comentário no Figma/PenPot = "Resolved". Link público/permissões concedidas.

### Artifacts gerados
- Figma File / PenPot Project link + page hi-fi.
- `docs/ux/<slug>-03-hifi-notes.md` (tokens usados, decisões não-triviais, alternativas consideradas).

---

## Fase 3 — Gates Quality Obrigatórios (Thresholds NUMÉRICOS, não avaliação subjetiva)

> **Executados por `/che-ship §0.9.5 DOMAIN GATES` automaticamente quando ship de uma feature com `domain: ux`.** Mesmo engine fail-fast do core (threshold + retry 1 grátis + human required após 2nd falha).

### Ordem de execução (alphabetical por arquivo nome, igual ship §0.9 G1-G4)

| # | Gate | Arquivo físico | Threshold Obrigatório | Retry Policy | Hard Stop? |
|---|---|---|---|---|---|
| G-UX-1 | **A11y WCAG 2.2 AA** | `domains/ux/gates/accessibility-gate.md` | `CRITICAL_count === 0` (0 erros críticos · qualquer número > 0 → FAIL). 10 checks automáticos via `@axe-core/cli` oficial. | 1ª falha: retry grátis aplicando recommendations do axe-core report. | ✅ Sim. 2ª falha → pede humano. Não abre PR. |
| G-UX-2 | **Pixel Perfect** | `domains/ux/gates/pixel-check-gate.md` | `score_0_to_10 ≥ 8.0` AND `pct_elements_within_4px_tolerance ≥ 95%`. Desvio > 8px em 1 único elemento crítico → FAIL. | 1ª falha: retry grátis aplicando recommendations (fixa os top-3 maiores desvios primeiro). | ✅ Sim. 2ª falha → pede humano. Não abre PR. |

### Log obrigatório por execução (decisions.log.jsonl)
```
[DOMAIN-GATE-EXECUTED] domain=ux gate=accessibility-gate status=PASS score=9.3 critical_count=0 duration_ms=4217 traceId=...
[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status=FAIL score=6.7 within_4px_pct=0.82 duration_ms=12143 traceId=...
```

### Override explícito proibido por padrão
Abaixar threshold de um gate (ex: pixel de 8.0 → 7.0) SÓ é permitido via `EXPLICIT_OVERRIDE` user VERBATIM em resposta no chat, **logado em decisions.log** com `[EXPLICIT_OVERRIDE] domain=ux gate=... old=8.0 new=7.0 reason="..."`. NUNCA o agente abaixa threshold sozinho.

---

## Fase 4 — Dev Handoff (entrega final estruturada para dev)

### Objetivo
**NÃO é só mandar link Figma/PenPot e torcer.** Nenhuma medida "olha no Figma". Tudo absolutamente tudo estruturado em Markdown e JSON.

### Etapas 4.1 → 4.5 (não pula)
4.1 **Preencher template `domains/ux/templates/dev-handoff-template.md` COMPLETO:** Campos obrigatórios = SPEC id + ticket id · medidas absolute px por breakpoint · browsers suportados lista · assets export SVG/PNG 2x path · animations duration/easing tokens · accessibility checklist final (15 itens do profile)
4.2 **Export design tokens → JSON automático:** Rodar script de extração Figma Variables / PenPot Design Tokens → arquivo `tokens.json` estruturado por categoria. Nenhum valor hardcoded.
4.3 **Rodar `/figma-pixel-check` (se usado skill implementação codegen `/che-figma`):** Report anexar no handoff.
4.4 **Rodar `@axe-core/cli` axe-core accessibility final:** Report JSON + HTML anexar no handoff.
4.5 **Approved humano final:** Dev (ou usuário) confirma "Handoff Completo e Entendido" literal.

### Checklist de entregáveis FINAL para encerrar playbook
- [x] Etapa 0 JTBD Brief Approved ✅
- [x] Etapa 1 Wireframe SM/MD/LG Approved ✅
- [x] Etapa 2 Hi-fi 4 breakpoints + 7 states componentes ✅
- [x] Etapa 3 Gate G-UX-1 (A11y) PASS critical_count=0 ✅
- [x] Etapa 3 Gate G-UX-2 (Pixel) PASS score≥8.0 AND ≥95% ≤4px ✅
- [x] Etapa 4 `dev-handoff-template.md` 100% preenchido ✅
- [x] Etapa 4 `tokens.json` exportado ✅
- [x] Entry final decisions.log: `[UX-PLAYBOOK-COMPLETE] slug=... gate_results={a11y:PASS,pixel:PASS} handoff_path=...` ✅

> **Fim do playbook.** Agora o `/che-ship` executa §0.9 G1-G4 normalmente (scope / review / compliance / QA), depois §0.9.5 G5 Domain Gates confirma novamente G-UX-1 e G-UX-2 nos artifacts gerados, e abre Draft PR.

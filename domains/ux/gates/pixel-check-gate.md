---
gate_id: "ux-pixel-check-gate"
domain: "ux"
version: "0.1.0"
inspired_by_skill_referencia: "Flockr /figma-pixel-check skill oficial (ver domains/ux/profile.md cross-references)"
threshold_pass: "score_0_to_10 ≥ 8.0  AND  pct_elements_within_4px_tolerance ≥ 95%"
threshold_single_critical_fail: "Qualquer elemento crítico único (CTA button, heading hero) com desvio > 8px → FAIL, independente do score geral."
tool_primary: "MCP oficial mcp_open-pencil.diff_jsx (dev mode) + export_image + node_bounds"
tool_fallback: "CLI npm oficial figma-cli export + pixelmatch biblioteca npm"
retry_policy: "1 free automático (fixa os 3 maiores desvios / padding / radius / font-size). 2nd falha → HUMAN REQUIRED hard stop ship."
log_format_decisions: "[DOMAIN-GATE-EXECUTED] domain=ux gate=pixel-check-gate status={PASS|FAIL} score={x.y} within_4px_pct={0.xx} deviation_max_px={n} duration_ms={ms} traceId=..."
---

# Gate Executável — UX · Pixel Perfect (baseado `/figma-pixel-check`)

> **Filosofia: Medidas absolutas por elemento (padding, radius, tamanho fonte, cor hex EXATA, posição X/Y) são NUMÉRICAS — não tem gosto. Não avaliamos "beleza" — avaliamos desvio absoluto de N pixels entre referência Figma/PenPot e implementação código. 100% matemático. 0% subjetivo.**

---

## 0. Pré-requisitos
- Referência design válida: arquivo Figma/PenPot com node_id ou frame específico. NÃO "imagem qualquer".
- Implementação código rodando localmente (Next.js build ou dev server).
- Conexão MCP `mcp_open-pencil` autenticada OU CLI `figma-cli` logada.
- Fallback biblioteca npm (se MCP indisponível):
  ```bash
  corepack pnpm add -D pixelmatch pngjs @playwright/browser-chromium
  ```

---

## 1. Metodologia de Comparação (13 elementos por frame analisado)

Para cada node/frame único = uma página / tela / componente, nós medimos ABSOLUTO esses valores e comparamos referência vs implementação:

| # | Categoria Medição | Como medimos | Tolerância permitida (pass) |
|---|---|---|---|
| 1 | **Width / Height box model** | `node.width`, `node.height` (Figma) vs `getBoundingClientRect()` (implementação) | ≤ 4px em cada eixo |
| 2 | **Padding-top / right / bottom / left internos** | 4 valores individuais | ≤ 4px cada (todos 4 tem que passar) |
| 3 | **Margin externo para siblings próximos** | Espaço entre elemento anterior e posterior | ≤ 4px |
| 4 | **Border-radius (todos 4 cantos top-left…bottom-right individualmente)** | Valor exato token profile: xs=2/sm=4/md=8/lg=16/xl=24/full=9999 | ≤ 2px (radius mais sensível; desvio 3px já é perceptível visualmente) |
| 5 | **Border-width / Border-color hex** | `getComputedStyle` vs Figma stroke | Width ≤1px · Cor delta E ≤ 5 CIE76 |
| 6 | **Typography font-size (px ponto a ponto)** | Computed vs Figma font size | ≤ 2px (muito sensível visual) |
| 7 | **Typography font-weight (400/500/600/700)** | Exato. Nenhuma tolerância. | EXACT match (não tem "quase 600"). |
| 8 | **Typography line-height (leading)** | Valor exato (1.5, 1.2, 1.4 profile) | ≤ 0.05 leading |
| 9 | **Typography letter-spacing** | 0.01em default, tokens exatos | ≤ 0.01em |
| 10 | **Foreground color hex / RGB (text)** | Delta E 1976 CIE76 | ≤ 5 (olho humano não vê diferença) |
| 11 | **Background color hex / RGB (surface)** | Delta E 1976 CIE76 | ≤ 5 |
| 12 | **Box-shadow parameters (x/y/blur/spread/color alpha)** | 5 valores cada shadow individuo | x,y ≤ 2px · blur,spread ≤ 4px · alpha ≤ 0.04 |
| 13 | **Position X / Y absoluto no viewport SM/MD/LG/XL** (alinhamento grid 12 colunas) | Figma x,y vs screenshot | ≤ 8px por breakpoint |

---

## 2. Score Final 0–10 (weighted average ponderada por importância)

Cada elemento acima tem PESO diferente para score (mais importante = mais penalidade se errar):

| Peso | Categorias |
|---|---|
| **×2 (Peso duplo · Elemento Crítico)** | #2 Padding interno, #6 Font-size, #7 Font-weight, #10 Foreground color |
| **×1.5 (Peso médio)** | #3 Margin, #4 Radius, #13 Position X/Y |
| **×1 (Peso padrão)** | Todos os outros restantes |

### Cálculo
```
score_raw_por_elemento = max(0, 1.0 - (desvio_medido / tolerancia_permitida))
score_ponderado = Σ (score_raw_por_elemento × PESO) / Σ PESOS
score_final_0_10 = round(score_ponderado × 10, 1)
```

### PASS Condition (todas 3 têm que ser VERDADEIRAS ao mesmo tempo)
1. `score_final_0_10 ≥ 8.0`
2. `(total_medicoes_passadas / total_medicoes) ≥ 0.95` (95% dos valores individuais dentro tolerância)
3. **Nenhum elemento PESO ×2 (crítico) tem desvio > 8px** (CTA button 8px padding errado = FAIL, mesmo que resto score 9.0)

---

## 3. Execução Prática (step-by-step)

### 3.1 Método Recomendado (rápido, MCP nativo, mesmo script `/figma-pixel-check`)
```
1. Abrir página implementada no browser (Playwright / local dev server).
2. Identificar node_id da referência Figma/PenPot exato (mesma tela, mesmo breakpoint).
3. run_mcp → mcp_open-pencil.diff_jsx(
     file_id: FIGMA_FILE_ID,
     node_id: REFERENCE_NODE_ID,
     actual_dom_screenshot: <screenshot atual página>
   )
4. Result: diff lista cada valor (Figma X valor vs Actual Y valor, desvio N px, peso).
5. Calcular score usando fórmula acima. Output JSON estruturado + relatório visual.
```

### 3.2 Fallback (MCP indisponível, CLI figma + pixelmatch)
```bash
# [STEP 1/4] Export screenshot REFERÊNCIA Figma
corepack pnpm figma export FILE_ID --node NODE_ID --format png --scale 2 --output /tmp/figma-ref.png
# [STEP 2/4] Screenshot implementação código mesmo viewport
npx playwright screenshot --viewport-size="1280,832" http://localhost:3000/<slug> /tmp/actual.png
# [STEP 3/4] pixelmatch quantifica diff pixels
corepack pnpm -e "import pixelmatch from 'pixelmatch'; ...match diff, devolve JSON desvio."
# [STEP 4/4] Parse → score. Mesma fórmula, mesmo threshold.
```

---

## 4. Retry Policy (igual A11y gate)
| Falha # | Ação |
|---|---|
| **1ª falha** | **Retry GRÁTIS AUTOMÁTICO**: Pega as 3 medições com MAIOR desvio (top 3) e aplica o fix óbvio (padding: 12→16, radius: 4→8, color: #...). Re-roda o gate 1x nova vez. |
| **2ª falha** (após retry automático) | **HARD STOP ship §0.9.5 DOMAIN GATES.** Não abre PR. Mensagem: "GATE G-UX-2 PIXEL FAIL após retry. Score atual = {s} ≥8.0? N. Top 3 desvios: [...]. Fix manual ou EXPLICIT_OVERRIDE user VERBATIM logado em decisions.log." |
| **EXPLICIT_OVERRIDE (SÓ user VERBATIM)** | `[EXPLICIT_OVERRIDE] domain=ux gate=pixel-check-gate old=8.0 new={x.y} reason="..."` |

---

## 5. O que este gate NÃO faz (delimitado propósito, KISS)
- ❌ Não avalia "beleza visual" / gosto pessoal → só desvio numérico.
- ❌ Não valida animações / motion → motion fica em `domains/ux/gates/motion-gate.md` (fase 2 futuro, não criado hoje).
- ❌ Não valida conteúdo textual copy → copy gate separado domínio copywriting (fase 2 futuro).
- ❌ Não substitui a validação A11y → roda A11y Gate ANTES deste. Layout correto com inacessível = Fail mesmo.

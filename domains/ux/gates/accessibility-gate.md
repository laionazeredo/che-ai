---
gate_id: "ux-accessibility-gate"
domain: "ux"
version: "0.1.0"
threshold_hard_stop: "CRITICAL_count > 0 → HARD FAIL"
tool_official: "@axe-core/cli (npm package by Deque Systems, maintainer oficial WCAG)"
tool_package_manager: "npm"
retry_policy: "1 free automático aplicando axe-core recommendations. 2nd falha = HUMAN REQUIRED hard stop ship."
log_format_decisions: "[DOMAIN-GATE-EXECUTED] domain=ux gate=accessibility-gate status={PASS|FAIL} critical_count={n} serious_count={m} duration_ms={ms} traceId=..."
wcag_level: "WCAG 2.2 AA (nível mínimo HARD STOP. AAA não obrigatório, pontos de AAA marcados como optional bonus.)"
---

# Gate Executável — UX · Accessibility (axe-core CLI · WCAG 2.2 AA)

> **Mesmo fail-fast engine G1-G4 ship §0.9:** Threshold NUMÉRICO, retry 1 automático, 2nd falha = HUMAN REQUIRED, EXPLICIT_OVERRIDE só via user VERBATIM logado em decisions.log. Nenhuma avaliação subjetiva "achamos que acessível".

---

## 0. Pré-requisitos (instalar uma vez por workspace)

```bash
# [STEP 0/2] Instalar @axe-core/cli oficial Deque (§20 = NÃO use puppeteer raw, NÃO use Lighthouse isolado sem axe-core)
corepack pnpm add -D @axe-core/cli playwright
# [STEP 1/2] Instalar browsers Playwright para o CLI (se não tiver global)
corepack pnpm exec playwright install chromium
```

---

## 1. Thresholds OBRIGATÓRIOS (fail = qualquer um violado)

### 1.1 Níveis de severidade axe-core (mesmos padrões MDN / W3C)
| Severidade axe-core | O que significa | PASS condition |
|---|---|---|
| **CRITICAL** | Violação grave WCAG AA: trava leitura screen reader, impossibilita navegação keyboard, inacessibilidade total. | `COUNT === 0` (ZERO). Qualquer número ≥ 1 → **HARD FAIL imediato SEM retry automático? Não → tem retry 1, mas 2nd falha hard stop.** |
| **SERIOUS** | Violação importante WCAG AA: contraste ruim, heading hierarquia quebrada, alt faltando. | `COUNT ≤ 3`. Maior que 3 → WARNING, não FAIL por padrão (mas avaliação de score final penaliza). Se ≥ 10 → FAIL. |
| **MODERATE / MINOR** | Boas práticas, melhorias. | Não influenciam PASS/FAIL, apenas reportados para log. |

### 1.2 10 checks automáticos OBRIGATÓRIOS sempre rodados
(Todos fazem parte do conjunto ruleset padrão `wcag22aa` do axe-core. Nenhum desligado.)
1. **color-contrast** — contraste texto/background (tabela profile body ≥ 4.5:1 · heading grande ≥ 3.0:1).
2. **document-title** — `<title>` não vazio, único, descritivo por página.
3. **html-has-lang** — `<html lang="pt-BR">` ou `en` configurado por projeto (§13 Language 4-axis).
4. **image-alt** — tags `<img>` tem alt ou alt="" (decorativa). Nunca alt faltando.
5. **button-name** — `<button>` tem nome acessível (texto visível ou aria-label / aria-labelledby).
6. **link-name** — `<a>` tem nome acessível (não "Clique aqui" / "Saiba mais" sem contexto).
7. **aria-allowed-attr** — atributos ARIA usados em roles permitidos (não `aria-label` em `<div>` genérico sem role).
8. **label** — `<input>` tem `<label>` associado, `aria-label` ou tá dentro de fieldset com legend. Nunca placeholder como label só.
9. **bypass** — "Skip to content" link antes de header (hidden visualmente, visível focus). H1 único por página.
10. **focus-order-semantics** — ordem de foco = ordem visual leitura. Nenhum tab pula seções. Nenhum `tabindex="> 0"` (tabindex positivo = anti-pattern WCAG).

---

## 2. Execução (one-liner padrão, igual CI)

```bash
# [STEP 1/3] Buildar app (Next.js) — necessário para pages estáticas
corepack pnpm nx run @flockr/platform:build

# [STEP 2/3] Rodar @axe-core/cli apontando para página (URL ou HTML buildado)
#     Ruleset EXPLICITO = wcag22aa (nunca default "best practices" misturado)
#     Saída: JSON estruturado + HTML visual para humanos
corepack pnpm axe --chromedriver-path $(corepack pnpm exec which playwright-chromium) \
  --rules wcag22aa \
  --tags wcag2a,wcag2aa,wcag22a,wcag22aa \
  --format json \
  --output-dir $HARNESS_SESSION_DIR/reports/ \
  --save accessibility-report.json \
  http://localhost:3000/<page-slug>

# Opcional também gerar relatório HTML bonito para stack-holders
corepack pnpm axe ...(mesmos flags)... --format html --save accessibility-report.html

# [STEP 3/3] Parse JSON → log decisions.log entry e comparar threshold
# (feito automaticamente pelo harness-ship §0.9.5 DOMAIN GATES)
#
# pseudo-código parse:
# critical_count = len([r for r in report.violations if r.impact === 'critical'])
# serious_count  = len([r for r in report.violations if r.impact === 'serious'])
# PASS = critical_count === 0 AND serious_count <= 3 AND (todos 10 checks acima com NONE violation)
```

---

## 3. Retry Policy (exatamente igual core G2 code-review)

| Falha Número | Ação |
|---|---|
| **1ª falha** (qualquer motivo) | **Retry GRÁTIS AUTOMÁTICO**: Executa `axe-core` recommendations para cada violação CRITICAL (fix 1-click do axe-core quando possível). Por exemplo: adiciona alt ausente, corrige label ausente, adiciona `:focus-visible` outline. Re-roda gate NOVA vez. |
| **2ª falha** (continua CRITICAL_count ≥ 1 após retry automático) | **HARD STOP ship**: NÃO abre nenhum PR. Pede humano (designer / dev / acessibilidade expert). Mensagem erro padronizada: "GATE G-UX-1 A11Y FAIL após retry. CRITICAL issues restantes = N. Fix manual ou EXPLICIT_OVERRIDE VERBATIM user logado em decisions.log." |
| **EXPLICIT_OVERRIDE** (SÓ se user VERBATIM falar "ignora a11y aqui" EXPLICITAMENTE) | Log obrigatório `[EXPLICIT_OVERRIDE] domain=ux gate=accessibility-gate old=CRITICAL_count=0 new=permit N reason="..."` → threshold muda, mas fica audit trail para sempre. NUNCA o agente decide sozinho. |

---

## 4. Score adicional (0–10) — não influencia PASS/FAIL, mas vai para relatório final
- `+2 pts` se passar AAA opcional (não obrigatório)
- `+1 pts` se MODERATE_count === 0
- `+1 pts` se rodou e reportou em 4 breakpoints SM/MD/LG/XL (não só desktop)
- `score_final = base PASS 7.0 + extras`

---

## 5. Compatibilidade com §13 Language 4-axis
- Mensagens erro para o humano (LANG_CHAT): pt-BR
- Nome dos rulesets / saída JSON axe-core: sempre EN (LANG_CODE)
- Reports HTML para stakeholders: LANG_DOCS (pt-BR se projeto Brasil)
- Logs estruturados decisions.log: sempre EN (LANG_REPORT)

---
name: "ui-testing-contracts"
description: "Defines canonical UI testing contracts for Testing Library selectors, Playwright helpers, data-testid naming, and accessibility-focused test hygiene."
---

# UI Testing Contracts Skill

> Helper helper para UI tests (RTL + Playwright + data-testid 3-part convention).
> Invocado via `/che-ui-testing` quando usuário pede ajuda com: selectors CSS, testes UI, data-testid attributes, Playwright boilerplate, RTL Testing Library order enforcement.
> Integração: cross-reference com Category8 UI Hygiene (ONDA1 code-review) e SbE Behavior Table coluna "UI Selector Contract" (ONDA2 che-spec).

---

## §1 Kent C. Dodds Testing Library Priority Order Enforcement (CANÔNICO — CATEGORY 8 G8.2 HIGH)

**Priority Order canônico Kent C. Dodds (Testing Library 2023) — USAR ESTA ORDEM ESTRITA SEMPRE:**

1. ✅ **`ByRole`** (primeira escolha SEMPRE) — ex: `getByRole('button', { name: 'Confirm refund' })`
2. ✅ **`ByLabelText`** — campos de formulário com label (input, select, textarea)
3. ✅ **`ByPlaceholderText`** — inputs com placeholder mas sem label visível
4. ✅ **`ByText`** — parágrafos, spans, texto exibido ao usuário
5. ✅ **`ByDisplayValue`** — valor atual exibido num input preenchido
6. ✅ **`ByAltText`** — imagens (`<img alt="Event logo">`)
7. ✅ **`ByTitle`** — `<svg title="Search icon">` ou `title` attribute HTML
8. ⛔ **`ByTestId` (data-testid)** — **ÚLTIMO RECURSO APENAS**, use SOMENTE quando:
   - Elemento não tem role/texto acessível (ex: toast messages, icon-only buttons)
   - Texto é dinâmico / traduzido (i18n muda o texto)
   - Múltiplos elementos com o mesmo texto (ex: botões "Edit" numa tabela)

### Snippet ByTestId Guard Clause Check (para code-review G8.2 HIGH)

```javascript
// ⛔ ANTI-PATTERN: usa getByTestId em elemento que tem role visível
const button = screen.getByTestId('refund__btn__confirm');

// ✅ CORRETO: usa ByRole com nome acessível primeiro
const button = screen.getByRole('button', { name: /confirm refund/i });

// 👮 ByTestId SÓ SE NÃO HÁ OUTRA FORMA
const toastIcon = screen.getByTestId('refund__toast__success-icon');
```

---

## §2 Playwright Flockr Boilerplate Helper — `byTestId()` Wrapper (G8.3 convention 3-partes)

### Snippet TypeScript Verbatim (copiar-colar em fixtures Playwright do projeto Flockr):

```typescript
// Playwright boilerplate Flockr — usa data-testid convention 3-partes (domain__component__action)
import { Page, expect, test } from '@playwright/test';

// Wrapper helper (reutilizável em qualquer arquivo .spec.ts)
const byTestId = (id: string, page: Page) => page.getByTestId(id);

// Exemplo de teste completo — título = comportamento PÚBLICO OBSERVÁVEL (NÃO colocar IDs no título)
test('confirms a full refund succeeds and displays success toast', async ({ page }) => {
  // @ac B-1 | @ticket FLO-513  ← 1ª LINHA DENTRO DO BLOCO it()/test() — NÃO no título
  // Arrange: navegar página booking
  await byTestId('booking__row__btn-actions', page).click();

  // Act: abrir modal + confirmar
  await byTestId('refund__action-btn__open-modal', page).click();
  await byTestId('refund__modal-input__reason', page).fill('Customer cancelled');
  await byTestId('refund__action-btn__confirm', page).click();

  // Assert: behavior público observável
  await expect(byTestId('refund__toast__success-message', page)).toBeVisible();
  await expect(byTestId('booking__row__status-label', page)).toHaveText(/refunded/i);
});
```

---

## §3 3-Part data-testid Convention Regex Lint Inline (G8.3 MEDIUM enforcement)

### Convenção canônica (Category 8 G8.3 / SbE UI Selector Contract):

```
Formato: <domain>__<component-or-screen>__<action-or-element>[--<unique-id>]
- Todos lowercase kebab-case a-z 0-9 hífens simples
- Separador entre partes: DUPLO underscore `__` (NÃO usar `-` ou `_` único como separador de NÍVEL)
- Unique ID opcional no final com DUPLO hífen `--` (ex: linhas de listas duplicadas)
Exemplos VÁLIDOS:
  ✅ refund__modal__confirm-btn
  ✅ refund__toast__success-message
  ✅ booking__table__row-actions--bk-456  (unique suffix p/ linhas duplicadas)
  ✅ scanner__qr-reader__camera-button
Exemplos INVÁLIDOS (viola G8.3 MEDIUM):
  ❌ RefundModalConfirm (camelCase / kebab errado)
  ❌ refund-modal-confirm (separador simples errado)
  ❌ btn-confirm (2 partes só, faltou domain)
  ❌ refund__modal__btn__confirm (4 níveis — máximo 3 + unique suffix)
```

### Grep one-liner enforcement (rodar em PRs manualmente):

```bash
# Conta número de data-testid VIOLANDO a convenção 3-partes
grep -rnE 'data-testid=' --include='*.tsx' --include='*.ts' packages/ \
  | grep -cvE 'data-testid="^[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*(--[a-z0-9][a-z0-9-]*)?$"'

# Resultado: 0 = SEM violações ✅; ≥1 = WARNING G8.3 MEDIUM (número acima = qtd violações)
```

### Regex canônico (usar em lints / custom ESLint rule):

```regex
^[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*__[a-z0-9][a-z0-9-]*(--[a-z0-9][a-z0-9-]*)?$
```

---

## §4 Cross-reference Category 8 UI Hygiene (Code-review gate ONDA1) + SbE Enforcement

### Canais de enforcement (ONDA1 + ONDA2):

| ID G8 Category 8 | Severity | O que flaggar | Cross-ref this skill |
|---|---|---|---|
| G8.1 | 🟠 HIGH | **Novo componente interativo SEM `data-testid`** quando ByRole/ByLabel não é estável (icon-only, toast, spinner, linhas tabela) | §1 ByTestId last escape hatch + §2 boilerplate |
| G8.2 | 🟠 HIGH | **Teste usa `nth-child()` / XPath 1..N / classes CSS (`css=.btn-primary div:nth(3)`** em vez de ByRole + ByTestId | §1 Priority Order enforcement + guard clause snippet |
| G8.3 | 🟡 MEDIUM | Nome `data-testid` FORA da convenção 3-partes (camelCase, 2 níveis, separador errado, uppercase) | §3 regex lint + grep one-liner |
| G8.4 | 🔵 LOW | IDs duplicados em listas/tabelas SEM unique suffix `--<id>` no final (ex: múltiplas linhas booking com mesmo `booking__row__delete-btn`) | §3 convenção parte opcional `--<unique-id>` |

### SbE Spec Integration (ONDA2 che-spec §4.2 Behavior Table nova coluna):

Quando uma SbE spec tem **Playwright ou RTL marcado ✅ na coluna "Test Layers"**, OBRIGATÓRIO preencher a coluna **"UI Selector Contract"** com o data-testid 3-partes exato:

| B-ID | Given | When | Then observável | Unit | Integ | Playwright | UI Selector Contract |
|---|---|---|---|---|---|---|---|
| B-1 | ... | Clica Confirm | Toast success visível | - | - | ✅ | `refund__toast__success-message` + `refund__action-btn__confirm` |

> SbE + G8.3 = enforcement end-to-end: spec define o ID → componente implementa `data-testid=X` → teste Playwright usa `byTestId(X)` → code-review verifica G8.1-G8.4 → scope-checker CHECK2 bilateral confere B-ID ↔ ↔ anchor ↔ data-testid.

---
template_id: "ux-component-spec"
domain: "ux"
version: "0.1.0"
consumed_by_playbook_etapa: "Etapa 2 — Hi-fi Protótipo (apos tokens aplicados, antes gates quality)"
cross_ref_design_tokens_table: "domains/ux/profile.md §Conventions tokens escala 4/8"
cross_ref_states_table: "domains/ux/playbook.md Etapa 2.3 tabela 7 states"
---

# Template — Component Specification (Entra no Design System)

> **Preencher 100% os campos obrigatórios (🔴). Campos opcionais (🟡) só preencher se aplicar.** Nenhum campo "aproximadamente". Tudo tokens ou valores exatos. Sem "tenta". Sem "ver no Figma".

---

## Metadata (🔴 obrigatório 100%)
| Campo | Valor preenchido aqui |
|---|---|
| **Component Nome canônico (slug EN · PascalCase)** | 🔴 `<ComponentName>` |
| **Categoria Design System** | 🔴 `Primitives` / `Components` / `Patterns` / `Templates` |
| **Responsável owner (equipe/designer/dev)** | 🔴 `<nome>` |
| **Ticket / SPEC ID associado** | 🔴 `<LINEAR-ID>` / `<SPEC-slug.md>` |
| **Dependências outros componentes** | 🟡 `<ComponentA>, <ComponentB>` |
| **Figma / PenPot link dev-mode node** | 🔴 `https://...?node-id=<ID>` |
| **Mobile-first? (sempre SIM)** | 🔴 ✅ Sim / ❌ Não (se Não → justificar abaixo) |
| **Se Não mobile-first, justificativa ADR:** | 🟡 `Apenas em telas desktop interno admin. Breakpoint mínimo MD ≥768` |

---

## 1. Design Tokens usados por este componente (🔴 obrigatório TODOS)

> **Regra de ouro:** TODO valor NESTA seção referencia o TOKEN e seu VALOR, NÃO só valor solto. Exemplo: ✅ `spacing.md (16px)`. ❌ Apenas `16px`. Se você precisou de um valor que não existe nos tokens → PRIMEIRO cria token, DEPOIS referencea aqui. Nenhuma exceção.

### 1.1 Spacing (interno padding · externo margin)
| Token | Valor | Aplicado em qual posição? |
|---|---|---|
| 🔴 spacing.`<xs|sm|md|lg|xl|...>` | `X px` | padding-top / padding-right / padding-bottom / padding-left |
| 🔴 spacing.`<md|lg|...>` | `X px` | margin-top / margin-right / margin-bottom / margin-left (elementos fora) |

### 1.2 Radius
| Token | Valor | Aplicado em (container / button / input?) |
|---|---|---|
| 🔴 radius.`<xs|sm|md|lg|xl|full>` | `X px` | corners container / botão / avatar ... |

### 1.3 Cores (Foreground text · Background surface · Border stroke)
| Token (ex: neutral-900 / primary-500 / danger) | Valor Hex/RGB | Aplicado em? |
|---|---|---|
| 🔴 color.`<on-primary / on-surface / ...>` | `#...` | Text heading / Text body / Text caption |
| 🔴 color.`<surface / background / primary-500>` | `#...` | Container bg / Button bg / Card bg |
| 🔴 color.`<neutral-200 / neutral-300>` | `#...` | Border stroke container / Divider |
| 🟡 color.`<success / warning / danger / info>` | `#...` | Badge estado / Alert tipo |

### 1.4 Typography (text styles por role)
| Role textual dentro do componente | Font Token size · weight · line-height | Valor exato |
|---|---|---|
| 🔴 Heading (se tiver H3/H4/H5/H6) | typography.`<3xl / 2xl / xl>` · bold/semibold · 1.2 / 1.1 | `31px / 700 / 1.2` |
| 🔴 Body (paragrafo) | typography.`<base / lg>` · regular/medium · 1.5 | `16px / 400 / 1.5` |
| 🔴 Caption / Helper / Badge | typography.`<xs / sm>` · medium/semibold · 1.4 | `12px / 500 / 1.4` |
| 🟡 Overline / Eyebrow | typography.`<xs>` · semibold · 1.4 · uppercase · tracking-wide | `12px / 600 / 1.4` |

### 1.5 Elevation / Shadow (🔴 obrigatório se componente flutua ex: Card/Dropdown/Modal)
| Shadow Token | Valor | Aplicado em state qual? |
|---|---|---|
| 🔴 elevation.`<sm / md / lg / xl>` | `0 4px 8px rgba(0,0,0,0.08)` | default / hover / active |

### 1.6 Motion (🟡 obrigatório se tem interação · animação)
| Interação (hover / focus / abrir modal) | Duration token | Easing token (standard / enter / exit) | Valor |
|---|---|---|---|
| 🟡 Button hover elevation change | duration.`<150ms / 300ms>` | easing.standard | `300ms cubic-bezier(0.2,0,0,1)` |

---

## 2. Os 7 Estados Obrigatórios (🔴 NENHUM pode faltar. Ver profile tabela states)
> Para cada estado, preencher: aparência descreta + valores exatos que mudam (ex: hover: elevation sm → md, +0.98 scale). NENHUM estado "não aplica". Todo componente interativo SEMPRE tem os 7.

| State | 🔴 Valores que mudam vs Default | ✅ Aparência descrita + screenshot path |
|---|---|---|
| **Default** | — (baseline todos tokens acima) | `<screenshot default>` |
| **Hover** `:hover` + pointer cursor | elevation sm→md, optional scale 0.98 | `<screenshot hover>` |
| **Focus-visible** `:focus-visible` | ring 2px primary-500 + ring-offset-2 surface | `<screenshot focus>` |
| **Active** `:active` / mousedown | scale 0.97 · elevation downgrade sm · opaco 0.96 | `<screenshot active>` |
| **Disabled** `disabled` / `aria-disabled` | opacity 0.4 · cursor not-allowed · remove hover interaction | `<screenshot disabled>` |
| **Loading** `aria-busy="true"` role="status" | conteúdo substituído por spinner · mesma width/height · texto SR "Carregando…" | `<screenshot loading>` |
| **Error / Invalid** `aria-invalid="true"` | borda 2px danger + ícone + helper text vermelho (ÍCONE + TEXTO + COR = nunca só cor) | `<screenshot error>` |

---

## 3. Breakpoints 4 completos (🔴 obrigatório mobile-first)
> Layout SÓ pode ter uma aparência? NÃO. Todo componente reage a SM/MD/LG/XL. Preencher: padding muda? Colunas quebram? Fonte diminui?

| Breakpoint · width | Viewport width | 🔴 Alterações neste componente? (paddings / fontes / grid columns) | Screenshot |
|---|---|---|---|
| **SM** | ≥ 640px | 🔴 `<descrição>` | `<sm>` |
| **MD** | ≥ 768px | 🔴 `<descrição>` | `<md>` |
| **LG** | ≥ 1024px | 🔴 `<descrição>` | `<lg>` |
| **XL ≥** | ≥ 1280px | 🔴 `<descrição>` | `<xl>` |

---

## 4. Acessibilidade Checklist Final (🔴 100% obrigatório preencher · resumo a11y gate)
- [ ] 🔴 **44×44px mínimo área toque mobile** em todos alvos interativos (botões / links / inputs / chips / tabs).
- [ ] 🔴 **Keyboard nav completo**: Tab / Shift+Tab / Enter / Space / Arrow keys / Esc → cada ação documentada nesta tabela.
- [ ] 🔴 **Foco segue ordem DOM visual**: não pula seções. Tabindex positivo PROIBIDO.
- [ ] 🔴 **Contraste todos textos**: Body ≥ 4.5:1 · Heading grande ≥ 3.0:1. Verificado.
- [ ] 🔴 **Focus ring NUNCA removido sem substituição adequada** (`outline: 0` banido).
- [ ] 🔴 **Roles / ARIA**: Botão tem `<button>`. Link tem `<a>`. Modal role="dialog" aria-modal="true". Alert role="alert". Nunca `<div onClick>`.
- [ ] 🔴 **Imagens**: Decorativa `alt=""` · Informativa `alt="..."` ≤125 caracteres. SVG icon aria-hidden + title se necessário.
- [ ] 🔴 **Reduced motion**: Animations DESLIGADAS se `prefers-reduced-motion: reduce`.
- [ ] 🔴 **Nunca só cor para indicar estado**: Sempre ícone + texto + cor (error state acima).
- [ ] 🟡 **Screen reader teste prático**: VoiceOver (macOS/iOS) ou NVDA (Windows) rodo e ouvi leitura correta. (Entrega bônus, não-obrigatória.)

---

## 5. Assinatura (Gate Approved por humano)
| Cargo | Nome | Data | Aprovação EXPLÍCITA ("Component Spec Approved" literal) |
|---|---|---|---|
| DesignOps / UI Designer responsável | `<nome>` | `<YYYY-MM-DD>` | ✅ / ❌ Comentários: `<...>` |
| Dev Frontend que vai implementar | `<nome>` | `<YYYY-MM-DD>` | ✅ / ❌ Comentários: `<...>` (medidas claras? tokens existem? etc.) |

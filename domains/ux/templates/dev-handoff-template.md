---
template_id: "ux-dev-handoff"
domain: "ux"
version: "0.1.0"
consumed_by_playbook_etapa: "Etapa 4 — Dev Handoff (ENTREGA FINAL · NÃO pula)"
cross_ref_component_spec_template: "domains/ux/templates/component-spec-template.md"
cross_ref_accessibility_gate: "domains/ux/gates/accessibility-gate.md"
cross_ref_pixel_gate: "domains/ux/gates/pixel-check-gate.md"
---

# Template — Developer Handoff Estruturado (NÃO é só link Figma)

> **Regra fundamental:** Dev NUNCA precisa abrir o Figma/PenPot para saber MEDIDAS EXATAS. Tudo neste arquivo. Se alguma medida estiver faltando → handoff INCOMPLETO → volta etapa 2. Nenhum "olha a página 3 frame B".

---

## 0. Header Metadata (🔴 obrigatório 100%)
| Campo | Valor |
|---|---|
| 🔴 **Handoff ID canônico slug** | `ux-handoff-<YYYYMMDD>-<slug-feature>` |
| 🔴 **SPEC ID aprovado** (link para `spec_<slug>.md` em workspace) | `../../specs/spec_<slug>.md` |
| 🔴 **Ticket Linear / ClickUp / Jira** | `<LINEAR-ID>` / `<CLICKUP-ID>` |
| 🔴 **Feature / Descrição 1 linha** | `<1 linha, o que essa entrega entrega>` |
| 🔴 **Designer Owner** | `<nome designer>` |
| 🔴 **Dev Owner atribuído** | `<nome dev frontend>` |
| 🔴 **Figma link page (OBRIGATÓRIO, mas como referência, não como única fonte medidas)** | `https://www.figma.com/design/<FILE_ID>/...?node-id=<ROOT_PAGE_ID>` |
| 🟡 **PenPot link page (se alternativo)** | `https://design.penpot.app/#/workspace/...` |
| 🔴 **Data da entrega handoff** | `<YYYY-MM-DD>` |
| 🔴 **Prazo implementação dev (estimativa)** | `<dias úteis>` |

---

## 1. Lista de Componentes + Telas nesta entrega (🔴 100%)
> Para CADA componente/tela novo ou modificado, referencia 1 arquivo `component-spec-template.md` preenchido (ver template irmão). Nenhum componente solto sem spec.

| # | Tela / Componente Nome (slug PascalCase) | Figma node_id direto | Component Spec preenchido link | Breakpoints suportados |
|---|---|---|---|---|
| 1 | 🔴 `<PageHeroSection>` | `?node-id=<ID>&m=dev` | `./components/component-spec-PageHeroSection.md` | ✅ SM · MD · LG · XL |
| 2 | 🔴 `<PrimaryButtonCTA>` | `?node-id=<ID>&m=dev` | `./components/component-spec-PrimaryButtonCTA.md` | ✅ SM · MD · LG · XL |
| N | ... | ... | ... | ... |

---

## 2. Medidas Absolutas por Breakpoint (🔴 NÃO "aproximadamente". TODOS os 4 breakpoints preenchidos)
> Layout container 12-colunas (mobile-first). Para cada breakpoint, medir o MAX-WIDTH container e os gutters.

### 2.1 Layout container global
| Breakpoint | Min-width viewport | Container MAX-WIDTH | Gutter esq/dir | Grid columns count | Gutter inter colunas |
|---|---|---|---|---|---|
| 🔴 SM | ≥ 640px | `<X px>` | `<16 / 24 px>` | 4 | `8 px` |
| 🔴 MD | ≥ 768px | `<X px>` | `<24 / 32 px>` | 8 | `12 px` |
| 🔴 LG | ≥ 1024px | `<X px>` | `<32 / 48 px>` | 12 | `16 px` |
| 🔴 XL | ≥ 1280px | `<X px>` | `<48 / 64 px>` | 12 | `16 px` |
| 🔴 2XL | ≥ 1536px | `<X px>` | `<64 / 96 px>` | 12 | `16 px` |

### 2.2 Tela / componente específico medidas (exemplo — repetir para cada tela)
**Nome Tela:** `<Homepage Hero Section>`
| Breakpoint | Hero Height | Padding top interno | Padding bottom | Heading size (H1) | Body copy size | CTA width / height | CTA gap |
|---|---|---|---|---|---|---|---|
| SM | `<px>` | `<px>` | `<px>` | `<31px / 700 / 1.1>` | `<16px / 400>` | `<full / 44px>` | `<12px>` |
| MD | `<px>` | `<px>` | `<px>` | `<39px / 700 / 1.1>` | `<16px / 400>` | `<260px / 48px>` | `<16px>` |
| LG | `<px>` | `<px>` | `<px>` | `<49px / 700 / 1.1>` | `<18px / 400>` | `<320px / 52px>` | `<20px>` |
| XL | `<px>` | `<px>` | `<px>` | `<61px / 700 / 1.1>` | `<18px / 400>` | `<360px / 56px>` | `<24px>` |

---

## 3. Assets Exportados (🔴 obrigatório path relativo pasta)
> SVG: sempre `fill="currentColor"` para ícones (Forbidden Pattern #6 profile). PNG: SEMPRE exportar 2x (@2x) para retina + 4x para 4K se imagem hero. Nenhuma imagem JPEG se não for fotografia real.

| Asset nome | Tipo | Path relativo nesta entrega | Tamanho px (W × H) | Densidade | Token color usado / Nota |
|---|---|---|---|---|---|
| 🔴 `<icon-user.svg>` | SVG Ícone interface | `./assets/icons/icon-user.svg` | `24×24` | Vetor | ✅ `fill="currentColor"` |
| 🔴 `<icon-arrow-right.svg>` | SVG Ícone | `./assets/icons/...` | `20×20` | Vetor | ✅ currentColor |
| 🔴 `<hero-background-mobile.png>` | PNG Imagem | `./assets/hero/...sm.png` | `640×960` | @2x | Otimizado AVIF / WebP + fallback PNG |
| 🔴 `<hero-background-desktop.png>` | PNG Imagem | `./assets/hero/...xl.png` | `1280×720` | @2x | ... |
| 🟡 `<illustration-empty-state.svg>` | SVG Ilustração | `./assets/illustrations/...` | `400×300` | Vetor | Cores tokens neutral/primary mantidas |

---

## 4. Browsers Suportados (🔴 obrigatório tabela)
> NUNCA escreva "últimas 2 versões" sem numerar. Sempre específico. Last 2 + iOS Safari 15.7+ mínimo.

| Browser Plataforma | Versão mínima suportada | Navegação / Touch? | Testado screenshot? |
|---|---|---|---|
| 🔴 Chrome (desktop) | Last 2 (130+) | Mouse + Keyboard | ✅ / ❌ |
| 🔴 Firefox (desktop) | Last 2 (131+) | Mouse + Keyboard | ✅ / ❌ |
| 🔴 Safari (macOS · WebKit) | Latest 2 (17.4+) | Mouse + Keyboard | ✅ / ❌ |
| 🔴 Chrome (Android) | Latest 2 | Touch + Android back | ✅ / ❌ |
| 🔴 Safari (iOS · iPhone) | iOS 15.7+ (mínimo absoluto, por questões de segurança) | Touch + Safari tab bar | ✅ / ❌ |
| 🟡 Edge (Windows) | Latest 2 | Mouse + Keyboard | ✅ / ❌ (PC tester) |

---

## 5. Motion / Animations tokens (🟡 obrigatório se houver interação)
| Interação | Elemento | Duration token | Easing token | Valor exato | Acessibilidade reduced motion? |
|---|---|---|---|---|---|
| 🟡 Hover CTA button | PrimaryButtonCTA | duration.150ms | easing.standard | `150ms cubic-bezier(0.2,0,0,1)` | ✅ desliga se prefers-reduced-motion |
| 🟡 Open modal overlay | `<ModalCheckout>` | duration.300ms | easing.enter + exit | `300ms enter · 150ms exit` | ✅ desliga |

---

## 6. Gates Quality Executados Results (🔴 obrigatório anexar reports · seção 3 playbook)
> Resultados do Gate G-UX-1 (A11y) e G-UX-2 (Pixel). NÃO só PASS/FAIL. Colocar score + JSON path.

| Gate | Resultado PASS / FAIL? | Score / threshold | Report JSON path relativo | Report HTML path (se tem para stakeholder) |
|---|---|---|---|---|
| 🔴 **A11y axe-core WCAG 2.2 AA** | PASS / FAIL | CRITICAL_count = N · serious_count = M · Score 0-10 = x.y | `./reports/accessibility-report.json` | `./reports/accessibility-report.html` |
| 🔴 **Pixel Perfect (referência Figma vs código)** | PASS / FAIL | Score = x.y (≥8.0?). Within 4px % = 0.xx. Max deviation = N px | `./reports/pixel-check-report.json` | `./reports/pixel-visual-diff.png` |
| 🟡 **Lighthouse Performance (não gate obrigatório UX, mas bônus)** | PASS / FAIL | LCP / TTI / CLS = x,y,z · Performance score ≥ 90? | `./reports/lighthouse-report.json` | `./reports/lighthouse-report.html` |

---

## 7. Acessibilidade Checklist Final Resumo (🔴 15 itens · copiado profile, 100% tem que ser ✅ para passar A11y Gate)
- [ ] 🔴 1 H1 único por página. Nível heading NÃO pula (H1 → H3 proibido).
- [ ] 🔴 Contraste texto body ≥ 4.5:1 · headings grandes ≥ 3.0:1. Verificado.
- [ ] 🔴 Alvos toque móvel ≥ 44×44px. Espaço entre ≥ 8px.
- [ ] 🔴 Keyboard nav Tab / Shift+Tab / Enter / Space / Arrow / Esc. Funciona 100%.
- [ ] 🔴 Ordem foco DOM = ordem visual. Nenhum tabindex positivo > 0.
- [ ] 🔴 Focus ring `:focus-visible` NUNCA removido sem substituição.
- [ ] 🔴 Img decorativa alt="". Informativa alt funcional ≤125char. Nunca alt omitido.
- [ ] 🔴 `<button>` real, não `<div onClick>`. `<a href>` real p/ links internos/externos.
- [ ] 🔴 ARIA só se não tem texto visível. Nunca duplica texto visível.
- [ ] 🔴 Nunca só cor indica estado. Sempre ícone + texto + cor.
- [ ] 🔴 Input `<label>` associado ou aria-labelledby. Nunca placeholder como label só.
- [ ] 🔴 Modal role="dialog" aria-modal="true". Esc key fecha. Foco trap.
- [ ] 🔴 Spinner loading aria-busy role="status". Texto SR "Carregando…".
- [ ] 🔴 `prefers-reduced-motion: reduce` = animations/transitions DESLIGADAS.
- [ ] 🔴 Zoom 200% em 360px width viewport = SEM overflow horizontal.

---

## 8. Assinatura Aprovação Humana (dupla check · Design + Dev · obrigatória)
| Parte | Nome | Cargo | Data | Aprovação EXPLÍCITA literal "Handoff Completo e Entendido" |
|---|---|---|---|---|
| Design entrega | 🔴 `<Designer Owner>` | UI/UX DesignOps | `<YYYY-MM-DD>` | ✅ / ❌ Comentários: `<...>` |
| Dev recebe | 🔴 `<Dev Owner>` | Frontend Engineer | `<YYYY-MM-DD>` | ✅ / ❌ Comentários: `<Medidas X faltando, token Y não existe...>` |
| QA (se envolvido nesta fase) | 🟡 `<QA Owner>` | QA Engineer | `<YYYY-MM-DD>` | ✅ / ❌ Comentários |

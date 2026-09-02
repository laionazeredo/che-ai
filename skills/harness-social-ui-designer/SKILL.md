---
name: "harness-social-ui-designer"
description: "V4 — Backend-neutral design pipeline with Social Media, UI/UX Feature, Design System and Brand modes. Mandatory SPEC approval, staged execution and visual review. Supports capability-selected OpenPencil, Figma or spec-only execution. Trigger: /harness-design, /harness-figma."
---

# Harness — Social UI Designer (Orchestrator) v4.0

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo):**
> - **Formatting + verbosity ≤500w**: engineering-contracts §18 (subtítulos ## / ###, bullets ≤2 linhas, bold keywords)
> - **Hard-won session lessons** (composição offline / template text nodes / validação unique colors): §3 abaixo
> - **Design tokens + Tailwind**: engineering-contracts skill (DS section)
> - **Image source fallback waterfall**: §3 item #1 (Unsplash real > text_to_image endpoint > G(search) headless)
> - **SVG vetor quality gates**: §12 logo/marca

Este é o **orquestrador top-level** do design harness. O workflow é backend-neutral.
Backend selection MUST follow `references/DESIGN_BACKEND_CONTRACT.md`.
OpenPencil-specific instructions apply ONLY when backend=`openpencil`.
Figma execution follows `references/backends/FIGMA.md` when backend=`figma`.
Never select a backend only because the runtime is Trae or Codex.

### Runtime bootstrap

Before creating any durable design artifact:

    source "${HARNESS_HOME:-$HOME/.trae}/contracts/harness_sessions_contract.sh"
    harness_compute_paths "$WORKTREE_ROOT" "$(harness_current_session_id)" "$PWD"
    harness_ensure_session_dirs "$WORKTREE_ROOT"
    HARNESS_DESIGN_ROOT="${HARNESS_DESIGN_ROOT:-$HARNESS_WORKSPACE_SHARED/design}"
    HARNESS_DESIGN_DIR="$HARNESS_DESIGN_ROOT/<modo>-<slug>-YYYYMMDD"

Create `$HARNESS_DESIGN_DIR` only after the bound-worktree/session preflight passes.
**4 modos mutuamente exclusivos** (escolher 1 no início via `AskUserQuestion`):
- **MODE A → Social Media Posts**: posts 1:1 / stories 9:16 + copies profissionais.
- **MODE B → UI/UX Feature**: wireframes → hi-fi → dev-spec (React/Tailwind 4).
- **MODE C → Design System**: Tailwind 4 tokens ↔ OpenPencil variables + componentes atômicos.
- **MODE D → Logotipo & Marca**: descoberta profunda de marca → briefing de marca → conceitos logo → refinamento vetorial → brandbook completo (SVG obrigatório).

---

## 🔴 0. NON-NEGOTIABLE GATES (executar NA ORDEM — falha = STOP)

### GATE -1 (HARD — NÃO passa SEM APROVAÇÃO) → ESCREVER + ITERAR UI/POST SPEC OBRIGATÓRIA
> **Regra dura:** *Nenhum pixel é desenhado, nenhuma imagem baixada, nenhuma etapa executada até o usuário responder explicitamente "Aprovo a spec" a um documento estruturado.*
>
> 2 rounds de ajuste na spec ainda ambíguo → oferecer defaults em 1 linha (§7 fail-fast).

#### 0.1 Escrever spec completa (use §9 TEMPLATE abaixo como base)
Spec deve ter **TODOS** esses campos preenchidos, por peça/screen:

| Campo (por peça) | Descrição exemplo (MODE A Post 1:1) |
|---|---|
| **ID / Nome peça** | `C1-CAPA` , `C2-CARDAPIO` |
| **Objetivo peça** | Hook inicial, tráfego perfil |
| **Copy verbatim (nenhum caractere pode mudar)** | Headline / Subline / Body / CTA (wordcount max por linha) |
| **Paleta hex (exatos, p/ peça)** | bg=#FFF7ED | headline=#C2410C | cta=#EA580C | text=#292524 |
| **Dimensão base + export scale** | 1080×1080 → scale 2 = 2160×2160 PNG |
| **Layout grid (posições absolutas ou relative)** | Foto 360×360 x=696 y=540 canto inf-dir; Bloco texto x=72 y=72 w=936 padding=24 |
| **Imagem (fallback cascade por §3.1)** | (1) Unsplash ID `photo-1586444248902-2f64eddc13df` / (2) prompt stock / (3) prompt text_to_image |
| **Estética visual (por elemento)** | Foto: radius=28 / stroke branco=6 / shadow=4 8 blur14 alpha40; Overlay dark #1C1917 alpha=35% SE foto for quente+texto branco |
| **Tipografia (peso/tamanho/leading)** | Headline: Inter Black 72/76; CTA: Inter SemiBold 48/52 |
| **Contraste WCAG obrigatório** | Headline sobre bg min 4.5:1 body / 3:1 grande (explicar overlay se necessário) |
| **Stacking order camadas (INDEX baixo → alto)** | 0=foto → 1=overlay (se houver) → 2=headline/subline → 3=CTA button → NUNCA foto sobre texto |
| **Saída esperada** | `FINAL-C1-CAPA@2x.png` 2160×2160 |

Campos extra para **MODE B UI screens**: persona, job story, 3 core behaviors max, breakpoints responsive (mobile 375 / tablet 768 / desktop 1280).
Campos extra para **MODE C Design System**: origem tokens (Tailwind 4 config / do zero), dark mode obrigatório, lista componentes (Button/Card/Input/Textarea/Badge/Avatar/Alert/Toggle/Switch/Radio/Checkbox/Select — default 12).
Campos extra para **MODE D Logotipo & Marca (OBRIGATÓRIOS 100% preenchidos)**:
| Campo MODE D | Descrição obrigatória |
|---|---|
| **Nome marca + slogan (se houver)** | Texto VERBATIM do wordmark; slogan opcional. |
| **Ideia central / posicionamento marca** | 1-2 frases "A marca X é para Y que querem Z". |
| **Setor + público-alvo (persona mínimo)** | Ex: "Padaria artesanal UK, público 25-55 anos, classe média-alta". |
| **Paleta primária (cores marca hex)** | 2-5 cores hex (primary / secondary / accent / neutrals). Se não definida → descobrir. |
| **Tipografia wordmark + corpo** | Família wordmark (Display) + Body (ex: Playfair Display Bold 72 / Inter 400). |
| **Voz da marca (brand voice doc) + 3 frases exemplo** | Tom (amigável / premium / minimalista / jovem / sério) + 3 exemplos de comunicação escrita. |
| **Referências (até 5)** | (a) URLs de sites/marcas similares; (b) Logotipos existentes em anexo; (c) Temas/estilos visuais (ex: "minimalista nórdico", "artesanal papel kraft"). |
| **Estilo logotipo (até 3 escolher)** | Wordmark-only / Lettermark (monograma iniciais) / Pictorial mark (ícone) / Combination mark (ícone+palavra) / Emblem (selo). |
| **Arquitetura de informação do brandbook final** | Capa → Logos → Paleta → Tipografia → Aplicações mockups → Do/Don't (mínimo 6 seções). |
| **Variantes logo obrigatórias** | Primary (horizontal full) / Secondary (stacked / vert.) / Monochrome preto / Monochrome branco / Icon only / Favicon 64×64. ≥6 variantes. |
| **SVG deliverable OBRIGATÓRIO (HARD GATE)** | Todas variantes devem ser SVG standalone, SEM bitmaps embutidos, < 128KB, viewBox `0 0 1024 1024` default. |

#### 0.2 Escrever spec no disco e pedir aprovação explícita
- Salvar spec em: `$HARNESS_DESIGN_DIR/spec.md`
- Mostrar spec ao usuário **formatada para leitura diagonal** (tabelas, negrito, bullets).
- Pergunta única de aprovação (obrigatória):
  > **"Aprovo esta spec do jeito que está — pode executar (Sim / Não, ajustar estes X pontos)"**
- Se NÃO → ajustar apenas os pontos listados; re-apresentar; repetir.

---

### GATE 0: Escolher modo A/B/C/D (se user não especificou)
Se pedido do usuário já indica modo → direto. Senão parar e perguntar via `AskUserQuestion` (4 opções: A Social / B UI-UX / C Design System / **D Logotipo & Marca**).

### GATE 0.1 → MODE D EXCLUSIVO: Perguntas de descoberta profunda OBRIGATÓRIAS
Se modo = **D (Logotipo & Marca)**, ANTES de escrever spec §0.1, rodar **5 lotes de perguntas** (lote por lote, esperar respostas por lote):

| Lote D | Perguntas OBRIGATÓRIAS (max 5 por lote) |
|---|---|
| **Lote D1 — Identidade** | 1. Nome completo marca (verbatim, maiúsculas/minúsculas exatas)? 2. Slogan existe? Se sim qual verbatim. 3. Quando a marca nasceu? Tem história curta para contar? 4. Qual setor/indústria exato? 5. Região/país onde opera? |
| **Lote D2 — Posicionamento** | 1. Qual problema a marca resolve? 1 frase. 2. Quem é o cliente ideal (persona, 3 características). 3. Quem são os 3-5 principais concorrentes diretos. 4. Diferencial 1 único contra concorrentes. 5. 3 adjetivos que descrevem personalidade da marca (ex: acolhedor, premium, jovem). |
| **Lote D3 — Estilo & Estética (até 5 cada)** | 1. 3-5 **URLs de marcas/sites de referência** (amamos / odiamos). 2. 3-5 temas/estilos visuais de referência: minimalista / brutalista / artesanal / luxo / retro / moderno / orgânico / tech etc. 3. Você tem logotipos antigos, sketches, desenhos, moodboards existentes anexar? 4. Quais cores associadas à marca (ou cores que NÃO quer usar de jeito nenhum). 5. Tipografia favorita (ou família que odeia). |
| **Lote D4 — Voz & Comunicação** | 1. Tom de voz 1 frase (ex: "especialista acessível", "amigo que explica bem", "luxo discreto"). 2. 3 frases EXEMPLO de como marca falaria com cliente (uma saudação, um agradecimento, um CTA). 3. Frases proibidas / NUNCA dizer. 4. Uso de emoji permitido? (Sim / Não / Com moderação). 5. Língua principal e outras línguas que marca opera. |
| **Lote D5 — Aplicações & Restrições** | 1. Top 5 lugares onde o logo vai aparecer (Instagram perfil / cartão visita / fachada loja / camiseta / site header / embalagem...). 2. O que o logo NÃO PODE ter (ex: "nenhum ícone de pãozinho genérico", "não queremos uso de gradient"). 3. Você já tem paleta/tipografia definida? (Sim → compartilhar / Não → construímos do zero). 4. Variantes logo obrigatórias? (mini favicon, horizontal stacked, preto, branco, monograma iniciais). 5. Formatos entrega finais? (SVG obrigatório default + PNG 1x/2x + PDF vetor / Favicon .ico / fonte wordmark?). |

**Fail-fast lote D (se 2 lotes ainda ambíguo)**: perguntar 1 vez: "Default: minimalista, tons terrosos neutros, Inter + Playfair, 3 conceitos, 6 variantes. Seguir assim e ir refinando por etapa? (Sim / Não — listar ajustes)".

### GATE 1: Save path + brandbook
- **Design directory**: `$HARNESS_DESIGN_DIR="$HARNESS_DESIGN_ROOT/<modo>-<slug>-YYYYMMDD"`. Source representation is backend-specific.
- **Brandbook (3 bullets curtos)**: paleta hex / tipografia (default Inter) / tom de voz copy (default "Profissional acessível").
- Inicializar/abrir a fonte de design usando o driver ativo. OpenPencil pode criar source local; Figma registra metadata em `$HARNESS_DESIGN_DIR/figma-source.md`.

---

## 🧯 3. HARD-WON LESSONS (CANÔNICO — fallback obrigatório NESTA ORDEM)
> *Jamais deviar desta ordem. Custou 4 horas + 14 bugs descobrir isso em produção.*

### 3.1 Cascade de fonte de FOTOS reais (garantir unique colors > 25.000)
1. **PRIORIDADE 1 — Unsplash photo URLs reais (GARANTIDO)**:
   ```
   https://images.unsplash.com/photo-<ID>?auto=format&fit=crop&w=1024&h=1024&q=90
   ```
   Headers obrigatórios: `User-Agent: Mozilla/5.0` + `Accept: image/webp,image/jpeg,*/*`. **NÃO usar source.unsplash.com (descontinuado → HTML 403)**. Validar magic bytes `ffd8ff` (JPEG) ou `89504e47` (PNG), size > 80KB — senão cair.
2. **PRIORIDADE 2 — text_to_image endpoint (checar por placeholder)**:
   ```
   https://coresg-normal.trae.ai/api/ide/v1/text_to_image?prompt=<ENCODED>&image_size=square_hd|portrait_16_9
   ```
   **VALIDAÇÃO OBRIGATÓRIA**: MD5 da foto ≠ MD5 de outras; unique colors > 25.000; SEM substring `The image is generating` ou `refresh page` no raw bytes. Se falhar → p/ 3.
3. **PRIORIDADE 3 — `stock_photo` MCP open-pencil**: aplicar diretamente a um `create_shape(RECTANGLE 360×360 leaf)` via requests JSON array (query + orientation=square). Útil se OpenPencil desktop GUI aberto (headless pode não baixar — se falhar → p/4).
4. **PRIORIDADE 4 — fallback offline PILLOW/IMAGEMAGICK**: compositor offline 100% garantido (colar foto baixada em 1 ou 2, sobre PNG base do canvas já renderizado com textos + fills). **Este fallback NUNCA FALHA**.

### 3.2 TEXT nodes no OpenPencil v0.8.4 — ESTRUTURA RODA APENAS COM TEMPLATE BUILT-IN
- **PROIBIDO criar `TEXT` manualmente via `create_shape` ou `I(null,{type:text,...})`**: node fica width=height=0, sem runs de layout/Fonte internos no engine Rust → **TEXTO INVISÍVEL / clip / chapado**.
- **MÉTODO CANÔNICO OBRIGATÓRIO**: `use-template knowledge-card-square` (1080×1080, 31 nodes por card) → gera toda a store de texto/runs/fontes corretamente. Depois sobrescrever só copies/fills/fontes via MCP `set_text` + `set_font`.
- Salvar SEMPRE via `save_document(filePath)` depois de alterar texto (salva stores internas no .op — sem isso SHA256 diferente e texto some no desktop).

### 3.3 Validação VISUAL OFFLINE (SEM PRECISAR ABRIR GUI DESKTOP) — unique colors
Heurística **definitiva** Python (rodar sobre qualquer PNG exportado, validar por peça):
| Faixa unique colors | Significado | Ação |
|---|---|---|
| **< 2.000** | Chapado / nada renderizou | Reproduzir etapa |
| **2.000 — 8.000** | Texto + fills OK, SEM FOTOS | Se etapa esperava foto → fallback 3.1.4 (Pillow) |
| **> 25.000** | FOTOGRAFIA REAL renderizada (gradientes naturais, pixel data) | ✅ PASS |

Rodar snippet Python em §10 após CADA export de etapa.

### 3.4 Stacking order OBRIGATÓRIO (fotos NUNCA sobrepõem texto!)
Por frame (card/screen):
- **INDEX 0 → (FOTO)**: sempre fundo, ATRÁS de tudo.
- **INDEX 1 → (OVERLAY dark se WCAG pede, alpha 30-40%)**: só **se** foto for luminosa/quente E texto for branco. Mesmo radius da foto.
- **INDEX 2..N-1 → (TEXTOS headline/subline/body)**: sempre em cima de foto + overlay.
- **INDEX ÚLTIMO filho → (CTA button)**: sempre na camada mais alta, garante clique/tap target.

### 3.5 Imagem nodes no OpenPencil headless LIMIT
- `batch_design operations G(slot_id, "search", prompt)` cria node filho no slot, mas **CLI headless NÃO baixa a foto stock** (sem backend integração no runtime headless).
- A foto SÓ renderiza ao abrir o .op no GUI desktop (ele baixa no load). **Se a entrega precisa de PNG RÁPIDO sem abrir GUI → obrigatório cair em fallback offline Pillow 3.1.4**.

---

## 📐 1. MODE A — Social Media Creatives (Execução POR ETAPAS + REVISOR POR ETAPA)
Goal: Entregar N criativos (default 4 Feed 1:1) com copies 100% verbatim, paleta, layout grid, fotos, estética, export @2x, **tudo alinhado à spec §GATE -1 aprovada**.

### 1.0 Precondição hard: Spec APROVADA pelo usuário (§GATE -1)
- Copiar spec aprovada para: `$HARNESS_DESIGN_DIR/spec.APPROVED.md` (SHA256 salvo para revisor comparar).

### Fluxo etapas (≤4 etapa total, 1 etapa executa de cada vez)
**POR ETAPA → (a) Agente Executor (designer) executa; (b) Agente Revisor Visual valida contra spec; (c) Se passar → próxima etapa; (d) Se reprovar ≤2 vezes → rework etapa; >2 vezes → voltar spec ajuste.**

| Etapa | O que executa (Agente Executor) | O que valida Revisor Visual |
|---|---|---|
| **ETAPA 1 — Assets Fotos** | Baixar 1 foto por peça via cascade §3.1; salvar em `/assets/<piece>.png`; center crop 1024×1024; unsharp 0.8 110% | (1) 4 arquivos PNG existem; (2) Cada unique colors >25.000; (3) MD5 diferentes (não placeholder repetido); (4) Query Unsplash / prompt text_to_image corresponde temática da peça na spec. |
| **ETAPA 2 — Estrutura Canvas + Textos Verbatim** | 1 template `knowledge-card-square` por peça (TEXT nodes OK); nomear layers semanticamente (`C1-Headline`, `C2-CTA-Buy`); setar copies 100% verbatim da spec (char-by-char, nenhum alterado); setar fontes da spec; setar fills de cor hex paleta spec | Export @1x e validar: (1) Unique colors 2k-8k (texto/fills OK); (2) Copies idênticos spec (hash do texto); (3) Paleta hex corresponde spec (`analyze_colors`); (4) Layers não tem "Rectangle12" (todos semânticos); (5) Contraste WCAG AA. |
| **ETAPA 3 — Slots Foto + Estética Visual** | Criar slot rect 360×360 por peça na posição x/y EXATA da spec; aplicar foto asset (ou fallback 3.1.4 Pillow composição offline se headless não render). Aplicar radius, stroke branco, shadow, overlay dark (tudo valores EXATOS spec). **Stacking order INDEX 0 (foto) → INDEX1 (overlay) → textos sempre acima.** | Export @1x: (1) Posição x/y EXATA da spec (dif px ≤2); (2) radius + stroke + shadow exatos (pixel check via máscara de edge); (3) Overlay dark SOMENTE se spec pedia; (4) Foto NUNCA cobre headline/CTA (stacking); (5) Unique colors >25.000 EM TODAS PEÇAS (prova foto incorporada). |
| **ETAPA 4 — Export @2x Final + QA Final Gate** | Export cada peça scale=2 format=PNG; save_document source `.op` + `.openpencil` SHA idênticos; agrupar em `/exports/` com nomes exatos spec; rodar gates §4 em TODOS outputs | Todos gates §4 passam; entregas listadas; spec vs output checklist completa. |

---

## 🖥 2. MODE B — UI/UX Feature Design (mesma estrutura Spec → Etapas + Revisor)
Goal: Wireframes → Hi-Fi → Dev-Spec (React/Tailwind 4 pasteable output).

| Etapa | Ação Executor | Revisor valida |
|---|---|---|
| **SPEC GATE-1** | Escrever spec completa: persona / job story / 3 core behaviors / 2-3 screens / breakpoints / dark mode / tokens / paleta / componentes reuso | Spec aprovada user → `APPROVED.md` salvo. |
| **ETAPA B1** | Low-fi wireframes (only boxes + labels; NO fills/photos). Max 3 screens. | Estrutura alinhada spec; labels corretas; sem fill/gradient. |
| **ETAPA B2** | Design tokens collection (OpenPencil variables): 8 cor / 6 radius / 8 spacing / 3 typography; ligar layers a variables (SEM raw hex). | Todas layers ligadas a var; sem raw hex em elementos sistema; collection criada com 2 modos se dark mode. |
| **ETAPA B3** | High-fi: fills via var; fontes + sizes exatos; radius + efeitos; hero foto via cascade §3.1; components (Button/Card) → `create_component`. | Variáveis ligadas; paleta 100% da spec; foto >25k unique colors; WCAG AA; componentes criados. |
| **ETAPA B4** | Export dev-spec: `design_to_tokens(tailwind)` + PNG 2× screens + SVG components + 15-line `dev-spec.md` (1 para components / tokens / breakpoints). | Output tailwind pasteable; PNGs screens 2× 2560×1440; SVG components com variáveis; dev-spec 15 lines. |

---

## 🎨 3. MODE C — Design System (Tailwind 4 ↔ OpenPencil variables)
Goal: Extrair tokens Tailwind → criar variables + 12 componentes atômicos × 4 variants (primary/secondary/ghost/destructive) + export 3 formatos (tailwind / CSS / JSON DTCG).

| Etapa | Ação Executor | Revisor valida |
|---|---|---|
| **SPEC GATE-1** | Spec: origem tokens (Tailwind config / do zero) / dark mode obrigatório / 12 components default; aprovar. | Spec aprovada salvo. |
| **ETAPA C1** | Criar collection 2 modos (Light/Dark) → ~60 semantic vars (cor/radius/spacing/typography/shadow/opacity). Bind SEMPRE via semantic (nunca raw hex). | 60+ vars criadas; 2 modos se dark; sem raw hex layers; naming semantic (color/brand/50, semantic/bg/primary). |
| **ETAPA C2** | 12 components atômicos: Button (5 variants + 3 sizes + disabled) / Card / Input+Textarea (focus ring) + Badge/Avatar/Alert/Toggle/Checkbox/Radio/Select/Modal-header. Cada 4 variants; grupo SECTION por componente → `create_component`. | 48 variants total; padding/radius ligados a vars; focus state via stroke+effects; components criados (não só frames). |
| **ETAPA C3** | `design_to_tokens` 3 formatos (tailwind/CSS/JSON) → salvar `/tokens/` | 3 arquivos tokens; tailwind output colado em `packages/ui/tailwind.config` se existir Flockr. |

---

## 🏷 4. MODE D — Logotipo & Marca (SVG OBRIGATÓRIO + Brandbook)
Goal: Descoberta profunda marca → briefing validado → 3 conceitos logo (esboço baixo-fidelidade na OpenPencil) → refinamento vetorial de 1 conceito → **SVG standalone por variante** (HARD) → brandbook final com paleta/tipografia/aplicações + voz da marca.

### Pré-condições HARD MODE D (falhar = STOP):
1. **5 lotes perguntas descoberta GATE 0.1 respondidos.**
2. **Spec MODE D (§GATE -1 campos extra D) 100% preenchida e APROVADA pelo usuário → salva em `spec.APPROVED.md`.**
3. **Pelo menos 2 referências (URL / logos anexos / temas) informadas.**

### Fluxo etapas MODE D (≤5 etapa total; cada etapa valida com usuário ANTES de próxima):
**Cada etapa SEMPRE nesta ordem → (a) Executor cria; (b) Revisor Visual valida alinhado spec; (c) Usuário confirma PASS / pede ajustes ≤2 bullets; (d) Se aprovado user → próxima etapa.**

| Etapa MODE D | O que executa (Agente Executor Designer) | O que valida Revisor Visual antes de mostrar user | Checkpoint OBRIGATÓRIO usuário |
|---|---|---|---|
| **D0 — Brand Briefing Validado** | Escrever `brandbook/00-briefing.md`: nome, slogan, posicionamento, persona, concorrentes, diferencial, 5 adjetivos personalidade, voz da marca + 3 frases exemplo, top 5 aplicações, restrições proibidas. | (1) Todos campos D1-D5 de descoberta aparecem no briefing; (2) 3 frases voz da marca escritas; (3) ≤2 referências por URL/anexo listadas. | ✅ Usuário assina: "Briefing correto — pode gerar conceitos" (Sim / Não ajustes X) |
| **D1 — 3 Conceitos Baixa Fidelidade** | No OpenPencil, 3 artboards lado-a-lado 1024×1024 (CONCEITO-A / B / C). Cada um: **caixas + labels** (nenhuma estética final): posição wordmark / posição ícone / iniciais / proporção geral horizontal ou empilhada. Apenas formas básicas + labels de texto. | (1) 3 conceitos existem; (2) Nenhum bitmap / gradient / fill estético; (3) Cada conceito tem proporção / estilo diferente (ex: A = horizontal wordmark only; B = ícone+palavra vertical; C = monograma circular). | ✅ Usuário escolhe 1 conceito para refinar (pode dizer "híbrido A topo + B corpo"). ≤1 híbrido permitido. |
| **D2 — Refinamento Vetorial do Conceito Escolhido** | No OpenPencil, em 1 artboard só: construir **vectors puros** (BOOLEANOS union/subtract/intersect — SEM raster, SEM bitmaps) para: (a) wordmark (1 tipo ligado em curvas se display); (b) ícone / símbolo / monograma; (c) combinação primary horizontal full. Aplicar paleta hex da spec; aplicar tipografia wordmark exata; ajustar kerning visual. | (1) **TODOS nós são vetores** (ver export SVG — sem `<image>`, sem base64); (2) Paleta exata hex spec (`analyze_colors`); (3) Tipografia ligada; (4) SVG inicial exportado < 256KB; (5) Proporções alinhadas conceito escolhido D1. | ✅ Usuário valida traço / kerning / cores do vetor. |
| **D3 — 6 Variantes + Export SVG (HARD GATE)** | Criar **≥6 variantes logo obrigatórias**: (1) Primary horizontal full (wordmark + ícone); (2) Secondary stacked vertical; (3) Lettermark / monograma iniciais square; (4) Pictorial icon-only; (5) Monochrome preto (1 cor); (6) Monochrome branco (1 cor reverse). **TODAS 6 exportar individualmente como SVG standalone vetor puro.** Validar via snippet §12.1 antes de avançar. Extra opcional: favicon 64×64 SVG. | (1) **6 arquivos SVG em `/vectors/`**; (2) **Cada SVG: zero tags `<image>` / zero base64 (validar regex)**; (3) Cada SVG `viewBox="0 0 1024 1024"` (ou proporção correta); (4) Tamanho cada < 128KB; (5) 2 variantes monocromáticas (preto + branco) 100% 1 cor; (6) SVG standalone abre em browser sem erros (validar via parse XML). | ✅ Usuário valida as 6 variantes finais. Pede ajustes finais de cor / espaçamento (≤3 bullets). |
| **D4 — Brandbook Final Completo + Aplicações Mockups** | (a) Montar estrutura brandbook 6 seções mínimo: `01-capa.md`, `02-logos-e-variantes.md` (todas 6 SVGs embed), `03-paleta.md` (nomes cores + hex + usos: primary / secondary / text / bg), `04-tipografia.md` (Display wordmark + Body + weights + line heights + examples), `05-aplicacoes.md` (≥3 mockups aplicação real: perfil Insta 1:1 / cartão visita / header site 1280×640 — gerar PNG mockups em canvas separado), `06-do-and-dont.md` (3 DO + 3 DON'T: ex: DO deixar clear space 0.5× altura "X" / DON'T colocar sobre fotos sem contraste). (b) Export PNG 2× todas SVGs em `/exports/logo-*@2x.png`. | (1) 6 seções brandbook em markdown + assets; (2) 3 mockups PNG criados (≥2560 wide); (3) DO/DON'T tem pelo menos 3 cada; (4) TODAS SVGs já validadas permanecem em `/vectors/`; (5) Voz da marca consistente no texto do brandbook. | ✅ Usuário aprova brandbook final. |

---

### Fluxo de validação usuário por etapa MODE D (HARD — NÃO pula):
1. Executor termina etapa → salva arquivos.
2. Revisor emite PASS/REWORK ≤3 bullets.
3. Se REWORK → executor corrige só desvios.
4. Se PASS do revisor → **sobe pro usuário pergunta única**: `"Etapa D<N> concluída. Aprova para avançar para D<N+1>? (Sim / Não — ajustes: [1,2,3 pontos])"`.
5. Se NÃO → ajustar apenas os pontos listados; re-subir para aprovação. **Não avança para próxima etapa sem Sim explícito do usuário.**

---

## ✅ 4. QUALITY GATES (HARD FAIL se não passar → fix antes de entregar)
Todos gates 1-7 aplicam a **QUALQUER MODO** e **toda etapa final**. Gates D1-D5 são **MODE D exclusivos (HARD)**:

### Gates globais (todos modos)
1. **CONTRASTE WCAG AA**: Body text ≥ 4.5:1; large text ≥3:1. Checar com `analyze_colors` MCP se dúvida. Overlay dark obrigatório se texto branco + foto luminosa (card forno lenha = exemplo).
2. **IMAGENS VALIDADAS**: (a) `unique colors > 25.000` (§3.3) POR PEÇA que esperava foto; (b) SEM placeholder endpoint (checar bytes + MD5); (c) Tema da foto corresponde à peça.
3. **SEMPRE EXPORT SCALE 2 (2×)**: Feed 2160×2160; Stories 2160×3840; Screens desktop ≥2560 wide.
4. **LAYERS SEM NOMES LIXO**: SEM "Rectangle 12", "Text 4". Sempre: `<Piece>-<Role>` (ex `C1-Headline-Hero`, `CTA-Buy-Ticket`).
5. **FALLBACK OFFLINE OBRIGATÓRIO SE ETAPA 3 FOTOS HEADLESS FALHAR**: Rodar compositor Pillow §3.1.4 (colar foto asset baixada sobre PNG base texto renderizado) — este é o gate final para entregar foto **garantida**.
6. **STORAGE PATHS LIMPOS**: outputs duráveis ficam em `$HARNESS_DESIGN_DIR`; assets em `$HARNESS_DESIGN_DIR/assets/`; exports em `$HARNESS_DESIGN_DIR/exports/`.
7. **SPEC CHECKSUM**: Saída final **DEVE** corresponder à `APPROVED-spec.md`. Revisor compara item por item (paleta / copies verbatim / layout / dimensão).

### Gates MODE D exclusivos (Logotipo & Marca) — HARD fail
8. **D1: SVG PURO (SEM BITMAPS)**: Nenhuma variante logo pode conter `<image>` tags inline, base64 bitmaps, `<foreignObject>`, ou raster data embed. Validar via regex em cada arquivo SVG. Se precisar de foto → PNG separado, NÃO dentro do logo SVG.
9. **D2: VARIANTES OBRIGATÓRIAS MÍNIMAS 6**: Primary horizontal + Secondary stacked + Monochrome preto + Monochrome branco + Icon only + Monogram/Lettermark iniciais. ≥6 arquivos em `/vectors/` ao final da D3.
10. **D3: SVG PEQUENO, STANDALONE, VIEWBOX CORRETO**: Cada SVG ≤128KB; `viewBox` (ex: `0 0 1024 1024` square OU proporção width:height natural); SEM dependências externas (fonts linkadas remotas, URLs); abre em qualquer navegador moderno sem erros. Validar snippet §12.1.
11. **D4: MONOCROMÁTICO 1 COR**: variantes preta (`#000000` ou cor escura spec) E branca (`#FFFFFF`) DEVEM ter 100% dos paths em SÓ 1 fill. Nenhum gradient, nenhuma sombra rasterizada. Para testar: abrir SVG em editor de texto → substituir fill → só 1 cor muda (não partes).
12. **D5: BRANDBOOK 6 SEÇÕES MÍNIMO**: 00-briefing / 02-logos-variantes / 03-paleta / 04-tipografia / 05-aplicacoes-mockups (≥3) / 06-do-and-dont (≥3 DO / ≥3 DON'T). Mockups PNG ≥2560px cada.
13. **D6: NOMENCLATURA SVG CANÔNICA**: `logo-primary.svg`, `logo-stacked.svg`, `logo-monochrome-black.svg`, `logo-monochrome-white.svg`, `logo-icon.svg`, `logo-monogram-<INITIALS>.svg`. Nenhum espaço / caractere especial.
14. **D7: CLEAR SPACE & MIN SIZE DOCUMENTADO**: Brandbook 02-logos-variantes deve ter tabela: clear-space mínimo (ex: "0.5× a altura do X do wordmark") e tamanho mínimo impressão / digital (ex: "≥48px altura digital").

---

## 👀 5. AGENTE REVISOR VISUAL ESPECIALISTA (papel e critérios)
Invocado **APÓS CADA ETAPA** (antes de próxima). Papel = QA visual + compliance spec.

### 5.1 Protocolo revisão por etapa
```
Input:
  - SPEC_APPROVED_PATH (arquivo salvo após aprovação)
  - ETAPA_ID (1/2/3/4)
  - OUTPUT_FILES da etapa (lista paths PNG / .op / json)
  - ENGINEERING_CONTRACTS §18 verbosity
Saída:
  [PASS] → 1 frase "Alinhado à spec em todos os gates. Próxima etapa liberada."
  [REWORK] → ≤3 bullets APENAS dos desvios (ex: "C3 radius=24 mas spec pede 28"; "Unique colors C2 = 3.200 (esperado >25k foto)")
```

### 5.2 Limites
- ≤ 2 rounds REWORK por etapa; **>2 rounds REWORK = STOP e voltar spec para ajuste** (problema na especificação).
- Revisor NUNCA altera arquivos; só emite PASS / REWORK com lista ≤3 desvios.
- Validação visual offline: sempre rodar snippet unique colors (§3.3) + `analyze_colors` para contraste antes de decidir.

---

## 🚦 7. FAIL-FAST RULES (todos modos)
- **2 rounds de ajuste na Spec Gate-1 ainda ambíguo** → 1 pergunta: "Quer defaults e vai? A) Sim / B) Vou detalhar mais".
- **2 rounds ajustes copies/layout etapa NÃO passam revisor** → voltar Spec Gate-1.
- **Fotos placeholder 3x em cascade** → pular direto fallback Pillow offline 3.1.4 (garantido).

---

## 📝 6. OUTPUT SHAPE §18 (todas respostas ≤500w)
```
### 📍 Status <1 frase>
### 🧩 Mudanças-chave (≤3 bullets)
  • **<Rótulo>**: ≤2 linhas.
### 🔗 Refs (≤5 links)
  • [<nome-arq>](file:///absoluto/path)
### ❓ Aprofundar
Quer aprofundar em **<UMA COISA ÚNICA>**? (Sim / Não)
```

---

## 📁 8. NOMENCLATURA PATHS
```
$HARNESS_DESIGN_DIR/
  ├── spec.md                  # Spec draft (iteração)
  ├── spec.APPROVED.md         # Spec SHA256 travada após aprovação (GATE-1)
  ├── assets/
  │   ├── C1-hero.png          # Imagens 1024×1024 (>25k unique colors)
  │   └── C2-flatlay.png
  ├── exports/
  │   ├── FINAL-<piece>@2x.png # Saídas 2160×2160 / 2160×3840 (modos A/B)
  │   └── logo-primary@2x.png  # (MODE D only) PNG 2× de cada variante SVG
  ├── vectors/ (MODE D only OBRIGATÓRIO)
  │   ├── logo-primary.svg
  │   ├── logo-stacked.svg
  │   ├── logo-monochrome-black.svg
  │   ├── logo-monochrome-white.svg
  │   ├── logo-icon.svg
  │   └── logo-monogram-<INICIAIS>.svg
  ├── brandbook/ (MODE D only)
  │   ├── 00-briefing.md
  │   ├── 01-capa.md
  │   ├── 02-logos-e-variantes.md (embed todos SVG)
  │   ├── 03-paleta.md
  │   ├── 04-tipografia.md
  │   ├── 05-aplicacoes.md
  │   └── 06-do-and-dont.md
  ├── tokens/ (MODE C only)
  │   ├── tokens.tailwind.txt / tokens.css / tokens.json
  └── dev-spec.md (MODE B only, ≤15 linhas)
```

Backend source artifacts are conditional: backend=`openpencil` stores `source.pen`
plus the identical `source.openpencil` copy; backend=`figma` stores only
`figma-source.md` metadata. backend=`spec-only` creates neither source artifact.

---

## 🗂 9. SPEC TEMPLATE COMPLETO (exemplo MODE A MasterPan Instagram 4 posts 1:1)
> *Copiar este template, preencher 100% campos, apresentar, esperar aprovação explícita "Sim, aprovo spec" antes de qualquer execução.*

```
# SPEC — Carrossel Instagram MasterPan Padaria (4 posts 1:1 1080×1080)
## Meta
- Objetivo campanha: Apresentar MasterPan como padaria artesanal.
- Tom de voz: Aconchegante, artesanal, clássico, caloroso.
- Paleta global (todos cards): #FFF7ED bg-stone-50 | #C2410C headline-orange-700 | #EA580C cta-orange-600 | #292524 text-stone-800 | #FFFFFF stroke-white
- Tipografia global: Inter (Black 72 headlines, Bold 40 subline, SemiBold 48 CTA)
- Export por card: 1080 base → scale 2 → 2160×2160 PNG final.

---
## Por Peça (4x)
| Campo | C1-CAPA | C2-CARDÁPIO | C3-PROCESSO | C4-VISITE |
|---|---|---|---|---|
| **Objetivo** | Hook hero: "Quem somos" | 3 pães icônicos | Forno lenha = autenticidade | Localização + CTA visitar |
| **Headline (verbatim)** | *MasterPan* | *Nossos Pães* | *Assados em Forno a Lenha* | *Venha nos Visitar* |
| **Subline (verbatim)** | Padaria Artesanal | Clássicos. Quentes. Sempre frescos | Desde 1998, com paciência e brasa | Rua das Flores 123 • Centro |
| **Body bullets** | 1. Fermentação natural longa; 2. Ingredientes orgânicos | 1. Pão francês quente 7h; 2. Pão de queijo mineiro; 3. Croissant amanteigado | 1. Tijolos refratários; 2. Assados diariamente 5h | 1. Ter-Dom 7h-19h; 2. Delivery WhatsApp; 3. Wifi gratuito |
| **CTA button text** | Ver Cardápio → | Pedir Agora → | Ver Processo → | Traçar Rota → |
| **Pos foto (x,y) 360×360** | (696, 540) inf-dir | (696, 88) sup-dir | (696, 540) inf-dir | (696, 88) sup-dir |
| **Foto Unsplash ID / prompt** | photo-1586444248902 (sourdough hero dourado luz quente) | photo-1549931319 (flat lay 3 pães parchment) | photo-1556909114 (forno lenha brasa tijolos) | photo-1555507036 (fachada padaria toldo amarelo manhã) |
| **Foto radius | stroke | shadow** | 28 / 6 branco / 4 8 blur14 alpha40 | igual C1 | igual C1 | igual C1 |
| **Overlay dark?** | Não | Não | **SIM #1C1917 alpha 35%** (texto branco) | Não |
| **Stacking order (0→N)** | 0=foto → 1=textos → último=CTA | 0=foto → 1=textos → último=CTA | 0=foto → 1=overlay → 2=textos brancos → último=CTA | 0=foto → 1=textos → último=CTA |
| **Nome saída final** | FINAL-WITH-REAL-PHOTO_C1-CAPA@2x.png | FINAL-WITH-REAL-PHOTO_C2-CARDAPIO@2x.png | FINAL-WITH-REAL-PHOTO_C3-PROCESSO@2x.png | FINAL-WITH-REAL-PHOTO_C4-VISITE@2x.png |

---
## Gate WCAG (por peça)
- C1: Texto laranja sobre bg-stone-50 → 5.2:1 ✅
- C2: idem C1
- C3: Texto branco sobre foto forno + overlay 35% → ≥4.5:1 via overlay
- C4: idem C1
```

---

## 🗂 9.1 SPEC TEMPLATE COMPLETO — MODE D (Logotipo & Marca)
> **MODE D EXCLUSIVO.** Copiar este template, preencher 100% campos após rodar 5 lotes perguntas D1-D5, apresentar ao usuário, esperar APROVAÇÃO EXPLÍCITA "Sim, aprovo spec" antes de qualquer vetor desenhado.

```
# SPEC MODE D — Logotipo & Marca <NOME-MARCA> (YYYY-MM-DD)
## D0 — Identidade e Posicionamento
- Nome marca (VERBATIM maiúsculas/minúsculas):
- Slogan (se existe, VERBATIM):
- História curta / origem marca (1-2 frases):
- Setor / indústria exato:
- Região / país opera:
- Problema que resolve (1 frase):
- Cliente ideal (persona: 3 características):
- 3-5 concorrentes diretos + URL seus sites:
- 1 diferencial único vs concorrentes:
- 5 adjetivos personalidade da marca:
- Voz da marca (1 frase tom):
  - 3 frases EXEMPLO de como marca fala com cliente:
  - Frases PROIBIDAS / NUNCA dizer:
  - Emojis permitidos? (Sim / Não / Com moderação)
  - Língua principal + outras línguas:

## D1 — Estética, Referências e Restrições
### Referências OBRIGATÓRIAS (pelo menos 2 de uma categoria):
- (a) 3-5 URLs de marcas/sites de referência (amamos):
- (b) 3-5 URLs de marcas/sites de referência (odiamos):
- (c) Logotipos antigos / sketches / moodboards existentes anexados (lista paths):
- (d) Temas/estilos visuais de referência (ex: "minimalista nórdico", "brutalista", "luxo", "artesanal kraft"):
### Cores:
- Paleta hex DEFINIDA (se já tiver): primary=#XXXXXX | secondary=#XXXXXX | accent=#XXXXXX | neutrals=#XXXXXX,#XXXXXX,#XXXXXX
- Cores PROIBIDAS NUNCA USAR:
### Tipografia:
- Wordmark (Display) família já definida? (Sim → qual / Não → escolheremos no D2)
- Body família já definida? (Sim → qual / Não)
- Famílias tipográficas PROIBIDAS odiamos:
### Estilo(s) logotipo (escolher até 3):
- [ ] Wordmark-only (só texto)
- [ ] Lettermark / monograma iniciais
- [ ] Pictorial mark (ícone abstrato / ilustração)
- [ ] Combination mark (ícone + palavra horizontal)
- [ ] Emblem / selo (circular, retangular)
### Top 5 lugares logo vai aparecer (definem proporções e min-size):
1. Ex: perfil Instagram 320×320
2. Ex: cartão visita 85×55mm (300dpi)
3. Ex: header site 1280×640 (256px altura máx)
4. Ex: embalagem frente
5. Ex: camiseta serigrafia
### O QUE O LOGO NÃO PODE TER (restrições explícitas):
- Proibição 1 (ex: "nenhum ícone genérico de pão"):
- Proibição 2 (ex: "sem gradient, cor chata só"):
- Proibição 3:

## D2 — Variantes obrigatórias + arquitetura brandbook
### Variantes logo OBRIGATÓRIAS (≥6):
1. Primary horizontal full (wordmark + ícone lado)
2. Secondary stacked vertical (wordmark abaixo do ícone)
3. Monochrome preto (1 cor fill único, sem gradiente)
4. Monochrome branco (1 cor fill único, reverse)
5. Icon / pictorial mark only (quadrado)
6. Lettermark / monograma iniciais (quadrado)
7. (opcional) Favicon 64×64 SVG
### Nomes arquivos SVG finais (HARD gate D6):
- `vectors/logo-primary.svg`
- `vectors/logo-stacked.svg`
- `vectors/logo-monochrome-black.svg`
- `vectors/logo-monochrome-white.svg`
- `vectors/logo-icon.svg`
- `vectors/logo-monogram-<INICIAIS>.svg`
### Brandbook (6 seções mínimo):
1. Capa (nome marca + slogan + logo primary + data)
2. Logos e variantes (todas 6 SVGs + clear-space + min-size table)
3. Paleta de cores (nomes + hex + usos: primary / secondary / texto / fundo)
4. Tipografia (Display wordmark + Body + weights + line-height + exemplos)
5. Aplicações reais (≥3 mockups PNG 2×: perfil IG / cartão / header site)
6. DO and DON'T (≥3 DO + ≥3 DON'T, cada um com explicação curta)

## D3 — SVG gates finais (HARD — falha = STOP):
- Cada SVG ≤ 128KB
- Cada SVG: ZERO `<image>`, ZERO base64, ZERO `<foreignObject>`, ZERO links externos
- viewBox (square: `0 0 1024 1024` ou proporção natural ex: `0 0 1536 512` para horizontal)
- Monochrome preto e branco: 100% fill único (checar via grep fill= 1 única cor não transparente)
- Todos SVGs parse XML válido (Python xml.etree.ElementTree)

---
## Assinatura
**Aprovador (usuário):** _________________________  Data: ________
Resposta esperada para continuar: "Sim, aprovo spec MODE D. Pode executar etapas D0 → D4."
```

---

## 🛠 10. SNIPPETS CANÔNICOS (colar direto)
### 10.1 Validação unique colors Python (rodar POR PEÇA após export)
```python
import struct,zlib,os,hashlib
def validate_png(p:str, min_colors=25000, photo_expected=True)->tuple[bool,str]:
    with open(p,'rb') as f: d=f.read()
    is_png = d[:8].hex()=='89504e470d0a1a0a'
    placeholder = b'The image is generating' in d or b'refresh page' in d
    i=8; idat=b''; w=h=ct=0
    while i<len(d):
        L=struct.unpack('>I',d[i:i+4])[0]; ctt=d[i+4:i+8].decode('latin1'); cd=d[i+8:i+8+L]
        if ctt=='IHDR': w,h,_,ct,_,_,_=struct.unpack('>IIBBBBB',cd)
        if ctt=='IDAT': idat+=cd
        i+=12+L
    bpp={0:1,2:3,3:1,4:2,6:4}[ct]; stride=w*bpp+1
    try:
        raw=zlib.decompress(idat); seen=set()
        for ln in range(h):
            s=ln*stride+1; buf=raw[s:s+(stride-1)]
            for pi in range(0,len(buf)-bpp+1,bpp):
                seen.add(tuple(buf[pi:pi+bpp]))
                if len(seen)>600000: break
            if len(seen)>600000: break
        uc=len(seen)
    except:
        uc=0
    md5=hashlib.md5(d).hexdigest()[:12]; sz=os.path.getsize(p)//1024
    ok=True; reasons=[]
    if not is_png: ok=False; reasons.append('not_png')
    if placeholder: ok=False; reasons.append('placeholder_endpoint')
    if photo_expected and uc<min_colors: ok=False; reasons.append(f'low_colors(<{min_colors}):{uc}')
    return ok, f"{os.path.basename(p):42s} {w}x{h} {sz:>4d}KB uc={uc:>6d} md5={md5} {'OK' if ok else 'FAIL:'+','.join(reasons)}"
```

### 10.2 Fallback offline composição Pillow (3.1.4 — colar foto sobre PNG base texto)
```python
from PIL import Image, ImageDraw, ImageFilter, ImageOps
def compose_photo_onto_base(base_png:str, foto_png:str, out_png:str, *,
                             x:int,y:int,FW:int,FH:int, radius:int,
                             border_px:int, shadow_alpha:int=96,
                             dark_overlay_rgba:tuple[int,int,int,int]|None=None):
    base = Image.open(base_png).convert("RGBA")
    foto = ImageOps.fit(Image.open(foto_png).convert("RGBA"),(FW,FH),Image.LANCZOS,centering=(.5,.5))
    # Foto clip radius
    mask = Image.new("L",(FW,FH),0); ImageDraw.Draw(mask).rounded_rectangle((0,0,FW,FH),radius=radius,fill=255)
    foto.putalpha(mask)
    # Moldura
    MS = (FW+border_px*2, FH+border_px*2); MR = radius + border_px//2 + 2
    moldura = Image.new("RGBA", MS, (0,0,0,0)); ImageDraw.Draw(moldura).rounded_rectangle((0,0,*MS),radius=MR,fill=(255,255,255,255))
    # Shadow
    SPAD=14*3; SZ=(MS[0]+SPAD*2, MS[1]+SPAD*2)
    shadow=Image.new("RGBA",SZ,(0,0,0,0)); ImageDraw.Draw(shadow).rounded_rectangle((SPAD,SPAD,SPAD+MS[0],SPAD+MS[1]),radius=MR,fill=(0,0,0,shadow_alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=14))
    # Colar
    out = base.copy()
    out.alpha_composite(shadow,(x-border_px-SPAD+4, y-border_px-SPAD+8))
    out.alpha_composite(moldura,(x-border_px, y-border_px))
    out.alpha_composite(foto,(x,y))
    if dark_overlay_rgba:
        ov=Image.new("RGBA",(FW,FH),(0,0,0,0)); ImageDraw.Draw(ov).rounded_rectangle((0,0,FW,FH),radius=radius,fill=dark_overlay_rgba)
        out.alpha_composite(ov,(x,y))
    out.save(out_png,"PNG",optimize=True)
```

### 10.3 MODE D — Validação SVG vetor puro (rodar POR VARIANTE após export D3)
```python
import os,re,xml.etree.ElementTree as ET
def validate_svg_logo(path:str,min_variants:int=6)->tuple[bool,str]:
    if not os.path.exists(path):
        return False,f"{os.path.basename(path):48s} MISSING"
    with open(path,'rb') as f: raw=f.read(); sz=os.path.getsize(path)//1024
    try:
        root=ET.fromstring(raw)
        tag=lambda x: x.split('}')[-1] if '}' in x else x
        # D1: sem image / foreignObject / base64 data URI
        forbidden_tags={'image','foreignObject','use'}
        bad_tags=[e.tag for e in root.iter() if tag(e.tag) in forbidden_tags]
        has_b64=b'data:image' in raw or b'base64' in raw
        # D3: viewBox exists
        vb=root.attrib.get('viewBox','')
        # Monochrome check heuristic: count unique fill hex
        fills=set(re.findall(r'fill\s*=\s*["\'](#[0-9a-fA-F]{3,8})["\']',raw.decode('utf-8','ignore')))
        mono_ok = len(fills)<=2  # ≤2 cores não transparente (1 fill + maybe stroke same)
        xml_ok = True
    except ET.ParseError as e:
        return False,f"{os.path.basename(path):48s} sz={sz:>3d}KB XML_INVALID: {str(e)[:40]}"
    ok=True; r=[]
    if sz>128: ok=False; r.append(f'oversize({sz}KB>128KB)')
    if bad_tags: ok=False; r.append('bad_tags:'+','.join(tag(x) for x in bad_tags[:3]))
    if has_b64: ok=False; r.append('b64_or_datauri')
    if not vb: ok=False; r.append('no_viewBox')
    return ok,f"{os.path.basename(path):48s} sz={sz:>3d}KB fills={len(fills)} vb={bool(vb)} mono~{mono_ok} {'OK' if ok else 'FAIL:'+','.join(r)}"
```

### 10.4 MODE D — Export PNG 2× de todos SVG (via cairosvg OU Pillow fallback)
```python
def rasterize_svgs_to_png2x(vectors_dir:str, exports_dir:str, scale:int=2):
    import subprocess, pathlib
    V=pathlib.Path(vectors_dir); E=pathlib.Path(exports_dir); E.mkdir(parents=True,exist_ok=True)
    for svg in V.glob('*.svg'):
        out=E/f"{svg.stem}@{scale}x.png"
        # Try cairosvg first, else rsvg-convert, else ImageMagick convert
        for cmd in (["cairosvg",str(svg),"-o",str(out),f"--scale={scale}"],
                    ["rsvg-convert","-o",str(out),"-w",str(2048),str(svg)],
                    ["convert","-density",str(144*scale),str(svg),str(out)]):
            try:
                if subprocess.run(cmd,capture_output=True,timeout=30).returncode==0: break
            except FileNotFoundError: continue
```

---

## 🧩 11. DESIGN BACKEND SELECTION

Canonical contract: `references/DESIGN_BACKEND_CONTRACT.md`.

Available drivers:

- `openpencil` → `references/backends/OPENPENCIL.md`
- `figma` → `references/backends/FIGMA.md`
- `spec-only` → SPEC/dev-spec only; STOP before pixel execution

Selection is capability-based, not IDE-based.

User explicit backend choice has precedence when that capability exists.

If the requested backend capability is unavailable, FAIL CLOSED instead of silently switching design engines.

---

## 🧰 12. MODE D — SVG Logo Reference (vetor booleano & clean-up)
### 12.1 Vetor puro & booleans (HARD para logo)
1. **WORDMARK**: se display/script, ideal converter outlines em paths via OpenPencil `boolean_union` ANTES de exportar SVG (garante render sem depender de fonte instalada).
2. **SÍMBOLO/MONOGRAMA**: construir SEMPRE com primitivos (rect / circle / path bezier) → depois `boolean_union/subtract/intersect` para único contorno. Evitar 12 camadas sobrepostas que geram artefatos.
3. **CLEAN-UP OBRIGATÓRIO ANTES EXPORT SVG**: remove layers vazias / invisíveis / duplicates; flatten groups desnecessários. Nomes camadas finais: `wordmark` / `icon` / `monogram` / `bg`.

### 12.2 Regras WCAG & contraste no logo
- Variante primary: contraste logo contra fundo claro (branco / bg spec) ≥ 3:1 para legível em header 48px+.
- Variante monochrome branca: testar SEMPRE contra fundo #111827 escuro da própria paleta.
- Clear-space mínimo documentado no brandbook 02-logos-e-variantes: **0.5× a altura do X do wordmark em TODOS os lados do bounding box do logo.**

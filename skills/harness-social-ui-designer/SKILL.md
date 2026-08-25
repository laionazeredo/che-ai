---
name: "harness-social-ui-designer"
description: "Design pipeline: social media creatives (images+copy), UI/UX features, or design systems — using local OpenPencil MCP (Figma-equivalent). Invoke when user says '/harness-design', '/harness-figma', asks for posts/stories/creatives, UI screens, or a Tailwind/Figma design system."
---

# Harness — Social UI Designer (Orchestrator)

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo aqui):**
> - Response formatting + verbosity: `engineering-contracts` skill §18
> - Output shape canônico (Status/Mudanças/Refs/Aprofundar): `HARNESS_RULES.md` §🔴 RESPOSTAS ENXUTAS
> - Design tokens variables + Tailwind sync: `engineering-contracts` skill (Design systems references)
> - Text-to-image endpoint (MANDATORY para imagens criativas): `user_rules/rule-1786391353377.md` Image Guidelines

This is the **top-level orchestrator skill** for the global design harness.
It creates **production-grade designs locally** using the `mcp_open-pencil` MCP server — Figma-equivalent tools, completely local.
3 mutually exclusive operating modes (choose ONE at the start via `AskUserQuestion`):
- **MODE A → Social Media Creatives**: batch of 6 posts + professional copy (headlines/CTAs).
- **MODE B → UI/UX Feature Design**: wireframes → high-fidelity → dev-spec (React/Tailwind).
- **MODE C → Design System**: Tailwind 4 tokens → Figma variables + atomic component library.

---

## 0. NON-NEGOTIABLE PRE-FLIGHT (run BEFORE anything)

### 0.1 Trigger: modo escolhido ou pergunta ao user

If the user's request already specifies a clear mode → pick it directly. Otherwise — **STOP immediately** and ask via `AskUserQuestion`:

```
Qual modo quer rodar?
A) Social Media (posts / stories / reels templates + copy profissional)
B) UI/UX Feature (wireframes → hi-fi → dev spec)
C) Design System (tokens Tailwind → variáveis Figma + components)
```

### 0.2 Pergunta Figma-project / save-path (HARD — resposta do user requisito)

The user's request said: *"disparar o harness, ele me perguntar em que projeto do figma eu quero que ele trabalhe e ele faça o resto direto no figma"*.

Since we run locally via `mcp_open-pencil` (not cloud Figma API — see section 8 for MCP comparison), translate this question into an **OpenPencil save path** ask via `AskUserQuestion`:

```
Onde quer salvar o arquivo de design (equivalente ao seu "projeto Figma")?
Forneça um caminho absoluto em /home/laion. Ex: "/home/laion/designs/flockr-social-0824.pen"
  - Deixe vazio default → crio em /home/laion/.trae/designs/<modo>-<slug>-YYYYMMDD.pen
```

Create `.trae/designs/` directory if it does not exist.

When user provides path:
- Initialize via `mcp_open-pencil.new_document(path: <ABSOLUTE_PATH>)`.
- Store `DESIGN_FILE_PATH` variable for the entire session.
- Store `OPEN_PENCIL_DOCUMENT_ID` (if returned) for future tool calls.

### 0.3 Pergunta brandbook / referências de marca

Ask user (3 bullets, short):
- **Cor primária / paleta**: se tem hex codes, ou quer "sugerir paleta baseada em nome do produto".
- **Tipografia**: se tem fonte específica (Ex: Inter, Poppins, Space Grotesk) — default = Inter.
- **Tom de voz (copywriting)**: "Divertido / Jovem / Sério / Luxo / Informal UK" — default = "Profissional mas acessível".

---

## 1. MODE A — Social Media Creatives Pipeline

**Goal:** Deliver 6 creatives = 2 × Feed (1080×1080) + 2 × Stories (1080×1920) + 2 × Reels Template (1080×1920).
All with: (1) professional copy, (2) generated background/hero image, (3) correct grid alignment, (4) contrast AA.

### 1.1 Scope capture (≤5 perguntas concisas)

Ask via `AskUserQuestion` (4 answers min before moving on):
1. **Tema / produto do criativo**: Ex "Lançamento evento Flockr — festival de música UK"
2. **USP principal (1 frase)**: Ex "Primeiro app com tickets em NFT sem gas fee"
3. **CTA final**: Ex "Baixar app / Comprar ingresso / Seguir perfil"
4. **Paleta e tom**: (if unanswered in 0.3)
5. **Referências (opcional)**: 2-3 URLs de criativos que o usuário gosta, ou None.

### 1.2 Step A1: Gerar 3 variações de copy p/ cada tamanho

For EACH of 6 pieces → write (short, ≤2 lines each):
- **Headline** (max 8 words)
- **Subline** (max 12 words)
- **Body** (2 bullets max)
- **CTA button text** (max 4 words)

Language default: PT-BR unless user specified EN/UK.

Present them to user. Ask approval: **A) Aprovar todos copies / B) Ajustar o copy X**.
Fail-fast: 2 rounds of B sem aprovar → re-fazer scope capture §1.1.

### 1.3 Step A2: Gerar 6 imagens de fundo/hero via Text-to-Image (HARD RULE)

Use the MANDATORY endpoint from user_rules Image Guidelines:

```
https://coresg-normal.trae.ai/api/ide/v1/text_to_image?prompt={URL_ENCODED_PROMPT}&image_size={SIZE}
```

| Piece | Size | image_size |
|---|---|---|
| Feed 1080×1080 | 1:1 | `square_hd` |
| Stories 1080×1920 | 9:16 | `portrait_16_9` |
| Reels template 1080×1920 | 9:16 | `portrait_16_9` |

Prompt rules (SDXL best-practices — from web research):
- Be **concrete and visual**, not abstract. Ex: "event poster for UK indie music festival, gradient purple-orange background, bokeh concert lights foreground, no text".
- Always end with `, professional photography, high contrast, 4k, rule of thirds composition, no text`.
- For brands: include palettes keywords. Ex: "flockr-brand deep-purple #6D28D9 and gold F59E0B accents".

Save the 6 downloaded images locally to:
```
/home/laion/.trae/designs/assets/<slug>-<piece-type>-<idx>.png
```

### 1.4 Step A3: Compose designs in OpenPencil (MCP tools calls)

For each of 6 pieces:

1. **Create 2 pages if needed**, or use 6 SECTIONS inside a single page.
2. For each creative:
   - `create_shape(type: FRAME, x, y, width: 1080, height: 1080|1920, name: Feed-01/Story-01 etc.)` → get frame ID.
   - **Set image fill as background**: `set_image_fill(id: <FRAME_ID>, path: <local path to generated PNG>)`. (Requires checking tool descriptor first — Step 2.3 in rules.)
   - Overlay headline TEXT shape + Subline + CTA RECTANGLE button (rounded via `set_radius`) with solid contrast fill → text inside button.
   - Apply brand colors via `set_fill(color: "#HEX")` on texts/buttons.
   - Apply `set_effects(id, drop_shadow_4px)` on CTA button.
3. Convert every creative FRAME to a **Component** so user can re-instance: `create_component(id: <FRAME_ID>)`.

### 1.5 Step A4: Exportar deliverables

Run `export_image(ids: [<all 6 frame ids>], format: PNG, scale: 2, path: /home/laion/.trae/designs/exports/<slug>-<name>.png)` — exports 2× hi-res PNGs (post-production ready).

Also save the source: `save_file(path: <DESIGN_FILE_PATH>)`.

### 1.6 Mode-A Delivery Summary (§18 shape)

Show to user:
- ✅ 6 PNGs exported links (paths clickable).
- ✅ Source `.pen` file (OpenPencil / Figma-equivalent).
- ✅ 1 oferta Aprofundar: *"Quer uma 2ª leva com mais 6 criativos usando tom de voz diferente?"*

---

## 2. MODE B — UI/UX Feature Design (Wireframes → Hi-fi → Dev Spec)

**Goal:** Deliver (1) low-fi wireframes, (2) high-fidelity screens, (3) dev-spec (Tailwind classes list + Figma variables exported as tokens).
Uses `mcp_open-pencil` + optionally imports Tailwind tokens from existing project `packages/ui/tailwind.config`.

### 2.1 Scope Capture (≤6 questions via AskUserQuestion)

1. **Feature / tela**: Ex "Tela Dashboard Creator — vendas por evento no Flockr"
2. **Persona / user role**: Admin Creator / Public Attendee / Scanner Staff
3. **User goal (1 job story)**: "When I open dashboard, I want sales-by-event chart, so I know which event to promote."
4. **3 core behaviors max**: (never more than 3 visible → §18 rule)
5. **Existe projeto Figma/OpenPencil pra reutilizar componentes?**: path se sim.
6. **Dark mode + Light mode?**: Yes (default) / No (light only).

### 2.2 Step B1: Low-fidelity Wireframes (1 round)

- 1 SECTION page inside the open document.
- Use only: create_shape(FRAME/RECTANGLE/TEXT/SECTION), `set_stroke` on boxes, labels como "Hero Title" / "CTA Button" + "Image placeholder" rects (grey fills light).
- **NO gradients, NO photos, NO font choices yet** — only structure.
- 2–3 screens max in first pass.

Present to user: A) Aprovar wireframes / B) Mover seção X / C) Remover tela Y.
Max 2 rounds. If still blocked → return to scope capture.

### 2.3 Step B2: Apply design tokens / brand

Create variables collection (if not already exists):

```
create_collection(name: "Flockr Design Tokens")
create_variable(collection_id, name: "color/brand/primary", type: COLOR, value: "#6D28D9")
create_variable(collection_id, name: "radius/sm", type: FLOAT, value: "6")
create_variable(collection_id, name: "typography/heading", type: STRING, value: "Inter Bold")
```

Núcleo mínimo de variáveis (Schema 2025 best practices — Extended Collections idea):
- **Color**: brand-primary / brand-secondary / bg / surface / text-primary / text-secondary / border / success / danger / warning
- **Radius**: xs / sm / md / lg / xl / pill
- **Spacing**: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64
- **Typography**: heading / body / caption (font families)

### 2.4 Step B3: High-fidelity pass

Over wireframes skeleton:
- Apply fills via `set_fill(id, color: variable-name)` em caixas.
- **Fonts & sizes**: `set_font(id, family: "Inter", weight: 700, size: 40, line_height: 44)` on headings.
- **Rounded corners**: `set_radius(id, radius: 12)` on cards.
- **Gradients**: Background hero = `set_fill(id, color: "#6D28D9", color_end: "#F59E0B", gradient: "left-right")`.
- **Hero image**: Use text-to-image endpoint for the feature if needed, then `set_image_fill` on the frame.
- **Components**: Convert Button / Card / Input boxes to components (reuse).

### 2.5 Step B4: Export Dev Spec (TWO formats)

1. **Tokens → Tailwind**: Run `design_to_tokens(format: "tailwind")` → output pastable into `packages/ui/tailwind.theme.ts` (Flockr stack).
2. **SVG + PNG exports**: Export screens via `export_image(format: PNG, scale: 2, path: …)` + key components as `export_svg(ids: [...])` para SVGs otimizados.
3. **Dev-spec one-pager**: Write to `/home/laion/.trae/designs/<slug>/dev-spec.md` (15 lines max: component list, tokens, responsive breakpoints).

### 2.6 Mode-B Delivery Summary (§18 shape)

- ✅ Hi-fi screens (PNG 2× exported).
- ✅ `design_to_tokens tailwind` output pasteable.
- ✅ Components library (Buttons/Cards) as OpenPencil components.
- ✅ 1 Oferta: *"Quer que eu já implemente esses screens em React + Tailwind 4 no worktree?"*

---

## 3. MODE C — Design System (Tailwind 4 ↔ OpenPencil/Figma variables)

**Goal:** Bidirectional sync core: (1) extract tokens de um Tailwind config existente → create variables no OpenPencil; (2) criar biblioteca de 12 componentes atômicos (Button, Card, Input, Textarea, Select, Checkbox, Radio, Toggle, Badge, Avatar, Alert, Modal header) — variants primary/secondary/ghost/destructive (shadcn style, match @flockr/ui if present).

### 3.1 Scope capture (2 perguntas)

1. **Origem dos tokens**: A) Ler de `packages/ui/tailwind.config` (padrão Flockr) / B) Criar do zero (escolher paleta + tipografia).
2. **Componentes obrigatórios**: 12 atomic acima é default, mas user pode reduzir se quiser.

### 3.2 Step C1: Variables Collection (Light + Dark Modes)

Following Figma Schema 2025 Extended Collections pattern (Modes):
- **Collection**: `Flockr DS`
- **Mode 1**: `Light` — default values.
- **Mode 2**: `Dark` — invert surface/bg/text pairs.
- Criar ~60 variáveis (color / spacing / radius / typography / shadow / opacity).

Use semantic naming (colorfyi.com guide best practices):
- `color/brand/50 → 900` (raw palette)
- `semantic/bg/primary` → references `color/neutral/0` (light) or `color/neutral/950` (dark).
- NEVER use raw hex on layers. Always bind to semantic vars.

### 3.3 Step C2: Component library atomic

For every of 12 components: create FRAME → set layout (padding min/max / auto layout) → set fills/radius/bind variables → add 4 variants frames (primary/secondary/ghost/destructive) next to it → group into SECTION per component → finally `create_component(id: <FRAME_ID>)`.

Componentes mínimos:
- **Button**: variants primary / secondary / outline / ghost / destructive + sizes sm/md/lg + disabled state.
- **Card**: padding 24, radius 16, shadow-sm, header/body/footer auto-layout slots.
- **Input / Textarea**: border color, focus ring via stroke+effects, label+caption above/below.
- **Avatar / Badge / Alert / Modal header / Toggle**.

### 3.4 Step C3: Export

Run:
- `design_to_tokens(format: tailwind)` → Tailwind theme.
- `design_to_tokens(format: css)` → `:root { --flockr-* }` custom properties CSS file.
- `design_to_tokens(format: json)` → DTCG-approx JSON for other tools.

Save all 3 outputs to: `/home/laion/.trae/designs/<ds-slug>/tokens/`

### 3.5 Mode-C Delivery Summary (§18 shape)

- ✅ 12 componentes × 4 variantes = 48 variants library.
- ✅ 3 exports tokens (Tailwind / CSS / JSON).
- ✅ Source `.pen` design-system library reutilizável.
- ✅ 1 Oferta: *"Quer que eu sincronize os tokens exportados p/ dentro de packages/ui/tailwind.config.ts no worktree?"*

---

## 4. Quality Gates (HARD FAIL se não passar)

Every deliverable (ANY MODE) must satisfy BOTH:

4.1 **Contraste AA WCAG**: Text on backgrounds ≥ 4.5:1 for body, 3:1 for large text. Quick check via `analyze_colors` tool if in doubt. If failing → ajustar hex codes.
4.2 **Nenhum raw hex em layers visuais**: Tudo ligado a uma variable (MODE C obrigatório; MODE B obrigatório em fills de sistema; MODE A opcional se for criativo único).
4.3 **Exportadas em scale 2 (2x)**: Sempre 2160px para feeds, 2160×3840 para stories/reels.
4.4 **Nomes de layers semânticos**: Nunca "Rectangle 12" ou "Text 4". Sempre "Card-bg", "CTA-Buy-Ticket", etc.

If any gate fails in final QA → fix antes de mostrar entrega.

---

## 5. Fail-fast Rules (ANY MODE)

- **2 iterações scope capture ainda ambíguo** → pergunta em 1 linha: *"Quer que eu sugiro defaults e prossiga? A) Sim, defaults e vai / B) Não, vou detalhar mais agora"*.
- **2 rounds ajustes copies/layouts ainda não aprovado** → voltar Scope Capture.
- **Imagens geradas violarem prompt (têm texto, low quality)** → regenerar antes de compor.

---

## 6. Output (§18 shape obrigatório)

TODAS as respostas intermediárias seguem shape canônico 4 seções:

```
### 📍 Status <1 frase curta>
### 🧩 Mudanças-chave (≤3 bullets)
  • **<Rótulo>**: <1 thought, ≤2 linhas>
### 🔗 Refs (≤5 links)
  • [<NOME_ARQUIVO curto>](file:///path)
### ❓ Aprofundar
Quer aprofundar em **<UMA ÚNICA coisa>**? (Sim / Não)
```

---

## 7. File Naming Convention (outputs)

```
/home/laion/.trae/designs/
  ├── <slug>-YYYYMMDD.pen                          # Source file (OpenPencil/Figma-equivalent)
  ├── assets/
  │   └── <piece>.png                              # Generated hero images
  ├── exports/
  │   └── <slug>-<nome-criativo|tela>.png          # Final PNGs (2×)
  ├── tokens/ (MODO C only)
  │   ├── tokens.tailwind.txt
  │   ├── tokens.css
  │   └── tokens.json
  └── dev-spec.md (MODO B only)                    # 15 lines
```

---

## 8. MCP Comparison (Resposta à dúvida: "usar Figma MCP?")

**RESUMO EXECUTIVO (≤3 bullets):**
• **Backend atual**: `mcp_open-pencil` — 140+ tools, **100% local**, equivalente a Figma desktop (criar nodes / variables / components / export tokens / PNG SVG). Vantagens = zero auth, sem cloud round-trips, sem limites de API.
• **Backend alternativo (MISSING hoje)**: Figma Cloud MCP oficial / figma-console-mcp (github southleft v1.39.1) para criar designs DIRETAMENTE em projeto Figma cloud via Personal Access Token. Tem `figma_setup_design_tokens` atomico e integra Code Connect, mas exige token, rede, rate limits.
• **Recomendação HARD do harness**: `mcp_open-pencil` por padrão (melhor UX: "perguntar path → fazer tudo local") — que é o que este skill usa. **Se o user realmente pedir salvar em cloud Figma**, podemos adicionar `figma-console-mcp` como backend secundário em v2 (perguntar PAT + file key). Hoje NÃO implementamos cloud Figma por simplicidade KISS.

---
name: "harness-social-ui-designer"
description: "V2 — Design pipeline: social media creatives or UI/UX features. MANDATORY FLOW: (1) Spec detalhada escrita + iteração usuário → APROVAÇÃO EXPLÍCITA GATE; (2) Execução em ETAPAS (≤4); (3) Revisor visual por etapa valida alinhado spec; (4) Fallback composição offline (Pillow/ImageMagick) + Unsplash foto real. Usa mcp_open-pencil local Figma-equivalent. Trigger: /harness-design, /harness-figma, posts/stories/screens."
---

# Harness — Social UI Designer (Orchestrator) v2.0

> **SHARED REFERENCES (CANONICAL — NÃO DUPLICAR corpo):**
> - **Formatting + verbosity ≤500w**: engineering-contracts §18 (subtítulos ## / ###, bullets ≤2 linhas, bold keywords)
> - **Hard-won session lessons** (composição offline / template text nodes / validação unique colors): §3 abaixo
> - **Design tokens + Tailwind**: engineering-contracts skill (DS section)
> - **Image source fallback waterfall**: §3 item #1 (Unsplash real > text_to_image endpoint > G(search) headless)

Este é o **orquestrador top-level** do design harness. Backend = `mcp_open-pencil` local (equivalente a Figma desktop, sem auth/limites).
**3 modos mutuamente exclusivos** (escolher 1 no início via `AskUserQuestion`):
- **MODE A → Social Media Posts**: posts 1:1 / stories 9:16 + copies profissionais.
- **MODE B → UI/UX Feature**: wireframes → hi-fi → dev-spec (React/Tailwind 4).
- **MODE C → Design System**: Tailwind 4 tokens ↔ OpenPencil variables + componentes atômicos.

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

#### 0.2 Escrever spec no disco e pedir aprovação explícita
- Salvar spec em: `/home/laion/.trae/designs/<slug>-spec.md`
- Mostrar spec ao usuário **formatada para leitura diagonal** (tabelas, negrito, bullets).
- Pergunta única de aprovação (obrigatória):
  > **"Aprovo esta spec do jeito que está — pode executar (Sim / Não, ajustar estes X pontos)"**
- Se NÃO → ajustar apenas os pontos listados; re-apresentar; repetir.

---

### GATE 0: Escolher modo A/B/C (se user não especificou)
Se pedido do usuário já indica modo → direto. Senão parar e perguntar via `AskUserQuestion`.

### GATE 1: Save path + brandbook
- **Path projeto (OpenPencil source)**: perguntar caminho absoluto em /home/laion; default `/home/laion/.trae/designs/<modo>-<slug>-YYYYMMDD.pen`.
- **Brandbook (3 bullets curtos)**: paleta hex / tipografia (default Inter) / tom de voz copy (default "Profissional acessível").
- Inicializar documento `mcp_open-pencil.new_document(path: <PATH>)` → guardar `DESIGN_FILE_PATH` e `OPEN_PENCIL_DOCUMENT_ID`.

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
- Copiar spec aprovada para: `/home/laion/.trae/designs/<slug>-spec.APPROVED.md` (SHA256 salvo para revisor comparar).

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

## ✅ 4. QUALITY GATES (HARD FAIL se não passar → fix antes de entregar)
Todos gates aplicam a **QUALQUER MODO** e **toda etapa final**:

1. **CONTRASTE WCAG AA**: Body text ≥ 4.5:1; large text ≥3:1. Checar com `analyze_colors` MCP se dúvida. Overlay dark obrigatório se texto branco + foto luminosa (card forno lenha = exemplo).
2. **IMAGENS VALIDADAS**: (a) `unique colors > 25.000` (§3.3) POR PEÇA que esperava foto; (b) SEM placeholder endpoint (checar bytes + MD5); (c) Tema da foto corresponde à peça.
3. **SEMPRE EXPORT SCALE 2 (2×)**: Feed 2160×2160; Stories 2160×3840; Screens desktop ≥2560 wide.
4. **LAYERS SEM NOMES LIXO**: SEM "Rectangle 12", "Text 4". Sempre: `<Piece>-<Role>` (ex `C1-Headline-Hero`, `CTA-Buy-Ticket`).
5. **FALLBACK OFFLINE OBRIGATÓRIO SE ETAPA 3 FOTOS HEADLESS FALHAR**: Rodar compositor Pillow §3.1.4 (colar foto asset baixada sobre PNG base texto renderizado) — este é o gate final para entregar foto **garantida**.
6. **STORAGE PATHS LIMPOS**: Nenhum output temporário em `/tmp`; todos assets em `/home/laion/.trae/designs/<slug>/assets/`, exports em `/exports/`.
7. **SPEC CHECKSUM**: Saída final **DEVE** corresponder à `APPROVED-spec.md`. Revisor compara item por item (paleta / copies verbatim / layout / dimensão).

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
/home/laion/.trae/designs/<slug>-YYYYMMDD/
  ├── spec.md                  # Spec draft (iteração)
  ├── spec.APPROVED.md         # Spec SHA256 travada após aprovação (GATE-1)
  ├── source.pen               # OpenPencil source (via save_document; .openpencil cópia idêntica)
  ├── source.openpencil
  ├── assets/
  │   ├── C1-hero.png          # Imagens 1024×1024 (>25k unique colors)
  │   └── C2-flatlay.png
  ├── exports/
  │   ├── FINAL-<piece>@2x.png # Saídas 2160×2160 / 2160×3840
  ├── tokens/ (MODE C only)
  │   ├── tokens.tailwind.txt / tokens.css / tokens.json
  └── dev-spec.md (MODE B only, ≤15 linhas)
```

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

---

## 🧩 11. MCP Backend A/B (comparativo rápido)
- **PADRÃO: `mcp_open-pencil` local → 140+ tools, 100% offline sem auth, sem limites API.** Sempre usar.
- **OPCIONAL futuro: Figma Cloud MCP (github southleft v1.39.1)** → trabalha DIRETO em projetos Figma via PAT + file key; tem Code Connect; mas requer token, rede, rate limits. Adicionar apenas se usuário pedir explicitamente cloud. KISS: manter local por padrão.

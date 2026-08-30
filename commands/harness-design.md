---
description: "Design pipeline 4 modos: Social Media criativos, UI/UX telas, Design System atômico, OU Logotipo & Marca (SVG obrigatório + brandbook). Usa open-pencil MCP local."
arguments:
  - name: mode
    description: "Modo: A (Social Media), B (UI-UX Feature), C (Design System), D (Logotipo & Marca + SVG). Opcional — se omitido, pergunta."
    required: false
  - name: path
    description: "Caminho absoluto para salvar arquivo .pen (OpenPencil/Figma-equivalente). Default: ~/.trae/designs/<modo>-<slug>-YYYYMMDD.pen"
    required: false
  - name: palette
    description: "Paleta HEX separada por vírgula. Ex: #6D28D9,#F59E0B,#111827,#F9FAFB"
    required: false
  - name: tone
    description: "Tom de voz para copy. Ex: 'Luxo minimalista', 'Conversacional jovem'"
    required: false
  - name: brand-refs
    description: "(Modo D only) URLs de marcas/logos referência separadas por vírgula. Ex: https://nike.com,https://stripe.com"
    required: false
---

IMMEDIATELY invoke the **`harness-social-ui-designer`** Skill.

Preflight (if params omitted from user command):
1. If `mode` is missing → AskUserQuestion: 1 pergunta, 4 opções (A) Social Media / (B) UI-UX / (C) Design System / (D) Logotipo & Marca (SVG + brandbook).
2. If `path` is missing → ask absolute save path (default: `/home/laion/.trae/designs/<mode>-<slug>-YYYYMMDD.pen`).
3. If mode = **D** (Logotipo & Marca):
   - If `brand-refs` OR reference links/logos anexados OR temas NÃO foram fornecidos → garantido pela Skill que vai rodar 5 lotes D1-D5 de perguntas (não precisa perguntar aqui; a Skill já pede).
4. If mode in {A,B,C} and (`palette` or `tone` missing) → ask; reasonable defaults OK if user doesn't care.

Then the Skill executes the selected mode with fail-fast quality gates and WCAG AA.

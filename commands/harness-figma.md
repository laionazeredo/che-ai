---
description: "Alias de /harness-design — mesmo pipeline 4 modos: Social, UI-UX, Design System, OU Logotipo & Marca (SVG + brandbook) via open-pencil MCP."
arguments:
  - name: mode
    description: "A (Social) / B (UI-UX) / C (Design System) / D (Logotipo & Marca SVG + brandbook). Opcional."
    required: false
  - name: path
    description: "Caminho absoluto salvar .pen. Default ~/.trae/designs/..."
    required: false
  - name: palette
    description: "Paleta HEX separada por vírgula"
    required: false
  - name: tone
    description: "Tom de voz copy"
    required: false
  - name: brand-refs
    description: "(Modo D only) URLs marcas/logos referência separadas vírgula. Ex: https://nike.com,https://stripe.com"
    required: false
---

Alias for `/harness-design`. Same behavior:

1. IMMEDIATELY invoke **`harness-social-ui-designer`** Skill.
2. Do the same preflight as /harness-design:
   - mode prompt: 4 opções (A Social / B UI-UX / C Design System / **D Logotipo & Marca SVG**) se faltar;
   - path prompt se faltar;
   - brand-refs / referências marca (Modo D): se faltar a Skill faz 5 lotes de perguntas D1-D5 automaticamente;
   - palette/tone prompt se faltar e modo ∈ {A,B,C}.
3. Proceed with Skill execution.

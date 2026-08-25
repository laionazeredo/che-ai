---
description: "Alias de /harness-design — mesmo pipeline: Social, UI-UX ou Design System via open-pencil MCP."
arguments:
  - name: mode
    description: "A (Social) / B (UI-UX) / C (Design System). Opcional."
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
---

Alias for `/harness-design`. Same behavior:

1. IMMEDIATELY invoke **`harness-social-ui-designer`** Skill.
2. Do the same preflight as /harness-design (mode prompt, path prompt, palette/tone prompt if missing).
3. Proceed with Skill execution.

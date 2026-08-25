---
description: "Design pipeline: Social Media criativos, UI/UX telas, ou Design System atômico. Usa open-pencil MCP local."
arguments:
  - name: mode
    description: "Modo: A (Social Media), B (UI-UX Feature), C (Design System). Opcional — se omitido, pergunta."
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
---

IMMEDIATELY invoke the **`harness-social-ui-designer`** Skill.

Preflight (if params omitted from user command):
1. If `mode` is missing → AskUserQuestion: 1 pergunta, 3 opções (A) Social Media / (B) UI-UX / (C) Design System.
2. If `path` is missing → ask absolute save path (default: `/home/laion/.trae/designs/<mode>-<slug>-YYYYMMDD.pen`).
3. If `palette` or `tone` missing → ask; reasonable defaults are OK if user doesn't care.

Then the Skill executes the selected mode with fail-fast quality gates and WCAG AA.

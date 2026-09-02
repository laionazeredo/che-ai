---
description: "Design V4 backend-neutral para Social Media, UI/UX, Design System ou Logotipo & Marca."
arguments:
  - name: mode
    description: "Modo: A (Social Media), B (UI-UX Feature), C (Design System), D (Logotipo & Marca + SVG). Opcional — se omitido, pergunta."
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

IMMEDIATELY invoke the **`harness-social-ui-designer`** Skill and pass through
the user-provided neutral design inputs.

The Skill owns missing-input collection, backend capability detection and backend
selection. OpenPencil remains supported when selected from the capabilities
available in the Trae session.

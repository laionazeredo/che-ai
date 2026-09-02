---
description: "Design V4 com preferência explícita por backend Figma quando disponível no runtime Trae."
arguments:
  - name: mode
    description: "A (Social) / B (UI-UX) / C (Design System) / D (Logotipo & Marca SVG + brandbook). Opcional."
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

IMMEDIATELY invoke the **`harness-social-ui-designer`** Skill with an explicit
request for backend=`figma`, passing through the user-provided neutral design inputs.

The Skill owns missing-input collection and capability detection. If Figma is not
available in the Trae session, fail closed and report the unavailable capability;
do not silently switch to an incompatible backend.

---
description: "Design V4 backend-neutral for Social Media, UI/UX, Design System, or Logo & Branding."
arguments:
  - name: mode
    description: "Mode: A (Social Media), B (UI-UX Feature), C (Design System), D (Logo & Branding + SVG). Optional — if omitted, prompt user."
    required: false
  - name: palette
    description: "Comma-separated HEX palette. Ex: #6D28D9,#F59E0B,#111827,#F9FAFB"
    required: false
  - name: tone
    description: "Copy tone of voice. Ex: 'Minimalist luxury', 'Young conversational'"
    required: false
  - name: brand-refs
    description: "(Mode D only) Comma-separated reference brand/logo URLs. Ex: https://nike.com,https://stripe.com"
    required: false
  - name: source-ref
    description: "Figma design/file URL or existing local .pen/.openpencil file. Recognizable unsupported references fail closed."
    required: false
  - name: backend
    description: "Explicit backend request: figma or openpencil. Must match source-ref when both are provided."
    required: false
---

IMMEDIATELY invoke the **`che-social-ui-designer`** Skill and pass through
the user-provided neutral design inputs.

The Skill owns design-source classification, missing-input collection, backend
capability detection and backend selection. Pass `source-ref` verbatim and treat
`backend` as `requested_backend`. OpenPencil remains supported when selected from
the capabilities available in the session.

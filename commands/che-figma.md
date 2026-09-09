---
description: "Design V4 with explicit preference for Figma backend when available in runtime. Alias of /che-design — same 4-mode pipeline: Social, UI-UX, Design System, OR Logo & Branding (SVG + brandbook)."
arguments:
  - name: mode
    description: "A (Social) / B (UI-UX) / C (Design System) / D (Logo & Branding SVG + brandbook). Optional."
    required: false
  - name: palette
    description: "Comma-separated HEX palette"
    required: false
  - name: tone
    description: "Copy tone of voice"
    required: false
  - name: brand-refs
    description: "(Mode D only) Comma-separated reference brand/logo URLs. E.g.: https://nike.com,https://stripe.com"
    required: false
  - name: source-ref
    description: "Figma design/file URL to classify and consume with the Figma capability."
    required: false
---

IMMEDIATELY invoke the **`che-social-ui-designer`** Skill with an explicit
request for backend=`figma`, passing through the user-provided neutral design inputs.
Treat `source-ref` as the verbatim design source and `figma` as the explicit
`requested_backend`. If both `source-ref` and `backend` are provided, they must match.

The Skill owns missing-input collection and capability detection. If Figma is not
available in the session, fail closed and report the unavailable capability;
do not silently switch to an incompatible backend. OpenPencil remains supported
when selected from the capabilities available in the session.

Fallback behavior (alias `/che-design`) — same preflight checks:
32→- mode prompt: 4 options (A Social / B UI-UX / C Design System / **D Logo & Branding SVG**) if missing;
33→- brand-refs (Mode D): if missing, the Skill automatically asks 5 batches of questions D1-D5;
34→- palette/tone prompt if missing and mode ∈ {A,B,C}.

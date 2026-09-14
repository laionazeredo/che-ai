# UX/UI Design — Sub-Capability Map (R1 + R7)

> Single source of truth mapping each design sub-capability to exactly one
> authoritative skill or connector path. Consumers navigate here instead of
> re-discovering backend/capability wiring in the orchestrator.

## Capability table

| Capability | Authoritative path | Mode / scope |
|---|---|---|
| Branding | `skills/che-social-ui-designer/SKILL.md` | MODE D — brand discovery → brandbook |
| Logo & iconography | `skills/che-social-ui-designer/SKILL.md` | MODE D §12 — pure-vector SVG gates |
| UI web | `skills/che-social-ui-designer/SKILL.md` | MODE B — wireframe → hi-fi → dev-spec |
| UI mobile-first | `domains/ux/playbook.md` | breakpoints + responsive layout |
| Design system | `skills/che-social-ui-designer/SKILL.md` | MODE C — Tailwind 4 ↔ OpenPencil variables |
| Social | `skills/che-social-ui-designer/SKILL.md` | MODE A — social creatives 1:1 / 9:16 |

## Backend selection (R7 — fails closed)

Backend selection is capability-based and fails closed. A Figma source is never
silently converted to OpenPencil, and vice-versa.

- Canonical contract: `skills/che-social-ui-designer/references/DESIGN_BACKEND_CONTRACT.md`
- OpenPencil driver: `skills/che-social-ui-designer/references/backends/OPENPENCIL.md`
- Figma driver: `skills/che-social-ui-designer/references/backends/FIGMA.md`
- OpenPencil connector config: `domains/ux/connectors/openpencil.config.md`
- Figma connector config: `domains/ux/connectors/figma.config.md`

# Templates — product domain

Creative / document templates consumed by playbook steps.
Copy and rename for each task rather than writing from scratch.
Use when possible to keep deliverables consistent across agent runs and sessions.

## `PRD.md.template`

Product decision record for the start of the flow (copy into the project's `product/` folder and rename).
It is deliberately **product-focused**: the problem comes first and names no feature; the users table
includes an explicit "explicitly not for" row; the experience section describes the journey rather than the
interface; scope is written with the out-of-scope column first; success metrics pair one primary metric
(with a baseline) against a guardrail that must not regress; and unresolved items are listed as open
questions instead of being answered by guessing.

Architecture, data model, APIs and acceptance criteria are **out of scope by design** — the template states
that they belong to `ARCHITECTURE.md`, `DESIGN.md` and the per-change execution spec, so the boundary
survives review.

Every claim carries a provenance tag: `[data]` (measured), `[research]` (interview / usability session),
`[hunch]` (belief, not yet validated) or `[needs input]` (never invent a number).

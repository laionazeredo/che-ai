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

### Derivation

The sections were chosen from the consensus of widely-used PRD models rather than invented: the
problem-first framing (writing features before the problem is the most-cited PRD failure), a users
table with an explicit exclusion row, non-goals written before goals, a primary metric carrying a
baseline plus a guardrail that must not regress, and a closing list of open questions. The provenance
tags are this template's own addition — they turn "define the problem with evidence, not assumptions"
into a rule that can actually be checked.

**One deliberate deviation:** most PRD models include a "technical approach" section. This one does
not, because a document read by design, copywriting, social and SEO teams has to be legible to all of
them, and Che already routes that content to `ARCHITECTURE.md`, `DESIGN.md` and the per-change
execution spec. The "What this document is NOT" block at the top exists to hold that boundary.

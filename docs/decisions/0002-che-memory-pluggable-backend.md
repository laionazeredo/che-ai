# ADR-0002: Che memory as a pluggable backend (filesystem vs Paperclip)

- Status: Proposed
- Date: 2026-09-18
- Area: memory / decision log / multi-human deployment

## Context

Che's shared team brain is filesystem + git: decisions append to
`decisions.log.jsonl`, specs/tasks/projects live as git-diffable markdown, and
`che_core/state_store.py` maintains a **SQLite index** over those files for
query/search. That model is single-machine: the assets a dev produces with
`che architect` / `che onboarding` stay in their local worktree, so a designer on
another machine regenerates them and the team diverges.

ADR-0001 proved a Paperclip company can be seeded from Che (agents, org chart,
instructions, cron). This ADR extends that to **runtime memory**: when Che runs
inside Paperclip, its memory writes/reads should target Paperclip's shared state
so the whole team shares the same specs, projects, decisions and tasks.

## Decision

Introduce a **pluggable memory backend** behind a `DecisionStore`/`MemoryStore`
interface (Port/Adapter). The filesystem backend is the default and is
byte-for-byte the current behaviour; a Paperclip backend is selected
automatically when `CHE_ENV=paperclip` or any `PAPERCLIP_*` variable is present.

| Che asset (local today) | Filesystem backend (default) | Paperclip backend |
|-------------------------|------------------------------|-------------------|
| decision log (ADR)      | `decisions.log.jsonl`        | `che_decisions` table (separate — see below) |
| specs                   | `specs/*.md`                 | Paperclip `documents` |
| project context/arch    | worktree + `architecture.md` | Paperclip `projects` + `documents` |
| approved task graph     | task graph + envelopes       | Paperclip `issues` (`blockedBy` = `depends_on`) |
| code                    | git worktree                 | Paperclip execution `workspace` |

**Decision-log divergence (verified against source):** Paperclip's `decisions`
is a runtime *option-selection* system (`DecisionSpec = {options, inputs}`,
options carry `effects` that mutate issues, with proposed/accepted/rejected
stats) — **not** a durable ADR log. Che's decision log (`kind`/`title`/`body`/
`tags`, tied to spec/session/worktree) does **not converge** with it. Therefore
Che ADR decisions keep a **separate `che_decisions` table** in Paperclip's
Postgres, while the rest of the knowledge uses Paperclip's native
`documents`/`projects`/`issues`.

## Rationale

- **SSoT per environment, not bidirectional sync.** A project bound to Paperclip
  uses Paperclip/Postgres as SSoT (jsonl is *not* written); a local project uses
  jsonl. No reconciliation loop.
- **No regression.** The filesystem backend is the current code path; existing
  `che` commands resolve to it unchanged when no Paperclip env is present.
- **Reuses an existing seam.** `che_core/state_store.py` already separates
  "files (SSoT)" from "SQL (query index)"; swapping SQLite for Paperclip's
  Postgres is an evolution of that pattern, not a rewrite.
- **Keeps the harness, gains collaboration.** Che remains the guardrail layer
  (DbC gates, spec-by-example, deterministic classification); Paperclip provides
  the shared state, org chart and multi-human membership.

## Consequences

- **Git-diffability trade-off.** In Paperclip mode the SSoT is Postgres, so
  specs/ADRs are no longer git-diffable files. Mitigated by Paperclip's
  company export to markdown (the portability package) as a periodic git snapshot.
- **Spike backend is a shared file, not Postgres yet.** To make routing testable
  without credentials, the first `PaperclipDecisionStore` writes to
  `$PAPERCLIP_HOME/che-shared/decisions.jsonl` (the Paperclip data volume). The
  `che_decisions` Postgres table lands behind the same interface as a follow-up.
- **`che` CLI must be present in the Paperclip container** for the executable
  guards (Mode B), installed via a derived Docker image.
